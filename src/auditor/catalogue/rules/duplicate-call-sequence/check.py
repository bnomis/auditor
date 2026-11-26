import ast
import collections
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


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


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag two functions in different files that share a long call-name subsequence in order."""
    # Build per-function signature
    signatures: list[tuple[str, int, str, tuple[str, ...]]] = []
    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        rel = auditor.api.relpath(path, scope)
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
            accept = auditor.api.accept_reason(auditor.api.source_lines(full_a), line_a, rule='duplicate-call-sequence')
            auditor.api.emit(
                related=[rel_b],
                rule='duplicate-call-sequence',
                variant=f'{fname_a} shares {len(lcs)} calls in order with {rel_b}:{fname_b}',
                path=rel_a,
                line=line_a,
                evidence=f'shared sequence: {" -> ".join(meaningful_lcs or lcs)} (peer at {rel_b}:{line_b}:{fname_b})',
                accepted=bool(accept),
                accepted_reason=accept,
            )
