#!/usr/bin/env python3
"""Audit checks driver.

Runs every mechanical check across the scope and emits JSON-lines.
Each line represents one hit. Callers (the auditme skill) must
transcribe every line into a finding - there is no sampling, filtering,
or "accepted because pre-existing" logic in the calling layer.

Usage:
    audit.py <scope-root> [--package <package-name>] [--extra-root <dir> ...]

<scope-root> is the project directory (agents/, docs/, and usually src/).
src/ is optional: the sweep passes over the packages under it, if any, then
the extra roots. A project with neither is reported on stderr and gets the
project-level checks alone (auditme.registry.PROJECT_CHECKS), once.
A .py file directly in src/ belongs to no root, so the driver reports it as a
src-loose-module hit (accepted by a line-1 marker) rather than skip it unseen.
<package-name> restricts the run to one package under src/. It defaults to
EVERY package under src/, each audited in its own pass, plus every extra root.

That default matters. A project whose src/ holds both the library and the test
tree - src/mylib/ and src/tests/ - has two packages, and a driver that audited
only the first would report a partial scope as a complete one. On one project
that silently hid every hit in src/tests/ across several audit cycles: the
sweep looked clean because the test tree was never read.

An extra root is auditable Python that is not a package under src/. bin/ is
the default one, and the same failure had a second instance there: enumerating
packages *under src/* gave a project whose scripts live in bin/ zero rows for
them - accepted or otherwise - while three consecutive summaries recorded
"bin/ remains at zero unaccepted hits" as though it were a measurement.
--extra-root replaces that default set; each root named must exist. It also
replaces the roots a project declares in [tool.auditme] in pyproject.toml, for
that run, so a malformed declaration does not stop it.

A project that declares [tool.auditme] roots gets exactly those roots, in
order, instead of src/ packages and the default extras. An invalid declaration
is reported as "ERROR: <message>" on stderr, with exit 2 and nothing on stdout.

Each root gets its own pass rather than one pass over src/, because
src_root.name is the package's dotted root - six checks build module names as
'.'.join((src_root.name,) + parts) - so a single pass rooted at src/ would
rename every module to src.<pkg>.<mod> and break the import-graph checks and
the AGENTS.md acceptance rows, which carry no src. prefix.

Duplicate hits are suppressed: project-level checks (the lockfile, and every
check that reads AGENTS.md) see the same project once per package.

Output schema (one JSON object per line):
    {
        "rule": "<rule-family-name>",
        "variant": "<variant-within-family>",
        "path": "<relative path>",
        "line": <1-indexed line number or null>,
        "evidence": "<source snippet or identifier>",
        "accepted": <bool>,
        "accepted_reason": "<why, if accepted>",
        "related": ["<other path>", ...]
    }

`related` appears only on a hit that compares files: the other files' paths,
sorted, never the hit's own. `changed.py` treats the hit as changed when any
of them changed.

Acceptance is determined exclusively by:
    1. AGENTS.md "Accepted cross-layer exceptions" / "Accepted lazy imports" tables
    2. An inline `# auditme: accept[<rule>] <reason>` comment on the
       preceding or same line as the hit, answering for that rule only. The
       unscoped `# auditme: accept <reason>` answers for every rule on the
       line, including rules added later, so new markers name their rule.
    3. A few file-level and multi-line forms some checks document in their
       own docstrings (a line-1 marker for `src-loose-module`, a marker on
       any line of a multi-line statement).

`ruff` and `lockfile-drift` hits are never accepted by a marker: they are
cleared with ruff's `# noqa` or `uv lock`.

No other signal acts as acceptance. The existence of a finding in a
prior review, a decision note, or an assumption of intentionality does
NOT make a hit accepted. Callers must treat `accepted=false` as a
required finding.
"""

import argparse
import pathlib
import sys
import typing

import auditme.core
import auditme.registry

if typing.TYPE_CHECKING:
    import collections.abc

DEFAULT_EXTRA_ROOTS = ', '.join(f'{name}/' for name in auditme.core.EXTRA_ROOT_NAMES)


def report_unreadable(scope: pathlib.Path) -> None:
    """Emit one `unreadable-file` hit per file a check could not read, then forget them."""
    for path, error in sorted(auditme.core.UNREADABLE.items()):
        try:
            shown = path.relative_to(scope).as_posix()
        except ValueError:
            shown = path.as_posix()
        auditme.core.emit(
            rule='unreadable-file',
            variant='a file a check could not read',
            path=shown,
            line=None,
            evidence=error,
            accepted=False,
            accepted_reason=None,
        )
    auditme.core.UNREADABLE.clear()


def run_check(check: collections.abc.Callable[[pathlib.Path, pathlib.Path], None], scope: pathlib.Path, root: pathlib.Path) -> None:
    """Run one check, reporting a crash as a hit so the sweep continues."""
    try:
        check(scope, root)
    # auditme: accept[silent-broad-except] reporting a crashing check as a hit is the handler's job
    except Exception as exc:
        auditme.core.emit(
            rule='auditme-check-crash',
            variant=check.__name__,
            path=None,
            line=None,
            # auditme: accept[except-interpolation] the crash text is the hit's evidence
            evidence=f'{type(exc).__name__}: {exc}',
            accepted=False,
            accepted_reason=None,
        )
    finally:
        report_unreadable(scope)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'scope',
        type=pathlib.Path,
        help='Project root (containing src/, agents/, ...)',
    )
    parser.add_argument(
        '--package',
        help='Audit only this package under src/ (default: every package, plus every extra root)',
        default=None,
    )
    parser.add_argument(
        '--extra-root',
        action='append',
        metavar='DIR',
        help=(
            'Audit this directory, relative to the scope root, as its own pass. Repeatable. '
            f'Replaces the default set: {DEFAULT_EXTRA_ROOTS}, each used only when it exists and holds .py files.'
        ),
        default=None,
    )
    args = parser.parse_args()

    auditme.core.clear_source_cache()
    scope = args.scope.resolve()
    if not scope.is_dir():
        print(f'ERROR: {scope} is not a directory', file=sys.stderr)
        return 2

    if args.package and (pathlib.Path(args.package).name != args.package or args.package in ('.', '..')):
        print(f'ERROR: --package {args.package} is not a directory name directly under src/', file=sys.stderr)
        return 2

    if args.extra_root is not None:
        # A root named on the command line is not silently dropped when it is
        # missing: an unnoticed typo would reinstate exactly the empty pass
        # this flag exists to end.
        auditme.core.EXTRA_ROOT_NAMES = tuple(args.extra_root)
        auditme.core.DECLARATION_IGNORED = True
        for name in args.extra_root:
            if not auditme.core.path_inside((scope / name).resolve(), scope):
                print(f'ERROR: --extra-root {name} is outside {scope}', file=sys.stderr)
                return 2
            if not (scope / name).is_dir():
                print(f'ERROR: {scope / name} is not a directory', file=sys.stderr)
                return 2

    default_roots: list[pathlib.Path] = []
    if not args.package:
        # Read first: an invalid declaration must exit before anything is emitted.
        try:
            default_roots = auditme.core.audit_roots(scope)
        except auditme.core.RootsError as exc:
            # auditme: accept[except-interpolation] the entry point prints the message and its chained cause once
            print(f'ERROR: {auditme.core.describe_error(exc)}', file=sys.stderr)
            return 2

        # A module directly in src/ belongs to no root, so no pass would read
        # it. The driver reports it, not a registered check: a check runs once
        # per root, and a project holding only src/a.py has none.
        for path in auditme.core.loose_src_modules(scope):
            reason = auditme.core.accept_reason(auditme.core.source_lines(path), 1, rule='src-loose-module')
            auditme.core.emit(
                rule='src-loose-module',
                variant='module directly under src/, outside any package',
                path=path.relative_to(scope).as_posix(),
                line=1,
                evidence=path.name,
                accepted=reason is not None,
                accepted_reason=reason,
            )

    if args.package:
        # --package is a request for one package, so it drops the extra roots
        # too. It is for re-checking a single package during fix verification;
        # a normal audit passes neither flag.
        roots = [scope / 'src' / args.package]
    else:
        roots = default_roots
        if not roots:
            print('audit.py: no package under src/ and no extra root; running the project-level checks only', file=sys.stderr)
            for check in auditme.registry.PROJECT_CHECKS:
                run_check(check, scope, scope)
            return 0

    for root in roots:
        if not root.is_dir():
            reason = 'is not a directory' if root.exists() else 'not found'
            print(f'ERROR: {root} {reason}', file=sys.stderr)
            return 2

    # These read only the project, so the scope stands in for the root they
    # ignore. They run once, not once per root.
    for check in auditme.registry.PROJECT_CHECKS:
        run_check(check, scope, scope)

    # One pass per root, rather than one pass over src/ itself. src_root.name
    # is the package's dotted root: six checks build module names as
    # '.'.join((src_root.name,) + parts). Handing them src/ would rename every
    # module to src.<pkg>.<mod>, silently breaking the import-graph and
    # public-surface checks and every AGENTS.md acceptance row, which are
    # written without the src. prefix. Running per root keeps each name right.
    for src_root in roots:
        for check in auditme.registry.CHECKS:
            run_check(check, scope, src_root)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
