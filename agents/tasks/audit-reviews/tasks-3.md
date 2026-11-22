# Tasks: Audit review 3

**Source:** `agents/audit-reviews/review-3.md`
**Created:** 2026-11-22
**Version:** 3

Fixes the findings the operator approved on review-3's page on 2026-11-22:
F2 to F10, all "Fix". F1 was dismissed and is recorded in the A1 ledger. D1
and the `ruff format` defect are requests in
`claude/skills/auditme/requests.md`; they are not this list's work. The
answers are in review-3's Answers section.

Every task's Definition of Done names the tests for the modules it changes;
the last task runs the whole-tree checks once, before the branch merges.

---

## Task 1: Translate an OSError in changed.py's entry

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** F3

**Technical Goal:** a failure of `Path.cwd()` or `resolve()` in `changed.py`'s
`main` reaches the user as the gate's one-line error, not a traceback.

**Subtasks:**

- [ ] Write the failing test first, in `claude/skills/auditme/tests/test_changed.py`: with `pathlib.Path.cwd` patched to raise `OSError`, `changed.main([...])` exits non-zero and prints an `ERROR:` line naming the error, with no traceback
- [ ] In `claude/skills/auditme/checks/changed.py`, translate `OSError` from the `Path.cwd()` call (line 224 on 2026-11-22) and the `repo_root.resolve()` call (line 225) to `ChangedError`, so `main`'s existing handler reports it
- [ ] Add `ChangedError` to any `Raises:` section the change affects

**Acceptance Criteria:**

- [ ] The new test fails before the change and passes after it

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/test_changed.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/changed.py`

---

## Task 2: Add a property test for positive_int

**Status:** todo
**Priority:** low
**Complexity:** small
**Source Reference:** F2

**Technical Goal:** `phaseb.positive_int` has the hypothesis test T2 asks for.

**Subtasks:**

- [ ] In `claude/skills/auditme/tests/phaseb/test_cli.py`, add a test with `@settings(max_examples=20, deadline=10000)` over text and integers: `positive_int(value)` returns `int(value)` exactly when `value` parses as an integer of 1 or more, and raises `argparse.ArgumentTypeError` otherwise. Call `phaseb.positive_int` directly, not through a local alias

**Acceptance Criteria:**

- [ ] The test passes
- [ ] `python3 claude/skills/auditme/checks/phaseb.py candidates . --question T2` lists a property test for `phaseb.py::positive_int`

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/phaseb/test_cli.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/phaseb.py` (`positive_int`), `claude/skills/auditme/tests/phaseb/test_cli.py`

---

## Task 3: Build docrefs' dataclasses complete

**Status:** todo
**Priority:** low
**Complexity:** small
**Source Reference:** F4

**Technical Goal:** `ClassInfo` and `CorpusIndex` in `docrefs.py` are
constructed once with their contents, not filled after construction.

**Subtasks:**

- [ ] Record the current output first: `python3 claude/skills/auditme/checks/phaseb.py candidates . --question Doc4 > <scratch>/before.jsonl`, and the same for Doc5
- [ ] In `claude/skills/auditme/checks/auditme/phaseb/docrefs.py`, build the `members` and `field_types` dicts before constructing `ClassInfo` (line 227 on 2026-11-22), and make `CorpusIndex.build` (line 185) assemble its dicts, then construct the frozen index once; `add_module` then works on the dicts being assembled, not on the frozen instance
- [ ] Run the same two listings again and diff them against the recorded ones

**Acceptance Criteria:**

- [ ] The Doc4 and Doc5 listings are identical before and after
- [ ] No `CorpusIndex` or `ClassInfo` field is assigned or mutated after construction (grep the module)

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/phaseb/test_docrefs.py claude/skills/auditme/tests/phaseb/test_doc_candidates.py -q -p no:cacheprovider` passes

**Notes:**

- Keep the record files outside the repository
- Key files: `claude/skills/auditme/checks/auditme/phaseb/docrefs.py`

---

## Task 4: Name the local constants and make phaseb's imports relative

**Status:** todo
**Priority:** low
**Complexity:** small
**Source Reference:** F7, F8

**Technical Goal:** function-local constants are UPPER_SNAKE throughout, and
`phaseb/__init__.py` uses the relative `from .module import Symbol` form
`claude/rules/auditme/imports.md` allows.

**Subtasks:**

- [ ] In `claude/skills/auditme/checks/auditme/rules/error_handling.py`, rename `stdlib_excs` (line 249 on 2026-11-22) and `safe_attrs` (line 92) to UPPER_SNAKE and update their uses
- [ ] In `claude/skills/auditme/checks/auditme/phaseb/__init__.py`, replace the absolute `from auditme.phaseb... import` lines (10, 11, 20, 21) with `from .candidates import ...`, `from .errors import ...` and `from .ledger import ...`
- [ ] For `batches`: every reader imports `auditme.phaseb.batches` itself (`checks/phaseb.py`, `tests/phaseb/test_batches.py`), so drop `batches` from `phaseb/__init__.py`'s import and `__all__`; grep for `auditme.phaseb.batches` reached through the package attribute before removing it, and keep the side-effect import of `auditme.phaseb.architecture`
- [ ] Run the sweep and confirm no new hit (`python3 claude/skills/auditme/checks/audit.py .`)

**Acceptance Criteria:**

- [ ] `grep -n '^from auditme' claude/skills/auditme/checks/auditme/phaseb/__init__.py` prints nothing
- [ ] The sweep reports no unaccepted hit

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/rules/error_handling.py`, `claude/skills/auditme/checks/auditme/phaseb/__init__.py`

---

## Task 5: Resolve the roots once in surface_files' callers

**Status:** todo
**Priority:** low
**Complexity:** small
**Source Reference:** F5

**Technical Goal:** one T1 or A1 listing resolves the audit roots a fixed
number of times, not once per candidate.

**Subtasks:**

- [ ] Write the failing test first, in `claude/skills/auditme/tests/test_core.py`: with `auditme.core.audit_roots` wrapped to count its calls, listing T1 candidates for a fixture project with several functions calls it no more than a small fixed number of times (not once per candidate)
- [ ] Make `surface_files` (`claude/skills/auditme/checks/auditme/core.py:771` on 2026-11-22) take the roots from the per-run cache review-2's Task 6 added, or from its caller through `privacy`, instead of calling `audit_roots` itself
- [ ] Confirm the T1 and A1 listings of this repository are unchanged: run `python3 claude/skills/auditme/checks/phaseb.py candidates . --question <Q>` for T1 and A1 before and after and diff them

**Acceptance Criteria:**

- [ ] The new test fails before the change and passes after it
- [ ] The T1 and A1 listings are identical before and after

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests -q -p no:cacheprovider` passes (`core.py` is reached by every test module)

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/core.py` (`surface_files`, `privacy`), `claude/skills/auditme/checks/auditme/phaseb/candidates.py`, `claude/skills/auditme/checks/auditme/phaseb/architecture.py`

---

## Task 6: Move the error-handling and duplication checks onto the shared parse

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Source Reference:** F6

**Technical Goal:** the checks in `error_handling.py` and `duplication.py`
take each file's tree from `auditme.core.read_and_parse` rather than calling
`ast.parse` on its lines themselves.

**Subtasks:**

- [ ] Record the sweep first: `python3 claude/skills/auditme/checks/audit.py . | sort > <scratch>/sweep-before.jsonl`, and time three runs (`time python3 claude/skills/auditme/checks/audit.py . > /dev/null`)
- [ ] In `claude/skills/auditme/checks/auditme/rules/error_handling.py` and `duplication.py`, replace each `ast.parse('\n'.join(lines))` of a file's own lines with the tree `read_and_parse` returns for that path, keeping each check's handling of a file that does not parse (it is skipped, as before; an unreadable one is the driver's `unreadable-file` hit). Leave an `ast.parse` of a string that is not a file's content (a snippet, a docstring) as it is
- [ ] Sort the sweep again and diff it with the recorded one

**Acceptance Criteria:**

- [ ] The sorted sweep is identical before and after
- [ ] `grep -n "ast.parse('\\\\n'.join(lines))" claude/skills/auditme/checks/auditme/rules/error_handling.py claude/skills/auditme/checks/auditme/rules/duplication.py` prints nothing

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/test_duplication.py claude/skills/auditme/tests/test_get_container_default.py claude/skills/auditme/tests/test_driver.py -q -p no:cacheprovider` passes

**Notes:**

- On 2026-11-22 `error_handling.py` held 18 `ast.parse(` calls and `duplication.py` 1; not every one parses a file
- Keep the record files outside the repository

---

## Task 7: Move the remaining checks onto the shared parse, and measure

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Source Reference:** F6

**Technical Goal:** every remaining rule check takes its trees from
`read_and_parse`, and the sweep's run time is measured against the one
review-3 recorded.

**Subtasks:**

- [ ] Do the same as Task 6 for `state_and_effects.py`, `imports_and_surfaces.py`, `style_and_naming.py` and `project_hygiene.py`
- [ ] Sort the sweep and diff it with Task 6's recorded one
- [ ] Time three runs and record the median in the task's Notes, beside review-3's figure (12.2 s for a sweep of this repository, of which 5.4 s in `ast.parse`, measured on 2026-11-22)

**Acceptance Criteria:**

- [ ] The sorted sweep is identical to Task 6's record
- [ ] No rule module calls `ast.parse` on a file's own lines

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests -q -p no:cacheprovider` passes (the four modules' own tests are spread across most test modules)

**Notes:**

- Depends on Task 6, whose recorded sweep it diffs against

---

## Task 8: Correct the specs

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** F9

**Technical Goal:** each spec statement F9 lists says what the code does now,
or is worded as a record of its spec's change.

**Subtasks:**

- [ ] Correct each site F9 lists in `agents/audit-reviews/review-3.md`, checking each against the code as it stands after Tasks 1 to 7: the nine in `agents/specs/project-setup/spec.md`, and one each in the architecture-, documentation- and test-questions specs (the test-questions spec has two)
- [ ] Line numbers are from 2026-11-22; find each statement by its text

**Acceptance Criteria:**

- [ ] Each F9 statement is corrected or reworded as a record

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)

**Notes:**

- Depends on Tasks 1 to 7

---

## Task 9: Correct the user docs

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** F10

**User Story:** As a user of the checker, I want its guides to say what it
does, so that I can rely on their lists of failures, exemptions and rules.

**Subtasks:**

- [ ] Correct each site F10 lists in `agents/audit-reviews/review-3.md`, in `docs/concepts.md`, `docs/guide/checker.md`, `docs/reference/cli.md` and `docs/setup.md`, checking each against the code as it stands after Tasks 1 to 7. Include the two review-2 left stale: the failure list at `docs/reference/cli.md:229` and `docs/concepts.md:25`
- [ ] Where a list is only examples, say "for example"; otherwise make it complete
- [ ] Run `uv run mkdocs build --strict`

**Acceptance Criteria:**

- [ ] Each F10 statement is corrected
- [ ] `uv run mkdocs build --strict` exits 0

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)

**Notes:**

- Depends on Tasks 1 to 7

---

## Task 10: Run the whole-tree checks and update the summary

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** all

**Technical Goal:** the branch passes every whole-tree check before it
merges, and the audit summary records what this list resolved.

**Subtasks:**

- [ ] In `agents/audit-reviews/summary.md`, move each finding Tasks 1 to 9 fixed from Unresolved to Recently resolved, naming its task; leave any that did not ship, with the reason
- [ ] Under "Checker changes since the last review", add a dated line for each behaviour change (the `OSError` translation in `changed.py`, the shared parse and its measured run time, the dropped `batches` re-export)

**Acceptance Criteria:**

- [ ] The Unresolved table holds only findings that did not ship, each with its reason

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `pre-commit run --all-files` passes
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` passes (the pre-push whole-tree audit)
- [ ] `uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes (`core.py` and every rule module changed, and every checker test reaches them)

**Notes:**

- Depends on Tasks 1 to 9

---
