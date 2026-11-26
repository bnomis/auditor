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
  symlink in `~/.claude/`; a directory (`hooks/`, `rules/`, `skills/`) becomes a real
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
| `1` | `settings.json` is not valid JSON or not a JSON object, a key on the edit path is not an object, or `hooks.Stop` is not a list; nothing changed |
| `2` | A bad argument; nothing changed |

Environment: `HOME`.

To upgrade the installer, set `INSTALL_IN_CLAUDE_REV` to a newer commit
(`git ls-remote git@github.com:bnomis/install-in-claude.git refs/heads/main`,
first field) and run `bin/install-claude.sh --dry-run` to see what it changes.

## `bin/install-hooks.sh`

```text
bin/install-hooks.sh [--rev <commit>] [--push] [--no-install] [--dry-run] [<repo-path>]
```

Installs the audit hooks in another git repository, or moves them to a newer
commit of this one, by editing that repository's `.pre-commit-config.yaml`,
then installs its git hooks. `<repo-path>` is any path inside the repository;
the default is the current directory. Run it again whenever you want the
latest checker: a second run at the same commit changes nothing.

What it does to `.pre-commit-config.yaml`:

- **No file:** writes one holding only the auditor entry.
- **No auditor entry:** adds one at the end of the `repos:` list (before any
  top-level key that follows the list), indented like the list's first
  entry:

  ```yaml
  - repo: https://github.com/bnomis/auditor
    rev: <commit>
    hooks:
      - id: auditme-changed
      - id: auditme-all
  ```

- **An auditor entry** (by `git@github.com:bnomis/auditor.git` or
  `https://github.com/bnomis/auditor`, with or without `.git`): sets its
  `rev:` to the commit, dropping any comment on that line, moves its
  `repo:` to `https://github.com/bnomis/auditor` (which CI clones without a
  key), and adds
  `auditme-changed` or `auditme-all` if the entry lacks one. Every other
  line, the entry's `stages:` and `args:` included, stays as it was.

Then, unless `--no-install` or `--dry-run`, it runs
`pre-commit install --hook-type pre-commit --hook-type pre-push` in the
repository. When `pre-commit` is on `PATH` the new file is checked with
`pre-commit validate-config` before it replaces the old one.

| Option | Effect |
|---|---|
| `--rev <commit>` | Pin this commit (7 to 40 hex digits) instead of the current `main` of `bnomis/auditor`, read with `git ls-remote https://github.com/bnomis/auditor refs/heads/main` |
| `--push` | When it adds `auditme-all`, give it `stages: [manual, pre-push]`, so every push sweeps the whole tree. Leave it off for a project that still has unaccepted hits (see [An existing project](../setup.md#an-existing-project)); an `auditme-all` already in the file keeps its stages |
| `--no-install` | Edit the file only; do not run `pre-commit install` |
| `--dry-run` | Print the change as a unified diff and change nothing |

| Exit | Meaning |
|---|---|
| `0` | Installed or updated, already at the commit, or a dry run |
| `1` | Nothing changed, because: `main` of `bnomis/auditor` could not be read; `pre-commit` is needed and not installed; the file pins the audit hooks from `bnomis/agents` (move it first, see [Moving a project from agents](../setup.md#moving-a-project-from-agents)); it has more than one auditor entry, no block-style top-level `repos:` list, or an auditor entry with no `hooks:` list; or the new file fails `pre-commit validate-config` |
| `2` | A bad argument, a `--rev` that is not a commit hash, or a path that is not in a git repository; nothing changed |

It does not add the CI step: `/auditme-project-setup` does that (see
[An existing project](../setup.md#an-existing-project)). The CI step needs no
key, since the hooks clone over HTTPS from a public repository.

## `bin/check-foreign-names.sh`

```text
check-foreign-names.sh [--allow=<name>]... [--] <file>...
```

Fails when a file names a project on a list kept outside the repository, so
that the list itself is never committed. It is the entry of the
`no-project-names` hook and changes nothing on disk.

- The list is one name per line; blank lines and lines starting with `#` are
  skipped.
- Matching is whole-word, case-insensitive and literal (`grep -w -i -F`): a
  name inside a longer word does not match.
- `--allow=<name>` removes that name from the list for this run (compared
  case-insensitively against whole lines). Repeatable. A repository used
  across projects passes its own name this way.
- Each match is printed as `file:line:text`, followed by a pointer to
  `claude/rules/rule-scope.md` in the agents repository.

| Exit | Meaning |
|---|---|
| `0` | No match; or nothing exists at the list path (a notice goes to stderr and nothing is checked); or the list is empty after comments and `--allow`; or no files given |
| `1` | At least one match, even when another file is unreadable (a message naming it goes to stderr) |
| `2` | Something exists at the list path but it cannot be read as a file (a directory, or no read permission) (`check-foreign-names: cannot read <list>` on stderr), whatever the files; or no match, but a file could not be read (a message naming it goes to stderr) |

Environment: `AUDITOR_FOREIGN_NAMES` (path of the list), `HOME` (the default
list is `~/.config/auditor/foreign-names`).

## `auditor check`

```text
auditor check [-h] [--package PACKAGE] [--extra-root DIR] scope
```

The checker driver. Runs every registered check over the project at `scope`
and prints one JSON object per hit on stdout. It reads the tree and writes
nothing.

| Option | Effect |
|---|---|
| `scope` | Project root. |
| `--package PACKAGE` | Audit only `src/PACKAGE`, which must be a directory name directly under `src/` (a path or `..` exits 2). Drops the extra roots and the loose-module check. For re-checking one package; a normal audit passes neither option. |
| `--extra-root DIR` | Audit `DIR` (relative to `scope`) as its own pass, as a `package` root. Repeatable. Replaces the default extra root, `bin/`, and replaces any roots declared in `[tool.auditme]` for that run; each named directory must exist and resolve inside `scope` (one outside exits 2). |

Without options it audits every package under `src/`, each in its own pass,
then `bin/` when it exists and holds `.py` files. A `.py` file directly in
`src/` is reported as `src-loose-module`. A project with neither, such as one
with no Python, still gets the project-level checks, once: the lockfile
(`lockfile-drift`), the ruff pin (`ruff-version-drift`) and
`spec-api-signature-drift` over the project's Markdown.

### Declared roots

A project whose Python is not under `src/<package>/` and `bin/` declares its
roots in `pyproject.toml`:

```toml
[tool.auditme]
roots = [
    { path = "tools/mypkg" },
    { path = "tools", modules = "top-level" },
]
```

| Key | Meaning |
|---|---|
| `path` | Required. A directory relative to `scope` that holds at least one `.py` file. |
| `modules` | `"package"` (the default) or `"top-level"`. |

A `package` root is swept recursively and its modules are named after the root
(`tools/mypkg/core.py` is `mypkg.core`). A `top-level` root is a directory on
`sys.path`: only the `.py` files directly in it are swept, each named by its
stem, and its subdirectories are left to their own roots, so a package inside
it is declared as a `package` root of its own.

The declared list replaces the default roots, in the order given: a project
that also has `src/` packages lists them. With no `[tool.auditme]` table, or
no `pyproject.toml`, the defaults apply. `--extra-root` replaces the declared
list for one run. A declared root that resolves outside the project is an invalid declaration. No two `package` roots may nest, and no `top-level` root may
sit inside a `package` root. The hooks and the Phase B listers read the same
list.

### First-party libraries

`raises-section-drift` follows a call into a first-party library only when
the project lists the library's package directory:

```toml
[tool.auditme]
first-party = ["../lib/src/lib"]
```

Each entry is a directory named as its import name (`../lib/src/lib` for
`import lib`), relative to the project. It may lie outside the project. The
rule reads its `Raises:` sections and error classes, so an error the library
declares counts as a domain error, but never sweeps it: no hit is reported on
its files. A listed directory must exist wherever the sweep runs, CI
included, or the sweep stops with the errors below. Nothing is inferred from
`[tool.uv.sources]` or the environment.

### Never-accepted rules

`never-accepted` lists rules whose accept markers a project refuses:

```toml
[tool.auditme]
never-accepted = ["silent-broad-except", "layering-*"]
```

Each entry is a rule name, or a family ending in `*` (the `*` only at the
end). A hit of a listed rule is reported with `accepted` false and the
marker's reason in `refused_reason`; a hit with no marker carries no
`refused_reason`. `auditor changed` names the setting in its advice for such a hit.
The key can sit beside `roots`.

Each output line carries `rule`, `variant`, `path`, `line`, `evidence`,
`accepted` and `accepted_reason`; a hit from a rule that compares several
files also carries `related`, the other files involved. Identical hits are
printed once. A check that raises is reported as an `auditme-check-crash`
hit, and the sweep continues.

| Exit | Meaning |
|---|---|
| `0` | Sweep completed, whatever it found; also when there is no root to audit (a notice goes to stderr and only the project-level checks run) |
| `2` | `scope` is not a directory; `--package` is not a plain directory name, or its directory does not exist or is a file; a named `--extra-root` is outside `scope` or is not a directory; an argument error (argparse's usage message on stderr); `AUDITME_RUFF` is set to something that is not an executable file (`ERROR: AUDITME_RUFF=<value> is not an executable file`); or an invalid `[tool.auditme]` declaration, printed as `ERROR: <message>` on stderr with nothing on stdout (see below) |

The declaration errors, each exit `2`:

| Message | Cause |
|---|---|
| `pyproject.toml: not valid TOML (<parse error>)` | `pyproject.toml` is not valid TOML and mentions `[tool.auditme` |
| `pyproject.toml [tool.auditme]: must be a table` | `[tool.auditme]` is not a table |
| `pyproject.toml [tool.auditme]: unknown key '<key>'` | a key other than `roots`, `first-party` or `never-accepted` |
| `pyproject.toml [tool.auditme]: never-accepted must be a list of strings` | `never-accepted` is not a list of strings |
| `pyproject.toml [tool.auditme]: never-accepted '<pattern>' may use * only at the end` | a `*` anywhere but the last character |
| `pyproject.toml [tool.auditme]: never-accepted '<pattern>' matches no rule id` | a name or family that matches no rule |
| `pyproject.toml [tool.auditme]: roots must be a list of tables` | `roots` is not a list of tables |
| `pyproject.toml [tool.auditme]: unknown key '<key>' in a roots entry` | an entry has a key other than `path` or `modules` |
| `pyproject.toml [tool.auditme]: a roots entry has no path` | an entry lacks `path` |
| `pyproject.toml [tool.auditme]: modules must be 'package' or 'top-level', not '<value>'` | an invalid `modules` |
| `declared root <path> not found` | the directory does not exist |
| `declared root <path> holds no .py file` | no `.py` file (for `top-level`, none directly in it) |
| `declared roots <a> and <b> overlap` | two roots would sweep a file twice |
| `declared root <path> is outside the project` | the path resolves outside `scope`, as an absolute path or `..` does |
| `pyproject.toml [tool.auditme]: first-party must be a list of strings` | `first-party` is not a list of non-empty strings |
| `first-party path <path> not found` | the entry does not exist or is not a directory |
| `first-party path <path> holds no .py file` | no `.py` file in the directory |
| `first-party path <path> lies inside a root the sweep audits` | the entry is inside a swept root |

The hooks treat any of these as a sweep that cannot run, and `auditor phaseb`
exits `2` with the same message.

`auditor phaseb` exits `2` for a `--question` that is not a registered question, on every subcommand, before it builds a ledger path, and for a `<root>` that does not exist or is not a directory, so a mistyped root never reads as an empty listing.

It also exits `2`, printing `phaseb.py: ` and the error's message to stderr, whenever a Phase B step fails: for example a `merge` for a run planned for another question, or a `merge` whose batches fail `check`.

`auditor phaseb plan` records the callee depth it listed at (`--depth`, default 3)
in `plan.json`. `auditor phaseb merge` exits `2`, naming both depths and writing
nothing to the ledger, when its own `--depth` differs from the plan's: merge
with the plan's depth, or plan again. A `plan.json` written before the depth
was recorded is read as depth 3.

`--depth` is accepted by `candidates`, `plan`, `merge` and `report`, only for
the questions that follow callees (A4, T1 and T2), and must be at least 1.
For any other question, or a value below 1, the command exits `2` with a
usage error.

The exit status does not reflect hits: callers read stdout.

Environment: the checks run `ruff` and `uv` as subprocesses with the caller's
environment, finding them through `PATH` (ruff from `$AUDITME_RUFF` when set,
else the project's `.venv/bin/ruff`, first). `AUDITME_RUFF` is the path of an
executable ruff; `auditor check` exits `2` when it names anything else. When `uv lock --check` fails because of a user-level
`exclude-newer` setting, it is rerun with `UV_NO_CONFIG` set.

## `auditor rules`

Reports on the rules repository that `AUDITOR_RULES_PATH` names. Every command
prints `ERROR: ...` and exits non-zero when the variable is unset or the
repository is invalid.

```text
auditor rules list [--kind {check,project-check,question,standard}]
auditor rules check
auditor rules test [pytest args]
auditor rules standards
auditor rules questions [--category {A,D,Doc,P,S,Sec,T}]
auditor rules identity [--expect <json-file>]
auditor rules pending
```

| Command | What it does | Exit status |
|---|---|---|
| `list` | One line per rule: name, kind, what it emits or its id, title | 0 |
| `check` | Imports every entry file; reports imports outside the helper API package | non-zero on a bad import |
| `test` | Runs pytest over `rules/*/tests` with the `auditor.testing` plugin; extra arguments go to pytest | pytest's |
| `standards` | Prints every standard rule's `rule.md`, in name order | 0 |
| `questions` | Prints the Phase B checklist: id, title and `rule.md` of each question | 0 |
| `identity` | Prints the runner and rules identity as JSON; the audit skill records it in each review | with `--expect`, 1 when it differs from the file |
| `pending` | Lists the open items (the `## ` headings) of the rules repository's `TODO.md` | 1 when an item is open |

`auditor check` and `auditor phaseb` load the same repository and run its
rules in rule-name order.

## `auditor changed`

```text
auditor changed [-h] [--all] [--scope] [--base BASE] [repo_root]
```

The entry of the `auditme-changed` and `auditme-all` hooks. Runs `auditor check`
over the whole tree with the same interpreter (timeout 600 seconds), then
reports every unaccepted hit in scope. It writes nothing.

| Option | Effect |
|---|---|
| `repo_root` | Repository root. Default: `git rev-parse --show-toplevel` of the working directory. |
| `--all` | Report every unaccepted hit, not only those in changed files. |
| `--scope` | Run no sweep. Print one JSON line per changed `.py` or `.sh` file, `{"path": ..., "ranges": [[start, end], ...]}`: the lines changed since the merge base of `BASE` and `HEAD` (index and working tree included), each Python hunk widened to its enclosing function, else its enclosing class; shell hunks are kept as they are. A deleted file is not listed. Exit `0`; with no diff base, a message on stderr and exit `0`. |
| `--base BASE` | Diff base. Default: the first of `@{upstream}`, `origin/main`, `main` that resolves. A value starting with `-` is refused, whatever spelling of the option gave it (an abbreviation such as `--bas=`, or a repeat), and git is told where options end before it is passed the range. |

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
beneath, then how to accept a hit (a `ruff`, `lockfile-drift` or `never-accepted` hit gets its own advice instead, as no accept marker applies to any of them) and how to skip the hook once
(`SKIP=auditme-changed git commit`, or `SKIP=auditme-all git push` with
`--all`). All output goes to stdout, except argparse's usage errors and the no-diff-base message of `--scope`, which go to stderr.

| Exit | Meaning |
|---|---|
| `0` | No unaccepted hit in scope; the sweep was skipped as above; or `--help` |
| `1` | An unaccepted hit in scope; or any failure: argument error, `--base` refused, git failed, `--scope` cannot read a changed Python file, the sweep timed out, exited non-zero, printed a line that is not a JSON object, or reported a crashed check (even one outside the scope); or the audit sweep could not start, or the repository root could not be resolved |

Environment: none directly; git and `auditor check` inherit the caller's.

## Published pre-commit hooks

`.pre-commit-hooks.yaml` publishes these hooks for other repositories to pin
by `rev`. This repository runs the same entries from its own tree as `repo:
local` hooks in `.pre-commit-config.yaml`, so a checker change applies in the
commit that makes it.

| Hook id | Stages as published | Entry | Checks | In this repository |
|---|---|---|---|---|
| `auditme-changed` | `[pre-commit]` | `auditor changed` | Unaccepted checker hits in the files the change touches | Same stage |
| `auditme-all` | `[manual]` | `auditor changed --all` | Unaccepted checker hits anywhere | `[manual, pre-push]`: runs on every push |
| `no-project-names` | `[pre-commit, commit-msg]` | `bin/check-foreign-names.sh` | Project names in staged files and the commit message; `uv.lock` excluded | Same stages, no `--allow` |

Both audit hooks set `pass_filenames: false` and `always_run: true`: they
find their own scope and run even when no file is staged.
`no-project-names` receives the staged file names, or the commit message file
at `commit-msg`; a repository used across projects pins it with its own names
as `args: [--allow=<name>]`, and installs the `commit-msg` hook type
(`pre-commit install --hook-type commit-msg`).
The audit hooks use `language: python`, so pre-commit installs this
repository's `auditor` package into the hook's own environment and runs
`auditor changed` from it. `no-project-names` uses `language: script`, so its
entry runs from the hook repository with `bash`.

To run the manual hook by hand:

```shell
pre-commit run auditme-all --hook-stage manual --all-files
```

This repository's config also runs `ruff-check`, `ruff-format` and
`shellcheck`; those come from their own repositories and are not published
here.

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
auditor changed
```

The exception is a worktree of the auditor repository itself: when the git
directory that `bin/install-claude.sh` recorded in `~/.claude/auditor-source`
is the project's own shared git directory and the project holds
`src/auditor/cli.py`, the hook runs `uv run --project <root> auditor changed`
instead, so a branch that changes the checker is judged by that branch. Any
other repository's `src/auditor` is never run.

When that exits `1` it prints `{"decision": "block", "reason": "<report>"}`,
and Claude Code keeps the turn going with the report as the reason. Since
`auditor changed` exits `1` on a failed sweep as well as on hits, a sweep that
cannot run also blocks.

It also blocks when the checker never ran, so a broken install cannot turn
the audit off without a word:

- when `auditor` is not on `PATH` (and the project is not a trusted worktree),
  it blocks once, saying the auditor CLI is not installed; run
  `bin/install-claude.sh` in this repository to install it;
- when `auditor changed` exits with any status other than `0` or `1` (for example
  `127` for no `uv`), it blocks with the status and the output.

As with every block, it blocks at most once in a row. The hook itself always
exits `0` and writes nothing to disk.

Requires `jq`, `git` and `auditor` on `PATH` (and `uv` for a trusted worktree). Environment: `HOME`.

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
