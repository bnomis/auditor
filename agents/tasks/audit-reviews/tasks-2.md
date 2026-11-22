# Tasks: Audit review 2

**Source:** `agents/audit-reviews/review-2.md`
**Created:** 2026-11-22
**Version:** 2

Fixes the findings the operator approved on review-2's page on 2026-11-22:
F1 and F3 to F14 ("Fix"), with D2 ("Report it as a hit") for F3. F2 was
dismissed, and is recorded in the A1 ledger. D1 filed a request in
`claude/skills/auditme/requests.md`; that request is not part of this list.
The answers are in review-2's Answers section.

Every task's Definition of Done names the tests for the modules it changes.
The last task runs the whole-tree checks once, before the branch merges.

---

## Task 1: Make the no-project-names hook fail on a match beside an unreadable file

**Status:** done
**Priority:** high
**Complexity:** small
**Source Reference:** F8

**Technical Goal:** `bin/check-foreign-names.sh` exits 1 whenever a file
names a project, whatever else grep reports, so a commit that names one
cannot pass because another file is unreadable.

**Subtasks:**

- [x] Write the failing test first, in `tests/test_check_foreign_names.py`: a matching file passed with a missing one makes the script exit 1 and print the match; a missing file alone exits 2 with a message on stderr
- [x] In `bin/check-foreign-names.sh`, capture grep's exit status rather than testing it in the `if`. Exit 1 when it is 0, and exit 2 with a message naming the unreadable file when it is 2. When grep printed a match and also returned 2, exit 1, after the message
- [x] Update `docs/reference/cli.md` (the `bin/check-foreign-names.sh` section, line 84) with the exit codes

**Acceptance Criteria:**

- [x] The new tests fail before the change and pass after it
- [x] The existing tests in `tests/test_check_foreign_names.py` and `tests/test_published_hooks.py` pass unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests/test_check_foreign_names.py tests/test_published_hooks.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `bin/check-foreign-names.sh`, `tests/test_check_foreign_names.py`, `docs/reference/cli.md`

---

## Task 2: Pass --depth only to listers that take it, and refuse a bad one

**Status:** done
**Priority:** high
**Complexity:** small
**Source Reference:** F6, F13

**Technical Goal:** `phaseb.py` never crashes on `--depth`. It passes the
depth only to the A4, T1 and T2 listers, as
`agents/specs/listed-phase-b-architecture-questions/spec.md:271` says. It
refuses `--depth` for any other question, and any value below 1, with a
usage error.

**Subtasks:**

- [x] Write the failing tests first, in `claude/skills/auditme/tests/phaseb/test_cli.py`:
  - `phaseb.py candidates <probe> --question A11 --depth 3` exits 2 with a usage error naming the questions that take a depth;
  - `--depth 0` and `--depth -1` exit 2;
  - `--question A4 --depth 2` still lists, as before;
  - `plan` behaves the same as `candidates`
- [x] In `claude/skills/auditme/checks/auditme/phaseb/candidates.py`, `list_candidates` passes `depth` only to a lister registered as taking one; record that in the registry entry rather than inspecting the lister's signature
- [x] In `claude/skills/auditme/checks/phaseb.py`, give `--depth` a type that refuses a value below 1, and refuse it for a question whose lister takes no depth
- [x] F13: add the trailing comma to each argparse call in `claude/skills/auditme/checks/phaseb.py` (lines 70, 72, 73, 77, 78, 99, 100, 102, 103, 106, 108, 109, 113, 114 and 116 on 2026-11-22), so `ruff format` puts one argument per line, as `~/.claude/rules/python/argparse.md` asks
- [x] Update `docs/reference/cli.md`'s `phaseb.py` section with the `--depth` rule

**Acceptance Criteria:**

- [x] The new tests fail before the change and pass after it
- [x] No argparse call in `phaseb.py` takes more than one argument on one line

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/phaseb/test_cli.py claude/skills/auditme/tests/phaseb/test_a4_candidates.py claude/skills/auditme/tests/phaseb/test_t1_candidates.py claude/skills/auditme/tests/phaseb/test_t2_candidates.py claude/skills/auditme/tests/phaseb/test_model.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/phaseb/candidates.py` (`list_candidates`, `register_question`, `REGISTRY`), `claude/skills/auditme/checks/phaseb.py`

---

## Task 3: Report a missing uv or ruff as a hit

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** F3, D2

**Technical Goal:** as D2 decided, `check_lockfile` and `check_ruff_version`
emit a hit naming the missing tool when `uv` or `ruff` cannot run, as
`check_ruff` already does, rather than returning silently.

**Subtasks:**

- [ ] Write the failing tests first, in `claude/skills/auditme/tests/test_project_hygiene.py`:
  - a project with `pyproject.toml` and `uv.lock`, and no `uv` on `PATH`, gets one `lockfile` hit whose variant names `uv`;
  - a project with a `ruff-pre-commit` rev and no ruff to run gets one `ruff-version-drift` hit whose variant says ruff could not run
- [ ] In `claude/skills/auditme/checks/auditme/rules/project_hygiene.py`, replace each `except OSError: return` in `check_lockfile` and `check_ruff_version` with an emitted hit. Use the rule's own name, a variant naming the tool and the error, and the path and line the rule already reports at
- [ ] Say in each function's docstring that a tool that cannot run is reported as a hit
- [ ] Update `docs/guide/checker.md:327-330`, which says the checks are silent with no ruff and with no `uv`, and the `changed.py` advice for `lockfile-drift` hits in `docs/reference/cli.md` if it names the case

**Acceptance Criteria:**

- [ ] The new tests fail before the change and pass after it
- [ ] With `uv` and `ruff` present, the sweep of this repository reports the same hits as before

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/test_project_hygiene.py claude/skills/auditme/tests/test_driver.py -q -p no:cacheprovider` passes

**Notes:**

- The A1 verdict on these calls stays flagged until the D1 request settles whether an emitted hit is translation; that request is not this list's work
- Key files: `claude/skills/auditme/checks/auditme/rules/project_hygiene.py`

---

## Task 4: Translate the A17 lister's read and export what phaseb.py reads

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** F1, F4

**Technical Goal:** the A17 lister reports an unreadable `__init__.py` as
`PhaseBError`, and `phaseb.py` reads only `auditme.phaseb`'s public surface.

**Subtasks:**

- [ ] Write the failing test first, in `claude/skills/auditme/tests/phaseb/test_architecture_candidates.py`: an `__init__.py` that is not valid UTF-8 makes the A17 lister raise `PhaseBError` naming the file
- [ ] In `claude/skills/auditme/checks/auditme/phaseb/architecture.py`, make `list_a17_candidates.read_entries` read through `auditme.phaseb.candidates.read_text` (the translating reader); add `PhaseBError` to `list_a17_candidates`' `Raises:` if it is not there
- [ ] Export from `claude/skills/auditme/checks/auditme/phaseb/__init__.py` what `phaseb.py` needs: `DEFAULT_DEPTH`, and a function that returns the registered question names (for example `registered_questions()`). Keep `__all__` in the order `non-alphabetical-literal` accepts
- [ ] In `claude/skills/auditme/checks/phaseb.py`, read those names instead of `auditme.phaseb.candidates.REGISTRY` and `auditme.phaseb.candidates.DEFAULT_DEPTH`

**Acceptance Criteria:**

- [ ] The new test fails before the change and passes after it
- [ ] `grep -n 'auditme.phaseb.candidates' claude/skills/auditme/checks/phaseb.py` prints nothing

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/phaseb/test_architecture_candidates.py claude/skills/auditme/tests/phaseb/test_cli.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 2, which also edits `phaseb.py`
- Key files: `claude/skills/auditme/checks/auditme/phaseb/architecture.py`, `claude/skills/auditme/checks/auditme/phaseb/__init__.py`, `claude/skills/auditme/checks/phaseb.py`

---

## Task 5: Name the file readers after what they do, and build Candidate once

**Status:** todo
**Priority:** low
**Complexity:** medium
**Source Reference:** F10, F11

**Technical Goal:** no pure-named function reads files (A9), and the
listers build `Candidate` through one helper (A13, A15), as review-1's Task
12 did for the earlier functions of each kind.

**Subtasks:**

- [ ] Starting-point check: `grep -rnwE 'read_and_parse|index_reads|index_definitions|index_frozen_classes|span_candidate' claude/skills/auditme/checks` prints nothing. If it prints a line, stop as `blocked` and name the clash
- [ ] Rename these, and update every caller and test, and every doc and spec that names them as current code:
  - `auditme.core.parse_source` to `read_and_parse`;
  - `build_reads` to `index_reads`;
  - `build_definitions` to `index_definitions`;
  - `auditme.rules.state_and_effects.build_frozen_by_name` to `index_frozen_classes`.
  Take the full list from `grep -rnw` over `claude/`, `docs/` and `agents/specs/`, and leave dated records unchanged
- [ ] Add a helper beside `candidates.site_candidate` that builds a `Candidate` from a file, a node or a span, an id and the hash parts, and use it at the four inline sites in `claude/skills/auditme/checks/auditme/phaseb/architecture.py` (`:306`, `:398`, `:698` and `:824` on 2026-11-22)
- [ ] Document in `Candidate.id`'s comment the path-only id the A17 lister uses
- [ ] Confirm the candidate ids and hashes are unchanged: run `python3 claude/skills/auditme/checks/phaseb.py candidates . --question <Q>` for A1, A11, A17 and A19 before and after, and diff the output

**Acceptance Criteria:**

- [ ] The before-and-after candidate listings are identical
- [ ] `grep -rnwE 'parse_source|build_reads|build_definitions|build_frozen_by_name' claude/ docs/` prints nothing, except in dated records

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests -q -p no:cacheprovider` passes (the renamed functions are in `core.py`, which every test module reaches)

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/core.py`, `claude/skills/auditme/checks/auditme/rules/state_and_effects.py`, `claude/skills/auditme/checks/auditme/phaseb/architecture.py`, `claude/skills/auditme/checks/auditme/phaseb/candidates.py`

---

## Task 6: Resolve the roots once per run, and run the spec check once

**Status:** todo
**Priority:** low
**Complexity:** medium
**Source Reference:** F12

**Technical Goal:** one sweep or one Phase B listing reads `[tool.auditme]`
once, and `check_spec_api_signature_drift` runs once per sweep, not once per
root.

**Subtasks:**

- [ ] In `claude/skills/auditme/checks/auditme/phaseb/testmap.py`, resolve `audit_roots` once in `load_test_index` and pass the roots to `source_sites`, `read_test_tree` and `test_tree_roots`, instead of each calling it again
- [ ] In `claude/skills/auditme/checks/auditme/core.py`, make `corpus_index` take the corpus file list from the per-run cache instead of calling `corpus_py_files` on every lookup; clear it where the driver clears the parse cache
- [ ] Move `check_spec_api_signature_drift` from `CHECKS` to `PROJECT_CHECKS` in `claude/skills/auditme/checks/auditme/registry.py`, adjusting its signature if `PROJECT_CHECKS` entries take a different one; this changes the emission order, so record it under "Checker changes since the last review" in `agents/audit-reviews/summary.md`
- [ ] Add a test in `claude/skills/auditme/tests/test_registry.py` that `check_spec_api_signature_drift` is a project-level check, and one in `claude/skills/auditme/tests/test_core.py` that a corpus index lookup does not list the corpus again within a run
- [ ] Compare the sweep of this repository before and after: the same hits, possibly in a different order

**Acceptance Criteria:**

- [ ] `python3 claude/skills/auditme/checks/audit.py . | sort` is identical before and after
- [ ] The new tests pass

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests -q -p no:cacheprovider` passes (`core.py` and the registry are reached by every test module)

**Notes:**

- Depends on Task 5, which also edits `core.py`
- `claude/skills/auditme/tests/registry-order.txt` records the emission order and `test_registry.py` checks it; update it for the move. The spec check's own tests are in `claude/skills/auditme/tests/test_nested_underscore_and_spec_signatures.py`

---

## Task 7: Add the two missing tests

**Status:** todo
**Priority:** low
**Complexity:** small
**Source Reference:** F5

**Technical Goal:** `core.corpus_index` has a direct test, and
`phaseb.registered_question` has a property test.

**Subtasks:**

- [ ] In `claude/skills/auditme/tests/test_core.py`, test `corpus_index` directly: it builds each kind of index once per run, and rebuilds it after a corpus file changes or a file is added
- [ ] In `claude/skills/auditme/tests/phaseb/test_cli.py`, add a hypothesis test, `@settings(max_examples=20, deadline=10000)`, over arbitrary strings: `registered_question` returns its input unchanged exactly when it is a registered question, and raises `argparse.ArgumentTypeError` otherwise

**Acceptance Criteria:**

- [ ] Both tests pass
- [ ] `python3 claude/skills/auditme/checks/phaseb.py candidates . --question T1` lists a `direct` test for `core.py::corpus_index`

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/phaseb/test_cli.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 4 and 6, which change `registered_question`'s source and `corpus_index`

---

## Task 8: Correct the specs

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** F7, F14

**Technical Goal:** every statement F7 lists says what the code does now,
or is worded as the record of its spec's change, and the test-questions spec's
`--question` setting has its type and default.

**Subtasks:**

- [ ] Correct each site F7 lists in `agents/audit-reviews/review-2.md`:
  - `listed-phase-b-architecture-questions/spec.md:19` and `listed-phase-b-test-questions/spec.md:17`: reword "every question but A4 is still sampled" and "only A4 is listed" as the state when the spec was written;
  - `listed-phase-b-architecture-questions/spec.md:213` and `listed-phase-b-documentation-questions/spec.md:177-179`: say "version 1 when written", or point at `grep -n 'Brief version' claude/skills/auditme/phaseb/briefs/*.md`;
  - `listed-phase-b-documentation-questions/spec.md:104-105`: say what the code does with `.pre-commit-config.yaml`, which it reads by regex and does not parse;
  - `project-setup/spec.md:260`: give the message `pyproject.toml: not valid TOML (<the parser's message>)`;
  - `project-setup/spec.md:752`: give the current ruff pin, `v0.17.4`, or reword it as the pin at the time;
  - `repeatable-phase-b/spec.md:157` and `:170`: add `RootsError` to `list_candidates`' `Raises:`, and `PhaseBError` (size below 1) to `plan_batches`.
- [ ] Confirm after Task 2 that `listed-phase-b-architecture-questions/spec.md:271` matches the code; reword it only if the code now differs
- [ ] F14: in `listed-phase-b-test-questions/spec.md:308`, give `--question` as `str`, required, with no default
- [ ] Line numbers are from 2026-11-22; find each statement by its text

**Acceptance Criteria:**

- [ ] Each F7 statement is corrected or reworded as a record

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)

**Notes:**

- Depends on Task 2 (F6's spec line)
- Key files: the five specs under `agents/specs/` named above

---

## Task 9: Correct the user docs and give every check a docstring

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Source Reference:** F9

**User Story:** As a user of the checker, I want its guides to say what it
does, so that I can rely on their exit codes, failure lists and rules.

**Subtasks:**

- [ ] Correct each site F9 lists in `agents/audit-reviews/review-2.md`, in `docs/concepts.md`, `docs/guide/checker.md`, `docs/reference/cli.md`, `docs/reference/skills.md` and `docs/setup.md`, checking each against the code as it stands after Tasks 1 to 6
- [ ] Add a docstring stating the predicate and its carve-outs to each of these checks, so `docs/guide/checker.md:191-193` holds: `check_paired_sibling_helpers`, `check_silent_broad_except`, `check_def_class_in_init`, `check_unused_submodule_imports`, `check_ruff`, `check_lockfile`, `check_duplicated_word`
- [ ] Make every list of exit or failure conditions complete; where a list is only examples, write "for example"
- [ ] Run `uv run mkdocs build --strict`

**Acceptance Criteria:**

- [ ] Each F9 statement is corrected
- [ ] Every registered check has a docstring: `python3 -c` over `auditme.registry.CHECKS + PROJECT_CHECKS` finds no function whose `__doc__` is empty
- [ ] `uv run mkdocs build --strict` exits 0

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/test_registry.py claude/skills/auditme/tests/test_project_hygiene.py claude/skills/auditme/tests/test_style_and_naming.py claude/skills/auditme/tests/test_duplication.py claude/skills/auditme/tests/test_imports_and_surfaces.py claude/skills/auditme/tests/test_error_handling.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 1 to 6, whose behaviour the docs describe
- The docstrings live in `claude/skills/auditme/checks/auditme/rules/`; find each check's module with `grep -rn 'def <name>'`

---

## Task 10: Run the whole-tree checks and update the summary

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** all

**Technical Goal:** the branch passes every whole-tree check before it
merges, and the audit summary records what this list resolved.

**Subtasks:**

- [ ] In `agents/audit-reviews/summary.md`, move each finding Tasks 1 to 9 fixed from Unresolved to Recently resolved, naming the task that fixed it; leave any that did not ship, with the reason
- [ ] Under "Checker changes since the last review", add a dated line for each behaviour change: the hook's exit codes, the `--depth` rule, the missing-tool hits, the moved check's emission order and the renames

**Acceptance Criteria:**

- [ ] The Unresolved table holds only findings that did not ship, each with its reason

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `pre-commit run --all-files` passes
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` passes (the pre-push whole-tree audit)
- [ ] `uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes (`core.py`, changed in Tasks 5 and 6, is reached by every checker test, and Task 1 changes a script the top-level tests run)

**Notes:**

- Depends on Tasks 1 to 9

---
