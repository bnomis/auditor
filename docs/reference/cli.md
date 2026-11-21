# Command line and hooks

Reference for the scripts in this repository and the hooks it publishes. For
installation see [Setup](../setup.md); for what the checker's rules report
see [The checker](../guide/checker.md).

## `bin/install-claude.sh`

```text
bin/install-claude.sh [--dry-run] [any other install-in-claude option]
```

Links the contents of `claude/` into `~/.claude/`, and registers the Stop
hook, by running the shared installer
[install-in-claude](https://github.com/bnomis/install-in-claude) at the commit
pinned in the script's `INSTALL_IN_CLAUDE_REV`:

```shell
uvx --from "git+ssh://git@github.com/bnomis/install-in-claude.git@$INSTALL_IN_CLAUDE_REV" \
    install-in-claude --source "$REPO/claude" \
    --append 'hooks.Stop[auditme-stop.sh]={"hooks":[{"type":"command","command":"bash \"$HOME/.claude/hooks/auditme-stop.sh\""}]}'
```

Its own arguments pass through: `bin/install-claude.sh --dry-run` prints what
would change and changes nothing. It needs `uv`, and SSH access to
`bnomis/install-in-claude` for the first run of a pinned commit; `uvx` caches
it after that. The shared rules, the other skills and the status line are
installed by the agents repository's own installer.

What the installer does, in short (its README has the detail):

- Checks every option and reads `~/.claude/settings.json` first; a settings
  file that is not a valid JSON object stops it, exit `1`, before anything is
  linked or written.
- For each top-level entry of `claude/` (dotfiles skipped): a file becomes a
  symlink in `~/.claude/`; a directory (`hooks/`, `skills/`) becomes a real
  directory in `~/.claude/` whose entries are symlinks, so
  `~/.claude/skills/auditme` links to `claude/skills/auditme/`. Links are
  relative. An existing symlink is replaced; an existing file is renamed with
  a `.orig` suffix (numbered when that name is taken).
- Prints any dangling symlinks in `~/.claude/` and its immediate
  subdirectories, with a quoted `rm` command to remove them. It does not
  remove them.
- Adds the Stop hook entry to `~/.claude/settings.json` unless a `Stop` entry
  already names `auditme-stop.sh`. Every other key and hook is kept; the first
  original is copied to `settings.json.orig`; the file is written atomically
  and keeps its mode.

| Exit | Meaning |
|---|---|
| `0` | Installed, or nothing to do |
| `1` | `settings.json` is not valid JSON or not a JSON object; nothing changed |
| `2` | A bad argument; nothing changed |

Environment: `HOME`.

To upgrade the installer, set `INSTALL_IN_CLAUDE_REV` to a newer commit
(`git ls-remote git@github.com:bnomis/install-in-claude.git refs/heads/main`,
first field) and run `bin/install-claude.sh --dry-run` to see what it changes.

## `claude/skills/auditme/checks/audit.py`

```text
audit.py [-h] [--package PACKAGE] [--extra-root DIR] scope
```

The checker driver. Runs every registered check over the project at `scope`
and prints one JSON object per hit on stdout. It reads the tree and writes
nothing.

| Option | Effect |
|---|---|
| `scope` | Project root. |
| `--package PACKAGE` | Audit only `src/PACKAGE`. Drops the extra roots and the loose-module check. For re-checking one package; a normal audit passes neither option. |
| `--extra-root DIR` | Audit `DIR` (relative to `scope`) as its own pass. Repeatable. Replaces the default extra root, `bin/`; each named directory must exist. |

Without options it audits every package under `src/`, each in its own pass,
then `bin/` when it exists and holds `.py` files. A `.py` file directly in
`src/` is reported as `src-loose-module`. A project with neither, such as one
with no Python, still gets the project-level checks, once: the lockfile
(`lockfile-drift`) and the ruff pin (`ruff-version-drift`).

Each output line carries `rule`, `variant`, `path`, `line`, `evidence`,
`accepted` and `accepted_reason`; a hit from a rule that compares several
files also carries `related`, the other files involved. Identical hits are
printed once. A check that raises is reported as an `auditme-check-crash`
hit, and the sweep continues.

| Exit | Meaning |
|---|---|
| `0` | Sweep completed, whatever it found; also when there is no root to audit (a notice goes to stderr and only the project-level checks run) |
| `2` | `scope`, a named `--extra-root` or the `--package` directory does not exist; or an argument error |

The exit status does not reflect hits: callers read stdout.

Environment: the checks run `ruff` and `uv` as subprocesses with the caller's
environment, finding them through `PATH` (ruff from the project's
`.venv/bin/ruff` first). When `uv lock --check` fails because of a user-level
`exclude-newer` setting, it is rerun with `UV_NO_CONFIG` set.

## `claude/skills/auditme/checks/changed.py`

```text
changed.py [-h] [--all] [--base BASE] [repo_root]
```

The entry of the `auditme-changed` and `auditme-all` hooks. Runs `audit.py`
over the whole tree with the same interpreter (timeout 600 seconds), then
reports every unaccepted hit in scope. It writes nothing.

| Option | Effect |
|---|---|
| `repo_root` | Repository root. Default: `git rev-parse --show-toplevel` of the working directory. |
| `--all` | Report every unaccepted hit, not only those in changed files. |
| `--base BASE` | Diff base. Default: the first of `@{upstream}`, `origin/main`, `main` that resolves. A value starting with `-` is refused. |

Without `--all`, the scope is the files changed in `BASE...HEAD` plus those
changed in the index or working tree against `HEAD`, deletions excluded. A
hit is in scope when its `path` or any of its `related` paths is in scope, so
a cross-file hit on an untouched file fails when its peer changes.

Without `--all`, the sweep is skipped (exit `0`, with a message) when:

- no diff base resolves; or
- no changed file is reportable: a `.py` file, a `uv.lock`, or a `.md` file
  outside hidden directories and outside `.git`, `.venv`, `node_modules`,
  `__pycache__`, `audit-reviews` and `tasks`.

Each reported hit prints as `path:line  rule` with its variant indented
beneath, then how to accept a hit and how to skip the hook once
(`SKIP=auditme-changed git commit`, or `SKIP=auditme-all git push` with
`--all`). All output goes to stdout.

| Exit | Meaning |
|---|---|
| `0` | No unaccepted hit in scope; the sweep was skipped as above; or `--help` |
| `1` | An unaccepted hit in scope; or any failure: argument error, `--base` refused, git failed, the sweep timed out, exited non-zero, printed a line that is not a JSON object, or reported a crashed check (even one outside the scope) |

Environment: none directly; git and `audit.py` inherit the caller's.

## Published pre-commit hooks

`.pre-commit-hooks.yaml` publishes these hooks for other projects to pin by
`rev`. This repository runs the same entries from its own tree as `repo:
local` hooks in `.pre-commit-config.yaml`, so a checker change applies in the
commit that makes it.

| Hook id | Stages as published | Entry | Checks | In this repository |
|---|---|---|---|---|
| `auditme-changed` | `[pre-commit]` | `claude/skills/auditme/checks/changed.py` | Unaccepted checker hits in the files the change touches | Same stage |
| `auditme-all` | `[manual]` | `claude/skills/auditme/checks/changed.py --all` | Unaccepted checker hits anywhere | `[manual, pre-push]`: runs on every push |

Both audit hooks set `pass_filenames: false` and `always_run: true`: they
find their own scope and run even when no file is staged.
Each hook uses `language: script`, so the entry runs from the hook
repository with the interpreter its shebang finds (`python3` for
`changed.py`).

To run the manual hook by hand:

```shell
pre-commit run auditme-all --hook-stage manual --all-files
```

This repository's config also runs `ruff-check`, `ruff-format` and
`shellcheck`, and the agents repository's `no-project-names` hook, pinned
from `bnomis/agents`; those come from their own repositories and are not
published here.

## The Stop hook

`claude/hooks/auditme-stop.sh` is a Claude Code Stop hook: Claude Code runs it
when Claude is about to end a turn, with the event JSON on stdin.

It does nothing (exit `0`, no output) when:

- the payload's `stop_hook_active` is `true`, meaning the turn is already
  continuing because of an earlier block, so it blocks at most once in a row;
- the working directory is not in a git repository;
- the project is not opted in: its root `.pre-commit-config.yaml` does not
  contain the text `id: auditme-changed`.

Otherwise it runs the installed checker, not the project's pinned one, from
the repository root:

```shell
python3 -I "$HOME/.claude/skills/auditme/checks/changed.py"
```

When that exits `1` it prints `{"decision": "block", "reason": "<report>"}`,
and Claude Code keeps the turn going with the report as the reason. Since
`changed.py` exits `1` on a failed sweep as well as on hits, a sweep that
cannot run also blocks.

It also blocks when the checker never ran, so a broken install cannot turn
the audit off without a word:

- when `~/.claude/skills/auditme/checks/changed.py` is missing or a dangling
  link, it blocks without running it, naming the path; run
  `bin/install-claude.sh` in this repository to install it again;
- when `changed.py` exits with any status other than `0` or `1` (for example
  `127` for no `python3`), it blocks with the status and the output.

As with every block, it blocks at most once in a row. The hook itself always
exits `0` and writes nothing to disk.

Requires `jq`, `git` and `python3` on `PATH`. Environment: `HOME`.

### Registration

`bin/install-claude.sh` adds it once to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$HOME/.claude/hooks/auditme-stop.sh\""
          }
        ]
      }
    ]
  }
}
```

It is global, but acts only in opted-in projects. Check it with
`grep -n 'auditme-stop.sh' ~/.claude/settings.json`.
