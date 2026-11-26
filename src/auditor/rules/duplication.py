"""Checks that compare code across files for repeated structure."""

import ast
import collections
import re
import typing

import auditor.core

if typing.TYPE_CHECKING:
    import pathlib

SET_CALL_NAMES = frozenset({'frozenset', 'set'})
SINK_TOKENS = ('dump', 'emit', 'flush', 'log', 'persist', 'publish', 'register', 'save', 'upload', 'write')


def is_pytest_param(node: ast.AST) -> bool:
    """True for a call to `pytest.param`."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'param'
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == 'pytest'
    )


def test_expectation_nodes(tree: ast.AST) -> set[int]:
    """The ids of every node inside an `assert` statement or a `pytest.param(...)` call."""
    inside: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) or is_pytest_param(node):
            inside.update(id(child) for child in ast.walk(node))
    return inside


def check_literal_duplication(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag the same string-literal collection written in two or more places.

    Refinement (2026-11-21): in a test file (a `tests` directory, `test_*.py`,
    `*_test.py` or `conftest.py`) a one-member literal and a literal inside an
    `assert` statement or a `pytest.param(...)` call are expectations, not
    shared data, and are not counted. A multi-member literal in test set-up
    still counts, and so does any literal in source.
    """
    bucket: dict[tuple[typing.Any, ...], set[tuple[str, int, str]]] = collections.defaultdict(set)
    for path in auditor.core.all_py_files(src_root):
        rel = auditor.core.relpath(path, scope)
        tree = auditor.core.read_and_parse(path)
        if tree is None:
            continue
        # Find frozenset(...) / set(...) call nodes so we can skip their inner ast.Set/Tuple child
        skip_inner_nodes: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in SET_CALL_NAMES:
                if node.args and isinstance(node.args[0], (ast.Set, ast.Tuple, ast.List)):
                    skip_inner_nodes.add(id(node.args[0]))
        in_test = auditor.core.is_test_relpath(rel)
        expectation_nodes = test_expectation_nodes(tree) if in_test else set()
        for node in ast.walk(tree):
            if id(node) in skip_inner_nodes or id(node) in expectation_nodes:
                continue
            members = None
            kind = None
            if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
                members = node.elts
                kind = type(node).__name__
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in SET_CALL_NAMES:
                    if node.args and isinstance(node.args[0], (ast.Set, ast.Tuple, ast.List)):
                        members = node.args[0].elts
                        kind = 'frozenset'
            if not members or (in_test and len(members) == 1):
                continue
            consts: list[str] = []
            ok = True
            for m in members:
                if isinstance(m, ast.Constant) and isinstance(m.value, str):
                    consts.append(m.value)
                else:
                    ok = False
                    break
            if not ok or not consts:
                continue
            if kind in {'Set', 'frozenset'}:
                key = ('unordered', tuple(sorted(consts)))
            else:
                key = ('ordered', tuple(consts))
            bucket[key].add((rel, node.lineno, repr(tuple(consts))))
    for key, hits in bucket.items():
        if len(hits) < 2:
            continue
        # A single file can legitimately have two copies at different linenos;
        # that's still a finding. But if the same (path, line) is hit twice,
        # dedup via the set.
        for rel, lineno, evidence in sorted(hits):
            full = scope / rel
            full_lines = auditor.core.source_lines(full)
            accept = auditor.core.accept_reason(full_lines, lineno, rule='literal-duplication')
            auditor.core.emit(
                related=[h[0] for h in hits],
                rule='literal-duplication',
                variant=f'identical {key[0]} literal across {len(hits)} locations',
                path=rel,
                line=lineno,
                evidence=evidence[:200],
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_paired_sibling_helpers(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag module-level functions in two or more files whose bodies are identical.

    Signal: the unparsed body, leaving out docstring and bare-constant
    statements, is the same text in functions of at least two different files.
    Carve-outs: a body shorter than 40 characters is skipped, as is a group
    whose functions all sit in one file. Each member of a group is one hit,
    carrying the other files in `related`.
    """
    bodies: dict[str, list[tuple[str, int, str]]] = collections.defaultdict(list)
    for path in auditor.core.all_py_files(src_root):
        rel = auditor.core.relpath(path, scope)
        tree = auditor.core.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body_src = '\n'.join(ast.unparse(b) for b in node.body if not isinstance(b, ast.Expr) or not isinstance(b.value, ast.Constant))
            if not body_src.strip() or len(body_src) < 40:
                continue
            bodies[body_src].append((rel, node.lineno, node.name))
    for hits in bodies.values():
        if len(hits) < 2:
            continue
        files = {h[0] for h in hits}
        if len(files) < 2:
            continue
        for rel, lineno, fname in hits:
            full = scope / rel
            full_lines = auditor.core.source_lines(full)
            accept = auditor.core.accept_reason(full_lines, lineno, rule='paired-sibling-helpers')
            peers = sorted(set(h[2] for h in hits) - {fname})
            auditor.core.emit(
                related=sorted(files),
                rule='paired-sibling-helpers',
                variant=f'{len(hits)} functions share a body across files',
                path=rel,
                line=lineno,
                evidence=f'def {fname}(...) - matches: {", ".join(peers) or "(peer)"}',
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_duplicate_side_effect_per_target(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag when two or more methods on the same class call the same
    sink function with an argument pointing to the same attribute target.

    Signal:
      - Class C defines methods M1, M2 (M1 != M2, both non-private,
        both non-dunder, neither named like a pure setter).
      - M1 and M2 each call F(<args>) where F is a module-level function
        in the project.
      - At least one argument to F is `self.<attr>` and is identical
        across the call sites.

    Example: `Pipeline.tokenize` and `Pipeline.train` both call
    `pkg.config.persistence.flush_resolved_config(..., self.run_dir)`.
    Calling from multiple stages silently re-flushes the same target and
    can overwrite a patched snapshot if stages write different config
    versions.
    """
    MUTATING_METHOD_NAMES = {
        'set',
        'reset',
        'clear',
        'update',
        'mutate',
        'merge',
        'replace',
        'apply',
        'patch',
        'override',
        'flush',
        'write',
        'persist',
        'save',
        'emit',
        'dump',
    }
    for path in auditor.core.all_py_files(src_root):
        rel = auditor.core.relpath(path, scope)
        lines = auditor.core.source_lines(path)
        tree = auditor.core.read_and_parse(path)
        if tree is None:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            # For each method, collect calls of the shape f(..., self.<attr>, ...)
            # keyed by (callee_dotted, frozenset(self.<attr> args))
            calls_per_key: dict[tuple[str, tuple[str, ...]], list[tuple[str, int]]] = collections.defaultdict(list)
            for member in cls.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                mname = member.name
                if mname.startswith('_'):
                    continue
                lname = mname.lower()
                if any(lname.startswith(p + '_') or lname == p for p in MUTATING_METHOD_NAMES):
                    continue
                for inner in ast.walk(member):
                    if not isinstance(inner, ast.Call):
                        continue
                    callee = ast.unparse(inner.func)
                    # collect self.<attr> args
                    self_args: list[str] = []
                    for a in inner.args:
                        src = ast.unparse(a)
                        if src.startswith('self.'):
                            self_args.append(src)
                    for kw in inner.keywords:
                        if kw.arg is None:
                            continue
                        src = ast.unparse(kw.value)
                        if src.startswith('self.'):
                            self_args.append(src)
                    if not self_args:
                        continue
                    key = (callee, tuple(sorted(self_args)))
                    calls_per_key[key].append((mname, inner.lineno))
            for (callee, self_args), sites in calls_per_key.items():
                method_names = {m for (m, _) in sites}
                if len(method_names) < 2:
                    continue
                # Deduplicate the sink function itself; only emit when callee
                # looks like a sink (write/flush/persist/save/emit/log/dump)
                # or when the arg set suggests a shared target
                callee_tail = callee.rsplit('.', 1)[-1].lower()
                looks_like_sink = any(tok in callee_tail for tok in SINK_TOKENS)
                target_is_path_or_dir = any('dir' in a.lower() or 'path' in a.lower() or 'file' in a.lower() for a in self_args)
                if not (looks_like_sink or target_is_path_or_dir):
                    continue
                _, first_line = sites[0]
                accept = auditor.core.accept_reason(lines, first_line, rule='duplicate-side-effect-per-target')
                auditor.core.emit(
                    rule='duplicate-side-effect-per-target',
                    variant=f'{cls.name}.{{{", ".join(sorted(method_names))}}} all call {callee}({", ".join(self_args)})',
                    path=rel,
                    line=first_line,
                    evidence=f'{cls.name}: methods {sorted(method_names)} share sink {callee}',
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


def check_redundant_sink_caller_plus_callee(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions that call a sink S directly, and then call a helper
    G which itself also calls S with IDENTICAL argument signatures.

    Example: `run_evaluate` calls `flush_resolved_config(config, run_dir)`
    at line L1, then calls `pipeline.tokenize(splits)` which itself
    calls `flush_resolved_config(config, run_dir)`. The argument
    signatures match, so the outer call is redundant.

    Tight signal to avoid the O(n^2) false positives on large pipelines
    (where one orchestrator calls five helpers that each log metrics -
    those are NOT redundant, they log different arguments):
      - Function F calls sink S(args1) at line L1.
      - Function F calls helper G at line L2 where L2 > L1.
      - G is a module-level function in this project whose body also
        calls S(args2).
      - args1 and args2 have the same **normalised argument tails**:
        for each positional arg, the trailing name (`config`, `run_dir`)
        matches; for each keyword arg, the keyword and its value's trailing
        name match.
      - S's short name contains a sink token (`flush`, `write`, `save`,
        `persist`, `emit`, `dump`, `log`, `publish`, `upload`,
        `register`).

    Refinements (2026-11-21), each removing a misread:
      - A call inside a def nested in F (or in G) belongs to the nested def,
        not to F, and is not counted for either.
      - A call from F to F itself (self-recursion) is not a helper call.
      - A helper is resolved by qualified name: `pipeline.tokenize` matches
        only a function whose module path ends `pipeline.tokenize`, and a bare
        `tokenize` matches the same module's function, else a single
        project-wide function of that name; an ambiguous bare name matches
        nothing.
      - Keyword values are compared as well as keyword names, so
        `write(path=a)` and `write(path=b)` are different calls.
    """
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
    for path in auditor.core.all_py_files(src_root):
        tree = auditor.core.read_and_parse(path)
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
            for inner in auditor.core.walk_within_scope(node):
                if not isinstance(inner, ast.Call):
                    continue
                callee = ast.unparse(inner.func)
                callee_tail = callee.rsplit('.', 1)[-1].lower()
                tail_parts = set(re.split(r'[_\W]+', callee_tail))
                if not any(tok in tail_parts for tok in SINK_TOKENS):
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
    for path in auditor.core.all_py_files(src_root):
        tree = auditor.core.read_and_parse(path)
        if tree is None:
            continue
        rel = auditor.core.relpath(path, scope)
        lines = auditor.core.source_lines(path)
        rel_parts = path.relative_to(src_root).parts
        module = '' if rel_parts[-1] == '__init__.py' else package_root_name + '.' + '.'.join(rel_parts)[:-3]
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            own_key = f'{module}.{node.name}'
            direct_sinks: list[tuple[int, str, tuple[tuple[str, ...], tuple[str, ...]]]] = []
            helper_calls: list[tuple[int, str, list[str]]] = []
            for inner in auditor.core.walk_within_scope(node):
                if not isinstance(inner, ast.Call):
                    continue
                callee = ast.unparse(inner.func)
                tail = callee.rsplit('.', 1)[-1].lower()
                tail_parts = set(re.split(r'[_\W]+', tail))
                if any(tok in tail_parts for tok in SINK_TOKENS):
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
                            accept = auditor.core.accept_reason(lines, sink_line, rule='redundant-sink-caller-plus-callee')
                            auditor.core.emit(
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


# Calls that say nothing about a function's architecture: builtins, string
# and container methods, filesystem operations, and the connection plumbing
# every database test performs. A sequence made mostly of these describes the
# framework being used, not the shape of the code, so counting them makes two
# unrelated tests that both open a connection look like copies.
TRIVIAL_CALLS = frozenset(
    {
        'append',
        'as_posix',
        'close',
        'commit',
        'connect',
        'copy',
        'cursor',
        'debug',
        'deepcopy',
        'dumps',
        'endswith',
        'error',
        'exception',
        'execute',
        'executemany',
        'exists',
        'extend',
        'fetchall',
        'fetchmany',
        'fetchone',
        'flush',
        'format',
        'get',
        'info',
        'is_dir',
        'is_file',
        'items',
        'join',
        'keys',
        'loads',
        'lower',
        'mkdir',
        'open',
        'pop',
        'read',
        'read_bytes',
        'read_text',
        'replace',
        'resolve',
        'rollback',
        'seek',
        'set',
        'split',
        'startswith',
        'strip',
        'update',
        'upper',
        'values',
        'warning',
        'write',
        'write_bytes',
        'write_text',
    }
)


def check_duplicate_call_sequence(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag two functions (across different classes or modules) that
    share a long subsequence of call-name tokens in the same order.

    Signal:
      - For every FunctionDef / AsyncFunctionDef, extract the ordered
        sequence of callee short-names from calls with >=1 argument and
        whose callee is dotted (skips stdlib / builtin 1-word calls).
      - Skip very short sequences (< 5 calls) to avoid false positives.
      - Normalise: drop sequential duplicates (so `logger.info` stutter
        does not dominate the signature).
      - Group functions by the longest-common-subsequence key, which
        is the ordered tuple of distinct callee short-names appearing
        in each function.
      - If two functions share a LCS-key of length >= 5, emit.
    """
    # Build per-function signature
    signatures: list[tuple[str, int, str, tuple[str, ...]]] = []
    for path in auditor.core.all_py_files(src_root):
        tree = auditor.core.read_and_parse(path)
        if tree is None:
            continue
        rel = auditor.core.relpath(path, scope)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            seq: list[str] = []
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                callee = ast.unparse(inner.func)
                # Require a dotted callee (skips bare len(), str(), dict(),
                # and a project's own local helpers). Measured both ways on a
                # 200-file suite: without it the sequences fill with builtins
                # and the pair count triples, so it stays. Note the side
                # effect, which is not obvious - a project that forbids
                # `from X import Y` dots every call, so this check is
                # markedly more sensitive there than in one that prefers
                # from-imports, where the same duplication hides behind bare
                # names.
                if '.' not in callee:
                    continue
                short = callee.rsplit('.', 1)[-1]
                if short in TRIVIAL_CALLS:
                    continue
                if seq and seq[-1] == short:
                    continue
                seq.append(short)
            # Keep the sequence as an ordered tuple; require >= 5 distinct calls
            if len(seq) < 5:
                continue
            fname = node.name
            signatures.append((rel, node.lineno, fname, tuple(seq)))

    if len(signatures) < 2:
        return

    # Compute longest common subsequences pairwise; report pairs that share
    # a subsequence of length >= 5. Quadratic in function count - bounded
    # to architecturally-significant functions (we already filtered to >=5).
    def longest_common_subsequence(a: tuple[str, ...], b: tuple[str, ...]) -> list[str]:
        n, m = len(a), len(b)
        if n == 0 or m == 0:
            return []
        # use rolling arrays
        prev = [0] * (m + 1)
        curr = [0] * (m + 1)
        back: list[list[int]] = [[0] * (m + 1) for _ in range(n + 1)]
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                if a[i - 1] == b[j - 1]:
                    curr[j] = prev[j - 1] + 1
                    back[i][j] = 1
                elif prev[j] >= curr[j - 1]:
                    curr[j] = prev[j]
                    back[i][j] = 2
                else:
                    curr[j] = curr[j - 1]
                    back[i][j] = 3
            prev, curr = curr, prev
        # Reconstruct
        i, j = n, m
        out: list[str] = []
        while i > 0 and j > 0:
            d = back[i][j]
            if d == 1:
                out.append(a[i - 1])
                i -= 1
                j -= 1
            elif d == 2:
                i -= 1
            else:
                j -= 1
        out.reverse()
        return out

    # Count how many distinct functions each call-name appears in
    call_fanout: dict[str, int] = collections.defaultdict(int)
    for _, _, _, seq in signatures:
        for c in set(seq):
            call_fanout[c] += 1
    # Calls that appear in >30% of all functions are too generic to count
    n_funcs = max(len(signatures), 1)
    generic_threshold = max(5, n_funcs // 3)
    generic_calls = {c for c, n in call_fanout.items() if n > generic_threshold}

    reported: set[tuple[str, str]] = set()
    for i, (rel_a, line_a, fname_a, seq_a) in enumerate(signatures):
        for rel_b, line_b, fname_b, seq_b in signatures[i + 1 :]:
            if (rel_a, fname_a) == (rel_b, fname_b):
                continue
            # Skip intra-file pairs: within-file duplication is usually a
            # legitimate family of similar shaped functions (e.g. chart
            # generators). Cross-file duplication is the architectural smell.
            if rel_a == rel_b:
                continue
            # A same-package filter was started here and deliberately not
            # finished: it would have skipped pairs whose top-level packages
            # match, which is where most real duplication lives and directly
            # contradicts the rule above that cross-file duplication is the
            # smell worth reporting. The two unused locals it left behind are
            # removed rather than wired up.

            # The LCS is no longer than the shorter sequence, so a pair whose
            # lengths differ too much cannot cover 70% of both: skip the LCS.
            shorter, longer = sorted((len(seq_a), len(seq_b)))
            if shorter < 6 or shorter / max(longer, 1) < 0.7:
                continue
            # Only interesting if LCS is long enough
            lcs = longest_common_subsequence(seq_a, seq_b)
            if len(lcs) < 6:
                continue
            # Drop generic calls that appear in many functions; the LCS
            # must still be long enough after the drop.
            meaningful_lcs = [c for c in lcs if c not in generic_calls]
            if len(meaningful_lcs) < 5:
                continue
            # Require the LCS to cover MOST of BOTH sequences. A shared
            # sub-skeleton of 6+ calls that each function also decorates
            # with 4-5 unique calls is not duplication, it's a family.
            # True duplication means each function is ~70%+ the same.
            if len(lcs) / max(len(seq_a), 1) < 0.7:
                continue
            if len(lcs) / max(len(seq_b), 1) < 0.7:
                continue
            key_a = (rel_a, fname_a)
            key_b = (rel_b, fname_b)
            pair_key = tuple(sorted([f'{k[0]}:{k[1]}' for k in (key_a, key_b)]))
            if pair_key in reported:
                continue
            reported.add(pair_key)
            full_a = scope / rel_a
            accept = auditor.core.accept_reason(auditor.core.source_lines(full_a), line_a, rule='duplicate-call-sequence')
            auditor.core.emit(
                related=[rel_b],
                rule='duplicate-call-sequence',
                variant=f'{fname_a} shares {len(lcs)} calls in order with {rel_b}:{fname_b}',
                path=rel_a,
                line=line_a,
                evidence=f'shared sequence: {" -> ".join(meaningful_lcs or lcs)} (peer at {rel_b}:{line_b}:{fname_b})',
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_recompile_duplication(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag module-level constants assigned from `re.compile(...)` when
    the same CONSTANT NAME is also assigned from `re.compile(...)` in
    another file.

    Name collision across files is the real risk - the two copies read
    as if they express the same predicate, so any change to one silently
    drifts from the other. Comparing regex literals byte-wise would miss
    functionally-equivalent variants (e.g., `r'^foo$'` vs `r'^(foo)$'`),
    so the predicate is scoped to name duplication.

    Signal:
      - Module-level `Assign`/`AnnAssign` whose RHS is
        `re.compile(<literal>)`.
      - Same LHS name appears in >= 2 distinct files.
    """
    # name -> list of (path, lineno, literal)
    sites: dict[str, list[tuple[pathlib.Path, int, str]]] = collections.defaultdict(list)
    for path in auditor.core.all_py_files(src_root):
        tree = auditor.core.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            target_name: str | None = None
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    target_name = node.targets[0].id
                    value = node.value
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    target_name = node.target.id
                    value = node.value
            if target_name is None or value is None:
                continue
            if not isinstance(value, ast.Call):
                continue
            is_re_compile = False
            if isinstance(value.func, ast.Attribute) and value.func.attr == 'compile':
                if isinstance(value.func.value, ast.Name) and value.func.value.id == 're':
                    is_re_compile = True
            if not is_re_compile:
                continue
            if not value.args:
                continue
            arg0 = value.args[0]
            if not (isinstance(arg0, ast.Constant) and isinstance(arg0.value, str)):
                continue
            sites[target_name].append((path, node.lineno, arg0.value))

    for name, locations in sites.items():
        distinct_paths = {p for p, _, _ in locations}
        if len(distinct_paths) < 2:
            continue
        for path, lineno, _ in locations:
            rel = auditor.core.relpath(path, scope)
            lines = auditor.core.source_lines(path)
            accept = auditor.core.accept_reason(lines, lineno, rule='recompile-duplication')
            other_paths = sorted({auditor.core.relpath(p, scope) for p, _, _ in locations if p != path})
            auditor.core.emit(
                related=other_paths,
                rule='recompile-duplication',
                variant=(f'constant `{name} = re.compile(...)` also defined in {other_paths!r}; canonicalise to one home'),
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


__all__ = [
    'check_duplicate_call_sequence',
    'check_duplicate_side_effect_per_target',
    'check_literal_duplication',
    'check_paired_sibling_helpers',
    'check_recompile_duplication',
    'check_redundant_sink_caller_plus_callee',
]
