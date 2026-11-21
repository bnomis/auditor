# Tasks: Clearing this repository's audit backlog

**Source:** `agents/reviews/audit-backlog-2026-11-21.md`
**Created:** 2026-11-21
**Version:** 1

Clears the 685 unaccepted hits `python3 claude/skills/auditme/checks/audit.py .`
reported on 2026-11-21 in this repository's own checker and tests, as the
review decided (every recommendation accepted, 2026-11-21). The motivating
item is `TODO.md`'s "Fix or accept this repository's audit backlog"; the last
task moves it to `DONE.md`.

Until the sweep reaches zero, the `auditme-changed` commit hook would block
almost every commit on hits a later task clears. As the operator chose on
2026-11-21, Task 1 pauses it (`stages: [manual]`) and the last task restores
it, with `pre-push` on `auditme-all`, only once the whole-tree sweep is at
zero. Every other hook runs on every commit. The Claude Code Stop hook still
runs the sweep at the end of each turn; it blocks once and lets the turn end
the second time, and a task does not act on its report.

The checker refinements (Tasks 4 to 7) change rules every project's audit
uses; each is a narrowing (a carve-out), documented in the rule's docstring
and in `claude/skills/auditme/SKILL.md`'s documented refinements, with a test
that the carve-out does not fire.

The repository has no affected-tests tool. Each task names its own test files;
the last task runs every test tree.

The sweep's count after each task is recorded in its commit body, so a task
that adds hits shows.

---

## Task 1: Pause the commit hook for this list

**Status:** done
**Priority:** high
**Complexity:** small
**Source Reference:** the operator's hook choice of 2026-11-21 (header)

**Technical Goal:** Let this list's commits through while hits remain, with
the pause visible in the config and in `TODO.md`.

**Subtasks:**

- [x] The worktree has its own `.venv`, synced from `uv.lock` (`uv sync --frozen`), so the audit runs the pinned ruff (0.17.2) rather than the one on `PATH`; without it the sweep adds a `ruff-version-drift` hit that exists only in the worktree (unblocked 2026-11-21: the first run counted 686)
- [x] Check the starting point: `python3 claude/skills/auditme/checks/audit.py . | python3 -c "import sys,json; print(sum(1 for h in map(json.loads, sys.stdin) if not h['accepted']))"` prints 685 or fewer; if more, stop the list as `blocked`, naming the count
- [x] `.pre-commit-config.yaml`: set the local `auditme-changed` hook's `stages` to `[manual]`, with a comment that `agents/tasks/reviews/tasks-1.md` paused it and its last task restores `[pre-commit]`
- [x] `TODO.md`: add a dated note to "Fix or accept this repository's audit backlog" that `auditme-changed` is paused until this list's last task

**Acceptance Criteria:**

- [x] `pre-commit run --all-files` no longer lists `auditme-changed`

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)

**Notes:**

- Key file: `.pre-commit-config.yaml`
- Unblocked 2026-11-21 by the operator: the starting check counted 686 because the worktree had no `.venv`; after `uv sync --frozen` it counts 685. Every later task's sweep runs in the same worktree and uses that `.venv`.

---

## Task 2: Raises sections

**Status:** todo
**Priority:** high
**Complexity:** small
**Source Reference:** "The plan the coding standards settle", Raises sections

**Technical Goal:** Every `Raises:` section names what reaches the caller,
including `RootsError` from `_audit_roots` (added 2026-11-21).

**Subtasks:**

- [ ] Add `RootsError` to the six `Raises:` sections `raises-section-drift` names (callers of `_audit_roots` in `checks/auditme/phaseb/`)
- [ ] Add a `Raises:` section to `declared_roots`, `entry_point_targets`, `target_bytes`, `file_target`, `write_ledger` and `resolve_base`
- [ ] Run the sweep: no `raises-section-drift` or `missing-raises-section` hit remains

**Acceptance Criteria:**

- [ ] The sweep reports neither rule

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_roots.py claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1

---

## Task 3: The drifted spec signatures

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** "The plan the coding standards settle", Specs

**Technical Goal:** The two implemented specs show `check_run`,
`list_candidates` and `register_question` as the code defines them.

**Subtasks:**

- [ ] Find the three `spec-api-signature-drift` hits in the sweep and update each `def` line in its spec's `## API` block to the current signature, with a dated note under it
- [ ] Run the sweep: no `spec-api-signature-drift` hit remains

**Acceptance Criteria:**

- [ ] The sweep reports no `spec-api-signature-drift` hit

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)

**Notes:**

- Depends on Task 1

---

## Task 4: R1 - line-pattern rules skip non-docstring string literals

**Status:** todo
**Priority:** high
**Complexity:** medium
**Source Reference:** R1

**Technical Goal:** The leading-underscore rules, `legacy-typing`,
`aliased-imports` and `relative-import-nonpackage` stop reading a plain string
literal (fixture source, a regex) as code.

**Subtasks:**

- [ ] In the rules that match source lines, skip lines that sit inside a string literal that is not a docstring (found with `ast`: the line ranges of every `ast.Constant` string not in a docstring position); docstrings are still read
- [ ] Tests in each rule's test module: a fixture string holding the pattern does not fire; the same text as code still fires; a docstring mention still fires
- [ ] Document the refinement in each rule's docstring and under SKILL.md's documented refinements, dated
- [ ] Run the sweep and record the count in the commit body

**Acceptance Criteria:**

- [ ] The fixture-string hits the review counted (about 21) are gone; the three docstring mentions remain for Task 14

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_style_and_naming.py claude/skills/auditme/tests/test_imports_and_surfaces.py claude/skills/auditme/tests/test_leading_underscore_binding.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- Key file: `claude/skills/auditme/checks/auditme/rules/style_and_naming.py`, `imports_and_surfaces.py`

---

## Task 5: R2 - `literal-duplication` leaves test expectations alone

**Status:** todo
**Priority:** high
**Complexity:** small
**Source Reference:** R2 (option A)

**Technical Goal:** In test files, a one-member literal and a literal inside
an `assert` or a `pytest.param` is not counted as a duplicate.

**Subtasks:**

- [ ] In `check_literal_duplication` (`rules/duplication.py`), for a file under a test directory, skip one-member literals and literals inside `assert` statements and `pytest.param(...)` calls; a multi-member literal in test set-up still counts
- [ ] Tests: each skipped form does not fire in a test file; the same literal in source still fires; a repeated multi-member literal in a test fixture still fires
- [ ] Document it in the rule's docstring and SKILL.md's documented refinements, dated
- [ ] Run the sweep and record the count in the commit body

**Acceptance Criteria:**

- [ ] The test expectation hits (about 122) are gone

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_duplication.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1

---

## Task 6: R3, R4, R6 - envelope and `tomllib` carve-outs

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Source Reference:** R3, R4, R6

**Technical Goal:** Three rules stop firing on the cases their own rationale
excludes.

**Subtasks:**

- [ ] R3: `filesystem-envelope-gap` fires only where the handler raises a project error (translates); a handler that returns, continues or logs does not
- [ ] R4: `filesystem-op-without-envelope` accepts a call to a function in the same module whose own body wraps the operation in a handler for `OSError`
- [ ] R6: `get-container-default-then-method-call` skips a mapping produced by `tomllib.load` or `tomllib.loads`
- [ ] Tests for each: the carve-out does not fire; the original shape still fires
- [ ] Document each in the rule's docstring and SKILL.md's documented refinements, dated
- [ ] Run the sweep and record the count in the commit body

**Acceptance Criteria:**

- [ ] The 23, 1 and 2 hits the review named are gone

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/test_state_and_effects.py claude/skills/auditme/tests/test_get_container_default.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- Key files: `claude/skills/auditme/checks/auditme/rules/error_handling.py`, `state_and_effects.py` (whichever defines each check)

---

## Task 7: R5 and R7 - sink pairs and first-party labels

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Source Reference:** R5, R7

**Technical Goal:** `redundant-sink-caller-plus-callee` stops its four
misreads, and `in-function-import` labels declared-root modules first-party.

**Subtasks:**

- [ ] R5: ignore calls inside nested functions, ignore self-recursion, resolve the callee by qualified name, and compare keyword values rather than only keyword names
- [ ] R7: a module under a declared root (`[tool.auditme]`, either mode) is labelled first-party in `in-function-import`'s variant
- [ ] Tests for each misread and for the label
- [ ] Document both in the rules' docstrings and SKILL.md's documented refinements, dated
- [ ] Run the sweep and record the count in the commit body

**Acceptance Criteria:**

- [ ] The six `redundant-sink-caller-plus-callee` hits are gone

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_duplication.py claude/skills/auditme/tests/test_imports_and_surfaces.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1

---

## Task 8: P1 - project-level checks run once

**Status:** todo
**Priority:** medium
**Complexity:** small
**Source Reference:** P1

**Technical Goal:** `check_lockfile` and `check_ruff_version` run once per
sweep in every project, not once per root.

**Subtasks:**

- [ ] `auditme.registry`: remove both from `CHECKS`; `audit.py` runs `PROJECT_CHECKS` once, before the per-root passes, whether or not there is a root (the no-root path stays as it is)
- [ ] Update amendment 1.8's sentence in `agents/specs/project-setup/spec.md` ("Each is also in `CHECKS`") with a dated note that they now run once and that hit order changed
- [ ] Tests in `test_driver.py`: with three roots each project-level check runs once; the no-root case is unchanged
- [ ] Run the sweep and record the count in the commit body

**Acceptance Criteria:**

- [ ] `subprocess-without-memoisation` no longer fires on `check_lockfile` and `check_ruff_version`

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_driver.py claude/skills/auditme/tests/test_project_hygiene.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- The next audit's convergence note must name the changed emission order

---

## Task 9: E1 - entry points print the cause

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Source Reference:** E1 (option A)

**Technical Goal:** The cause of a failure is printed once by the entry point,
and the raise sites stop interpolating it.

**Subtasks:**

- [ ] First: grep the tests for assertions on an error message's system text (`No such file`, `Errno`, `Permission denied`); note each one this task must keep passing
- [ ] `audit.py`, `changed.py`, `phaseb.py`: where they print an error, also print `exc.__cause__` when it is set (`ERROR: <message> (<cause>)`)
- [ ] The 23 `raise PhaseBError(f'...: {error}') from error` sites drop the `{error}` interpolation
- [ ] The 7 report-message sites (`audit.py:106,158`, `changed.py:229`, `phaseb.py:190,193`, `batches.py:164,175`, as of 2026-11-21) get scoped `except-interpolation` accept markers giving the reason
- [ ] Tests: an entry point's error output carries the cause
- [ ] Run the sweep and record the count in the commit body

**Acceptance Criteria:**

- [ ] No unaccepted `except-interpolation` hit remains
- [ ] Every test noted in the first subtask passes

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_driver.py claude/skills/auditme/tests/test_changed.py claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1

---

## Task 10: Small mechanical fixes and dead handlers

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Source Reference:** "The plan the coding standards settle", small mechanical fixes and dead handlers

**Technical Goal:** Clear the small rules the standards settle.

**Subtasks:**

- [ ] `typing-deprecated-alias` (3): `collections.abc`
- [ ] `bare-parametric-annotation` (2): `list[ast.stmt]`, `dict[str, object]`
- [ ] `leading-underscore-binding` (15) and `underscore-forloop-target-read` (1): `_` for unused bindings, `module` for the read loop target
- [ ] `non-alphabetical-literal` (16 to fix) and `non-alphabetical-dict-keys` (8): sort; split `FILESYSTEM_TOUCHING_CALLS` by its comment groups; leave `BASE_CANDIDATES` and `GIT_ENV_ARGS` for Task 14
- [ ] `mutable-module-level-exported`: `FILESYSTEM_TOUCHING_CALLS` as a frozenset (leave `REGISTRY` for Task 14)
- [ ] `in-function-import` (2): move to the top-level imports
- [ ] `filesystem-op-without-envelope` (2): wrap the `read_bytes` calls at `candidates.py:758` and `:1016` in `PhaseBError`
- [ ] `literal-duplication` in code (19): shared constants (`SINK_TOKENS`, the broad-handler names, `'*bare*'`, the `ImportError` pair, `['uv', 'lock', '--check']` and the rest); in tests (8): a conftest `git()` helper next to `GIT_ENV_ARGS`
- [ ] `paired-sibling-helpers` (2): one shared candidate helper in conftest
- [ ] `silent-broad-except` (36): remove the `try/except Exception` around `ast.unparse`; update the S112 comment in `pyproject.toml`
- [ ] Run the sweep and record the count in the commit body

**Acceptance Criteria:**

- [ ] None of the rules above reports a hit beyond those left for Task 14

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 4 to 9 (their refinements change which of these still fire)
- Line numbers are as of 2026-11-21; take current ones from the sweep

---

## Task 11: Cross-module renames and full import paths in code

**Status:** todo
**Priority:** medium
**Complexity:** large
**Source Reference:** "The plan the coding standards settle", Renames

**Technical Goal:** The 15 names shared across modules lose their leading
underscore, and the checker's code imports by full path.

**Subtasks:**

- [ ] Rename, everywhere they are used (code and tests): `_emit`, `_accept_reason`, `_relpath`, `_all_py_files`, `_source_lines`, `_audit_roots`, `_walk_within_scope`, `_type_checking_linenos`, `_accepted_lazy_imports`, `_EMITTED`, `_SIDE_EFFECT_CALL_NAMES` (core) and `_spec_markdown_files`, `_SPEC_SKIP_PARTS`, `_CLASS_LINE_RE`, `_DEF_LINE_RE` (`project_hygiene`); a name that would collide gets a new one
- [ ] Convert the code's `from auditme.core import ...` and the other code `from` imports to `import auditme.core` and qualified names, one module at a time
- [ ] Grep for each old name afterwards, in code, tests, docs and SKILL.md: none remains
- [ ] Run the sweep and record the count in the commit body

**Acceptance Criteria:**

- [ ] No old name is left anywhere in the repository
- [ ] No `from-import` hit remains in code

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 10
- About 530 references; commit per module if that keeps each diff readable

---

## Task 12: Module-local renames in code

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Source Reference:** "The plan the coding standards settle", Renames

**Technical Goal:** No leading-underscore definition, constant or attribute
is left in the checker's code.

**Subtasks:**

- [ ] Rename the remaining module-local functions, classes and constants, and `self._counts`, avoiding the collisions the review names (`_types` would shadow `types`; `_members`)
- [ ] Run the sweep: no `leading-underscore-*` hit remains in code except the docstring mentions left for Task 14

**Acceptance Criteria:**

- [ ] As above

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 11

---

## Task 13: Test helpers and test imports

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Source Reference:** "The plan the coding standards settle", Renames

**Technical Goal:** The tests follow the same standards: no leading-underscore
helpers and full import paths.

**Subtasks:**

- [ ] Rename the test helpers and constants (about 43), giving a colliding name a new one (`_candidate`, `_line`, `_read`, `_verdict`, `_git` -> `make_candidate` and the like)
- [ ] Convert the test `from` imports (`from auditme import phaseb` and the rest) to full paths, updating their references
- [ ] Drop the test's `_map` pass-through and call `testmap.build_test_map` directly
- [ ] Revisit the five accept markers in `test_core.py` for `leading-underscore-attribute-access`: remove each one the renames made unnecessary
- [ ] Run the sweep and record the count in the commit body

**Acceptance Criteria:**

- [ ] No `leading-underscore-*`, `from-import` or `passthrough-shim` hit remains in the tests

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 12

---

## Task 14: Accept the approved lines, reach zero, restore the gates

**Status:** todo
**Priority:** high
**Complexity:** small
**Source Reference:** A1-A12; the TODO item's Fix direction

**Technical Goal:** The sweep reports no unaccepted hit, the gates are back
on, and the backlog item is closed.

**Subtasks:**

- [ ] Add a scoped `# auditme: accept[<rule>] <reason>` marker, with the review's reason, on each line items A1 to A12 name
- [ ] Run the sweep: if any unaccepted hit remains that no task or item covers, stop the list as `blocked`, listing each by rule and `path:line`; do not accept it
- [ ] `.pre-commit-config.yaml`: restore `auditme-changed` to `stages: [pre-commit]` and `auditme-all` to `stages: [manual, pre-push]`, removing the pause comments
- [ ] Move "Fix or accept this repository's audit backlog" to the end of `DONE.md`: heading and body unchanged, then `Done: <date> - agents/reviews/audit-backlog-2026-11-21.md and agents/tasks/reviews/tasks-1.md; the sweep reports no unaccepted hit, and both gates are back on.`
- [ ] Say in the task's report that the repository is ready for its first audit (`/auditme`), and do not start it

**Acceptance Criteria:**

- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [ ] `.pre-commit-config.yaml` has both gates back on

**Definition of Done:**

- [ ] `pre-commit run --all-files` exits 0
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes
- [ ] `python3 ~/.claude/skills/todo-review/verify_bodies.py <baseline> TODO.md DONE.md` exits 0, with `<baseline>` the `TODO.md` of the commit that added this task list (`git show $(git log --diff-filter=A --format=%H -- agents/tasks/reviews/tasks-1.md):TODO.md`)

**Notes:**

- Depends on Tasks 2 to 13
