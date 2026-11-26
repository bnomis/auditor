#!/usr/bin/env bash
# Claude Code SessionStart hook: put the rules repository's standards into the
# session's context. Claude Code adds a SessionStart hook's stdout to the
# context. Opt-in means the project's .pre-commit-config.yaml lists the
# auditme-changed hook, the same test as the Stop hook. When the standards
# cannot be read, the ERROR: line is printed instead, so the session says why
# they are missing. Always exits 0.
set -uo pipefail

root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
grep -q 'id: auditme-changed' "$root/.pre-commit-config.yaml" 2>/dev/null || exit 0

if ! command -v auditor >/dev/null 2>&1; then
    echo "ERROR: the auditor CLI is not installed: run 'uv tool install <source>' (see docs/setup.md)"
    exit 0
fi

auditor rules standards 2>&1
exit 0
