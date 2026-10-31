#!/usr/bin/env bash
# Fail when a file names a project that this shared repository must not
# mention (claude/rules/rule-scope.md). The names cannot be listed here - the
# list would name them - so they are read from a file outside the repository:
# one name per line in $AGENTS_FOREIGN_NAMES, default
# ~/.config/agents/foreign-names. Blank lines and lines starting with # are
# skipped. Matching is whole-word and ignores case.
#
# Usage: check-foreign-names.sh <file>...
set -euo pipefail

list="${AGENTS_FOREIGN_NAMES:-$HOME/.config/agents/foreign-names}"
if [ ! -f "$list" ]; then
    echo "check-foreign-names: no list at $list; nothing checked" >&2
    exit 0
fi

patterns=$(grep -v -E '^[[:space:]]*(#|$)' "$list" || true)
if [ -z "$patterns" ] || [ "$#" -eq 0 ]; then
    exit 0
fi

if grep -H -n -i -w -F -e "$patterns" -- "$@"; then
    echo
    echo "These lines name a project. This repository is shared: write 'one project'"
    echo "or a neutral name (pkg, probe, AppSettings) instead; see claude/rules/rule-scope.md."
    exit 1
fi
exit 0
