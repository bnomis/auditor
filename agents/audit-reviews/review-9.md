# Audit Review 9

**Date:** 2026-11-22
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`); every sampled question ran on the whole tree
**Commit:** 2fb0d4b72e08d8f15e56f0a05d733ed1542cd680
**Script output:** /tmp/audit-auditor.jsonl (48 hits, 48 accepted, 0 unaccepted)
**Script version:** f15c2958d2fa76bea9a0630438285b696c327b820e2d8549f495c8cf2643c553
**Convergence note:** the whole-tree audit after the first audit with no finding. Measured on 2026-11-22: 14 listed candidates judged (T1 6, Doc4 5, Doc5 3), no verdict changed, and every listed question has nothing open. Of the sampled questions run on the whole tree, only P1 and P3 flag anything, both at one site measured on another, larger project; this repository's sample of the code is too small to show the cost.
**Review page:** https://claude.ai/artifact/HnT6dpT2XdpijXiSwGFYe3

## What is being reviewed and how

This is the checker repository's ninth audit of its own code, its third whole-tree pass. The sweep, every listed question, the spec review and every sampled question but the two performance questions are clean. Choose Fix (it becomes a task) or Dismiss (with your reason) for the one finding.

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 48 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 14 judged (T1 6, Doc4 5, Doc5 3); every other listed question carried every verdict |
| `phaseb.py check` on every listed question | pass, no retries |
| Every sampled question returned a hit list or "no hits" | pass |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| Prior findings to re-verify | review-8 O1: shipped; no `contextlib.suppress(Exception)` is left under `claude/skills/auditme/checks/` |

## Summary

The sweep reports 48 hits, all accepted. Phase B leaves no listed verdict open. The sampled questions flag P1 1 and P3 1, at the same site. The spec review finds no gap.

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits.

## Phase B findings (consolidated)

### F1. The T1 lister rescans every test file's imports for every function (P1, P3)

- **Category:** P. **Questions:** P1, P3 (sampled). **Severity:** low.
- **Locations:** `claude/skills/auditme/checks/auditme/phaseb/testmap.py`:
  - `:272` `TestIndex.test_files` checks every test file against every caller module, once per function: functions x test files x modules;
  - `:183` `imports_module` rebuilds `imported_names(file)` on every call, though the result depends only on the file.
- **Description:** measured on 2026-11-22 with cProfile. On one project with 743 source files, listing T1 took 35.8 s, of which `test_files` took 20.5 s; `imports_module` was called 1,533,427 times (15.5 s). On this repository the same listing takes 2.2 s, 0.36 s of it in `test_files`, which is why no earlier sample showed it. The work grows with the project, so it is a real-size cost.
- **Recommendation:** compute each test file's imported names once when the index is built, and index the test files by each module they import, so `test_files` looks its modules up instead of scanning every file.

## Phase B per-question results

Listed questions: the verdicts are in `agents/audit-reviews/ledger/`; `phaseb.py report <root> --question <Q>` prints the open ones. No listed question has any, and no verdict changed on re-judging.

#### A2 (sampled): Except tuple coverage
- Mode: full
- Inspected: every `try` statement in every tracked `.py` file at `2fb0d4b` (AST listing of each `try` with its handler types and the calls in its body), then each body that touches disk or a JSON/TOML parser read by hand: `audit.py`, `changed.py`, `phaseb.py`, `auditme/core.py`, `auditme/phaseb/{architecture,batches,candidates,docrefs,ledger,testmap}.py`, `auditme/rules/project_hygiene.py`. Every disk body catches `OSError` (or `Exception`), adds `UnicodeDecodeError` where it decodes (`read_text`, `cached_bytes(...).decode`), and `json.JSONDecodeError` where it calls `json.loads` on a file (`batches.py:148`); bodies over `cached_bytes` that keep bytes (`candidates.py:82,411,603`, `docrefs.py:316`) need only `OSError`. `json.loads`/`tomllib.loads` on text already read or on subprocess output do not touch disk; subprocess-only bodies (`changed.py:63,235`, `project_hygiene.py:48,102,222`, `docrefs.py:299`) are not disk bodies. `architecture.py:44` is a try/finally. Searched for translating decorators and `with` contextmanagers in source: none (the hits are rule code and docstrings in `rules/error_handling.py` and `phaseb/architecture.py`). The dispatch envelope in `phaseb.py:274` calls only commands whose disk access is wrapped in their own readers/writers. Test-file `try` blocks are fakes and fixture text.
- Hits: No hits

#### A3 (sampled): Domain-error layering
- Mode: full
- Inspected: every `raise` in every tracked non-test `.py` file (AST listing of raised types). Domain errors: `auditme.core.RootsError`, `auditme.core.CachedReadError` (an `OSError` subclass, raised at `core.py:103`), `auditme.phaseb.errors.PhaseBError`, `changed.ChangedError`. Other raises: `SystemExit` at the three entry points (`audit.py:246`, `changed.py:366`, `phaseb.py:287`) and `argparse.ArgumentTypeError` in the `type=` callables (`phaseb.py:45,67,69`), which argparse requires. The six `ValueError`s at `auditme/phaseb/batches.py:181-198` are the sweep's (`layer-has-domain-error-raises-stdlib`, accepted), not mine. Test-file raises are fakes.
- Hits: No hits

#### A5 (sampled): Two sources of truth
- Mode: full
- Inspected: module state rebound by the driver or by helpers against the parameters that read it: `auditme.core.EXTRA_ROOT_NAMES` / `DECLARATION_IGNORED` (rebound at `audit.py:175-176`) against `extra_roots(scope, names=None)` (docstring: `names` defaults to the current `EXTRA_ROOT_NAMES`, read at call time) and `declared_roots`; `auditme.core.ROOT_MODULES` rebound in `audit_roots` and `cached_roots` (`core.py:452-467`, `801-814`), always together with the roots list it describes and returned alongside it, read by `py_files` callers and `rules/imports_and_surfaces.py:128-132`; `phaseb.py` `--depth` against `Plan.depth` (`batches.py:43`, `write_plan(depth=DEFAULT_DEPTH)`), `list_candidates(depth=None)` falling to each lister's default, and `today=None` parameters in `ledger.dismiss_verdict` and `batches.read_run_verdicts`. Each precedence is stated in a docstring or comment and enforced.
- Hits: No hits

#### A6 (sampled): Stage method dual-path
- Mode: full
- Inspected: every class in every tracked `.py` file and each method that assigns to or mutates `self.<attr>` (AST listing). The project has no pipeline-stage class. The only self-mutating methods are `SiteCounter.next` (`auditme/phaseb/architecture.py:106`, increments a counter and returns the new int, not a tuple) and `IndexEntries.add_module` / `record` (`auditme/phaseb/docrefs.py:225,241`, return `None`).
- Hits: No hits

#### A7 (sampled): Constructor purity
- Mode: full
- Inspected: every `__init__` in every tracked `.py` file (AST listing): `SiteCounter.__init__` (`auditme/phaseb/architecture.py:103`, an empty `Counter`), and the test fakes `Result.__init__` (`tests/test_project_hygiene.py:141`) and `LockResult.__init__` (`tests/test_project_hygiene.py:203`), which assign constants and arguments. No I/O, no expensive compute, no argument mutated. Other `__init__` text in tests is fixture source strings.
- Hits: No hits

#### A8 (sampled): Late dataclass mutation
- Mode: full
- Inspected: every `@dataclass` in the tracked `.py` files (all `frozen=True` except `ClassInfo`, `IndexEntries` in `auditme/phaseb/docrefs.py` and `TestIndex` in `auditme/phaseb/testmap.py`), every construction of one bound to a local name inside a function, and every later attribute or item assignment, mutating container call or `setattr`/`object.__setattr__` on that name (AST scan, tests included; none found), then each construction site read: `ClassInfo` is built complete at `docrefs.py:265`; `CorpusIndex.build` fills an `IndexEntries` through its own methods and then constructs the frozen `CorpusIndex` from the finished dicts (`docrefs.py:186-205`); `TestIndex` is built complete at `testmap.py:346`. Changed copies go through `dataclasses.replace`.
- Hits: No hits

#### A9 (sampled): Pure-named function side effects
- Mode: full
- Inspected: every function and method (nested included) in every tracked `.py` file whose name, leading underscores stripped, starts with a pure prefix (AST enumeration), each body read for direct I/O calls and for calls to project helpers that read files (`read_*`, `audit_roots`, `all_py_files`, `iter_*`, `load_*`, git/subprocess). Every `check_` function in `checks/auditme/rules/*.py` is a member of `CHECKS` or `PROJECT_CHECKS` in `checks/auditme/registry.py`, so the registered-check carve-out applies (this covers `check_ruff`, `check_lockfile`, `check_ruff_version`, which run subprocess / test existence). `load_test_index` and `load_test_map` (`checks/auditme/phaseb/testmap.py`) read the package and test tree under the root their argument names, which is what they say they load. `ast.walk` is not I/O. No sweep hit for this question in /tmp/audit-auditor.jsonl.
- Hits: No hits

#### A10 (sampled): Predicate semantics
- Mode: full
- Inspected: every `is_*`, `has_*` and `should_*` function in every tracked `.py` file (core.py, phaseb/architecture.py, phaseb/candidates.py, phaseb/docrefs.py, phaseb/testmap.py, rules/duplication.py, rules/error_handling.py, rules/style_and_naming.py, tests/phaseb/test_t2_candidates.py), each body compared with its name and docstring. Every conjunct is part of the question the name and docstring state (e.g. `is_builtin_call` excludes shadowed builtins by definition; `is_dunder_all_assignment` states "single target").
- Hits: No hits

#### A12 (sampled): assert misuse
- Mode: full
- Inspected: every tracked `.py` file outside test files (`tests/` directories, `test_*.py`, `conftest.py`), searched for `assert` statements.
- Hits: No hits (no `assert` outside test files)

#### A13 (sampled): Same value to multiple structural slots
- Mode: full
- Inspected: every call to a capitalised name (class constructor) in every tracked `.py` file, checked by AST for the same non-constant expression passed to two or more slots. One site matched: `checks/auditme/phaseb/docrefs.py:281` `DocTarget(kind, rel, rel, 1, last_line)` passes `rel` to `id` and `path`; it is inside the explicit factory `path_target` with a docstring, and the `id` field's comment documents `'path' for a file or directory`, which is the factory-or-docstring the question accepts.
- Hits: No hits

#### A14 (sampled): Repeated computation per request
- Mode: full
- Inspected: project-state helpers in non-test code - `auditme.core.audit_roots` (resolved `[tool.auditme]` roots; its pyproject read memoised by `cached_declared_roots`, and `cached_roots` used by per-candidate callers), `read_pyproject`, `imported_modules`, and the git helpers in `checks/changed.py` (`read_base_ref`, `rev-parse --show-toplevel`, `merge-base`). Traced each request flow: `audit.py main` calls `audit_roots` once; each Phase B lister (`list_a1_candidates`, `list_a17_candidates`, `list_a4_candidates`, `load_test_index`) reaches it at most twice; `changed.py main` resolves the repository root and the base once each.
- Hits: No hits

#### A15 (sampled): Duplicate constructor / serialisation logic
- Mode: full
- Inspected: every construction of a project-defined class in non-test code, grouped by class with keyword/positional field sets (`Candidate`, `DocTarget`, `Scope`, `Site`, `SiteCounter`, `Verdict`, and the error classes `ChangedError`, `PhaseBError`, `RootsError`). `Candidate` is built only inside the three factories `site_candidate`, `span_candidate`, `section_candidate` (`checks/auditme/phaseb/candidates.py`); `DocTarget` only inside `node_target` and `path_target`; `Verdict` is built once from a judged result and once deserialised field-by-field from the ledger; `Scope` and `Site` sites pass different values per slot; error classes take one message.
- Hits: No hits

#### A16 (sampled): CLI entry envelope
- Mode: full
- Inspected: `git ls-files` for any `cli/*.py`; the repository has no `cli/` directory, so the question's enumeration (top-level `run_*` in `cli/*.py`) has no members. The `run_*` functions in `checks/phaseb.py` and `checks/audit.py` are outside `cli/` and so outside the enumeration.
- Hits: No hits

#### A18 (sampled): Hot-path setup
- Mode: full
- Inspected: every tracked `.py` and `.sh` file, searched for callback methods (`on_step`, `on_log`, `on_evaluate`, `on_batch_*`); none is defined outside fixture strings in the tests.
- Hits: No hits

#### A20 (sampled): Mutable module-level singleton
- Mode: full
- Inspected: every module-level assignment in every tracked `.py` file whose value is a `dict`/`list`/`set` literal, comprehension or bare-builtin call, or a `MappingProxyType`/`frozenset`/`tuple` wrapper; each name grepped across all tracked `.py` files (tests and `bin/` included) for `from <module> import <name>`, `<module>.<name>` and `sys.modules[...].<name>`. Mutable containers read elsewhere are `core.py` `EMITTED`, `UNREADABLE`, `INDEX_CACHE` (and `SOURCE_CACHE`) and `phaseb/candidates.py` `REGISTRY`, `KINDS` - all swept (`mutable-module-level-exported`, accepted) and not mine. `candidates.TAKES_DEPTH`, `phaseb.py` `COMMANDS`, `changed.py` `RULE_HELP`, `imports_and_surfaces.STDLIB`, `state_and_effects` `DISK_IO_NAMES`/`MUTABLE_VALUE_SHAPES`/`MUTABLE_CONSTRUCTORS`, `style_and_naming` `STRFTIME_TOKENS`/`PARAMETRIC_NONBUILTIN_GENERICS`/`TYPING_DEPRECATED_ALIASES` are read only in their own module (the `COMMANDS` mention in `tests/test_annotated_all.py` is a string in a fixture).
- Hits: No hits

#### A21 (sampled): Lazy init race
- Mode: full
- Inspected: every `if X is None:` in non-test `.py` files and every `global` statement (`core.py:462`, `core.py:807`, both assigning `ROOT_MODULES` unconditionally, not an `is None` lazy init); the per-run caches use `if key not in INDEX_CACHE`, not `is None`. No tracked code uses threads, multiprocessing, asyncio or executors, so no path is called concurrently.
- Hits: No hits

#### A22 (sampled): Fall-through after partial handling
- Mode: full
- Inspected: AST scan of non-test `.py` files for an `if` whose branch holds a `try` with a raising handler and is followed by further statements; the one match, `changed.py:196` (`scope_records`), raises `ChangedError` on a read failure with no fallback that re-runs the other branch. Shell scripts `bin/check-foreign-names.sh`, `bin/install-claude.sh`, `claude/hooks/auditme-stop.sh` read in full.
- Hits: No hits

#### A23 (sampled): Discarded multi-return
- Mode: full
- Inspected: every non-test call to a project function annotated to return a `tuple[...]` or a project dataclass (AST scan, then each partial use read): `core.read_source`/`read_and_parse` take one element of `cached_source`, `core.read_is_private` takes `privacy(...)[0]`, `candidates.question_brief`/`question_batch_size` index `registered(...)`, `candidates.question_kinds` calls `registered(question)` for its raise, `batches.py:268` reads `read_run_check(...).problems` (its only field), `testmap.py:362` calls `.refs` on `load_test_index(...)`. None of the dropped components is documented as changing how the kept one is used; every other call unpacks or keeps the whole value.
- Hits: No hits

#### A24 (sampled): Identity of subprocess / shell-out calls
- Mode: full
- Inspected: every `subprocess.run` in non-test `.py` files and every `git`/`python3` invocation in the shell scripts. `rules/project_hygiene.py:50`, `:104` (with its conditional retry at `:112` under a different environment) and `:225` are swept (`subprocess-without-memoisation`, accepted) and not mine. `changed.py:64` (`run_git`) runs distinct git commands once each per invocation (`main`, `read_base_ref`, `changed_files`, `changed_hunks`); `phaseb/docrefs.py:301` (`tracked_files`) runs once per `phaseb.py` invocation, since each invocation lists one question and each Doc lister calls it or `CorpusIndex.build` once. `auditme-stop.sh` runs `git rev-parse` on different directories.
- Hits: No hits

#### A25 (sampled): Shallow immutable wrapper
- Mode: full
- Inspected: every module-level `MappingProxyType`/`frozenset`/`tuple` wrapper read from another module: `core.py` `BARE_GENERIC_NAMES`, `EXTRA_ROOT_NAMES`, `ROOT_MODULES` (empty, and rebuilt from `(Path, str)` pairs), `SIDE_EFFECT_CALL_NAMES`; `candidates.T2_ENUM_BASES`; `registry.py` `CHECKS`, `PROJECT_CHECKS` (function references); `project_hygiene.SPEC_SKIP_PARTS`. Every member is a string, a path or a function; none is a `dict`/`list`/`set`, a nested container, or a non-frozen project dataclass.
- Hits: No hits

#### S1 (sampled): Type annotations on every signature
- Mode: full
- Inspected: every tracked non-test Python file (`git ls-files '*.py'` outside `tests/` directories), via `ruff check --select ANN` (ruff 0.17.4); test files counted, not enumerated, as the question requires. Shell files have no signatures to annotate.
- Hits: No hits (non-test source: every signature annotated)
- Test count (files under a `tests/` directory): 130 missing parameter annotations (126 ANN001, 3 ANN003, 1 ANN002), 32 missing return annotations (30 ANN201, 2 ANN202); 9 modules affected, 25 of 34 test modules fully annotated. No AGENTS.md test-annotation exemption to drift-check.

#### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake
- Mode: full
- Inspected: every tracked Python file with `ruff check --select N`, against `claude/rules/auditme/coding-standards.md` (Naming); variable and function names in `bin/check-foreign-names.sh`, `bin/install-claude.sh`, `claude/hooks/auditme-stop.sh`.
- Hits: No hits. Ruff's N806 reports function-local UPPER_SNAKE constant collections (e.g. `rules/state_and_effects.py:282 MUTATION_METHODS`, `rules/error_handling.py:90 SAFE_ATTRS`); each is a constant, which the standards name UPPER_SNAKE, and every function-local constant collection in the tree uses that form, so the tree is consistent (as review-6 judged). Shell scripts: script constants upper, working variables lower, functions lower_snake.

#### S3 (sampled): TYPE_CHECKING block placement
- Mode: full
- Inspected: every top-level `if typing.TYPE_CHECKING:` block in tracked Python files (source and tests, AST scan), compared with the last top-level import of its file.
- Hits: No hits. Every block uses `if typing.TYPE_CHECKING:` immediately after the module's imports; the indented occurrences in `tests/phaseb/test_t1_candidates.py:120` and `tests/test_core.py:141` are inside fixture source strings.

#### S4 (sampled): Project-specific rule files
- Mode: full
- Inspected: `claude/rules/auditme/coding-standards.md`, `imports.md`, `dependencies.md` and the argparse allowance in `~/.claude/rules/python/argparse.md`, plus the AGENTS.md no-project-names rule; checked the parts with no sweep rule: `as` imports, `from __future__`, stdlib `logging`, `print()` outside CLI entry points, `assert` in product code, `%`/`.format` formatting, broad excepts and `contextlib.suppress` (the review-7 `suppress(Exception)` sites are gone since review-6's commit), argparse trailing-comma form; ran `bin/check-foreign-names.sh` over every in-scope file (exit 0, no match). Sweep-reported sites (`from-import`, `silent-broad-except`, `except-interpolation`) excluded.
- Hits: No hits. `print` appears only in the CLI entry points `checks/audit.py`, `checks/phaseb.py`, `checks/changed.py` and in the checker's JSON-lines emitter `auditme/core.py:60`; the one remaining `except Exception` outside the sweep's hit (`phaseb/architecture.py:53`) re-raises as `PhaseBError`.

#### P1 (sampled): O(n^2) on real-size inputs
- Mode: full
- Inspected: every nested loop and multi-generator comprehension in non-test Python source (AST scan for inner iterables over project-wide collections, then read each); measured with cProfile on this repository and on one project with 743 `.py` files under `src/` (2026-11-22). `check_duplicate_call_sequence` (`rules/duplication.py:616`) and the suffix scan in `check_asymmetric_exception_translation` (`rules/error_handling.py:350`) are unchanged since review-6 (`git log -L eba7404..HEAD` shows no commit), so not reported again. Nested walks in `check_in_function_imports`, `translator_envelopes`, `check_redundant_sink_caller_plus_callee` are per-function re-walks, linear in tree size times nesting depth.
- Hits:
  - `claude/skills/auditme/checks/auditme/phaseb/testmap.py:272` - `TestIndex.test_files` scans every test file against every module of the site's callers for each site (sites x test files x modules); listing T1 on the 743-file project spent 20.5 s of 35.8 s (cProfile, 2026-11-22) in it for 1388 sites; an index from module to importing test files makes each site a lookup.

#### P2 (sampled): Blocking I/O in hot paths
- Mode: full
- Inspected: every tracked Python and shell file for training loops, request handlers and callbacks; the checker and the Phase B lister are batch CLIs, and the Stop hook (`claude/hooks/auditme-stop.sh`) runs the checker once per turn by design.
- Hits: No hits

#### P3 (sampled): Repeated expensive computation per request
- Mode: full
- Inspected: every non-test Python source file, for values recomputed inside loops whose inputs do not change (file walks, parses, globs, graph searches); review-6's P3 sites confirmed fixed (`caught_elsewhere` removed, `declared_root_modules` and `ruff_executable` cached in `INDEX_CACHE`, `reach` memoised in `TestIndex.refs`); `subprocess-without-memoisation` sweep sites excluded. `auditme.core.all_py_files` (`core.py:245`) re-globs the root once per check (214 calls in one sweep of the 743-file project), measured 3.9 s of a 245 s profiled sweep (1.6%, 2026-11-22): small, not a hit. Phase B listers run one question per process, so `read_audited_files` parses once per run.
- Hits:
  - `claude/skills/auditme/checks/auditme/phaseb/testmap.py:183` - `imports_module` rebuilds `imported_names(file)` (a pass over the file's bindings and top-level imports) on every call, and `test_files` (line 272) calls it per site x test file x module and once more for `reexport_names`; the result depends only on the file. Listing T1 on the 743-file project called `imported_names` 1,533,427 times, 15.5 s of 35.8 s (cProfile, 2026-11-22); computing it once per test file in `TestIndex` removes the repeat.

#### Sec1 (sampled): Secrets in source. API keys, passwords, tokens.
- Mode: full
- Inspected: grep for api key/password/secret/token/private-key markers over every tracked Python, shell, YAML and TOML file; `.github/workflows/ci.yml`, `.github/workflows/docs.yml` (token comes from `secrets.GITHUB_TOKEN` via `env:`, not a literal); project-setup CI templates (secret referenced by name only).
- Hits: No hits

#### Sec2 (sampled): Input validation at system boundaries. CLI args, HTTP bodies, file paths from user.
- Mode: full
- Inspected: `claude/skills/auditme/checks/audit.py` `main` (scope is_dir, `--package` bare-name check, `--extra-root` containment and is_dir); `claude/skills/auditme/checks/changed.py` `parse_args`/`main` (`--base` refused when it starts with `-`, git failures raised as `ChangedError`); `claude/skills/auditme/checks/phaseb.py` parser (question validated by `registered_question`, depth >= 1, `--batch-size` checked in `batches.plan_batches`, `--depth` restricted to depth questions); `claude/hooks/auditme-stop.sh` (payload parsed with jq, checker trust by git common dir); `bin/check-foreign-names.sh`; `bin/install-claude.sh`. No HTTP boundary exists.
- Hits: No hits

#### Sec3 (sampled): Command injection. Unsanitised input passed to `subprocess` or shell-execution helpers.
- Mode: full
- Inspected: every `subprocess` call in non-test code (`changed.py:64`, `changed.py:236`, `auditme/rules/project_hygiene.py:50,104,112,225`, `auditme/phaseb/docrefs.py:301`) - all list argv, no `shell=True`, `--base` guarded against option injection; no `os.system`/`eval`/`exec`; shell scripts (`auditme-stop.sh`, `check-foreign-names.sh`, `install-claude.sh`) quote every expansion, use `grep -F -e` and `--`, no `eval`/`bash -c`; CI `run:` steps interpolate only `secrets.GITHUB_TOKEN` through `env:`.
- Hits: No hits

#### Sec4 (sampled): Path traversal. User-supplied paths joined to project paths without containment.
- Mode: full
- Inspected: `audit.py` (`--package` must be a bare name; `--extra-root` checked with `auditme.core.path_inside`); `auditme/core.py` `declared_roots` (`path_inside` at line 376) and `extra_roots`; `auditme/phaseb/docrefs.py` `read_path_targets` (normalised, `..` refused, matched against the tracked-file index); `auditme/phaseb/batches.py` (batch/result/plan file names built from integers and constants under the operator's run dir); `phaseb.py` `ledger_path` (question is a registered name).
- Hits: No hits

#### Sec5 (sampled): PII in logs. Raw text inputs at INFO level or above.
- Mode: full
- Inspected: every non-test Python file for `logging`/`logger`/`loguru` use (none; the checker writes JSON hits and error messages to stdout/stderr only; `architecture.py` mentions logger names only as detection data); shell scripts' output (paths and checker reports only).
- Hits: No hits

#### T3 (sampled): Integration vs unit balance. Pipeline orchestrators have at least one end-to-end test.
- Mode: full
- Inspected: orchestrators and their end-to-end tests - `audit.py` (`tests/test_driver.py`, runs the entry point as a subprocess), `changed.py` (`tests/test_changed.py`), `phaseb.py` (`tests/phaseb/test_cli.py`, drives candidates, plan, check, merge, report and dismiss), `claude/hooks/auditme-stop.sh` (`tests/test_stop_hook.py`), `bin/install-claude.sh` (`tests/test_install_claude.py`), `bin/check-foreign-names.sh` (`tests/test_check_foreign_names.py`).
- Hits: No hits

#### D1 (sampled): Declared in pyproject. Every imported third-party module is declared.
- Mode: full
- Inspected: every `import`/`from` in tracked Python files. Third-party imports actually executed: `pytest`, `hypothesis` (tests), both in the `dev` group. `loguru`, `requests`, `orjson` occur only inside fixture strings in `tests/phaseb/test_architecture_candidates.py`, `tests/test_error_handling.py`, `tests/test_imports_and_surfaces.py`; `pkg`/`probe`/`a`/`other` are fixture modules.
- Hits: No hits

#### D2 (sampled): Unused declarations. Every declared dependency is imported somewhere, or run as a command.
- Mode: full
- Inspected: `pyproject.toml` dependency groups: `hypothesis`, `pytest` (imported in tests); `ruff` (run by `subprocess` in `auditme/rules/project_hygiene.py` and provided by the `ruff-pre-commit` repo in `.pre-commit-config.yaml`); `mkdocs` (run in `.github/workflows/docs.yml` `run:` steps); `mkdocs-material` (theme `name: material` in `mkdocs.yml`).
- Hits: No hits

#### D3 (sampled): Lockfile coherence. Already script-checked; flag if the script's lockfile-drift hit appears.
- Mode: full
- Inspected: `/tmp/audit-auditor.jsonl` (no lockfile-drift hit); `uv lock --check` resolves cleanly.
- Hits: No hits

#### Doc3 (sampled): README.md and AGENTS.md consistent.
- Mode: full
- Inspected: `README.md` (whole), `AGENTS.md` (whole), checked against `.pre-commit-hooks.yaml`, `.pre-commit-config.yaml`, `bin/install-claude.sh`, `claude/` layout (`hooks/auditme-stop.sh`, `rules/auditme`, `skills/auditme`, `skills/auditme-project-setup`), and the docs statements on the same points: `docs/index.md:1-20` (what the repository holds, installer), `docs/setup.md:100-130,163-164` (installer, agents repository, hook types), `docs/concepts.md:53-58` (Stop hook registration), `docs/reference/cli.md:245-256` (hook stages, commit-msg hook type). Compared: repository contents, installer behaviour (links and Stop-hook registration), source of the other shared rules, test command (identical in both files), `no-project-names` hook and the hook types to install (repo config has `auditme-all` at `pre-push` and `no-project-names` at `commit-msg`, matching AGENTS.md:32-33).
- Hits: No hits

#### Spec review
- agents/specs/auditme-false-positives/spec.md - no gap
- agents/specs/listed-phase-b-architecture-questions/spec.md - no gap
- agents/specs/listed-phase-b-documentation-questions/spec.md - no gap
- agents/specs/listed-phase-b-test-questions/spec.md - no gap
- agents/specs/project-setup/spec.md - no gap
- agents/specs/raises-section-resolution/spec.md - no gap
- agents/specs/repeatable-phase-b/spec.md - no gap

Checks run per spec: Version/Status/Date header present; Module location, API, Error handling, Implementation, External dependencies sections present; no empty or placeholder-only section, no TBD; API has a code block; every relative markdown link (and every anchor into another .md) resolves. Every spec is listed in `agents/specs/index.md`.

## Prior findings re-verified

Review-8's O1 shipped in the review-8 task list: `grep -rn 'suppress(Exception)' claude/skills/auditme/checks` prints nothing. Review-8 raised no finding. No task list under `agents/tasks/audit-reviews/` has an incomplete task.

## Decisions

None this review.

## Answers

Answered on the review page on 2026-11-22, with no comment.

| Item | Answer |
|---|---|
| F1 | Fix |
