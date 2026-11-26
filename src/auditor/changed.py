"""Fail on unaccepted audit hits in the files a change touches.

Sweeps the whole tree with `auditor check` (so cross-file rules see every file) and
reports each unaccepted hit whose path, or any `related` path, is in scope: the
files changed since the diff base, or every file with `--all`. A sweep that
cannot run (a timeout, a non-zero exit, a line that is not JSON, a crashed
check) fails. Without `--all`, the sweep is skipped, and the run passes, when
no diff base resolves or no changed file can carry a hit (`reportable`); the
push gate and CI run `--all`, which never skips.

Usage:
    auditor changed [--all] [--base <ref>] [<repo-root>]
    auditor changed --scope [--base <ref>] [<repo-root>]

`--scope` runs no sweep: it prints one JSON line per changed `.py` or `.sh` file,
`{"path": ..., "ranges": [[start, end], ...]}`, the changed lines of the file
since the diff base, each Python hunk widened to its enclosing function or class.

Stdlib only, like the rest of the checker.
"""

import argparse
import ast
import json
import pathlib
import re
import subprocess
import sys
import typing

import auditor.core
import auditor.hygiene

if typing.TYPE_CHECKING:
    import collections.abc

SWEEP_TIMEOUT = 600
SWEEP_COMMAND = [sys.executable, '-I', '-c', 'import sys, auditor.cli; sys.exit(auditor.cli.main(sys.argv[1:]))', 'check']
# auditme: accept[non-alphabetical-literal] the order is the priority in which a diff base is tried
BASE_CANDIDATES = ('@{upstream}', 'origin/main', 'main')
CRASH_RULE = 'auditme-check-crash'
ACCEPT_HELP = 'Fix each hit, or accept one with a comment on its line or the line above:\n    # auditme: accept[<rule>] <reason>'
# Hits no accept marker can accept: each comes from a tool, and is cleared there.
RULE_HELP = {
    'lockfile-drift': 'lockfile-drift: run `uv lock` and commit uv.lock; no accept marker applies.',
    'ruff': 'ruff: fix the code, or silence one line with `# noqa: <code>`; no accept marker applies.',
}
REFUSED_HELP = '{rule}: this project does not accept markers for this rule ([tool.auditme] never-accepted); fix the code.'
SCOPE_SUFFIXES = frozenset({'.py', '.sh'})
HUNK_HEADER = re.compile(r'^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
SKIP_HELP = 'To skip this check for one commit: SKIP=auditme-changed git commit'
SKIP_ALL_HELP = 'To skip this check for one push: SKIP=auditme-all git push'


class ChangedError(Exception):
    """The runner could not decide which files changed, or could not run the sweep."""


def run_git(repo_root: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ['git', *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise ChangedError('cannot run git') from exc


def git_lines(repo_root: pathlib.Path, *args: str) -> list[str]:
    result = run_git(repo_root, *args)
    if result.returncode != 0:
        raise ChangedError(f'git {" ".join(args)} failed: {result.stderr.strip()}')
    return [line for line in result.stdout.splitlines() if line]


def read_base_ref(repo_root: pathlib.Path) -> str | None:
    """The first of the candidate refs that resolves, or None.

    Raises:
        ChangedError: `git rev-parse` fails for a reason other than the ref not resolving.
    """
    for candidate in BASE_CANDIDATES:
        result = run_git(repo_root, 'rev-parse', '--verify', '--quiet', candidate)
        if result.returncode == 0:
            return candidate
        if result.returncode != 1:
            raise ChangedError(f'git rev-parse {candidate} failed: {result.stderr.strip()}')
    return None


def changed_files(repo_root: pathlib.Path, base: str) -> frozenset[str]:
    """Repository-relative paths changed in base...HEAD, deletions excluded.

    Paths changed in the index or working tree relative to HEAD count too: the
    commit hook runs before the commit exists, so the files it is about to
    record are not yet in HEAD.

    Side effect: runs `git diff --name-only --diff-filter=d`.

    Raises:
        ChangedError: git cannot be run, or the diff fails.
    """
    committed = git_lines(repo_root, 'diff', '--name-only', '--diff-filter=d', '--end-of-options', f'{base}...HEAD')
    pending = git_lines(repo_root, 'diff', '--name-only', '--diff-filter=d', 'HEAD')
    return frozenset(committed) | frozenset(pending)


def changed_hunks(repo_root: pathlib.Path, base: str) -> dict[str, list[tuple[int, int]]]:
    """Each changed `.py` or `.sh` file's changed line ranges, new-side, since the merge base.

    Deletions of whole files are excluded; a hunk that only removes lines is the
    one line where the removal sits. Index and working-tree changes count.

    Side effect: runs `git merge-base` and `git diff -U0`.

    Raises:
        ChangedError: git cannot be run, or the diff fails.
    """
    merge_base = git_lines(repo_root, 'merge-base', '--end-of-options', base, 'HEAD')[0]
    lines = git_lines(repo_root, 'diff', '-U0', '--no-color', '--no-ext-diff', '--diff-filter=d', merge_base)
    hunks: dict[str, list[tuple[int, int]]] = {}
    current: list[tuple[int, int]] | None = None
    body_left = 0  # lines of the current hunk's body still to skip, so a body line that reads `+++ ` is not a header
    for line in lines:
        if body_left:
            body_left -= 1
            continue
        if line.startswith('+++ '):
            path = line[4:]
            suffix = pathlib.PurePosixPath(path).suffix
            current = hunks.setdefault(path[2:], []) if path.startswith('b/') and suffix in SCOPE_SUFFIXES else None
            continue
        match = HUNK_HEADER.match(line)
        if match:
            old_count = 1 if match.group(1) is None else int(match.group(1))
            start = int(match.group(2))
            count = 1 if match.group(3) is None else int(match.group(3))
            body_left = old_count + count
            if current is not None:
                current.append((start, start + max(count, 1) - 1))
    return {path: ranges for path, ranges in hunks.items() if ranges}


def enclosing_ranges(source: str) -> list[tuple[int, int, bool]]:
    """Each function and class in the source as (first line, last line, is a function)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
            found.append((first, node.end_lineno or node.lineno, not isinstance(node, ast.ClassDef)))
    return found


def widen(hunk: tuple[int, int], scopes: collections.abc.Sequence[tuple[int, int, bool]]) -> list[tuple[int, int]]:
    """The hunk with each of its lines widened to the innermost function holding it,
    else the innermost class, else the line itself. Pure."""
    widened = []
    for number in range(hunk[0], hunk[1] + 1):
        holding = [scope for scope in scopes if scope[0] <= number <= scope[1]]
        functions = [scope for scope in holding if scope[2]] or holding
        best = min(functions, key=lambda scope: scope[1] - scope[0], default=None)
        widened.append((best[0], best[1]) if best else (number, number))
    return widened


def merge_ranges(ranges: collections.abc.Iterable[tuple[int, int]]) -> list[list[int]]:
    """Sorted ranges with overlapping and adjacent ones joined. Pure."""
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def scope_records(repo_root: pathlib.Path, base: str) -> list[dict[str, object]]:
    """One record per changed `.py` or `.sh` file: its path and the line ranges to judge.

    Raises:
        ChangedError: git fails, or a changed Python file cannot be read.
    """
    records: list[dict[str, object]] = []
    for path, hunks in sorted(changed_hunks(repo_root, base).items()):
        ranges = list(hunks)
        if path.endswith('.py'):
            try:
                scopes = enclosing_ranges((repo_root / path).read_text(encoding='utf-8'))
            except (OSError, UnicodeDecodeError) as exc:
                raise ChangedError(f'cannot read {path}') from exc
            ranges = [widened for hunk in hunks for widened in widen(hunk, scopes)]
        records.append({'path': path, 'ranges': merge_ranges(ranges)})
    return records


def in_scope(hit: collections.abc.Mapping[str, object], scope: frozenset[str] | None) -> bool:
    """Whether a hit is reported: always when scope is None (--all), else when its
    path or any of its related paths is in scope. Pure."""
    if scope is None:
        return True
    related = hit.get('related') or []
    paths = [hit.get('path'), *related]  # type: ignore[misc]
    return any(path in scope for path in paths if isinstance(path, str))


def reportable(path: str) -> bool:
    """Whether a changed path can carry a hit the sweep reports."""
    pure = pathlib.PurePosixPath(path)
    if pure.suffix == '.py' or pure.name == 'uv.lock':
        return True
    if pure.suffix == '.md':
        dirs = pure.parts[:-1]
        return not (auditor.hygiene.SPEC_SKIP_PARTS & set(dirs) or any(part.startswith('.') for part in dirs))
    return False


def sweep(repo_root: pathlib.Path) -> list[dict[str, object]]:
    """Run auditor check over the whole tree and parse its hits.

    Raises:
        ChangedError: the sweep timed out, could not start, exited non-zero,
            printed a line that is not JSON, or reported a crashed check.
    """
    command = [*SWEEP_COMMAND, str(repo_root)]
    try:
        result = subprocess.run(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=SWEEP_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ChangedError(f'the audit sweep timed out after {SWEEP_TIMEOUT} seconds') from exc
    except OSError as exc:
        raise ChangedError('the audit sweep could not start') from exc
    if result.returncode != 0:
        detail = (result.stderr.strip() or result.stdout.strip())[-500:]
        raise ChangedError(f'the audit sweep exited {result.returncode}: {detail}')
    hits: list[dict[str, object]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            hit = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ChangedError(f'the audit sweep printed a line that is not JSON: {line[:200]!r}') from exc
        if not isinstance(hit, dict):
            raise ChangedError(f'the audit sweep printed a line that is not a hit: {line[:200]!r}')
        if hit.get('rule') == CRASH_RULE:
            raise ChangedError(f'audit check {hit.get("variant")} crashed: {hit.get("evidence")}')
        hits.append(hit)
    return hits


def parse_args(argv: collections.abc.Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='changed.py',
        description='Fail on unaccepted audit hits in changed files (or everywhere with --all).',
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Report every unaccepted hit, not only those in changed files',
    )
    parser.add_argument(
        '--scope',
        action='store_true',
        help='Print the changed line ranges of each changed .py or .sh file as JSON lines; run no sweep',
    )
    parser.add_argument(
        '--base',
        help='Diff base (default: the first of @{upstream}, origin/main, main that resolves)',
        default=None,
    )
    parser.add_argument(
        'repo_root',
        nargs='?',
        type=pathlib.Path,
        help="Repository root (default: the working directory's git top level)",
        default=None,
    )
    return parser.parse_args(argv)


def format_hits(hits: collections.abc.Sequence[dict[str, object]]) -> str:
    ordered = sorted(hits, key=lambda hit: (str(hit.get('path')), hit.get('line') or 0))  # type: ignore[arg-type,return-value]
    lines = []
    for hit in ordered:
        lines.append(f'{hit.get("path")}:{hit.get("line")}  {hit.get("rule")}')
        lines.append(f'    {hit.get("variant")}')
    return '\n'.join(lines)


def main(argv: collections.abc.Sequence[str] | None = None) -> int:
    """0 when no unaccepted hit is in scope, 1 otherwise or on any failure.

    A `ChangedError`, including an `OSError` from finding the repository root,
    is printed as one line and returns 1.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1
    if args.base is not None and args.base.startswith('-'):
        print('changed.py: --base must be a ref, not an option')
        return 1
    try:
        repo_root = args.repo_root
        try:
            if repo_root is None:
                repo_root = pathlib.Path(git_lines(pathlib.Path.cwd(), 'rev-parse', '--show-toplevel')[0])
            repo_root = repo_root.resolve()
        except OSError as exc:
            raise ChangedError(f'cannot resolve the repository root: {exc}') from exc
        if args.scope:
            base = args.base or read_base_ref(repo_root)
            if base is None:
                print('changed.py: no diff base resolves (no upstream, origin/main or main); nothing to compare', file=sys.stderr)
                return 0
            for record in scope_records(repo_root, base):
                print(json.dumps(record, sort_keys=True))
            return 0
        scope: frozenset[str] | None = None
        if not args.all:
            base = args.base or read_base_ref(repo_root)
            if base is None:
                print('changed.py: no diff base resolves (no upstream, origin/main or main); nothing to compare')
                return 0
            scope = changed_files(repo_root, base)
            if not any(reportable(path) for path in scope):
                print('changed.py: no reportable file changed; sweep skipped')
                return 0
        hits = [hit for hit in sweep(repo_root) if not hit.get('accepted') and in_scope(hit, scope)]
    except ChangedError as exc:
        # auditme: accept[except-interpolation] the entry point prints the message and its chained cause once
        print(f'changed.py: {auditor.core.describe_error(exc)}')
        return 1
    if not hits:
        return 0
    print(format_hits(hits))
    print()
    rules = {hit.get('rule') for hit in hits}
    refused = {hit.get('rule') for hit in hits if hit.get('refused_reason')}
    for rule, advice in sorted(RULE_HELP.items()):
        if rule in rules:
            print(advice)
    for rule in sorted(str(rule) for rule in refused if rule not in RULE_HELP):
        print(REFUSED_HELP.format(rule=rule))
    if rules - RULE_HELP.keys() - refused:
        print(ACCEPT_HELP)
    print(SKIP_ALL_HELP if args.all else SKIP_HELP)
    return 1
