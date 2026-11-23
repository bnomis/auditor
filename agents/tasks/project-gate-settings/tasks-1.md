# Tasks: Project gate settings

**Spec:** `agents/specs/project-gate-settings/spec.md`
**Created:** 2026-11-23
**Version:** 1

Implements the whole spec, version 1.0, approved in review 1 on 2026-11-23:
`[tool.auditme] never-accepted` (rules whose accept markers never count in a
project, refused in `emit`), the `RULE_IDS` registry it validates against,
and the `AUDITME_RUFF` environment variable naming the ruff the sweep runs.
Every choice the spec makes was approved; no task decides anything.

The new rule-id list is the one hand-kept list in the change. `CHECKS` in
`claude/skills/auditme/checks/auditme/registry.py` and
`claude/skills/auditme/tests/registry-order.txt` stay as they are: no check is
added, removed or reordered. Every existing test must pass unchanged; a task in
which an existing test's expected output changes stops as `blocked` for the
operator, naming the test and the output before and after. It never edits the
test to pass.

Every task runs unattended: none calls an LLM, makes a network request or
reads another repository. Moving other projects onto the pinned hook is the
operator's work, outside this repository and this list.

The repository has no affected-tests tool. Each task names its own test files
and the test files that import the module it changes; the last task runs every
test tree. Test commands run from the repository root. Tests use neutral
fixture names (`probe`, `Probe`), as the `no-project-names` hook requires, and
a test that sets `AUDITME_RUFF` does it with `monkeypatch.setenv`, never in the
process environment, and never prints the environment.

---

## Task 1: Add `RULE_IDS` and keep it in step with the source and the docs

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** API (`RULE_IDS`); Implementation (`RULE_IDS`); Testing (`test_registry.py`)

**Technical Goal:** Give the checker one list of every rule id it can emit,
so `never-accepted` can refuse a misspelt name, and make a test fail when a
rule is added to the source or the docs without it.

**Subtasks:**

- [x] Starting-point check: `grep -rnwE 'RULE_IDS|SettingsError|NEVER_ACCEPTED|never_accepted|is_never_accepted|AUDITME_RUFF|refused_reason' claude/skills/auditme/checks` prints nothing; if it prints anything, stop as `blocked` and name what it found
- [x] Tests first, in `claude/skills/auditme/tests/test_registry.py`: (a) every `rule='<literal>'` and `rule="<literal>"` keyword in `claude/skills/auditme/checks/auditme/` and `claude/skills/auditme/checks/audit.py` (read with `ast`, not a regex over text) is in `RULE_IDS`; (b) `RULE_IDS` equals the set of first-column ids of every Markdown table whose header's first cell is `Rule id` under the `## The rules` heading of `docs/guide/checker.md`, up to the next `## ` heading, backticks stripped; (c) `ruff` and `lockfile-drift` are in it. Run them and see them fail on the missing name
- [x] Add `RULE_IDS: frozenset[str]` to `claude/skills/auditme/checks/auditme/registry.py`, a literal with one id per line, sorted, with the spec's docstring as a comment above it. Fill it from the tests' failure output; for each of the five `rule=rule` call sites (`grep -rn 'rule=rule' claude/skills/auditme/checks`), read where `rule` comes from and confirm each value it can take is in the set
- [x] If (b) fails because an id the source emits has no row in `docs/guide/checker.md`, or a row names an id the source never emits, stop as `blocked`, naming each such id: which side is right is the operator's call, not this task's

**Acceptance Criteria:**

- [x] `RULE_IDS` holds every id the source can emit and every id the docs' rule tables list, and nothing else
- [x] Removing any one id from `RULE_IDS`, or adding a row to a rules table, makes a `test_registry.py` test fail (checked by hand once, then reverted)

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/test_registry.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/registry.py`, `claude/skills/auditme/tests/test_registry.py`, `docs/guide/checker.md` (read only)

---

## Task 2: Read `never-accepted` and refuse markers in `emit`

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** API (`SettingsError`, `RootsError`, `NEVER_ACCEPTED`, `never_accepted`, `is_never_accepted`, `refused_reason`); Settings (`never-accepted`); Implementation (Reading `never-accepted`, Refusing markers); Error handling (rows 1 and 3); Testing (`test_roots.py`/`test_settings.py`, `test_core.py`, `test_driver.py`); Compatibility

**Technical Goal:** A project lists rules in `[tool.auditme] never-accepted`;
`audit.py` validates the list before anything is emitted, and every hit of a
listed rule is reported unaccepted with its marker's text in `refused_reason`.

**Subtasks:**

- [x] Tests first:
  - a new `claude/skills/auditme/tests/test_settings.py`: `never_accepted` returns the patterns in order; absent table or key gives `()`; a non-list, a non-string entry, an unknown id, a `*` pattern matching no id and a `*` not at the end each raise `SettingsError` and, through `audit.py`, exit 2 with `ERROR: pyproject.toml [tool.auditme]: <detail>` on stderr and nothing on stdout; `ruff` and `lockfile-drift` are accepted as entries
  - `test_core.py`: `is_never_accepted` for an exact id, a family (`leading-underscore-*` against `leading-underscore-parameter`), and a near miss (`leading-underscore` against the pattern `leading-underscore-*`); `emit` with `NEVER_ACCEPTED` set refuses an accepted hit of a listed rule (`accepted` false, `accepted_reason` null, `refused_reason` the old reason) and leaves an accepted hit of an unlisted rule as it was, with no `refused_reason` key
  - `test_driver.py`: a `probe` project with a `literal-duplication` hit carrying a scoped marker reports `accepted: false` with `refused_reason` when `never-accepted = ["literal-duplication"]`, and `accepted: true` with no `refused_reason` when the key is absent; the same with `--package`
  - Run them and see them fail
- [x] In `claude/skills/auditme/checks/auditme/core.py`: add `SettingsError(Exception)` and make `RootsError` subclass it; add `never-accepted` to the table's known keys in `declared_roots`; add `NEVER_ACCEPTED`, `never_accepted(scope)` and `is_never_accepted(rule, patterns)` as the spec's API gives them, reading the table the way `declared_roots` does and validating against `auditme.registry.RULE_IDS`; export the new names beside `RootsError` in the module's `__all__`
- [x] In `emit`, before de-duplication and printing: when `is_never_accepted(rule, NEVER_ACCEPTED)` and the hit is accepted, set `accepted` to false, move `accepted_reason` to `refused_reason` and set `accepted_reason` to None
- [x] In `claude/skills/auditme/checks/audit.py`: read `never_accepted(scope)` before the sweep on every run, `--package` and `--extra-root` included, and set `auditme.core.NEVER_ACCEPTED`; catch `SettingsError` (replacing the `RootsError` handler) and exit 2 with the existing `ERROR:` line
- [x] If `core.py` importing `registry.py` makes an import cycle, put the validation in `audit.py` instead (it imports both) and say so in the commit body; the API stays as the spec gives it

**Acceptance Criteria:**

- [x] A project without `never-accepted` gets byte-identical output to before (no `refused_reason` key anywhere)
- [x] A listed rule's marked hit is unaccepted and carries `refused_reason`; an unlisted rule's marked hit stays accepted
- [x] Each invalid value exits 2 before any hit is printed

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/test_settings.py claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/test_driver.py claude/skills/auditme/tests/test_roots.py claude/skills/auditme/tests/test_registry.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1 (`RULE_IDS`)
- `test_roots.py` runs because `declared_roots` and `RootsError` change; every existing roots test must pass unchanged

---

## Task 3: `AUDITME_RUFF` names the ruff the sweep runs

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** API (`ruff_executable`); Settings (`AUDITME_RUFF`); Implementation (`AUDITME_RUFF`); Error handling (row 2); Testing (`test_project_hygiene.py`)

**Technical Goal:** A project whose ruff lives in a shared environment sets
`AUDITME_RUFF`, and the sweep runs that ruff ahead of `.venv/bin/ruff` and
PATH; a value naming no executable stops the sweep.

**Subtasks:**

- [x] Tests first, in `claude/skills/auditme/tests/test_project_hygiene.py`, each setting the variable with `monkeypatch.setenv` or removing it with `monkeypatch.delenv(..., raising=False)`: an executable named by `AUDITME_RUFF` wins over an executable `.venv/bin/ruff`, with label `AUDITME_RUFF`; unset and empty each fall through to `.venv/bin/ruff`, then `ruff on PATH`; through `audit.py`, a value naming a missing file, and one naming a non-executable file, each exit 2 with `ERROR: AUDITME_RUFF=<value> is not an executable file` on stderr and nothing on stdout. Run them and see them fail
- [x] In `ruff_executable` (`claude/skills/auditme/checks/auditme/rules/project_hygiene.py`), check `os.environ.get('AUDITME_RUFF')` first; update its docstring to the spec's
- [x] In `claude/skills/auditme/checks/audit.py`, before the sweep and beside the settings read of Task 2: when the variable is set and not empty and does not name an executable file, print the error and return 2

**Acceptance Criteria:**

- [x] With the variable unset, the ruff lookup and every existing test's output are unchanged
- [x] An invalid value exits 2 before any hit is printed

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/test_project_hygiene.py claude/skills/auditme/tests/test_driver.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 2 (the pre-sweep checks in `audit.py` sit together)
- `ruff_executable` caches per run and scope in `INDEX_CACHE`; the tests clear it (or use a fresh scope) so one test's lookup does not leak into the next

---

## Task 4: `changed.py` names the never-accepted rule in its advice

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Implementation (`changed.py`'s advice); Testing (`test_changed.py`)

**Technical Goal:** When a push fails on a refused marker, the hook says the
project does not accept markers for that rule, instead of telling the user to
add one.

**Subtasks:**

- [x] Tests first, in `claude/skills/auditme/tests/test_changed.py`: `--all` on a `probe` project with `never-accepted = ["literal-duplication"]` and a marked `literal-duplication` hit exits 1, prints the hit, and prints `literal-duplication: this project does not accept markers for this rule ([tool.auditme] never-accepted); fix the code.` once; a project with two such hits of one rule prints the line once. Run them and see them fail
- [x] In `claude/skills/auditme/checks/changed.py`, after the hit list: print that line once per rule whose reported hits carry `refused_reason`, beside `RULE_HELP`'s lines, and leave the generic `ACCEPT_HELP` for the other rules

**Acceptance Criteria:**

- [x] The advice appears once per refused rule and never for a hit without `refused_reason`
- [x] Output for a run with no refused hit is unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/test_changed.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 2 (`refused_reason`)

---

## Task 5: Document both settings

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Implementation (Documentation); Settings; Error handling

**Technical Goal:** A user can find, configure and understand both settings
from the guide, the CLI reference and the setup page.

**Subtasks:**

- [x] `docs/guide/checker.md`: a "Never-accepted rules" section beside the declared-roots material under "Accepting a hit": the key, the `*` family syntax, that a misspelt name exits 2, the `refused_reason` key in the output, and when a project would use it (a rule it fixes and never accepts); describe `AUDITME_RUFF` where ruff's lookup is described
- [x] `docs/reference/cli.md`: both settings, and the two new exit-2 cases with their messages
- [x] `docs/setup.md`: the ruff prerequisite names `AUDITME_RUFF` for a ruff outside the project's `.venv`
- [x] `claude/skills/auditme/SKILL.md` (the acceptance mechanism) and `claude/skills/auditme/checks/audit.py`'s module docstring: a project can refuse markers for named rules
- [x] `grep -rn 'never accepted by a marker\|no accept marker' docs claude/skills/auditme/SKILL.md` and update each passage that lists only `ruff` and `lockfile-drift` as never accepted, so none says a project cannot add to them

**Acceptance Criteria:**

- [x] Each page names `never-accepted` or `AUDITME_RUFF` as the subtasks say, with an example
- [x] No page names a project the checker has been run on

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/test_registry.py -q -p no:cacheprovider` passes (the docs' rule tables are unchanged, so `RULE_IDS` still matches)
- [x] `uv run --group docs mkdocs build --strict` passes

**Notes:**

- Depends on Tasks 2-4

---

## Task 6: Whole-tree checks, deduplication, and close the spec

**Status:** in-progress
**Priority:** high
**Complexity:** small
**Spec Reference:** whole spec

**Technical Goal:** Remove any duplication the new code introduced, run every
check the change can reach, save the final test run to the test log, and mark
the spec implemented.

**Subtasks:**

- [ ] Hoist anything the new code duplicates to a single owner: grep `claude/skills/auditme/checks/` for each literal and one-line helper Tasks 2-4 added (the `[tool.auditme]` table read, the executable-file test, the advice text), and import rather than copy. Prefer `core.py`, which every module already imports, over adding a new edge
- [ ] Confirm `claude/skills/auditme/tests/registry-order.txt` and `CHECKS` are unchanged against the branch's base: `git diff <base> -- claude/skills/auditme/tests/registry-order.txt` prints nothing, and `git diff <base> -- claude/skills/auditme/checks/auditme/registry.py` shows only the `RULE_IDS` addition
- [ ] Set the spec's `**Status:**` to `implemented` in `agents/specs/project-gate-settings/spec.md`
- [ ] Run `pre-commit run --all-files` and `pre-commit run auditme-all --hook-stage manual --all-files`; fix what they report
- [ ] Run the final full test run, saving it to the test log relative to the main checkout (the list may run in a worktree):
      `MAIN=$(git worktree list --porcelain | sed -n '1s/^worktree //p'); LOG="$MAIN/logs/rro/project-gate-settings/tasks-1/final-tests.log"; mkdir -p "$(dirname "$LOG")"; uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider 2>&1 | tee "$LOG"; [ "${PIPESTATUS[0]}" -eq 0 ] && echo 'all selected test directories passed' | tee -a "$LOG"`
      The pass line `all selected test directories passed` is printed only when pytest exits 0

**Acceptance Criteria:**

- [ ] No literal or helper added by this list is defined twice under `claude/skills/auditme/checks/`
- [ ] The spec's status is `implemented`
- [ ] `$MAIN/logs/rro/project-gate-settings/tasks-1/final-tests.log` ends with `all selected test directories passed`

**Definition of Done:**

- [ ] `pre-commit run --all-files` exits 0
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [ ] The final test command above exits 0 and prints `all selected test directories passed`
- [ ] `uv run --group docs mkdocs build --strict` passes

**Notes:**

- Depends on Tasks 1-5
- After the merge, the merged commit on `main` is the pin the operator records in their coordinating note; that and every other project's move to the hook are outside this list

---

## Task 7: Make the install-hooks "pre-commit absent" test independent of the machine

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** none (found by Task 6's final test run)

**Technical Goal:** `tests/test_install_hooks.py::test_installing_without_pre_commit_fails_before_writing` fails when `pre-commit` is on PATH (it expects exit 1 and gets 0). Make it hide `pre-commit` from the script's PATH itself, so the full run passes on any machine.

**Subtasks:**

- [x] Confirm the failure on `main` (this branch does not touch `bin/` or `tests/test_install_hooks.py`)
- [x] Give the test a PATH without `pre-commit`, via `monkeypatch` or the `run` helper's environment
- [x] Re-run Task 6's final test command and the `pre-commit` checks

**Definition of Done:**

- [x] The final test command in Task 6 exits 0 and prints `all selected test directories passed`

**Notes:**

- Task 6 stays `in-progress` until this passes; its other subtasks are done
