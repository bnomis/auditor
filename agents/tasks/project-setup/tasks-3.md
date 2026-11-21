# Tasks: Project setup

**Spec:** `agents/specs/project-setup/spec.md`
**Created:** 2026-11-01
**Version:** 3

Implements amendment 1.4 of the spec only: a project-level `ruff-version-drift`
check, which reports a hit when the ruff on `PATH` is not the version the
project's `ruff-pre-commit` hook pins, plus this repository's own catch-up and
the documentation. `tasks-1.md` (1.1) and `tasks-2.md` (1.2) are complete;
1.3 was done without a task list.

The motivating finding is the top item in `TODO.md`, "The checker runs
whatever `ruff` is on `PATH`, not the version the ruff hook pins". Task 4
moves it to `DONE.md`.

Task 1 lowers this repository's ruff hook before Task 2 adds the check, so no
commit on the branch fails the push gate (`auditme-all` runs on `pre-push`
here). Nothing here changes another repository or the operator's home
directory. Every test builds its projects in temporary directories, with a
stub `ruff` on a temporary `PATH`.

The repository has no affected-tests tool. Each task names its own test files,
and the last task runs every test tree the checker's change can reach.

---

## Task 1: Lower this repository's ruff hook to the locked version

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation - The ruff version check (1.4), "This repository's own hit"

**Technical Goal:** Make the ruff hook and the locked ruff the same version, as
the operator decided on 2026-11-01, so the check added in Task 2 finds nothing
here.

**Subtasks:**

- [x] Confirm the locked version: `grep -n -A1 '^name = "ruff"' uv.lock` shows `version = "0.17.1"`. If it shows another version, stop the task as `blocked` and name it: the operator's decision covers 0.17.1 only
- [x] In `.pre-commit-config.yaml`, change the `astral-sh/ruff-pre-commit` repo's `rev: v0.17.3` to `rev: v0.17.1`. Change nothing else in the file (the decision names this line only)
- [x] Run `pre-commit run ruff-check --all-files` and `pre-commit run ruff-format --all-files`. If either reports a change or a failure, stop the task as `blocked` with the output: the operator decided on the version, not on reformatting

**Acceptance Criteria:**

- [x] `.pre-commit-config.yaml` pins `rev: v0.17.1` for `ruff-pre-commit`
- [x] `.venv/bin/ruff --version` prints `ruff 0.17.1`
- [x] Both ruff hooks pass on every file without changing one

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)

**Notes:**

- `claude/skills/project-setup/templates/pre-commit-config.yaml` keeps `rev: v0.17.3`: the decision is about this repository's own hit, and a new project locks whatever its own cooldown admits
- The coding standards say not to modify `.pre-commit-config.yaml` without explicit instruction; the spec's recorded decision is that instruction, for this one line

---

## Task 2: Add the `ruff-version-drift` check

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** API - The ruff version check (1.4); Error handling (1.4 rows); Implementation - The ruff version check (1.4), steps 1-4 and acceptance; Testing (1.4)

**Technical Goal:** Report a hit when the ruff the checker runs is not the
version the project's `ruff-pre-commit` hook pins, so a lock held back by a
cooldown, or a hook bumped without the lock, fails the push gate and CI rather
than letting the commit hook and the CI audit disagree.

**Subtasks:**

- [x] Tests first, in `claude/skills/auditme/tests/test_project_hygiene.py`, under a `# check_ruff_version` heading beside the existing `# check_ruff` and `# check_lockfile` ones. A fixture writes an executable stub `ruff` into a temporary directory that prints a chosen line for `--version`, and puts that directory first on `PATH` (`monkeypatch.setenv`). Cases, each from the spec's Testing (1.4) list:
  - equal versions give no hit;
  - different versions give one hit at the `rev:` line, with `evidence='ruff on PATH is 0.17.1; the hook pins v0.17.3'`;
  - a `rev` without the `v` compares the same;
  - a SHA `rev` with `# frozen: v0.17.3` uses that version;
  - a SHA `rev` with no comment, and a repo entry with no `rev:`, each give the `the ruff-pre-commit rev names no version` hit (at the `rev:` line, and at the repo line);
  - a stub printing no version gives the `ruff --version printed no version` hit;
  - no `.pre-commit-config.yaml`, a config without `ruff-pre-commit`, and no `ruff` on `PATH` give none;
  - `# auditme: accept[ruff-version-drift] <reason>` on the `rev:` line, and on the line above it, accepts the hit; a marker scoped to another rule does not;
  - a repo URL ending in `.git` or `/` is still found;
  - running the check for two roots of one project prints one hit, not two.
  Run them and see them fail before writing the check
- [x] `claude/skills/auditme/checks/auditme/rules/project_hygiene.py`: add `check_ruff_version(scope, src_root) -> None` with the spec's signature and docstring, following steps 1-4 of the spec's Implementation section exactly: the line regexes, the `frozen:` fallback, `ruff --version` with `cwd=scope`, the three variants and their anchors, and `_accept_reason(lines, rev_line, rule='ruff-version-drift')`
- [x] Return without a hit on `FileNotFoundError` from `ruff --version`; `check_ruff` already reports `ruff not installed`
- [x] `claude/skills/auditme/checks/auditme/registry.py`: import it and append `check_ruff_version` to the end of `CHECKS` (append, never insert)
- [x] `claude/skills/auditme/tests/registry-order.txt`: append `check_ruff_version` as the last line
- [x] Leave `check_ruff` unchanged

**Acceptance Criteria:**

- [x] Every case above passes
- [x] `uv run --no-project python claude/skills/auditme/checks/audit.py .` in this repository gives no `ruff-version-drift` hit (Task 1 matched the versions)
- [x] The same run with `rev:` temporarily set back to `v0.17.3` (not committed) gives exactly one `ruff-version-drift` hit naming both versions
- [x] No other rule's output changes: `test_registry.py` and every existing `test_project_hygiene.py` test pass unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_project_hygiene.py claude/skills/auditme/tests/test_registry.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- Key files: `claude/skills/auditme/checks/auditme/rules/project_hygiene.py` (`check_ruff`, `check_lockfile`), `claude/skills/auditme/checks/auditme/core.py` (`_emit()`, whose de-duplication of identical lines makes a project-level check report once; `_accept_reason()`, which reads the given line and the one above it)
- The checker stays stdlib-only: no YAML parser
- The hit's path is `.pre-commit-config.yaml`. `changed.py` only sweeps when a `.py`, reportable `.md` or `uv.lock` file changed, and reports hits on changed paths, so this hit reaches the commit hook only by chance; the push gate and CI (`changed.py --all`) are where it is caught, as the spec's acceptance criterion says. Do not change `changed.py` in this list: the spec does not ask for it

---

## Task 3: Document `ruff-version-drift`

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Documentation (Amendment 1.4)

**User Story:** As someone setting up or upgrading a project, I want the guide
to say which ruff the checker needs and what to do when the sweep reports
`ruff-version-drift`, so that I can clear it without reading the checker.

**Subtasks:**

- [x] `docs/setup.md`, the "`ruff` on `PATH`" requirement: say the ruff there must be the version the ruff hook's `rev` pins, that the sweep reports `ruff-version-drift` otherwise, and how to make them equal (`uv add --dev ruff==<version>`, or change the hook's `rev`)
- [x] `claude/skills/project-setup/templates/ci.yml`: extend the comment above the `.venv/bin` step to say, in one line, that the locked ruff must equal the ruff hook's `rev`
- [x] `claude/skills/auditme/SKILL.md`: document `ruff-version-drift` beside the existing ruff check under "Mechanical sweep": what it compares, that it is project-level, the two "cannot verify" variants, and how to accept one
- [x] Check the wording against the implemented check in `project_hygiene.py`, variant strings included

**Acceptance Criteria:**

- [x] Each variant string the docs quote matches the code exactly
- [x] `claude/skills/project-setup/tests/test_templates.py` passes with the changed template

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/project-setup/tests/test_templates.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 2
- No file in this repository may name an external project (`claude/rules/rule-scope.md`; the `no-project-names` hook checks it)

---

## Task 4: Close amendment 1.4

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Acceptance criteria (1.4)

**Technical Goal:** Check the whole change before the branch merges, move the
motivating item to `DONE.md`, and mark the spec implemented.

**Subtasks:**

- [x] Move the `TODO.md` item "The checker runs whatever `ruff` is on `PATH`, not the version the ruff hook pins" to the end of `DONE.md`: append its heading and body unchanged, then `Done: <date> - spec amendment 1.4, agents/tasks/project-setup/tasks-3.md: the ruff-version-drift check, and this repository's ruff hook lowered to v0.17.1.`, and remove it from `TODO.md`
- [x] Set the spec's `**Status:**` to `implemented`

**Acceptance Criteria:**

- [x] The spec's 1.4 acceptance criteria hold: a project whose ruff differs from its `ruff-pre-commit` `rev` fails `changed.py --all` with one `ruff-version-drift` hit (shown by Task 2's tests and its temporary-`rev` run); a matching or hook-less project gets no new hit; this repository's whole-tree audit passes with `rev: v0.17.1`

**Definition of Done:**

- [x] `pre-commit run --all-files` exits 0
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests claude/skills/project-setup/tests tests -q -p no:cacheprovider` passes
- [x] `git show $(git log --diff-filter=A --format=%H -- agents/tasks/project-setup/tasks-3.md):TODO.md > <scratch>/todo-before.md`, then `python3 claude/skills/todo-review/verify_bodies.py <scratch>/todo-before.md TODO.md DONE.md` exits 0

**Notes:**

- Depends on Tasks 1-3
- After the merge and push, the operator checks that the CI run on `main` passed; a task in the list cannot see GitHub

---
