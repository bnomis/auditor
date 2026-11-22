# Tasks: Audit review 6

**Source:** `agents/audit-reviews/review-6.md`
**Created:** 2026-11-22
**Version:** 6

Fixes the findings the operator approved on review-6's page on 2026-11-22
(F1-F9; F10 was dismissed, U1-U5 kept as not findings, and D1 leaves the
briefs unchanged). The answers are in review-6's Answers section.

No task changes a brief in `claude/skills/auditme/phaseb/briefs/`: the
operator chose to leave them (D1), and a brief change would re-judge every
candidate of its question in review-7.

---

## Task 1: Correct the doc and spec statements

**Status:** done
**Priority:** medium
**Complexity:** small
**Source Reference:** F3, F4, F5, F6, F7

**Technical Goal:** the specs, user docs and `AGENTS.md` match the code, and
no spec states a brief's version.

**Subtasks:**

- [x] F3: in `agents/specs/listed-phase-b-architecture-questions/spec.md` (line 59 on 2026-11-22), `agents/specs/listed-phase-b-test-questions/spec.md` (line 259) and `agents/specs/repeatable-phase-b/spec.md` (line 303), remove each figure that gives a brief's current version, and say instead that each brief's `**Brief version:**` line holds it. A dated amendment that records the version a brief had on its date may keep the figure, worded as a record of that date
- [x] F3: `grep -rnE 'brief (is )?at version|at brief version|version [0-9]+ \(' agents/specs docs README.md AGENTS.md` and treat any other current-state version figure the same way
- [x] F4: in `agents/specs/listed-phase-b-documentation-questions/spec.md`'s API block (line 79), give `read_name_targets` the `Raises:` its docstring in `claude/skills/auditme/checks/auditme/phaseb/docrefs.py` declares
- [x] F5: in `docs/reference/cli.md`, say that `changed.py --scope` prints its no-diff-base message to stderr (line 226), and add `--scope` failing to read a changed Python file to the exit-1 list (line 231); read both from `claude/skills/auditme/checks/changed.py`
- [x] F6: in `docs/guide/checker.md`'s `silent-self-mutation` row (line 294), add `__post_init__` and `__setattr__`, read from `check_silent_self_mutation`
- [x] F7: in `AGENTS.md` (line 31), replace "both hook types" with wording that matches the command on line 33, without a count
- [x] Find each statement by its text; the line numbers are from 2026-11-22

**Acceptance Criteria:**

- [x] Each statement matches the code it describes
- [x] No spec, doc or `AGENTS.md` line states a brief's current version
- [x] `uv run --group docs mkdocs build --strict` exits 0

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)

**Notes:**

- Key files: the three specs above, `agents/specs/listed-phase-b-documentation-questions/spec.md`, `docs/reference/cli.md`, `docs/guide/checker.md`, `AGENTS.md`

---

## Task 2: Translate `cached_bytes`'s read failure and test it directly

**Status:** done
**Priority:** medium
**Complexity:** small
**Source Reference:** F1

**Technical Goal:** a public core function does not let `OSError` escape,
and its caching is tested where it is defined.

**Subtasks:**

- [x] Read every caller of `cached_bytes` (`grep -rnw cached_bytes claude/skills/auditme/checks`). If only package modules call it and nothing outside `auditme` should, drop it from `auditme.core.__all__`; otherwise catch `OSError` in it and raise the error its callers already raise for an unreadable file, keeping the `Raises:` section and the callers' handling in step
- [x] Write the tests first, in `claude/skills/auditme/tests/test_core.py`: a file is read once per run however often `cached_bytes` is called; it is read again after it is rewritten with a different size or mtime; an unreadable path gives the documented error
- [x] Update `docs/guide/checker.md` or the spec that names `cached_bytes`, if either states its contract

**Acceptance Criteria:**

- [x] The new tests fail before the change and pass after it
- [x] `python3 claude/skills/auditme/checks/phaseb.py candidates . --question A1` either lists no `cached_bytes` call or lists it inside a wrap

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/phaseb/test_docrefs.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/core.py`, `claude/skills/auditme/checks/auditme/phaseb/docrefs.py`

---

## Task 3: Property tests for the `--scope` helpers

**Status:** done
**Priority:** medium
**Complexity:** small
**Source Reference:** F2

**Technical Goal:** each `--scope` helper's invariant is checked over
generated inputs.

**Subtasks:**

- [x] In `claude/skills/auditme/tests/test_changed.py`, add a hypothesis test for each, following the file's existing hypothesis style:
  - `merge_ranges`: the result is sorted, no two ranges overlap or touch, it covers exactly the union of the input lines, and merging it again changes nothing;
  - `widen`: one range per hunk line, each holding its line; the line itself when no scope holds it, else the shortest enclosing function, or class when no function does, checked against a brute-force search;
  - `enclosing_ranges`: for generated nested functions and classes, each range lies within the source, starts at its decorator line, and is marked a function exactly for functions; source that does not parse gives no ranges
- [x] If a property fails, fix the helper and keep the failing example as a plain test

**Acceptance Criteria:**

- [x] Each helper is called directly by a `@given` test

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_changed.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/changed.py`, `claude/skills/auditme/tests/test_changed.py`

---

## Task 4: Rename the test helper and compute run-fixed values once

**Status:** done
**Priority:** low
**Complexity:** medium
**Source Reference:** F8, F9

**Technical Goal:** no name hides a read, and a value fixed for the run is
worked out once.

**Subtasks:**

- [x] F8: rename `resolve_token` in `claude/skills/auditme/tests/phaseb/test_docrefs.py` (line 206 on 2026-11-22) to `read_token`, with every use
- [x] Record the outputs first, outside the repository: `python3 claude/skills/auditme/checks/audit.py .` and `python3 claude/skills/auditme/checks/phaseb.py candidates . --question <Q>` for A1, A17 and T1
- [x] F9, each through the per-run cache the driver already clears:
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py:50`: resolve `audit_roots(scope)` once per listing, not once per check;
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py:37` and `:217`: resolve `ruff_executable(scope)` once per run;
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py:446`: build `caught_elsewhere` once per root, not once per `errors.py`;
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:173`: call `declared_root_modules()` once per run;
  - `claude/skills/auditme/checks/auditme/phaseb/testmap.py:231`: run `reach` once per function in `TestIndex.refs`, not once per calling test
- [x] Add a test per cache that the value is computed once in a run, in the module's own test file
- [x] Run the commands again and diff the outputs against the record

**Acceptance Criteria:**

- [x] Every output is identical before and after
- [x] Each new test fails before its change and passes after it

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/phaseb claude/skills/auditme/tests/test_project_hygiene.py claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/test_imports_and_surfaces.py -q -p no:cacheprovider` passes

**Notes:**

- `caught_elsewhere` in `check_sibling_error_no_common_base` was built and never read, so it was removed rather than cached; its test asserts the root is walked once.
- Before/after outputs were compared with the HEAD checker and the new checker over the same fixed copy of HEAD, because auditing this repository itself shifts with the edits.

- Check each test file name exists before running (`ls claude/skills/auditme/tests`), and name the module's own test file if it differs

---

## Task 5: Run the whole-tree checks, the doc listers, and update the summary

**Status:** in-progress
**Priority:** medium
**Complexity:** small
**Source Reference:** all

**Technical Goal:** the branch passes every whole-tree check before it
merges, its docs and specs still match the code it changed, and the audit
summary records what this list resolved.

**Subtasks:**

- [ ] Run `python3 claude/skills/auditme/checks/phaseb.py candidates . --question Doc4` and `--question Doc5`, take the candidates whose `path` is a doc or spec this list changed, or that names a code file it changed (`git diff --name-only <base>...HEAD`), and check every statement in their sections against the code by hand, not only the lines this list edited; fix any that no longer matches. Record what was checked in the task's Notes
- [ ] For each identifier, option or version this list renamed, removed or changed, grep `docs agents/specs README.md AGENTS.md` for its old form and fix each hit
- [ ] In `agents/audit-reviews/summary.md`, move each finding Tasks 1 to 4 fixed to Recently resolved, naming its task

**Acceptance Criteria:**

- [ ] The Unresolved table holds only findings that did not ship, each with its reason

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `pre-commit run --all-files` passes
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` passes (the pre-push whole-tree audit)
- [ ] `uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes (`core.py` and the rule modules changed, and every checker test reaches them)
- [ ] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Depends on Tasks 1 to 4
- Doc4 and Doc5 listers run on 2026-11-22; candidates whose path or target is a file this list changed were checked against the code changes (`CachedReadError` in `core.py`, the per-run caches in `project_hygiene.py`, `imports_and_surfaces.py`, `architecture.py` and `testmap.py`, the removed `caught_elsewhere`). No spec or doc states the `cached_bytes` exception type, the cached helpers' internals or a changed signature (`ruff_executable` keeps its signature); `declared_root_modules` now returns a `frozenset` and no doc names its type. The one remaining version figure, "T1 brief (version 3)" in the test-questions spec's dated amendment, is a record of that date
- Old forms grepped over `docs agents/specs README.md AGENTS.md`: `resolve_token`, `caught_elsewhere`, `cached_bytes`, "both hook types" - no stale hit

---
