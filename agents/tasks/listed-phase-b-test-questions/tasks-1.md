# Tasks: Listed Phase B test questions

**Spec:** `agents/specs/listed-phase-b-test-questions/spec.md`
**Created:** 2026-11-20
**Version:** 1

Implements the whole spec, version 1.2: the shared helpers hoisted to
`core.py`, `is_private` (decision 1 of the spec), the test tree index
(`phaseb/testmap.py`), the T1 and T2 listers, their version 1 briefs, and the
`SKILL.md` changes that name T1 and T2 as listed.

The listers are modelled on the A4 lister that `agents/tasks/repeatable-phase-b/tasks-1.md`
builds and on the documentation listers of
`agents/tasks/listed-phase-b-documentation-questions/tasks-1.md`. They reuse
that work's `Candidate`, `Verdict`, `register_question`, ledger, batches,
command line and shared call resolver unchanged, and follow the module
layout the documentation-questions list leaves. The last task therefore has a
deduplication subtask.

No check is added to or removed from `CHECKS`, so
`claude/skills/auditme/checks/auditme/registry.py` and
`claude/skills/auditme/tests/registry-order.txt` stay as they are. No rule's
output changes: `_walk_within_scope`, `_SIDE_EFFECT_CALL_NAMES` and
`is_dunder_all_assignment` move to `core.py` verbatim and their rule modules
import them from there. Every existing test must pass unchanged; a task that
would need to change an existing test stops as `blocked` and names it.

Every task runs unattended: none calls an LLM, makes a network request or
reads another repository, and none stops for the operator. Running the T1 and
T2 listed path on a real project is the operator's step after the list ships,
not a task here.

The repository has no affected-tests tool. Each task names its own test
files; the last task runs every test tree the change can reach and saves the
run to the order's test log. Test commands run from the repository root.
Tests use neutral fixture names (`pkg`, `probe`, `Probe`), as the shared
repository's `no-project-names` hook requires.

---

## Task 1: Check the prerequisites and hoist the shared helpers into `core.py`

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Prerequisites; Module location (reused, not copied)

**Technical Goal:** Confirm the two specs this one builds on have shipped, then
move the rule-module helpers the new `phaseb` code needs into
`claude/skills/auditme/checks/auditme/core.py`, so `phaseb/` never imports a
rule module and no helper exists twice. The moves are verbatim: every rule's
output stays as it is.

**Subtasks:**

- [x] Prerequisite check: `grep -c '^\*\*Status:\*\* implemented' agents/specs/repeatable-phase-b/spec.md` prints `1`, `grep -c '^\*\*Status:\*\* implemented' agents/specs/listed-phase-b-documentation-questions/spec.md` prints `1`, and `python3 claude/skills/auditme/checks/phaseb.py candidates . --question A4` exits 0. If any fails, stop as `blocked`, naming the spec that is not `implemented` or the command that failed
- [x] Starting-point check: `grep -rnwE 'TestRef|build_test_map|is_private|t1_reasons|is_t2_candidate' claude/skills/auditme/checks` prints nothing and `claude/skills/auditme/checks/auditme/phaseb/testmap.py` does not exist; if either fails, stop as `blocked` and name what it found
- [x] Read where the earlier lists left things: the module that registers the A4 and documentation listers (`phaseb/candidates.py`, or the group module the documentation-questions list introduced), the shared call resolver's name and signature in `core.py`, and the names `phaseb/` already imports from `core.py`. Later tasks use these as they are
- [x] Tests first in `claude/skills/auditme/tests/test_core.py`, under a new `# scope walk` heading: `_walk_within_scope` imported from `auditme.core` yields an `if` in a function's body and not one inside a nested `def`, `lambda` or class. Run them and see them fail
- [x] Move `_walk_within_scope` from `claude/skills/auditme/checks/auditme/rules/error_handling.py` to `core.py` unchanged (name, docstring, body); `error_handling.py` imports it from `auditme.core`
- [x] Move `_SIDE_EFFECT_CALL_NAMES` from `claude/skills/auditme/checks/auditme/rules/state_and_effects.py` to `core.py` unchanged (same name, same members, still a `set`); `state_and_effects.py` imports it from `auditme.core`
- [x] Move `is_dunder_all_assignment` from `claude/skills/auditme/checks/auditme/rules/style_and_naming.py` to `core.py` unchanged, for Task 2's `is_private`; `style_and_naming.py` imports it from `auditme.core`, and the `non-alphabetical-literal` entry in `claude/skills/auditme/SKILL.md` that names its location is updated to `checks/auditme/core.py`
- [x] Skip any of these moves the documentation-questions list already made (the helper is defined in `core.py` and not in the rule module); a helper defined in both places is moved as above

**Acceptance Criteria:**

- [x] The new tests pass
- [x] `grep -rn 'def _walk_within_scope\|^_SIDE_EFFECT_CALL_NAMES\|def is_dunder_all_assignment' claude/skills/auditme/checks` shows each in `core.py` only
- [x] Every existing test in `test_error_handling.py`, `test_state_and_effects.py`, `test_style_and_naming.py` and `test_core.py` passes unchanged; if one would need a change, stop as `blocked` and name it

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/test_state_and_effects.py claude/skills/auditme/tests/test_style_and_naming.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on `agents/tasks/repeatable-phase-b/tasks-1.md` and `agents/tasks/listed-phase-b-documentation-questions/tasks-1.md` having merged to `main`
- The rule modules already import underscored helpers from `auditme.core` (`_emit`, `_relpath`, `_source_lines`), so the moved names keep their spelling, as the spec names them
- `state_and_effects.py` builds `BUILD_SIDE_EFFECTS = _SIDE_EFFECT_CALL_NAMES | {...}`; keeping the set's type keeps that line's result the same

---

## Task 2: `is_private` in `core.py`

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** API (`is_private`); Decisions 1; Implementation (Tests: `is_private`)

**Technical Goal:** Add `is_private(qualname, module, root)` to `core.py` with
decision 1's rule, early and with its own tests, because the T1 brief's
payload uses it here and the architecture-questions spec reuses it.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/test_core.py`, under a new `# is_private` heading, on fixture projects with `src/pkg/`: a function named in `src/pkg/__init__.py`'s `__all__` is not private; one left out of it is private, even with no leading underscore; one named in its module's own `__all__` is not private; a method's privacy follows its class's name (`Probe.load` is not private when `Probe` is named in an `__all__`); with no `__all__` in the package or the module, `pkg.mod.load` is not private and `pkg.mod._load`, `pkg._mod.load` and `pkg.mod.Probe._load` are; with an `__all__` that names it, `_load` is not private (the underscore counts only where no `__all__` exists); an annotated `__all__: list[str] = [...]` is read like a plain one. Run them and see them fail
- [x] Implement `is_private` in `claude/skills/auditme/checks/auditme/core.py` with the spec's signature and docstring, reading `__all__` through `is_dunder_all_assignment` (moved in Task 1) and locating the module's file with the same roots `_audit_roots` gives
- [x] Add `is_private` to `core.py`'s public names wherever the module lists them

**Acceptance Criteria:**

- [x] The new tests pass
- [x] `is_private` takes no leading underscore and needs nothing from `phaseb/` or a rule module

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/test_core.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- `module` is the dotted name `module_dotted` returns
- Which `__all__` files count is the spec's 1.2 docstring: the module's own and every package `__init__.py` above it; public when any names the first qualname segment, private when one has an `__all__` and none names it, the underscore fallback only when none has one

---

## Task 3: The test tree index: test files, imports and direct tests

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** API (`TestRef`, `build_test_map`); Implementation (Scope; Finding the tests, direct route); Error handling

**Technical Goal:** Create `claude/skills/auditme/checks/auditme/phaseb/testmap.py`
with the frozen `TestRef` dataclass and the first half of `build_test_map`:
find the test tree, parse each test file once, and map each package function
to the tests that call it directly, from the test function's body or a
fixture it requests.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_testmap.py`, on a fixture project with `src/pkg/` and `src/tests/`: a test calling `pkg.mod.load` after `from pkg.mod import load` gives a `direct` ref with the test's id (`src/tests/test_mod.py::test_load`), path and lines; a method `test_*` in a `Test*` class is found, with the id `path::TestProbe.test_load`; a test that requests a fixture calling `load`, defined in the same file or in a `conftest.py` above it, gives a `direct` ref; a test decorated with `given` imported from `hypothesis` has `property: true`, and one without has `false`; a same-named `load` called in a test file that imports neither the module nor the name adds no ref; a test call the resolver cannot follow is left out without an error; a project with neither `src/tests/` nor `tests/` gives an empty map; a test file or audited source file that does not parse raises `PhaseBError` naming the file; refs for a function come back sorted by id. Run them and see them fail
- [x] Add `TestRef` with the spec's fields and docstring, and the test tree walk: every `test_*.py` and `*_test.py` under `src/tests/` and `tests/`
- [x] Implement the direct route with the shared call resolver from `core.py`, starting from each test file's imports, so a bare name match is never evidence
- [x] Re-export the module's public names where `phaseb/__init__.py` lists the package's names

**Acceptance Criteria:**

- [x] The new tests pass
- [x] Each test file is parsed once per `build_test_map` call
- [x] Hypothesis is recognised by the name `given` imported from `hypothesis`; nothing imports hypothesis

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1 (the resolver's name and signature)
- Key code: the shared resolver and `_audit_roots`, `module_dotted` in `claude/skills/auditme/checks/auditme/core.py`; the A4 lister's use of the resolver in `phaseb/`
- The test file name `test_testmap.py` starts with `test_`; the names `TestRef` and `test_files` in package code are not tests, and pytest does not collect `TestRef` because it lives in the checker, not in a test module

---

## Task 4: Caller routes, `callers` and `test_files`

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** API (`build_test_map` depth; T1 payload `callers`, `test_files`); Implementation (Finding the tests, caller route and `test_files`); Settings (`--depth`)

**Technical Goal:** Finish `build_test_map`: a test that directly reaches a
package function whose resolved callees reach the target within `depth` gives
a `caller` ref with `via` set; and add the helpers the listers use for a
candidate's `callers` (package functions reaching it within `depth`) and its
`test_files`.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_testmap.py`: a test calling `run`, where `run` calls `load`, gives `load` a `caller` ref with `via` the id of `run`; a target three calls below the tested function is reached at depth 3 and not at depth 1; a function with both a direct test and a caller test keeps both refs; `callers` of `load` lists `run` with its `{id, path, start, end}` within depth and not beyond it; `test_files` is sorted and holds the mirrored test file (`src/pkg/mod.py` -> `src/tests/pkg/test_mod.py` where that layout exists), every test file importing the candidate's module and every test file importing a listed caller's module, and not a test file importing neither. Run them and see them fail
- [x] Implement the caller route over the package call graph the shared resolver gives (the A4 lister's `class_methods=True` use), following callees to `depth`
- [x] Implement the `callers` and `test_files` helpers in `testmap.py`

**Acceptance Criteria:**

- [x] The new tests pass
- [x] A cycle in the call graph terminates

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 3
- The mirror rule follows `claude/rules/python/testing.md`; check its wording for the mirrored path before writing the test

---

## Task 5: `t1_reasons`

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** API (`t1_reasons`); Implementation (T1 candidates); Implementation (Tests: T1 reasons)

**Technical Goal:** Implement `t1_reasons(node, cls)`: the reasons `if`,
`try`, `match` and `state` a function's own body gives, walked with
`_walk_within_scope` so a nested def's branches belong to the nested def.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_t1_candidates.py`: an `if` (and an `elif`) gives `if`; a `try` with an `except` handler (and a `try`/`except*`) gives `try`; a `match` gives `match`; an assignment to `self.state` where another method of the class tests `self.state` in an `if`, a `match` subject or a comparison gives `state`; a conditional expression, a comprehension filter, an `assert`, a `try`/`finally` alone, an assignment to an attribute no other method tests, and an `if` inside a nested def give no reason; reasons come back in a fixed order without repeats. Run them and see them fail
- [x] Implement `t1_reasons` with the spec's signature and docstring, in the module that holds the listers (Task 1 read which)

**Acceptance Criteria:**

- [x] The new tests pass
- [x] `t1_reasons` walks with `_walk_within_scope` imported from `auditme.core`, not a copy

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1

---

## Task 6: The T1 lister and its content hash

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** API (T1 registration and payload); Implementation (Scope; T1 candidates; Content hash); Error handling (no test tree); Decisions 1 and 2

**Technical Goal:** Register `T1`: every function or method under
`_audit_roots`, outside the test tree, with a non-empty `t1_reasons`, minus
`@typing.overload` stubs and defs under `if TYPE_CHECKING:`, with the payload
`reasons`, `tests`, `callers`, `test_files` and `private`, and a hash over its
source and its `test_files`.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_t1_candidates.py`, on a fixture project with `src/pkg/` and `src/tests/`: a branchy function is a candidate with id `src/pkg/mod.py::name`, its reasons, its direct and caller tests (each `TestRef` as a dict) and its `test_files`; a function in a test file, a `conftest.py`, a `test_*.py` or `*_test.py` or under a `tests` directory is never a candidate; an `@typing.overload` stub and a def under `if TYPE_CHECKING:` are not; `private` is `is_private`'s answer; a project with no test tree lists candidates with empty `tests`; adding a test to the mirrored test file changes the hash, and editing a test file that imports neither the module nor a caller's module does not; a second call returns the same candidates, order and hashes; `--depth` reaches the lister. Run them and see them fail
- [x] Implement the lister beside A4's, reusing `_audit_roots`, `module_dotted`, `_type_checking_linenos` and `is_private` from `core.py` and `build_test_map` from `testmap.py`
- [x] Compute the hash as the spec's Content hash section says: sha256 over the candidate's source, then each `test_files` file's full text in path order, NUL-separated
- [x] Register it as `T1` with the brief path `claude/skills/auditme/phaseb/briefs/T1.md` (written in Task 9)
- [x] Extend `claude/skills/auditme/tests/phaseb/test_cli.py` with one case: `phaseb.py candidates <fixture> --question T1` prints one JSON line per candidate

**Acceptance Criteria:**

- [x] The new tests pass
- [x] Every existing test under `claude/skills/auditme/tests/phaseb/` passes unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 2, 4 and 5
- The brief version is not part of the hash; the batch planner compares it beside the hash

---

## Task 7: `is_t2_candidate`

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** API (`is_t2_candidate`); Implementation (T2 candidates, rules 1-4); Decisions 3; Settings (lister constants)

**Technical Goal:** Implement `is_t2_candidate(node, package_types)` as the
spec's positive rule: a pure, non-async, non-generator module-level function
or `staticmethod` with parameters, whose every annotation is built from the
well-defined type set (with `str` and `bytes`, decision 3), with no side
effect in its own body, and a branch, loop or comprehension.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_t2_candidates.py`: a function over `int` returning `int` with an `if` is a candidate, as is one over a frozen `Probe` dataclass the package defines, one over `str` and `bytes`, one over `list[int] | None`, a `Literal[...]`, a package `Enum`, `NamedTuple` and `TypedDict` of such types, and a `staticmethod`; a function taking `pathlib.Path`, a non-frozen dataclass, a frozen dataclass with a `pathlib.Path` field, or an unannotated parameter is not; nor one returning `None`, with no parameters, `async`, a generator, or a method that is not a `staticmethod`; nor one calling `write_text`, `open`, `print`, `now` or a `random` or `subprocess` function, using `global` or `nonlocal`, or assigning to a parameter's attribute or subscript; nor one without a branch, loop or comprehension in its own body (one in a nested def does not count). Run them and see them fail
- [x] Implement `is_t2_candidate` with the spec's signature and docstring; keep the type set and the extra call names as module constants beside it, extending `_SIDE_EFFECT_CALL_NAMES` imported from `auditme.core`, not copying it
- [x] Follow package types' fields recursively, stopping on a type already being checked

**Acceptance Criteria:**

- [x] The new tests pass
- [x] `_SIDE_EFFECT_CALL_NAMES` is defined only in `core.py`

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- The type set and call names change only with a brief version bump (spec Settings); say so in the constants' comment

---

## Task 8: The T2 lister, `pairs`, `types` and its content hash

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** API (T2 registration and payload); Implementation (T2 candidates, `pairs`; Content hash)

**Technical Goal:** Register `T2`: every function `is_t2_candidate` accepts
under `_audit_roots`, outside the test tree, with the payload `params`,
`returns`, `types`, `pairs`, `tests` and `test_files`, and a hash over its
source, its `types` classes' source and its `test_files`.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_t2_candidates.py`, on a fixture project with `src/pkg/` and `src/tests/`: a candidate's `params` are `[{name, annotation}]` with the annotation's source text, `returns` likewise, and `types` lists each package class its annotations name (directly or through a field) as `{id, path, start, end}`; `parse_probe` and `format_probe` list each other in `pairs`, as do `encode`/`decode`, `to_x`/`from_x` and `dumps`/`loads`, and an unrelated candidate has no pair; a test file is never a candidate; a test decorated with hypothesis `given` calling the candidate appears in `tests` with `property: true`; adding a field to `Probe` changes the hash of a candidate over it, as does adding a test to the mirrored test file; a second call returns the same candidates, order and hashes. Run them and see them fail
- [x] Implement the lister beside T1's, building the package type map once per call and reusing `build_test_map` and the `test_files` helper from `testmap.py`
- [x] Compute the hash as the spec says: sha256 over the candidate's source, then each `types` class's source in id order, then each `test_files` file's full text in path order, NUL-separated
- [x] Register it as `T2` with the brief path `claude/skills/auditme/phaseb/briefs/T2.md` (written in Task 9)

**Acceptance Criteria:**

- [x] The new tests pass
- [x] Every existing test under `claude/skills/auditme/tests/phaseb/` passes unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 4, 6 and 7

---

## Task 9: The T1 and T2 briefs, version 1

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation (Briefs; Content hash, the note the brief carries); Decisions 1 and 2

**Technical Goal:** Write `claude/skills/auditme/phaseb/briefs/T1.md` and
`T2.md`, each with its question verbatim from `SKILL.md`, its thresholds, the
input and output format and `**Brief version:** 1`.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_briefs.py`: each of the T1 and T2 briefs contains its question's text as it stands in `claude/skills/auditme/SKILL.md` and has exactly one `**Brief version:** 1` line (the existing every-registered-brief test then covers both). Run them and see them fail
- [x] Write `T1.md`: the input (a batch of candidates with `reasons`, `tests`, `callers`, `test_files`, `private`); the question; the thresholds (covered when a listed `direct` test calls it, or, for a candidate with `private: true`, a `caller` test reaches it; an unconditionally skipped or `xfail` test does not count; read `test_files` for calls the map could not follow); the output (one JSON line per candidate with `id`, `findings` as `{"missing": ["test case"]}` or `{"missing": []}`, and a `reason` naming the covering test's id, every candidate present)
- [x] Write `T2.md`: the input (`params`, `returns`, `types`, `pairs`, `tests`, `test_files`); the question; the thresholds (covered when a test with `property: true` calls it directly; flagged only when the reason states a property the domain supports - a round trip with a `pairs` entry, idempotence, an output invariant, a simpler oracle, a bound - and with none statable not flagged, the reason saying why; whether the project declares hypothesis does not change the verdict); the output (`findings` as `{"missing": ["property test"]}` or `{"missing": []}`, with `id` and `reason`, every candidate present)
- [x] In both: a test in a file that imports neither the module nor a caller's module does not re-plan a candidate, and `--rejudge` covers it; a threshold the brief does not settle is reported in the reply, not decided
- [x] In both, repeat the security rule every subagent brief carries: never list environment variables (`env`, `printenv`, `set`) or print an env file; to test that a variable is set, use `[ -n "${VAR:-}" ]` and print only yes or no

**Acceptance Criteria:**

- [x] The new tests pass
- [x] Neither brief names a project, path or review other than this repository's own

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 6 and 8
- Model the layout on `claude/skills/auditme/phaseb/briefs/A4.md` and the documentation briefs beside it

---

## Task 10: `SKILL.md`: T1 and T2 listed

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation (Skill changes)

**Technical Goal:** Update `claude/skills/auditme/SKILL.md` so T1 and T2 run
on the listed path, and record T2's candidate rule as a refinement.

**Subtasks:**

- [x] In section 4, Interpretive review, add T1 and T2 to the questions with a lister, in the form the documentation-questions list left, so they lose `(sampled)`
- [x] Under "Refining a predicate", add a dated entry (the date of the commit) recording T2's candidate rule as the predicate's reading of "well-defined domains", naming `is_t2_candidate` and the module that holds it
- [x] Say that the first audit after this change judges every T1 and T2 candidate as new, and that its findings are coverage, not drift
- [x] Add `test_testmap.py`, `test_t1_candidates.py` and `test_t2_candidates.py` to `claude/skills/auditme/tests/README.md`'s description of the test tree

**Acceptance Criteria:**

- [x] `grep -n 'T1\|T2' claude/skills/auditme/SKILL.md` shows neither marked `(sampled)`
- [x] The T1 and T2 question texts in the Phase B checklist are unchanged, so Task 9's verbatim tests still pass

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/phaseb/test_briefs.py -q -p no:cacheprovider` passes
- [x] `uv run --group docs mkdocs build --strict` passes

**Notes:**

- Depends on Tasks 6, 8 and 9

---

## Task 11: Whole-tree checks, deduplication, close the spec and save the test log

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** whole spec

**Technical Goal:** Remove any duplication the new modules introduced, run
every check the change can reach, mark the spec implemented, and save the
final full test run to the order's test log in the main checkout.

**Subtasks:**

- [x] Hoist anything `testmap.py` and the T1 and T2 listers duplicate from the rule modules, `core.py` or the A4 and documentation listers to a single owner: grep the tree for each literal collection, constant and one-line helper the new code defines (the test-file name patterns, the import-binding reading, the type-checking and overload filters especially), and import rather than copy. Choose the owner from the existing import graph; prefer a module the consumer already imports over adding a new edge. A helper `phaseb/` uses from a rule module moves to `core.py`, the rule importing it from there, with that rule's tests passing unchanged; a move that would need an existing test changed stops as `blocked`, naming the test
- [x] Confirm no helper moved to `core.py` stays defined twice: `grep -rn 'def _walk_within_scope\|^_SIDE_EFFECT_CALL_NAMES\|def is_dunder_all_assignment\|def is_private' claude/skills/auditme/checks` shows each in `core.py` only
- [x] Run `python3 claude/skills/auditme/checks/phaseb.py candidates . --question T1` and `... --question T2` from the repository root and check each exits 0 and that each line it prints parses as JSON with the `id`, `hash` and `payload` keys (a repository with no audit root prints none)
- [x] Confirm `claude/skills/auditme/tests/registry-order.txt` is unchanged against the branch's base (`git diff <base> -- claude/skills/auditme/tests/registry-order.txt` prints nothing)
- [x] Set the spec's `**Status:**` to `implemented` in `agents/specs/listed-phase-b-test-questions/spec.md`
- [x] Run the final full test run and save it to the order's test log in the main checkout (the list runs in a worktree), printing the pass line only on exit 0:
      `MAIN=$(git worktree list --porcelain | sed -n '1s/^worktree //p'); LOG="$MAIN/logs/rro/listed-phase-b-test-questions/tasks-1/final-tests.log"; mkdir -p "$(dirname "$LOG")"; uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests claude/skills/project-setup/tests tests -q -p no:cacheprovider 2>&1 | tee "$LOG"; [ "${PIPESTATUS[0]}" -eq 0 ] && echo 'all selected test directories passed' | tee -a "$LOG"`

**Acceptance Criteria:**

- [x] No literal collection or helper is defined both in `phaseb/` and elsewhere under `claude/skills/auditme/checks/`
- [x] The spec's status is `implemented`
- [x] The test log ends with `all selected test directories passed`

**Definition of Done:**

- [x] `pre-commit run --all-files` exits 0
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [x] The final test run above exits 0 and its log ends with the pass line
- [x] `uv run --group docs mkdocs build --strict` passes

**Notes:**

- Depends on Tasks 1-10
- No `TODO.md` item moves to `DONE.md` here: the item "Put the Phase B questions that find most onto the listed path" stays open, because the architecture-questions list, which runs later in the order, closes it
- `logs/rro/` lies in the main checkout, outside the worktree's tree, and `.gitignore` ignores `logs/`, so the log is never staged with the task's commit

---
