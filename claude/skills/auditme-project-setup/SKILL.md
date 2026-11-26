---
name: auditme-project-setup
description: Set up a new project with the shared audit guards, or adopt them into an existing project - pre-commit hooks, CI gate and project files
when_to_use: |
    Use this skill whenever the user mentions:
        - set up a new project
        - project setup
        - adopt the audit hooks
        - add auditme to a project
        - add the shared guards to this repository

allowed_tools: [Read, Write, Edit, Bash, AskUserQuestion]
---

# Project setup

Invoke as:
    /auditme-project-setup new [<path>]
    /auditme-project-setup adopt [<path>]

`<path>` defaults to the working directory's repository root
(`git rev-parse --show-toplevel`). All work happens in that repository.

The guards are the `auditme-changed` hook (commit stage, changed files), the
`auditme-all` hook (manual stage, whole tree, run in CI, and on push once a
project has no unaccepted hits) and the project files
that the shared rules and skills expect. The templates are in
[templates/](templates/); the design is in
`agents/specs/project-setup/spec.md`.

Follow [asking-questions.md](../../rules/asking-questions.md): every question
goes through `AskUserQuestion`, one decision per question, recommended option
first.

## Confirm before committing

Ask with `AskUserQuestion`, and wait for the answer, before committing.
Writing files in the working tree and running `pre-commit install` need no
confirmation. Never push.

## Filling the templates

| Placeholder | Source |
|---|---|
| `{{AUDITOR_REV}}` | the commit on `main` of the auditor repository: `git ls-remote https://github.com/bnomis/auditor refs/heads/main`, first field |
| `{{PROJECT_NAME}}` | the repository directory's name; confirm it |
| `{{TEST_COMMAND}}` | ask the operator for the project's test command |

If `git ls-remote` fails (no network access to GitHub), stop and say so: the
hooks cannot be pinned without a revision.

The auditor repository is public and the hooks clone it over HTTPS, so
neither a developer machine nor CI needs a key or secret to run them.

## No rules repository yet

The checker loads its rules from the repository `AUDITOR_RULES_PATH` names. When
`[ -n "${AUDITOR_RULES_PATH:-}" ]` is false, tell the user, before `new` or
`adopt`, the steps to create one (never edit `.envrc` yourself; the user does):

1. In a terminal, run `auditor rules packs` and choose the packs.
2. Run `auditor rules init <dir> --pack <pack>` (repeat `--pack`; none selects
   every pack). It writes `<dir>/selection.txt`.
3. Edit `<dir>/selection.txt`: comment out each rule you do not want.
4. Run `auditor rules apply <dir>`. It copies the rules and checks them.
5. Add `export AUDITOR_RULES_PATH=<dir>` to the project's `.envrc`, then run
   `direnv allow`.

## `new`

For an empty or freshly initialised repository. If the target already holds
`.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `AGENTS.md`, `TODO.md`
or `DONE.md`, ask whether to overwrite each one, or stop and suggest `adopt`.

1. Write `.pre-commit-config.yaml` from `templates/pre-commit-config.yaml`
   (ruff check and format, shellcheck, and both auditme hooks pinned at
   `{{AUDITOR_REV}}`, with `auditme-all` also at the `pre-push` stage).
2. Write `.github/workflows/ci.yml` from `templates/ci.yml`: checkout, Python
   and uv, `uv sync`, `pre-commit run --all-files`, the
   `auditme-all` step and `{{TEST_COMMAND}}`.
3. Write `AGENTS.md`, `CLAUDE.md` (`@AGENTS.md`), `TODO.md`, `DONE.md` and
   `claude/rules/README.md` from the templates, with `{{PROJECT_NAME}}`.
4. Run `pre-commit install --hook-type pre-commit --hook-type pre-push`.
5. Ask whether to commit the new files. If yes, commit as
   `build: set up the project guards`.

Check that no placeholder remains in any written file
(`grep -rnE '\{\{[A-Z_]+\}\}' <files>` prints nothing). A bare `{{` search is
not enough: a workflow can hold GitHub's own `${{ ... }}` expressions.

## `adopt`

For an existing project.

1. **Hooks.** Add the `https://github.com/bnomis/auditor` repo block with
   `auditme-changed` and `auditme-all`, at `{{AUDITOR_REV}}`, to
   `.pre-commit-config.yaml` (create it from the template's hook block if it is
   absent). An existing auditor entry that clones over SSH
   (`git@github.com:bnomis/auditor.git`) moves to the HTTPS URL. Look for a project-local hook, script or `.claude/settings.json`
   Stop hook that does the same job (an audit runner scoped to changed files).
   Show it to the operator, then ask before removing it: left in place, every
   commit or turn runs the sweep twice.
2. **Count.** Run
   `pre-commit run auditme-all --hook-stage manual --all-files` and count the
   unaccepted hits by rule from its output. Record the date of the run.
3. **Zero hits:** add `stages: [manual, pre-push]` under `- id: auditme-all`
   in `.pre-commit-config.yaml`, so every push sweeps the whole tree. Add the
   CI step from `templates/ci-audit-step.yml` (the `auditme-all` step) to the
   project's existing workflow after its own setup. **More than zero:** do
   not add the push stage and do not touch the workflow. File one `TODO.md` item with the
   [todo-add](../todo-add/SKILL.md) conventions: the dated count by rule, and a
   Fix direction of "fix or accept every hit, then add the push stage and the
   CI step". Neither gate is ever enabled over a backlog: a gate that fails
   every push gets switched off.
4. **Commit.** Ask whether to commit the hook and `TODO.md` changes as
   `build(audit): adopt the shared audit hooks`.

## Do not

- Push.
- Enable the CI gate (add the CI step) while the unaccepted-hit count is above
  zero.
- Write a project's name, path or date into a template; fill placeholders in
  the target's copy only.
