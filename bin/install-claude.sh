#!/usr/bin/env bash
# Install the auditor CLI (an editable `uv tool install` of this repository),
# record this repository's git directory in ~/.claude/auditor-source for the
# Stop hook, then install this repository's Claude Code files (claude/) into
# ~/.claude and register the auditme Stop and SessionStart hooks, with the shared installer install-in-claude
# at the commit this repository was tested with. Extra arguments pass
# through, e.g. --dry-run.
set -euo pipefail

INSTALL_IN_CLAUDE_REV=fa68deb10fb77ed1c59f1c35a79a93881f955901

REPO=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

# $HOME stays literal: Claude Code expands it when it runs the hook.
# shellcheck disable=SC2016
STOP_HOOK='hooks.Stop[auditme-stop.sh]={"hooks":[{"type":"command","command":"bash \"$HOME/.claude/hooks/auditme-stop.sh\""}]}'

# shellcheck disable=SC2016
START_HOOK='hooks.SessionStart[auditme-standards.sh]={"hooks":[{"type":"command","command":"bash \"$HOME/.claude/hooks/auditme-standards.sh\""}]}'

uv tool install --editable "$REPO"
mkdir -p "$HOME/.claude"
git -C "$REPO" rev-parse --path-format=absolute --git-common-dir > "$HOME/.claude/auditor-source"

exec uvx --from "git+ssh://git@github.com/bnomis/install-in-claude.git@$INSTALL_IN_CLAUDE_REV" \
    install-in-claude --source "$REPO/claude" --append "$STOP_HOOK" --append "$START_HOOK" "$@"
