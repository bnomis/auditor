# Tasks: Raises section resolution

**Spec:** `agents/specs/raises-section-resolution/spec.md`
**Created:** 2026-11-20
**Version:** 1

Implements the whole spec, version 1.2: the auditme rule
`raises-section-drift` resolves `<ClassName>.<method>(...)` calls through the
shared resolver, follows a callee with no `Raises:` section into its own
raises and callees up to `SECTIONLESS_DEPTH` calls deep, names the chain in
its variant, and the docs say so. Both decisions in the spec's `## Decisions`
section (depth fixed at three; a section-less wrapper's own raises counted)
are already part of the design below.

This list runs after `agents/tasks/repeatable-phase-b/tasks-1.md` has merged:
it needs that list's Task 1, the shared call resolver in
`claude/skills/auditme/checks/auditme/core.py` with a `class_methods` flag.
Task 1 here checks it first and stops as `blocked` if it is missing.

This is an extension in the sense of `claude/skills/auditme/SKILL.md`
"Extending the script": omission hits grow. `CHECKS` in
`claude/skills/auditme/checks/auditme/registry.py` and
`claude/skills/auditme/tests/registry-order.txt` stay as they are. Every
existing test in `claude/skills/auditme/tests/test_error_handling.py` must
pass unchanged; a task in which an existing test's expected hits change stops
as `blocked` for the operator, naming the test and the hits before and after.
It never edits the test to pass.

Every task runs unattended: none calls an LLM, makes a network request or
reads another repository. The spec's "After this ships" steps (the catch-up
sweep in each project with the shared hooks, deleting the request entry from
`claude/skills/auditme/requests.md`) are the operator's, not tasks here.

The repository has no affected-tests tool. Each task names its own test
files and the test files that import the module it changes; the last task
runs every test tree the change can reach. Test commands run from the
repository root. Tests use neutral fixture names (`probe`, `Probe`,
`ProbeError`), as the shared repository's `no-project-names` hook requires.

---

## Task 1: Check the prerequisite and resolve `Class.method()` calls

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Prerequisite; Implementation (Resolution); Testing (`Probe.load()`)

**Technical Goal:** Confirm the shared resolver is in place, then have
`check_raises_section_drift` call it with `class_methods=True`, so a
`<ClassName>.<method>(...)` call on a class the package defines resolves, with
`bound` set from the method's decorator.

**Subtasks:**

- [x] Prerequisite check: `grep -n 'class_methods' claude/skills/auditme/checks/auditme/core.py` prints the shared resolver's signature, and `grep -n 'class_methods' claude/skills/auditme/checks/auditme/rules/error_handling.py` prints nothing. If either fails, stop as `blocked`, naming the missing prerequisite: Task 1 of `agents/tasks/repeatable-phase-b/tasks-1.md` (the shared call resolver with `class_methods` in `core.py`) has not merged
- [x] Starting-point check: `grep -nw 'SECTIONLESS_DEPTH\|escapes' claude/skills/auditme/checks/auditme/rules/error_handling.py` prints nothing; if it prints anything, stop as `blocked` and name what it found
- [x] Tests first in `claude/skills/auditme/tests/test_error_handling.py`, under a new `# --- raises-section-drift: Class.method() calls` heading after the existing `raises-section-drift` sections, on the `probe` fixtures (`ProbeError` in `errors.py`): a classmethod `Probe.load` declaring and raising `ProbeError`, called `Probe.load(path)` by a caller with no handler and no entry, gives one hit with variant `... declared by probe.conf.Probe.load`, both with `Probe` defined in the caller's module and with `Probe` imported by name from `probe.conf`; a handler catching `ProbeError` around the call gives none; a classmethod whose only raise sits under `if strict:` (an optional argument), called `Probe.load(path)`, gives none (`bound` true); a `@staticmethod` with the same guard, called with an argument in the guarded position, gives a hit (`bound` false). Run them and see the tests that expect a hit fail
- [x] In `check_raises_section_drift` (`claude/skills/auditme/checks/auditme/rules/error_handling.py`), pass `class_methods=True` to the resolver
- [x] Set `bound` for a `<ClassName>.<method>(...)` call: true when the method is decorated `@classmethod`, false for `@staticmethod` or an undecorated method; a `self.` call keeps `bound` true. `cls.<method>()` and inherited methods stay unresolved
- [x] Run the existing tests; if any existing test's expected hits change, stop as `blocked` naming it

**Acceptance Criteria:**

- [x] The new tests pass
- [x] Every existing test in `claude/skills/auditme/tests/test_error_handling.py` passes unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/test_registry.py claude/skills/auditme/tests/test_get_container_default.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on `agents/tasks/repeatable-phase-b/tasks-1.md` Task 1 (merged)
- `test_registry.py` and `test_get_container_default.py` import `error_handling`, so they run with the rule's own tests
- The current `bound` test is the `self`-attribute check before the `unset_optional_guard` call in `check_raises_section_drift`

---

## Task 2: Follow a callee with no `Raises:` section

**Status:** done
**Priority:** high
**Complexity:** large
**Spec Reference:** API (`SECTIONLESS_DEPTH`, `escapes`); Implementation (Following a section-less callee; What is reported); Error handling; Testing (Wrapper, Handlers at every hop, Raise in the wrapper, Depth, Cycle, Kept narrowing, Extras only shrink, Accept marker); Decisions 1 and 2

**Technical Goal:** Add `SECTIONLESS_DEPTH: typing.Final = 3` and the inner
`escapes(qualname, hop, chain)`, so a section-less callee contributes the
domain errors leaving it (its own uncaught raises and, up to the depth bound,
its callees' declared or escaping errors), and report each omission with the
shortest chain.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/test_error_handling.py`, under a new `# --- raises-section-drift: section-less callees` heading, on the `probe` fixtures with `perform()` in `probe/inner.py` and `wrapper()` in `probe/wrap.py`:
      - wrapper: section-less `wrapper()` calls `perform()`, which declares and raises `ProbeError`; a caller whose section omits `ProbeError` gets one hit, variant `... declared by probe.inner.perform via probe.wrap.wrapper`, `related` naming both files; a caller declaring `ProbeError`, or its base, gets none
      - handlers at every hop: no hit when the caller catches `ProbeError` around `wrapper()`, or `wrapper()` catches it around `perform()`; a hit when `wrapper()` catches and re-raises it
      - raise in the wrapper: `wrapper()` raising `ProbeError` itself gives `raised by probe.wrap.wrapper`
      - depth: `perform()` behind two section-less wrappers gives a hit, whose variant lists both wrappers in call order, comma-separated after `via`; behind three, none
      - cycle: section-less `a()` and `b()` call each other, `b()` calls `perform()`; the caller of `a()` gets one hit and the check ends
      - kept narrowing: `wrapper()` calling `load('x')`, whose only raise is under `if strict:`, gives none; `load('x', strict=True)` gives a hit
      - extras only shrink: a subject declaring `ProbeError`, catching it from another call and reaching it through `wrapper()`, gets no "never reaches the caller" hit
      - accept marker: an accept marker for `raises-section-drift` on the caller's `def` line marks the new wrapper hit accepted
      Run them and see the tests that expect a hit (or, for the last two, the changed verdict) fail
- [x] Add the module constant `SECTIONLESS_DEPTH: typing.Final = 3` with the docstring the spec's API section gives
- [x] Add the inner `escapes(qualname, hop, chain)` beside `caught` and `is_domain`, walking `nested_call_sites(f)` as the spec's Implementation section says: uncaught domain raises escape with chain `(f,)`; only while `hop < SECTIONLESS_DEPTH`, a resolved call to a function not in `chain` and not `f` adds, minus `f`'s handlers at that site, a sectioned callee's declared domain errors not skipped by `unset_optional_guard` (chain `(f, callee)`) or a section-less callee's `escapes(g, hop + 1, (*chain, f))` prefixed by `f`; anything else adds nothing. No memoisation; iterate every set sorted
- [x] In the subject's call-site loop, keep a callee with a section as today (not followed), and for a section-less callee add `escapes(callee, 1, (subject,))` minus what the handlers around the call catch, keeping the chains in `reached`
- [x] Report one omission hit per name not covered, naming the shortest chain (ties broken by sorting the chain tuples): `raised here`, `declared by <q>`, `declared by <q> via <w1>, <w2>` or `raised by <w>`; fill `related` with the file of every function, outside the subject's file, on any chain by which a reported name reaches the subject (spec 1.2, "What is reported"), sorted and de-duplicated
- [x] Use the grown `reached` in the extra-declaration branch unchanged in logic, so a "never reaches" hit can only disappear
- [x] Run the existing tests; if any existing test's expected hits change, stop as `blocked` naming it

**Acceptance Criteria:**

- [x] The new tests pass
- [x] Every existing test in `claude/skills/auditme/tests/test_error_handling.py` passes unchanged
- [x] `escapes` enters no function already on its chain and follows no call at `hop == SECTIONLESS_DEPTH`, so no package shape can raise `RecursionError`
- [x] Two runs on the same fixture give identical output (sorted iteration)

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/test_registry.py claude/skills/auditme/tests/test_get_container_default.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1 (the `Probe.load()` resolution and `bound`)
- Every narrowing from the auditme false-positives spec (unset optional argument guards, called nested functions, handler scope) applies at every hop: `escapes` uses `nested_call_sites` and `unset_optional_guard` exactly as the subject's loop does
- `related` covers every chain that reaches a reported name, not only the shortest one the variant names (spec 1.2): today's `related` for direct callees is kept, and wrapper files are added; `test_a_callee_error_names_the_callee_file_as_related` passes unchanged

---

## Task 3: Document the extension

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Implementation (Documentation); Settings

**Technical Goal:** Bring the rule's docstring, Phase B question A4 in
`SKILL.md` and the checker guide's row in line with the new resolution.

**Subtasks:**

- [x] In the docstring of `check_raises_section_drift`, rewrite the "Callees are followed one level" sentence to state the new resolution (`<ClassName>.<method>(...)` for a package class, and section-less callees followed to `SECTIONLESS_DEPTH`), and add an `Extension (<the date of this task's commit>):` paragraph naming both gaps, `SECTIONLESS_DEPTH` and the request "`raises-section-drift` should follow pass-through callees and `Class.method()` calls" in `claude/skills/auditme/requests.md`
- [x] In `claude/skills/auditme/SKILL.md` A4, replace "it follows each same-package callee one level through its declared `Raises:`" with "it follows each same-package callee, including `<ClassName>.<method>(...)` for a class the package defines, through its declared `Raises:`, and follows a callee with no section into its own raises and callees, up to three calls deep"; add `cls.<method>()` calls and inherited methods to the list of what Phase B reviews by hand. Add no "Documented refinements" entry
- [x] In `docs/guide/checker.md`, extend the `raises-section-drift` row to say errors are followed through wrappers with no section and through `Class.method()` calls

**Acceptance Criteria:**

- [x] No text in the three files still says callees are followed one level only
- [x] `SKILL.md`'s "Documented refinements" list is unchanged
- [x] None of the three files names a project other than this repository

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests/test_error_handling.py -q -p no:cacheprovider` passes
- [x] `uv run --group docs mkdocs build --strict` passes

**Notes:**

- Depends on Task 2
- `SECTIONLESS_DEPTH` stays a module constant, not a setting (spec, Settings)

---

## Task 4: Whole-tree checks, deduplication, and close the spec

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** whole spec; After this ships

**Technical Goal:** Remove any duplication the new code introduced, run every
check the change can reach, save the final test run to the run order's test
log, and mark the spec implemented.

**Subtasks:**

- [x] Hoist anything the new code duplicates to a single owner: grep `claude/skills/auditme/checks/` for each literal collection, constant and one-line helper Tasks 1 and 2 added (a decorator-name test for `@classmethod` / `@staticmethod`, a `Raises:`-section test, a chain formatter), and import rather than copy. Choose the owner from the existing import graph; prefer `core.py`, which `error_handling.py` already imports, over adding a new edge
- [x] Confirm `claude/skills/auditme/tests/registry-order.txt` and `CHECKS` in `claude/skills/auditme/checks/auditme/registry.py` are unchanged against the branch's base (`git diff <base> -- claude/skills/auditme/tests/registry-order.txt claude/skills/auditme/checks/auditme/registry.py` prints nothing)
- [x] Set the spec's `**Status:**` to `implemented` in `agents/specs/raises-section-resolution/spec.md`
- [x] Run `pre-commit run --all-files` and `pre-commit run auditme-all --hook-stage manual --all-files`; fix what they report
- [x] Run the final full test run, saving it to the order's test log relative to the main checkout (the list runs in a worktree):
      `MAIN=$(git worktree list --porcelain | sed -n '1s/^worktree //p'); LOG="$MAIN/logs/rro/raises-section-resolution/tasks-1/final-tests.log"; mkdir -p "$(dirname "$LOG")"; uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests claude/skills/project-setup/tests tests -q -p no:cacheprovider 2>&1 | tee "$LOG"; [ "${PIPESTATUS[0]}" -eq 0 ] && echo 'all selected test directories passed' | tee -a "$LOG"`
      The pass line `all selected test directories passed` is printed only when pytest exits 0

**Acceptance Criteria:**

- [x] No literal collection or helper added by this list is defined twice under `claude/skills/auditme/checks/`
- [x] The spec's status is `implemented`
- [x] `$MAIN/logs/rro/raises-section-resolution/tasks-1/final-tests.log` ends with `all selected test directories passed`

**Definition of Done:**

- [x] `pre-commit run --all-files` exits 0
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [x] The final test command above exits 0 and prints `all selected test directories passed`
- [x] `uv run --group docs mkdocs build --strict` passes

**Notes:**

- Depends on Tasks 1-3
- The spec's "After this ships" steps are not tasks: the catch-up sweep in each project with the shared hooks (fix or accept marker for each new hit, noted in that project's `agents/audit-reviews/summary.md`) and deleting the request entry from `claude/skills/auditme/requests.md` are the operator's, outside this list
- The `TODO.md` item "`raises-section-drift` misses errors reached through a section-less wrapper or a `Class.method()` call" stays open: this list does not move it to `DONE.md`. It moves only after the request entry is deleted

---
