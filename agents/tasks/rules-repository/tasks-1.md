# Tasks: Rules repository

**Spec:** `agents/specs/rules-repository/spec.md`
**Created:** 2026-11-25
**Version:** 1

This list implements the whole spec, version 1.0, which was approved on
2026-11-25 (`agents/specs/runner-rules-split-review.md`, every item approved,
item 17 included). It is the second of four lists for the runner and rules
split, and needs `agents/tasks/auditor-cli/tasks-1.md` finished.

Until the catalogue list (`agents/tasks/default-rule-catalogue/tasks-1.md`)
runs, an unset `AUDITOR_RULES_PATH` keeps the built-in registry. Every
existing test must therefore pass unchanged after every task in this list.
Three rules hold for every task:

- **No changed tests.** A task in which an existing test's expected output
  changes stops as `blocked`, naming the test.
- **No decisions.** Where a task meets a case the spec does not name, it stops
  as `blocked` for the operator, naming the case.
- **Fixture rules repositories** live under `tests/rulesrepo/fixtures/`, one
  directory per case, and hold only what their case needs.

---

## Task 1: Start the helper API

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** API (`auditor.api`)

**Technical Goal:** `auditor.api` exists as the one module that rule code may
import, re-exporting `emit`, `Candidate` and the readers and resolvers in
`auditor.core`, with `API_VERSION = (1, 0)`.

**Subtasks:**

- [x] Starting-point check: `grep -rnwE 'rulesrepo|RulesRepoError|rulescli|API_VERSION' src/auditor` prints nothing, and `test ! -e src/auditor/api` succeeds. If either fails, stop as `blocked` and name what exists
- [x] Tests first, in `tests/rulesrepo/test_api.py`: every name the spec lists is reachable as `auditor.api.<name>` and is the same object as its source
- [x] Write `src/auditor/api/__init__.py`, re-exporting by full path as the package's `__init__` rules allow, with `API_VERSION = (1, 0)`

**Acceptance Criteria:**

- [x] The test passes, and no existing module imports `auditor.api` yet

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests/rulesrepo/test_api.py -q -p no:cacheprovider` passes

**Notes:**

- The catalogue list adds the helpers it promotes. This task exports only what `auditor.core`, `auditor.phaseb.candidates` (for `Candidate`) and the emitter hold today

---

## Task 2: Load and validate a rules repository

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Repository format; API (`Rule`, `RulesRepo`, `rules_root`, `load`); Implementation (Loading, Caching); Error handling

**Technical Goal:** `auditor.rulesrepo.load` reads `auditor-rules.toml` and
every `rules/*/rule.toml`, validates them against the spec's key table, and
imports no rule code.

**Subtasks:**

- [x] Tests first, in `tests/rulesrepo/test_load.py`, with fixtures for:
  - one valid rule of each kind;
  - an unknown key;
  - an unknown kind;
  - a missing `rule.md`;
  - a check without `check.py`;
  - a question with a lister but no `kinds`;
  - a duplicate rule id across two directories;
  - `api = "2.0"`;
  - `api = "1.1"` against runner 1.0;
  - a missing `auditor-rules.toml`;
  - an unset or empty `AUDITOR_RULES_PATH`, and one naming a missing directory.

  Each error case asserts the spec's message, naming the file
- [x] Write `src/auditor/rulesrepo.py`, defining:
  - `RulesRepoError(SettingsError)`;
  - `Rule` and `RulesRepo` (with `rule_ids()`, which includes the runner's own ids);
  - `rules_root` and `load`;
  - a per-process cache that `auditor.core.clear_source_cache` also clears

**Acceptance Criteria:**

- [x] Every case passes, and `load` imports nothing: a fixture `check.py` that raises at import does not fail `load`

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests/rulesrepo/test_load.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- The runner's own ids come from the Default rule catalogue spec's list: `auditme-check-crash`, `unreadable-file`, `src-loose-module`, `ruff` and `lockfile-drift`

---

## Task 3: Run a rules repository's checks in the sweep

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** API (`import_entry`); Commands (`auditor check`); Implementation (Loading); Error handling (A rule's code raises)

**Technical Goal:** With `AUDITOR_RULES_PATH` set, `auditor check` runs:

1. every `project-check` once;
2. then every `check` once per root;

each in rule-name order, imported through `import_entry`, with nothing put on
`sys.path`. With the variable unset, the built-in registry runs as today.

**Subtasks:**

- [x] Tests first, in `tests/rulesrepo/test_sweep.py`, checking that:
  - a fixture project swept with a fixture rules repository emits exactly the fixture's hits;
  - a rule whose `check` raises yields one `auditme-check-crash` hit naming the rule directory, and the other rules still run;
  - a rule cannot import a sibling rule;
  - `[tool.auditme] never-accepted` is validated against the loaded repository's `rule_ids()`;
  - with the variable unset, the full existing suite is unaffected
- [x] Write `import_entry`, using `importlib.util.spec_from_file_location` under `auditor_rules.<name>.<stem>`, with the module registered in `sys.modules`
- [x] In `src/auditor/sweep.py`, choose between the loaded repository and `auditor.registry` by whether `AUDITOR_RULES_PATH` is set. Report a `RulesRepoError` as `ERROR: <message>` on stderr, with exit 2 and nothing on stdout

**Acceptance Criteria:**

- [x] The new tests pass, and the existing suite passes unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests/rulesrepo tests/checker/test_driver.py tests/checker/test_settings.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 2

---

## Task 4: Run a rules repository's Phase B questions

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Repository format (question keys); Implementation (Phase B)

**Technical Goal:** With the variable set, the Phase B registry is built from
the loaded `question` rules that have a lister. `kinds`, `batch-size` and
`takes-depth` come from `rule.toml`, and the brief is the rule's `brief.md`.
The plan, check, merge and ledger code does not change.

**Subtasks:**

- [x] Tests first, in `tests/rulesrepo/test_phaseb.py`. A fixture question with a lister, run through `auditor phaseb candidates` and `plan`, must give:
  - its candidates;
  - its brief version;
  - its batch size;
  - the depth only when `takes-depth` is true
- [x] In `src/auditor/phaseb/candidates.py`, build the registry from the loaded repository when the variable is set, and keep today's registrations when it is unset

**Acceptance Criteria:**

- [x] The new tests pass, and `tests/checker/phaseb` passes unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests/rulesrepo/test_phaseb.py tests/checker/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 3

---

## Task 5: Add the `auditor rules` report commands

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Commands (`list`, `check`, `standards`, `questions`, `pending`); Implementation (Import boundary); Tests (`rules pending`)

**Technical Goal:** `auditor rules list|check|standards|questions|pending` work
as the spec says. `check` also reports every `import auditor.<x>` in rule code
where `<x>` is not `api`.

**Subtasks:**

- [x] Tests first, in `tests/rulesrepo/test_rulescli.py`, one per command over the fixtures. Cover:
  - the import-boundary failure;
  - the `pending` cases: no `TODO.md`, a `TODO.md` with no `## ` heading, a heading inside a fenced block, and two open items
- [x] Write `src/auditor/rulescli.py` and register `rules` in `src/auditor/cli.py`

**Acceptance Criteria:**

- [x] Every command's output and exit status match the spec. `pending` exits 1 and lists headings only when an item is open

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests/rulesrepo/test_rulescli.py tests/checker/test_cli.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 4

---

## Task 6: Report the rules identity

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** API (`Identity`, `identity`); Commands (`identity`); Tests

**Technical Goal:** `auditor rules identity` prints the runner version, the API
version, the rules path, the commit, the dirty flag and the digest as JSON.
With `--expect <file>`, it exits 1 on any difference.

**Subtasks:**

- [x] Tests first, in `tests/rulesrepo/test_identity.py`, over a fixture rules repository that the test makes into a git repository:
  - `--expect` exits 0 on the same identity, and exits 1 after a commit;
  - `rules_dirty` is true after an uncommitted edit;
  - `rules_commit` is null outside a work tree
- [x] Write `identity` and the command. The digest is sha256 over the tracked files under `rules/`, in path order

**Acceptance Criteria:**

- [x] The new tests pass

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests/rulesrepo/test_identity.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 5

---

## Task 7: Run a rules repository's own tests

**Status:** done
**Priority:** medium
**Complexity:** medium
**Spec Reference:** Commands (`test`); External dependencies (pytest)

**Technical Goal:** `auditor rules test` runs pytest over `rules/*/tests` with
the `auditor.testing` plugin, which is the generic helpers of
`tests/checker/conftest.py`. pytest comes from the `auditor[test]` extra.

**Subtasks:**

- [x] Move the generic fixtures and helpers (`git`, `project`, `run_check`, `clean_emitted` and the settings-restoring fixtures) into `src/auditor/testing.py`, as a pytest plugin. `tests/checker/conftest.py` loads the plugin and keeps only what is specific to this suite
- [x] Add `[project.optional-dependencies] test = ["pytest>=9.2.0"]` and run `uv lock`
- [x] Tests first, in `tests/rulesrepo/test_rules_test.py`:
  - a fixture rule's own test passes through `auditor rules test`;
  - without pytest installed, the command exits 2 and names `auditor[test]`
- [x] Add `test` to `src/auditor/rulescli.py`

**Acceptance Criteria:**

- [x] The new tests pass, and every existing test passes with the moved fixtures

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests -q -p no:cacheprovider` passes, because this task moves fixtures that every checker test uses

**Notes:**

- Depends on Task 5
- `uv lock` must resolve under `exclude-newer = "14 days"`. If it does not, stop as `blocked` and name the version

---

## Task 8: Add the standards SessionStart hook

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Standards hook; Tests

**Technical Goal:** `claude/hooks/auditme-standards.sh` prints
`auditor rules standards` in an opted-in project, and prints the `ERROR:` line
when it cannot. It always exits 0. `bin/install-claude.sh` registers it as a
SessionStart hook.

**Subtasks:**

- [x] Tests first, in `tests/test_standards_hook.py`, covering:
  - a valid fixture repository prints its standards;
  - an unset variable prints the `ERROR:` line;
  - a project that has not opted in prints nothing;
  - every case exits 0
- [x] Write the hook, reusing the Stop hook's opt-in test
- [x] Add a `hooks.SessionStart[auditme-standards.sh]` append to `bin/install-claude.sh`, and extend `tests/test_install_claude.py`

**Acceptance Criteria:**

- [x] The new tests pass

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests/test_standards_hook.py tests/test_install_claude.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 5
- The spec relies on Claude Code adding a SessionStart hook's stdout to the session's context. If the Claude Code hooks documentation does not say this, stop as `blocked` and quote what it says instead

---

## Task 9: Record identity in reviews, document it and close the spec

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Spec Reference:** Recording identity; Trust; Change requests; Settings

**Technical Goal:** The audit skill records and compares the identity, the
docs describe rules repositories, and the spec is closed.

**Subtasks:**

- [ ] In `claude/skills/auditme/SKILL.md`:
  - the review template's `**Script version:**` line becomes `**Auditor identity:**`, holding `auditor rules identity` as JSON;
  - the skill refuses to start an audit while `rules_dirty` is true;
  - when the identity differs from the previous review's, the review writes `Rules changed since review N: <fields>` and does not count as a convergence measurement
- [ ] Add the Change requests procedure to `SKILL.md`, as a rule that applies only when `AUDITOR_RULES_PATH` is set:
  - filing with `todo-add` in `$AUDITOR_RULES_PATH/TODO.md`;
  - the `auditor rules pending` precondition;
  - rejection, to `DONE.md` and to `## Rejected widenings` in the rule's `rule.md`;
  - runner requests, which go to the auditor repository's `TODO.md`.

  The built-in path keeps `requests.md` until the catalogue list retires it
- [ ] In the docs:
  - `docs/concepts.md`: the trust paragraph and what a rules repository is;
  - `docs/reference/cli.md`: every `auditor rules` command;
  - `docs/setup.md`: setting `AUDITOR_RULES_PATH` with direnv
- [ ] Set the spec's `**Status:**` to `implemented`
- [ ] Save the full test run for the run order's merge gate, from the repository root of this worktree: `MAIN=$(git worktree list --porcelain | sed -n '1s/^worktree //p'); LOG="$MAIN/logs/rro/rules-repository/tasks-1/final-tests.log"; mkdir -p "$(dirname "$LOG")"; uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider 2>&1 | tee "$LOG"; [ "${PIPESTATUS[0]}" -eq 0 ] && echo 'all selected test directories passed' | tee -a "$LOG"`, and the log ends with `all selected test directories passed`

**Acceptance Criteria:**

- [ ] `uv run --group docs mkdocs build --strict` passes, and the skill text names `auditor rules identity` and `auditor rules pending`

**Definition of Done:**

- [ ] `pre-commit run --all-files` exits 0
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [ ] `uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider` passes
- [ ] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Depends on Tasks 6, 7 and 8

---
