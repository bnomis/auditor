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

block() {
    printf '%s' "$1" | jq -Rs '{decision: "block", reason: .}'
}

# The installed checker, not the project's pinned one: this is the early warning.
checker="$HOME/.claude/skills/auditme/checks/changed.py"
# -f follows a link, so a dangling one counts as missing.
if [ ! -f "$checker" ]; then
    block "The auditme checker is not installed: $checker is missing or a dangling link. Run bin/install-claude.py in the auditor repository to install it."
    exit 0
fi

report=$(cd "$root" && python3 -I "$checker" 2>&1)
status=$?
# changed.py exits only 0 or 1; any other status means it never ran.
if [ "$status" -eq 1 ]; then
    block "$report"
elif [ "$status" -ne 0 ]; then
    block "The auditme checker could not run (exit $status): $checker
$report"
fi
exit 0
