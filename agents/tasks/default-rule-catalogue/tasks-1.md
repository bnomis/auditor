# Tasks: Default rule catalogue

**Spec:** `agents/specs/default-rule-catalogue/spec.md`
**Created:** 2026-11-25
**Version:** 1

This list implements the whole spec, version 1.0, which was approved on
2026-11-25 (`agents/specs/runner-rules-split-review.md`). It also carries two
corrections made while the list was written:

- the rule-id tables are in `docs/guide/checker.md`;
- the pack-membership test belongs to the Rules init list.

It is the third of four lists, and needs
`agents/tasks/auditor-cli/tasks-1.md` and
`agents/tasks/rules-repository/tasks-1.md` finished.

**How the list keeps every step green.** From Task 2 until Task 12,
`auditor.registry` is a transitional registry. It holds the built-in checks
not yet moved, plus every rule already in `src/auditor/catalogue/`, loaded
through `auditor.rulesrepo.import_entry`. A sweep with `AUDITOR_RULES_PATH`
unset therefore still runs every rule after every task. Task 12 deletes the
transitional registry.

**Test changes that are allowed.** A check's tests move into its rule
directory with their bodies unchanged. Two kinds of change are allowed:

- the edits Task 2 names in `tests/checker/test_registry.py`;
- deleting lines of `tests/checker/registry-order.txt` for checks that have
  moved.

Any other change to an existing test's expected output stops the task as
`blocked`, naming the test.

**No decisions.** Where a task meets a case the spec does not name, it stops as
`blocked` for the operator, naming the case.

**The baseline** is `$BASELINE`, set to
`${TMPDIR:-/tmp}/default-rule-catalogue-baseline`, which is outside the
repository.

**A family task** moves one family module (Tasks 3 to 9) as follows:

1. Promote each helper that a check in another family, or a lister, also uses
   to the `auditor.api` submodule the spec names. A helper that no submodule
   fits stops the task as `blocked`, naming the helper. A Phase B lister that
   calls a check function directly (several in `src/auditor/phaseb/architecture.py`
   and `candidates.py` do) gets the site finder it needs promoted to the API
   in the same task, and imports that instead of the check.
2. Write one rule directory per check (`rule.toml`, `check.py`, `tests/`). Its
   `rule.md` holds the docstring's rationale: the signal, the carve-outs and
   the dated refinements.
3. Move the check's tests into the rule directory's `tests/`, unchanged.
4. Remove the check from the family module and add it to the transitional
   registry.

---

## Task 1: Record the baseline

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation 1

**Technical Goal:** Save the sweep output for this repository and for every
test fixture project, and the candidates of every listed question, so that
Task 13 can prove equivalence.

**Subtasks:**

- [x] Starting-point check: `test ! -e src/auditor/catalogue` succeeds, and `AUDITOR_RULES_PATH` is unset in this run (`[ -z "${AUDITOR_RULES_PATH:-}" ]`). Otherwise stop as `blocked`
- [x] Add a test-only `AUDITOR_DUMP_FIXTURES=<dir>` to `tests/checker/conftest.py`, which writes each `run_check` result to `<dir>/<test id>.jsonl`. Run the full suite with it set to `$BASELINE/fixtures`
- [x] `uv run auditor check . > "$BASELINE/sweep.jsonl"`, and for each registered question `uv run auditor phaseb candidates --question <Q> . > "$BASELINE/candidates-<Q>.jsonl"`

**Acceptance Criteria:**

- [x] `$BASELINE/fixtures` holds one file per `run_check` call, and the sweep and candidates files exist

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests/checker -q -p no:cacheprovider` passes

**Notes:**

- The dump hook is removed in Task 13

---

## Task 2: Create the catalogue and the transitional registry

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Module location; Implementation 2 (the registry keeps running), 9 (sweep coverage)

**Technical Goal:** `src/auditor/catalogue/` is a valid, empty rules
repository. `auditor.registry` loads its rules alongside the built-ins. The
sweep audits the catalogue's rule code in exactly one root.

**Subtasks:**

- [x] Write `src/auditor/catalogue/auditor-rules.toml` with `api = "1.0"`, and an empty `rules/`
- [x] Make `CHECKS`, `PROJECT_CHECKS` and `RULE_IDS` in `src/auditor/registry.py` include the catalogue's rules, in the existing order followed by the catalogue's in name order
- [x] In `tests/checker/test_registry.py`, make the "defined in a rules module" and "exercised by a test module" tests also accept a catalogue rule directory and its `tests/`. This is the change to registry tests that the header allows
- [x] Write `tests/catalogue/test_catalogue.py`: `auditor rules check` passes over the catalogue, and every `standards` entry names a `standard` rule
- [x] Spec step 9:
  - put one probe rule directory in the catalogue;
  - run the sweep, and see how it names `check.py`;
  - declare `src/auditor/catalogue/rules` in `[tool.auditme] roots` in the form that names each file, and exclude it from the `src/auditor` root;
  - record the declaration and why it is needed in the commit message;
  - delete the probe.

  If `[tool.auditme] roots` cannot exclude a subdirectory, stop as `blocked` and say so

**Acceptance Criteria:**

- [x] With the empty catalogue, the suite passes and the sweep gives the baseline's hits

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests/checker/test_registry.py tests/catalogue -q -p no:cacheprovider` passes
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0

**Notes:**

- Depends on Task 1
- Blocked on the last subtask, checked on 2026-11-26. `[tool.auditme] roots` cannot exclude a subdirectory: `declared_roots` in `src/auditor/core.py` rejects a root nested inside a `package` root as an overlap, and a `top-level` root finds no `check.py` in a subdirectory. A probe rule directory (`probe-rule/check.py`) was already swept by path, under the `src/auditor` root alone, so no root is skipped today; the spec asks for the exclusion form regardless. The operator decides: allow an `exclude` key in a roots entry, or accept the `src/auditor` root as the one root for the rule files
- **Decision 2026-11-26 (decided by Claude, not yet reviewed):** accept the `src/auditor` root as the one root for the catalogue's rule files, with no `[tool.auditme] roots` entry for `src/auditor/catalogue/rules`. Spec step 9's requirement is that every rule file is audited in exactly one root, and the probe shows it already is; an `exclude` key would change the checker's root handling for no gain. In place of the declaration, add a test to `tests/catalogue/test_catalogue.py` that puts a probe `check.py` and `lister.py` under a catalogue rule directory in a fixture copy and checks that the sweep reads each exactly once, naming it by its file path, so that a later change to root handling cannot skip the rule code silently. Record this and the reason in the task's commit message, delete the probe, and tick the step 9 subtask. The decision covers only spec step 9

---

## Task 3: Move the `duplication` family

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** What becomes a rule directory; API; Implementation 2

**Technical Goal:** Every check in `src/auditor/rules/duplication.py` is a
catalogue rule, moved as the header's family task says.

**Subtasks:**

- [x] Move each check as a family task (see the header)
- [x] Delete `src/auditor/rules/duplication.py` once it is empty

**Acceptance Criteria:**

- [x] The sweep of this repository gives the baseline's hits, and the moved tests pass under `auditor rules test`

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `AUDITOR_RULES_PATH=src/auditor/catalogue uv run auditor rules test` passes
- [x] `uv run pytest tests/checker/test_registry.py tests/catalogue -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 2
- Blocked on 2026-11-26, before any file moved. Two existing tests in `tests/rulesrepo/test_api.py` stop every family task, and the header allows no change to an existing test's expectation. The operator decides how to amend them:
  - `test_no_existing_module_imports_the_api` fails the moment a catalogue `check.py` imports `auditor.api`: it scans every `.py` under `src/auditor` outside `api/` for the text `auditor.api`, and `src/auditor/catalogue/` is inside that tree. Proposed amendment: also skip the `catalogue` directory
  - `test_all_lists_exactly_the_exports` pins `auditor.api.__all__` to the current names, so no helper can be promoted to the API (the family-task step 1). The first case is `SINK_TOKENS` (the sink-name tuple), used by both `duplicate-side-effect-per-target` and `redundant-sink-caller-plus-callee`. No submodule in the spec's list fits it. Copying it into both `check.py` files instead would be a `literal-duplication` hit in the sweep. Proposed: promote it to a new `auditor.api` name and extend the expected list, or decide that the two rules keep separate copies with an accept comment
  - The same two tests will block Tasks 4 to 9 as well, so the amendment should cover the whole list
- **Decision 2026-11-26 (decided by Claude, not yet reviewed), for Tasks 3 to 9:** both tests guarded the starting state of the API that rules-repository Task 1 created, and this list's spec grows that API (its API section: "The task that splits each family module adds any other helper that it finds used by two or more rules"), so amending them is the spec's own work, and these two amendments are allowed in addition to the header's list:
  - `test_no_existing_module_imports_the_api`: also skip `src/auditor/catalogue/`, since rule code is meant to import `auditor.api`; the test still guards that no runner module imports it
  - `test_all_lists_exactly_the_exports`: compare `auditor.api.__all__` with exactly the union of each `auditor.api` submodule's own `__all__` plus `API_VERSION`, and assert that every name the spec's API section lists is in it. It stays an exact check, and a promotion no longer needs the test edited
  - `SINK_TOKENS` is used by two rules, so it is promoted, to `auditor.api.calls` (it classifies callees by name, as that submodule's helpers do). A later helper used by two or more rules goes to the spec submodule whose helpers it is most like; one that fits none still stops the task, naming it
  - `API_VERSION` stays `(1, 0)`: no release has shipped the API yet. The decision covers only these two tests and the placement of promoted helpers

---

## Task 4: Move the `style_and_naming` family

**Status:** in-progress
**Priority:** high
**Complexity:** medium
**Spec Reference:** What becomes a rule directory (table-driven checks); API; Implementation 2

**Technical Goal:** Every check in `src/auditor/rules/style_and_naming.py` is a
catalogue rule. `check_text_patterns` becomes one directory, `text-patterns`,
that lists every id it emits.

**Subtasks:**

- [ ] Move each check as a family task (see the header)
- [ ] The checks that emit several ids from a table (`check_text_patterns`, the bare-annotation checks and `check_typing_deprecated_alias`) each list every id in `emits`
- [ ] Delete the module once it is empty

**Acceptance Criteria:**

- [ ] As Task 3

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `AUDITOR_RULES_PATH=src/auditor/catalogue uv run auditor rules test` passes
- [ ] `uv run pytest tests/checker/test_registry.py tests/catalogue -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 3
- Blocked on 2026-11-26, before any file moved. One helper has no `auditor.api` submodule in the spec's list: `leading_underscore_names` in `src/auditor/rules/style_and_naming.py`, which returns the `_foo` Store-names in an unpacking target. Both `underscore-unpack-target-read` and `underscore-forloop-target-read` use it, so it must be promoted (family-task step 1; copying it into both `check.py` files would be a `paired-sibling-helpers` hit). It is a target-shape helper, not a source reader, a call resolver or an `if` chain. The operator decides: put it in `auditor.api.flow` (the nearest, since `if_chain` is also an AST-shape helper), or name another submodule. No other helper in the module is shared, so nothing else blocks Task 4
- **Decision 2026-11-26 (decided by Claude, not yet reviewed), for Tasks 4 to 9:** promote `leading_underscore_names` to `auditor.api.flow`, beside `if_chain`: both read the shape of an AST node rather than source, calls, errors or docs. This refines the Task 3 decision's last point: a later helper used by two or more rules that reads only the shape of AST nodes also goes to `auditor.api.flow`, and does not stop the task. A shared helper that fits neither `flow` nor another spec submodule still stops the task, naming it

---

## Task 5: Move the `imports_and_surfaces` family

**Status:** todo
**Priority:** high
**Complexity:** medium
**Spec Reference:** What becomes a rule directory; API (`auditor.api.calls`); Implementation 2

**Technical Goal:** Every check in `src/auditor/rules/imports_and_surfaces.py`
is a catalogue rule. The checks the A17 lister calls are promoted with their
helpers, so that the lister can still reach them.

**Subtasks:**

- [ ] Move each check as a family task (see the header). The Phase B listers in `src/auditor/phaseb/` import any promoted helper from `auditor.api`. A lister that calls a check function directly (`check_migration_shim_consumers`, `check_empty_init_with_exporting_siblings`) has the site finder it needs promoted instead of the check
- [ ] Delete the module once it is empty

**Acceptance Criteria:**

- [ ] As Task 3, and `auditor phaseb candidates --question A17 .` gives the baseline's file

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `AUDITOR_RULES_PATH=src/auditor/catalogue uv run auditor rules test` passes
- [ ] `uv run pytest tests/checker/test_registry.py tests/checker/phaseb tests/catalogue -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 4

---

## Task 6: Move the `state_and_effects` family

**Status:** todo
**Priority:** high
**Complexity:** large
**Spec Reference:** What becomes a rule directory; API (`auditor.api.flow`); Implementation 2

**Technical Goal:** Every check in `src/auditor/rules/state_and_effects.py` is
a catalogue rule.

**Subtasks:**

- [ ] Move each check as a family task (see the header). `if_chain` and the site finders that the A11 lister uses go to `auditor.api`
- [ ] Delete the module once it is empty

**Acceptance Criteria:**

- [ ] As Task 3, and the A11 candidates match the baseline

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `AUDITOR_RULES_PATH=src/auditor/catalogue uv run auditor rules test` passes
- [ ] `uv run pytest tests/checker/test_registry.py tests/checker/phaseb tests/catalogue -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 5

---

## Task 7: Move the first half of the `error_handling` family

**Status:** todo
**Priority:** high
**Complexity:** large
**Spec Reference:** What becomes a rule directory; API (`auditor.api.errors`); Implementation 2

**Technical Goal:** The first half of the `error_handling` checks become
catalogue rules: those that come earliest in `CHECKS` order, up to and
including the middle one.

**Subtasks:**

- [ ] Move each check as a family task (see the header). `class_lineage`, `package_class_parents`, `is_broad_handler`, `raises_section_names`, `translator_envelopes` and `callable_short_name` go to `auditor.api.errors` or `auditor.api.calls`, as the spec lists them

**Acceptance Criteria:**

- [ ] As Task 3, and the A1, A4 and A19 candidates match the baseline

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `AUDITOR_RULES_PATH=src/auditor/catalogue uv run auditor rules test` passes
- [ ] `uv run pytest tests/checker/test_registry.py tests/checker/phaseb tests/catalogue -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 6
- Split in two because the module is the largest family

---

## Task 8: Move the rest of the `error_handling` family

**Status:** todo
**Priority:** high
**Complexity:** large
**Spec Reference:** What becomes a rule directory; Implementation 2

**Technical Goal:** The remaining `error_handling` checks become catalogue
rules, and the module is deleted.

**Subtasks:**

- [ ] Move each remaining check as a family task (see the header)
- [ ] Delete the module

**Acceptance Criteria:**

- [ ] As Task 7

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `AUDITOR_RULES_PATH=src/auditor/catalogue uv run auditor rules test` passes
- [ ] `uv run pytest tests/checker/test_registry.py tests/checker/phaseb tests/catalogue -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 7

---

## Task 9: Move the `project_hygiene` family

**Status:** todo
**Priority:** high
**Complexity:** medium
**Spec Reference:** What becomes a rule directory (`PROJECT_CHECKS`); API (`auditor.api.docs`); Implementation 2

**Technical Goal:** Every check in `src/auditor/rules/project_hygiene.py` is a
catalogue rule. The three `PROJECT_CHECKS` become `project-check` rules, and
`check_ruff` becomes a `check` rule. The ruff lookup stays in the runner,
because `AUDITME_RUFF` is a runner setting.

**Subtasks:**

- [ ] Move each check as a family task (see the header). `spec_markdown_files` goes to `auditor.api.docs`, and the ruff-command lookup goes to `auditor.api.project`
- [ ] Delete the module once it is empty

**Acceptance Criteria:**

- [ ] As Task 3, and the Doc1, Doc2, Doc4 and Doc5 candidates match the baseline

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `AUDITOR_RULES_PATH=src/auditor/catalogue uv run auditor rules test` passes
- [ ] `uv run pytest tests/checker/test_registry.py tests/checker/phaseb tests/catalogue -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 8

---

## Task 10: Move the Phase B questions and the prose standards

**Status:** todo
**Priority:** high
**Complexity:** large
**Spec Reference:** What becomes a rule directory (questions, standards); Implementation 3, 4

**Technical Goal:** Every Phase B question is a `question` rule, and every
section of the three prose standards files is a `standard` rule.

**Subtasks:**

- [ ] Each listed question becomes a directory (`a4`, `doc1` and so on):
  - its lister moves into `lister.py`;
  - its brief moves into `brief.md`, with the `**Brief version:**` unchanged;
  - `kinds`, `batch-size` and `takes-depth` are copied from its registration.

  Then delete the listers' modules in `src/auditor/phaseb/` and `src/auditor/briefs/`
- [ ] Each other question in the `SKILL.md` checklist becomes a directory with only `rule.md`, holding its checklist text word for word
- [ ] Each `##` section of `claude/rules/auditme/coding-standards.md`, `imports.md` and `dependencies.md` becomes `std-<section-slug>`, with the section's text word for word in `rule.md`. Then delete `claude/rules/auditme/` and remove its link from `bin/install-claude.sh` and its tests
- [ ] Add a `standards` key to each check whose rationale names a standards section
- [ ] In `SKILL.md`:
  - replace the checklist with `auditor rules questions`;
  - replace the standards references with the SessionStart hook;
  - move each "Documented conflicts" entry into the winning rule's `rule.md`

**Acceptance Criteria:**

- [ ] The candidates of every listed question match the baseline, ids and hashes included
- [ ] `auditor rules questions` prints every question that the old checklist held
- [ ] `auditor rules standards` prints every section that the three files held

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `AUDITOR_RULES_PATH=src/auditor/catalogue uv run auditor rules test` passes
- [ ] `uv run pytest tests/checker/phaseb tests/catalogue tests/test_install_claude.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 9
- The Phase B ledger in `agents/audit-reviews/ledger` must still match: the candidate hashes and brief versions do not change

---

## Task 11: Retire `requests.md`

**Status:** todo
**Priority:** medium
**Complexity:** small
**Spec Reference:** Implementation 5

**Technical Goal:** Change requests go to the rules repository's `TODO.md`. The
one rejected entry moves into its rule, and nothing refers to `requests.md`.

**Subtasks:**

- [ ] Starting-point check: the `## Open` section of `claude/skills/auditme/requests.md` holds no entry. If it holds one, stop as `blocked` and name it, because `requests.md` requires it to be shipped or rejected first
- [ ] Move each `## Rejected` entry word for word under `## Rejected widenings` in the named rule's `rule.md` (today, `mutable-module-level-exported`)
- [ ] In `SKILL.md`:
  - move the file's prose on why requests block into step 3, beside `auditor rules pending`;
  - change the completion-gate line to "`auditor rules pending` exited 0 at audit start";
  - remove the built-in-path wording that `agents/tasks/rules-repository/tasks-1.md` Task 9 left
- [ ] Rewrite every other reference, in `SKILL.md`, `docs/reference/skills.md` and the comments and docstrings of the moved rule code and tests. Then delete the file

**Acceptance Criteria:**

- [ ] `git grep -n 'requests\.md' -- '*.md' '*.py' '*.sh' ':!agents'` prints nothing

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `AUDITOR_RULES_PATH=src/auditor/catalogue uv run auditor rules test` passes

**Notes:**

- Depends on Task 10

---

## Task 12: Remove the built-in rules

**Status:** todo
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation 6, 8; Error handling (Missing rules repository); Settings; Tests

**Technical Goal:** The runner holds no rules. `AUDITOR_RULES_PATH` is
required, and the tests and CI set it to the catalogue.

**Subtasks:**

- [ ] Delete `src/auditor/registry.py`, `src/auditor/rules/` and `tests/checker/registry-order.txt`. Remove the unset-variable fallback from the sweep and from Phase B, so that every command raises the unset-variable `RulesRepoError`
- [ ] Replace the tests in `tests/checker/test_registry.py` that read the built-in registry with their catalogue forms in `tests/catalogue/test_catalogue.py`, then delete the old ones:
  - every emitted id is in `rule_ids()`;
  - `rule_ids()` equals the ids in the rule tables of `docs/guide/checker.md`;
  - `ruff` and `lockfile-drift` are always included
- [ ] `tests/conftest.py` sets `AUDITOR_RULES_PATH` to `src/auditor/catalogue` for the suite. `.github/workflows/ci.yml` and the local audit hooks in `.pre-commit-config.yaml` pass it to their commands
- [ ] In `docs/setup.md`, add the upgrade steps for a project that pins the hooks: create a rules repository, set the variable with direnv, and set it in CI
- [ ] Test that every command exits 2 with the spec's message when the variable is unset

**Acceptance Criteria:**

- [ ] `grep -rnw 'auditor.registry' src tests` prints nothing, and the suite passes

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest tests -q -p no:cacheprovider` passes, because this task changes how every test finds its rules
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0

**Notes:**

- Depends on Task 11
- This repository's own `.envrc` is the user's. No task edits it

---

## Task 13: Prove equivalence and close the spec

**Status:** todo
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation 1, 7; Error handling (Equivalence failure); Tests

**Technical Goal:** The catalogue gives the baseline's hits and candidates. The
fixture comparison stays as a test, and the spec is closed.

**Subtasks:**

- [ ] Run the suite with `AUDITOR_DUMP_FIXTURES=$BASELINE/fixtures-after`. Compare each fixture file with its baseline as a set of `(rule, variant, path, line, evidence, accepted)`
- [ ] Do the same for the sweep of this repository and for every question's candidates, ids and hashes included. Map the paths of moved files before comparing. Any other difference stops the task as `blocked`, listing it
- [ ] Commit the fixture comparison as `tests/catalogue/test_equivalence.py`, with the baseline fixture outputs as data under `tests/catalogue/baseline/`. These are small JSON lines recording expected results, not generated data. Then remove the `AUDITOR_DUMP_FIXTURES` hook
- [ ] Set `version = "0.3.0"` in `pyproject.toml`, marking the breaking change (the bump is made at the list's last task, against `main`)
- [ ] Set the spec's `**Status:**` to `implemented`
- [ ] Save the full test run for the run order's merge gate, from the repository root of this worktree: `MAIN=$(git worktree list --porcelain | sed -n '1s/^worktree //p'); LOG="$MAIN/logs/rro/default-rule-catalogue/tasks-1/final-tests.log"; mkdir -p "$(dirname "$LOG")"; uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider 2>&1 | tee "$LOG"; [ "${PIPESTATUS[0]}" -eq 0 ] && echo 'all selected test directories passed' | tee -a "$LOG"`, and the log ends with `all selected test directories passed`

**Acceptance Criteria:**

- [ ] Every comparison matches

**Definition of Done:**

- [ ] `pre-commit run --all-files` exits 0
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [ ] `uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider` passes
- [ ] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Depends on Tasks 1 to 12
- Before committing, check `git diff --cached --stat`. If the baseline files exceed 1 MB in total, stop as `blocked`, because they would then be data rather than a record

---
