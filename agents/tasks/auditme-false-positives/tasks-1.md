# Tasks: Auditme false positives

**Spec:** `agents/specs/auditme-false-positives/spec.md`
**Created:** 2026-11-01
**Version:** 1

Implements the whole spec: five narrowings of the auditme checker, the two
shared helpers they need, the documentation, and the closing move of the
`TODO.md` item "auditme rules report hits the code does not have", which
points at this list.

Every change only narrows what a rule reports. Each narrowing task writes its
tests first and sees them fail: a test that the carve-out does not fire, and
a neighbouring test that the unrefined shape still fires. Every existing test
in the touched test files must pass unchanged; a task that needs to change an
existing test stops as `blocked` and names it.

No check is added or removed, so `CHECKS` in
`claude/skills/auditme/checks/auditme/registry.py` and
`claude/skills/auditme/tests/registry-order.txt` stay as they are.

The repository has no affected-tests tool. Each task names its own test
files; the last task runs every test tree the checker's change can reach.
Test commands run from the repository root.

---

## Task 1: Hoist the package class tree into shared helpers

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** API (`package_class_parents`, `class_lineage`)

**Technical Goal:** Move the class-tree logic out of the closure inside
`check_raises_section_drift` into module-level helpers, so Task 4 can use the
same lineage for `missing-raises-section`. Behaviour does not change.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/test_error_handling.py`, under a new `# package_class_parents and class_lineage` heading: a base written `Base` and one written `mod.Base` both give `Base`; classes from two modules are pooled; `class_lineage` returns the name and every ancestor transitively; a cycle (`A(B)`, `B(A)`) terminates; an unknown name gives `{name}`. Run them and see them fail
- [x] In `claude/skills/auditme/checks/auditme/rules/error_handling.py`, add `package_class_parents(trees: Iterable[ast.Module]) -> dict[str, set[str]]` and `class_lineage(name: str, parents: Mapping[str, set[str]]) -> set[str]` with the spec's signatures and docstrings, beside `module_tuple_constants`
- [x] Replace the `package_classes`/`parents` construction and the `ancestors` closure in `check_raises_section_drift` with calls to the helpers; keep `is_domain` reading the same set of top-level class names

**Acceptance Criteria:**

- [x] The new tests pass
- [x] Every existing `raises-section-drift` test passes unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_error_handling.py -q -p no:cacheprovider` passes

**Notes:**

- Key code: `check_raises_section_drift` (the class tree is built near its top, `ancestors` and `is_domain` are inner functions)
- Tests use the `project` and `run_check` fixtures in `claude/skills/auditme/tests/conftest.py`; the helpers can be tested directly on `ast.parse` trees

---

## Task 2: `raises-section-drift` skips errors guarded by unset optional arguments

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation 1 (amendment 1.1); API (`unset_optional_guard`); Error handling

**Technical Goal:** A callee error whose every raise is guarded by an optional
parameter that the call leaves unset no longer reaches that caller, as the
operator decided on 2026-11-01 (spec amendment 1.1).

**Subtasks:**

- [x] Rework the uncommitted tests from the first attempt (see Notes) to the 1.1 shapes, beside the existing drift tests, using the `drift` helper with `ERRORS` and a callee `load(name, strict=False)` of its own that raises `ParseError` only under `if strict:`: no omission hit for a caller calling `load('x')`, or `self.load('x')` on a method `load(self, name, strict=False)`; still one omission hit for `load('x', True)`, `load('x', strict=True)` and `load(*args)`; still one hit when the guard tests a parameter without a default, a module-level name, or when the name is also raised outside the guard; still one hit when the callee only documents `ParseError` and raises it through its own callee. Run them and see the "no hit" cases fail
- [x] Replace the first attempt's `argument_dependent` with `unset_optional_guard(func, error, parents, call, bound) -> bool`, with the spec's signature and docstring. Walk `func`'s own scope only; a raise counts when `_raised_name` gives a name whose `class_lineage` contains `error`; it is skipped when an enclosing `If` (body or `orelse`) or `Match` inside `func` has a test or subject reading a `Name` that is a parameter with a default (positional with a default, or keyword-only with a default) not supplied by `call`: no keyword names it, no positional argument reaches its position (offset by one with `bound`), and `call` has no `Starred` argument and no `**` keyword
- [x] In `check_raises_section_drift`, keep a map from qualname to `FunctionDef` while collecting subjects; where a resolved callee's documented name would reach the caller, skip it when `unset_optional_guard(callee_node, name, parents, call, bound)`, with `bound` true for a call resolved through `self.`. A qualname with no `FunctionDef` is never skipped. Omissions only: leave the extra-declaration branch alone
- [x] Add a `Refinement (2026-11-01): ...` paragraph to `check_raises_section_drift`'s docstring stating the carve-out, and that other value-dependent cases are left to the Phase B review (A4)

**Acceptance Criteria:**

- [x] Every case above passes
- [x] Every existing `raises-section-drift` test passes unchanged, including the five that the first attempt broke: `test_a_callee_error_missing_from_raises_is_a_hit`, `test_a_callee_error_names_the_callee_file_as_related`, `test_a_method_call_on_self_follows_the_method`, `test_a_scoped_marker_accepts_raises_drift`, `test_a_function_re_exported_by_a_package_init_is_followed`

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_error_handling.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- The drift rule never reads a callee's body today; it uses only the callee's documented `Raises:` (`raises_section_names`). This task adds the one body read the decision needs
- The decision covers only errors guarded by optional arguments the call leaves unset. It does not cover evaluating the caller's values or guards (fixed names, pre-checked values, dispatch types); those stay hits
- 2026-11-01, unblocked by the operator: the first attempt implemented the 1.0 predicate (any parameter guard), which also covered plain input validation and broke the five tests above. The operator chose to narrow the carve-out to unset optional arguments (spec amendment 1.1). The first attempt's code and tests are in the working tree, uncommitted; rework them rather than starting over

---

## Task 3: `raises-section-drift` follows called nested functions

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation 2; API (`nested_call_sites`)

**Technical Goal:** An error a nested function catches and re-raises on one
branch, called by the subject, reaches the subject's callers; a bare `raise`
inside a def defined in a handler no longer makes that handler re-raise.

**Subtasks:**

- [x] First, reproduce finding 2 in the shape the operator confirmed on 2026-11-01 (see Notes): the subject `run(text, other, strict)` declares `ParseError` in `Raises:`; it defines a nested `attempt()` that calls `probe.parse.parse(text)` inside `try:` with `except probe.errors.ParseError:` re-raising it with a bare `raise` under `if strict:` and otherwise returning 0; the subject also has its own `try: probe.parse.parse(other)` / `except probe.errors.ParseError: pass`; and it ends `return attempt()`. Today this gives exactly one hit, `run: Raises: declares ParseError, which never reaches the caller`. Run the test and see it fail (the test asserts no hit)
- [x] Further tests: a nested def that is defined but never called adds nothing (an omission hit for the subject does not appear because of it); a call to the nested def inside the subject's own `try`/`except ParseError` that does not re-raise means `ParseError` does not reach; a handler in the subject that defines a nested def containing a bare `raise`, and itself does not re-raise, catches. Run them and see the new-behaviour cases fail
- [x] Add `nested_call_sites(func)` with the spec's signature and docstring: `_reach_sites(func.body)`, plus, for each call by bare `Name` to a def nested directly in `func.body`, that def's `_reach_sites(def.body)` with the call's levels prepended; one level deep
- [x] In `check_raises_section_drift`, use `nested_call_sites(node)` in place of `_reach_sites(node.body)`
- [x] Change `_handler_passes_on` to search the handler with `_walk_within_scope` rather than `ast.walk`, so a raise inside a def, lambda or class defined in the handler does not count; a bare `raise` under an `if` in the handler still does
- [x] Extend the `Refinement (2026-11-01)` paragraph in `check_raises_section_drift`'s docstring with the nested-function case

**Acceptance Criteria:**

- [x] The reproduction test no longer gives the hit, and every case above passes
- [x] Every existing `raises-section-drift` and translator-envelope test passes unchanged (both use handler helpers)

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_error_handling.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- 2026-11-01, unblocked by the operator session: the first attempt's probe lacked the subject's own catching handler, and the extra-declaration branch fires only when some `try` level in the subject catches the error without re-raising, so it gave no hit. The reported site, read in the project that found it, has such a handler on another call, and its error reaches the caller only through the nested def's conditional bare `raise`. The shape in the first subtask was run against this worktree's checker at commit `338aa44` and gives the one hit above; the fix in the later subtasks (following called nested defs) covers it
- `_reach_sites` skips nested defs, lambdas and classes today, and `_handler_passes_on` uses `ast.walk`, which enters them; `_walk_within_scope` is the existing scope-bounded walk in the same module
- Check every caller of `_handler_passes_on` (grep it) before changing it

---

## Task 4: `missing-raises-section` ignores caught raises

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation 3

**Technical Goal:** A raise that a handler around it catches, by its own
class or a base class, no longer counts as reaching the caller, and a nested
def's raise counts only where the nested def is called.

**Subtasks:**

- [x] Tests first, beside the existing `missing-raises-section` tests (an `errors.py` with `ProbeError` and `ParseError(ProbeError)`, and a module using them): no hit when `raise ParseError(...)` sits in a `try` whose handler catches `ParseError`, `ProbeError`, `Exception` or a bare `except:` without re-raising; no hit when a nested def raises it and the nested def's only call sits in such a `try`; no hit when a nested def raises it and is returned but never called in the subject (the nested def is still reported as its own subject when it has a docstring without `Raises:`); still a hit when the handler re-raises, catches an unrelated class, or there is no handler; still a hit for a nested def called outside any `try`. Run them and see the "no hit" cases fail
- [x] In `check_missing_raises_section`, build the parents table once per package with `package_class_parents`; for each subject (still every function at any depth), take sites from `nested_call_sites(node)`; a `Raise` site counts when its name passes today's test and no handler level at the site catches `class_lineage(name, parents)` (`_level_catches`, which treats a bare `except:`, `Exception` and `BaseException` as catching)
- [x] Keep the `__init__.py`/`errors.py` skip and the `Raises:` marker regex as they are
- [x] Add a docstring paragraph `Refinement (2026-11-01): ...` stating the carve-out

**Acceptance Criteria:**

- [x] Every case above passes
- [x] The existing `missing-raises-section` tests pass unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_error_handling.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 1 and 3
- The rule reads one file at a time today; the parents table needs every module of the package, as `check_raises_section_drift` builds it

---

## Task 5: `passthrough-shim` flags only real forwarding

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Implementation 4

**Technical Goal:** A wrapper that computes or repeats an argument, or is
decorated, is no longer reported as a pass-through shim.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/test_imports_and_surfaces.py`, beside the existing shim tests: no hit for `return table.get(name, name)`; no hit for a keyword argument with a computed value (`f(x, size=len(x))`) or a `**kwargs` keyword; no hit for a function decorated `@pytest.fixture`, `@pytest.fixture(scope='module')`, or any other decorator; still a hit for `return f(a, b)` and for `return f(a, key=key)` with `a` and `key` parameters. Run them and see the "no hit" cases fail
- [x] In `check_passthrough_shim`: skip a function with any decorator; require every keyword to have a name (`kw.arg is not None`) and a value that is a `Name` of one of the wrapper's parameters; require that no parameter appears twice across positional and keyword arguments
- [x] Add a docstring paragraph `Refinement (2026-11-01): ...` stating the carve-out and why a decorator excludes a function (it registers the function for something else)

**Acceptance Criteria:**

- [x] Every case above passes
- [x] The existing `passthrough-shim` tests pass unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_imports_and_surfaces.py -q -p no:cacheprovider` passes

**Notes:**

- Key file: `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py`, `check_passthrough_shim`
- Skipping every decorator, not only `@pytest.fixture`, is the spec's choice

---

## Task 6: `non-alphabetical-literal` accepts ruff's `__all__` order

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Implementation 5; API (`ruff_dunder_all_key`)

**Technical Goal:** An `__all__` sorted the way ruff's RUF022 sorts it is no
longer reported.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/test_style_and_naming.py`, beside the existing literal tests: `__all__ = ['X_Y', 'Thing', '_private', 'helper', 'item2', 'item10']` gives no hit; the same list assigned to any other name gives one; a plainly sorted `__all__` gives no hit; an `__all__` in neither order gives one; an annotated `__all__: list[str] = [...]` in RUF022 order gives no hit. Direct tests of `ruff_dunder_all_key` on the same names. Run them and see the RUF022 cases fail
- [x] In `claude/skills/auditme/checks/auditme/rules/style_and_naming.py`, add `ruff_dunder_all_key(name)` with the spec's signature and docstring: group 0 when `len(name) > 1 and name.isupper()`, group 1 when `name[:1].isupper()`, group 2 otherwise; then a natural key splitting digit runs into integers
- [x] In `check_nonalphabetical_literals`, for an `Assign` or `AnnAssign` whose single target is the `Name` `__all__`, pass when the members equal `sorted(members)` or `sorted(members, key=ruff_dunder_all_key)`
- [x] Give `check_nonalphabetical_literals` a docstring stating its predicate (top-level assignments of string tuples, lists, sets and `frozenset(...)` literals; the fixed-length tuple exemption) and the `Refinement (2026-11-01): ...` paragraph

**Acceptance Criteria:**

- [x] Every case above passes
- [x] The existing `non-alphabetical-literal` tests pass unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_style_and_naming.py -q -p no:cacheprovider` passes

**Notes:**

- The fixture list was checked against ruff 0.17.3 `ruff check --isolated --select RUF022 --fix` on 2026-11-01; the tests do not run ruff

---

## Task 7: Document the refinements

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Implementation, "Docs"

**User Story:** As someone reading an audit hit or the checker's guide, I
want each narrowed rule to say what it no longer reports, so that I can tell
a missing hit from a carve-out.

**Subtasks:**

- [x] `claude/skills/auditme/SKILL.md`, "Documented refinements": one entry per rule, `raises-section-drift`, `missing-raises-section`, `passthrough-shim` and `non-alphabetical-literal`, each dated 2026-11-01, in the existing format (the carve-out with an example, what keeps the old behaviour, and the helper and module to see)
- [x] `claude/skills/auditme/SKILL.md`, checklist item A4: add that `raises-section-drift` skips a callee error guarded only by optional arguments the call leaves unset, and that Phase B reviews the other value-dependent cases (fixed names, pre-checked values, dispatch types)
- [x] `docs/guide/checker.md`: update the rows for `missing-raises-section`, `raises-section-drift`, `passthrough-shim` and `non-alphabetical-literal` to match the narrowed predicates
- [x] Check each description against the code the earlier tasks wrote

**Acceptance Criteria:**

- [x] Each entry names a helper that exists (`grep -n 'def <helper>'` finds it)
- [x] `uv run --group docs mkdocs build --strict` passes

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --group docs mkdocs build --strict` passes

**Notes:**

- Depends on Tasks 2-6
- No file in this repository may name an external project (`claude/rules/rule-scope.md`; the `no-project-names` hook checks it): the finding came from "another project"

---

## Task 8: Close the spec

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Acceptance criteria; Implementation, "Closing"

**Technical Goal:** Check the whole change before the branch merges, move the
`TODO.md` item to `DONE.md`, and mark the spec implemented.

**Subtasks:**

- [x] Run `uv run --no-project python claude/skills/auditme/checks/audit.py .` on this branch, and the same command in a temporary worktree of `main` (`git worktree add --detach <scratch> main`, removed afterwards), and compare their unaccepted hits. A hit on the branch that `main` does not have stops the task as `blocked` with both outputs
- [x] Move the `TODO.md` item "auditme rules report hits the code does not have" to the end of `DONE.md`: append its heading and body unchanged, then `Done: <date> - agents/specs/auditme-false-positives/spec.md, agents/tasks/auditme-false-positives/tasks-1.md: the five refinements, documented in SKILL.md.`, and remove it from `TODO.md`
- [x] Set the spec's `**Status:**` to `implemented`

**Acceptance Criteria:**

- [x] The spec's acceptance criteria hold: each finding's fixture gives no hit, each "still" shape gives one, and this repository's audit has no new unaccepted hit

**Definition of Done:**

- [x] `pre-commit run --all-files` exits 0
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests claude/skills/project-setup/tests tests -q -p no:cacheprovider` passes
- [x] `uv run --group docs mkdocs build --strict` passes
- [x] `git show $(git log --diff-filter=A --format=%H -- agents/tasks/auditme-false-positives/tasks-1.md):TODO.md > <scratch>/todo-before.md`, then `python3 claude/skills/todo-review/verify_bodies.py <scratch>/todo-before.md TODO.md DONE.md` exits 0

**Notes:**

- Depends on Tasks 1-7
- After the merge and push, the operator checks that the CI and docs runs on `main` passed; a task in the list cannot see GitHub
- The other project removes its accept markers once it pins this change; that is its own work, not a task here
