#!/usr/bin/env bash
# Claude Code Stop hook: block the end of a turn once while the changed files
# of an opted-in project carry unaccepted auditme hits. Opt-in means the
# project's .pre-commit-config.yaml lists the auditme-changed hook.
set -uo pipefail

payload=$(cat)

# Already continuing because of an earlier block: let the turn end.
if [ "$(printf '%s' "$payload" | jq -r '.stop_hook_active // false')" = "true" ]; then
    exit 0
fi

root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
grep -q 'id: auditme-changed' "$root/.pre-commit-config.yaml" 2>/dev/null || exit 0

# The installed checker, not the project's pinned one: this is the early warning.
report=$(cd "$root" && python3 -I "$HOME/.claude/skills/auditme/checks/changed.py" 2>&1)
status=$?
if [ "$status" -eq 1 ]; then
    printf '%s' "$report" | jq -Rs '{decision: "block", reason: .}'
fi
exit 0
