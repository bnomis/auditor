# Project setup

**Version:** 1.11
**Status:** implemented
**Date:** 2026-10-31
**Review page (1.11):** https://claude.ai/artifact/XQ1bgLekKX9gPJJt9QGDFX

Every project that uses these rules and skills should get the same mechanical
guards by default: the auditme sweep on every commit, the whole-tree sweep in
CI, and the Claude Code Stop hook that refuses to end a turn over unaccepted
hits. Today only one project has them, built inside that project, and each copy
has gaps. This spec moves the guards into this repository, publishes them as
pre-commit hooks that a project pins by revision, adds a
`/auditme-project-setup` skill that installs them in a new project or adopts
them into an existing one, and documents the whole setup for a new machine, a
new user and a new project.

## Motivation

Found 2026-10-31 by a full audit of a project that had the guards (its review
recorded why 344 unaccepted hits had passed every check). Each gap is in the
design, not the project:

- **The commit hook reports only files the branch changed.** When the checker
  gained a rule, every hit it found in files nobody touched afterwards stayed
  invisible: 341 of the 344, in 37 files of which one had been committed since
  the rule shipped.
- **Cross-file rules name one file.** A rule comparing two files emits a hit on
  each location; when the changed file's copy carries an accept marker, the hit
  that remains names the unchanged file, which the scope filter drops. All three
  non-alias hits were this case.
- **In CI the scope is empty.** On a push the diff base `origin/main` is the
  pushed commit itself, so no file counts as changed; that project's CI printed
  "no new audit hits in changed files ... Passed" over a tree holding 341 or more
  unaccepted hits.
- **Only one project had any of it.** Of the projects checked out beside this
  repository on 2026-10-31, one carried the hook; the rest had pre-commit
  configurations with no audit step.
- **The checker is unpinned.** Projects run the skill through the
  `~/.claude/skills` symlink, so a checker change reaches every project the
  moment it is committed here, with no commit in the project to show its
  catch-up surface - the auditme skill's own failure mode 1.
- **The checker refuses a project without `src/<package>/`** (amendment 1.2,
  found 2026-10-31 by walking `docs/setup.md` in a throwaway repository pinned
  at `3974fbb`). Committing `bin/tool.py` failed `auditme-changed` with `the
  audit sweep exited 2: ERROR: <repo>/src does not exist`, and a loose
  `src/a.py` failed with `ERROR: no package under <repo>/src`. `main()` in
  `audit.py` returns 2 before `bin/` is considered, and `changed.py` fails on
  any non-zero exit, so no commit touching a `.py` file can pass. Of the git
  repositories beside this one on 2026-10-31, 19 of 24 had no `src/`, this
  repository among them, so `adopt` blocks them as `new` does. The two guards
  date from the first checker (2026-05-03), which audited only `src/`; extra
  roots came later and the guards were never revisited. The operator chose on
  2026-10-31 to audit whatever roots exist.
- **The checker's ruff is not the hook's ruff** (amendment 1.4, found
  2026-11-01 in one adopting project's own `TODO.md`). The CI audit runs
  `ruff` from the project's `.venv`, where a dependency cooldown had locked an
  older ruff than the `rev` of the project's `ruff-pre-commit` hook. Both
  versions passed the tree that day, but any later difference between them
  makes the commit hook and the CI audit disagree. `check_ruff` runs a bare
  `ruff` from `PATH`; `docs/setup.md` and `templates/ci.yml` point it at the
  `.venv`; nothing ties that version to the hook's `rev`. This repository has
  the gap itself: on 2026-11-01 its `uv.lock` held ruff 0.17.1 and its
  `.pre-commit-config.yaml` pinned `rev: v0.17.3`. The operator chose on
  2026-11-01 to check it rather than only document it.
- **The audit's ruff depends on the shell** (amendment 1.5, found 2026-11-01
  on the first push after 1.4 merged). The operator's shell had another ruff
  (0.17.3) first on `PATH`, so the push gate ran it against this
  repository's `rev: v0.17.1` and failed, while CI, which puts `.venv/bin`
  first, passed. The same tree gave two answers, the disagreement 1.4 was
  written to stop. The operator chose on 2026-11-01 that the checker prefers
  the project's own ruff.
- **The Stop hook passes silently when the installed checker is missing**
  (amendment 1.6, found 2026-11-21 in the survey made before the checker
  moved out of the agents repository). The hook blocked only on exit 1, so a
  missing or dangling `~/.claude/skills/auditme` (status 2) or no `python3`
  (status 127) turned the end-of-session audit off without a word.
- **The spec still named the agents repository** (amendment 1.7, found
  2026-11-21 in a review of `TODO.md`). When the checker moved here,
  `5a8eb69` moved the skill and its templates to `bnomis/auditor`,
  `AUDITOR_DEPLOY_KEY` and the `github-auditor` alias, but this spec kept the
  agents repository's hook block, upgrade command, secret, alias and
  deploy-key steps. 1.7 matches them to the templates. The rules it cites
  (`git-conventions.md`, `rule-scope.md`) stay in the agents repository and
  are named as its.
- **A project with no audit root skipped the project-level checks**
  (amendment 1.8, found 2026-10-31 as the known limit of 1.2, fixed
  2026-11-21 at the operator's request). With no package under `src/` and no
  extra root, the driver ran no pass, so the lockfile and ruff-pin checks
  never ran and a project with no Python passed them unchecked.
- **The skill's name was too general** (amendment 1.9, decided by the
  operator on 2026-11-21). `/project-setup` read as a skill for setting up
  any project, beside other installed skills; it is renamed
  `/auditme-project-setup`, in `claude/skills/auditme-project-setup/`. This
  spec keeps its own name and path, since it covers the hooks, the Stop hook
  and the guide as well as the skill. Dated task lists and `DONE.md` keep the
  old name: they are records.
- **The installer is shared** (amendment 1.10, decided by the operator on
  2026-11-21). `bin/install-claude.py` was one of several copies of the same
  script, each hard-coding its project's settings. It is replaced by
  `bin/install-claude.sh`, which runs the shared installer `install-in-claude`
  (`git@github.com:bnomis/install-in-claude.git`) at a pinned commit with
  `uvx`, passing this repository's `claude/` and the Stop hook as arguments.
  The installer's own behaviour - linking, the `.orig` copies, the
  dangling-link report, the settings merge - is specified and tested there;
  what this spec keeps is the arguments.
- **The audit read none of this repository's own Python** (amendment 1.11,
  found 2026-11-21 when `/auditme` was run on this repository). The roots were
  fixed by layout - each package under `src/`, then `bin/` - and every line of
  this repository's Python lives under `claude/skills/`, so `audit.py` gave no
  hits, the Phase B listers found no candidates for A1, A4 or T1, and the
  commit and push hooks checked nothing here. Swept by hand with the
  directories passed as `--extra-root`, the same tree gave 659 hits, 654
  unaccepted, on 2026-11-21. `--extra-root` reached only one hand run: the
  hooks run `audit.py <repo-root>` with no options, and `phaseb.py` takes
  none. The operator chose on 2026-11-21 that a project declares its roots in
  `pyproject.toml`, that the declared list replaces the defaults, and that
  each root says how its modules are named.

## Module location

| Path | What it is |
|------|------------|
| `claude/skills/auditme/checks/changed.py` | The changed-files runner (new): runs the sweep, filters by scope, exits non-zero on unaccepted hits |
| `claude/skills/auditme/checks/auditme/core.py` | `_emit()` gains the optional `related` field |
| `claude/skills/auditme/checks/auditme/rules/*.py` | Each cross-file rule passes `related` |
| `.pre-commit-hooks.yaml` | At the repository root (new): publishes `auditme-changed` and `auditme-all` |
| `claude/hooks/auditme-stop.sh` | The Stop hook (new) |
| `bin/install-claude.sh` | Runs the shared installer, which also registers the Stop hook in `~/.claude/settings.json` (1.10; was `bin/install-claude.py`) |
| `claude/skills/auditme-project-setup/SKILL.md` | The skill (new), with `templates/` beside it |
| `docs/setup.md` | The user guide (new); `README.md` gains an overview linking to it |
| `claude/skills/auditme/tests/test_changed.py`, `tests/test_install_claude.py` | Tests (new); 1.10: `test_install_claude.py` tests the wrapper's arguments |
| `claude/skills/auditme/checks/audit.py` | 1.2: drops the `src/` guards, emits `src-loose-module` |
| `claude/skills/auditme/checks/auditme/core.py` | 1.2: `loose_src_modules()` (new) |
| `claude/skills/auditme/tests/test_driver.py` | 1.2: the no-`src/` cases replace the two error tests |
| `claude/skills/auditme/checks/auditme/rules/project_hygiene.py` | 1.4: `check_ruff_version()` (new) |
| `claude/skills/auditme/checks/auditme/registry.py` | 1.4: `check_ruff_version` appended to `CHECKS` |
| `claude/skills/auditme/tests/test_project_hygiene.py` | 1.4: the `ruff-version-drift` cases; 1.5: the `.venv` ruff cases |
| `claude/skills/auditme/checks/auditme/rules/project_hygiene.py` | 1.5: `ruff_executable()` (new), used by `check_ruff` and `check_ruff_version` |

## API

### The runner

```python
def changed_files(repo_root: pathlib.Path, base: str) -> frozenset[str]:
    """Repository-relative paths changed in base...HEAD, deletions excluded.

    Side effect: runs `git diff --name-only --diff-filter=d`.

    Raises:
        ChangedError: git cannot be run, or the diff fails.
    """


def in_scope(hit: Mapping[str, object], scope: frozenset[str] | None) -> bool:
    """Whether a hit is reported: always when scope is None (--all), else when its
    path or any of its related paths is in scope. Pure."""


def main(argv: Sequence[str] | None = None) -> int:
    """0 when no unaccepted hit is in scope, 1 otherwise or on any failure."""


class ChangedError(Exception):
    """The runner could not decide which files changed, or could not run the sweep."""
```

Invocation: `changed.py [--all] [--base <ref>] [<repo-root>]`, `<repo-root>`
defaulting to `git rev-parse --show-toplevel` of the working directory.

### The driver (1.2)

```python
def loose_src_modules(scope: pathlib.Path) -> list[pathlib.Path]:
    """Every `.py` file directly in `<scope>/src/`, outside any package, sorted.

    Empty when `src/` is absent. Pure apart from reading the directory.
    """
```

Invocation is unchanged: `audit.py <scope-root> [--package <name>]
[--extra-root <dir> ...]`. `src/` becomes optional.

### The ruff version check (1.4)

```python
def check_ruff_version(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Emit a `ruff-version-drift` hit when the ruff the audit runs (see
    `ruff_executable`, 1.5) is not the version the project's `ruff-pre-commit`
    hook pins, or when the pin cannot be read.

    Project-level: reads `<scope>/.pre-commit-config.yaml` and runs
    `ruff --version` in `scope`; `src_root` is unused. Silent when the file is
    absent, holds no `ruff-pre-commit` repo, or ruff is not installed.
    """


def ruff_executable(scope: pathlib.Path) -> tuple[str, str]:
    """(1.5) Return (command, label) for the ruff the audit runs: the
    project's `.venv/bin/ruff` when it is an executable file, labelled
    `.venv/bin/ruff`, else `ruff` from PATH, labelled `ruff on PATH`."""
```

### The hooks

`auditme-changed` (commit stage) and `auditme-all` (manual stage), published in
`.pre-commit-hooks.yaml`; see [The published hooks](#the-published-hooks).

**The push gate (1.3, decided by the operator on 2026-10-31).** A project with
no unaccepted hits also runs `auditme-all` on push, by overriding its stages in
its own config (`stages: [manual, pre-push]` under `- id: auditme-all`). The
manifest keeps `[manual]`, so a project adopted over a backlog is not blocked
on every push. The push gate is switched on at the same moment as the CI gate:
by `new` through the template, and by `adopt` only when the count is zero.
This reconciles the spec with the agents repository's
`claude/rules/git-conventions.md`, which runs
whole-tree checks at `pre-push` and in CI, and gives the `pre-push` git hook
that both `new` and the guide install a check to run. The sweep took 1-21
seconds on the repositories measured on 2026-10-31, and each commit already
pays one.

### The skill

```text
/auditme-project-setup new [<path>]
/auditme-project-setup adopt [<path>]
```

`<path>` defaults to the working directory's repository root. Frontmatter
matches the other skills in `claude/skills/`, with
`allowed_tools: [Read, Write, Edit, Bash, AskUserQuestion]`.

## Error handling

| Failure | Result |
|---------|--------|
| git missing, or `git diff` / `rev-parse` fails for a reason other than an unresolved ref | `ChangedError`, exit 1 |
| `--base` starting with `-` | exit 1, before git runs |
| No base resolves (no upstream, no `origin/main`, no `main`) | exit 0 with a message |
| Sweep timeout, exception, non-JSON line, or an `auditme-check-crash` hit | exit 1 naming the cause |
| Unaccepted hits in scope | exit 1, listing them |
| Stop hook: project not opted in, or `stop_hook_active` already true | exit 0, no output |
| Stop hook: installed `changed.py` missing or a dangling link (1.6) | block, naming the path and `bin/install-claude.sh` |
| Stop hook: `changed.py` exits other than 0 or 1 (1.6) | block, carrying the status and output |
| `install-claude.sh`: `~/.claude/settings.json` is not valid JSON | the shared installer refuses, naming the file, exit 1; nothing linked or written (1.10) |
| `audit.py`: `<scope-root>` is not a directory (1.2) | `ERROR: <scope> is not a directory`, exit 2 |
| `audit.py`: no package under `src/` and no extra root (1.2, 1.8) | notice on stderr, the project-level checks run once, exit 0 |
| `[tool.auditme]` is not a table, `roots` is not a list of tables, an entry has no `path`, an unknown key, or a `modules` other than `package` or `top-level` (1.11) | `ERROR: pyproject.toml [tool.auditme]: <what is wrong>`, exit 2; the hooks then fail as a sweep that cannot run |
| `pyproject.toml` is not valid TOML (1.11) | `ERROR: pyproject.toml: <the parser's message>`, exit 2, but only when the file mentions `[tool.auditme]`; otherwise the defaults apply and the lockfile check reports the file as before |
| a declared root that does not exist, or holds no `.py` file (1.11) | `ERROR: declared root <path> not found` or `... holds no .py file`, exit 2 |
| two declared roots that would sweep a file twice (1.11) | `ERROR: declared roots <a> and <b> overlap`, exit 2 |
| `audit.py`: a `.py` file directly in `src/` (1.2) | one unaccepted `src-loose-module` hit per file |
| `audit.py --package <name>` naming a missing package | unchanged: `ERROR: <root> not found`, exit 2 |
| `ruff-version-drift`: no `.pre-commit-config.yaml`, or no `ruff-pre-commit` repo in it (1.4) | no hit |
| `ruff-version-drift`: no ruff to run, neither `.venv/bin/ruff` nor one on `PATH` (1.4, 1.5) | no hit; `check_ruff` already reports `ruff not installed` |
| `ruff-version-drift`: the repo has no `rev:`, or a `rev:` that is neither a version nor carries a `# frozen: <version>` comment (1.4) | one unaccepted hit, variant `the ruff-pre-commit rev names no version` |
| `ruff-version-drift`: `ruff --version` prints no `ruff X.Y.Z` (1.4) | one unaccepted hit, variant `ruff --version printed no version` |

## Implementation

### The changed-files runner

A generic version of the runner the motivating project keeps in its own `bin/`,
with the gaps closed. It is stdlib-only, like the rest of the checker.

- **Diff base**, when neither `--all` nor `--base` is given: the first of
  `@{upstream}`, `origin/main`, `main` that resolves. None resolving exits 0 with
  a message (a repository with no history to compare). A `--base` starting with
  `-` is refused before git runs.
- **The sweep** runs as a subprocess, `[sys.executable, <checks>/audit.py,
  <repo-root>]`, the `audit.py` beside `changed.py`, with no `--package`, so it
  covers the whole tree and cross-file rules see every file. `audit.py` itself is
  unchanged apart from `related` (amended 2026-10-31: the first draft said
  in-process, which contradicted the timeout and non-JSON handling below and
  named a driver function `audit.py` does not have).
- **Skip when nothing reportable changed**: as today, a scope holding no `.py`
  file, no reportable `.md` file and no `uv.lock` exits 0 without sweeping. The
  reportable set is read from the checker's own constants, not mirrored.
- **Output**: each reported hit as `path:line  rule`, then its variant, then how
  to accept one (`# auditme: accept[<rule>] <reason>`) and how to skip once
  (`SKIP=auditme-changed git commit`; with `--all`, which runs on push and in
  CI, `SKIP=auditme-all git push`, 1.3).

**Cross-file hits carry `related`.** `_emit()` takes an optional
`related: list[str]` of repository-relative paths, omitted when empty so a hit
without it is byte-identical to today's. Every rule whose predicate compares
locations in two or more files sets it to the other locations' paths:
`literal-duplication`, `paired-sibling-helpers`, `duplicate-call-sequence`,
`recompile-duplication`, `spec-api-signature-drift` (the source file),
`asymmetric-exception-translation` (the callee's file) and
`mutable-module-level-exported` (the reading modules). A test asserts the list,
so a cross-file rule added later without `related` fails it. This changes the
JSONL bytes of those rules' hits; it ships between audit cycles, and each
project's next audit summary notes it.

**A sweep that cannot run fails.** The project-local runner skipped (exit 0) when
the skill was missing, the sweep timed out or crashed; that is the same fail-open
as the empty CI scope. Here a missing checker cannot happen (the hook runs the
checker beside it), and a timeout, crash, non-JSON line or `auditme-check-crash`
hit exits 1 naming the cause. The timeout is 600 seconds.

### Projects without a `src/` package (1.2)

`audit.py` audits whatever roots exist, instead of requiring `src/<package>/`:

1. The `src/ does not exist` guard is replaced by a check that `<scope-root>`
   is a directory, so a mistyped scope is still an error.
2. The `no package under src` guard is removed. `_audit_roots()` already
   returns `[]` for a missing `src/`, so a project with only `bin/` is swept
   over `bin/`. With no root at all, the driver prints
   `audit.py: no package under src/ and no extra root; running the
   project-level checks only` on stderr, runs the project-level checks once
   (1.8, below), and exits 0.
3. **Loose modules.** Before the first pass, and only when `--package` is
   not given, the driver emits one hit per path from `loose_src_modules()`:
   `rule='src-loose-module'`, `variant='module directly under src/, outside
   any package'`, `path='src/<name>.py'`, `line=1`, `evidence=<name>.py`.
   Acceptance is the usual inline marker on line 1, read with
   `_accept_reason(lines, 1, rule='src-loose-module')`. Such a file belongs
   to no root, so without this hit it would never be audited, and the Python
   rules' layout is `src/<project>/`. It is emitted by the driver, not
   registered in `CHECKS`, because a registered check runs once per root and
   a project holding only `src/a.py` has none.
4. `--package` and `--extra-root` keep their errors for a missing name.
   `changed.py` is unchanged: a loose file is a `.py` file, so it triggers
   the sweep.

Output for a project with a package under `src/` and no loose module beside
it is unchanged byte for byte. The one existing layout whose output changes is
a package plus a loose `src/*.py`, which today passes with the loose file
never audited.

**Project-level checks without a root (1.8).** `auditme.registry` names the
checks that read only the project, never the root they are handed, as
`PROJECT_CHECKS`: `check_lockfile` and `check_ruff_version`. Each is also in
`CHECKS`, in the same order, so a project with a root runs them as before
and its output is unchanged. With no root, the driver runs `PROJECT_CHECKS`
alone, once, passing the scope as the unused root, with the same crash
isolation as a pass. The checks that read `AGENTS.md` and the spec-drift
check are not among them: they judge or accept Python definitions and hits,
so with no Python they have nothing to compare.

### Declared audit roots (1.11)

A project whose Python is not laid out as `src/<package>/` and `bin/` declares
its roots in `pyproject.toml`:

```toml
[tool.auditme]
roots = [
    { path = "claude/skills/auditme/checks/auditme" },
    { path = "claude/skills/auditme/checks", modules = "top-level" },
    { path = "claude/skills/auditme/tests" },
]
```

- `path` is relative to the project root and must be a directory holding at
  least one `.py` file.
- `modules` is `"package"` (the default) or `"top-level"`.
  - A `package` root is swept recursively, and a module is named after the
    root as today (`module_dotted`): `checks/auditme/core.py` under the root
    `checks/auditme` is `auditme.core`.
  - A `top-level` root is a directory on `sys.path`: only the `.py` files
    directly in it are swept, each named by its stem (`checks/audit.py` is
    `audit`), and its subdirectories are left to their own roots. So a
    package inside it is declared as a `package` root of its own, and no file
    is swept twice.
- The declared list replaces the default roots, in the order given. A project
  that also has `src/` packages lists them. A project with no `[tool.auditme]`
  table, or no `pyproject.toml`, keeps the defaults unchanged.
- `--extra-root` on the command line replaces the declared list for that run,
  each named root swept as a `package` root; `--package` is unchanged.
- No two `package` roots may nest, and no `top-level` root may sit inside a
  `package` root, since either would sweep a file twice.

Every consumer reads the roots through `_audit_roots()` in `core.py`, which
now reads the table, so `audit.py`, the hooks' `changed.py` (which runs
`audit.py <repo-root>`) and the Phase B listers in `phaseb.py` all follow it
with no new option. `corpus_py_files()` spans the declared roots too. The modes
reach the helpers through one module-level table in `core.py`,
`ROOT_MODULES: types.MappingProxyType[pathlib.Path, str]`, rebound (never
mutated) when the roots are read, as the driver rebinds `EXTRA_ROOT_NAMES`
today; `_all_py_files()` and `module_dotted()` consult it, so no check's
call site changes. A root absent from the table is a `package` root, which is
every root a test builds by hand.

**This repository's roots.** `pyproject.toml` declares
`claude/skills/auditme/checks/auditme` (package),
`claude/skills/auditme/checks` (top-level),
`claude/skills/auditme/tests`, `claude/skills/auditme-project-setup/tests`
and `tests` (each package). Declaring them exposes the backlog measured in
the motivation, so, as `adopt` does for a project with a backlog, the same
change takes `pre-push` off `auditme-all` in `.pre-commit-config.yaml` (the
commit hook stays on, so a commit cannot add hits to the files it changes)
and files a `TODO.md` item recording the count by rule and the date, whose
fix direction is to fix or accept every hit and then put `pre-push` back.
The first audit of this repository runs after that item is done.

### The ruff version check (1.4)

`check_ruff_version` is a project-level check like `check_lockfile`: it looks
at the project, not the root, so it emits the same hit on every pass and
`_emit()`'s de-duplication of identical lines leaves one. It is appended to
`CHECKS` (never inserted, as the auditme skill requires).

1. **Find the pin** by scanning `.pre-commit-config.yaml` line by line - the
   checker stays stdlib-only, so no YAML parser. A repo entry is a line
   matching `^\s*-\s*repo:\s*(\S+)`. The ruff one is the first whose URL,
   with a trailing `/` and `.git` removed, ends in `/ruff-pre-commit`. Its pin
   is the first line matching `^\s*rev:\s*['"]?([^'"\s#]+)['"]?\s*(#.*)?$`
   after the repo line and before the next repo entry.
2. **Read the pinned version**: the `rev` itself when it matches
   `^v?(\d+\.\d+\.\d+)$`; else the version in a trailing
   `# frozen: v?X.Y.Z` comment, which `pre-commit autoupdate --freeze` writes
   beside a commit SHA. Neither gives the `names no version` hit, anchored at
   the `rev:` line, or at the repo line when there is no `rev:`.
3. **Read the running version**: `ruff --version` with `cwd=scope`, run with
   the command `ruff_executable(scope)` gives, as `check_ruff` is (1.5); its stdout must match `^ruff (\d+\.\d+\.\d+)`.
   Otherwise the `printed no version` hit, anchored at the `rev:` line, with
   the first 200 characters of the output as evidence.
4. **Compare**: equal versions emit nothing. Different ones emit
   `rule='ruff-version-drift'`,
   `variant='the ruff the audit runs differs from the ruff-pre-commit rev'`,
   `path='.pre-commit-config.yaml'`, `line=<the rev: line>`,
   `evidence='<label> is <running>; the hook pins <rev>'`, `<label>` from
   `ruff_executable` (1.5). The evidence names both versions and which ruff
   ran, so it changes only when one of them does.

Acceptance is the usual inline marker, read with
`_accept_reason(lines, rev_line, rule='ruff-version-drift')`, so a YAML
comment `# auditme: accept[ruff-version-drift] <reason>` on the `rev:` line or
the line above it accepts the hit - for a cooldown that has not yet let the
hook's version into the lockfile, say. The fix is to make the two equal:
`uv add --dev ruff==<version>` to move the lock, or a `rev` change to move the
hook.

**Which ruff runs (1.5).** Both `check_ruff` and `check_ruff_version` run
the command `ruff_executable(scope)` returns: the project's
`<scope>/.venv/bin/ruff` when it is a file with the execute bit, else `ruff`
from `PATH`. The project's own ruff is the version its lockfile pins, so the
audit gives the same answer in every shell and in CI, whatever ruff a shell
finds first; `PATH` is only the fallback for a project with no `.venv`. 1.4
had both checks run whichever ruff was first on `PATH`.

**Catch-up surface.** This repository fires the check at once (0.17.1 locked,
`v0.17.3` pinned, on 2026-11-01), and so does any adopting project whose lock
and hook differ. Each project fixes or accepts its own hit when it next
updates its pinned hooks, as with any checker change. In this repository the
task list resolves the hit as recorded below.

**This repository's own hit (1.4, decided by the operator on 2026-11-01).**
Its ruff hook is lowered to `rev: v0.17.1`, the locked version, so the hook
and the lock run the same ruff today. A later `pre-commit autoupdate` raises
the hook again once the 14-day `exclude-newer` cooldown in `pyproject.toml`
admits a newer ruff, and the check then says to move the lock with it. The
alternative, accepting the hit until 0.17.3 cleared the cooldown, was
rejected: it leaves a marker someone must remember to remove.

### The published hooks

`.pre-commit-hooks.yaml` at the repository root:

```yaml
- id: auditme-changed
  name: no unaccepted audit hits in changed files
  entry: claude/skills/auditme/checks/changed.py
  language: script
  pass_filenames: false
  always_run: true
  stages: [pre-commit]
- id: auditme-all
  name: no unaccepted audit hits anywhere
  entry: claude/skills/auditme/checks/changed.py --all
  language: script
  pass_filenames: false
  always_run: true
  stages: [manual]
```

A project adds them by revision, which is what pins the checker:

```yaml
- repo: git@github.com:bnomis/auditor.git
  rev: <commit of this repository>
  hooks:
    - id: auditme-changed
    - id: auditme-all
```

`language: script` runs the file with its own `#!/usr/bin/env python3`, so the
interpreter is the one on `PATH`, which must meet this repository's
`requires-python`. Upgrading the checker is `pre-commit autoupdate --repo
git@github.com:bnomis/auditor.git` in the project: one commit, whose CI run shows
the new rules' catch-up surface.

#### CI

The CI step, in the project's workflow after its own setup:

```yaml
- name: Audit the whole tree
  run: pre-commit run auditme-all --hook-stage manual --all-files
```

The repository is private, so the runner needs read access to it. Decided with
the operator 2026-10-31: **a deploy key per project**. The project holds an
`AUDITOR_DEPLOY_KEY` secret, the private half of an SSH key added read-only to
this repository's deploy keys, and its workflow installs it before pre-commit
runs, with `Host github.com` / `IdentityFile` / `IdentitiesOnly yes` in
`~/.ssh/config`. A project that already uses a deploy key for another private
repository on the same host needs an `ssh` host alias per key, because GitHub
admits one deploy key per repository; the template uses `github-auditor` as the
alias and rewrites the hook's URL to it with `git config --global
url."git@github-auditor:bnomis/auditor.git".insteadOf
"git@github.com:bnomis/auditor.git"`.

### The Stop hook

`claude/hooks/auditme-stop.sh`, registered once. Decided with the operator
2026-10-31: **global, opt-in by project**.

- `bin/install-claude.sh` adds a `Stop` entry running the hook to
  `~/.claude/settings.json`, merging into what is there: it runs the shared
  installer with
  `--append 'hooks.Stop[auditme-stop.sh]={"hooks":[{"type":"command","command":"bash \"$HOME/.claude/hooks/auditme-stop.sh\""}]}'`,
  which adds the entry only if no `Stop` entry's JSON already names
  `auditme-stop.sh`, writes the result atomically, and keeps the original as
  `settings.json.orig` the first time. Running it twice changes nothing (1.10).
  The wrapper pins the installer's commit in `INSTALL_IN_CLAUDE_REV` and passes
  its own arguments through, so `bin/install-claude.sh --dry-run` shows the
  plan.
- The hook exits 0 at once unless the working directory is in a git repository
  whose `.pre-commit-config.yaml` lists `id: auditme-changed`.
- It exits 0 when the payload's `stop_hook_active` is true, so it blocks at most
  once per turn.
- Otherwise it runs `python3 -I ~/.claude/skills/auditme/checks/changed.py`; on
  exit 1 it prints the Claude Code block decision (`{"decision": "block",
  "reason": ...}`, built with `jq -Rs`) carrying the runner's report.
- When `changed.py` is not a file (missing, or a dangling link) it blocks
  without running it, with a reason naming the path and
  `bin/install-claude.sh`; on any status other than 0 and 1 it blocks with the
  status and the output, since `changed.py` itself exits only 0 or 1 (1.6).

It runs the **installed** checker, not the project's pinned one: it is the
earliest warning, and the binding gates - the commit hook and CI - run the pinned
one. A project's own `.claude/settings.json` Stop hook doing the same job is
removed when the project adopts this one, or every turn runs the sweep twice.

### The `/auditme-project-setup` skill

`claude/skills/auditme-project-setup/SKILL.md`, invoked as
`/auditme-project-setup new [<path>]` or
`/auditme-project-setup adopt [<path>]`. It confirms before each outward-facing step (creating a deploy key, setting a secret,
committing) and never pushes.

**`new`**, in an empty or freshly initialised repository:

1. Write `.pre-commit-config.yaml` from `templates/pre-commit-config.yaml`: ruff
   check and format, shellcheck, and the two auditme hooks pinned to this
   repository's `origin/main` commit, with `auditme-all` at
   `[manual, pre-push]` (1.3).
2. Write `.github/workflows/ci.yml` from `templates/ci.yml`: checkout, the deploy
   key step, Python and uv, `uv sync`, `pre-commit run --all-files`, the
   `auditme-all` step and the project's test command (asked).
3. Write `AGENTS.md`, `CLAUDE.md` (`@AGENTS.md`), `TODO.md`, `DONE.md` and
   `claude/rules/README.md` from templates, the title from the project name.
4. Run `pre-commit install`, then the deploy-key steps below.

**`adopt`**, in an existing project:

1. Add the two hooks to `.pre-commit-config.yaml` (create it if absent); remove
   any project-local hook or Stop hook that does the same job, after showing it.
2. Run `pre-commit run auditme-all --hook-stage manual --all-files` and count the
   unaccepted hits by rule.
3. **Zero**: add the push stage (1.3), the CI step and the deploy-key steps.
   **More than zero**: file
   one `TODO.md` item recording the count by rule and the date, whose Fix
   direction is to fix or accept every hit and then add the push stage and the CI
   step - the gate is never enabled over a backlog, because a gate that fails every push is switched
   off, and one that is not switched on cannot be.
4. Commit the hook and `TODO.md` changes as `build(audit): adopt the shared audit
   hooks`, when the operator agrees.

**Deploy-key steps** (asked before each): `ssh-keygen -t ed25519 -N '' -f
<scratch>/auditor_deploy_key`; `gh repo deploy-key add <scratch>/auditor_deploy_key.pub
--repo bnomis/auditor --title <project>`; `gh secret set AUDITOR_DEPLOY_KEY --repo
<owner>/<project> < <scratch>/auditor_deploy_key`; then delete both files. The
private key is never printed.

## Documentation

`docs/setup.md`, the user guide, written for someone who has not seen this
conversation or the project that motivated it, in this order:

1. **What you get** - the guards, what each catches, and why the commit hook is
   scoped to changed files while CI sweeps the whole tree.
2. **A new machine** - prerequisites (`git`, `gh` authenticated, an SSH key on
   GitHub with access to this repository, `uv`, `pre-commit` via `uv tool
   install pre-commit`, Python meeting `requires-python`, `jq`); clone this
   repository; run `bin/install-claude.sh` (it needs `uv`); check it (`ls ~/.claude/skills`,
   the `Stop` entry in `~/.claude/settings.json`).
3. **A new user** - being given read access to this repository; their own SSH
   key; that rules and skills are shared and project specifics go in the
   project's `claude/` directory (the agents repository's
   `claude/rules/rule-scope.md`).
4. **A new project** - `/auditme-project-setup new`, what it writes, and the
   deploy key.
5. **An existing project** - `/auditme-project-setup adopt`, the backlog step,
   and enabling the CI gate.
6. **Upgrading the checker** - `pre-commit autoupdate`, and handling its
   catch-up hits in the same commit.
7. **Troubleshooting** - the hook cannot clone (SSH, the deploy key, the host
   alias); the Stop hook does not fire (not opted in, `jq` missing); hits appear
   only after an upgrade (expected); `SKIP=auditme-changed` for one commit.

Amendment 1.2: "What you get" says which files are audited - packages under
`src/<package>/` and scripts in `bin/` - that a `.py` file directly in `src/`
is reported as `src-loose-module`, and that other directories are not swept.
The auditme `SKILL.md` drops "the directory containing `src/`" from its
`<project-root>` wording, and documents `src-loose-module` beside the driver's
description of roots.

Amendment 1.4: `docs/setup.md`'s "ruff on `PATH`" requirement says the ruff
there must be the version the ruff hook's `rev` pins, that the sweep reports
`ruff-version-drift` when it is not, and how to make them equal (`uv add --dev
ruff==<version>`, or change the `rev`). The comment above
`templates/ci.yml`'s `.venv/bin` step says the same in one line. The auditme
`SKILL.md` documents `ruff-version-drift` beside the existing ruff check.

Amendment 1.11: "What you get" in `docs/setup.md` says that a project whose
Python lives elsewhere declares its roots in `[tool.auditme]`, with the
example above, and that undeclared directories are not swept.
`docs/reference/cli.md` documents the table, both `modules` values, how
`--extra-root` overrides it, and the new exit-2 errors; the auditme `SKILL.md`
names `[tool.auditme]` beside its description of roots.

Every command in it is runnable as written, with placeholders saying where the
value comes from. `README.md` gains a short section saying what the repository
is and linking to `docs/setup.md`.

## Testing

`uv run --no-project --with pytest pytest claude/skills/auditme/tests`, plus:

- `test_changed.py`, against a temporary git repository: scope from the diff
  base; `--all`; a hit reported through `related` when only its peer changed;
  `--base -x` refused; no base resolves; a sweep crash, timeout and non-JSON line
  each exit 1; nothing reportable changed skips the sweep.
- Each cross-file rule's test asserts its hits' `related`; `test_registry.py`
  asserts the set of rules that emit `related` equals the list above.
- `test_install_claude.py` (1.10): the wrapper, run with a stub `uvx` on
  `PATH`, passes the pinned commit, this repository's `claude/`, the Stop
  hook `--append` and its own arguments through; the commit is a full hash.
- The Stop hook: a shell test running it with a stub payload in an opted-in and a
  non-opted-in repository.
- 1.2, `test_driver.py`: `test_a_missing_src_directory_is_an_error` and
  `test_an_empty_src_directory_is_an_error` are replaced by cases for: a project
  with only `bin/` is swept over `bin/` and exits 0; an empty project exits 0
  with the stderr notice; a scope that is not a directory exits 2; a loose
  `src/a.py` gives one `src-loose-module` hit at line 1, with or without a
  package beside it; a line-1 `# auditme: accept[src-loose-module] <reason>`
  marker accepts it; `--package` emits none.
- 1.2, `test_changed.py`: in a temporary repository with no `src/`, a commit
  of a clean `bin/` script passes, and one with a hit in `bin/` fails.
- 1.4, `test_project_hygiene.py`, with a stub `ruff` script on a temporary
  `PATH` printing a chosen `ruff --version` line: equal versions give no hit;
  different ones give one hit at the `rev:` line naming both; a `v`-less
  `rev` compares the same; a SHA `rev` with `# frozen: v0.17.3` uses that
  version; a SHA `rev` with no comment, and a repo with no `rev:`, give the
  `names no version` hit; a stub printing no version gives the `printed no
  version` hit; no config file, a config without `ruff-pre-commit`, and no
  `ruff` on `PATH` give none; `# auditme: accept[ruff-version-drift] <reason>`
  on the `rev:` line, and on the line above it, accepts the hit, and a marker
  scoped to another rule does not; two roots give one hit, not two.
- 1.5, `test_project_hygiene.py`: a `.venv/bin/ruff` stub is preferred over a
  different ruff on `PATH`; a differing `.venv` ruff's hit names
  `.venv/bin/ruff` in its evidence; a `.venv/bin/ruff` without the execute bit
  falls back to `PATH`; `check_ruff` runs the `.venv` ruff when `PATH` has
  none.
- 1.11, `test_driver.py` and a new `test_roots.py`: a project with
  `[tool.auditme]` sweeps exactly its declared roots, in order, and not
  `src/` or `bin/`; a `top-level` root sweeps only its own files, named by
  stem, and a package inside it only as its own root; a `package` root names
  modules after the root as before; no table, or no `pyproject.toml`, keeps
  today's output byte for byte; `--extra-root` replaces the declared list;
  each error row above exits 2 with its message; `changed.py --all` and
  `phaseb.py plan` on a fixture with declared roots see the declared files
  (a hit there blocks, a candidate there is listed); `corpus_py_files()`
  spans the declared roots.

## Acceptance criteria

- A project pinning the hooks at this repository's commit fails a commit that
  adds an unaccepted hit, and fails CI on an unaccepted hit in a file the push
  did not touch.
- A cross-file hit whose named file is unchanged is reported when its peer
  changed.
- `audit.py`'s output is byte-identical to the previous commit's for every hit
  without `related`.
- `/auditme-project-setup new` in an empty repository and
  `/auditme-project-setup adopt` in an existing one each leave a working, committed setup; `adopt` adds no CI gate
  over a non-zero count.
- `docs/setup.md` takes a new machine from nothing to a passing hook run.
- 1.2: a project with no `src/` can commit a clean `bin/` script and is
  blocked by a hit in one; a loose `src/*.py` blocks the commit until it moves
  into a package or is accepted; output for a project with a `src/` package
  and no loose module is byte-identical to `3d7aed9`'s.
- 1.5: with another ruff first on `PATH`, a project whose `.venv/bin/ruff`
  equals its hook's `rev` gets no `ruff-version-drift` hit, in the push gate
  as in CI.
- 1.4: a project whose ruff differs from its `ruff-pre-commit`
  `rev` fails `auditme-changed --all` with one `ruff-version-drift` hit until
  the versions match or the hit is accepted; a project whose versions match,
  or that has no `ruff-pre-commit` hook, gets no new hit; this repository's
  own CI passes with its ruff hook at `rev: v0.17.1`.

## External dependencies

`git`, `pre-commit` (the remote-hook mechanism, `language: script`, the `manual`
stage), `gh` (deploy keys and secrets), `ssh-keygen`, `jq` (the Stop hook), and
GitHub deploy keys (read-only, one per repository). The checker stays
stdlib-only.

## Consumers

Background only; each is its own repository's work. The project whose review
motivated this adopts the hooks in its review task list, replacing its
`bin/audit-changed.*` and its own Stop hook, and that work waits for this spec's
implementation. Every other project adopts with `/auditme-project-setup adopt`.
