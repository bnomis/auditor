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
the extra roots, and a project with neither is reported and exits 0.
A .py file directly in src/ belongs to no root, so the driver reports it as a
src-loose-module hit (accepted by a line-1 marker) rather than skip it unseen.
<package-name> restricts the run to one package under src/. It defaults to
EVERY package under src/, each audited in its own pass, plus every extra root.

That default matters. A project whose src/ holds both the library and the test
tree - src/mylib/ and src/tests/ - has two packages, and a driver that audited
only the first would report a partial scope as a complete one. On the litrev
project that silently hid 440 hits, all of them in src/tests/, across five
audit cycles: the sweep looked clean because the test tree was never read.

An extra root is auditable Python that is not a package under src/. bin/ is
the default one, and the same failure had a second instance there: enumerating
packages *under src/* gave a project whose scripts live in bin/ zero rows for
them - accepted or otherwise - while three consecutive summaries recorded
"bin/ remains at zero unaccepted hits" as though it were a measurement.
--extra-root replaces that default set; each root named must exist.

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
        "accepted_reason": "<why, if accepted>"
    }

Acceptance is determined exclusively by:
    1. AGENTS.md "Accepted cross-layer exceptions" / "Accepted lazy imports" tables
    2. An inline `# auditme: accept <reason>` comment on the preceding or
       same line as the hit.

No other signal acts as acceptance. The existence of a finding in a
prior review, a decision note, or an assumption of intentionality does
NOT make a hit accepted. Callers must treat `accepted=false` as a
required finding.
"""

import argparse
import pathlib
import sys

import auditme.core
import auditme.registry
from auditme.core import _emit

DEFAULT_EXTRA_ROOTS = ', '.join(f'{name}/' for name in auditme.core.EXTRA_ROOT_NAMES)


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

    scope = args.scope.resolve()
    if not scope.is_dir():
        print(f'ERROR: {scope} is not a directory', file=sys.stderr)
        return 2

    if args.extra_root is not None:
        # A root named on the command line is not silently dropped when it is
        # missing: an unnoticed typo would reinstate exactly the empty pass
        # this flag exists to end.
        auditme.core.EXTRA_ROOT_NAMES = tuple(args.extra_root)
        for name in args.extra_root:
            if not (scope / name).is_dir():
                print(f'ERROR: {scope / name} is not a directory', file=sys.stderr)
                return 2

    if not args.package:
        # A module directly in src/ belongs to no root, so no pass would read
        # it. The driver reports it, not a registered check: a check runs once
        # per root, and a project holding only src/a.py has none.
        for path in auditme.core.loose_src_modules(scope):
            reason = auditme.core._accept_reason(auditme.core._source_lines(path), 1, rule='src-loose-module')
            _emit(
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
        roots = auditme.core._audit_roots(scope)
        if not roots:
            print('audit.py: no package under src/ and no extra root; nothing to audit', file=sys.stderr)
            return 0

    for root in roots:
        if not root.exists():
            print(f'ERROR: {root} not found', file=sys.stderr)
            return 2

    # One pass per root, rather than one pass over src/ itself. src_root.name
    # is the package's dotted root: six checks build module names as
    # '.'.join((src_root.name,) + parts). Handing them src/ would rename every
    # module to src.<pkg>.<mod>, silently breaking the import-graph and
    # public-surface checks and every AGENTS.md acceptance row, which are
    # written without the src. prefix. Running per root keeps each name right.
    for src_root in roots:
        for check in auditme.registry.CHECKS:
            try:
                check(scope, src_root)
            except Exception as exc:
                _emit(
                    rule='auditme-check-crash',
                    variant=check.__name__,
                    path=None,
                    line=None,
                    evidence=f'{type(exc).__name__}: {exc}',
                    accepted=False,
                    accepted_reason=None,
                )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
