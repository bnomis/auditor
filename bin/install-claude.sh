#!/usr/bin/env bash
# Install this repository's Claude Code files (claude/) into ~/.claude, and
# register the auditme Stop hook, with the shared installer install-in-claude
# at the commit this repository was tested with. Extra arguments pass
# through, e.g. --dry-run.
set -euo pipefail

INSTALL_IN_CLAUDE_REV=fa68deb10fb77ed1c59f1c35a79a93881f955901

REPO=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

# $HOME stays literal: Claude Code expands it when it runs the hook.
# shellcheck disable=SC2016
STOP_HOOK='hooks.Stop[auditme-stop.sh]={"hooks":[{"type":"command","command":"bash \"$HOME/.claude/hooks/auditme-stop.sh\""}]}'

exec uvx --from "git+ssh://git@github.com/bnomis/install-in-claude.git@$INSTALL_IN_CLAUDE_REV" \
    install-in-claude --source "$REPO/claude" --append "$STOP_HOOK" "$@"
