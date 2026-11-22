# Audit Review 14

**Date:** 2026-11-22
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`); every sampled question ran on the whole tree
**Commit:** 7162f02a3a382b6f4d7ca7c341247001bd606c8a
**Script output:** /tmp/audit-auditor.jsonl (48 hits, 48 accepted, 0 unaccepted)
**Script version:** 3e86b7b0e21a73d2d0ff0485ab37065e38bf96c8ae4a599b905029c3c03683a0
**Convergence note:** the third loop the operator delegated on 2026-11-22. Measured on 2026-11-22: 65 listed candidates judged (T1 36, Doc5 13, Doc4 11, A4 3, A1 1, T2 1); every review-13 fix confirmed, and the two guards it added hold (no `cached_roots` subscript; the exit-2 paragraph states a rule). Two findings, down from five: one line of that new paragraph names two examples that print differently (F1), and one boundary check in `audit.py` that tests existence where it needs a directory (F2).
**Review page:** https://claude.ai/artifact/PousW45Xf4PRB9v3rp4nFq

## What is being reviewed and how

This is the checker repository's fourteenth audit of its own code, a whole-tree pass. The operator delegated the loop on 2026-11-22, so Claude answers this page by taking each recommendation, and records that in the Answers section.

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 48 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 65 judged; every other listed question carried every verdict |
| `phaseb.py check` on every listed question | pass, no retries |
| Every sampled question returned a hit list or "no hits" | pass |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| Prior findings to re-verify | review-13 F1-F5: shipped and confirmed |

## Summary

The sweep reports 48 hits, all accepted. Phase B leaves 1 listed verdict open (Doc5). The sampled questions flag Sec2 1. The spec review finds no gap.

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits.

## Phase B findings (consolidated)

### F1. The exit-2 paragraph's examples include two argparse errors (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed). **Severity:** low.
- **Location:** `docs/reference/cli.md:176`, rewritten by Task 1 of the review-13 task list.
- **Description:** the paragraph says a failing Phase B step prints `phaseb.py: ` and the message, and gives an unregistered `--question` and a missing root as examples. Both are refused by argparse instead, which prints `phaseb.py <command>: error: argument ...` (checked on 2026-11-22). Line 174 already states those two cases correctly.
- **Recommendation:** drop those two examples from line 176, leaving the Phase B step failures.

### F2. `audit.py --package` accepts a plain file (Sec2)

- **Category:** Sec. **Question:** Sec2 (sampled). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/audit.py:224`.
- **Description:** the check is `root.exists()`, so with `src/<name>` a plain file, `--package <name>` runs only the project-level checks and exits 0 (reproduced on 2026-11-22). The scope and `--extra-root` checks refuse a non-directory with exit 2.
- **Recommendation:** test `root.is_dir()` and exit 2 with "not a directory", as the scope check does; test it. Grep the checker's entry points for any other `.exists()` on a path that must be a directory (on 2026-11-22 the other two, `core.py:269` and `:887`, test files).

## Phase B per-question results

Listed questions: the verdicts are in `agents/audit-reviews/ledger/`; `phaseb.py report <root> --question <Q>` prints the open ones: Doc5 (F1).

#### A2 (sampled): Except tuple coverage
- Mode: full
- Inspected: every `try` in every tracked `.py` file at `7162f02` (`git ls-files '*.py'`), listed by AST with its handler types and the disk, decode, json and subprocess calls in its body, each read; plus the Python diff since review-13's `b0166c2` (`scan_accepted_lazy_imports` split in `core.py`, `roots, _ = cached_roots(...)` in `phaseb/architecture.py` and `phaseb/candidates.py`), which adds no `try`. Decoding disk bodies catch `OSError` and `UnicodeDecodeError` (`core.py:154`, `phaseb/architecture.py:88,745`, `phaseb/batches.py:148,207`, `phaseb/candidates.py:194,398,576`, `phaseb/docrefs.py:86`, `phaseb/ledger.py:67`, `phaseb/testmap.py:56`, `changed.py:197`); `batches.py:148` also catches `json.JSONDecodeError`. Byte-only and stat bodies (`core.py:97,125,144`) and write bodies (`batches.py:129`, `ledger.py:91,105`) catch `OSError`. In-memory `json.loads`/`tomllib.loads` bodies (`ledger.py:76`, `changed.py:255`, `rules/project_hygiene.py:64`, `core.py:349`) touch no disk; subprocess-only bodies (`rules/project_hygiene.py:48,102,222`, `changed.py:63,235`, `docrefs.py:299`, `tests/test_project_hygiene.py:26`) are not disk bodies; `architecture.py:44` is try/finally. No translating decorator or `contextmanager` envelope in the source; `candidates.py:644` decodes with `errors='replace'`. No `pandas` or `.gz` use.
- Hits: No hits

#### A3 (sampled): Domain-error layering
- Mode: full
- Inspected: every `raise` with an exception in every tracked non-test `.py` file at `7162f02` (AST listing by raised type). Raised types: `auditme.core.RootsError` and `CachedReadError` (`core.py`), `auditme.phaseb.errors.PhaseBError` (every `phaseb/` module; `auditme.phaseb.PhaseBError` in `phaseb.py`), `changed.ChangedError`; `SystemExit` at the entry points (`audit.py`, `changed.py`, `phaseb.py`); `argparse.ArgumentTypeError` in the argparse `type=` callables in `phaseb.py`, the type argparse requires. The six `ValueError`s at `phaseb/batches.py:181-198` are sweep hits (`layer-has-domain-error-raises-stdlib`, accepted). No `rules/` module raises. Test-file raises are fakes.
- Hits: No hits

#### A5 (sampled): Two sources of truth
- Mode: full
- Inspected: module state rebound by the driver (`auditme.core.EXTRA_ROOT_NAMES` / `DECLARATION_IGNORED` at `audit.py:175-176`) against `extra_roots`, `declared_roots`, `cached_declared_roots` and `cached_roots`; `ROOT_MODULES` rebound with the roots; `phaseb.py` `--depth` against `Plan.depth`; `today=None` parameters in `phaseb/ledger.py` and `phaseb/batches.py`; `core.cached_per_run` (`core.py:456`) and its callers, including the new `accepted_lazy_imports` -> `scan_accepted_lazy_imports` split (`core.py:263-267`): one value keyed on `(name, scope)` in `INDEX_CACHE`, cleared by the driver each run. Each precedence is stated and enforced.
- Hits: No hits

#### A6 (sampled): Stage method dual-path
- Mode: full
- Inspected: every class in every tracked `.py` file and every method that assigns to `self.<attr>` or mutates a `self` container (AST listing, each match read). No pipeline-stage class. Self-mutating methods: `SiteCounter.next` (`phaseb/architecture.py:107`, returns an `int`, not a tuple) and `IndexEntries.add_module` / `record` (`phaseb/docrefs.py:225,241`, return `None`). `TestIndex.refs` (`phaseb/testmap.py:208`) only reads `self` and builds local dicts; `TestIndex.importers` is a `functools.cached_property`.
- Hits: No hits

#### A7 (sampled): Constructor purity
- Mode: full
- Inspected: every `__init__`, `__post_init__` and `__new__` in every tracked `.py` file (AST listing): `SiteCounter.__init__` (`phaseb/architecture.py:104`, an empty `Counter`), and the test fakes `Result.__init__` (`tests/test_project_hygiene.py:142`) and `LockResult.__init__` (`tests/test_project_hygiene.py:204`), which assign constants and arguments. No `__post_init__` or `__new__`. No I/O, no expensive compute, no argument mutated.
- Hits: No hits

#### A8 (sampled): Late dataclass mutation
- Mode: full
- Inspected: every `@dataclass` in the tracked `.py` files (all `frozen=True` except `ClassInfo` and `IndexEntries` in `phaseb/docrefs.py:149,217` and `TestIndex` in `phaseb/testmap.py:192`), and every attribute store whose target is not `self`/`cls` and every `setattr`/`__setattr__` call across every tracked file, tests included (AST scan). Non-self stores: module rebinds at `audit.py:175-176` and `tests/conftest.py:87` (not dataclass instances); `tests/phaseb/test_model.py:48,50`, which assert `FrozenInstanceError`; every other `setattr` is `monkeypatch.setattr` on a module or class. `ClassInfo` is built complete; `IndexEntries()` is filled only through its own methods before the frozen `CorpusIndex` is built from it; `TestIndex` is built complete in `testmap.py`.
- Hits: No hits

#### A9 (sampled): Pure-named function side effects
- Mode: full
- Inspected: every function in every tracked `.py` file whose name (leading underscores stripped) starts with a pure prefix, found by an AST walk at `7162f02`, with each body's calls listed. Functions named in `CHECKS` or `PROJECT_CHECKS` in `claude/skills/auditme/checks/auditme/registry.py` excluded under the registered-check carve-out (every `check_*` with I/O, such as `check_ruff`, `check_lockfile`, `check_ruff_version` and `check_cli_entry_missing_error_envelope`, is registered; no unregistered `check_*` exists outside tests). The remaining non-test pure-named functions read: `load_test_index`/`load_test_map` (`phaseb/testmap.py`; read the package and its test tree, which is what they load), `parse_result` (`phaseb/batches.py`; `json.loads` on a string), `parse_verdict` (`phaseb/ledger.py`; in memory), `resolve_setting` (`phaseb/docrefs.py`; `dataclasses.replace`), `is_t2_candidate`/`is_well_defined_type` (`phaseb/candidates.py`; `walk_within_scope` is an AST walk, `ast.parse` on an annotation string), `parse_spec_def` (`rules/project_hygiene.py`; parses a string), `parse_args` (`changed.py`) and `build_parser` (`phaseb.py`; argparse only), and the AST predicates. The Python diff since review-13's base `b0166c2` (`core.accepted_lazy_imports` split into a cached wrapper and `scan_accepted_lazy_imports`; `cached_roots` unpacking in `architecture.py` and `candidates.py`) adds no pure-named function with I/O.
- Hits: No hits

#### A10 (sampled): Predicate semantics
- Mode: full
- Inspected: every `is_*`, `has_*` and `should_*` function outside the test trees, each body read against its name and docstring: `core.py` (`is_test_relpath`, `is_dunder_all_assignment`, `is_main_guard`), `phaseb/architecture.py` (`is_constant_operand`, `is_enum_class`, `is_under`, `is_external_call`), `phaseb/candidates.py` (`is_stub`, `is_builtin_call`, `is_overload`, `is_frozen_dataclass`, `is_well_defined_class`, `is_well_defined_type`, `is_t2_candidate`), `phaseb/docrefs.py` (`is_path_shaped`), `phaseb/testmap.py` (`is_test_path`, `is_fixture`, `is_property_test`), `rules/duplication.py` (`is_pytest_param`), `rules/error_handling.py` (`is_broad_handler`, `is_categorical_class_name_expr`, `is_tomllib_call`, `is_toml_source`, nested `is_domain`, `is_bound`), `rules/style_and_naming.py` (`is_stdlib_public_access_only`, `is_fixed_length_tuple`, `is_leading_underscore`). None changed since `b0166c2`. No `should_*` function exists.
- Hits: No hits

#### A12 (sampled): assert misuse
- Mode: full
- Inspected: an AST walk for `ast.Assert` and `git grep -n -E '^\s*assert\b'` over every tracked `.py` file outside `claude/skills/auditme/tests/`, `claude/skills/auditme-project-setup/tests/` and `tests/`.
- Hits: No hits (no `assert` statement outside the test trees)

#### A13 (sampled): Same value to multiple structural slots
- Mode: full
- Inspected: an AST walk of every call in every tracked non-test `.py` file for a non-constant argument expression passed to two or more slots, then a pass restricted to class calls. Read: `run_check(check, scope, scope)` at `checks/audit.py:220,231` (a function, not a constructor; the comment at `:228` says the scope stands in for the root project checks ignore), `DocTarget(kind, rel, rel, 1, last_line)` at `phaseb/docrefs.py:281` (inside the explicit factory `path_target`, with the `DocTarget.id` field comment documenting that a file's id is its path). The rest are `dict.get(key, key)` defaults and `getattr(check, '__name__', check)`.
- Hits: No hits

#### A14 (sampled): Repeated computation per request
- Mode: full
- Inspected: every helper reading project state (`AGENTS.md`, `pyproject.toml`, `git ls-files`, the ruff executable) found by grep over `claude/skills/auditme/checks/`, and its call sites in the sweep driver (`checks/audit.py`: `PROJECT_CHECKS` once, `CHECKS` once per root) and in each `phaseb.py` command. Cached per run through `core.cached_per_run`: `accepted_lazy_imports` (`core.py:263`, the review-13 F5 hit, now cached by `5a48e7b`), `project_bans_as_imports`, `read_package_layering`, `project_has_all_guard`; `cached_roots` for the roots. Uncached readers run once per invocation: `check_lockfile` (`project_hygiene.py:98`, a project check), the `pyproject.toml` and `AGENTS.md` readers in `phaseb/architecture.py:742` and `phaseb/candidates.py:498-573`, and `tracked_files` (`phaseb/docrefs.py:294`), one per `phaseb.py` command. Previously dismissed `auditme.core.all_py_files` (review-11 F5) is unchanged and not reported again.
- Hits: No hits

#### A15 (sampled): Duplicate constructor / serialisation logic
- Mode: full
- Inspected: every call to a class defined in the repository, grouped by class, in source and test trees. `Candidate` is built only in the factories in `phaseb/candidates.py`; `Verdict` from a reviewer record (`phaseb/batches.py`) and from a ledger row (`phaseb/ledger.py`), different inputs; `Site`, `Scope`, `DocTarget`, `ClassInfo`, `TestIndex` and `SiteCounter` with differing field sets or a single site; exception classes take a message only. Tests build `Candidate`/`Verdict` through `make_candidate`/`make_verdict` in `claude/skills/auditme/tests/conftest.py`. The diff since `b0166c2` adds no construction site.
- Hits: No hits

#### A16 (sampled): CLI entry envelope
- Mode: full
- Inspected: `git ls-files '*.py'` for any `cli/*.py` (none) and `git grep cappa` (only the checker's own rule text in `rules/error_handling.py`). The `run_*` functions in `claude/skills/auditme/checks/phaseb.py` and `run_check` in `checks/audit.py` are not in a `cli/` module, so the enumeration does not reach them.
- Hits: No hits

#### A18 (sampled): Hot-path setup
- Mode: full
- Inspected: grep for `def on_(step|log|evaluate|batch_*)` over every tracked `.py`/`.sh` file; the only matches are fixture source strings in `claude/skills/auditme/tests/test_state_and_effects.py` (lines 821, 844), which are test inputs for the sweep's own callback check, not callbacks of this project.
- Hits: No hits

#### A20 (sampled): Mutable module-level singleton
- Mode: full
- Inspected: every module-level assignment in non-test modules and `tests/conftest.py`; for each mutable `dict`/`set`/`list` (`DISK_IO_NAMES`, `MUTABLE_VALUE_SHAPES`, `MUTABLE_CONSTRUCTORS`, `COMMANDS`, `STDLIB`, `STRFTIME_TOKENS`, `PARAMETRIC_NONBUILTIN_GENERICS`, `TYPING_DEPRECATED_ALIASES`, `RULE_HELP`, `SOURCE_CACHE`, `GIT_ENV_ARGS`, `__all__` lists) grepped `from <module> import <name>`, `<module>.<name>` and `sys.modules[...]` across the whole tree including tests and `bin/`. Each is read only in its own module (the `'COMMANDS'` in `test_annotated_all.py` and `module.__all__` are fixture strings). Readers of `core.EMITTED`, `core.UNREADABLE`, `core.INDEX_CACHE` and `candidates.REGISTRY`/`KINDS`/`TAKES_DEPTH` are sweep hits (`mutable-module-level-exported`, accepted), not judged here.
- Hits: No hits

#### A21 (sampled): Lazy init race
- Mode: full
- Inspected: every `is None:` test and every `global` statement in non-test modules; the per-run caches in `claude/skills/auditme/checks/auditme/core.py` (`corpus_index`, `cached_source`, `cached_roots`, `audit_roots`) use `key not in CACHE` and are not `if X is None: X = ...` patterns; grep for `thread`, `concurrent`, `multiprocessing`, `asyncio` found only string literals in rule tables - the checker runs single-threaded.
- Hits: No hits

#### A22 (sampled): Fall-through after partial handling
- Mode: full
- Inspected: AST scan of every non-test module for an `if` block holding a `try` with a raising handler whose body does not end in return/raise and is followed by more statements; one candidate, `claude/skills/auditme/checks/changed.py:196` (`scope_records`), where the `.py` branch widens `ranges` and the shared `records.append` that follows is intended for both branches - no retry of a translated error. Shell scripts `bin/check-foreign-names.sh`, `bin/install-claude.sh`, `claude/hooks/auditme-stop.sh` read in full.
- Hits: No hits

#### A23 (sampled): Discarded multi-return
- Mode: full
- Inspected: AST scan of every function annotated to return a `tuple[...]` in non-test modules and every call whose result is subscripted, discarded or bound whole; plus attribute reads on call results (`read_run_check(...).problems`, a single-field dataclass). Partial uses `cached_source(path)[0]`/`[1]` (`core.py:175,184`), `privacy(...)[0]` (`core.py:927`, second component only names the deciding rule) and `registered(question)[1]`/`[2]`/bare call (`candidates.py:142,151,161`, plain accessors / validation) drop nothing documented as changing how the kept component is used.
- Hits: No hits

#### A24 (sampled): Identity of subprocess / shell-out calls
- Mode: full
- Inspected: every `subprocess.*` call and git helper in non-test modules and the shell scripts. `claude/skills/auditme/checks/changed.py` (`run_git`, `git_lines`, `read_base_ref`, `changed_files`, `changed_hunks`, `sweep`) runs each distinct git command once per invocation; `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:301` `tracked_files` is called once per Phase B run (one question per run: via `CorpusIndex.build` for Doc1, directly at `candidates.py:641` for Doc2); `auditme-stop.sh` calls `git rev-parse` on distinct directories. `project_hygiene.py:50,104,225` are sweep hits (`subprocess-without-memoisation`, accepted).
- Hits: No hits

#### A25 (sampled): Shallow immutable wrapper
- Mode: full
- Inspected: every module-level `types.MappingProxyType(...)`, `frozenset(...)` and `tuple` constant in non-test modules read from another module (`core.ROOT_MODULES` - `Path -> str`; `core.EXTRA_ROOT_NAMES`, `registry.CHECKS`/`PROJECT_CHECKS` - functions; `project_hygiene.SPEC_SKIP_PARTS` and the other `frozenset` name tables - strings). Every member is a `str`, `Path` or function.
- Hits: No hits

#### S1 (sampled): Type annotations on every signature
- Mode: full
- Inspected: every tracked `.py` file (`git ls-files '*.py'`) with `ruff check --select ANN` (ANN is not in the project's ruff `select`); shell files have no signatures to annotate. No AGENTS.md note records a test-annotation exemption, so there is no figure to drift-check. The 2 ANN401 reports (`tests/test_imports_and_surfaces.py:823`, `typing.Any`) are annotations present, not missing.
- Hits: non-test source: No hits. Tests (count only): 130 missing parameter annotations, 32 missing return annotations, 7 test modules affected, 27 of 34 test modules fully annotated (unchanged from review-13).

#### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake
- Mode: full
- Inspected: every tracked `.py` file with `ruff check --select N` plus a grep of `def`/`class` and module-level bindings against the Naming section of `claude/rules/auditme/coding-standards.md`; variable case in `bin/check-foreign-names.sh`, `bin/install-claude.sh`, `claude/hooks/auditme-stop.sh` and the other tracked `.sh` file. The only ruff reports are N806 on function-local literal constant collections (`MUTATING_METHOD_NAMES`, `SAFE_ATTRS`, `STDLIB_EXCS`, `PURE_PREFIXES`, `HOT_IO`, ...) in `rules/duplication.py`, `rules/error_handling.py`, `rules/state_and_effects.py`: constants named UPPER_SNAKE as the rule asks, with no lower-case function-local literal constant anywhere, so one idiom (as reviews 9, 12 and 13 judged). Lower-case function-local frozensets (`docrefs.py:182`, `imports_and_surfaces.py:138`) are computed values, not constants. The one shell change since review-13 (`bin/check-foreign-names.sh:26`) keeps lower_snake `list` for a working variable.
- Hits: No hits

#### S3 (sampled): TYPE_CHECKING block placement
- Mode: full
- Inspected: every `TYPE_CHECKING` occurrence in tracked `.py` files. Every module-level `if typing.TYPE_CHECKING:` (`audit.py:92`, `changed.py:38`, `phaseb/batches.py:24`, `phaseb/ledger.py:22`, `phaseb/testmap.py:19`, each `rules/*.py`, `tests/conftest.py:37` and the test modules) sits directly after the last import, including `changed.py` and `conftest.py`, whose last imports follow a `sys.path` set-up. Indented occurrences (`test_t1_candidates.py:120`, `test_imports_and_surfaces.py:163,747`, `test_core.py:201`) are fixture strings. No `from __future__ import annotations` line in any tracked file.
- Hits: No hits

#### S4 (sampled): Project-specific rule files
- Mode: full
- Inspected: the rule files AGENTS.md points to (`claude/rules/auditme/coding-standards.md`, `imports.md`, `dependencies.md`) and the shared python rules they reference (`argparse.md`, `asserts.md`, `logging.md`), checked across the non-test source files for what the sweep does not enforce: `as` imports, wildcard imports, stdlib `logging`, `%`/`.format()` formatting, `assert` in product code, leading-underscore names, clean `__init__.py`, argparse use and trailing-comma style, `print()` use. Only matches are rule text and regexes inside the checker itself, and the `from` imports the sweep already reports. argparse is allowed (the checker is standard-library only); every `ArgumentParser`/`add_argument`/`add_parser` call in `audit.py`, `changed.py`, `phaseb.py` is one argument per line with a trailing comma (`audit.py:137` takes no arguments); `print()` is confined to the three CLI entry points and `core.py:60`, which emits the JSON-lines hit stream.
- Hits: No hits

#### P1 (sampled): O(n^2) on real-size inputs
- Mode: full
- Inspected: every rule and phaseb module, and the code changed since review-13 (`core.accepted_lazy_imports` now per-run cached; `cached_roots` unpacking in `phaseb/architecture.py` and `phaseb/candidates.py`), none of which adds a loop. Measured on one project with 766 tracked Python files: full sweep 53.8 s unprofiled; under cProfile (209 s) the largest checks are `check_asymmetric_exception_translation` 9.5% (dismissed in review-6), `check_redundant_sink_caller_plus_callee` 5.7%, `check_translator_envelope_gap` 5.6%, `check_in_function_imports` 4.5%, `check_duplicate_call_sequence` 4.3% (dismissed), `check_text_patterns` 4.2%; every one under a tenth.
- Hits: No hits

#### P2 (sampled): Blocking I/O in hot paths
- Mode: full
- Inspected: all tracked `.py` and `.sh` files for reads/writes in loops, handlers and callbacks. The only callback is the Stop hook (`claude/hooks/auditme-stop.sh`, unchanged since review-13), which runs `git` once and `changed.py` once per turn end. Checker file reads go through `core.cached_source` (85,113 calls, 1.5% of the profiled 766-file sweep, one disk read per file); `subprocess.run` is called 8 times per sweep (0.1%).
- Hits: No hits

#### P3 (sampled): Repeated expensive computation per request
- Mode: full
- Inspected: shared derivations across the sweep on the 766-file project: `corpus_index` 7 calls, 4.1% cumulative; `translator_envelopes` 3 calls (once per root), 2.3%; `accepted_lazy_imports` now computed once per run (3 calls, 1 scan, under 0.1%); `all_py_files` 1.2% (dismissed in review-11). Re-listing candidates in separate `plan`/`merge`/`report` invocations is one derivation per process; the `list_a1_candidates` recomputation of `translator_envelopes` (`phaseb/architecture.py`) measured 8.9% in review-13 and its code changed only in how `cached_roots` is unpacked.
- Hits: No hits

#### Sec1 (sampled): Secrets in source
- Mode: full
- Inspected: every tracked `.py`, `.sh`, `.toml`, `.yaml`/`.yml` file (`git grep -i` for api key, secret, password, token, private-key headers); `.github/workflows/ci.yml`, `.github/workflows/docs.yml` (the token comes from `secrets.GITHUB_TOKEN` through `env:`), the project-setup CI templates (the deploy key comes from `secrets.AUDITOR_DEPLOY_KEY`)
- Hits: No hits

#### Sec2 (sampled): Input validation at system boundaries
- Mode: full
- Inspected: `claude/skills/auditme/checks/audit.py`, `changed.py` and `phaseb.py`, `bin/check-foreign-names.sh`, `bin/install-claude.sh`, `claude/hooks/auditme-stop.sh`, `auditme/core.py` `declared_roots`. Each was run with a missing path, a directory where a file is expected and a file where a directory is expected: the audit.py scope, `--extra-root`, `--package` and an `AGENTS.md` directory; the changed.py repository root under default, `--all` and `--scope`; the phaseb.py root, `--out`, the run directory of `check` and `merge`, a ledger that is a directory and an `agents` that is a file; `AUDITOR_FOREIGN_NAMES` and the file arguments of check-foreign-names.sh; and the Stop hook with `HOME` missing, the installed checker as a directory and `.pre-commit-config.yaml` as a directory. install-claude.sh takes no path (its repository is derived from `BASH_SOURCE`, and other arguments pass through to the installer). Every other case reported the problem with a non-zero exit, or skipped as documented.
- Hits:
  - `claude/skills/auditme/checks/audit.py:223` - `--package <name>` where `src/<name>` is a file, not a package directory, passes the `root.exists()` check: the per-root checks run over a file, and the run exits 0 having reported only project-level hits. It should say "not a directory" with exit 2, the way the scope (line 163) and `--extra-root` (line 181) are checked. Reproduced: `audit.py <proj> --package pkgfile` with `src/pkgfile` a plain file printed one `ruff-format` hit and exited 0.

#### Sec3 (sampled): Command injection
- Mode: full
- Inspected: every `subprocess` call in tracked non-test Python (`changed.py` `run_git` and `sweep`, `auditme/rules/project_hygiene.py` ruff and `uv lock --check`, `auditme/phaseb/docrefs.py` `git ls-files`), the shell entry points (`bin/install-claude.sh` `exec uvx`, `bin/check-foreign-names.sh` `grep -F -e ... --`, `claude/hooks/auditme-stop.sh`), and the `run:` steps in `.github/workflows/*.yml`. Every call passes an argument list with no shell. The user-supplied `--base` ref is refused when it starts with `-`, and is placed after `--end-of-options`.
- Hits: No hits

#### Sec4 (sampled): Path traversal
- Mode: full
- Inspected: `audit.py` `--package` (a bare directory name only, with `.` and `..` refused) and `--extra-root` (`path_inside` containment); `auditme/core.py` `declared_roots` (containment check); `phaseb.py` (`--question` limited to registered questions before it builds the ledger path); `auditme/phaseb/batches.py` (batch file names built from integers); `auditme/phaseb/docrefs.py` `read_path_targets` (document tokens normalised, `..` refused, looked up in the git-tracked index only); `changed.py` `scope_records` (paths come from `git diff`).
- Hits: No hits

#### Sec5 (sampled): PII in logs
- Mode: full
- Inspected: every tracked Python and shell file for logging calls (`logging.`, `logger.`) and for what reaches stdout or stderr. Product code has no logger: it prints hits, file paths and error messages, and no raw user text.
- Hits: No hits

#### T3 (sampled): Integration vs unit balance
- Mode: full
- Inspected: the orchestrators and the tests that run them whole. The `audit.py` driver is run as a subprocess in `claude/skills/auditme/tests/test_driver.py`. `changed.py` has one case in `claude/skills/auditme/tests/test_changed.py` that runs the real `audit.py` in a temporary git repository. `phaseb.py` is run as a subprocess through plan, check, merge and report in `claude/skills/auditme/tests/phaseb/test_cli.py`. The Stop hook, the installer, check-foreign-names.sh and the published hooks are run by `tests/test_stop_hook.py`, `tests/test_install_claude.py`, `tests/test_check_foreign_names.py` and `tests/test_published_hooks.py`.
- Hits: No hits

#### D1 (sampled): Declared in pyproject
- Mode: full
- Inspected: an AST walk of every tracked `.py` file for absolute imports outside `sys.stdlib_module_names`, which found only `hypothesis` and `pytest` beyond the first-party modules (`audit`, `auditme`, `changed`, `conftest`, `phaseb`). Both are declared in `pyproject.toml` `[dependency-groups] dev`. The `loguru` and `pkg` imports in `tests/phaseb/test_architecture_candidates.py` are inside fixture strings, not real imports.
- Hits: No hits

#### D2 (sampled): Unused declarations
- Mode: full
- Inspected: the declared dependencies in `pyproject.toml`. `hypothesis` and `pytest` are imported. `ruff` is run as a subprocess in `auditme/rules/project_hygiene.py`, and `.pre-commit-config.yaml` names it through `astral-sh/ruff-pre-commit`. `mkdocs` is run in the `.github/workflows/docs.yml` `run:` steps. `mkdocs-material` registers the `material` theme, which `mkdocs.yml` names under `theme: name:`.
- Hits: No hits

#### D3 (sampled): Lockfile coherence
- Mode: full
- Inspected: `/tmp/audit-auditor.jsonl` (it has no `lockfile-drift` hit); `uv lock --check` (passed: "Resolved 36 packages")
- Hits: No hits

#### Doc3 (sampled): README.md and AGENTS.md consistent
- Mode: full
- Inspected: `README.md` (whole), `AGENTS.md` (whole); compared the component list (checker, `auditme-changed`/`auditme-all` hooks, `no-project-names` hook, Stop hook, `/auditme-project-setup` skill, `claude/rules/auditme/`), what `bin/install-claude.sh` installs, the source of the other shared rules and skills, and the test command (identical in `README.md:19` and `AGENTS.md:22`). Cross-checked against `docs/setup.md`, `docs/concepts.md:55`, `docs/reference/cli.md` statements on the installer and Stop hook registration, and `.pre-commit-config.yaml` stages (pre-commit, pre-push, commit-msg) behind `AGENTS.md:32-33`.
- Hits: No hits

#### Spec review
- agents/specs/auditme-false-positives/spec.md - no gap (Settings omitted, permitted by the criteria)
- agents/specs/listed-phase-b-architecture-questions/spec.md - no gap
- agents/specs/listed-phase-b-documentation-questions/spec.md - no gap
- agents/specs/listed-phase-b-test-questions/spec.md - no gap
- agents/specs/project-setup/spec.md - no gap (in-page link `#the-published-hooks` at line 221 resolves to the heading at line 487)
- agents/specs/raises-section-resolution/spec.md - no gap
- agents/specs/repeatable-phase-b/spec.md - no gap
- agents/specs/index.md - no gap (every entry links to an existing spec)

## Prior findings re-verified

Review-13's F1-F5 shipped in its task list (`tasks-12.md`) and are confirmed: `cached_per_run` is tested directly; the names hook exits 2 for a directory list; no `cached_roots(...)` call is subscripted, and a test now fails if one is; `accepted_lazy_imports` is cached per run. F4's rule-plus-examples paragraph holds, with one wrong example (F1 here). Earlier dismissals stand. No task list under `agents/tasks/audit-reviews/` has an incomplete task.

## Decisions

None this review.

## Answers

Decided by Claude on 2026-11-22: the operator delegated the loop that day ("keep doing whole-tree audits and fixes in a loop until there are no findings and do not stop waiting for me"), so every item takes its recommendation.

| Item | Answer |
|---|---|
| F1-F2 | Fix |
