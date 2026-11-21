# Tasks: Listed Phase B architecture questions

**Spec:** `agents/specs/listed-phase-b-architecture-questions/spec.md`
**Created:** 2026-11-20
**Version:** 1

Implements the whole spec, version 1.2: the site-finder hoists
(`if_chain`, `is_broad_handler`, the underscore drops in
`rules/error_handling.py`, the A20 read index moved to `core.py`),
`capture_hits`, the A11, A19, A1 and A17 listers in
`claude/skills/auditme/checks/auditme/phaseb/architecture.py` with their
version-1 briefs, and the `SKILL.md` changes that name them as listed.

This list runs after three others have merged to `main`:
`agents/tasks/repeatable-phase-b/tasks-1.md`,
`agents/tasks/listed-phase-b-documentation-questions/tasks-1.md` and
`agents/tasks/listed-phase-b-test-questions/tasks-1.md`. It uses their
`Candidate`, `Verdict`, `register_question`, ledger, batches, `check_run`,
command line, shared call resolver and `is_private` unchanged, and follows
the layout and the sampled-question rule they leave in `phaseb/` and
`SKILL.md`. Task 1 checks that they have merged before anything else.

No check is added to or removed from `CHECKS`, so
`claude/skills/auditme/checks/auditme/registry.py` and
`claude/skills/auditme/tests/registry-order.txt` stay as they are. The hoists
leave every rule's output unchanged: every existing test passes unchanged,
and a task that would need to change an existing test stops as `blocked` and
names it.

Every task runs unattended: none calls an LLM, makes a network request or
reads another repository, and none stops for the operator. Judging a real
project's candidates is the operator's step after the list ships, not a task
here.

The listers adapt the A4 lister (`phaseb/candidates.py`, from the
repeatable-phase-b list) and the sweep rules whose sites they reuse, so the
last task carries a deduplication subtask.

The repository has no affected-tests tool. Each task names its own test
files; the last task runs every test tree the change can reach. Test commands
run from the repository root. Tests use neutral fixture names (`pkg`,
`probe`, `ProbeError`, `Mode`), as the shared repository's
`no-project-names` hook requires.

---

## Task 1: Prerequisites, then hoist `if_chain` and `is_broad_handler`

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Prerequisites; API (`if_chain`, `IfChain`, `is_broad_handler`); Implementation (Hoists)

**Technical Goal:** Confirm the three earlier lists have merged, then make
the chain walk inside `check_assert_never_missing` a public `if_chain` with
the subject test as a parameter, and replace the copied handler-type test in
`check_silent_broad_except` and `check_broad_except_wrong_level` with a
public `is_broad_handler`, without changing either rule's output.

**Subtasks:**

- [x] Prerequisite check, before any edit: `grep -n '^\*\*Status:\*\*' agents/specs/repeatable-phase-b/spec.md agents/specs/listed-phase-b-documentation-questions/spec.md agents/specs/listed-phase-b-test-questions/spec.md` prints `implemented` for all three; `python3 claude/skills/auditme/checks/phaseb.py candidates . --question A4` exits 0; and `grep -nw 'def is_private' claude/skills/auditme/checks/auditme/core.py` prints one line. If any fails, stop as `blocked` and name which
- [x] Starting-point check: `grep -rnwE 'capture_hits|if_chain|IfChain|is_broad_handler|translator_envelopes|handler_translates|callable_short_name|FILESYSTEM_TOUCHING_CALLS|corpus_py_files|dotted_read|sys_modules_key|reads_by_module_and_name' claude/skills/auditme/checks` prints nothing, and `claude/skills/auditme/checks/auditme/phaseb/architecture.py` does not exist; if either fails, stop as `blocked` and name what it found (the underscored names do not match a whole-word search, so the existing private helpers do not fire it)
- [x] Tests first in `claude/skills/auditme/tests/test_state_and_effects.py`, under a new `# if_chain` heading, on `ast.parse` trees: a three-arm `if/elif/elif` on one name returns its subject, its three tests and `orelse` None; one ending in `else` returns that body as `orelse`; a chain whose second test names another subject returns None; a test the `subject_of` callable rejects returns None. Run them and see them fail
- [x] Tests first in `claude/skills/auditme/tests/test_error_handling.py`, under a new `# is_broad_handler` heading: true for a bare `except:`, `except Exception`, `except BaseException`, and a tuple holding either; false for `except ValueError` and a tuple of narrow types. Run them and see them fail
- [x] Add the frozen `IfChain` dataclass (`subject: str`, `tests: list[ast.expr]`, `orelse: list[ast.stmt] | None`) and `if_chain` to `claude/skills/auditme/checks/auditme/rules/state_and_effects.py`, and have `check_assert_never_missing` call it with `_extract_string_eq_var`, keeping its walk over every `If` node, its three-arm minimum and its `assert_never` test
- [x] Add `is_broad_handler` to `claude/skills/auditme/checks/auditme/rules/error_handling.py` and replace the handler-type test in `check_silent_broad_except` and `check_broad_except_wrong_level` with it

**Acceptance Criteria:**

- [x] The new tests pass
- [x] Every existing test in `test_state_and_effects.py` and `test_error_handling.py` passes unchanged
- [x] Each helper stays in its rule module: neither serves more than one rule module or reads the whole corpus, so the spec's Hoists rule keeps it out of `core.py`

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_state_and_effects.py claude/skills/auditme/tests/test_error_handling.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on `agents/tasks/repeatable-phase-b/tasks-1.md`, `agents/tasks/listed-phase-b-documentation-questions/tasks-1.md` and `agents/tasks/listed-phase-b-test-questions/tasks-1.md` (all merged)
- Key code: `check_assert_never_missing` and `_extract_string_eq_var` in `rules/state_and_effects.py`; `check_silent_broad_except` and `check_broad_except_wrong_level` in `rules/error_handling.py`
- If either rule's handler test differs from the spec's definition (a bare except, or `Exception` or `BaseException` alone or in a tuple) so that one helper would change a rule's output, stop as `blocked` and name the difference

---

## Task 2: Public envelope helpers and the A20 read index in `core.py`

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation (Hoists)

**Technical Goal:** Drop the underscore from `_FILESYSTEM_TOUCHING_CALLS`,
`_translator_envelopes`, `_handler_translates` and `_callable_short_name` in
`rules/error_handling.py`, and move `_corpus_py_files`, `_dotted_read`,
`_sys_modules_key` and `_reads_by_module_and_name` from
`rules/state_and_effects.py` to `core.py` without the underscore, so the
listers can import them. A rename and a move only: no behaviour changes.

**Subtasks:**

- [x] Rename the four `error_handling.py` names and every use of them: `grep -rnE '_FILESYSTEM_TOUCHING_CALLS|_translator_envelopes|_handler_translates|_callable_short_name' claude tests` prints nothing afterwards
- [x] Move the four read-index functions to `claude/skills/auditme/checks/auditme/core.py` beside `_audit_roots` (the documentation-questions list already moved `_corpus_py_files` there and imports it back into `rules/state_and_effects.py`: rename it in place and drop that re-import rather than moving it again), as `corpus_py_files`, `dotted_read`, `sys_modules_key` and `reads_by_module_and_name`; have the A20 rules in `rules/state_and_effects.py` (`check_mutable_module_level_exported` and `check_mutable_members_in_immutable_wrapper`, or whichever call the index) and `rules/project_hygiene.py` (which imports `_corpus_py_files` from `state_and_effects`) import them from `core.py`
- [x] Update the docstring in `core.py` that names `_corpus_py_files`
- [x] `grep -rnE '_corpus_py_files|_dotted_read|_sys_modules_key|_reads_by_module_and_name' claude tests` prints nothing

**Acceptance Criteria:**

- [x] Every existing test in `test_core.py`, `test_state_and_effects.py`, `test_error_handling.py` and `test_project_hygiene.py` passes unchanged
- [x] No moved or renamed name is defined in two places

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/test_state_and_effects.py claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/test_project_hygiene.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- If an existing test imports one of the underscored names, renaming it would change that test: stop as `blocked` and name the test

---

## Task 3: `capture_hits` and the `architecture.py` skeleton

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** API (`capture_hits`, candidate ids); Error handling; Implementation (Sites the sweep already reports)

**Technical Goal:** Add `capture_hits` to `phaseb/architecture.py` (spec
1.2: not `core.py`, which `phaseb` imports): run a sequence of
checks over every audit root with `_EMITTED` saved and restored and stdout
captured, and return each hit, accepted or not, as `(rule, path, line)`.
Create `phaseb/architecture.py` with the shared pieces every lister in it
uses: parsing a file or raising `PhaseBError` naming it, the per-qualname
site counter for ids, and dropping a candidate whose anchor line carries an
owning rule's hit.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_architecture_candidates.py`, under a `# capture_hits` heading, on a fixture project with `src/pkg/`: one rule's hits come back as `(rule, path, line)` triples; an accepted hit is included; `_EMITTED` holds the same entries after the call as before it; nothing reaches stdout; a check that raises gives `PhaseBError` whose message names the check. Run them and see them fail
- [x] Implement `capture_hits` in `claude/skills/auditme/checks/auditme/phaseb/architecture.py` with the signature and docstring in the spec's API, generalising the capture in the `run_check` fixture in `claude/skills/auditme/tests/conftest.py`; leave that fixture as it is
- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_architecture_candidates.py`, under a `# shared` heading: a file under an audit root that does not parse raises `PhaseBError` naming it; the site counter numbers two sites in one qualname `#1` and `#2` in order of appearance, and a site added in another function leaves them unchanged; module-level code has the qualname `<module>`. Run them and see them fail
- [x] Create `phaseb/architecture.py` with those helpers, and import it wherever the earlier lists import their lister modules so its registrations run (follow `phaseb/__init__.py` as the earlier lists left it)

**Acceptance Criteria:**

- [x] The new tests pass
- [x] `capture_hits` returns accepted hits as well as unaccepted ones
- [x] No lister is registered yet, so `claude/skills/auditme/tests/phaseb/test_briefs.py` passes unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 2
- `capture_hits` lives in `phaseb/architecture.py` (spec 1.2), so it raises `PhaseBError` without an import cycle
- A hit falls on an anchor when its path and line match; each lister task supplies its own owning rules and anchor lines from the spec's table

---

## Task 4: The A11 lister and brief

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation (A11 candidates; Sites the sweep already reports, A11 row; Briefs, A11); API (A11 ids)

**Technical Goal:** Register `A11`: every single-subject `if` chain head with
two or more arms (or one arm and an `else`), every two-way split on a name
assigned from such a comparison, and every `match`, minus those whose first
`if` carries an `assert-never-missing` hit; with the payload and hash the
spec gives, and the version-1 brief.

**Subtasks:**

- [x] Tests first in `test_architecture_candidates.py`, under `# A11`, on a fixture `pkg` with a `Mode` enum and a `Literal` alias: a chain on `mode == Mode.FAST` / `Mode.SLOW` is a candidate with id `<path>::<qualname>::if:mode#1`; a chain using `is`, `in` and a tuple of constants is one; a single `if` with no `else` is not; a chain head that is the sole `orelse` of another `if` is not listed separately; a chain whose tests name two subjects is not; an `if flag:` / `else` where `flag = mode == 'a'` in the same function is one; a `match` is one with id `::match:<subject>#1`; `annotation` and `type_source` are filled from a parameter annotation naming `Mode` and null for an unannotated subject; a three-arm string chain the `assert-never-missing` rule flags is dropped, and so is one whose hit carries an accept comment; the id survives an unrelated edit above the site; an edit inside the chain changes the hash and one outside does not. Run them and see them fail
- [x] Implement the lister in `phaseb/architecture.py` with `if_chain` and a subject test that accepts a name or dotted attribute compared by `==`, `is` or `in` with string constants, attribute constants or tuples of them; anchor on the chain's first `if` and drop through `capture_hits` with `check_assert_never_missing`
- [x] Write `claude/skills/auditme/phaseb/briefs/A11.md`: the A11 question verbatim from `SKILL.md`, the input format, the output (one JSON line per candidate with `id`, `findings`, `reason`), the A11 thresholds from the spec's Briefs section, the rule that an unsettled threshold is reported and never decided, the rule never to list environment variables (`env`, `printenv`, `set`) or print an env file, and `**Brief version:** 1`
- [x] Register `A11` with that brief path

**Acceptance Criteria:**

- [x] The new tests pass, and `claude/skills/auditme/tests/phaseb/test_briefs.py` passes for `A11`
- [x] `python3 claude/skills/auditme/checks/phaseb.py candidates . --question A11` exits 0

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb claude/skills/auditme/tests/test_state_and_effects.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 1 and 3
- A `match` that the A11 brief later rules out (class or structural patterns) is still listed; the reviewer applies that threshold

---

## Task 5: The A19 lister and brief

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation (A19 candidates; Sites the sweep already reports, A19 row; Briefs, A19); API (A19 ids)

**Technical Goal:** Register `A19`: every broad handler and every handler
whose body calls `.exception(` on a logger name, minus those on a hit of the
three owning rules, with the payload and hash the spec gives, and the
version-1 brief.

**Subtasks:**

- [x] Tests first in `test_architecture_candidates.py`, under `# A19`: an `except Exception` that logs at `warning` and returns a default is a candidate with id `<path>::<qualname>::except#1`, with `log_calls` holding `warning: <text>`; a bare `except:` is one; an `except ValueError` that calls `logger.exception(` is one, and so are `log`, `_logger`, `LOGGER`, `logging`, `loguru.logger` and `self.logger`; an `except ValueError` that logs at `error` is not; a handler on a `silent-broad-except`, `broad-except-wrong-level` or `logger-exception-graceful-degradation` hit is dropped, including a hit on the function's last `return` when the handler falls through, accepted or not; at module level the hash is the `try` statement's source; an edit in the enclosing function changes the hash and one in another function does not. Run them and see them fail
- [x] Implement the lister with `is_broad_handler` and `capture_hits` on the three owning rules, anchoring on the handler's lines and, for a handler that falls through, the function's last `return`
- [x] Write `claude/skills/auditme/phaseb/briefs/A19.md` as Task 4's brief, with the A19 question verbatim from `SKILL.md` and the A19 thresholds from the spec, and `**Brief version:** 1`
- [x] Register `A19` with that brief path

**Acceptance Criteria:**

- [x] The new tests pass, and `test_briefs.py` passes for `A19`
- [x] `python3 claude/skills/auditme/checks/phaseb.py candidates . --question A19` exits 0

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb claude/skills/auditme/tests/test_error_handling.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 1 and 3
- Key code: `check_silent_broad_except`, `check_broad_except_wrong_level` and `check_logger_exception_graceful_degradation` in `rules/error_handling.py`

---

## Task 6: The A1 lister and brief

**Status:** done
**Priority:** high
**Complexity:** large
**Spec Reference:** Implementation (A1 candidates; Sites the sweep already reports, A1 row; Briefs, A1); API (A1 ids); Decisions 1 and 2

**Technical Goal:** Register `A1`: every external call the spec lists, in a
non-test file of a package that defines a domain error, minus those on a hit
of the three owning rules, with its `try`, envelopes, domain errors and, for
a call in a private or nested helper, its resolved callers; the hash the
spec gives; and the version-1 brief.

**Subtasks:**

- [x] Tests first in `test_architecture_candidates.py`, under `# A1`, on a fixture `pkg` defining `ProbeError(Exception)`: an `open(...)` call is a candidate with id `<path>::<qualname>::call:open#1`, with its enclosing `try`, `envelopes` and `domain_errors` `['ProbeError']`; a call to a name in `FILESYSTEM_TOUCHING_CALLS`, `subprocess.run`, `torch.load`, `pandas.read_csv`, `df.to_parquet` and `requests.get` is each one; `conn.execute` is one in a module importing `sqlite3` and not in one that does not; no call in a package without a domain error is listed; no call in `test_probe.py`, `probe_test.py`, `conftest.py` or under `tests/` is listed; a call on a `filesystem-envelope-gap`, `filesystem-op-without-envelope` or `translator-envelope-gap` hit is dropped, whether the hit is on the call's line or on the first handler of its enclosing `try`; a call in a helper `is_private` marks private lists `callers` with each resolved call site and its enclosing envelope (or null); adding a caller changes the helper's hash; an edit in a caller not listed does not. Run them and see them fail
- [x] Implement the lister with `FILESYSTEM_TOUCHING_CALLS`, `translator_envelopes`, `handler_translates`, `callable_short_name`, `package_class_parents`, `class_lineage`, `is_private` and the shared call resolver the repeatable-phase-b list put in `core.py`; drop through `capture_hits` on the three owning rules
- [x] Write `claude/skills/auditme/phaseb/briefs/A1.md` as Task 4's brief, with the A1 question verbatim from `SKILL.md`, the A1 thresholds from the spec (including decision 2: a private or nested helper is covered when every resolved caller calls it inside a translating envelope), and `**Brief version:** 1`
- [x] Register `A1` with that brief path

**Acceptance Criteria:**

- [x] The new tests pass, and `test_briefs.py` passes for `A1`
- [x] Private means `is_private` and nothing else (decision 1, "what is private"); the lister defines no underscore test of its own
- [x] `python3 claude/skills/auditme/checks/phaseb.py candidates . --question A1` exits 0

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb claude/skills/auditme/tests/test_error_handling.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 2 and 3
- Key code: `check_filesystem_envelope_gap`, `check_filesystem_op_without_envelope` and `check_translator_envelope_gap` in `rules/error_handling.py`
- Whether a helper is covered is the reviewer's verdict; the lister only lists its callers

---

## Task 7: The A17 lister and brief

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation (A17 candidates; Sites the sweep already reports, A17 row; Briefs, A17); API (A17 ids); Decisions 1 and 3

**Technical Goal:** Register `A17`: every `__init__.py` under an audit root
with an `__all__` or no exports, with each exported name's consumers from
outside the package and the test tree (and `pyproject.toml` entry points),
an empty one's reach-ins, the hash the spec gives, and the version-1 brief.

**Subtasks:**

- [x] Tests first in `test_architecture_candidates.py`, under `# A17`: `src/pkg/__init__.py` with `__all__ = ['Probe']` is a candidate whose id is the path alone, with `consumers` listing a read of `Probe` from another package as `path: line text`; a read from `tests/` is left out of `consumers` and out of the hash; a `[project.scripts]` target in `pyproject.toml` is a consumer; an empty `__init__.py` lists `reach_ins` for each outside read of a submodule; an `__init__.py` with an `empty-init-while-siblings-export` hit on line 1 is dropped; a consumer line a `migration-shim-consumer` hit names is removed from `consumers`; moving a consumer's reading line leaves the hash unchanged; an edit to the `__init__.py` changes it. Run them and see them fail
- [x] Implement the lister with `is_dunder_all_assignment`, `reads_by_module_and_name` from `core.py`, `tomllib` for `pyproject.toml`, and `capture_hits` on `check_empty_init_with_exporting_siblings` and `check_migration_shim_consumers`
- [x] Write `claude/skills/auditme/phaseb/briefs/A17.md` as Task 4's brief, with the A17 question verbatim from `SKILL.md`, the A17 thresholds from the spec (a bypass to a submodule `is_private` marks private, decision 1; a test-tree read is not a consumer, decision 3), and `**Brief version:** 1`
- [x] Register `A17` with that brief path

**Acceptance Criteria:**

- [x] The new tests pass, and `test_briefs.py` passes for `A17`
- [x] `python3 claude/skills/auditme/checks/phaseb.py candidates . --question A17` exits 0

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb claude/skills/auditme/tests/test_imports_and_surfaces.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 2 and 3
- Key code: `check_empty_init_with_exporting_siblings` and `check_migration_shim_consumers` in `rules/imports_and_surfaces.py`; the test-tree definition is the one the test-questions list uses, where it has one

---

## Task 8: `SKILL.md`: A11, A19, A1 and A17 are listed

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation (Skill changes); Settings

**Technical Goal:** Update `claude/skills/auditme/SKILL.md` so A11, A19, A1
and A17 run on the listed path and lose `(sampled)`, and section 4 says a
site a sweep rule for the same question reports is not judged in Phase B.

**Subtasks:**

- [x] Add A11, A19, A1 and A17 to the listed questions where section 4 names them, in the layout the documentation-questions and test-questions lists left, and remove `(sampled)` from them wherever `SKILL.md` marks it
- [x] In section 4, say that a site a sweep rule for the same question reports, accepted or not, is not judged in Phase B, and is judged as new once the hit is fixed
- [x] Say that `--question` accepts the four and `--depth` applies to A4 only, where `SKILL.md` describes the options
- [x] Add `test_architecture_candidates.py` to `claude/skills/auditme/tests/README.md`'s description of the test tree

**Acceptance Criteria:**

- [x] No Phase B question text in `SKILL.md` changes, so each brief still holds its question verbatim and `test_briefs.py` passes
- [x] Nothing in `SKILL.md` names a project

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes
- [x] `uv run --group docs mkdocs build --strict` passes

**Notes:**

- Depends on Tasks 4-7

---

## Task 9: Whole-tree checks, deduplication, close the spec and the TODO item

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** whole spec

**Technical Goal:** Remove any duplication the listers introduced, run every
check the change can reach, mark the spec implemented, move the `TODO.md`
item this list completes to `DONE.md`, and save the final test run for the
run order's merge gate.

**Subtasks:**

- [x] Hoist anything `phaseb/architecture.py` duplicates from `phaseb/candidates.py`, the rule modules or `core.py` to a single owner: grep the tree for each literal collection, constant and one-line helper it defines (the logger names, the client module names, the `.to_*` method names, the test-file predicate especially), and import rather than copy. Choose the owner from the existing import graph; prefer a module the consumer already imports over adding a new edge
- [x] Run `python3 claude/skills/auditme/checks/phaseb.py candidates . --question <Q>` from the repository root for each of `A11`, `A19`, `A1` and `A17`, and check each exits 0 and each line it prints parses as JSON with the `id`, `hash` and `payload` keys
- [x] Confirm `claude/skills/auditme/tests/registry-order.txt` is unchanged against the branch's base (`git diff <base> -- claude/skills/auditme/tests/registry-order.txt` prints nothing)
- [x] Set the spec's `**Status:**` to `implemented` in `agents/specs/listed-phase-b-architecture-questions/spec.md`
- [x] Move the `TODO.md` item "Put the Phase B questions that find most onto the listed path" to the end of `DONE.md`: append its heading and body unchanged, then a line `Done: <YYYY-MM-DD> - specs agents/specs/listed-phase-b-documentation-questions/spec.md, agents/specs/listed-phase-b-test-questions/spec.md and agents/specs/listed-phase-b-architecture-questions/spec.md, task lists agents/tasks/listed-phase-b-documentation-questions/tasks-1.md, agents/tasks/listed-phase-b-test-questions/tasks-1.md and agents/tasks/listed-phase-b-architecture-questions/tasks-1.md` (names in backticks, as the other `Done:` lines have them); remove the item from `TODO.md` and touch no other `TODO.md` item

**Acceptance Criteria:**

- [x] No literal collection or helper is defined both in `phaseb/architecture.py` and elsewhere under `claude/skills/auditme/checks/`
- [x] The spec's status is `implemented`
- [x] The item is in `DONE.md` with its body unchanged and gone from `TODO.md`; every other `TODO.md` item is unchanged

**Definition of Done:**

- [x] `pre-commit run --all-files` exits 0
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [x] `uv run --group docs mkdocs build --strict` passes
- [x] `T=$(mktemp -d); git show "$(git log --diff-filter=A --format=%H -- agents/tasks/listed-phase-b-architecture-questions/tasks-1.md)":TODO.md > "$T/todo-before.md"; python3 ~/.claude/skills/todo-review/verify_bodies.py "$T/todo-before.md" TODO.md DONE.md` exits 0
- [x] The full test run is saved for the run order's merge gate, from the repository root of this worktree: `MAIN=$(git worktree list --porcelain | sed -n '1s/^worktree //p'); LOG="$MAIN/logs/rro/listed-phase-b-architecture-questions/tasks-1/final-tests.log"; mkdir -p "$(dirname "$LOG")"; uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests claude/skills/project-setup/tests tests -q -p no:cacheprovider 2>&1 | tee "$LOG"; [ "${PIPESTATUS[0]}" -eq 0 ] && echo 'all selected test directories passed' | tee -a "$LOG"`, and the log ends with `all selected test directories passed`

**Notes:**

- Depends on Tasks 1-8
- The saved log is read by `/rro`, whose merge gate does not rerun the tests; the path is relative to the main checkout, the first entry of `git worktree list --porcelain`. The pass line is printed only when pytest exits 0
- The `verify_bodies.py` baseline is `TODO.md` as it stood in the commit that added this task list, so a body edited since then fails the check
- This list is the last of the three that put the TODO item's groups on the listed path, so it alone moves the item

---
