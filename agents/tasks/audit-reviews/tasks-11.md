# Tasks: Audit review 12

**Source:** `agents/audit-reviews/review-12.md`
**Created:** 2026-11-22
**Version:** 11

Fixes the findings of review-12 (F1-F4), answered by Claude on 2026-11-22
under the loop the operator delegated that day; the answers are in
review-12's Answers section. No task changes a brief in
`claude/skills/auditme/phaseb/briefs/`.

Two findings (F3, F4) are sites a review-11 fix did not reach. Each task
here greps the whole tree for its pattern and fixes every site it finds, not
only the one reported.

---

## Task 1: Name every `phaseb.py` exit-2 cause, and the hook's directory case

**Status:** done
**Priority:** medium
**Complexity:** small
**Source Reference:** F1, F2

**Technical Goal:** the CLI reference states every way `phaseb.py` exits 2,
and the names hook names a path it cannot read as a file.

**Subtasks:**

- [x] F1: in `docs/reference/cli.md` (line 174 on 2026-11-22), add that `phaseb.py` exits 2 with the error's message whenever a Phase B step fails, naming the cases `claude/skills/auditme/checks/phaseb.py`'s `main` handles (a merge for another question, a plan or ledger that cannot be read, a failed write); read them from the code. Grep `docs agents/specs` for any other list of `phaseb.py`'s exit codes and make it agree
- [x] F2: write the failing test first, in `tests/test_check_foreign_names.py`: a directory argument exits 2 and is named in the "cannot read" message. Then in `bin/check-foreign-names.sh` (lines 51-55), treat a path that is not a regular readable file (`[ -f "$file" ] && [ -r "$file" ]`) as unreadable
- [x] F2: `grep -n '\[ -r ' bin/*.sh claude/hooks/*.sh` and apply the same rule to any other script that checks only readability before reading a file

**Acceptance Criteria:**

- [x] Each doc statement matches the code
- [x] The new test fails before the change and passes after it

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests/test_check_foreign_names.py -q -p no:cacheprovider` passes
- [x] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Key files: `docs/reference/cli.md`, `bin/check-foreign-names.sh`

---

## Task 2: Work out each project-level answer once per sweep

**Status:** done
**Priority:** low
**Complexity:** small
**Source Reference:** F3

**Technical Goal:** a helper whose answer depends only on the project runs
once per sweep, however many roots there are.

**Subtasks:**

- [x] Record `python3 claude/skills/auditme/checks/audit.py .` outside the repository
- [x] List every helper under `claude/skills/auditme/checks/auditme/` that takes only `scope` and is called from a per-root `check_*` (`grep -n 'def [a-z_]*(scope: pathlib.Path)' -r claude/skills/auditme/checks/auditme`); on 2026-11-22 these include `project_has_all_guard` and `project_bans_as_imports` in `rules/imports_and_surfaces.py`
- [x] Cache each through the per-run cache the driver clears, so it is computed once per sweep; add a test in `claude/skills/auditme/tests/test_imports_and_surfaces.py` that one sweep over a project with two roots calls `project_has_all_guard`'s scan once
- [x] Run the audit again and diff it against the record

**Acceptance Criteria:**

- [x] The audit output is identical before and after
- [x] The new test fails before the change and passes after it

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_imports_and_surfaces.py claude/skills/auditme/tests/test_core.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py`, `claude/skills/auditme/checks/auditme/core.py`

---

## Task 3: One builder per shared test object

**Status:** done
**Priority:** low
**Complexity:** small
**Source Reference:** F4

**Technical Goal:** no test file builds an object that `conftest.py`
already has a builder for.

**Subtasks:**

- [x] Give `make_candidate` in `claude/skills/auditme/tests/conftest.py` keyword overrides for every `Candidate` field, then replace `make_batch_candidate` in `claude/skills/auditme/tests/phaseb/test_batches.py` with it, keeping each test's meaning
- [x] `grep -rn 'Candidate(\|Verdict(' claude/skills/auditme/tests tests` and replace any other test-local construction of those classes in a helper with the shared builders

**Acceptance Criteria:**

- [x] No test file defines its own builder for `Candidate` or `Verdict`

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/tests/conftest.py`, `claude/skills/auditme/tests/phaseb/test_batches.py`

---

## Task 4: Run the whole-tree checks, the doc listers, and update the summary

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** all

**Technical Goal:** the branch passes every whole-tree check before it
merges, its docs still match the code it changed, and the audit summary
records what this list resolved.

**Subtasks:**

- [ ] Run `python3 claude/skills/auditme/checks/phaseb.py candidates . --question Doc4` and `--question Doc5`, take the candidates whose `path` is a doc or spec this list changed, or that names a code file it changed (`git diff --name-only <base>...HEAD`), and check every statement in their sections against the code by hand; fix any that no longer matches. Record what was checked in the task's Notes
- [ ] In `agents/audit-reviews/summary.md`, move each finding Tasks 1 to 3 fixed to Recently resolved, naming its task; when none is left, replace the Unresolved table and the line above it with the sentence "No finding is unresolved: every finding review-12 raised shipped (below)." rather than an empty row

**Acceptance Criteria:**

- [ ] The Unresolved section holds only findings that did not ship, each with its reason

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `pre-commit run --all-files` passes
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` passes (the pre-push whole-tree audit)
- [ ] `uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes
- [ ] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Depends on Tasks 1 to 3

---
