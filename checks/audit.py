#!/usr/bin/env python3
"""Audit checks driver.

Runs every mechanical check across the scope and emits JSON-lines.
Each line represents one hit. Callers (the auditme skill) must
transcribe every line into a finding - there is no sampling, filtering,
or "accepted because pre-existing" logic in the calling layer.

Usage:
    audit.py <scope-root> [--package <package-name>]

<scope-root> is the directory containing src/, agents/, docs/, etc.
<package-name> defaults to the single directory under src/.

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
    parser.add_argument('--package', help='Source package under src/ (default: first dir)', default=None)
    args = parser.parse_args()

    scope = args.scope.resolve()
    if not (scope / 'src').exists():
        print(f'ERROR: {scope}/src does not exist', file=sys.stderr)
        return 2

    if args.package:
        src_root = scope / 'src' / args.package
    else:
        children = sorted(p for p in (scope / 'src').iterdir() if p.is_dir())
        if not children:
            print(f'ERROR: no package under {scope}/src', file=sys.stderr)
            return 2
        src_root = children[0]

    if not src_root.exists():
        print(f'ERROR: {src_root} not found', file=sys.stderr)
        return 2

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
