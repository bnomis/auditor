# Tasks: Audit review 9

**Source:** `agents/audit-reviews/review-9.md`
**Created:** 2026-11-22
**Version:** 9

Fixes the one finding the operator approved on review-9's page on
2026-11-22 (F1). The answer is in review-9's Answers section. No task
changes a brief in `claude/skills/auditme/phaseb/briefs/`.

---

## Task 1: Index test files by the modules they import

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** F1

**Technical Goal:** listing T1 does work proportional to the functions and
the test files, not to their product with the caller modules.

**Subtasks:**

- [ ] Record `python3 claude/skills/auditme/checks/phaseb.py candidates . --question T1` and `--question T2` outside the repository
- [ ] Write a test first, in `claude/skills/auditme/tests/phaseb/test_testmap.py`, that building a `TestIndex` and calling `test_files` for every function computes each test file's imported names once (count calls to `imported_names` with a monkeypatch)
- [ ] In `claude/skills/auditme/checks/auditme/phaseb/testmap.py`, compute each test file's imported names once when the index is built, and keep a map from each imported dotted name and each of its parent modules to the test files that import it; make `test_files` (line 272 on 2026-11-22) look up its modules and re-export names in that map instead of scanning every test file, and make `imports_module` (line 183) use the stored names
- [ ] Keep `imports_module` and `imported_names` public behaviour as their docstrings state, and update any spec that describes how `test_files` finds its files (`agents/specs/listed-phase-b-test-questions/spec.md`, "Finding the tests") only if its statements stop being true
- [ ] Run the listings again and diff them against the record; time the T1 listing before and after

**Acceptance Criteria:**

- [ ] The T1 and T2 listings are identical before and after
- [ ] The new test fails before the change and passes after it

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/phaseb/test_testmap.py claude/skills/auditme/tests/phaseb/test_t1_candidates.py claude/skills/auditme/tests/phaseb/test_t2_candidates.py -q -p no:cacheprovider` passes

**Notes:**

- Measured on 2026-11-22: 0.36 s of a 2.2 s T1 listing here; 20.5 s of 35.8 s on one project with 743 source files

---

## Task 2: Run the whole-tree checks and update the summary

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** all

**Technical Goal:** the branch passes every whole-tree check before it
merges, and the audit summary records what this list resolved.

**Subtasks:**

- [ ] Run `python3 claude/skills/auditme/checks/phaseb.py candidates . --question Doc4` and `--question Doc5`, take the candidates that name a file this list changed (`git diff --name-only <base>...HEAD`), and check their statements against the code by hand; fix any that no longer matches. Record what was checked in the task's Notes
- [ ] In `agents/audit-reviews/summary.md`, move F1 to Recently resolved, naming Task 1; replace the Unresolved table with the sentence "No finding is unresolved: every finding review-9 raised shipped (below)." rather than an empty row

**Acceptance Criteria:**

- [ ] The Unresolved section holds only findings that did not ship, each with its reason

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `pre-commit run --all-files` passes
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` passes (the pre-push whole-tree audit)
- [ ] `uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes
- [ ] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Depends on Task 1

---
