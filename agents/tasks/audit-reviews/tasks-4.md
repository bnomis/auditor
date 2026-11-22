# Tasks: Audit review 4

**Source:** `agents/audit-reviews/review-4.md`
**Created:** 2026-11-22
**Version:** 4

Fixes the findings the operator approved on review-4's page on 2026-11-22:
F2 to F10, all "Fix". F1 was dismissed and is recorded in the A1 ledger. D1
leaves the default-verdict cases as they are; D2 is a request in
`claude/skills/auditme/requests.md` and not this list's work. The answers
are in review-4's Answers section.

Every task's Definition of Done names the tests for the modules it changes;
the last task runs the whole-tree checks once, before the branch merges.

---

## Task 1: Fail the no-project-names hook when its list cannot be read

**Status:** todo
**Priority:** high
**Complexity:** small
**Source Reference:** F7

**Technical Goal:** a list of names that exists but cannot be read stops the
hook with an error, so a commit is never passed unchecked because of it.

**Subtasks:**

- [ ] Write the failing test first, in `tests/test_check_foreign_names.py`: with `AUDITOR_FOREIGN_NAMES` pointing at a list file that exists but cannot be read (mode `000`; skip the test when running as root, where the mode does not stop a read), the script exits 2 and names the list on stderr, whatever the files passed
- [ ] In `bin/check-foreign-names.sh`, read the list so that a read failure is caught (test `-r` before reading, or check grep's status, which is 2 on a read error and 1 when it only filtered every line out) and exit 2 with `check-foreign-names: cannot read <list>`; a list whose lines are all blank or comments still exits 0
- [ ] Update the exit table in `docs/reference/cli.md` (the `bin/check-foreign-names.sh` section)

**Acceptance Criteria:**

- [ ] The new test fails before the change and passes after it
- [ ] The existing tests in `tests/test_check_foreign_names.py` and `tests/test_published_hooks.py` pass unchanged

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest tests/test_check_foreign_names.py tests/test_published_hooks.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `bin/check-foreign-names.sh` (lines 25-36 on 2026-11-22)

---

## Task 2: Keep a `--base` value that starts with `-` out of git

**Status:** todo
**Priority:** high
**Complexity:** small
**Source Reference:** F6

**Technical Goal:** no `--base` value reaches `git diff` as an option,
whatever spelling or repetition argparse accepts.

**Subtasks:**

- [ ] Write the failing tests first, in `claude/skills/auditme/tests/test_changed.py`: `--bas=-x` (an abbreviation argparse accepts) and `--base main --base=-x` (argparse keeps the last) each exit with a usage error and run no `git diff`
- [ ] In `claude/skills/auditme/checks/changed.py`, check the value argparse parsed (`args.base`) rather than the raw arguments: refuse a value that starts with `-`. Keep or drop `option_value_is_flag` as the new check makes it needed or not
- [ ] In the `git diff` call that takes the base (`changed_files`, line 105 on 2026-11-22), pass `--end-of-options` before the revision range, so git never reads it as an option even if a check is missed
- [ ] Update `docs/reference/cli.md` and `docs/guide/checker.md` where they describe `--base`

**Acceptance Criteria:**

- [ ] The new tests fail before the change and pass after it
- [ ] The existing `test_changed.py` tests pass unchanged

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/test_changed.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/changed.py` (`option_value_is_flag` at line 191, `changed_files` at line 105, on 2026-11-22)

---

## Task 3: Re-export batches from phaseb in the relative form

**Status:** todo
**Priority:** low
**Complexity:** small
**Source Reference:** F2

**Technical Goal:** `phaseb.py` reads `auditme.phaseb.batches` through the
package's public surface, without the absolute from-import S4 forbids.

**Subtasks:**

- [ ] In `claude/skills/auditme/checks/auditme/phaseb/__init__.py`, import the submodule with `from . import batches` and add `'batches'` to `__all__`, in the order `non-alphabetical-literal` accepts
- [ ] Confirm the sweep reports no new hit (`python3 claude/skills/auditme/checks/audit.py .`), and that the A17 lister's payload for `phaseb/__init__.py` no longer shows `phaseb.py` reaching a name outside `__all__`

**Acceptance Criteria:**

- [ ] `grep -n '^from auditme' claude/skills/auditme/checks/auditme/phaseb/__init__.py` prints nothing
- [ ] `batches` is in `auditme.phaseb.__all__`

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/phaseb/__init__.py`

---

## Task 4: Keep one copy of the root modes

**Status:** todo
**Priority:** low
**Complexity:** small
**Source Reference:** F3

**Technical Goal:** the root-mode mapping has one source within a run, so a
reader of `ROOT_MODULES` and a reader of the per-run cache always agree.

**Subtasks:**

- [ ] Write the failing test first, in `claude/skills/auditme/tests/test_core.py`: resolve the roots of scope A, then of scope B, then of A again from the cache; after the third call, the mode `py_files` uses for A's roots is A's
- [ ] In `claude/skills/auditme/checks/auditme/core.py`, make `cached_roots` (line 759 on 2026-11-22) set `ROOT_MODULES` on a cache hit too, or make the readers (`core.py:222`, `core.py:230`, `rules/imports_and_surfaces.py:129`) take the mode from the cache; choose whichever leaves one place that holds the mapping

**Acceptance Criteria:**

- [ ] The new test fails before the change and passes after it
- [ ] The sorted sweep of this repository is unchanged (`python3 claude/skills/auditme/checks/audit.py . | sort`, before and after)

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests -q -p no:cacheprovider` passes (`core.py` is reached by every test module)

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/core.py`, `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py`

---

## Task 5: Cut the reads and repeated work in docrefs

**Status:** todo
**Priority:** low
**Complexity:** medium
**Source Reference:** F4, F5

**Technical Goal:** `docrefs.py`'s name resolver does not read files under a
pure name, and one index build resolves the roots and the settings classes
once.

**Subtasks:**

- [ ] Record the Doc4 and Doc5 listings first: `python3 claude/skills/auditme/checks/phaseb.py candidates . --question Doc4 > <scratch>/doc4-before.jsonl`, and the same for Doc5
- [ ] F4: make `resolve_name` (`claude/skills/auditme/checks/auditme/phaseb/docrefs.py:380` on 2026-11-22) stop reading files through `read_path_targets` and `file_target` (`:312`): take the line count from a per-run cache built where files are read, or rename the reading functions after what they do, so the resolver stays a query
- [ ] F5: in `CorpusIndex.build` (`:187`), take the roots and file list from the per-run cache (`auditme.core.corpus_index` or `cached_roots`) instead of calling `audit_roots`, `corpus_definitions` and `corpus_py_files` each again; compute `settings_classes()` once per index and reuse it in `resolve_setting` (`:360`)
- [ ] Add a test in `claude/skills/auditme/tests/phaseb/test_docrefs.py` that one `CorpusIndex.build` calls `auditme.core.declared_roots` once
- [ ] Run the two listings again and diff them against the recorded ones

**Acceptance Criteria:**

- [ ] The Doc4 and Doc5 listings are identical before and after
- [ ] The new test fails before the change and passes after it

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/phaseb/test_docrefs.py claude/skills/auditme/tests/phaseb/test_doc_candidates.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 4, which changes `cached_roots`
- Keep the record files outside the repository

---

## Task 6: Correct the specs and their cross-references

**Status:** todo
**Priority:** low
**Complexity:** small
**Source Reference:** F8, F10

**Technical Goal:** the two project-setup statements match the code, and the
three 2026-11-22 amendments link the spec they cite.

**Subtasks:**

- [ ] F8, `agents/specs/project-setup/spec.md`: at line 356 (on 2026-11-22) say the spec-drift check is in `PROJECT_CHECKS`; at line 598 give the `new` step's command as `pre-commit install --hook-type pre-commit --hook-type pre-push`, as `claude/skills/auditme-project-setup/SKILL.md` runs it. Find each by its text
- [ ] F10: in `agents/specs/listed-phase-b-architecture-questions/spec.md` (line 59), `listed-phase-b-documentation-questions/spec.md` (line 242) and `listed-phase-b-test-questions/spec.md` (line 259), replace the code-formatted `agents/specs/repeatable-phase-b/spec.md` with the relative link `[Repeatable Phase B](../repeatable-phase-b/spec.md)`

**Acceptance Criteria:**

- [ ] Both F8 statements match the code
- [ ] `grep -n '`agents/specs/repeatable-phase-b/spec.md`' agents/specs/listed-phase-b-*/spec.md` prints nothing

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)

**Notes:**

- Key files: the four specs named above

---

## Task 7: Correct the user docs

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** F9

**User Story:** As a user of the checker, I want its guides to say what it
does, so that I can rely on their failure lists and descriptions.

**Subtasks:**

- [ ] Correct each site F9 lists in `agents/audit-reviews/review-4.md`, checking each against the code as it stands after Tasks 1 to 5:
  - `docs/concepts.md:25`
  - `docs/guide/checker.md:70`
  - `docs/reference/cli.md:52`
  - `docs/reference/skills.md:33`, `:36` and `:73`
  - `docs/setup.md:22` and `:275`
- [ ] For `docs/reference/cli.md:52`, judge the installer's exit cases against the pinned `install-in-claude` commit the repository names (`fa68deb` on 2026-11-22); if that version cannot be read, leave the row and say so in the task's Notes
- [ ] Include the exit changes Tasks 1 and 2 made
- [ ] Line numbers are from 2026-11-22; find each statement by its text
- [ ] Run `uv run mkdocs build --strict`

**Acceptance Criteria:**

- [ ] Each F9 statement is corrected
- [ ] `uv run mkdocs build --strict` exits 0

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)

**Notes:**

- Depends on Tasks 1 to 5

---

## Task 8: Run the whole-tree checks and update the summary

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** all

**Technical Goal:** the branch passes every whole-tree check before it
merges, and the audit summary records what this list resolved.

**Subtasks:**

- [ ] In `agents/audit-reviews/summary.md`, move each finding Tasks 1 to 7 fixed from Unresolved to Recently resolved, naming its task; leave any that did not ship, with the reason
- [ ] Under "Checker changes since the last review", add a dated line for each behaviour change (the hook's exit 2 on an unreadable list, the `--base` check, the `batches` re-export)

**Acceptance Criteria:**

- [ ] The Unresolved table holds only findings that did not ship, each with its reason

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `pre-commit run --all-files` passes
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` passes (the pre-push whole-tree audit)
- [ ] `uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes (`core.py` changed, and every checker test reaches it; Task 1 changes a script the top-level tests run)

**Notes:**

- Depends on Tasks 1 to 7

---
