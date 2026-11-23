#!/usr/bin/env bash
# Install or update the auditor's pre-commit hooks in a git repository: add
# the auditor block to its .pre-commit-config.yaml, or move the block's rev to
# a newer commit, then install the git hooks. An entry that clones over SSH
# moves to the HTTPS URL, which CI can clone without a key. See
# docs/reference/cli.md.
set -euo pipefail

AUDITOR_URL=https://github.com/bnomis/auditor
AUDITOR_PATTERN='github\.com[:/]bnomis/auditor(\.git)?'
AGENTS_PATTERN='github\.com[:/]bnomis/agents(\.git)?'

usage() {
    echo 'usage: install-hooks.sh [--rev <commit>] [--push] [--no-install] [--dry-run] [<repo-path>]' >&2
}

fail() {
    echo "install-hooks: $2" >&2
    exit "$1"
}

rev=''
push=0
install=1
dry_run=0
target=''
while [ $# -gt 0 ]; do
    case "$1" in
        --rev)
            [ $# -ge 2 ] || { usage; fail 2 '--rev needs a commit'; }
            rev=$2
            shift 2
            ;;
        --rev=*)
            rev=${1#--rev=}
            shift
            ;;
        --push) push=1; shift ;;
        --no-install) install=0; shift ;;
        --dry-run) dry_run=1; shift ;;
        -h | --help) usage; exit 0 ;;
        -*) usage; fail 2 "unknown option: $1" ;;
        *)
            [ -z "$target" ] || { usage; fail 2 "more than one repository given: $1"; }
            target=$1
            shift
            ;;
    esac
done

target=${target:-.}
[ -d "$target" ] || fail 2 "not a directory: $target"
top=$(git -C "$target" rev-parse --show-toplevel 2>/dev/null) || fail 2 "not a git repository: $target"

if [ -z "$rev" ]; then
    rev=$(git ls-remote "$AUDITOR_URL" refs/heads/main 2>/dev/null | cut -f1) || rev=''
    [ -n "$rev" ] || fail 1 "cannot read the main branch of $AUDITOR_URL; check the network, or pass --rev <commit>"
fi
[[ "$rev" =~ ^[0-9a-f]{7,40}$ ]] || fail 2 "--rev must be a commit hash: $rev"

if [ "$install" -eq 1 ] && [ "$dry_run" -eq 0 ] && ! command -v pre-commit > /dev/null; then
    fail 1 'pre-commit is not installed (uv tool install pre-commit), or pass --no-install'
fi

config="$top/.pre-commit-config.yaml"
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
new="$scratch/config.yaml"

block() {
    # $1: the indent of a repo entry.
    printf '%s- repo: %s\n%s  rev: %s\n%s  hooks:\n%s    - id: auditme-changed\n%s    - id: auditme-all\n' \
        "$1" "$AUDITOR_URL" "$1" "$rev" "$1" "$1" "$1"
    if [ "$push" -eq 1 ]; then
        printf '%s      stages: [manual, pre-push]\n' "$1"
    fi
}

if [ ! -e "$config" ]; then
    { echo 'repos:'; block '  '; } > "$new"
    action="created $config"
else
    [ -f "$config" ] || fail 1 "not a file: $config"
    if grep -Eq "^[[:space:]]*-?[[:space:]]*repo:[[:space:]]*['\"]?[^[:space:]]*${AGENTS_PATTERN}" "$config" &&
        grep -Eq 'id:[[:space:]]*auditme-' "$config"; then
        fail 1 "$config pins the audit hooks from bnomis/agents; move it first (docs/setup.md, Moving a project from agents)"
    fi
    blocks=$(grep -Ec "^[[:space:]]*-[[:space:]]*repo:[[:space:]]*['\"]?[^[:space:]]*${AUDITOR_PATTERN}['\"]?[[:space:]]*$" "$config" || true)
    [ "$blocks" -le 1 ] || fail 1 "$config has more than one auditor repo entry; keep one"
    grep -Eq '^repos:[[:space:]]*(#.*)?$' "$config" || fail 1 "$config has no block-style top-level 'repos:' list"

    if [ "$blocks" -eq 1 ]; then
        # Move the block's rev, and add whichever audit hook it lacks.
        awk -v pattern="$AUDITOR_PATTERN" -v url="$AUDITOR_URL" -v rev="$rev" -v push="$push" '
            function indent_of(line) { match(line, /^[ ]*/); return RLENGTH }
            function flush_missing() {
                if (!in_block || added) return
                hook = sprintf("%*s", hook_indent, "")
                if (!has_changed) print hook "- id: auditme-changed"
                if (!has_all) {
                    print hook "- id: auditme-all"
                    if (push) print hook "  stages: [manual, pre-push]"
                }
                added = 1
            }
            {
                lines[NR] = $0
            }
            END {
                # First pass: find the block, its hooks line and what it holds.
                for (i = 1; i <= NR; i++) {
                    line = lines[i]
                    if (!found && line ~ /^[ ]*-[ ]*repo:/ && line ~ pattern) {
                        found = 1; start = i; repo_indent = indent_of(line); stop = NR
                        continue
                    }
                    if (found && i > start && stop == NR && line ~ /[^ ]/ && line !~ /^[ ]*#/ && indent_of(line) <= repo_indent) stop = i - 1
                }
                for (i = start + 1; i <= stop; i++) {
                    if (lines[i] ~ /^[ ]*hooks:[ ]*(#.*)?$/) hooks_line = i
                    if (lines[i] ~ /^[ ]*-[ ]*id:[ ]*auditme-changed[ ]*(#.*)?$/) has_changed = 1
                    if (lines[i] ~ /^[ ]*-[ ]*id:[ ]*auditme-all[ ]*(#.*)?$/) has_all = 1
                    if (!hook_indent && lines[i] ~ /^[ ]*-[ ]*id:/) hook_indent = indent_of(lines[i])
                }
                if (!hook_indent) hook_indent = repo_indent + 4
                if (!hooks_line) { print "install-hooks: the auditor entry has no hooks: list" > "/dev/stderr"; exit 3 }
                for (i = 1; i <= NR; i++) {
                    line = lines[i]
                    if (i > start && i <= stop && line ~ /^[ ]*rev:/) {
                        match(line, /^[ ]*rev:[ ]*/)
                        old = substr(line, RLENGTH + 1)
                        sub(/[ ]*#.*$/, "", old)
                        print substr(line, 1, RLENGTH) rev
                        print old > "/dev/stderr"
                        continue
                    }
                    if (i == start) {
                        # Move an SSH or non-canonical URL to the HTTPS one.
                        match(line, /repo:[ ]*/)
                        head = substr(line, 1, RSTART + RLENGTH - 1)
                        rest = substr(line, RSTART + RLENGTH)
                        match(rest, /^[^ #]*/)
                        old_url = substr(rest, 1, RLENGTH)
                        gsub(/[\047"]/, "", old_url)
                        if (old_url != url) line = head url substr(rest, RLENGTH + 1)
                    }
                    print line
                    if (i == hooks_line) { in_block = 1; flush_missing() }
                }
            }
        ' "$config" > "$new" 2> "$scratch/old-rev" || {
            [ -s "$scratch/old-rev" ] && cat "$scratch/old-rev" >&2
            fail 1 "cannot update the auditor entry in $config"
        }
        old_rev=$(cat "$scratch/old-rev")
        if [ "$old_rev" = "$rev" ]; then
            action="the auditor hooks are pinned at $rev"
        else
            action="moved the auditor hooks from ${old_rev:-no rev} to $rev"
        fi
        canonical="repo:[[:space:]]*${AUDITOR_URL}[[:space:]]*\$"
        if ! grep -Eq -- "$canonical" "$config"; then
            action="$action, cloned from $AUDITOR_URL"
        fi
    else
        # Add the block at the end of the repos list.
        # The first entry's indent, or two spaces when the list is empty.
        width=$(awk '/^repos:/ { inside = 1; next } inside && /^[ ]*-[ ]*repo:/ { match($0, /^[ ]*/); print RLENGTH; exit }' "$config")
        block "$(printf '%*s' "${width:-2}" '')" > "$scratch/block"
        awk -v blockfile="$scratch/block" '
            function emit() {
                if (last != "" && last !~ /^repos:/) print ""
                while ((getline b < blockfile) > 0) print b
                done = 1
            }
            /^repos:/ { inside = 1; print; last = $0; next }
            inside && !done && /^[A-Za-z_]/ { emit(); print "" }
            { print; last = $0 }
            END { if (!done) emit() }
        ' "$config" > "$new"
        action="added the auditor hooks at $rev to $config"
    fi
fi

if [ -e "$config" ] && cmp -s "$config" "$new"; then
    echo "install-hooks: $action; $config is unchanged"
elif [ "$dry_run" -eq 1 ]; then
    if [ -e "$config" ]; then old_file=$config; else old_file=/dev/null; fi
    diff -u -L "$old_file" -L "$config" "$old_file" "$new" || true
    echo "install-hooks: dry run; would have $action"
    exit 0
else
    if command -v pre-commit > /dev/null; then
        (cd "$top" && pre-commit validate-config "$new") > "$scratch/validate" 2>&1 || {
            cat "$scratch/validate" >&2
            fail 1 "the new $config does not validate; nothing changed"
        }
    fi
    cp "$new" "$config"
    echo "install-hooks: $action"
fi

[ "$dry_run" -eq 0 ] || exit 0
if [ "$install" -eq 1 ]; then
    (cd "$top" && pre-commit install --hook-type pre-commit --hook-type pre-push)
fi
