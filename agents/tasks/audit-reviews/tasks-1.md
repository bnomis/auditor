# Tasks: Audit review 1 findings

**Source:** `agents/audit-reviews/review-1.md`
**Created:** 2026-11-21
**Version:** 1

Implements the 18 findings approved on review-1's page (2026-11-21), with the
options chosen there for decisions D2, D4, D5 and D6. F2 and F16 were
dismissed and have no task. The three checker requests the review filed in
`claude/skills/auditme/requests.md` (the test index, D1's thresholds, D3's A9
refinement) are skill changes of their own and are not in this list.

Every task edits and commits only this repository.

The test command changes in Task 1. Before Task 1 is done it is
`uv run --no-project --with pytest pytest <files> -q -p no:cacheprovider`;
from Task 1 on it is `uv run pytest <files> -q -p no:cacheprovider`, which
every later task's Definition of Done uses.

---

## Task 1: Declare the test dependencies

**Status:** done
**Priority:** high
**Complexity:** small
**Source Reference:** F19, D5

**Technical Goal:** the tests import `pytest`, and the property tests of Task 11 need `hypothesis`; neither is declared, so the test runner is unpinned. Declare both so every run uses the same versions.

**Subtasks:**

- [x] Add `pytest` and `hypothesis` to the `dev` group in `pyproject.toml` with `uv add --dev pytest hypothesis`, so the lock picks the newest releases outside the `exclude-newer = "14 days"` window; record each pinned version and its release date in the commit body
- [x] Change the test command to `uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` in `AGENTS.md`, `README.md` and `.github/workflows/ci.yml`, and in any copy under `docs/` (`grep -rn 'with pytest' docs AGENTS.md README.md .github`)
- [x] Leave the checker itself standard-library only: no import of `hypothesis` outside a test file

**Acceptance Criteria:**

- [x] `uv run pytest claude/skills/auditme/tests/test_core.py -q -p no:cacheprovider` passes
- [x] `grep -rn 'with pytest' AGENTS.md README.md docs .github` prints nothing
- [x] `uv.lock` pins `pytest` and `hypothesis`

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/test_hooks_manifest.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `pyproject.toml`, `uv.lock`, `AGENTS.md`, `README.md`, `.github/workflows/ci.yml`
- `uv.lock` changes only through `uv add`, as the dependency rule requires; D5 approved the dependency

---

## Task 2: Fix the user guides, README and AGENTS.md

**Status:** done
**Priority:** high
**Complexity:** small
**Source Reference:** F7, F8

**User Story:** As a user of the checker, I want its guides to describe what it does now, so that I can rely on them.

**Subtasks:**

- [x] `docs/reference/cli.md:264`: the Stop hook runs a trusted auditor worktree's own `changed.py` when the project is one, else the installed one (read `claude/hooks/auditme-stop.sh`)
- [x] `docs/reference/cli.md:157`: the invalid-TOML message is `pyproject.toml: not valid TOML (<parse error>)`, as `audit.py` prints it (read `core.declared_roots` and the driver)
- [x] `docs/reference/cli.md:209`: say that an argument error goes to stderr (argparse's `parser.error`)
- [x] `docs/guide/checker.md:35`: the swept roots are the declared ones when `[tool.auditme]` declares any, and `--extra-root` replaces the extra roots
- [x] `docs/guide/checker.md:104`: an AGENTS.md row makes the layering check print no hit, rather than an accepted one (read `maybe_emit_layering`)
- [x] `docs/guide/checker.md:326-330`: name as project-level only the checks `registry.py` runs once (`PROJECT_CHECKS`); move the others to the per-root list
- [x] `docs/reference/skills.md:40`: the `/auditme` commit message is `docs(audit): add review-N`
- [x] `docs/reference/skills.md:59-60`: name the files `/auditme-project-setup new` asks before overwriting, as its `SKILL.md` lists them
- [x] `AGENTS.md:5`: the Stop hook runs at the end of a turn
- [x] `README.md:3`: list the published `no-project-names` hook beside `auditme-changed` and `auditme-all`
- [x] Search `docs/`, `README.md` and `AGENTS.md` for every other copy of each corrected statement and fix it too

**Acceptance Criteria:**

- [x] Each line above matches the code it describes, checked against the file named
- [x] `uv run --group docs mkdocs build --strict` exits 0, as the docs workflow builds it

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Depends on Task 1 only for the test command it documents
- The full list of sites, with the reviewers' reasons, is under Doc5 and Doc3 in `agents/audit-reviews/review-1.md`

---

## Task 3: Fix spec drift and the five spec-template gaps

**Status:** done
**Priority:** medium
**Complexity:** medium
**Source Reference:** F6, F20, D6

**Technical Goal:** the specs name helpers and settings that have since changed, and five template gaps remain once D6 dismissed the size and module-location gaps.

**Subtasks:**

- [x] Fix each Doc4 site listed in `agents/audit-reviews/review-1.md` (21): the renamed helpers (`reach_sites`, `handler_passes_on`, `extract_string_eq_var`, `corpus_definitions`), `check_ruff_version` in `PROJECT_CHECKS`, `check_run`'s raises, `PhaseBError`'s module, the `--batch-size` default, the `--depth` setting, `DocTarget`'s kinds, the hashing of a def, the raise chain's form and the overtaken brief-version lines; where a spec records history, add a dated amendment line rather than rewriting the record
- [x] `agents/specs/listed-phase-b-architecture-questions/spec.md:257` and `agents/specs/listed-phase-b-documentation-questions/spec.md:253`: give each setting a type and default in the Settings section
- [x] `agents/specs/project-setup/spec.md`: add a Settings section for its options (`--base`, `--all`, `--package`, `--extra-root`, the declared roots, the Stop hook opt-in)
- [x] `agents/specs/listed-phase-b-test-questions/spec.md:60` and `:298`: link `../listed-phase-b-architecture-questions/spec.md`

**Acceptance Criteria:**

- [x] Every Doc4 site in the review is fixed or carries an amendment line
- [x] The five template gaps are closed; the 14 dismissed ones are untouched

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)

**Notes:**

- Key files: `agents/specs/*/spec.md`
- The sites are listed under Doc4 and Spec review in `agents/audit-reviews/review-1.md`

---

## Task 4: Complete a Raises section and the missing annotations

**Status:** done
**Priority:** medium
**Complexity:** small
**Source Reference:** F9, F11

**Technical Goal:** `list_candidates` omits `RootsError`, and 14 annotations are missing in checker source.

**Subtasks:**

- [x] Add `RootsError` to the `Raises:` section of `list_candidates` in `claude/skills/auditme/checks/auditme/phaseb/candidates.py`
- [x] Annotate `**kwargs` in `core.emit` (`core.py:41`), `maybe_emit_layering` (`rules/imports_and_surfaces.py:465`) and the two nested `walk_non_nested` helpers (`rules/state_and_effects.py:377`, `:651`)

**Acceptance Criteria:**

- [x] `ruff check --select ANN claude/skills/auditme/checks` reports nothing outside test files

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/test_imports_and_surfaces.py claude/skills/auditme/tests/test_state_and_effects.py claude/skills/auditme/tests/phaseb/test_model.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1

---

## Task 5: Enforce type-only imports with ruff

**Status:** done
**Priority:** medium
**Complexity:** small
**Source Reference:** F12

**Technical Goal:** the coding standard asks for type-only imports under `TYPE_CHECKING`, and nothing enforces it. Make the commit hook enforce it, then fix the 23 hits.

**Subtasks:**

- [x] Select ruff's `TC` rules in `pyproject.toml`'s `[tool.ruff.lint]`
- [x] Run `ruff check --select TC` and fix every hit; keep `typing` itself imported where the guard needs it
- [x] Note the rule under the coding standards' enforcement in `AGENTS.md` if it lists the enforced ruff rules

**Acceptance Criteria:**

- [x] `ruff check` passes with `TC` selected
- [x] The S4 sites in `agents/audit-reviews/review-1.md` are all fixed

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest` passes on the own test file of every module whose imports changed, named in the commit body

**Notes:**

- Depends on Task 1

---

## Task 6: Report an unreadable file as a hit

**Status:** done
**Priority:** high
**Complexity:** medium
**Source Reference:** F1, D2

**User Story:** As a user of the commit gate, I want a file the checker cannot read to be reported by name, so that a vanished or unreadable file never hides a check's other hits.

**Subtasks:**

- [x] Add one reader to `claude/skills/auditme/checks/auditme/core.py` that returns a file's text, or nothing when it raises `OSError` or `UnicodeDecodeError`, and records the path
- [x] Use it at every `read_text` site listed under A1 and A2 in `agents/audit-reviews/review-1.md`, keeping each site's handling of `SyntaxError`
- [x] Have the driver (`checks/audit.py`) emit one `unreadable-file` hit per recorded path in the existing schema: `path` the file, `line` null, `evidence` the error text, `accepted: false`
- [x] Widen the `subprocess.run` handlers in `rules/project_hygiene.py` (`check_lockfile`, `check_ruff`, `check_ruff_version`) to `OSError`, keeping each one's existing report
- [x] Tests: a file removed between listing and reading gives one `unreadable-file` hit and the check's other hits in that root; a file with bad bytes gives the hit; a missing `uv` or `ruff` still gives today's report
- [x] Document the new hit in `claude/skills/auditme/SKILL.md` (beside `src-loose-module`) and in `docs/guide/checker.md`

**Acceptance Criteria:**

- [x] No `read_text` call in `claude/skills/auditme/checks/auditme/` remains outside the shared reader, except a site that already catches `OSError`
- [x] The new tests pass, and fail when the reader re-raises `OSError`

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/test_driver.py claude/skills/auditme/tests/test_project_hygiene.py claude/skills/auditme/tests/test_duplication.py claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/test_imports_and_surfaces.py claude/skills/auditme/tests/test_state_and_effects.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- A new hit kind changes the sweep's output; add it to the registry or driver without reordering `CHECKS` (SKILL.md: `CHECKS`'s order is the emission order)

---

## Task 7: Refuse a merge at a different depth from its plan

**Status:** todo
**Priority:** high
**Complexity:** small
**Source Reference:** F13

**Technical Goal:** `phaseb.py merge` re-lists candidates with its own `--depth`, which `plan.json` does not record, so a mismatch saves verdicts whose hashes match no candidate.

**Subtasks:**

- [ ] Record the depth in `plan.json` when `phaseb.py plan` writes it
- [ ] Make `phaseb.py merge` stop with a `PhaseBError` naming both depths when its `--depth` differs from the plan's, and how to proceed (re-plan, or merge with the plan's depth)
- [ ] Read a `plan.json` written before this change as depth 3, the current default, and say so in the docstring
- [ ] Tests: a matching depth merges; a different one is refused with both values named; an old plan without the field merges at the default
- [ ] Update `docs/reference/cli.md` and the repeatable Phase B spec's plan format

**Acceptance Criteria:**

- [ ] A merge at a different depth writes nothing to the ledger

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/phaseb/test_cli.py claude/skills/auditme/tests/phaseb/test_batches.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- Key files: `claude/skills/auditme/checks/phaseb.py`, `claude/skills/auditme/checks/auditme/phaseb/batches.py`

---

## Task 8: Contain arguments and declared roots

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** F17

**Technical Goal:** `dismiss --question` builds a ledger path unchecked, `--extra-root` and `--package` can leave the project, and an absolute declared root makes the overlap check raise `ValueError` instead of `RootsError`.

**Subtasks:**

- [ ] `phaseb.py`: reject a `--question` that is not a registered question, on every subcommand that takes one
- [ ] `audit.py`: require `--package` to name a directory directly under `src/` and `--extra-root` to resolve inside the project, exiting 2 with a message as other argument errors do
- [ ] `core.declared_roots`: refuse a root that resolves outside the project with a `RootsError`
- [ ] Tests for each refusal, and one that an absolute declared root gives `RootsError`
- [ ] Update `docs/reference/cli.md` for the new refusals

**Acceptance Criteria:**

- [ ] No argument or declared root can make the checker read or write outside the project and the ledger directory

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/test_roots.py claude/skills/auditme/tests/test_driver.py claude/skills/auditme/tests/phaseb/test_cli.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1

---

## Task 9: Declare each checker module's surface

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Source Reference:** F4, F10, D4

**Technical Goal:** `core.py`, the `rules/` modules and `auditme/__init__.py` declare no `__all__`, so every helper counts as public and needs a direct test. Declare each module's surface, so a helper outside it is private and its callers' tests cover it.

**Subtasks:**

- [ ] Give `core.py` and each module under `rules/` an `__all__` naming what other modules and test files use (grep every root for `<module>.<name>` and `from <module> import`)
- [ ] `phaseb/__init__.py`: drop `Candidate`, `Lister`, `MergeResult`, `TestRef`, `Verdict`, `architecture`, `build_test_map`, `question_kinds` and `register_question` from `__all__`, keep the `architecture` import for its registration, and import those names in tests from their submodules
- [ ] Run the T1 lister (`python3 claude/skills/auditme/checks/phaseb.py plan . --question T1 --out <scratch>`) and check, for each of the 68 T1 ids flagged in `agents/audit-reviews/ledger/T1.jsonl`, that it is now `private: true` or has a direct test; write a direct test for each that is neither
- [ ] Note in the commit body that the next audit re-judges T1 and A1 under the new privacy

**Acceptance Criteria:**

- [ ] Every one of the 68 flagged T1 ids is private by the `all` rule or has a direct test
- [ ] No name in a package `__init__.py`'s `__all__` lacks a non-test consumer

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests -q -p no:cacheprovider` passes (every test of `core.py` and the rule modules, which the whole directory imports)

**Notes:**

- Depends on Task 1
- The module `__all__` lists are not `__init__.py` files, so A17 does not apply to them; test-used names may stay in them
- The test index cannot yet see this repository's tests (the request filed in `claude/skills/auditme/requests.md`), so the lister's `tests` lists stay empty: decide coverage from the test files

---

## Task 10: End-to-end tests for the Stop hook and the installer

**Status:** todo
**Priority:** low
**Complexity:** small
**Source Reference:** F18

**Technical Goal:** the hook's tests always substitute a fake `changed.py`, and the installer's a fake `uvx`; neither is run for real.

**Subtasks:**

- [ ] `tests/test_stop_hook.py`: one test that runs `claude/hooks/auditme-stop.sh` with the real `changed.py` on a temporary repository with one unaccepted hit, and one with none
- [ ] `tests/test_install_claude.py`: one test that runs `bin/install-claude.sh` against a temporary `HOME` and checks the links and the registered hook, with no network (skip with a reason when a tool it needs is absent)

**Acceptance Criteria:**

- [ ] Each test fails when the script's real call is broken (check by breaking it once locally)

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest tests/test_stop_hook.py tests/test_install_claude.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1

---

## Task 11: Property tests for the pure helpers

**Status:** todo
**Priority:** low
**Complexity:** medium
**Source Reference:** F5, D5

**Technical Goal:** each of the 23 T2 candidates has a well-defined domain and no property test.

**Subtasks:**

- [ ] For each T2 id flagged in `agents/audit-reviews/ledger/T2.jsonl`, write a hypothesis test of a property its domain supports (a round trip, an invariant, an idempotence), in the module's own test file
- [ ] Use `@settings(max_examples=20, deadline=10000)` on every one, as the testing rule requires

**Acceptance Criteria:**

- [ ] Every flagged T2 id has a test decorated with `given`

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest` passes on every test file the task edits, named in the commit body

**Notes:**

- Depends on Task 1 (hypothesis) and Task 9 (the test files' imports)

---

## Task 12: Name I/O honestly and build each shape once

**Status:** todo
**Priority:** low
**Complexity:** medium
**Source Reference:** F3, F14

**Technical Goal:** 11 pure-named functions read files or run git, and several shapes are built by hand in more than one place.

**Subtasks:**

- [ ] Rename each A9 function outside the registry listed in `agents/audit-reviews/review-1.md` (`resolve_base`, `is_private`, `parse_audited_files`, `check_batch`, `check_run`, `resolve_path`, `parse_file`, `parse_test_tree`, `build_index`, `build_test_map`, `parse_package_layering`) to a name that says it reads, or a `load_` name where A9's exemption applies; update every caller, test, spec and doc that names it
- [ ] Build `CorpusIndex` complete in `phaseb/docrefs.py` rather than setting `aliases` after construction
- [ ] One factory each for `Site` (`phaseb/testmap.py`, `phaseb/candidates.py`), the site-to-`Candidate` and section-to-`Candidate` construction (`phaseb/candidates.py`) and `DocTarget` (`phaseb/docrefs.py`)
- [ ] `phaseb/architecture.py:820`: document in the lister's docstring that an A17 candidate is one `__init__.py`, so its id is the file's path; leave the id form unchanged so existing ledger ids stay valid

**Acceptance Criteria:**

- [ ] No `phaseb.py` subcommand or ledger id changes as a side effect

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests -q -p no:cacheprovider` passes (the renames reach most test files)

**Notes:**

- Depends on Task 9 (the `__all__` lists name these functions)
- A rename of `is_private` or `build_test_map` changes a public name: grep `docs/`, `agents/specs/` and `claude/skills/` for each old name

---

## Task 13: Cut repeated work in the sweep, then run the whole-tree checks

**Status:** todo
**Priority:** low
**Complexity:** medium
**Source Reference:** F15

**Technical Goal:** each check re-reads every file, corpus indexes are rebuilt per root, `privacy` re-reads files on every call, a full LCS runs before the cheap length test, and the test index rebuilds the reverse call graph per site. Measure, fix, measure again.

**Subtasks:**

- [ ] Time `python3 claude/skills/auditme/checks/audit.py .` on this repository three times and record the median with the commit in the commit body
- [ ] Add a per-run parse cache in `core.py` (path to text and tree), cleared at the start of each `audit.py` run, and use it from `source_lines` and the shared reader of Task 6
- [ ] Build the corpus-wide indexes in `rules/state_and_effects.py` and `rules/project_hygiene.py` once per run, not once per root
- [ ] Memoise `audit_roots` and `all_names` for the life of one listing
- [ ] Run the length-ratio test before the LCS in `rules/duplication.py:611`
- [ ] Build the reverse call graph once in `phaseb/testmap.py`
- [ ] Time the sweep again and record both medians; confirm the JSONL output is byte-identical before and after (`diff`)

**Acceptance Criteria:**

- [ ] The sweep's output is unchanged, byte for byte
- [ ] The commit body records the run time before and after

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `pre-commit run --all-files` passes
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` passes (the pre-push whole-tree audit)
- [ ] `uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes (every module this list changed is `core.py` or reaches it, so every test file imports a changed module)

**Notes:**

- Depends on Task 6 (the shared reader) and Task 12 (the renamed functions)
- Last task of the list: it runs the whole-tree lint, the pre-push audit and every affected test once, before the branch merges
- Update `agents/audit-reviews/summary.md`: move each finding this list fixed to Recently resolved, as the auditme skill's step 8b asks

---
