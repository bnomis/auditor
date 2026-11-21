# Tasks: Project setup

**Spec:** `agents/specs/project-setup/spec.md`
**Created:** 2026-11-21
**Version:** 5

Completes amendment 1.11 of the spec ("Declared audit roots"): this
repository declares its own roots, which exposes the backlog the motivation
measured, so the same change takes `pre-push` off `auditme-all` and files the
backlog in `TODO.md`, as `adopt` does for a project with a backlog.

Run this list only after `tasks-4.md` is merged to `main`. On a branch the
commit hook's diff base is `origin/main`; with `tasks-4.md` merged, this
list's changes are `pyproject.toml`, `.pre-commit-config.yaml`, `TODO.md` and
`DONE.md`, none of which carries the backlog, so the hook has nothing to
block.

The motivating finding is the top item in `TODO.md`, "The audit reads none of
this repository's own Python". Task 1 moves it to `DONE.md`. Nothing here
changes another repository or the operator's home directory.

---

## Task 1: Declare this repository's roots and file the backlog

**Status:** todo
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation - Declared audit roots (1.11), "This repository's roots"

**Technical Goal:** The audit, the hooks and Phase B cover this repository's
own Python, with the whole-tree push gate deferred until the backlog is
cleared.

**Subtasks:**

- [ ] Check the starting point: after `git fetch origin`, `git show origin/main:claude/skills/auditme/checks/auditme/core.py | grep -cw ROOT_MODULES` is non-zero, so `tasks-4.md` is merged; if it is zero, stop the list as `blocked`, saying `tasks-4.md` must be merged first
- [ ] `pyproject.toml`: add `[tool.auditme]` with `roots` = `claude/skills/auditme/checks/auditme` (package), `claude/skills/auditme/checks` (`modules = "top-level"`), `claude/skills/auditme/tests`, `claude/skills/auditme-project-setup/tests` and `tests` (each package), in that order
- [ ] `.pre-commit-config.yaml`: change the local `auditme-all` hook's `stages` from `[manual, pre-push]` to `[manual]`, with a comment saying the push gate returns when the backlog item in `TODO.md` is done; leave `auditme-changed` on `pre-commit`
- [ ] Run `python3 claude/skills/auditme/checks/audit.py .`, save the output to the scratch directory, and count the unaccepted hits by rule
- [ ] File a `TODO.md` item, "Fix or accept this repository's audit backlog", in the shape `TODO.md`'s conventions give: the date, the total and the count by rule as measured, the cause (the checker's own code was never swept), and the Fix direction: fix or accept every hit, then put `pre-push` back on `auditme-all` and run the first audit of this repository
- [ ] Move "The audit reads none of this repository's own Python" to the end of `DONE.md`: its heading and body unchanged, then `Done: <date> - amendment 1.11 of agents/specs/project-setup/spec.md, agents/tasks/project-setup/tasks-4.md and tasks-5.md; the backlog is filed as "Fix or accept this repository's audit backlog".`
- [ ] Leave the spec's `**Status:**` at `implemented`

**Acceptance Criteria:**

- [ ] `python3 claude/skills/auditme/checks/audit.py .` prints no `no package under src/` notice and emits hits whose paths are under `claude/skills/`
- [ ] `python3 claude/skills/auditme/checks/phaseb.py plan . --question A4 --out <scratch>` writes at least one batch
- [ ] `TODO.md` holds the backlog item with dated counts, and `DONE.md` ends with the moved item and its `Done:` line

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `pre-commit run --all-files` exits 0
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes
- [ ] `python3 ~/.claude/skills/todo-review/verify_bodies.py <baseline> TODO.md DONE.md` exits 0, with `<baseline>` the `TODO.md` of the commit that added this task list (`git show $(git log --diff-filter=A --format=%H -- agents/tasks/project-setup/tasks-5.md):TODO.md`)

**Notes:**

- Depends on `tasks-4.md` (merged to `main`)
- `pre-commit run auditme-all --hook-stage manual --all-files` is expected to fail here: that failure is the backlog this task files. It is not a done-check until the backlog item is done
