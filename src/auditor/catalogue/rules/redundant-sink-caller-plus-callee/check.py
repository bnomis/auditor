import ast
import collections
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a function that calls a sink and then a helper that calls the same sink with the same arguments."""
    package_root_name = src_root.name

    def role_tail(expr: ast.expr) -> str:
        """Reduce one argument expression to its role token."""
        tail = ast.unparse(expr)
        if tail.startswith('self.'):
            tail = tail[5:]
        # If attribute access, take the last segment
        tail = tail.rsplit('.', 1)[-1]
        # If still contains underscores (e.g. `patched_config`,
        # `new_run_dir`, `resolved_config`), keep a suffix that
        # preserves the last two underscore-segments for `run_dir`
        # style names, otherwise just the last segment.
        parts = tail.split('_')
        if len(parts) >= 2:
            last_two = '_'.join(parts[-2:])
            tail = last_two if last_two in {'run_dir', 'run_id', 'trial_id', 'split_id', 'split_name'} else parts[-1]
        return tail

    def arg_signature(call: ast.Call) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Normalise a call's arguments into (positional_tails, keyword pairs).

        Normalisation keeps role tokens that survive renames: `patched_config`
        and `self.config` both normalise to `config`. The last underscore-
        separated token is the "role"; common prefixes (`patched_`, `new_`,
        `effective_`, `resolved_`) drop out, so `patched_config` == `config`.
        A keyword is kept as `name=<value tail>`.
        """
        positional = [role_tail(a) for a in call.args if role_tail(a)]
        kwargs = [f'{kw.arg}={role_tail(kw.value)}' for kw in call.keywords if kw.arg is not None]
        return tuple(positional), tuple(sorted(kwargs))

    # First pass: index every project function's sink calls with their signatures.
    function_sinks: dict[str, dict[str, list[tuple[tuple[str, ...], tuple[str, ...]]]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    # function_sinks[func_key][sink_callee] = list of (positional_tails, kwarg_keys)
    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        rel_parts = path.relative_to(src_root).parts
        if rel_parts[-1] == '__init__.py':
            continue
        mod = package_root_name + '.' + '.'.join(rel_parts)[:-3]
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            key = f'{mod}.{node.name}'
            for inner in auditor.api.walk_within_scope(node):
                if not isinstance(inner, ast.Call):
                    continue
                callee = ast.unparse(inner.func)
                callee_tail = callee.rsplit('.', 1)[-1].lower()
                tail_parts = set(re.split(r'[_\W]+', callee_tail))
                if not any(tok in tail_parts for tok in auditor.api.SINK_TOKENS):
                    continue
                function_sinks[key][callee].append(arg_signature(inner))
    if not function_sinks:
        return

    # Build lookup: short_name -> set of full keys
    short_to_full: dict[str, set[str]] = collections.defaultdict(set)
    for key in function_sinks:
        short = key.rsplit('.', 1)[-1]
        short_to_full[short].add(key)

    def resolve_helper(callee: str, module: str) -> list[str]:
        """The project functions a call can mean, by qualified name.

        A dotted callee matches keys ending in that dotted path. A bare name
        matches the calling module's own function, else the single function of
        that name in the project; an ambiguous bare name matches nothing.
        """
        short = callee.rsplit('.', 1)[-1]
        candidates = short_to_full.get(short, set())
        if '.' in callee:
            return sorted(k for k in candidates if k == callee or k.endswith(f'.{callee}'))
        if f'{module}.{callee}' in candidates:
            return [f'{module}.{callee}']
        return sorted(candidates) if len(candidates) == 1 else []

    # Second pass: walk each function. For each direct sink call, look for
    # a later helper call whose target (any full key matching its short name)
    # makes the SAME sink call with the SAME signature.
    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        rel_parts = path.relative_to(src_root).parts
        module = '' if rel_parts[-1] == '__init__.py' else package_root_name + '.' + '.'.join(rel_parts)[:-3]
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            own_key = f'{module}.{node.name}'
            direct_sinks: list[tuple[int, str, tuple[tuple[str, ...], tuple[str, ...]]]] = []
            helper_calls: list[tuple[int, str, list[str]]] = []
            for inner in auditor.api.walk_within_scope(node):
                if not isinstance(inner, ast.Call):
                    continue
                callee = ast.unparse(inner.func)
                tail = callee.rsplit('.', 1)[-1].lower()
                tail_parts = set(re.split(r'[_\W]+', tail))
                if any(tok in tail_parts for tok in auditor.api.SINK_TOKENS):
                    direct_sinks.append((inner.lineno, callee, arg_signature(inner)))
                else:
                    targets = [k for k in resolve_helper(callee, module) if k != own_key]
                    if targets:
                        helper_calls.append((inner.lineno, callee, targets))
            if not direct_sinks or not helper_calls:
                continue
            reported: set[tuple[int, str]] = set()
            for sink_line, sink_callee, sink_sig in direct_sinks:
                sink_tail = sink_callee.rsplit('.', 1)[-1]
                dedup_key = (sink_line, sink_callee)
                if dedup_key in reported:
                    continue
                found_redundant = False
                for helper_line, helper_callee, targets in helper_calls:
                    if helper_line <= sink_line:
                        continue  # only forward-direction redundancy
                    # sorted by resolve_helper, not set order: several modules can
                    # define a function with the same short name, the loop breaks
                    # on the first match, and set iteration follows string
                    # hashing - which is randomised per process.
                    for full in targets:
                        for inner_callee, sigs in function_sinks.get(full, {}).items():
                            if inner_callee.rsplit('.', 1)[-1] != sink_tail:
                                continue
                            if sink_sig not in sigs:
                                continue
                            accept = auditor.api.accept_reason(lines, sink_line, rule='redundant-sink-caller-plus-callee')
                            auditor.api.emit(
                                rule='redundant-sink-caller-plus-callee',
                                variant=f'{node.name} calls {sink_callee}(...) then {helper_callee} which re-calls {inner_callee} with the same args',
                                path=rel,
                                line=sink_line,
                                evidence=(f'direct {sink_callee}{sink_sig[0]} at line {sink_line}; helper {helper_callee} at line {helper_line} -> {full}'),
                                accepted=bool(accept),
                                accepted_reason=accept,
                            )
                            reported.add(dedup_key)
                            found_redundant = True
                            break
                        if found_redundant:
                            break
                    if found_redundant:
                        break
