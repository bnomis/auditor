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

git_dir() {
    git -C "$1" rev-parse --path-format=absolute --git-common-dir 2>/dev/null
}

# The installed tool, not the project's pinned one: this is the early warning.
# A worktree of the very repository the tool was installed from runs its own
# code instead (`uv run --project`), so a branch that changes the checker is
# judged by that branch. Trust comes from the shared git directory that the
# installer recorded in ~/.claude/auditor-source, never from the files a
# repository holds: any other repository's src/auditor is never run.
source_file="$HOME/.claude/auditor-source"
if [ -f "$source_file" ] && [ -f "$root/src/auditor/cli.py" ]; then
    trusted=$(cat "$source_file")
    if [ -n "$trusted" ] && [ "$trusted" = "$(git_dir "$root")" ]; then
        command=(uv run --project "$root" auditor changed)
    fi
fi
if [ -z "${command+set}" ]; then
    if ! command -v auditor >/dev/null 2>&1; then
        block "The auditor CLI is not installed: run 'uv tool install <source>' (see docs/setup.md)."
        exit 0
    fi
    command=(auditor changed)
fi

report=$(cd "$root" && "${command[@]}" 2>&1)
status=$?
# auditor changed exits only 0 or 1; any other status means it never ran.
if [ "$status" -eq 1 ]; then
    block "$report"
elif [ "$status" -ne 0 ]; then
    block "The auditor CLI could not run (exit $status): ${command[*]}
$report"
fi
exit 0
