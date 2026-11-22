# Tasks: Audit review 13

**Source:** `agents/audit-reviews/review-13.md`
**Created:** 2026-11-22
**Version:** 12

Fixes the findings of review-13 (F1-F5), answered by Claude on 2026-11-22
under the loop the operator delegated that day; the answers are in
review-13's Answers section. No task changes a brief in
`claude/skills/auditme/phaseb/briefs/`.

Two findings (F3, F4) were made by earlier fixes. Each fix here therefore
adds a guard that stops the pattern coming back: a test that fails on it, or
a rule stated in place of a closed list.

---

## Task 1: Fix the names hook's directory list and state `phaseb.py`'s exit rule

**Status:** done
**Priority:** high
**Complexity:** small
**Source Reference:** F2, F4

**Technical Goal:** the names hook never passes a commit it did not check,
and the CLI reference states `phaseb.py`'s exit-2 rule rather than a list.

**Subtasks:**

- [x] F2: write the failing tests first, in `tests/test_check_foreign_names.py`: a list path that is a directory exits 2 with "cannot read"; a list path where nothing exists still exits 0 with the "no list" notice
- [x] F2: in `bin/check-foreign-names.sh` (line 26 on 2026-11-22), test absence with `[ ! -e "$list" ]` for the exit-0 branch, so the existing exit-2 branch handles a path that exists but is not a readable regular file; update `docs/reference/cli.md`'s exit table for the hook (line 83) to say "nothing exists at the list path"
- [x] F4: in `docs/reference/cli.md` (the paragraph at line 176), replace the closed list of `phaseb.py`'s exit-2 causes with the rule: `phaseb.py` exits 2, printing the error's message, whenever a Phase B step fails; then give a few cases introduced by "for example" (an unregistered `--question`, a missing root, a merge for another question, a merge whose batches fail `check`). Grep `docs agents/specs` for any other closed list of `phaseb.py`'s exit causes and treat it the same way

**Acceptance Criteria:**

- [x] The new tests fail before the change and pass after it
- [x] No doc or spec gives a closed list of `phaseb.py`'s exit-2 causes

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests/test_check_foreign_names.py -q -p no:cacheprovider` passes
- [x] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Key files: `bin/check-foreign-names.sh`, `docs/reference/cli.md`

---

## Task 2: Name the root modes, cache the lazy-import table, test the per-run cache

**Status:** done
**Priority:** medium
**Complexity:** small
**Source Reference:** F1, F3, F5

**Technical Goal:** no call drops the root modes unnamed, every helper
reading `AGENTS.md` or `pyproject.toml` runs once per sweep, and the per-run
cache is tested where it is defined.

**Subtasks:**

- [x] Record `python3 claude/skills/auditme/checks/audit.py .` and `python3 claude/skills/auditme/checks/phaseb.py candidates . --question <Q>` for A1, A17 and A4, outside the repository
- [x] F3: write a test first, in `claude/skills/auditme/tests/test_core.py`, that reads every `.py` file under `claude/skills/auditme/checks/` and fails if any `cached_roots(...)` call is subscripted (parse with `ast` and look for a `Subscript` whose value is a call to `cached_roots`); then unpack each site into named parts (`roots, _modes = ...`): `phaseb/architecture.py:85`, `:622`, `phaseb/candidates.py:382` on 2026-11-22
- [x] F5: route `accepted_lazy_imports` (`claude/skills/auditme/checks/auditme/core.py:263`) through `cached_per_run`; then `grep -rn "AGENTS.md\|pyproject.toml" claude/skills/auditme/checks/auditme` and confirm every helper that reads either file is cached per run, caching any that is not
- [x] F1: add direct tests of `cached_per_run` to `claude/skills/auditme/tests/test_core.py`: it computes once per name and scope in a run, computes again after the per-run cache is cleared, and keeps two names apart
- [x] Run the commands again and diff them against the record

**Acceptance Criteria:**

- [x] Every output is identical before and after
- [x] The subscript test fails before the F3 change and passes after it

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/test_imports_and_surfaces.py claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Every `AGENTS.md` / `pyproject.toml` reader checked: `accepted_lazy_imports` now cached; the others are already cached per run or run once per command, not per root.
- Key files: `claude/skills/auditme/checks/auditme/core.py`, `phaseb/architecture.py`, `phaseb/candidates.py`

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
- [ ] In `agents/audit-reviews/summary.md`, move each finding Tasks 1 and 2 fixed to Recently resolved, naming its task; when none is left, replace the Unresolved table and the line above it with the sentence "No finding is unresolved: every finding review-13 raised shipped (below)." rather than an empty row

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
