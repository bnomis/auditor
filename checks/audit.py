#!/usr/bin/env python3
"""Audit checks driver.

Runs every mechanical check across the scope and emits JSON-lines.
Each line represents one hit. Callers (the auditme skill) must
transcribe every line into a finding - there is no sampling, filtering,
or "accepted because pre-existing" logic in the calling layer.

Usage:
    audit.py <scope-root> [--package <package-name>]

<scope-root> is the directory containing src/, agents/, docs/, etc.
<package-name> restricts the run to one package under src/. It defaults to
EVERY package under src/, each audited in its own pass.

That default matters. A project whose src/ holds both the library and the test
tree - src/mylib/ and src/tests/ - has two packages, and a driver that audited
only the first would report a partial scope as a complete one. On the litrev
project that silently hid 440 hits, all of them in src/tests/, across five
audit cycles: the sweep looked clean because the test tree was never read.

Each package gets its own pass rather than one pass over src/, because
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

import auditme.registry
from auditme.core import _emit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('scope', type=pathlib.Path, help='Project root (containing src/, agents/, ...)')
    parser.add_argument('--package', help='Audit only this package under src/ (default: every package)', default=None)
    args = parser.parse_args()

    scope = args.scope.resolve()
    if not (scope / 'src').exists():
        print(f'ERROR: {scope}/src does not exist', file=sys.stderr)
        return 2

    if args.package:
        src_roots = [scope / 'src' / args.package]
    else:
        src_roots = _packages_under(scope / 'src')
        if not src_roots:
            print(f'ERROR: no package under {scope}/src', file=sys.stderr)
            return 2

    for src_root in src_roots:
        if not src_root.exists():
            print(f'ERROR: {src_root} not found', file=sys.stderr)
            return 2

    # One pass per package, rather than one pass over src/ itself. src_root.name
    # is the package's dotted root: six checks build module names as
    # '.'.join((src_root.name,) + parts). Handing them src/ would rename every
    # module to src.<pkg>.<mod>, silently breaking the import-graph and
    # public-surface checks and every AGENTS.md acceptance row, which are
    # written without the src. prefix. Running per package keeps each name right.
    for src_root in src_roots:
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


def _packages_under(src: pathlib.Path) -> list[pathlib.Path]:
    """Every package directory directly under src/, sorted.

    Sorted because emission order is part of the output: CHECKS' order fixes
    the order within a package, and this fixes the order of the packages.

    Excludes caches and build artefacts, and any directory holding no .py file
    anywhere - not a package, and auditing it only slows the run.
    """
    if not src.is_dir():
        return []
    return sorted(
        p
        for p in src.iterdir()
        if p.is_dir()
        and not p.name.startswith('.')
        and p.name != '__pycache__'
        and not p.name.endswith(('.egg-info', '.dist-info'))
        and any(p.rglob('*.py'))
    )


if __name__ == '__main__':
    raise SystemExit(main())
