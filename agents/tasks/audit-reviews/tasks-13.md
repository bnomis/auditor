# Tasks: Audit review 14

**Source:** `agents/audit-reviews/review-14.md`
**Created:** 2026-11-22
**Version:** 13

Fixes the findings of review-14 (F1, F2), answered by Claude on 2026-11-22
under the loop the operator delegated that day; the answers are in
review-14's Answers section. No task changes a brief in
`claude/skills/auditme/phaseb/briefs/`.

---

## Task 1: Correct the exit-2 examples and refuse a file as `--package`

**Status:** done
**Priority:** medium
**Complexity:** small
**Source Reference:** F1, F2

**Technical Goal:** the CLI reference's exit-2 examples print what it says,
and `audit.py` refuses a package root that is not a directory.

**Subtasks:**

- [x] F1: in `docs/reference/cli.md` (the paragraph at line 176 on 2026-11-22), drop the unregistered `--question` and the missing root from the examples of a failing Phase B step; line 174 already states those two argparse cases. Run each remaining example by hand and confirm it prints `phaseb.py: ` and its message and exits 2
- [x] F2: write the failing test first, in `claude/skills/auditme/tests/test_audit_cli.py` (or the test file that already tests `audit.py`'s `--package`, found with `grep -rln -- '--package' claude/skills/auditme/tests`): with `src/pkg` a plain file, `audit.py <root> --package pkg` exits 2 and says the path is not a directory
- [x] F2: in `claude/skills/auditme/checks/audit.py` (line 224), test `root.is_dir()` and print "not a directory" when the path exists but is not one, keeping "not found" for a missing path; add the case to `docs/reference/cli.md`'s `audit.py` exit table
- [x] `grep -rn '\.exists()' claude/skills/auditme/checks bin claude/hooks` and confirm no other check on a path that must be a directory or a file uses `exists()` alone

**Acceptance Criteria:**

- [x] The new test fails before the change and passes after it
- [x] Each example in the exit-2 paragraph is run and prints as stated

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] The test file the F2 subtask names passes under `uv run pytest <file> -q -p no:cacheprovider`
- [x] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Key files: `docs/reference/cli.md`, `claude/skills/auditme/checks/audit.py`

---

## Task 2: Run the whole-tree checks, the doc listers, and update the summary

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** all

**Technical Goal:** the branch passes every whole-tree check before it
merges, its docs still match the code it changed, and the audit summary
records what this list resolved.

**Subtasks:**

- [ ] Run `python3 claude/skills/auditme/checks/phaseb.py candidates . --question Doc4` and `--question Doc5`, take the candidates whose `path` is a doc or spec this list changed, or that names a code file it changed (`git diff --name-only <base>...HEAD`), and check every statement in their sections against the code by hand, running any command a statement describes; fix any that no longer matches. Record what was checked in the task's Notes
- [ ] In `agents/audit-reviews/summary.md`, move each finding Task 1 fixed to Recently resolved, naming the task; when none is left, replace the Unresolved table and the line above it with the sentence "No finding is unresolved: every finding review-14 raised shipped (below)." rather than an empty row

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
