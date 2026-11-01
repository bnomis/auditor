#!/usr/bin/env bash
# Fail when a file names a project that a repository used across projects
# must not mention (claude/rules/rule-scope.md). The names cannot be listed here - the
# list would name them - so they are read from a file outside the repository:
# one name per line in $AGENTS_FOREIGN_NAMES, default
# ~/.config/agents/foreign-names. Blank lines and lines starting with # are
# skipped. Matching is whole-word and ignores case.
#
# A repository used across projects runs the hook on itself too; its own
# names are passed as --allow=<name> (any case) and are not matched.
#
# Usage: check-foreign-names.sh [--allow=<name>]... <file>...
set -euo pipefail

allowed=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --allow=*) allowed+=("${1#--allow=}"); shift ;;
        --) shift; break ;;
        *) break ;;
    esac
done

list="${AGENTS_FOREIGN_NAMES:-$HOME/.config/agents/foreign-names}"
if [ ! -f "$list" ]; then
    echo "check-foreign-names: no list at $list; nothing checked" >&2
    exit 0
fi

patterns=$(grep -v -E '^[[:space:]]*(#|$)' "$list" || true)
for name in "${allowed[@]+"${allowed[@]}"}"; do
    patterns=$(printf '%s\n' "$patterns" | grep -v -i -x -F -e "$name" || true)
done
if [ -z "$patterns" ] || [ "$#" -eq 0 ]; then
    exit 0
fi

if grep -H -n -i -w -F -e "$patterns" -- "$@"; then
    echo
    echo "These lines name a project. This repository is used across projects: write 'one project'"
    echo "or a neutral name (pkg, probe, AppSettings) instead; see claude/rules/rule-scope.md."
    exit 1
fi
exit 0
