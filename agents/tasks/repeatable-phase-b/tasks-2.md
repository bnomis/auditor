# Tasks: Repeatable Phase B

**Spec:** `agents/specs/repeatable-phase-b/spec.md`
**Created:** 2026-11-21
**Version:** 2

Implements amendment 1.2 of the spec only: one result line for every listed
question, `{id, findings: {kind: [...]}, reason}`, with each question's
finding kinds registered beside its lister, so `phaseb.py check` and `merge`
read every listed question and not only A4. Everything else in the spec
shipped with `agents/tasks/repeatable-phase-b/tasks-1.md` and the three
listed-question task lists; this list changes no lister, hash, ledger format,
`Verdict` field or `flagged`.

`REGISTRY` keeps its `(lister, brief, batch_size)` tuple, which
`claude/skills/auditme/tests/phaseb/test_cli.py` unpacks; the kinds live in a
separate mapping read through `question_kinds`. The only existing tests a task
may change are those that write a result line in A4's old top-level shape
(`missing` and `extra` beside `id`), because amendment 1.2 makes that shape
unparseable; each such test moves to the `findings` shape and keeps what it
asserts. A task that needs to change any other existing test stops as
`blocked` and names it.

Every task runs unattended: none calls an LLM, makes a network request or
reads another repository. The repository has no affected-tests tool, so each
task names its own test files and the last task runs every test tree the
change can reach. Test commands run from the repository root. Tests use
neutral fixture names (`pkg`, `probe`, `ProbeError`), as the shared
repository's `no-project-names` hook requires.

---

## Task 1: Register each question's finding kinds

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** API (`register_question`, `question_kinds`); Implementation, The result line (1.2), the kinds table

**Technical Goal:** Give `register_question` a `kinds` argument, keep the
kinds in a `KINDS` mapping beside `REGISTRY`, add `question_kinds`, and pass
each registered question its kinds from the spec's table.

**Subtasks:**

- [x] Starting-point check: `grep -rnwE 'question_kinds|KINDS' claude/skills/auditme/checks` prints nothing; if it prints anything, stop as `blocked` and name what it found
- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_model.py`, inside the fixture that saves and restores `REGISTRY` (save and restore `KINDS` the same way): registering a question stores its kinds and `question_kinds` returns them in the order given; empty kinds and a repeated kind each raise `PhaseBError` and register nothing; `question_kinds` on an unregistered question raises `PhaseBError`; and every question in `REGISTRY` after import has kinds equal to the spec's table (A4 `('missing', 'extra')`, Doc4 and Doc5 `('drift',)`, Doc1 and Doc2 `('stale', 'missing')`, T1 and T2 `('missing',)`, A1 `('call',)`, A11 `('unexhausted',)`, A17 `('surface',)`, A19 `('handler',)`). Run them and see them fail
- [x] In `claude/skills/auditme/checks/auditme/phaseb/candidates.py`, change the signature to `register_question(question, brief, kinds, batch_size=DEFAULT_BATCH_SIZE)`, validate `kinds`, store it in `KINDS: dict[str, tuple[str, ...]]`, and add `question_kinds` with the spec's docstring
- [x] Update every registration to pass its kinds as the third argument and any batch size by keyword (`batch_size=DOC_BATCH_SIZE`): the A4, Doc4, Doc5, Doc1, Doc2, T1 and T2 decorators in `candidates.py`, and the A11, A19, A1 and A17 decorators in `claude/skills/auditme/checks/auditme/phaseb/architecture.py`
- [x] Update the `Verdict.findings` comment in `candidates.py` to the spec's ("one list per registered kind")

**Acceptance Criteria:**

- [x] `question_kinds` returns the spec's kinds for every registered question
- [x] `REGISTRY`'s value tuple is unchanged, and `test_cli.py` passes unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/phaseb/test_model.py claude/skills/auditme/tests/phaseb/test_cli.py claude/skills/auditme/tests/phaseb/test_architecture_candidates.py claude/skills/auditme/tests/phaseb/test_doc_candidates.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/phaseb/candidates.py`, `claude/skills/auditme/checks/auditme/phaseb/architecture.py`
- BLOCKED (2026-11-21): the spec's signature makes `kinds` a required third argument, so four existing tests in `claude/skills/auditme/tests/phaseb/test_model.py` that call `register_question` without it (`test_register_question_records_lister_and_brief`, `test_register_question_returns_the_lister`, `test_question_registered_without_a_size_reads_back_the_default`, `test_question_registered_with_a_size_reads_it_back`) would fail. They are not A4 result-shape tests, so the list forbids changing them. Needs a decision: allow those four to pass `kinds`, or give `kinds` a default (which the spec forbids).
- DECIDED by the operator (2026-11-21): those four tests in `test_model.py` gain a `kinds` argument and keep what they assert; `kinds` stays required, as the spec says. This exception names those four tests only: any other existing test that would need changing still stops the task as `blocked`
- Pre-push audit (2026-11-21): only hit is ruff-version-drift (.pre-commit-config.yaml pins v0.17.2, local ruff is 0.17.5), not caused by this task
- The Doc registrations pass a batch size third today (`DOC_BATCH_SIZE`, `AGENTS_BATCH_SIZE`); moving it to a keyword is what keeps it from landing in `kinds`

---

## Task 2: Read the `findings` object in `check` and `merge`

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation, The result line (1.2); API (`check_run`)

**Technical Goal:** Make `parse_result` validate a line's `findings` object
against `question_kinds(plan.question)`, and `read_run_verdicts` store it
with each list sorted, so a line in any registered question's brief shape
passes and A4's old top-level shape does not.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_batches.py`: for every question in `REGISTRY`, a run whose result line has `findings` with exactly that question's kinds (one kind non-empty) passes `check_run` with no problem and no retry, and `read_run_verdicts` returns a `Verdict` whose `findings` holds those kinds with each list sorted; each of these lines is reported unparseable against its batch: a `findings` with an unregistered kind, one with a kind missing, one whose value is not a list of strings, a line with a key other than `id`, `findings` and `reason`, and an A4 line with top-level `missing` and `extra` and no `findings`. Run them and see them fail
- [x] In `claude/skills/auditme/checks/auditme/phaseb/batches.py`, give `parse_result` the question's kinds (from the plan the caller already reads) and validate the line as the spec says; keep its `ValueError` for every malformed line, so `check_batch` reports it as today
- [x] In `read_run_verdicts`, build `Verdict.findings` from the line's `findings`, each list sorted, in place of the hard-coded `missing` and `extra`
- [x] Move each existing test that writes a result line in A4's old top-level shape (in `test_batches.py`, `test_cli.py` and `test_briefs.py`) to the `findings` shape, keeping what it asserts; stop as `blocked` if any other existing test fails
- [x] Update the module docstring of `batches.py`, which describes the result line as `id`, `missing`, `extra`, `reason`

**Acceptance Criteria:**

- [x] A line in every registered question's shape passes `check_run`, and `merge` writes it to the ledger
- [x] A4's old top-level shape is reported unparseable

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/phaseb/test_batches.py claude/skills/auditme/tests/phaseb/test_cli.py claude/skills/auditme/tests/phaseb/test_ledger.py claude/skills/auditme/tests/phaseb/test_briefs.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- `test_ledger.py` and `test_model.py` build `Verdict` objects with `findings={'missing': ..., 'extra': ...}`: that is the ledger format, which does not change, so those tests stay as they are

---

## Task 3: Move the A4 and Doc briefs to the `findings` shape

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation, The result line (1.2), the Brief version column

**Technical Goal:** Rewrite the Output section of the A4, Doc1, Doc2, Doc4
and Doc5 briefs to ask for `{id, findings, reason}` with the question's
kinds, bump their versions, and test that every brief's Output names exactly
its registered kinds.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_briefs.py`: for every question in `REGISTRY`, its brief's Output section asks for a `findings` key and names each of `question_kinds(question)` and no top-level kind keys; the A4 brief's version is 3 and the Doc1, Doc2, Doc4 and Doc5 briefs' versions are 2; the T1, T2, A1, A11, A17 and A19 briefs' versions are unchanged at 1. Run them and see them fail
- [x] In `claude/skills/auditme/phaseb/briefs/A4.md`, rewrite Output so `findings` holds `missing` and `extra`, each sorted, with the same meanings as now, and set `**Brief version:** 3`
- [x] In `Doc4.md` and `Doc5.md`, move `drift` under `findings` with the same meaning, and set version 2; in `Doc1.md` and `Doc2.md`, move `stale` and `missing` under `findings`, and set version 2. Change nothing outside each Output section and its version line
- [x] Update any existing assertion in `test_briefs.py` that quotes a moved key at the top level, keeping what it asserts

**Acceptance Criteria:**

- [x] Every brief's Output names exactly its question's registered kinds under `findings`
- [x] The A4 brief is at version 3 and the Doc briefs at version 2; no threshold text changed

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/phaseb/test_briefs.py claude/skills/auditme/tests/phaseb/test_cli.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- The four thresholds the 2026-11-21 Doc pilot named are not settled here: they are the open `TODO.md` item "Pilot the documentation listers' batch sizes on a real audit", and land as later brief bumps

---

## Task 4: Whole-tree checks, close the spec and the TODO item

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** whole amendment 1.2; Tests (1.2)

**Technical Goal:** Prove every registered question round-trips through the
command line, run every check the change can reach, mark the spec
implemented and move the `TODO.md` item to `DONE.md`.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_cli.py`: for every question in `REGISTRY`, on a fixture project that gives it at least one candidate, `plan`, then a result file written in its brief's shape for every planned id, then `check` exits 0 and `merge` writes one ledger line per candidate. A question whose fixture lists no candidate is not skipped silently: the test names it and fails. Run them and see them fail if any question is not yet covered
- [x] Hoist anything the change duplicates (a kinds literal written in both `candidates.py` and a test, a second parser of the result line) to a single owner and import it
- [x] Confirm `claude/skills/auditme/tests/registry-order.txt` is unchanged against the branch's base (`git diff <base> -- claude/skills/auditme/tests/registry-order.txt` prints nothing)
- [x] Set the spec's `**Status:**` to `implemented`
- [x] Move the `TODO.md` item "`phaseb.py check` rejects the result of every listed question but A4" to the end of `DONE.md`: append its heading and body unchanged, then `Done: <date> - amendment 1.2 of agents/specs/repeatable-phase-b/spec.md, agents/tasks/repeatable-phase-b/tasks-2.md.`, and remove it from `TODO.md`; touch no other item

**Acceptance Criteria:**

- [x] Every registered question passes `plan`, `check` and `merge` end to end
- [x] The spec's status is `implemented`, and the item is in `DONE.md` and not in `TODO.md`

**Definition of Done:**

- [x] `pre-commit run --all-files` exits 0
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests claude/skills/project-setup/tests tests -q -p no:cacheprovider` passes
- [x] `uv run --group docs mkdocs build --strict` passes
- [x] `D=$(mktemp -d) && git show "$(git log --diff-filter=A --format=%H -- agents/tasks/repeatable-phase-b/tasks-2.md)":TODO.md > "$D/todo-before.md" && python3 ~/.claude/skills/todo-review/verify_bodies.py "$D/todo-before.md" TODO.md DONE.md` exits 0

**Notes:**

- Depends on Tasks 1-3
- Pre-push audit (2026-11-21): only hit is ruff-version-drift (.pre-commit-config.yaml pins v0.17.2, local ruff is 0.17.5), not caused by this task

---
