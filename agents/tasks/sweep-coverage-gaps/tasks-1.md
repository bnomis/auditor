# Tasks: Sweep coverage gaps

**Spec:** `agents/specs/sweep-coverage-gaps/spec.md`
**Created:** 2026-11-24
**Version:** 1

Implements the whole spec, version 1.0, approved on 2026-11-24 (every item
approved, `agents/reviews/sweep-coverage-gaps-spec-2026-11-24.md`). Each of
the seven changes is one task; the last task closes the list. No task decides
anything: where a task meets a case the spec does not name, it stops as
`blocked` for the operator, naming the case.

Every existing test must pass unchanged, except those built on
`ASYMMETRIC_HELPER` in `claude/skills/auditme/tests/test_error_handling.py`,
which Task 6 changes as the spec allows. A task in which any other existing
test's expected output changes stops as `blocked`, naming the test and the
output before and after; it never edits the test to pass.

Each task ends with this repository's whole-tree sweep clean
(`pre-commit run auditme-all --hook-stage manual --all-files`): a new hit the
task's change finds here is fixed, or accepted with a reason, in the same
task. Each task updates its own rule's row in `docs/guide/checker.md` and the
`SKILL.md` text the spec names, so `claude/skills/auditme/tests/test_registry.py`
(rule ids against the source and the guide) holds after every task.

Every task runs unattended: none calls an LLM, makes a network request or
reads another repository. The repository has no affected-tests tool: each task
names its own test files and the test files that import the module it
changes; the last task runs every test tree. Commands run from the repository
root. Fixtures use neutral names (`probe`, `Probe`), as the `no-project-names`
hook requires.

The `TODO.md` item "The sweep misses seven patterns one project's audits found
by hand" stays open after this list: it moves to `DONE.md` only when the
operator deletes the `requests.md` entry after running the sweep on the
projects that use the hooks (the spec's "After this ships"), which is outside
this repository and this list.

---

## Task 1: Read bare generics inside a subscript

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation 1; Testing 1

**Technical Goal:** `bare-parametric-annotation` reports `list[dict]`,
`dict[str, dict]` and `list[list]`, and still skips `Literal[...]`, `Annotated`
metadata and string forward references.

**Subtasks:**

- [x] Starting-point check: `grep -rnwE 'check_discarded_tuple_return|discarded-tuple-return' claude/skills/auditme/checks` prints nothing; if it prints anything, stop as `blocked` and name it
- [x] Tests first in `claude/skills/auditme/tests/test_style_and_naming.py`, the cases of the spec's Testing 1; run them and see the three hit cases fail
- [x] In `bare_parametric_annotation_in_file` (`claude/skills/auditme/checks/auditme/rules/style_and_naming.py`), descend into a `Subscript`'s slice (each element of a `Tuple` slice, or the slice itself) instead of returning; skip `Literal` by tail name, read only the first argument of `Annotated`, and do not read a string constant. Keep one hit per line
- [x] Update the rule's docstring and its row in `docs/guide/checker.md`

**Acceptance Criteria:**

- [x] The spec's Testing 1 cases pass; `test_a_parametric_annotation_is_not_a_hit` and `test_one_line_with_two_bare_annotations_reports_once` pass unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_style_and_naming.py claude/skills/auditme/tests/test_registry.py -q -p no:cacheprovider` passes
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0

**Notes:**

- `core.BARE_GENERIC_NAMES` is also read by `state_and_effects.py`; the set does not change

---

## Task 2: Add `TypeError` and `FileNotFoundError` to the stdlib raises

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation 3; Testing 3

**Technical Goal:** `layer-has-domain-error-raises-stdlib` reports `TypeError`
and `FileNotFoundError` as A3 asks.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/test_error_handling.py`, beside `test_raising_stdlib_where_the_package_has_a_domain_error_is_a_hit`: the spec's Testing 3 cases; see the two hit cases fail
- [x] Set `STDLIB_EXCS` in `check_layer_has_domain_error_but_raises_stdlib` (`claude/skills/auditme/checks/auditme/rules/error_handling.py`) to the five names, sorted; make the docstring name the same five
- [x] Add `FileNotFoundError` to A3's list in `claude/skills/auditme/SKILL.md`

**Acceptance Criteria:**

- [x] The spec's Testing 3 cases pass; the existing tests of the rule pass unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/test_registry.py -q -p no:cacheprovider` passes
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0

**Notes:**

- `claude/skills/auditme/checks/auditme/phaseb/batches.py` already carries accept markers for this rule; a new hit in this repository is fixed or accepted with a reason in this task

---

## Task 3: Add the `discarded-tuple-return` rule

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** API; Implementation 2; Testing 2

**Technical Goal:** A package function annotated `-> tuple[A, B, ...]` called
as a bare statement is a hit, as the spec's API docstring defines; A23 names
the rule as its mechanical part.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/test_state_and_effects.py`: the spec's Testing 2 cases; see them fail
- [x] Add `check_discarded_tuple_return` to `claude/skills/auditme/checks/auditme/rules/state_and_effects.py` with the spec's signature and docstring; resolve calls as `check_raises_section_drift` does (`auditme.core.resolve_call` with `class_methods=True`, `call_bindings`, `reexport_aliases`); variant and `related` as the spec's API says
- [x] Register it: `CHECKS` in `claude/skills/auditme/checks/auditme/registry.py` and `claude/skills/auditme/tests/registry-order.txt` (appended at the end), `RULE_IDS`, `CROSS_FILE_RULES` in `claude/skills/auditme/tests/test_registry.py`, and a row in `docs/guide/checker.md`
- [x] Add a sentence to A23 in `claude/skills/auditme/SKILL.md` naming the rule as its mechanical part; the dataclass and partial-use cases stay Phase B

**Acceptance Criteria:**

- [x] The spec's Testing 2 cases pass, including `related` on the cross-module hit
- [x] `test_registry.py` passes with the new id in the source, `RULE_IDS` and the guide

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_state_and_effects.py claude/skills/auditme/tests/test_registry.py claude/skills/auditme/tests/test_driver.py -q -p no:cacheprovider` passes
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0

---

## Task 4: Widen `assert-never-missing`

**Status:** done
**Priority:** medium
**Complexity:** medium
**Spec Reference:** Implementation 4; Testing 4

**Technical Goal:** The rule reads dotted subjects, `in` arms, a two-arm chain
on a `Literal` of three or more string members, and `match`, as the spec
lists; an unannotated two-arm chain stays exempt.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/test_state_and_effects.py` (the spec's Testing 4 rule cases) and `claude/skills/auditme/tests/phaseb/test_architecture_candidates.py` (A11 no longer lists a chain the rule now hits); see them fail
- [x] Change `check_assert_never_missing`, `if_chain` and `extract_string_eq_var` in `claude/skills/auditme/checks/auditme/rules/state_and_effects.py` as Implementation 4 says; read the `Literal` from the enclosing function's parameter annotation or a same-scope `AnnAssign`
- [x] Update the rule's docstring and its row in `docs/guide/checker.md`

**Acceptance Criteria:**

- [x] The spec's Testing 4 cases pass; `test_a_two_arm_chain_is_legitimately_bi_valued` and `test_a11_drops_a_chain_the_assert_never_rule_flags` pass unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_state_and_effects.py claude/skills/auditme/tests/phaseb/test_architecture_candidates.py claude/skills/auditme/tests/test_registry.py -q -p no:cacheprovider` passes
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0

**Notes:**

- `if_chain` is shared with the A11 lister (`claude/skills/auditme/checks/auditme/phaseb/architecture.py`); a change that alters what A11 lists for a chain the rule does not hit stops the task as `blocked`

---

## Task 5: Read I/O in the pure-name rules

**Status:** done
**Priority:** medium
**Complexity:** medium
**Spec Reference:** Implementation 5; Testing 5

**Technical Goal:** `pure-name-has-side-effect` reads the I/O A9 defines and
skips registered checks; `build-name-has-side-effect` reads `make_`.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/test_state_and_effects.py`: the spec's Testing 5 cases; see them fail
- [x] Add `PURE_NAME_IO_CALLS` beside `check_pure_name_has_side_effect` in `claude/skills/auditme/checks/auditme/rules/state_and_effects.py` with the calls Implementation 5 lists; read it besides `SIDE_EFFECT_CALL_NAMES`, which does not change
- [x] Skip a `check_` function registered as Implementation 5 says (a member of a module-level tuple, list, set or dict-value literal in the corpus, or decorated by a package function)
- [x] Add `make_` to the build rule's prefixes and to A9's prefix list in `claude/skills/auditme/SKILL.md`
- [x] Correct `check_pure_name_has_side_effect`'s docstring to the prefixes and calls it reads; update both rules' rows in `docs/guide/checker.md`

**Acceptance Criteria:**

- [x] The spec's Testing 5 cases pass; `test_a_load_function_may_do_io` and the T2 lister's tests pass unchanged
- [x] The whole-tree sweep reports no new unaccepted hit for `check_ruff`, `check_lockfile` or `check_ruff_version`

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_state_and_effects.py claude/skills/auditme/tests/phaseb/test_t2_candidates.py claude/skills/auditme/tests/test_registry.py -q -p no:cacheprovider` passes
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0

**Notes:**

- `SIDE_EFFECT_CALL_NAMES` is shared with the build rule and the T2 lister (`claude/skills/auditme/tests/phaseb/test_t2_candidates.py`), which is why the new calls go in their own constant

---

## Task 6: Require something to translate in `asymmetric-exception-translation`

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Implementation 6; Testing 6

**Technical Goal:** A callee is a hit only when its own body makes a call that
can raise what its callers translate, and not when it translates through a
same-module translator.

**Subtasks:**

- [x] Change `ASYMMETRIC_HELPER` in `claude/skills/auditme/tests/test_error_handling.py` to read a file (`pathlib.Path(name).read_text()`), and add the spec's two Testing 6 non-hit cases; see them fail
- [x] In `check_asymmetric_exception_translation` (`claude/skills/auditme/checks/auditme/rules/error_handling.py`), require a call in the callee's own body (nested defs skipped) to a `FILESYSTEM_TOUCHING_CALLS` name, a subprocess call, or a call rooted at a module imported from outside the swept package; skip a callee that calls a same-module function `translator_envelopes` lists
- [x] Update the docstring, the rule's row in `docs/guide/checker.md`, and add a dated entry under "Documented refinements" in `claude/skills/auditme/SKILL.md`

**Acceptance Criteria:**

- [x] The tests built on `ASYMMETRIC_HELPER` pass with the changed fixture, and the two new non-hit cases pass

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/test_registry.py -q -p no:cacheprovider` passes
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0

**Notes:**

- BLOCKED 2026-11-24: `claude/skills/auditme/tests/test_registry.py::test_exactly_the_cross_file_rules_emit_related` now fails. Its fixture `src/probe/setup.py` is `def setup_experiment(name: str) -> int: return len(name)`, which has nothing to translate, so `asymmetric-exception-translation` no longer emits `related` for it. Before: the emitting set equalled `CROSS_FILE_RULES`; after: it lacks `asymmetric-exception-translation`. The test is not built on `ASYMMETRIC_HELPER`, so this list forbids editing it; Task 9 asks the operator to allow the fixture change. The implementation, the docstring, the guide row and the `SKILL.md` entry are done and uncommitted.
- Unblocked 2026-11-24: the operator approved the fixture change Task 9 asks for; with it, both test files pass and the whole-tree sweep is clean.

---

## Task 7: List a submodule's `__all__` for A17

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Spec Reference:** Implementation 7; Testing 7

**Technical Goal:** The A17 lister also lists a submodule with a module-level
`__all__`, with consumers from any other file outside the test tree; the A17
brief covers the case and goes up one version.

**Subtasks:**

- [ ] Tests first in `claude/skills/auditme/tests/phaseb/test_architecture_candidates.py`: the spec's Testing 7 lister cases; see them fail
- [ ] In `list_a17_candidates` (`claude/skills/auditme/checks/auditme/phaseb/architecture.py`), list a submodule with a module-level `__all__` as Implementation 7 says; leave every `__init__.py` candidate's id and hash as they are
- [ ] In `claude/skills/auditme/phaseb/briefs/A17.md`, add the submodule case to the question and input text and raise `**Brief version:**` by one; mirror the question text in A17 in `claude/skills/auditme/SKILL.md`

**Acceptance Criteria:**

- [ ] The spec's Testing 7 cases pass; `test_a17_lists_an_all_init_with_its_consumers` and `test_a17_leaves_out_a_test_tree_reader_and_its_hash` pass unchanged
- [ ] `claude/skills/auditme/tests/phaseb/test_briefs.py` passes on the new brief version

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0

---

## Task 8: Close the list

**Status:** todo
**Priority:** medium
**Complexity:** small
**Spec Reference:** Testing; After this ships

**Technical Goal:** Run every check once over the whole branch, and mark the
spec implemented.

**Subtasks:**

- [ ] Run every test tree, with its log kept:
      `MAIN=$(git worktree list --porcelain | sed -n '1s/^worktree //p'); LOG="$MAIN/logs/rro/sweep-coverage-gaps/tasks-1/final-tests.log"; mkdir -p "$(dirname "$LOG")"; uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider 2>&1 | tee "$LOG"; [ "${PIPESTATUS[0]}" -eq 0 ] && echo 'all selected test directories passed' | tee -a "$LOG"`
- [ ] Read the "Documented refinements" and rule rows changed by Tasks 1 to 7 once more against the code, and fix any that disagree
- [ ] Set the spec's `**Status:**` to `implemented`
- [ ] Add a `Note 2026-MM-DD:` line (the day this task runs) to the `TODO.md` item saying the checker work shipped and the item waits on the operator's runs and the `requests.md` entry's deletion; change nothing else in the item

**Acceptance Criteria:**

- [ ] `$MAIN/logs/rro/sweep-coverage-gaps/tasks-1/final-tests.log` ends with `all selected test directories passed`

**Definition of Done:**

- [ ] `pre-commit run --all-files` exits 0
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [ ] The final test command above exits 0 and prints `all selected test directories passed`
- [ ] `uv run --group docs mkdocs build --strict` passes
- [ ] `python3 ~/.claude/skills/todo-review/verify_bodies.py <baseline> TODO.md DONE.md` exits 0, where `<baseline>` is `TODO.md` at the commit that added this list: `git show $(git log --diff-filter=A --format=%H -- agents/tasks/sweep-coverage-gaps/tasks-1.md):TODO.md`

**Notes:**

- Depends on Tasks 1 to 7

---

## Task 9: Change the registry cross-file fixture for Task 6

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Implementation 6

**Technical Goal:** `test_exactly_the_cross_file_rules_emit_related` keeps `asymmetric-exception-translation` in its emitting set with a fixture that has something to translate.

**Subtasks:**

- [x] Operator approves editing the existing test (the task list forbids it otherwise)
- [x] In `claude/skills/auditme/tests/test_registry.py`, change the `src/probe/setup.py` fixture to read a file (`import pathlib` and `pathlib.Path(name).read_text()`); `CROSS_FILE_RULES` does not change

**Acceptance Criteria:**

- [x] `test_registry.py` passes; Task 6 can then be committed and set to `done`

**Notes:**

- Depends on the operator's approval; blocks Task 6's commit
- Approved by the operator on 2026-11-24 ("unblock task 6"); done in Task 6's commit
