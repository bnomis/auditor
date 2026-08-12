"""Checks that compare code across files for repeated structure."""

from __future__ import annotations
import ast
import pathlib
import re
from collections import defaultdict

from auditme.core import _accept_reason, _all_py_files, _emit, _relpath, _source_lines


def check_literal_duplication(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    bucket: dict[tuple, set[tuple[str, int, str]]] = defaultdict(set)
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        # Find frozenset(...) / set(...) call nodes so we can skip their inner ast.Set/Tuple child
        skip_inner_nodes: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'frozenset', 'set'}:
                if node.args and isinstance(node.args[0], (ast.Set, ast.Tuple, ast.List)):
                    skip_inner_nodes.add(id(node.args[0]))
        for node in ast.walk(tree):
            if id(node) in skip_inner_nodes:
                continue
            members = None
            kind = None
            if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
                members = node.elts
                kind = type(node).__name__
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {'frozenset', 'set'}:
                    if node.args and isinstance(node.args[0], (ast.Set, ast.Tuple, ast.List)):
                        members = node.args[0].elts
                        kind = 'frozenset'
            if not members:
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
            full_lines = _source_lines(full)
            accept = _accept_reason(full_lines, lineno, rule='literal-duplication')
            _emit(
                rule='literal-duplication',
                variant=f'identical {key[0]} literal across {len(hits)} locations',
                path=rel,
                line=lineno,
                evidence=evidence[:200],
                accepted=bool(accept),
                accepted_reason=accept,
            )

def check_paired_sibling_helpers(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    bodies: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            try:
                body_src = '\n'.join(ast.unparse(b) for b in node.body if not isinstance(b, ast.Expr) or not isinstance(b.value, ast.Constant))
            except Exception:
                continue
            if not body_src.strip() or len(body_src) < 40:
                continue
            bodies[body_src].append((rel, node.lineno, node.name))
    for body_src, hits in bodies.items():
        if len(hits) < 2:
            continue
        files = {h[0] for h in hits}
        if len(files) < 2:
            continue
        for rel, lineno, fname in hits:
            full = scope / rel
            full_lines = _source_lines(full)
            accept = _accept_reason(full_lines, lineno, rule='paired-sibling-helpers')
            peers = sorted(set(h[2] for h in hits) - {fname})
            _emit(
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
    `feathf.config.persistence.flush_resolved_config(..., self.run_dir)`.
    Calling from multiple stages silently re-flushes the same target and
    can overwrite a patched snapshot if stages write different config
    versions.
    """
    MUTATING_METHOD_NAMES = {
        'set', 'reset', 'clear', 'update', 'mutate', 'merge', 'replace',
        'apply', 'patch', 'override', 'flush', 'write', 'persist', 'save',
        'emit', 'dump',
    }
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            # For each method, collect calls of the shape f(..., self.<attr>, ...)
            # keyed by (callee_dotted, frozenset(self.<attr> args))
            calls_per_key: dict[tuple[str, tuple[str, ...]], list[tuple[str, int]]] = defaultdict(list)
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
                    try:
                        callee = ast.unparse(inner.func)
                    except Exception:
                        continue
                    # collect self.<attr> args
                    self_args: list[str] = []
                    for a in inner.args:
                        try:
                            src = ast.unparse(a)
                        except Exception:
                            continue
                        if src.startswith('self.'):
                            self_args.append(src)
                    for kw in inner.keywords:
                        if kw.arg is None:
                            continue
                        try:
                            src = ast.unparse(kw.value)
                        except Exception:
                            continue
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
                looks_like_sink = any(
                    tok in callee_tail
                    for tok in ('flush', 'write', 'save', 'persist', 'emit', 'dump', 'log', 'publish', 'upload', 'register')
                )
                target_is_path_or_dir = any('dir' in a.lower() or 'path' in a.lower() or 'file' in a.lower() for a in self_args)
                if not (looks_like_sink or target_is_path_or_dir):
                    continue
                first_method, first_line = sites[0]
                accept = _accept_reason(lines, first_line, rule='duplicate-side-effect-per-target')
                _emit(
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
        matches; for each keyword arg, the keyword matches.
      - S's short name contains a sink token (`flush`, `write`, `save`,
        `persist`, `emit`, `dump`, `log`, `publish`, `upload`,
        `register`).
    """
    package_root_name = src_root.name
    SINK_TOKENS = ('flush', 'write', 'save', 'persist', 'emit', 'dump',
                   'log', 'publish', 'upload', 'register')

    def _arg_signature(call: ast.Call) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Normalise a call's arguments into (positional_tails, kwargs).

        Normalisation keeps role tokens that survive renames: `patched_config`
        and `self.config` both normalise to `config`. The last underscore-
        separated token is the "role"; common prefixes (`patched_`, `new_`,
        `effective_`, `resolved_`) drop out, so `patched_config` == `config`.
        """
        positional: list[str] = []
        for a in call.args:
            try:
                src = ast.unparse(a)
            except Exception:
                continue
            tail = src
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
                # keep the last two segments if they look like `run_dir`,
                # otherwise just the last one
                last_two = '_'.join(parts[-2:])
                if last_two in {'run_dir', 'run_id', 'trial_id', 'split_id', 'split_name'}:
                    tail = last_two
                else:
                    tail = parts[-1]
            positional.append(tail)
        kwargs: list[str] = []
        for kw in call.keywords:
            if kw.arg is not None:
                kwargs.append(kw.arg)
        return tuple(positional), tuple(sorted(kwargs))

    # First pass: index every project function's sink calls with their signatures.
    function_sinks: dict[str, dict[str, list[tuple[tuple[str, ...], tuple[str, ...]]]]] = defaultdict(lambda: defaultdict(list))
    # function_sinks[func_key][sink_callee] = list of (positional_tails, kwarg_keys)
    for path in _all_py_files(src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel_parts = path.relative_to(src_root).parts
        if rel_parts[-1] == '__init__.py':
            continue
        mod = package_root_name + '.' + '.'.join(rel_parts)[:-3]
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            key = f'{mod}.{node.name}'
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                try:
                    callee = ast.unparse(inner.func)
                except Exception:
                    continue
                callee_tail = callee.rsplit('.', 1)[-1].lower()
                tail_parts = set(re.split(r'[_\W]+', callee_tail))
                if not any(tok in tail_parts for tok in SINK_TOKENS):
                    continue
                function_sinks[key][callee].append(_arg_signature(inner))
    if not function_sinks:
        return

    # Build lookup: short_name -> set of full keys
    short_to_full: dict[str, set[str]] = defaultdict(set)
    for key in function_sinks:
        short = key.rsplit('.', 1)[-1]
        short_to_full[short].add(key)

    # Second pass: walk each function. For each direct sink call, look for
    # a later helper call whose target (any full key matching its short name)
    # makes the SAME sink call with the SAME signature.
    for path in _all_py_files(src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            direct_sinks: list[tuple[int, str, tuple[tuple[str, ...], tuple[str, ...]]]] = []
            helper_calls: list[tuple[int, str]] = []
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                try:
                    callee = ast.unparse(inner.func)
                except Exception:
                    continue
                tail = callee.rsplit('.', 1)[-1].lower()
                tail_parts = set(re.split(r'[_\W]+', tail))
                if any(tok in tail_parts for tok in SINK_TOKENS):
                    direct_sinks.append((inner.lineno, callee, _arg_signature(inner)))
                else:
                    short = callee.rsplit('.', 1)[-1]
                    if short in short_to_full:
                        helper_calls.append((inner.lineno, callee))
            if not direct_sinks or not helper_calls:
                continue
            reported: set[tuple[int, str]] = set()
            for sink_line, sink_callee, sink_sig in direct_sinks:
                sink_tail = sink_callee.rsplit('.', 1)[-1]
                dedup_key = (sink_line, sink_callee)
                if dedup_key in reported:
                    continue
                found_redundant = False
                for helper_line, helper_callee in helper_calls:
                    if helper_line <= sink_line:
                        continue  # only forward-direction redundancy
                    short = helper_callee.rsplit('.', 1)[-1]
                    # sorted, not set order: several modules can define a
                    # function with the same short name, the loop breaks on the
                    # first match, and set iteration follows string hashing -
                    # which is randomised per process. Unsorted, the same
                    # unchanged tree reports a different qualname between runs.
                    for full in sorted(short_to_full.get(short, set())):
                        for inner_callee, sigs in function_sinks.get(full, {}).items():
                            if inner_callee.rsplit('.', 1)[-1] != sink_tail:
                                continue
                            if sink_sig not in sigs:
                                continue
                            accept = _accept_reason(lines, sink_line, rule='redundant-sink-caller-plus-callee')
                            _emit(
                                rule='redundant-sink-caller-plus-callee',
                                variant=f'{node.name} calls {sink_callee}(...) then {helper_callee} which re-calls {inner_callee} with the same args',
                                path=rel,
                                line=sink_line,
                                evidence=(f'direct {sink_callee}{sink_sig[0]} at line {sink_line}; '
                                          f'helper {helper_callee} at line {helper_line} -> {full}'),
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
    for path in _all_py_files(src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = _relpath(path, scope)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            seq: list[str] = []
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                try:
                    callee = ast.unparse(inner.func)
                except Exception:
                    continue
                # Require a dotted callee (skip bare len(), str(), dict() etc.)
                if '.' not in callee:
                    continue
                short = callee.rsplit('.', 1)[-1]
                if short in {'warning', 'info', 'error', 'exception',
                             'debug', 'format', 'get', 'set', 'append',
                             'extend', 'update', 'pop', 'items', 'keys',
                             'values', 'join', 'split', 'strip', 'lower',
                             'upper', 'replace', 'startswith', 'endswith',
                             'replace', 'items', 'dumps', 'loads', 'copy',
                             'deepcopy', 'write_text', 'read_text',
                             'mkdir', 'exists', 'is_file', 'is_dir',
                             'as_posix', 'resolve'}:
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
    def _lcs(a: tuple[str, ...], b: tuple[str, ...]) -> list[str]:
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
    call_fanout: dict[str, int] = defaultdict(int)
    for (_, _, _, seq) in signatures:
        for c in set(seq):
            call_fanout[c] += 1
    # Calls that appear in >30% of all functions are too generic to count
    n_funcs = max(len(signatures), 1)
    generic_threshold = max(5, n_funcs // 3)
    generic_calls = {c for c, n in call_fanout.items() if n > generic_threshold}

    reported: set[tuple[str, str]] = set()
    for i, (rel_a, line_a, fname_a, seq_a) in enumerate(signatures):
        for (rel_b, line_b, fname_b, seq_b) in signatures[i + 1:]:
            if (rel_a, fname_a) == (rel_b, fname_b):
                continue
            # Skip intra-file pairs: within-file duplication is usually a
            # legitimate family of similar shaped functions (e.g. chart
            # generators). Cross-file duplication is the architectural smell.
            if rel_a == rel_b:
                continue
            # Skip if top-level packages match AND both are leaf functions
            # in the same kind of module (e.g. both in `*/metrics.py`).
            pkg_a = rel_a.split('/', 2)[:2]
            pkg_b = rel_b.split('/', 2)[:2]
            # Only interesting if LCS is long enough
            lcs = _lcs(seq_a, seq_b)
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
            accept = _accept_reason(_source_lines(full_a), line_a, rule='duplicate-call-sequence')
            _emit(
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
    sites: dict[str, list[tuple[pathlib.Path, int, str]]] = defaultdict(list)
    for path in _all_py_files(src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
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
        for path, lineno, literal in locations:
            rel = _relpath(path, scope)
            lines = _source_lines(path)
            accept = _accept_reason(lines, lineno, rule='recompile-duplication')
            other_paths = sorted({_relpath(p, scope) for p, _, _ in locations if p != path})
            _emit(
                rule='recompile-duplication',
                variant=(f'constant `{name} = re.compile(...)` also defined in '
                         f'{other_paths!r}; canonicalise to one home'),
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200]
                          if lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
