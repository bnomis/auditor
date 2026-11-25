# Auditor CLI

**Version:** 1.0
**Status:** approved
**Date:** 2026-11-25

Turns the auditme checker from scripts run by path
(`python3 ~/.claude/skills/auditme/checks/audit.py`) into an installable Python
package, `auditor`, with one command-line entry point. This is the first of
four specs that split the runner from the rules it checks, so that people and
projects other than this repository's author can install the runner and keep
their own rules:

1. **Auditor CLI** (this spec): the package and its commands, with behaviour
   unchanged.
2. [Rules repository](../rules-repository/spec.md): the rule format, the
   loader that reads rules from `$AUDITOR_RULES_PATH`, and the versioned
   helper API.
3. [Default rule catalogue](../default-rule-catalogue/spec.md): every
   existing rule moved into that format, and the built-in rules removed.
4. [Rules init](../rules-init/spec.md): `auditor rules init`, which creates a
   new rules repository from chosen packs of the catalogue.

Each spec requires the ones before it to be implemented.

This spec moves code and changes how it is invoked. It changes no rule, no
output and no exit status: the sweep of this repository gives the same JSON
lines before and after.

Decided with the user on 2026-11-25: the runner ships as a Python CLI that
`uv tool install` installs, plus the Claude Code skill and hooks that call it,
so it works with or without Claude Code.

## Module location

- `src/auditor/` - the package (new). Everything under
  `claude/skills/auditme/checks/` moves here:
  - `checks/auditme/` becomes `src/auditor/`, with the same module tree
    (`auditor.core`, `auditor.registry`, `auditor.rules.*`, `auditor.phaseb.*`).
  - `checks/audit.py` becomes `src/auditor/sweep.py`.
  - `checks/changed.py` becomes `src/auditor/changed.py`.
  - `checks/phaseb.py` becomes `src/auditor/phasebcli.py`.
  - `src/auditor/cli.py` (new) holds the dispatcher.
- `claude/skills/auditme/phaseb/briefs/` moves to `src/auditor/briefs/`, so
  that the briefs are installed with the package.
- `claude/skills/auditme/tests/` moves to `tests/checker/`.
- `pyproject.toml` gains `[build-system]`, `[project.scripts]` and the
  package layout.
- `.pre-commit-hooks.yaml`, `claude/hooks/auditme-stop.sh`,
  `bin/install-claude.sh`, `claude/skills/auditme/SKILL.md`,
  `claude/skills/auditme-project-setup/` and `docs/` call `auditor` instead of a
  script path.

## API

The command line is the interface. Each subcommand keeps the arguments, output
and exit statuses of the script it replaces:

```text
auditor check <project-root> [--package <pkg>] [--extra-root <dir> ...]
    # was: audit.py
auditor changed [--all] [--scope] [--base <ref>] [<repo-root>]
    # was: changed.py
auditor phaseb <candidates|plan|check|merge|report|dismiss> ...
    # was: phaseb.py
auditor --version
    # prints "auditor <version>", where the version is
    # importlib.metadata.version('auditor')
```

```python
# src/auditor/cli.py
def main(argv: collections.abc.Sequence[str] | None = None) -> int:
    """Dispatch `auditor <command>` to the command's own main and return its exit status.

    The command's own argument parser is used unchanged: `auditor check X` hands
    `['X']` to the parser that `audit.py X` used.

    Raises:
        SystemExit: an unknown command or `--help` (argparse's own exit, status 2 or 0).
    """
```

`[project.scripts]` maps `auditor = "auditor.cli:main"`.

## Error handling

- **Unknown command:** argparse prints the usage and the known commands, and
  exits 2.
- **Errors inside a command** keep the behaviour they have today. For example,
  `auditor check` reports an invalid `[tool.auditme]` as `ERROR: <message>` on
  stderr with exit 2, and `auditor changed` exits 1 on unaccepted hits.
- **`auditor` not on PATH:** the Stop hook (`claude/hooks/auditme-stop.sh`)
  blocks once with
  `The auditor CLI is not installed: run 'uv tool install <source>' (see docs/setup.md).`,
  replacing today's missing-checker message.
- **pre-commit hooks** install the package themselves, so a project never
  needs `auditor` on PATH for its hooks to run.

## Implementation

- **Package.** Use the `src/` layout with `uv_build` as the build backend:
  `requires = ["uv_build>=0.13.0,<0.14"]`. This was checked on 2026-11-25 with
  `uv build --wheel` under this repository's `exclude-newer = "14 days"`, using
  uv 0.13.9. Runtime dependencies stay empty, so the checker is still
  standard-library only. Version 0.2.0 marks the move.
- **Imports.** Imports are rewritten from `auditme.` to `auditor.` by full
  path, following `claude/rules/auditme/imports.md`. Every `sys.path.insert`
  that the scripts and `tests/conftest.py` do today is removed, because the
  package is installed.
- **Briefs.** These are found with `importlib.resources.files('auditor') / 'briefs'`
  rather than a path relative to `__file__`.
- **Stop hook.** The hook keeps its opt-in test and its block-once logic. It
  runs `auditor changed` from PATH. When the hook runs inside a worktree of
  this repository, it runs `uv run --project "$root" auditor changed` instead.
  As today, trust comes from the shared git directory, which here is the git
  directory of the repository the installed tool was built from: the installer
  records that directory in `~/.claude/auditor-source`. This keeps today's rule
  that a branch which changes the checker is judged by that branch.
- **pre-commit hooks.** `.pre-commit-hooks.yaml` changes the `auditme-changed`
  and `auditme-all` hooks to `language: python` with
  `entry: auditor changed` and `entry: auditor changed --all`. pre-commit
  installs the package at the pinned `rev`. The `no-project-names` hook is
  unchanged.
- **This repository's own hooks and CI.** `.pre-commit-config.yaml` runs the
  audit hooks from this repository's own tree rather than from a pinned
  `rev`. It keeps doing so: its local `auditme-changed` and `auditme-all`
  hooks become `language: system` with `entry: uv run auditor changed` and
  `entry: uv run auditor changed --all`, so that a commit is judged by the
  checker it changes.

  `.github/workflows/ci.yml` changes its pytest step to the new test command
  (`uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider`). Its other steps already go
  through these hooks. (Amendment of 2026-11-25: these two files were missing
  from the approved text.)
- **Installer.** `bin/install-claude.sh` runs
  `uv tool install --editable "$REPO"` before the `install-in-claude` step,
  and records the repository's git directory as above.
  `bin/install-hooks.sh` is unchanged; it only moves hook pins.
- **Skill and docs.** Every `python3 ~/.claude/skills/auditme/checks/...`
  command becomes the matching `auditor` command, in `SKILL.md`, the setup
  skill and its templates, `docs/`, `README.md` and `AGENTS.md`. The sweep's
  `phase-section-doc-reference` and the `Doc` questions are run afterwards, to
  find any command left over.
- **Equivalence.** Before the move, run the sweep of this repository and the
  Phase B candidate lists of every listed question, and save the output in the
  scratchpad. After the move, run the same commands through `auditor` and
  check that the output is byte-identical apart from `auditme` to `auditor` in
  paths.

## Settings

The existing settings are unchanged.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `AUDITME_RUFF` | env, path | unset (the project's `.venv` ruff, then PATH) | The ruff executable the sweep runs |
| `[tool.auditme] roots` | list of tables | `src/` packages and `bin/` | The roots the sweep passes over |
| `[tool.auditme] never-accepted` | list of str | `[]` | Rules whose accept markers never count |
| `[tool.auditme] first-party` | list of str | `[]` | Libraries `raises-section-drift` follows into |

## External dependencies

- **uv** (0.13.x) builds the package and installs the tool
  (`uv tool install`).
- **pre-commit** installs `language: python` hooks from a git `rev`.
- **jq** is used by the Stop hook, as today.

## Tests

- Every existing test passes from its new location under `tests/checker/`.
  The `AGENTS.md` and `README.md` test commands become
  `uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider`.
- A test runs `auditor --version` and `auditor check` on a fixture project
  through the installed entry point, as a subprocess.
- `tests/test_published_hooks.py` checks that the hooks are `language: python`
  and that their `entry` starts with `auditor`.
- `tests/test_stop_hook.py` covers `auditor` missing from PATH, the run from
  PATH, and the run of a worktree of this repository.
