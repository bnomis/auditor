#!/usr/bin/env bash
# Fail when a file names a project that a repository used across projects
# must not mention (claude/rules/rule-scope.md in the agents repository). The
# names cannot be listed here - the list would name them - so they are read
# from a file outside the repository:
# one name per line in $AUDITOR_FOREIGN_NAMES, default
# ~/.config/auditor/foreign-names. Blank lines and lines starting with # are
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

list="${AUDITOR_FOREIGN_NAMES:-$HOME/.config/auditor/foreign-names}"
if [ ! -e "$list" ]; then
    echo "check-foreign-names: no list at $list; nothing checked" >&2
    exit 0
fi

if [ ! -f "$list" ] || [ ! -r "$list" ]; then
    echo "check-foreign-names: cannot read $list" >&2
    exit 2
fi

status=0
patterns=$(grep -v -E '^[[:space:]]*(#|$)' "$list") || status=$?
if [ "$status" -ge 2 ]; then
    echo "check-foreign-names: cannot read $list" >&2
    exit 2
fi
for name in "${allowed[@]+"${allowed[@]}"}"; do
    patterns=$(printf '%s\n' "$patterns" | grep -v -i -x -F -e "$name" || true)
done
if [ -z "$patterns" ] || [ "$#" -eq 0 ]; then
    exit 0
fi

unreadable=()
for file in "$@"; do
    { [ -f "$file" ] && [ -r "$file" ]; } || unreadable+=("$file")
done

status=0
matches=$(grep -H -n -i -w -F -e "$patterns" -- "$@" 2>/dev/null) || status=$?
[ -z "$matches" ] || printf '%s\n' "$matches"

if [ "${#unreadable[@]}" -gt 0 ]; then
    echo "check-foreign-names: cannot read: ${unreadable[*]}" >&2
fi
if [ -n "$matches" ]; then
    echo
    echo "These lines name a project. This repository is used across projects: write 'one project'"
    echo "or a neutral name (pkg, probe, AppSettings) instead; see claude/rules/rule-scope.md"
    echo "in the agents repository."
    exit 1
fi
if [ "$status" -eq 2 ]; then
    exit 2
fi
exit 0
