# Audit Review 15

**Date:** 2026-11-22
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`); every sampled question ran on the whole tree
**Commit:** 793c8d83e98e6d05323e957f393b245d75ede84e
**Script output:** /tmp/audit-auditor.jsonl (48 hits, 48 accepted, 0 unaccepted)
**Script version:** 82809374a2f796b0ed5b36a47bcdebc16b7e29142fc6c7192240275ecf905fab
**Convergence note:** the first whole-tree audit with no finding, which ends the loop the operator delegated on 2026-11-22 ("until there are no findings"). Measured on 2026-11-22: 86 listed candidates judged (T1 41, Doc4 27, Doc5 14, A1 3, T2 1), no verdict open, the one changed verdict cleared by a named commit; every sampled question run on every tracked file with no hit; the spec review finds no gap. Whole-tree finding counts in the delegated loop: review-11 5, review-12 4, review-13 5, review-14 2, review-15 0.
**Review page:** https://claude.ai/artifact/1s8bhkuabaKZqHUgSsvdhh

## What is being reviewed and how

This is the checker repository's fifteenth audit of its own code, a whole-tree pass. It found nothing, so there is no item to answer and no task list.

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 48 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 86 judged; every other listed question carried every verdict |
| `phaseb.py check` on every listed question | pass, no retries |
| Every sampled question returned a hit list or "no hits" | pass: no hits |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| Prior findings to re-verify | review-14 F1-F2: shipped and confirmed |

## Summary

The sweep reports 48 hits, all accepted. Phase B leaves no listed verdict open, the sampled questions flag nothing, and the spec review finds no gap.

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits.

## Phase B findings (consolidated)

None.

## Phase B per-question results

Listed questions: the verdicts are in `agents/audit-reviews/ledger/`; `phaseb.py report <root> --question <Q>` prints the open ones. No listed question has any. The one verdict that changed, Doc5 on `docs/reference/cli.md:176`, cleared after `ca36952` removed its two wrong examples.

#### A2 (sampled): Except tuple coverage
- Mode: full
- Inspected: every `try` in every tracked `.py` file at `793c8d8` (`git ls-files '*.py'`), listed by AST with handler types and the disk, decode, json and subprocess calls in each body; flagged bodies read. The Python diff since review-14's `7162f02` (`audit.py:224` `is_dir()` check, `exists()` -> `is_file()` in `core.py:269`, `rules/imports_and_surfaces.py:279,408`, `rules/project_hygiene.py:100,199`, one new test in `tests/test_driver.py`) adds no `try`. Decoding disk bodies catch `OSError` and `UnicodeDecodeError` (`core.py:154`, `phaseb/architecture.py:88,745`, `phaseb/batches.py:148,207`, `phaseb/candidates.py:194,398,576`, `phaseb/docrefs.py:86`, `phaseb/ledger.py:67`, `phaseb/testmap.py:56`, `changed.py:197`); `batches.py:148` also catches `json.JSONDecodeError`. Byte-only, stat and write bodies (`core.py:97,125,144`, `phaseb/candidates.py:82`, `phaseb/batches.py:129`, `phaseb/ledger.py:91,105`) catch `OSError`. In-memory `json.loads`/`tomllib.loads` bodies (`phaseb/ledger.py:76`, `changed.py:255`, `rules/project_hygiene.py:64`, `core.py:349`) touch no disk and catch the decode error; subprocess-only bodies are not disk bodies; `phaseb/architecture.py:44` is try/finally. No translating decorator or `contextmanager` envelope in the source; no `pandas` or `.gz` use (the `gzip`/`pandas` mentions in `rules/error_handling.py` are rule logic).
- Hits: No hits

#### A3 (sampled): Domain-error layering
- Mode: full
- Inspected: every `raise` with an exception in every tracked non-test `.py` file at `793c8d8` (AST listing by raised type). Raised types: `RootsError` and `CachedReadError` (`core.py`), `PhaseBError` (every `phaseb/` module and `phaseb.py`), `ChangedError` (`changed.py`), `SystemExit` at the entry points (`audit.py`, `changed.py`, `phaseb.py`), `argparse.ArgumentTypeError` in the argparse `type=` callables in `phaseb.py`. The six `ValueError`s at `phaseb/batches.py:181-198` are sweep hits (`layer-has-domain-error-raises-stdlib`, accepted). No `rules/` module raises. Test-file raises are fakes.
- Hits: No hits

#### A5 (sampled): Two sources of truth
- Mode: full
- Inspected: module state rebound by the driver (`auditme.core.EXTRA_ROOT_NAMES` / `DECLARATION_IGNORED` at `audit.py:175-176`, and `tests/conftest.py:87`) against `extra_roots`, `declared_roots`, `cached_declared_roots`, `cached_roots`; `phaseb.py` `--depth` against `Plan.depth`; `today=None` parameters in `phaseb/ledger.py` and `phaseb/batches.py`; `core.cached_per_run` and its callers. The diff since `7162f02` changes only existence predicates and adds no config field or parameter. Each precedence is stated and enforced.
- Hits: No hits

#### A6 (sampled): Stage method dual-path
- Mode: full
- Inspected: every class and every method that assigns to `self.<attr>` or mutates a `self` container in every tracked `.py` file. No pipeline-stage class. Self-mutating methods: `SiteCounter.next` (`phaseb/architecture.py`, returns an `int`, not a tuple), `IndexEntries.add_module` / `record` (`phaseb/docrefs.py`, return `None`). No class changed since `7162f02`.
- Hits: No hits

#### A7 (sampled): Constructor purity
- Mode: full
- Inspected: every `__init__`, `__post_init__` and `__new__` in every tracked `.py` file (AST listing): `SiteCounter.__init__` (`phaseb/architecture.py:104`, an empty `Counter`) and the test fakes at `tests/test_project_hygiene.py:142,204`, which assign constants and arguments. No `__post_init__` or `__new__`. No I/O, expensive compute or argument mutation.
- Hits: No hits

#### A8 (sampled): Late dataclass mutation
- Mode: full
- Inspected: every `@dataclass` in the tracked `.py` files (all `frozen=True` except `ClassInfo` and `IndexEntries` in `phaseb/docrefs.py:149,217` and `TestIndex` in `phaseb/testmap.py:192`), and every attribute store whose target is not `self`/`cls` and every non-`monkeypatch` `setattr` across every tracked file, tests included (AST scan). Non-self stores: module rebinds at `audit.py:175-176` and `tests/conftest.py:87` (not dataclass instances); `tests/phaseb/test_model.py:48,50`, which assert `FrozenInstanceError`. No other `setattr`. `ClassInfo` and `TestIndex` are built complete; `IndexEntries()` is filled only through its own methods before the frozen `CorpusIndex` is built.
- Hits: No hits

#### A9 (sampled): Pure-named function side effects
- Mode: full
- Inspected: every function and method in the tracked non-test Python files whose name starts with a pure prefix (AST listing, with direct and transitive I/O calls); `checks/auditme/registry.py` `CHECKS` (every `check_*` definition is registered, so none is read as pure-named); bodies of `core.resolve_call`, the `docrefs.resolve_*` family, `testmap.is_test_path`, `testmap.load_test_index` / `load_test_map` (they read the project's test tree and roots config that their argument names, the `load_` carve-out), `batches.parse_result` (`json.loads` on a string, no I/O), `changed.parse_args`, `phaseb.build_parser`.
- Hits: No hits

#### A10 (sampled): Predicate semantics
- Mode: full
- Inspected: every `is_*` / `has_*` / `should_*` function in the non-test files (core, phaseb architecture/candidates/docrefs/testmap, rules duplication/error_handling/style_and_naming), read in full against name and docstring. `architecture.is_constant_operand` accepts only string constants, but its docstring states that, so it is not a hidden conjunct.
- Hits: No hits

#### A12 (sampled): assert misuse
- Mode: full
- Inspected: grep for `assert` statements across every tracked non-test Python file; none exists.
- Hits: No hits

#### A13 (sampled): Same value to multiple structural slots
- Mode: full
- Inspected: AST scan of every call to a capitalised callee in every tracked Python file (tests included) for a non-constant argument passed to 2+ slots. One match, `docrefs.path_target` passing `rel` as both `DocTarget.id` and `DocTarget.path`, is an explicit factory with a docstring, and the field comment says a file's id is its path.
- Hits: No hits

#### A14 (sampled): Repeated computation per request
- Mode: full
- Inspected: project-state helpers and their call sites: `core.cached_roots`/`audit_roots`/`declared_roots`, `cached_corpus_files`, `corpus_index`, `cached_bytes`, `read_and_parse`/`cached_source`, `docrefs.tracked_files` (git ls-files: at most once per lister, and `phaseb.py` runs one question per invocation), `CorpusIndex.build` (once per lister), `candidates.read_pyproject`/`read_hook_file`/`imported_modules`/`agents_document` (once per lister), `changed.run_git` (different arguments per call, negligible next to the sweep). `core.all_py_files` is unchanged since review-11 F5 was dismissed.
- Hits: No hits

#### A15 (sampled): Duplicate constructor / serialisation logic
- Mode: full
- Inspected: every constructor call of a project-defined class in the non-test files, grouped by class with its field set: `Candidate` (built only in the three factories `site_candidate`, `span_candidate` and `section_candidate`), `DocTarget` (`node_target`, `path_target`), `Site` and `Scope` (positional, with values that differ by branch), `SiteCounter`, `Verdict` (`batches.read_run_verdicts` keyword build and `ledger.parse_verdict` from a record; different sources). Serialisation goes through `dataclasses.asdict` everywhere.
- Hits: No hits

#### A16 (sampled): CLI entry envelope
- Mode: full
- Inspected: `git ls-files '*.py'` has no `cli/*.py` file, so the question's enumeration is empty. The top-level `run_*` functions in `checks/phaseb.py` are not under `cli/`.
- Hits: No hits

#### A18 (sampled): Hot-path setup
- Mode: full
- Inspected: every tracked `.py` and `.sh` file searched for `def on_step|on_log|on_evaluate|on_batch_*`; the only definitions are fixture source strings in `claude/skills/auditme/tests/test_state_and_effects.py:821` and `:844` (input to the checker under test, not callbacks this project runs).
- Hits: No hits

#### A20 (sampled): Mutable module-level singleton
- Mode: full
- Inspected: every module-level assignment in every tracked non-test `.py` file whose value is a `dict`/`list`/`set` literal, comprehension or bare-builtin call (AST scan). Swept and accepted: `core.py` `EMITTED`, `UNREADABLE`, `SOURCE_CACHE`, `INDEX_CACHE`; `phaseb/candidates.py` `REGISTRY`, `KINDS`. Remaining mutable containers - `phaseb/candidates.py` `TAKES_DEPTH`; `rules/imports_and_surfaces.py` `STDLIB`; `rules/state_and_effects.py` `DISK_IO_NAMES`, `MUTABLE_VALUE_SHAPES`, `MUTABLE_CONSTRUCTORS`; `rules/style_and_naming.py` `STRFTIME_TOKENS`, `PARAMETRIC_NONBUILTIN_GENERICS`, `TYPING_DEPRECATED_ALIASES`; `changed.py` `RULE_HELP`; `phaseb.py` `COMMANDS`; each module's `__all__` - grepped by word across every tracked `.py` and `.sh` file (covers `from m import N`, `m.N`) and for `sys.modules[...]`: each is read only in its own module (the `COMMANDS` and `module.__all__` text in `tests/test_annotated_all.py` is fixture source).
- Hits: No hits

#### A21 (sampled): Lazy init race
- Mode: full
- Inspected: every `if X is None:` in non-test files, both `global ROOT_MODULES` writers (`core.py` `audit_roots`, `cached_roots`), the `INDEX_CACHE` lazy fills (`core.py`, `rules/project_hygiene.py` `ruff_executable`) and the `functools.cached_property` uses in `phaseb/testmap.py`. No module in scope uses `threading`, `concurrent.futures`, `multiprocessing` or `asyncio` (matches are only rule-name strings in `rules/style_and_naming.py`), so no lazy init runs on a path called concurrently.
- Hits: No hits

#### A22 (sampled): Fall-through after partial handling
- Mode: full
- Inspected: AST scan of every non-test `.py` file for an `if` branch holding an `except` that raises and not ending in return/raise, with statements after it; single candidate `changed.py:196` (`scope_records`): the handler re-raises as `ChangedError`, so nothing after it runs as though the `.py` branch had not been taken. Also read the nested try in `changed.py:main` (lines 320-350).
- Hits: No hits

#### A23 (sampled): Discarded multi-return
- Mode: full
- Inspected: every non-test function annotated to return `tuple[...]` and each of its call sites (AST scan). Unpacked or `_`-named everywhere except index projections: `core.py:175` `read_source` and `:184` `read_and_parse` (`cached_source(...)[0]/[1]`), `core.py:927` `read_is_private` (`privacy(...)[0]`), `phaseb/candidates.py:142` and `:161` (`registered(...)[1]/[2]`), and the bare validation call `phaseb/candidates.py:151`. In each, no dropped component is documented as changing how the kept one is used. Single-name assignments (`dotted_read`, `a11_site`, `agents_document`, `ruff_hook_pin`, `parse_spec_def`, `wrapped_literal`) are unpacked after their None check.
- Hits: No hits

#### A24 (sampled): Identity of subprocess / shell-out calls
- Mode: full
- Inspected: every `subprocess.run` in non-test files. Swept and accepted: `rules/project_hygiene.py:50`, `:104`, `:225`. The rest: `rules/project_hygiene.py:112` (one conditional retry with a different environment, not the same call), `phaseb/docrefs.py:301` `tracked_files` (called at most once per `phaseb.py` invocation, which runs a single question's lister), `changed.py:64` `run_git` (each git command per run has different arguments: `rev-parse --show-toplevel`, one `rev-parse --verify` per base candidate until one resolves, two different `diff`s, `merge-base`), `changed.py:236` (sweep, once). Shell scripts `bin/check-foreign-names.sh`, `bin/install-claude.sh`, `claude/hooks/auditme-stop.sh`: each git call has distinct arguments.
- Hits: No hits

#### A25 (sampled): Shallow immutable wrapper
- Mode: full
- Inspected: every module-level `types.MappingProxyType(...)`, `frozenset(...)` and `tuple(...)` / tuple literal in non-test files (AST scan) and its members: `frozenset` members are string literals; tuple members are strings, nested string tuples (`T2_INVERSES`), `ast` classes or check functions (`registry.py` `CHECKS`, `PROJECT_CHECKS`; `phaseb/architecture.py` `A1_CHECKS`, `A17_CHECKS`, `A19_CHECKS`); `core.py` `ROOT_MODULES` wraps an empty dict at line 311 and a `{Path: str}` comprehension in `audit_roots`. No `dict`/`list`/`set` member, none one tuple deep, no non-frozen project dataclass instance.
- Hits: No hits

#### S1 (sampled): Type annotations on every signature
- Mode: full
- Inspected: every tracked `.py` file (`git ls-files '*.py'`) with `ruff check --isolated --select ANN001,ANN002,ANN003,ANN201,ANN202,ANN204,ANN205,ANN206` (ruff 0.14.0; ANN is not in the project's ruff `select`); shell files have no signatures to annotate. No AGENTS.md note records a test-annotation exemption, so there is no figure to drift-check. Code changed since review-14 (`audit.py:224`, `core.py:269`, `rules/imports_and_surfaces.py:279,408`, `rules/project_hygiene.py:100,199`) touches no signature.
- Hits: non-test source: No hits. Tests (count only): 130 missing parameter annotations, 32 missing return annotations, 7 test modules affected, 27 of 34 test modules fully annotated.

#### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake
- Mode: full
- Inspected: every tracked `.py` file with `ruff check --isolated --select N`, plus a grep of module-level bindings against the Naming section of `claude/rules/auditme/coding-standards.md`; variable and function case in `bin/check-foreign-names.sh`, `bin/install-claude.sh`, `claude/hooks/auditme-stop.sh`. The only ruff reports are N806 on function-local literal constant collections (`MUTATING_METHOD_NAMES`, `SAFE_ATTRS`, `STDLIB_EXCS`, `STDLIB_WRITE_CALLS`, `PURE_PREFIXES`, `MUTATION_METHODS`, `BUILD_SIDE_EFFECTS`, `HOT_IO`, `CACHE_DECORATORS`) in `rules/duplication.py`, `rules/error_handling.py`, `rules/state_and_effects.py`: constants named UPPER_SNAKE as the rule asks, one idiom across the tree (as reviews 9, 12, 13 and 14 judged). PascalCase module-level names (`Check`, `FunctionNode`, `Lister`, `HandlerLevel`) are type aliases. Shell scripts use UPPER_SNAKE for fixed settings in `bin/install-claude.sh` and lower_snake for working variables and functions elsewhere; no change since review-14.
- Hits: No hits

#### S3 (sampled): TYPE_CHECKING block placement
- Mode: full
- Inspected: an AST walk of every tracked `.py` file for `if ... TYPE_CHECKING:`. Every module-level block (`audit.py:92`, `changed.py:38`, `phaseb/batches.py:24`, `phaseb/ledger.py:22`, `phaseb/testmap.py:19`, each `rules/*.py`, `tests/conftest.py:37`, and the test modules `test_docrefs.py:14`, `test_ledger.py:14`, `test_model.py:11`, `test_changed.py:17`, `test_imports_and_surfaces.py:11`) directly follows the last import, with no import after it. The one nested match (`core.py:232`) is the checker testing for the string `TYPE_CHECKING`, not a block. No `from __future__ import annotations` line outside checker patterns and fixture strings.
- Hits: No hits

#### S4 (sampled): Project-specific rule files
- Mode: full
- Inspected: the rule files AGENTS.md points to (`claude/rules/auditme/coding-standards.md`, `imports.md`, `dependencies.md`), checked across the non-test source for what the sweep does not enforce: `as` imports, wildcard imports, stdlib `logging`, `%`/`.format()` formatting, `assert` in product code, argparse versus cappa (argparse allowed: the checker is standard-library only), and `print()` use. Only match is a regex inside the checker (`rules/style_and_naming.py:107`); `print()` is confined to the CLI entry points `audit.py`, `changed.py`, `phaseb.py` and `core.py:60`, which emits the JSON-lines hit stream. The diff since review-14 swaps `exists()` for `is_dir()`/`is_file()` and adds no rule-relevant construct.
- Hits: No hits

#### P1 (sampled): O(n^2) on real-size inputs
- Mode: full
- Inspected: every rule and phaseb module; the code changed since review-14 adds no loop. Measured a full sweep under cProfile on one project with 766 tracked Python files (245.5 s profiled, 2026-11-22): largest checks `check_asymmetric_exception_translation` 9.5% (dismissed in review-6, code unchanged), `check_translator_envelope_gap` 5.7%, `check_redundant_sink_caller_plus_callee` 5.5%, `check_spec_api_signature_drift` 4.7%, `check_in_function_imports` 4.5%, `check_text_patterns` 4.4%, `check_duplicate_call_sequence` 4.2% (dismissed); every one under a tenth.
- Hits: No hits

#### P2 (sampled): Blocking I/O in hot paths
- Mode: full
- Inspected: all tracked `.py` and `.sh` files for reads/writes in loops, handlers and callbacks. The only callback is the Stop hook (`claude/hooks/auditme-stop.sh`, unchanged), which runs `git` once and `changed.py` once per turn end. On the 766-file sweep, file reads go through `core.cached_source` (85,113 calls, 3.3% cumulative; `read_source` 37,972 calls, 0.8%); `subprocess.run` is called 8 times (0.1%).
- Hits: No hits

#### P3 (sampled): Repeated expensive computation per request
- Mode: full
- Inspected: shared derivations on the 766-file sweep: `corpus_index` 7 calls, 5.4% cumulative; `translator_envelopes` 3 calls (once per root), 2.3%; `reads_by_module_and_name` 3 calls, 1.5%; `corpus_definitions` 1 call, 2.8%; `accepted_lazy_imports` 3 calls with 1 scan, under 0.1%; `all_py_files` 214 calls, 1.1% (dismissed in review-11); `walk_within_scope` 4.6%, a generator pruning one AST per call, not a repeated derivation. The `list_a1_candidates` recomputation of `translator_envelopes` (`phaseb/architecture.py`) is unchanged since review-13's measurement.
- Hits: No hits

#### Sec1 (sampled): Secrets in source
- Mode: full
- Inspected: every tracked `.py` and `.sh` file, `pyproject.toml`, `.pre-commit-config.yaml`, `.pre-commit-hooks.yaml`, the setup skill's template `pre-commit-config.yaml` and `.github/workflows/*.yml`, searched for key/secret/password/token/bearer patterns and known key prefixes (`ghp_`, `sk-`, `AKIA`). The only token use is `.github/workflows/docs.yml:46-48`, which takes `secrets.GITHUB_TOKEN` from the Actions secret store at run time, not a literal value.
- Hits: No hits

#### Sec2 (sampled): Input validation at system boundaries
- Mode: full
- Inspected: the argument parsing of `claude/skills/auditme/checks/audit.py`, `changed.py` and `phaseb.py`, plus `bin/check-foreign-names.sh`, `bin/install-claude.sh` and `claude/hooks/auditme-stop.sh`. Each was run in the scratchpad with a missing path, a directory where a file is expected and a file where a directory is expected:
  - `audit.py`: scope, `--extra-root`, `--package` (missing and a file under `src/`), and a `[tool.auditme]` root that is missing or a file.
  - `changed.py`: `repo_root` with and without `--all` and `--scope`.
  - `phaseb.py`: `root` for every subcommand that takes one, `plan --out` (a file, and a missing nested directory), and `check` and `merge` with `dir` missing, a file, or an empty directory.
  - `check-foreign-names.sh`: `AUDITOR_FOREIGN_NAMES` missing or a directory, and file arguments missing or a directory.
  - `auditme-stop.sh`: the installed checker missing or a directory, and a payload that is not JSON.

  Every bad path gave a clear error with a non-zero exit, or a documented skip. `install-claude.sh` takes no path of its own: it passes its arguments through to `uvx install-in-claude`, which was not run because it fetches over the network and writes to `~/.claude`.
- Hits: No hits

#### Sec3 (sampled): Command injection
- Mode: full
- Inspected: every `subprocess` call in `claude/skills/auditme/checks/` (`changed.py`, `auditme/rules/project_hygiene.py`, `auditme/phaseb/docrefs.py`). Each passes a list with no `shell=True`. The shell scripts have no `eval`, `sh -c` or command built from a string; every variable is quoted, `grep` patterns go through `-e`, file arguments follow `--`, and `changed.py` refuses a `--base` that starts with `-`.
- Hits: No hits

#### Sec4 (sampled): Path traversal
- Mode: full
- Inspected: every place a user path is joined to a project path:
  - `audit.py` `--package`: must be a bare name, with `.` and `..` refused.
  - `audit.py` `--extra-root`: `path_inside` containment.
  - declared `[tool.auditme]` roots: `core.py:380` `path_inside`.
  - `docrefs.read_path_targets`: normalised, `..` refused, and only paths in the git file index are read.
  - phaseb run directories: batch and plan files have fixed names under the directory the caller names.
  - `check-foreign-names.sh` and `auditme-stop.sh`: paths come from the environment or git, not from a joined user string.
- Hits: No hits

#### Sec5 (sampled): PII in logs
- Mode: full
- Inspected: every tracked Python and shell file, for `logging` and `loguru` use. The checker has no logger: it writes JSON hits and error messages to stdout and stderr. Every `logger.` and `loguru` match is in a docstring or a test fixture string.
- Hits: No hits

#### T3 (sampled): Integration vs unit balance
- Mode: full
- Inspected: each pipeline orchestrator and its tests:
  - `changed.py` (sweep, then filter): `claude/skills/auditme/tests/test_changed.py:262` `test_end_to_end_against_the_real_checker`.
  - `phaseb.py` (plan, check, merge): `claude/skills/auditme/tests/phaseb/test_cli.py:347` round-trips plan, check and merge for every registered question.
  - `audit.py` (the driver over every root): `claude/skills/auditme/tests/test_driver.py` runs `main` on real project trees.
  - The shell entry points: `tests/test_stop_hook.py`, `tests/test_check_foreign_names.py`, `tests/test_install_claude.py` and `tests/test_published_hooks.py` run them as subprocesses.
- Hits: No hits

#### D1 (sampled): Declared in pyproject
- Mode: full
- Inspected: every import statement in the tracked `.py` files. Third-party imports outside fixture strings are `pytest` and `hypothesis`, and both are in `[dependency-groups] dev`. `loguru`, `requests`, `orjson`, `pkg.*` and `probe.*` appear only inside test fixture source strings (`test_architecture_candidates.py`, `test_error_handling.py`, `test_imports_and_surfaces.py`).
- Hits: No hits

#### D2 (sampled): Unused declarations
- Mode: full
- Inspected: each declared dependency in `pyproject.toml` `[dependency-groups]`, and the evidence that it is used:
  - `hypothesis`: imported in `tests/phaseb/test_cli.py:13`.
  - `pytest`: imported, and run in a `run:` step of `.github/workflows/ci.yml`.
  - `ruff`: the tool behind the `ruff-pre-commit` hooks, and run through `subprocess` in `auditme/rules/project_hygiene.py`.
  - `mkdocs`: run as `uv run mkdocs` in `.github/workflows/docs.yml`.
  - `mkdocs-material`: its installed `entry_points.txt` (9.7.7 and 9.8.0, in the uv cache) registers `[mkdocs.themes] material`, which `mkdocs.yml` names as `theme: name: material`.
- Hits: No hits

#### D3 (sampled): Lockfile coherence
- Mode: full
- Inspected: `/tmp/audit-auditor.jsonl` has no lockfile-drift hit, and `uv lock --check` exits 0 ("Resolved 36 packages").
- Hits: No hits

#### Doc3 (sampled): README.md and AGENTS.md consistent
- Mode: full
- Inspected: `README.md` (all lines), `AGENTS.md` (all lines), checked against `.pre-commit-hooks.yaml` (ids `auditme-changed`, `auditme-all`, `no-project-names`), `bin/install-claude.sh`, `bin/check-foreign-names.sh`, `claude/` layout (`skills/auditme`, `skills/auditme-project-setup`, `rules/auditme`, `hooks/auditme-stop.sh`), `tests/`, and the `docs/` statements on the same subjects (`docs/reference/cli.md` installer section, `docs/index.md`, `docs/concepts.md:55`, `docs/setup.md:163`). Both files give the same test command, the same installer scope (claude/ skills, rules and Stop hook; other shared rules from the agents repository's installer) and the same hook set; AGENTS.md's extra detail (Stop hook registered in `~/.claude/settings.json`, hook-type install command) agrees with `bin/install-claude.sh` and `docs/reference/cli.md`.
- Hits: No hits

#### Spec review
- agents/specs/auditme-false-positives/spec.md - no gap
- agents/specs/listed-phase-b-architecture-questions/spec.md - no gap
- agents/specs/listed-phase-b-documentation-questions/spec.md - no gap
- agents/specs/listed-phase-b-test-questions/spec.md - no gap
- agents/specs/project-setup/spec.md - no gap
- agents/specs/raises-section-resolution/spec.md - no gap
- agents/specs/repeatable-phase-b/spec.md - no gap
- agents/specs/index.md - no gap (every spec directory has an entry; every relative link in the index and specs resolves)

## Prior findings re-verified

Review-14's F1 and F2 shipped in its task list (`tasks-13.md`): `audit.py --package` given a plain file exits 2 with "not a directory" (checked 2026-11-22), and the exit-2 paragraph's examples now print as stated. Earlier dismissals stand. No task list under `agents/tasks/audit-reviews/` has an incomplete task.

## Decisions

None this review.

## Answers

Nothing to answer.
