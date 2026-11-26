import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions that mutate a parameter's dict/list items while
    the function name or docstring suggests pure validation / checking.

    Signal:
      - Function F has parameter P (typed as dict/list or named like
        `merged`, `config`, `data`, `params`).
      - F's name starts with `check_`, `validate_`, `is_`, `has_`,
        `get_`, `compute_`, `resolve_`, `parse_`.
      - F's body contains `P[key] = value` or `P.update(...)` or
        `P.pop(...)` or `P.append(...)` or similar mutation on P.
    """
    # `compute_` is intentionally omitted - HF Trainer's `compute_loss` and
    # similar methods routinely mutate their `inputs` dict. The pure-naming
    # contract does not hold for overridden framework methods.
    PURE_PREFIXES = ('check_', 'validate_', 'is_', 'has_', 'get_', 'resolve_', 'parse_', 'find_', 'count_')
    MUTATION_METHODS = {'update', 'pop', 'append', 'extend', 'insert', 'remove', 'clear', 'setdefault', 'popitem'}
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(node.name.startswith(p) for p in PURE_PREFIXES):
                continue
            param_names = {a.arg for a in node.args.args}
            if not param_names:
                continue
            # Walk body for mutation of a parameter
            for inner in ast.walk(node):
                # item assignment: param[k] = v
                if isinstance(inner, ast.Assign):
                    for tgt in inner.targets:
                        if isinstance(tgt, ast.Subscript) and isinstance(tgt.value, ast.Name):
                            if tgt.value.id in param_names:
                                accept = auditor.api.accept_reason(lines, inner.lineno, rule='parameter-mutation-in-pure-function')
                                auditor.api.emit(
                                    rule='parameter-mutation-in-pure-function',
                                    variant=f'{node.name} mutates parameter `{tgt.value.id}` via item assignment',
                                    path=rel,
                                    line=inner.lineno,
                                    evidence=(lines[inner.lineno - 1].strip()[:200] if inner.lineno <= len(lines) else ''),
                                    accepted=bool(accept),
                                    accepted_reason=accept,
                                )
                # augmented assignment: param[k] += v
                if isinstance(inner, ast.AugAssign):
                    if isinstance(inner.target, ast.Subscript) and isinstance(inner.target.value, ast.Name) and inner.target.value.id in param_names:
                        accept = auditor.api.accept_reason(lines, inner.lineno, rule='parameter-mutation-in-pure-function')
                        auditor.api.emit(
                            rule='parameter-mutation-in-pure-function',
                            variant=f'{node.name} mutates parameter `{inner.target.value.id}` via augmented assignment',
                            path=rel,
                            line=inner.lineno,
                            evidence=(lines[inner.lineno - 1].strip()[:200] if inner.lineno <= len(lines) else ''),
                            accepted=bool(accept),
                            accepted_reason=accept,
                        )
                # method call: param.update(...), param.append(...)
                if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute):
                    if isinstance(inner.func.value, ast.Name) and inner.func.value.id in param_names and inner.func.attr in MUTATION_METHODS:
                        accept = auditor.api.accept_reason(lines, inner.lineno, rule='parameter-mutation-in-pure-function')
                        auditor.api.emit(
                            rule='parameter-mutation-in-pure-function',
                            variant=f'{node.name} mutates parameter `{inner.func.value.id}` via `.{inner.func.attr}()`',
                            path=rel,
                            line=inner.lineno,
                            evidence=(lines[inner.lineno - 1].strip()[:200] if inner.lineno <= len(lines) else ''),
                            accepted=bool(accept),
                            accepted_reason=accept,
                        )
