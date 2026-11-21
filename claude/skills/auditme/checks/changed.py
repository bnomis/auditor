#!/usr/bin/env python3
"""Fail on unaccepted audit hits in the files a change touches.

Sweeps the whole tree with `audit.py` (so cross-file rules see every file) and
reports each unaccepted hit whose path, or any `related` path, is in scope: the
files changed since the diff base, or every file with `--all`. A sweep that
cannot run (a timeout, a non-zero exit, a line that is not JSON, a crashed
check) fails. Without `--all`, the sweep is skipped, and the run passes, when
no diff base resolves or no changed file can carry a hit (`reportable`); the
push gate and CI run `--all`, which never skips.

Usage:
    changed.py [--all] [--base <ref>] [<repo-root>]

Stdlib only, like the rest of the checker.
"""

import argparse
import collections.abc
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import auditme.core  # noqa: E402
import auditme.rules.project_hygiene  # noqa: E402  sys.path is set up immediately above

AUDIT_SCRIPT = HERE / 'audit.py'
SWEEP_TIMEOUT = 600
# auditme: accept[non-alphabetical-literal] the order is the priority in which a diff base is tried
BASE_CANDIDATES = ('@{upstream}', 'origin/main', 'main')
CRASH_RULE = 'auditme-check-crash'
ACCEPT_HELP = 'Fix each hit, or accept one with a comment on its line or the line above:\n    # auditme: accept[<rule>] <reason>'
# Hits no accept marker can accept: each comes from a tool, and is cleared there.
RULE_HELP = {
    'lockfile-drift': 'lockfile-drift: run `uv lock` and commit uv.lock; no accept marker applies.',
    'ruff': 'ruff: fix the code, or silence one line with `# noqa: <code>`; no accept marker applies.',
}
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


def resolve_base(repo_root: pathlib.Path) -> str | None:
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
    committed = git_lines(repo_root, 'diff', '--name-only', '--diff-filter=d', f'{base}...HEAD')
    pending = git_lines(repo_root, 'diff', '--name-only', '--diff-filter=d', 'HEAD')
    return frozenset(committed) | frozenset(pending)


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
        return not (auditme.rules.project_hygiene.SPEC_SKIP_PARTS & set(dirs) or any(part.startswith('.') for part in dirs))
    return False


def sweep(repo_root: pathlib.Path) -> list[dict[str, object]]:
    """Run audit.py over the whole tree and parse its hits.

    Raises:
        ChangedError: the sweep timed out, could not start, exited non-zero,
            printed a line that is not JSON, or reported a crashed check.
    """
    command = [sys.executable, str(AUDIT_SCRIPT), str(repo_root)]
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


def option_value_is_flag(argv: collections.abc.Sequence[str]) -> bool:
    """Whether `--base` is given a value starting with `-` (refused before git runs)."""
    for index, arg in enumerate(argv):
        if arg.startswith('--base='):
            return arg.removeprefix('--base=').startswith('-')
        if arg == '--base' and index + 1 < len(argv):
            return argv[index + 1].startswith('-')
    return False


def format_hits(hits: collections.abc.Sequence[dict[str, object]]) -> str:
    ordered = sorted(hits, key=lambda hit: (str(hit.get('path')), hit.get('line') or 0))  # type: ignore[arg-type,return-value]
    lines = []
    for hit in ordered:
        lines.append(f'{hit.get("path")}:{hit.get("line")}  {hit.get("rule")}')
        lines.append(f'    {hit.get("variant")}')
    return '\n'.join(lines)


def main(argv: collections.abc.Sequence[str] | None = None) -> int:
    """0 when no unaccepted hit is in scope, 1 otherwise or on any failure."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if option_value_is_flag(argv):
        print('changed.py: --base must be a ref, not an option')
        return 1
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1
    try:
        repo_root = args.repo_root
        if repo_root is None:
            repo_root = pathlib.Path(git_lines(pathlib.Path.cwd(), 'rev-parse', '--show-toplevel')[0])
        repo_root = repo_root.resolve()
        scope: frozenset[str] | None = None
        if not args.all:
            base = args.base or resolve_base(repo_root)
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
        print(f'changed.py: {auditme.core.describe_error(exc)}')
        return 1
    if not hits:
        return 0
    print(format_hits(hits))
    print()
    rules = {hit.get('rule') for hit in hits}
    for rule, advice in sorted(RULE_HELP.items()):
        if rule in rules:
            print(advice)
    if rules - RULE_HELP.keys():
        print(ACCEPT_HELP)
    print(SKIP_ALL_HELP if args.all else SKIP_HELP)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
