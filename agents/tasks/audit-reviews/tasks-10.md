# Tasks: Audit review 11

**Source:** `agents/audit-reviews/review-11.md`
**Created:** 2026-11-22
**Version:** 10

Fixes the findings the operator approved on review-11's page on 2026-11-22
(F1-F4; F5 was dismissed). The answers are in review-11's Answers section.
No task changes a brief in `claude/skills/auditme/phaseb/briefs/`.

---

## Task 1: Refuse a `phaseb.py` root that is not a directory

**Status:** done
**Priority:** high
**Complexity:** small
**Source Reference:** F1

**User Story:** As an operator running Phase B, I want a mistyped project
root to fail loudly, so that an empty listing or report never reads as a
clean result.

**Subtasks:**

- [x] Write the failing tests first, in `claude/skills/auditme/tests/phaseb/test_cli.py`: each of `candidates`, `plan`, `merge`, `report` and `dismiss` given a root that does not exist, and one that is a file, exits 2 and names the path on stderr, and writes nothing
- [x] In `claude/skills/auditme/checks/phaseb.py`, check the root once for every subcommand (in the argument type, or where `main` dispatches) and exit 2 with a message naming the path, as `claude/skills/auditme/checks/audit.py` does for its project root
- [x] Add the case to `phaseb.py`'s exit codes in `docs/reference/cli.md`, and to the synopsis's error notes in `agents/specs/repeatable-phase-b/spec.md` if that spec lists `phaseb.py`'s exit codes

**Acceptance Criteria:**

- [x] `python3 claude/skills/auditme/checks/phaseb.py report /nonexistent/xyz --question A1` exits 2
- [x] The new tests fail before the change and pass after it

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/phaseb/test_cli.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/phaseb.py`, `docs/reference/cli.md`

---

## Task 2: Work out the roots and each function's flags once per listing

**Status:** done
**Priority:** medium
**Complexity:** small
**Source Reference:** F2, F4

**Technical Goal:** a Phase B listing resolves the audit roots once, and the
A11 lister walks each function once.

**Subtasks:**

- [x] Record `python3 claude/skills/auditme/checks/phaseb.py candidates . --question <Q>` for every listed question, outside the repository
- [x] F2: `grep -rn 'audit_roots(' claude/skills/auditme/checks/auditme/phaseb` and route every call through `auditme.core.cached_roots` (on 2026-11-22: `architecture.py:85`, `:619`, `:772`, `candidates.py:382`, `:611`, `testmap.py:312`); add a test in `claude/skills/auditme/tests/phaseb/test_architecture_candidates.py` that one A1 listing scans the roots once (count calls to `auditme.core.audit_roots` with a monkeypatch)
- [x] F4: in `list_a11_candidates` (`claude/skills/auditme/checks/auditme/phaseb/architecture.py:297`), compute `flag_subjects` once per function rather than once per statement; add a test that it is called once per function
- [x] Run the listings again and diff them against the record

**Acceptance Criteria:**

- [x] Every listing is identical before and after
- [x] `grep -rn 'audit_roots(' claude/skills/auditme/checks/auditme/phaseb` prints nothing
- [x] Each new test fails before its change and passes after it

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Measured on 2026-11-22 (review-11 F4): the A11 listing took 22.0 s on one project of 340 files, 6.6 s with `flag_subjects` computed once per function
- Key files: `claude/skills/auditme/checks/auditme/phaseb/architecture.py`, `candidates.py`, `testmap.py`

---

## Task 3: One `Verdict` builder for the tests

**Status:** done
**Priority:** low
**Complexity:** small
**Source Reference:** F3

**Technical Goal:** a field added to `Verdict` needs one test-helper edit,
not three.

**Subtasks:**

- [x] Add `make_verdict` to `claude/skills/auditme/tests/conftest.py`, beside `make_candidate`, with the defaults `make_ledger_verdict`, `make_model_verdict` and `make_batch_verdict` share, and keyword overrides for every field
- [x] Replace the three builders in `claude/skills/auditme/tests/phaseb/test_ledger.py`, `test_model.py` and `test_batches.py` with it; keep each test's arguments meaning the same
- [x] `grep -rn 'Verdict(' claude/skills/auditme/tests` and move any other test-local builder of the same shape to it

**Acceptance Criteria:**

- [x] No test file defines its own `Verdict` builder

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/phaseb/test_ledger.py claude/skills/auditme/tests/phaseb/test_model.py claude/skills/auditme/tests/phaseb/test_batches.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/tests/conftest.py`

---

## Task 4: Run the whole-tree checks, the doc listers, and update the summary

**Status:** done
**Priority:** medium
**Complexity:** small
**Source Reference:** all

**Technical Goal:** the branch passes every whole-tree check before it
merges, its docs and specs still match the code it changed, and the audit
summary records what this list resolved.

**Subtasks:**

- [x] Run `python3 claude/skills/auditme/checks/phaseb.py candidates . --question Doc4` and `--question Doc5`, take the candidates whose `path` is a doc or spec this list changed, or that names a code file it changed (`git diff --name-only <base>...HEAD`), and check every statement in their sections against the code by hand; fix any that no longer matches. Record what was checked in the task's Notes
- [x] In `agents/audit-reviews/summary.md`, move each finding Tasks 1 to 3 fixed to Recently resolved, naming its task; when none is left, replace the Unresolved table with the sentence "No finding is unresolved: every finding review-11 raised shipped or was dismissed (below)." rather than an empty row

**Acceptance Criteria:**

- [x] The Unresolved section holds only findings that did not ship, each with its reason

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `pre-commit run --all-files` passes
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` passes (the pre-push whole-tree audit)
- [x] `uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes
- [x] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Depends on Tasks 1 to 3
- Checked on 2026-11-22: the Doc4 and Doc5 candidates in the specs and docs this list changed, or that name its code files. The two statements about the new `<root>` refusal (the exit-2 sentence in `docs/reference/cli.md` and the exit-2 bullet in the `repeatable-phase-b` spec) match `project_root` in `phaseb.py` (an argparse error, exit 2). No other statement was stale; the `list_a11_candidates` and test-builder changes are internal.

---
