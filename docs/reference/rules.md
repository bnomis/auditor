# Rules

The shared Claude Code rules the auditme checker enforces live here beside
it, in `claude/rules/auditme/`.
`bin/install-claude.sh` links that directory into `~/.claude/rules/auditme/`,
next to the rules the agents repository installs
(`bnomis/agents`, <https://bnomis.github.io/agents/reference/rules/>).

Each starts with `paths:` frontmatter, so Claude Code loads it only when
Claude works with a matching file. Their links to rules that stay in agents
(`../python/testing.md`, `../security.md`, ...) are relative to
`~/.claude/rules/`, so they resolve once both repositories are installed.

| File | Requires |
|---|---|
| `auditme/coding-standards.md` | Python 3.14; ruff as configured; full type annotations with built-in generics and `\|` unions; no leading underscores; f-strings; alphabetical ordering of enum-like collections; nothing defined in `__init__.py`; `loguru` for logging. |
| `auditme/dependencies.md` | Declare dependencies in `pyproject.toml` via `uv add`; commit `uv.lock` and never hand-edit it; no `pip install`. |
| `auditme/imports.md` | Full import paths (no `from X import Y` outside `__init__.py` re-exports), no `as` imports, no wildcard imports, no `from __future__ import annotations`. |

## Rules enforced by a check

The checks below run as this repository's pre-commit hooks or as rules of the
auditme checker; [The audit checker](../guide/checker.md) says what each
checker rule reports and how to accept a hit. `rule-scope.md`,
`git-conventions.md` and `python/asserts.md` are rules of the agents
repository; the others are the rules above. No hook or checker rule checks
any other rule.

### `rule-scope.md`

The `no-project-names` hook fails a file or a commit message that names a
project on a list kept outside the repository. It runs at the `pre-commit` and `commit-msg` stages, both as
published and in this repository's own config.

### `git-conventions.md`

The requirement that a script-checkable rule be a hook is met by the
`auditme-changed` hook at `pre-commit` and `auditme-all` at `pre-push`, plus
the ruff and shellcheck hooks a project's `.pre-commit-config.yaml` pins.
Nothing checks commit message format or branch names.

### `auditme/coding-standards.md`

| Requirement | Checker rule |
|---|---|
| Follow the project's ruff configuration | `ruff` (runs `ruff check` and `ruff format --check` with the project's config), `ruff-version-drift` (the ruff the audit runs differs from the ruff hook's `rev`) |
| No leading underscores | `leading-underscore-def-class`, `leading-underscore-const-upper`, `leading-underscore-const-lower`, `leading-underscore-self`, `leading-underscore-attribute-access`, `leading-underscore-binding`, `underscore-forloop-target-read`, `underscore-unpack-target-read` |
| f-strings | `legacy-formatting-percent`, `legacy-formatting-format` |
| Built-in generics and `\|` unions | `legacy-typing`, `typing-deprecated-alias`, `bare-parametric-annotation`, `bare-nonbuiltin-generic-annotation` |
| No `from __future__ import annotations` | `future-annotations` |
| `loguru`, not stdlib `logging` | `stdlib-logging` |
| Nothing defined in `__init__.py` | `def-class-in-init` |
| Alphabetical ordering | `non-alphabetical-literal`, `non-alphabetical-dict-keys` |

### `auditme/imports.md`

| Requirement | Checker rule |
|---|---|
| Full import paths | `from-import`, `relative-import-nonpackage` |
| No wildcard imports | `wildcard-imports` |
| No `as` imports | `aliased-imports`; also `as-import`, which fires only when the project's `AGENTS.md` declares the ban |
| No `from __future__ import annotations` | `future-annotations` |

### `auditme/dependencies.md`

`lockfile-drift` runs `uv lock --check` when the project has both
`pyproject.toml` and `uv.lock`, and reports a lockfile that no longer matches
`pyproject.toml`.

### `python/asserts.md`

No checker rule. Ruff reports `assert` as `S101` in a project whose ruff
config selects the `S` (bandit) rules, and the checker's `ruff` rule passes
that hit through.
