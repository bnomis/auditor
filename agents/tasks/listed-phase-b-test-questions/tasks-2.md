# Tasks: Listed Phase B test questions

**Spec:** `agents/specs/listed-phase-b-test-questions/spec.md`
**Created:** 2026-11-22
**Version:** 2

Implements amendment 1.5 of the spec (the test roots become every audit root,
then `src/tests/` and `tests/`), approved by the operator on 2026-11-22 on the
review page named in the spec's header. `tasks-1.md` built version 1.0 to 1.4
and is done. This list closes the `TODO.md` item "The Phase B test index reads
tests only from `src/tests/` and `tests/`" and its entry in
`claude/skills/auditme/requests.md`.

---

## Task 1: Read tests from every audit root

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation, Scope (amendment 1.5); Error handling; Tests

**Technical Goal:** The T1 and T2 listers see the tests under every declared
root, so a project whose tests sit outside `src/tests/` and `tests/` no longer
gets an empty test map.

**Subtasks:**

- [x] Starting-point check: `grep -nw 'TEST_TREES' claude/skills/auditme/checks/auditme/phaseb/testmap.py` prints the line `TEST_TREES = ('src/tests', 'tests')`. If it does not, stop as `blocked`, naming what the line now holds
- [x] Write the failing tests first, in `claude/skills/auditme/tests/phaseb/test_testmap.py`, using the existing `project` fixture:
  - a project declaring `[tool.auditme]` roots `pkg` (package) and `checks/tests` (package), with `checks/tests/test_mod.py` importing and calling `pkg.mod.load`: `load_test_map` gives `pkg/mod.py::load` a `direct` ref from `checks/tests/test_mod.py`, and the ref's file is in that candidate's `test_files`
  - a declared root in `top-level` mode holding `test_x.py`: the parsed test file's module is `test_x`, not `<root name>.test_x`
  - a file reachable under two roots (a declared root `tests` and the default `tests/`) yields one ref, not two
  - a `conftest.py` fixture in a declared test root reaches its test, and the chain stops at that root (a `conftest.py` above the root is not read)
  - a project declaring nothing, with `src/pkg/tests/test_mod.py` and `src/tests/test_other.py`, reads both
  - the existing `test_project_without_test_tree_gives_empty_map` and `test_top_level_tests_directory_is_read` still pass unchanged
- [x] Run the new tests and see them fail
- [x] In `claude/skills/auditme/checks/auditme/phaseb/testmap.py`, make `test_tree_roots(root)` return every root `auditme.core.audit_roots(root)` returns, in its order, then each of `src/tests` and `tests` that exists and is not already in the list; update its docstring
- [x] In `read_test_tree`, keep the first-wins skip of a path already read, and pass each test root as `read_test_file`'s base so `module_dotted` follows that root's `modules` mode
- [x] Add `RootsError` to the `Raises:` sections of `read_test_tree` and `test_tree_roots` if they now call `audit_roots`
- [x] Confirm `conftest_chain` and `TestIndex.mirrored` take their roots from `test_tree_roots` (no second list)

**Acceptance Criteria:**

- [x] Each new test passes, and failed before the change
- [x] `TEST_TREES` remains only as the default trees appended after the audit roots
- [x] On this repository, `python3 claude/skills/auditme/checks/phaseb.py plan . --question T1 --out <scratch dir>` writes batches in which some candidate of `claude/skills/auditme/checks/auditme/core.py` has a non-empty `tests` list (before the change every candidate's `tests` and `test_files` were empty); give the candidate's id in the task's Notes

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/phaseb/test_testmap.py claude/skills/auditme/tests/phaseb/test_t1_candidates.py claude/skills/auditme/tests/phaseb/test_t2_candidates.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/phaseb/testmap.py`, `claude/skills/auditme/tests/phaseb/test_testmap.py`
- `audit_roots` sets `ROOT_MODULES` as a side effect; `module_dotted` reads it, so call `audit_roots` before parsing (as `source_sites` already does)
- The briefs do not change and no brief version is bumped (amendment 1.5)
- Use a scratch directory outside the repository for `--out`
- Acceptance check: `claude/skills/auditme/checks/auditme/core.py::accept_reason` has a non-empty `tests` list (every `core.py` candidate has one)

---

## Task 2: Close the request and the TODO item, then run the whole-tree checks

**Status:** todo
**Priority:** high
**Complexity:** small
**Spec Reference:** Amendment 1.5; Skill changes

**Technical Goal:** Record that the request shipped, so the next audit's
precondition sees one entry fewer, and check the whole tree before the merge.

**Subtasks:**

- [ ] Delete the entry "The Phase B test index reads tests only from `src/tests/` and `tests/`" from the `## Open` section of `claude/skills/auditme/requests.md`
- [ ] In `agents/audit-reviews/summary.md`, under "Checker changes since the last review", add a dated line: the T1 and T2 test index now reads tests from every audit root (amendment 1.5 of `agents/specs/listed-phase-b-test-questions/spec.md`), so review-2's T1 and T2 verdicts are re-judged where `test_files` grew; and remove that request from the Convergence note's precondition bullet
- [ ] Move the `TODO.md` item "The Phase B test index reads tests only from `src/tests/` and `tests/`" to the end of `DONE.md`: append its heading and body unchanged, then `Done: <date> - amendment 1.5 of agents/specs/listed-phase-b-test-questions/spec.md and agents/tasks/listed-phase-b-test-questions/tasks-2.md; <the Task 1 commit hash>.`, and remove it from `TODO.md`
- [ ] Set the spec's `**Status:**` to `implemented` in `agents/specs/listed-phase-b-test-questions/spec.md`

**Acceptance Criteria:**

- [ ] `requests.md`'s `## Open` section no longer holds the test-index entry, and the other two entries are unchanged
- [ ] The spec's `**Status:**` is `implemented`

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `pre-commit run --all-files` passes
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` passes (the pre-push whole-tree audit)
- [ ] `uv run pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes (`candidates.py` imports `testmap.py`, and every test file under `phaseb/` reaches `candidates.py`)
- [ ] `python3 ~/.claude/skills/todo-review/verify_bodies.py <baseline> TODO.md DONE.md` exits 0, where `<baseline>` is `TODO.md` at the commit that added this list: `git show $(git log --diff-filter=A --format=%H -- agents/tasks/listed-phase-b-test-questions/tasks-2.md):TODO.md > <scratch file>`

**Notes:**

- Depends on Task 1
- Key files: `claude/skills/auditme/requests.md`, `agents/audit-reviews/summary.md`, `TODO.md`, `DONE.md`

---
