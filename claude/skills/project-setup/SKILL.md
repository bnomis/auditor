---
name: project-setup
description: Set up a new project with the shared audit guards, or adopt them into an existing project - pre-commit hooks, CI gate, deploy key and project files
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
    /project-setup new [<path>]
    /project-setup adopt [<path>]

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
first. Follow [security.md](../../rules/security.md): a private key is never
printed, logged or quoted.

## Confirm before anything outward-facing

Ask with `AskUserQuestion`, and wait for the answer, before each of:

- creating a deploy key (`ssh-keygen`, `gh repo deploy-key add`);
- setting a secret (`gh secret set`);
- committing.

Writing files in the working tree and running `pre-commit install` need no
confirmation. Never push.

## Filling the templates

| Placeholder | Source |
|---|---|
| `{{AUDITOR_REV}}` | the commit on `main` of the auditor repository: `git ls-remote git@github.com:bnomis/auditor.git refs/heads/main`, first field |
| `{{PROJECT_NAME}}` | the repository directory's name; confirm it |
| `{{TEST_COMMAND}}` | ask the operator for the project's test command |

If `git ls-remote` fails (no SSH access to the auditor repository), stop and
say so: the hooks cannot be pinned without a revision.

## `new`

For an empty or freshly initialised repository. If the target already holds
`.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `AGENTS.md`, `TODO.md`
or `DONE.md`, ask whether to overwrite each one, or stop and suggest `adopt`.

1. Write `.pre-commit-config.yaml` from `templates/pre-commit-config.yaml`
   (ruff check and format, shellcheck, and both auditme hooks pinned at
   `{{AUDITOR_REV}}`, with `auditme-all` also at the `pre-push` stage).
2. Write `.github/workflows/ci.yml` from `templates/ci.yml`: checkout, the
   deploy-key step, Python and uv, `uv sync`, `pre-commit run --all-files`, the
   `auditme-all` step and `{{TEST_COMMAND}}`.
3. Write `AGENTS.md`, `CLAUDE.md` (`@AGENTS.md`), `TODO.md`, `DONE.md` and
   `claude/rules/README.md` from the templates, with `{{PROJECT_NAME}}`.
4. Run `pre-commit install --hook-type pre-commit --hook-type pre-push`, then
   the [deploy-key steps](#deploy-key-steps).
5. Ask whether to commit the new files. If yes, commit as
   `build: set up the project guards`.

Check that no placeholder remains in any written file
(`grep -rnE '\{\{[A-Z_]+\}\}' <files>` prints nothing). A bare `{{` search is
not enough: `ci.yml` holds GitHub's own `${{ secrets.AUDITOR_DEPLOY_KEY }}`.

## `adopt`

For an existing project.

1. **Hooks.** Add the `git@github.com:bnomis/auditor.git` repo block with
   `auditme-changed` and `auditme-all`, at `{{AUDITOR_REV}}`, to
   `.pre-commit-config.yaml` (create it from the template's hook block if it is
   absent). Look for a project-local hook, script or `.claude/settings.json`
   Stop hook that does the same job (an audit runner scoped to changed files).
   Show it to the operator, then ask before removing it: left in place, every
   commit or turn runs the sweep twice.
2. **Count.** Run
   `pre-commit run auditme-all --hook-stage manual --all-files` and count the
   unaccepted hits by rule from its output. Record the date of the run.
3. **Zero hits:** add `stages: [manual, pre-push]` under `- id: auditme-all`
   in `.pre-commit-config.yaml`, so every push sweeps the whole tree. Add the
   CI step from `templates/ci-audit-step.yml` (the deploy-key step and the
   `auditme-all` step) to the project's existing workflow after its own setup,
   then run the [deploy-key steps](#deploy-key-steps). **More than zero:** do
   not add the push stage, do not touch the workflow and do not run the
   deploy-key steps. File one `TODO.md` item with the
   [todo-add](../todo-add/SKILL.md) conventions: the dated count by rule, and a
   Fix direction of "fix or accept every hit, then add the push stage and the
   CI step". Neither gate is ever enabled over a backlog: a gate that fails
   every push gets switched off.
4. **Commit.** Ask whether to commit the hook and `TODO.md` changes as
   `build(audit): adopt the shared audit hooks`.

## Deploy-key steps

Each step is asked before it runs, and shows the exact command first. Use a
scratch directory made for this run (`mktemp -d`), never the repository.

1. `ssh-keygen -t ed25519 -N '' -f <scratch>/auditor_deploy_key`
2. `gh repo deploy-key add <scratch>/auditor_deploy_key.pub --repo bnomis/auditor --title <project>`
3. `gh secret set AUDITOR_DEPLOY_KEY --repo <owner>/<project> < <scratch>/auditor_deploy_key`
4. Delete both files, and the scratch directory, whatever happened above.

`<project>` is the confirmed project name; `<owner>/<project>` comes from
`gh repo view --json nameWithOwner`. The key is read-only on the shared
repository and read only by `gh`; never `cat` it, echo it or pass it on a
command line.

## Do not

- Push.
- Enable the CI gate (add the CI step) while the unaccepted-hit count is above
  zero.
- Run a step that changes GitHub (deploy key, secret) without the operator's
  confirmation in this session.
- Print, log or quote a private key.
- Write a project's name, path or date into a template; fill placeholders in
  the target's copy only.
