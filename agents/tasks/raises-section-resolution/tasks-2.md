# Tasks: Raises section resolution

**Spec:** `agents/specs/raises-section-resolution/spec.md`
**Created:** 2026-11-24
**Version:** 2

Implements amendment 1.3 only ("first-party libraries outside the
project"); version 1.2 shipped with `tasks-1.md`. Every part of the
amendment was approved on 2026-11-24
(`agents/reviews/raises-first-party-amendment-2026-11-24.md`), and the
operator chose declared paths in a new `[tool.auditme] first-party` key the
same day. No task decides anything: a case the amendment does not name stops
the task as `blocked`, naming the case.

Every existing test must pass unchanged; a task in which an existing test's
expected output changes stops as `blocked`, naming the test and the output
before and after. It never edits the test to pass.

Every task runs unattended: none calls an LLM, makes a network request or
reads another repository. A test's first-party library is a directory the
test builds beside its project fixture under `tmp_path`, never a real
sibling repository. The repository has no affected-tests tool: each task
names its own test files and the test files that import the module it
changes; the last task runs every test tree. Commands run from the
repository root. Fixtures use neutral names (`probe`, `lib`, `LibError`), as
the `no-project-names` hook requires.

---

## Task 1: Read and validate `[tool.auditme] first-party`

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Amendment 1.3: Setting, API, Implementation (first bullet), Error handling, Testing (last bullet)

**Technical Goal:** `first_party_dirs(scope)` returns the listed package
directories, and `audit.py` stops with the roots' error and exit status on an
invalid entry, before any check runs.

**Subtasks:**

- [x] Starting-point check: `grep -rnwE 'first_party_dirs|cached_first_party_dirs' claude/skills/auditme/checks` prints nothing; if it prints anything, stop as `blocked` and name it
- [x] Tests first in `claude/skills/auditme/tests/test_settings.py` (reading and each `RootsError` case in the amendment's Testing list, `first-party` beside `roots` and `never-accepted` accepted) and `claude/skills/auditme/tests/test_driver.py` (a missing entry exits with the roots' status and names the entry before any hit is printed); see them fail
- [x] Add `first_party_dirs` and `cached_first_party_dirs` to `claude/skills/auditme/checks/auditme/core.py` beside `declared_roots`, with the amendment's signature and docstring; admit `first-party` in `declared_roots`' unknown-key check
- [x] Call `cached_first_party_dirs(scope)` in `claude/skills/auditme/checks/audit.py` where the roots are read, inside the existing `SettingsError` handling

**Acceptance Criteria:**

- [x] Without the key, `first_party_dirs` returns `[]` and the sweep's output is unchanged
- [x] Each invalid entry in the amendment's Testing list stops `audit.py` with a message naming the entry

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_settings.py claude/skills/auditme/tests/test_roots.py claude/skills/auditme/tests/test_driver.py claude/skills/auditme/tests/test_core.py -q -p no:cacheprovider` passes
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/core.py`, `claude/skills/auditme/checks/audit.py`
- `changed.py` runs `audit.py`, so it needs no change

---

## Task 2: Follow callees into the listed libraries

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Amendment 1.3: Implementation (second to fifth bullets), Testing (first four bullets)

**Technical Goal:** `raises-section-drift` adds every module under each
listed directory to its tables, follows calls into them as same-package
calls, counts their error classes as domain errors, and reports hits only on
the swept package's files.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/test_error_handling.py`, under the `# --- raises-section-drift` heading: the amendment's first four Testing bullets, with the library built beside the project fixture and listed in its `pyproject.toml`; see them fail
- [x] In `check_raises_section_drift` (`claude/skills/auditme/checks/auditme/rules/error_handling.py`), add each first-party module to `modules` under `module_dotted(path, dir)`, so its functions join `known`, `declared_by` and `node_of` and its classes join `parents`; keep the subject loop to the swept package's functions
- [x] Name a first-party file in `related` with `os.path.relpath(path, scope)`
- [x] Add an `Extension (<the day this task runs>):` paragraph to the rule's docstring

**Acceptance Criteria:**

- [x] The amendment's first four Testing cases pass
- [x] Every existing `raises-section-drift` test passes unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/phaseb/test_a4_candidates.py -q -p no:cacheprovider` passes
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0

**Notes:**

- Depends on Task 1
- The A4 lister does not change (amendment 1.3, last Implementation bullet); `test_a4_candidates.py` is run to show it

---

## Task 3: Document the setting and close the list

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Amendment 1.3: Documentation; Motivation

**Technical Goal:** The setting and the rule's new reach are documented,
every check passes over the whole branch, and the `TODO.md` item moves to
`DONE.md`.

**Subtasks:**

- [x] `docs/reference/cli.md`: a `### First-party libraries` section after "Declared roots", giving the key, an example, that entries may lie outside the project, that they are read but never swept, and that a listed directory must exist wherever the sweep runs (CI included); add the new errors to the errors table there
- [x] `docs/guide/checker.md`: the `raises-section-drift` row adds that callees in libraries `[tool.auditme] first-party` lists are followed
- [x] `claude/skills/auditme/SKILL.md` A4: the rule also follows callees into the libraries `first-party` lists
- [x] Run every test tree, with its log kept:
      `MAIN=$(git worktree list --porcelain | sed -n '1s/^worktree //p'); LOG="$MAIN/logs/rro/raises-section-resolution/tasks-2/final-tests.log"; mkdir -p "$(dirname "$LOG")"; uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider 2>&1 | tee "$LOG"; [ "${PIPESTATUS[0]}" -eq 0 ] && echo 'all selected test directories passed' | tee -a "$LOG"`
- [x] Set the spec's `**Status:**` to `implemented`
- [x] Move the `TODO.md` item "`raises-section-drift` does not follow `Raises:` sections of first-party libraries outside the sweep" to the end of `DONE.md`: append its heading and body unchanged, then `Done: <the day this task runs> - amendment 1.3 of agents/specs/raises-section-resolution/spec.md, agents/tasks/raises-section-resolution/tasks-2.md.`, and remove it from `TODO.md`

**Acceptance Criteria:**

- [x] `$MAIN/logs/rro/raises-section-resolution/tasks-2/final-tests.log` ends with `all selected test directories passed`

**Definition of Done:**

- [x] `pre-commit run --all-files` exits 0
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [x] The final test command above exits 0 and prints `all selected test directories passed`
- [x] `uv run --group docs mkdocs build --strict` passes
- [x] `python3 ~/.claude/skills/todo-review/verify_bodies.py <baseline> TODO.md DONE.md` exits 0, where `<baseline>` is `TODO.md` at the commit that added this list: `git show $(git log --diff-filter=A --format=%H -- agents/tasks/raises-section-resolution/tasks-2.md):TODO.md`

**Notes:**

- Depends on Tasks 1 and 2
