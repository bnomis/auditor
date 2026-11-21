# Tasks: Repeatable Phase B

**Spec:** `agents/specs/repeatable-phase-b/spec.md`
**Created:** 2026-11-20
**Version:** 1

Implements the whole spec, version 1.1: the shared call resolver, the
`phaseb` package (candidates, ledger, batches), its command line, the A4
brief, and the `SKILL.md` changes that put listed questions into Phase B.

No check is added to or removed from `CHECKS`, so
`claude/skills/auditme/checks/auditme/registry.py` and
`claude/skills/auditme/tests/registry-order.txt` stay as they are. No rule's
output changes: the resolver's `Class.method()` resolution is off by default
and only the A4 lister turns it on (amendment 1.1). Every existing test in a
touched test file must pass unchanged; a task that needs to change one stops
as `blocked` and names it.

Every task runs unattended: none calls an LLM, makes a network request or
reads another repository. Running the listed path on a real project is the
operator's step after the list ships, not a task here.

The repository has no affected-tests tool. Each task names its own test
files; the last task runs every test tree the change can reach. Test commands
run from the repository root. Tests use neutral fixture names (`pkg`,
`ProbeError`, `Probe`), as the shared repository's `no-project-names` hook
requires.

---

## Task 1: Hoist the call resolver into `core.py` with a `class_methods` flag

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Module location (the shared resolver, amendment 1.1)

**Technical Goal:** Move the call resolution inside `check_raises_section_drift`
(its inner `resolve`, the re-export alias table and the import bindings it
reads) to a module-level helper in `checks/auditme/core.py`, with a
`class_methods: bool = False` flag that, when set, also resolves
`<ClassName>.<method>(...)` for a class the package defines. The rule calls
it with the default, so its output does not change; Task 3's lister calls it
with `True`.

**Subtasks:**

- [x] Starting-point check: `grep -rnwE 'phaseb|PhaseBError|class_methods' claude/skills/auditme/checks` prints nothing; if it prints anything, stop as `blocked` and name what it found
- [x] Tests first in `claude/skills/auditme/tests/test_core.py`, under a new `# call resolver` heading, on `ast.parse` trees of a two-module fixture package `pkg`: a same-module call, a dotted call through an import, a call through a package `__init__.py` re-export, and a `self.method()` call each resolve to the defining function's dotted name; an attribute call on a local instance resolves to `None`; `Probe.load()` (a classmethod of a class `pkg` defines) resolves to `None` by default and to `pkg.mod.Probe.load` with `class_methods=True`, both when `Probe` is defined in the same module and when it is imported by name. Run them and see them fail
- [x] Add the helper to `claude/skills/auditme/checks/auditme/core.py` with a docstring that names the `class_methods` flag and why the rule leaves it off
- [x] Replace the inner `resolve`, the alias loop and their inputs in `check_raises_section_drift` (`claude/skills/auditme/checks/auditme/rules/error_handling.py`) with calls to the helper at its default

**Acceptance Criteria:**

- [x] The new tests pass
- [x] Every existing test in `claude/skills/auditme/tests/test_error_handling.py` passes unchanged
- [x] `check_raises_section_drift` passes no `class_methods` argument

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/test_error_handling.py -q -p no:cacheprovider` passes

**Notes:**

- Key code: `check_raises_section_drift` in `claude/skills/auditme/checks/auditme/rules/error_handling.py` (its `resolve` inner function, `aliases` and `_from_import_bindings`)
- `core.py` already holds the shared helpers the rule modules import; keep the helper's name free of a leading underscore

---

## Task 2: The `phaseb` package, its error and its data model

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** API (`Candidate`, `Verdict`, `register_question`, `list_candidates`); Error handling (`PhaseBError`)

**Technical Goal:** Create `claude/skills/auditme/checks/auditme/phaseb/` with
`PhaseBError`, the frozen `Candidate` and `Verdict` dataclasses (with
`Verdict.flagged`) and the question registry, so the later tasks have one
place to register a lister and its brief.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_model.py`: `Verdict.flagged` is true when any findings list is non-empty, false when all are empty, and false when `dismissed` is set; `register_question` records a lister and its brief path; `list_candidates` on an unregistered question raises `PhaseBError`; a registered lister's candidates come back sorted by id. Run them and see them fail
- [x] Add `phaseb/__init__.py` with `PhaseBError` and an `__all__`
- [x] Add the dataclasses with the spec's fields and docstrings, and `register_question`, `list_candidates` and a way to read a question's brief path, in `phaseb/candidates.py`; re-export the public names from `phaseb/__init__.py`

**Acceptance Criteria:**

- [x] The new tests pass
- [x] `Candidate` and `Verdict` are frozen and carry every field the spec's API lists

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1 (the starting-point check)
- Tests under `claude/skills/auditme/tests/phaseb/` pick up `claude/skills/auditme/tests/conftest.py` by directory; check how the existing tests put `checks/` on the import path and do the same

---

## Task 3: The A4 lister and the content hash

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation (A4 candidates; Content hash); Decisions D2

**Technical Goal:** Register the A4 lister: every function or method with a
Google-style `Raises:` section under the roots `audit.py` audits, minus D2's
abstract and protocol stubs, each with its section, its resolved callees to
`depth`, its unresolved calls, and a sha256 over its source and its callees'
source.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_a4_candidates.py`, on a fixture project with `src/pkg/`: a function with a `Raises:` section is a candidate with id `src/pkg/mod.py::name` and its lines; a method's id is `path::Class.method`; a function without one is not; each D2 stub shape (`...`, `pass`, a docstring alone, `raise NotImplementedError`) is not; a callee two calls deep appears in `callees` at depth 3 and not at depth 1; a `Probe.load()` call resolves into `callees`; a call on a local instance appears in `unresolved` with its `path:line` and source text; editing a callee's body changes the caller's hash, and editing an unrelated function does not; candidates come back in the same order and with the same hashes on a second call. Run them and see them fail
- [x] Implement the lister in `phaseb/candidates.py`, using Task 1's resolver with `class_methods=True` and the roots `audit.py` uses (`_audit_roots` and `_extra_roots` in `claude/skills/auditme/checks/auditme/core.py`, rather than repeating their logic)
- [x] Register it as `A4` with the brief path `claude/skills/auditme/phaseb/briefs/A4.md` (the file is written in Task 7; the lister does not read it)

**Acceptance Criteria:**

- [x] The new tests pass
- [x] The hash is computed exactly as the spec's Content hash section says: the candidate's source, then each listed callee's source in id order, NUL-separated

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 1 and 2
- The brief version is not part of the hash; Task 5 compares it beside the hash

---

## Task 4: The ledger: read, merge and dismiss

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** API (`read_ledger`, `merge_verdicts`); Error handling; Implementation (A review's findings); Decisions D3

**Technical Goal:** Implement `phaseb/ledger.py`: read a question's
`agents/audit-reviews/ledger/<question>.jsonl`, merge new verdicts into it
atomically, drop entries whose candidate has gone, keep a dismissal only
while the findings are unchanged, and record a dismissal.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_ledger.py`: a missing ledger reads as empty; a ledger with an unparseable line, or a line missing a `Verdict` field, raises `PhaseBError`, as does a path that is a directory; a merge writes the new verdicts and keeps current ones it was not given; a merge drops an entry whose id is not among the candidates; a new verdict with the same findings as a dismissed one keeps the dismissal, and one with different findings drops it; dismissing an id records `YYYY-MM-DD: <reason>` and makes `flagged` false; dismissing an id the ledger does not hold raises `PhaseBError`; a write that fails leaves the old ledger file intact. Run them and see them fail
- [x] Implement `read_ledger`, `merge_verdicts` (returning a `MergeResult` with the counts written, kept and dropped) and a `dismiss_verdict` function, writing through a temporary file in the same directory and `os.replace`
- [x] Write one verdict per line, sorted by id, so a ledger diff shows only the verdicts that changed

**Acceptance Criteria:**

- [x] The new tests pass
- [x] No code path treats a ledger that exists but cannot be read as empty

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 2

---

## Task 5: Planning batches and checking a run

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** API (`plan_batches`, `check_run`); Error handling (retries, not judged)

**Technical Goal:** Implement `phaseb/batches.py`: plan the candidates that
need a verdict into fixed batches, write them with a `plan.json`, and check a
run's output batch by batch, reporting each problem and the batches to retry.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_batches.py`: a candidate with a current verdict (same hash and brief version) is not planned; one with no verdict, a changed hash or an older brief version is; `rejudge=True` plans every candidate; batches keep id order and hold `size` candidates except the last; the written `plan.json` holds the question, brief path, brief version and each batch's ids; `check_run` reports a batch with no output file, an unparseable line, a missing id, a duplicate id and an unexpected id, each against its batch, lists exactly those batches to retry, and reports nothing for a complete run; `check_run` on a directory without `plan.json` raises `PhaseBError`. Run them and see them fail
- [x] Implement `plan_batches`, a writer for the batch files and `plan.json`, `check_run` and its `RunCheck` result, and a reader that turns a checked run's output into `Verdict` objects stamped with each candidate's hash, the plan's brief version and today's date

**Acceptance Criteria:**

- [x] The new tests pass
- [x] `check_run` raises nothing for a reviewer's malformed output; it reports it

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 2 and 4
- The retry count (two, each by a fresh reviewer) is the orchestrator's rule in `SKILL.md` (Task 8); `check_run` only reports which batches need one

---

## Task 6: The command line, `checks/phaseb.py`

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** API (command line); Settings; Error handling (exit codes)

**Technical Goal:** Add `claude/skills/auditme/checks/phaseb.py` beside
`audit.py`, with the subcommands `candidates`, `plan`, `check`, `merge`,
`report` and `dismiss` and the options `--question`, `--batch-size` (48),
`--depth` (3) and `--rejudge`, exiting 1 when `check` finds problems and 2 on
a `PhaseBError`, whose message goes to stderr.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_cli.py`, running the script as a subprocess on a fixture project: `candidates` prints one JSON line per candidate; `plan` writes batches and `plan.json` and prints how many candidates were planned and how many reused; `check` exits 0 on a complete run and 1 on one with a missing id, naming the batch; `merge` writes `agents/audit-reviews/ledger/A4.jsonl`, and a second `plan` with unchanged code plans nothing; `report` prints the open findings, split into new (judged in the last merge) and carried, and leaves out a dismissed one; `dismiss` records the reason; an unknown `--question` exits 2 with the message on stderr. Run them and see them fail
- [x] Implement the script with `argparse`, as a thin layer over the package
- [x] Mark the file executable, as `audit.py` is

**Acceptance Criteria:**

- [x] The new tests pass
- [x] Every option has the default the spec's Settings table gives

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 3, 4 and 5
- "New" in `report` needs the merge to record which ids it wrote; keep that in the ledger's verdicts (their `judged` date) rather than a second file

---

## Task 7: The A4 brief, version 1

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation (Briefs); Decisions D1

**Technical Goal:** Write `claude/skills/auditme/phaseb/briefs/A4.md` with
the A4 question verbatim from `SKILL.md`, every threshold the spec settles,
the input and output format, and `**Brief version:** 1`, and have `plan`
read the version from it.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_briefs.py`: every registered question's brief file exists and has exactly one `**Brief version:** N` line with N a positive integer; the A4 brief contains the A4 question text as it stands in `SKILL.md`; a brief without a version line makes `plan` raise `PhaseBError`. Run them and see them fail
- [x] Write the brief: the reviewer's input (a batch file of candidates with `raises`, `callees` and `unresolved`), the question, the thresholds (domain errors only; each class named separately, a base not covering a subclass; an error only from a callable passed in is not owed; D1, with the constant named in the reason; read every listed callee and every unresolved call), the output (one JSON line per candidate with `id`, `missing`, `extra`, `reason`, sorted names, every candidate present), and the rule that a threshold the brief does not settle is reported in the reply, not decided
- [x] Repeat the security rule every subagent brief carries: never list environment variables (`env`, `printenv`, `set`) or print an env file; to test that a variable is set, use `[ -n "${VAR:-}" ]` and print only yes or no
- [x] Have `plan` read the brief version from the registered brief and write it into `plan.json`

**Acceptance Criteria:**

- [x] The new tests pass
- [x] The brief names no project, path or review from the pilot

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 3 and 6
- D2's stubs never reach the reviewer, because the lister leaves them out (Task 3); the brief need not mention them

---

## Task 8: `SKILL.md`: listed questions in Phase B

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation (Skill changes; A review's findings)

**Technical Goal:** Update `claude/skills/auditme/SKILL.md` so an audit runs
a listed question through `phaseb.py` and every other question through the
per-question fan-out as now, marked `(sampled)`.

**Subtasks:**

- [x] In section 4, Interpretive review, add the listed-question path: `plan`, one reviewer per batch with the question's brief, `check`, up to two retries of a failing batch by fresh reviewers, `merge`, `report`; and name the questions with a lister (A4)
- [x] Say that a listed question's findings are its flagged ledger verdicts, new or carried; that a carried finding is not a regression and is never marked "missed by" a review; and that a finding the operator dismisses on the review page is recorded with `phaseb.py dismiss`
- [x] Say that every other question is sampled and marked `(sampled)` in the review, and that a new site in a sampled question is coverage, not drift
- [x] In the Convergence section, say the rule applies in full to listed questions
- [x] In the completion gate, add: every listed question has a current verdict for every candidate, or the review names each id not judged
- [x] Say that putting a question on the listed path (its lister, brief and tests) is a skill change made between audits, never during one
- [x] Add the `phaseb` tests to `claude/skills/auditme/tests/README.md`'s description of the test tree

**Acceptance Criteria:**

- [x] `SKILL.md` names `phaseb.py`'s subcommands with the paths Task 6 wrote
- [x] Nothing in `SKILL.md` names a project, path or review from the pilot

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --group docs mkdocs build --strict` passes

**Notes:**

- Depends on Tasks 6 and 7

---

## Task 9: Whole-tree checks, deduplication, and close the spec

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** whole spec

**Technical Goal:** Remove any duplication the new package introduced, run
every check the change can reach, and mark the spec implemented.

**Subtasks:**

- [x] Hoist anything the `phaseb` modules duplicate from the rule modules or `core.py` to a single owner: grep the tree for each literal collection, constant and one-line helper the new modules define (the `Raises:` section parser especially, which `error_handling.py` already has as `raises_section_names`), and import rather than copy. Choose the owner from the existing import graph; prefer a module the consumer already imports over adding a new edge
- [x] Run `python3 claude/skills/auditme/checks/phaseb.py candidates . --question A4` from the repository root and check it exits 0, and that each line it prints parses as JSON with the `id`, `hash` and `payload` keys (a repository with no audit root prints none)
- [x] Confirm `claude/skills/auditme/tests/registry-order.txt` is unchanged against the branch's base (`git diff <base> -- claude/skills/auditme/tests/registry-order.txt` prints nothing)
- [x] Set the spec's `**Status:**` to `implemented`

**Acceptance Criteria:**

- [x] No literal collection or helper is defined both in `phaseb/` and elsewhere under `claude/skills/auditme/checks/`
- [x] The spec's status is `implemented`

**Definition of Done:**

- [x] `pre-commit run --all-files` exits 0
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests claude/skills/project-setup/tests tests -q -p no:cacheprovider` passes
- [x] `uv run --group docs mkdocs build --strict` passes
- [x] The full test run is saved for the run order's merge gate, from the repository root of this worktree: `MAIN=$(git worktree list --porcelain | sed -n '1s/^worktree //p'); LOG="$MAIN/logs/rro/repeatable-phase-b/tasks-1/final-tests.log"; mkdir -p "$(dirname "$LOG")"; uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests claude/skills/project-setup/tests tests -q -p no:cacheprovider 2>&1 | tee "$LOG"; [ "${PIPESTATUS[0]}" -eq 0 ] && echo 'all selected test directories passed' | tee -a "$LOG"`, and the log ends with `all selected test directories passed`

**Notes:**

- Depends on Tasks 1-8
- The saved log is read by `/rro` (`agents/tasks/order-raises-resolution-and-listed-phase-b.md`), whose merge gate does not rerun the tests; the path is relative to the main checkout, the first entry of `git worktree list --porcelain`
- No `TODO.md` item in this repository tracks this work, so no item moves to `DONE.md`

---
