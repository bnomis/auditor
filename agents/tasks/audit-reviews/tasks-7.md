# Tasks: Audit review 7

**Source:** `agents/audit-reviews/review-7.md`
**Created:** 2026-11-22
**Version:** 7

Fixes the findings the operator approved on review-7's page on 2026-11-22
(F1-F4 and O1; U1 was kept as not a finding). The answers are in review-7's
Answers section. No task changes a brief in
`claude/skills/auditme/phaseb/briefs/`.

---

## Task 1: Correct the two doc statements

**Status:** done
**Priority:** medium
**Complexity:** small
**Source Reference:** F1, F2

**Technical Goal:** the user docs and the skill's completion gate describe
the sampled cadence and the `silent-self-mutation` exemptions as the code has
them.

**Subtasks:**

- [x] F1: in `docs/reference/skills.md` (line 32 on 2026-11-22) and in the completion gate of `claude/skills/auditme/SKILL.md` (line 252), say a sampled question runs on the lines changed since the previous review, each widened to its enclosing function, as the Sampled cadence section of `SKILL.md` says
- [x] F1: `grep -rn 'files changed since\|changed files' docs README.md AGENTS.md claude/skills/auditme/SKILL.md agents/specs` and fix each other line that describes the sampled mode as whole files; leave dated records and lines about `changed.py`'s own file selection as they are
- [x] F2: in `docs/guide/checker.md`'s `silent-self-mutation` row (line 294), add that a method whose name is one of the listed words followed by `_` and more (`update_cache`) is exempt too, read from `check_silent_self_mutation` in `claude/skills/auditme/checks/auditme/rules/state_and_effects.py`
- [x] Find each statement by its text; the line numbers are from 2026-11-22

**Acceptance Criteria:**

- [x] Each statement matches the code it describes
- [x] `uv run --group docs mkdocs build --strict` exits 0

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/phaseb/test_briefs.py -q -p no:cacheprovider` passes (it reads `SKILL.md`)

**Notes:**

- Key files: `docs/reference/skills.md`, `docs/guide/checker.md`, `claude/skills/auditme/SKILL.md`

---

## Task 2: Name the dropped modes and stop swallowing unparse failures

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** F3, F4, O1

**Technical Goal:** no call drops a returned component unnamed, no check
swallows an unexpected exception, and the sibling-error check's comments say
what it does.

**Subtasks:**

- [x] F3: in `claude/skills/auditme/checks/auditme/phaseb/architecture.py` (line 50 on 2026-11-22), unpack `auditme.core.cached_roots(scope)` into named parts (`roots, _modes = ...`), as `core.py` and `docrefs.py` do
- [x] F4: write a test first, in `claude/skills/auditme/tests/test_error_handling.py`, that `check_sibling_error_no_common_base` reports the same hit for an `errors.py` whose error classes have attribute, call and subscript bases; then remove the `contextlib.suppress(Exception)` around `ast.unparse(base)` in `claude/skills/auditme/checks/auditme/rules/error_handling.py` (line 418). `ast.unparse` of a parsed base expression does not fail; if a case is found that does, catch only that exception and test it
- [x] O1: replace the comments at `error_handling.py:442-446` with one that says what the check does: one finding per `errors.py` that holds two or more error classes with no shared parent in the file
- [x] Record `python3 claude/skills/auditme/checks/audit.py .` before and after, outside the repository, and diff them

**Acceptance Criteria:**

- [x] The audit output is identical before and after
- [x] The new test passes

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/phaseb/test_architecture_candidates.py -q -p no:cacheprovider` passes

**Notes:**

- The audit output differs only by one accepted finding's line number in `architecture.py` (793 to 794), from the extra unpack line.
- F3 uses `roots, _ =` as `docrefs.py` does: `roots, _modes =` is flagged by the leading-underscore-binding check.
- Key files: `claude/skills/auditme/checks/auditme/phaseb/architecture.py`, `claude/skills/auditme/checks/auditme/rules/error_handling.py`

---

## Task 3: Run the whole-tree checks, the doc listers, and update the summary

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** all

**Technical Goal:** the branch passes every whole-tree check before it
merges, its docs still match the code it changed, and the audit summary
records what this list resolved.

**Subtasks:**

- [ ] Run `python3 claude/skills/auditme/checks/phaseb.py candidates . --question Doc4` and `--question Doc5`, take the candidates whose `path` is a doc or spec this list changed, or that names a code file it changed (`git diff --name-only <base>...HEAD`), and check every statement in their sections against the code by hand; fix any that no longer matches. Record what was checked in the task's Notes
- [ ] For each identifier or behaviour this list changed, grep `docs agents/specs README.md AGENTS.md` for its old form and fix each hit
- [ ] In `agents/audit-reviews/summary.md`, move each finding Tasks 1 and 2 fixed to Recently resolved, naming its task; when none is left, replace the Unresolved table with the sentence "No finding is unresolved: every finding review-7 raised shipped (below)." rather than an empty row

**Acceptance Criteria:**

- [ ] The Unresolved section holds only findings that did not ship, each with its reason

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `pre-commit run --all-files` passes
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` passes (the pre-push whole-tree audit)
- [ ] `uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes
- [ ] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Depends on Tasks 1 and 2

---
