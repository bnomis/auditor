# Tasks: Audit review 5

**Source:** `agents/audit-reviews/review-5.md`, and the three open requests in `claude/skills/auditme/requests.md`
**Created:** 2026-11-22
**Version:** 5

Fixes the findings the operator approved on review-5's page on 2026-11-22
(F1, F2, F3, F5, F6 and F8; F4 and F7 were dismissed), and ships the three
requests open on that date, as the operator chose the same day:

- "A Doc candidate's hash leaves out the statements a reviewer reports under it" (review-5's Checker request; D2: ship before review-6);
- "Sample a changed file's changed lines between whole-tree audits" (D1);
- "Show a re-judged candidate's earlier verdict to its reviewer" (D3).

The answers are in review-5's Answers section. Each request's entry in
`requests.md` holds what it asks for.

Every task's Definition of Done names the tests for the modules it changes,
and every task that changes behaviour updates the docs and specs that
describe it in the same task. The last task runs the whole-tree checks and
the Doc4 and Doc5 listers over every doc and spec this list touched.

---

## Task 1: Correct the three doc statements

**Status:** done
**Priority:** medium
**Complexity:** small
**Source Reference:** F1, F2, F3

**Technical Goal:** the installer's exit table, the Stop-hook troubleshooting
list and the phaseb synopsis match the code.

**Subtasks:**

- [x] F1: in `docs/reference/cli.md`, the `bin/install-claude.sh` exit table's `1` row (line 52 on 2026-11-22): add that the installer also exits 1, before changing anything, when a key on the edit path is not an object or `hooks.Stop` is not a list. Review-5 read this from `install-in-claude` at the pinned commit `fa68deb` (`settings.py:137`, `:164`)
- [x] F2: in `docs/setup.md`, "The Stop hook does not fire" (line 268): add the cause "no reportable file changed, so `changed.py` skipped the sweep" (`claude/skills/auditme/checks/changed.py:229-231`)
- [x] F3: in `agents/specs/repeatable-phase-b/spec.md`, the command synopsis (lines 214-219): add `[--depth N]` to `candidates`, `plan`, `merge` and `report`, as `claude/skills/auditme/checks/phaseb.py` accepts it
- [x] Find each statement by its text; the line numbers are from 2026-11-22

**Acceptance Criteria:**

- [x] Each statement matches the code it describes
- [x] `uv run mkdocs build --strict` exits 0

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)

**Notes:**

- Key files: `docs/reference/cli.md`, `docs/setup.md`, `agents/specs/repeatable-phase-b/spec.md`

---

## Task 2: Move the two annotation-only imports under TYPE_CHECKING

**Status:** todo
**Priority:** low
**Complexity:** small
**Source Reference:** F8

**Technical Goal:** imports used only in annotations sit in a
`TYPE_CHECKING` block, as the coding standard asks.

**Subtasks:**

- [ ] Move `import collections.abc` in `claude/skills/auditme/checks/auditme/core.py` (line 5 on 2026-11-22) and the `Candidate` import in `claude/skills/auditme/checks/auditme/phaseb/ledger.py` (line 18) under `if typing.TYPE_CHECKING:`; first grep each module for a runtime use of the name, and leave the import where it is if one exists
- [ ] Confirm the sweep reports no new hit

**Acceptance Criteria:**

- [ ] Neither name is imported at runtime in its module, unless a runtime use was found and noted

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/phaseb/test_ledger.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/core.py`, `claude/skills/auditme/checks/auditme/phaseb/ledger.py`

---

## Task 3: Stop docrefs' resolver reading files, and read each file once in the listers

**Status:** todo
**Priority:** low
**Complexity:** medium
**Source Reference:** F5, F6

**Technical Goal:** no pure-named function in `docrefs.py` reads a file, and
one listing reads, parses and resolves each thing once.

**Subtasks:**

- [ ] Record the listings first, outside the repository: `python3 claude/skills/auditme/checks/phaseb.py candidates . --question <Q>` for every listed question
- [ ] F5: make `resolve_path` and `resolve_name` (`claude/skills/auditme/checks/auditme/phaseb/docrefs.py:328`, `:390` on 2026-11-22) take line counts from data already read when the index is built, so neither reaches `read_bytes()`; or give the reading functions names that say they read (`read_path_targets`), with every caller and doc updated
- [ ] F6, files read again: read each target file once per listing (`target_bytes`, `candidates.py:439`); read each document once (`:465`); read `AGENTS.md` once (`:572`, `:676`/`:687`); read a candidate's test files once per listing (`:816`, `:1075`). Use one per-run cache, cleared where the driver clears the parse cache
- [ ] F6, files parsed again: take trees from `auditme.core.read_and_parse` at `docrefs.py:191` and `candidates.py:302`, `:655`
- [ ] F6, work done twice: let `calls_of` (`candidates.py:348`) reuse the calls `direct` (`:330`) resolved; join a module's text once per module, not once per T2 site (`:1062`)
- [ ] Add a test in `claude/skills/auditme/tests/phaseb/test_doc_candidates.py` that one Doc4 listing reads a target file once however many sections name it
- [ ] Run the listings again and diff them against the record

**Acceptance Criteria:**

- [ ] Every listing is identical before and after
- [ ] The new test fails before the change and passes after it

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/phaseb/docrefs.py`, `claude/skills/auditme/checks/auditme/phaseb/candidates.py`, `claude/skills/auditme/checks/auditme/core.py`

---

## Task 4: Hash every statement a Doc candidate's findings can name

**Status:** todo
**Priority:** high
**Complexity:** small
**Source Reference:** request "A Doc candidate's hash leaves out the statements a reviewer reports under it" (review-5 D2)

**Technical Goal:** an edit anywhere in a section re-plans every candidate of
that section, so a fixed statement is judged again.

**Subtasks:**

- [ ] Write the failing test first, in `claude/skills/auditme/tests/phaseb/test_doc_candidates.py`: in a spec section that names a target on one line and holds another line naming no target, editing the second line changes the hash of the named-target candidate
- [ ] In `doc_candidates` (`claude/skills/auditme/checks/auditme/phaseb/candidates.py:479-489` on 2026-11-22), hash the whole section's text in every candidate of the section, plus the target's file, as the `(unresolved)` candidate already does
- [ ] Amend the hash description in `agents/specs/listed-phase-b-documentation-questions/spec.md` (its Content hash section), dated, citing review-5
- [ ] Delete the request's entry from `claude/skills/auditme/requests.md`

**Acceptance Criteria:**

- [ ] The new test fails before the change and passes after it
- [ ] The listings' candidate ids are unchanged; only Doc4 and Doc5 hashes change

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/phaseb/test_doc_candidates.py claude/skills/auditme/tests/phaseb/test_docrefs.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 3, which also edits `doc_candidates`

---

## Task 5: Give sampled reviewers the changed lines

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Source Reference:** request "Sample a changed file's changed lines between whole-tree audits" (review-5 D1)

**User Story:** As the operator running an audit between whole-tree passes,
I want each sampled question to judge only what changed since the last
review, so that a small edit does not reopen a whole file.

**Subtasks:**

- [ ] Starting-point check: `grep -nw -- '--scope' claude/skills/auditme/checks/changed.py` prints nothing; if it prints a line, stop as `blocked` and name the clash
- [ ] Write the failing tests first, in `claude/skills/auditme/tests/test_changed.py`: for a commit that changes one line inside a function of a three-function module, `changed.py --scope --base <commit>` prints that module's path with the enclosing function's line range only; a change at module level prints the changed lines; a new file prints its whole range; a deleted file prints nothing
- [ ] Add `--scope` to `claude/skills/auditme/checks/changed.py`: with the diff base it already resolves, print one JSON line per changed `.py` or `.sh` file, `{"path": ..., "ranges": [[start, end], ...]}`, each range a diff hunk widened to its enclosing function or class (Python, by `ast`); shell files keep the hunks as they are. It exits 0 and runs no sweep
- [ ] In `claude/skills/auditme/SKILL.md`'s "Sampled cadence", say that between whole-tree audits each sampled reviewer is given these ranges and judges only them, and that the review records the mode as "changed lines since <commit>"; the whole-tree cadence is unchanged
- [ ] Document `--scope` in `docs/reference/cli.md` and `docs/guide/checker.md`, and in the project-setup spec's changed-files runner section as a dated amendment
- [ ] Delete the request's entry from `claude/skills/auditme/requests.md`

**Acceptance Criteria:**

- [ ] The new tests fail before the change and pass after it
- [ ] `python3 claude/skills/auditme/checks/changed.py --scope --base HEAD~1` on this repository prints valid JSON lines

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/test_changed.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/changed.py`, `claude/skills/auditme/SKILL.md`, `agents/specs/project-setup/spec.md`

---

## Task 6: Put a re-planned candidate's earlier verdict in its batch

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Source Reference:** request "Show a re-judged candidate's earlier verdict to its reviewer" (review-5 D3)

**Technical Goal:** a reviewer re-judging a candidate sees the earlier
verdict, and a reviewer whose verdict differs says why.

**Subtasks:**

- [ ] Write the failing test first, in `claude/skills/auditme/tests/phaseb/test_batches.py`: a candidate re-planned because its hash changed carries `earlier` (`findings`, `reason`, `brief_version`, `judged`) in its batch line; a candidate new to the ledger carries no `earlier`
- [ ] In `claude/skills/auditme/checks/auditme/phaseb/batches.py` (`plan_batches` / `write_plan`), add `earlier` from the ledger to each re-planned candidate's line; keep `phaseb.py check` and `merge` ignoring it
- [ ] In every brief under `claude/skills/auditme/phaseb/briefs/`, add to the Input section: `earlier`, when present, is the verdict this candidate last had; if your verdict differs, say in `reason` what changed your judgement. Bump every brief's `**Brief version:**` by one, and update `claude/skills/auditme/tests/phaseb/test_briefs.py`
- [ ] Amend `agents/specs/repeatable-phase-b/spec.md` (the batch line and the briefs), dated, citing review-5
- [ ] Delete the request's entry from `claude/skills/auditme/requests.md`

**Acceptance Criteria:**

- [ ] The new test fails before the change and passes after it
- [ ] Every brief names `earlier`, and `test_briefs.py` passes with the new versions

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Every brief's version goes up, so review-6 judges every listed candidate again once; that is expected
- Key files: `claude/skills/auditme/checks/auditme/phaseb/batches.py`, `claude/skills/auditme/phaseb/briefs/*.md`

---

## Task 7: Run the whole-tree checks, the doc listers, and update the summary

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** all

**Technical Goal:** the branch passes every whole-tree check before it
merges, its docs and specs still match the code it changed, and the audit
summary records what this list resolved.

**Subtasks:**

- [ ] Run `python3 claude/skills/auditme/checks/phaseb.py candidates . --question Doc4` and `--question Doc5`, take the candidates whose `path` is a doc or spec this list changed (`git diff --name-only <base>...HEAD -- docs agents/specs README.md`), and check each one's statements against the code by hand; fix any statement that no longer matches. Record what was checked in the task's Notes
- [ ] In `agents/audit-reviews/summary.md`, move each finding Tasks 1 to 3 fixed to Recently resolved, naming its task, and add a dated line under "Checker changes since the last review" for each of Tasks 4 to 6
- [ ] Confirm `claude/skills/auditme/requests.md`'s Open section is empty

**Acceptance Criteria:**

- [ ] The Unresolved table holds only findings that did not ship, each with its reason
- [ ] `requests.md`'s Open section is empty

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `pre-commit run --all-files` passes
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` passes (the pre-push whole-tree audit)
- [ ] `uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes (`core.py`, the listers and the briefs changed, and every checker test reaches them)
- [ ] `uv run mkdocs build --strict` exits 0

**Notes:**

- Depends on Tasks 1 to 6

---
