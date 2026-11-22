# Audit Review 12

**Date:** 2026-11-22
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`); every sampled question ran on the whole tree
**Commit:** add7b4c21ffe7881f583ea2f99f3d9bb5a2f44b5
**Script output:** /tmp/audit-auditor.jsonl (48 hits, 48 accepted, 0 unaccepted)
**Script version:** d6b0e270c63b9be43d655dd953b45153219187eeb735316d28a1ad0abd8f2827
**Convergence note:** the first loop the operator delegated (2026-11-22: whole-tree audits and fixes until no finding, without waiting). Measured on 2026-11-22: 249 listed candidates judged (T1 201, T2 15, Doc4 12, Doc5 10, A4 9, A1 2), one verdict changed with its reason given. Every review-11 fix is confirmed, the A11 lister among them (6.0 s, from 22.0 s, on a 344-file project). Two of the four findings are sites of a pattern a review-11 fix reached at one place only (F3, F4); each task below therefore greps the whole tree for its pattern.
**Review page:** https://claude.ai/artifact/WWF6cfvRFVwuwvJTTmCd2R

## What is being reviewed and how

This is the checker repository's twelfth audit of its own code, a whole-tree pass. The operator delegated the loop on 2026-11-22, so Claude answers this page by taking each recommendation, and records that in the Answers section.

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 48 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 249 judged; every other listed question carried every verdict |
| `phaseb.py check` on every listed question | pass, no retries |
| Every sampled question returned a hit list or "no hits" | pass |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| Prior findings to re-verify | review-11 F1-F4: shipped; `phaseb.py report /nonexistent/xyz` exits 2 (checked 2026-11-22) |

## Summary

The sweep reports 48 hits, all accepted. Phase B leaves 1 listed verdict open (Doc5). The sampled questions flag Sec2 1, A14 2 and A15 1. The spec review finds no gap.

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits.

## Phase B findings (consolidated)

### F1. The CLI reference names only two of `phaseb.py`'s exit-2 causes (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed). **Severity:** low.
- **Location:** `docs/reference/cli.md:174`.
- **Description:** the line names an unregistered `--question` and a missing root; `phaseb.py`'s `main` also exits 2 on every Phase B error (`claude/skills/auditme/checks/phaseb.py:289-292`), such as a merge whose run was planned for another question (`:240`), a ledger or plan that cannot be read, or a failed write. Its earlier verdict, with code and brief unchanged, was not flagged; the reviewer gave its reason: the brief's rule that a list of exit conditions not marked as examples is complete.
- **Recommendation:** add that `phaseb.py` exits 2 with the error's message whenever a Phase B step fails, naming those cases.

### F2. The names hook exits 2 in silence when given a directory (Sec2)

- **Category:** Sec. **Question:** Sec2 (sampled). **Severity:** low.
- **Location:** `bin/check-foreign-names.sh:51-55`.
- **Description:** a directory passes the `[ -r "$file" ]` check, and grep's "Is a directory" error goes to `/dev/null`, so the hook exits 2 with no message. Reproduced on 2026-11-22. `tests/test_check_foreign_names.py` covers a missing file only. Pre-commit passes files, so this is reached only by hand.
- **Recommendation:** treat a path that is not a regular readable file as unreadable, so it is named in the existing message; test it.

### F3. Two project-level answers are worked out once per audit root (A14)

- **Category:** A. **Question:** A14 (sampled). **Severity:** low.
- **Locations:** `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:786` (`project_has_all_guard`, from `check_annotated_all_assignment`) and `:264` (`project_bans_as_imports`, from `check_as_import`).
- **Description:** each depends only on the project, but its check runs once per root: five times per sweep here, each `project_has_all_guard` call repeating a `src/` `rglob` and regex scan.
- **Recommendation:** cache each per run, through the per-run cache the driver clears; grep `checks/auditme/rules/` for every other helper taking only `scope` and called from a per-root check, and treat each the same way.

### F4. A `Candidate` test builder left beside the shared one (A15)

- **Category:** A. **Question:** A15 (sampled). **Severity:** low.
- **Location:** `claude/skills/auditme/tests/phaseb/test_batches.py:13` (`make_batch_candidate`), beside `make_candidate` in `claude/skills/auditme/tests/conftest.py:41`.
- **Description:** both build a `Candidate` with the same seven fields. Review-11's F3 fix merged the `Verdict` builders only.
- **Recommendation:** give `make_candidate` the overrides `make_batch_candidate` needs and use it; grep the tests for every builder of a class `conftest.py` already builds, and merge each.

## Phase B per-question results

Listed questions: the verdicts are in `agents/audit-reviews/ledger/`; `phaseb.py report <root> --question <Q>` prints the open ones. Only Doc5 has one (F1).

#### A2 (sampled): Except tuple coverage
- Mode: full
- Inspected: every `try` statement in every tracked non-test `.py` file at `add7b4c` (AST listing of each `try` body with its handler types), each body read by hand: `audit.py`, `changed.py`, `phaseb.py`, `auditme/core.py`, `auditme/phaseb/{architecture,batches,candidates,docrefs,ledger,testmap}.py`, `auditme/rules/project_hygiene.py`. Every disk body catches `OSError` (or `Exception`) and adds `UnicodeDecodeError` where it decodes (`read_text` at `core.py:154`, `architecture.py:87,743`, `batches.py:148,207`, `candidates.py:194`, `ledger.py:67`, `testmap.py:56`, `changed.py:197`; `cached_bytes(...).decode` at `candidates.py:397`, `docrefs.py:86`; `read_bytes().decode` at `candidates.py:575`), and `json.JSONDecodeError` where it parses a file it reads (`batches.py:148`). Byte-only bodies (`core.py:97,125,144`, `candidates.py:82,411,603`, `docrefs.py:316`) and write bodies (`batches.py:129`, `ledger.py:91,105`) need only `OSError`. `json.loads`/`tomllib.loads` on text already in memory (`ledger.py:76`, `changed.py:255`, `project_hygiene.py:64`, `core.py:345`) catch their parser error and touch no disk; subprocess-only bodies (`changed.py:63,235`, `project_hygiene.py:48,102,222`, `docrefs.py:299`) are not disk bodies; `batches.py:219` catches `ValueError`, the base of `JSONDecodeError`. `architecture.py:44` is a try/finally with no except tuple. No translating decorator or contextmanager `with` envelope in source. The changes since review-11 (`cached_roots` in place of `audit_roots`, `flags_by_scope` in `list_a11_candidates`, `project_root` in `phaseb.py`) add no `try`. Test-file `try` blocks are fakes and fixture text.
- Hits: No hits

#### A3 (sampled): Domain-error layering
- Mode: full
- Inspected: every `raise` in every tracked non-test `.py` file (AST listing of raised types). Raised domain errors: `auditme.core.RootsError` (`core.py:349-387`), `auditme.core.CachedReadError` (`core.py:103`), `auditme.phaseb.errors.PhaseBError` (every `phaseb/` module and `phaseb.py:240,242`), `changed.ChangedError`. Other raises: `SystemExit` at the entry points (`audit.py:246`, `changed.py:366`, `phaseb.py:300`) and `argparse.ArgumentTypeError` in the argparse `type=` callables (`phaseb.py:46` in the new `project_root`, `phaseb.py:58,80,82`), the type argparse requires of them. The `ValueError`s at `auditme/phaseb/batches.py:181,184,187,191,195,198` are the sweep's (`layer-has-domain-error-raises-stdlib`, accepted), not judged here. No `rules/` module raises. Test-file raises are fakes.
- Hits: No hits

#### A5 (sampled): Two sources of truth
- Mode: full
- Inspected: module state rebound by the driver against the parameters and caches that read it: `auditme.core.EXTRA_ROOT_NAMES` / `DECLARATION_IGNORED` (rebound at `audit.py:175-176`, after `clear_source_cache()` at `audit.py:159` and before any root is read) against `extra_roots(scope, names=None)` (docstring at `core.py:423`: `names` defaults to the current value, read at call time), `declared_roots` (`core.py:340`) and the per-run `('audit-roots', scope)` entry `cached_roots` keeps (`core.py:801-814`, built after the rebind; the test fixture `restore_extra_roots` and fresh `tmp_path` scopes keep tests apart); `ROOT_MODULES` rebound together with the roots it describes in `audit_roots` and `cached_roots` (`core.py:811-813`); `phaseb.py` `--depth` against `Plan.depth` (`depth_of` at `phaseb.py:207`, mismatch refused at `phaseb.py:241`) and the listers' `depth=None` defaults; `today=None` parameters in `ledger` and `batches`. Each precedence is stated and enforced. `TestIndex` fields are derived once in `load_test_index`.
- Hits: No hits

#### A6 (sampled): Stage method dual-path
- Mode: full
- Inspected: every class in every tracked `.py` file and each method that assigns to `self.<attr>` or mutates a `self` container (AST listing plus reading). The project has no pipeline-stage class. Self-mutating methods: `SiteCounter.next` (`auditme/phaseb/architecture.py:106`, returns an int, not a tuple) and `IndexEntries.add_module` / `record` (`auditme/phaseb/docrefs.py:224,241`, return `None`); `IndexEntries.class_info` returns a `ClassInfo` and mutates only through `record`, a different field. `TestIndex.importers` / `reverse` (`testmap.py:235,248`) are `functools.cached_property` members that assign no named field. Test classes (`Result`, `LockResult` in `tests/test_project_hygiene.py`) have only `__init__`.
- Hits: No hits

#### A7 (sampled): Constructor purity
- Mode: full
- Inspected: every `__init__` and `__post_init__` in every tracked `.py` file (AST listing): `SiteCounter.__init__` (`auditme/phaseb/architecture.py:103`, an empty `Counter`), and the test fakes `Result.__init__` (`tests/test_project_hygiene.py:142`) and `LockResult.__init__` (`tests/test_project_hygiene.py:204`), which assign constants and arguments. No `__post_init__` anywhere. No I/O, no expensive compute, no argument mutated.
- Hits: No hits

#### A8 (sampled): Late dataclass mutation
- Mode: full
- Inspected: every `@dataclass` in the tracked `.py` files (all `frozen=True` except `ClassInfo` and `IndexEntries` in `auditme/phaseb/docrefs.py` and `TestIndex` in `auditme/phaseb/testmap.py`), and every attribute store whose target is not `self`/`cls`, every `setattr` and every `object.__setattr__` across every tracked file, tests included (AST scan). The only non-self attribute stores are the module rebinds at `audit.py:175-176` and `tests/conftest.py:85` (not dataclass instances) and `tests/phaseb/test_model.py:48,50`, which assert `FrozenInstanceError` (line 50 now builds through the shared `conftest.make_verdict`). `ClassInfo` is built complete at `docrefs.py:265`; `IndexEntries()` at `docrefs.py:186` is filled through its own methods before the frozen `CorpusIndex` is built from it; `TestIndex` is built complete at `testmap.py:356`. Changed copies go through `dataclasses.replace`.
- Hits: No hits

#### A9 (sampled): Pure-named function side effects
- Mode: full
- Inspected: every function and method in every tracked non-test `.py` file whose name (leading underscores stripped) starts with a pure prefix, listed by AST walk with every call in its body. The `check_` carve-out applied against `CHECKS` and `PROJECT_CHECKS` in `claude/skills/auditme/checks/auditme/registry.py`: every `check_` function in the tree is a member, none is unregistered. `load_test_index` / `load_test_map` (`claude/skills/auditme/checks/auditme/phaseb/testmap.py:301`, `:360`) read the package and test tree under the `root` they are given (now through `cached_roots`), which is what a `load_` name says it loads. `build_parser` (`claude/skills/auditme/checks/phaseb.py`) now passes `project_root` as an argparse `type` but does not call it; `project_root` is not pure-prefixed. `parse_args`, `parse_result`, `parse_verdict`, `parse_spec_def` and every `is_`/`resolve_` function make no I/O, subprocess, clock or network call.
- Hits: No hits

#### A10 (sampled): Predicate semantics
- Mode: full
- Inspected: every `is_*`, `has_*` and `should_*` function in the tree, source and test files (AST walk), body read against its name and docstring. No predicate was added or changed since review-11 (`git diff b1d0482 HEAD`); the set is the one review-11 read (`core.py`, `phaseb/architecture.py`, `phaseb/candidates.py`, `phaseb/docrefs.py`, `phaseb/testmap.py`, `rules/duplication.py`, `rules/error_handling.py`, `rules/style_and_naming.py`, and `is_candidate_source` in `tests/phaseb/test_t2_candidates.py`). Each conjunct is part of the question its name asks.
- Hits: No hits

#### A12 (sampled): assert misuse
- Mode: full
- Inspected: AST walk for `ast.Assert` over every tracked `.py` file, keeping those outside test files.
- Hits: No hits (no `assert` outside test files)

#### A13 (sampled): Same value to multiple structural slots
- Mode: full
- Inspected: AST walk over every tracked `.py` file (source and tests) for calls to a capitalised callee passing the same non-constant expression to two or more positional or keyword slots. The one site, `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:281` `DocTarget(kind, rel, rel, 1, last_line)`, sits inside the explicit factory `path_target`, whose docstring and the `DocTarget.id` field comment state the equality, which is the question's own remedy. The new `make_verdict` (`claude/skills/auditme/tests/conftest.py:45`) passes each field once.
- Hits: No hits

#### A14 (sampled): Repeated computation per request
- Mode: full
- Inspected: every call of `auditme.core.audit_roots`, `cached_roots`, `declared_roots` / `cached_declared_roots`, `phaseb.docrefs.tracked_files`, `candidates.read_pyproject`, `imports_and_surfaces.project_bans_as_imports` and `project_has_all_guard`. Review-11 F2 is fixed: every `phaseb/` site now goes through `cached_roots` (the only direct `audit_roots` calls left are inside `cached_roots` and the driver, `checks/audit.py:189`). Then one sweep of this repository (`audit.py /Users/simonb/src/auditor`, run 2026-11-22) with call counters on the two `project_*` gates. The sweep's `subprocess-without-memoisation` hits in `rules/project_hygiene.py` are the sweep's and not repeated here.
- Hits:
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:786` - `project_has_all_guard(scope)`, a property of the project (does any file under `src/` read `__all__` as data), is called by `check_annotated_all_assignment` (`:826`) once per audit root: 5 calls in one sweep of this repository (5 declared roots), each repeating the `src/` `rglob` and regex scan; not cached, unlike `cached_roots` / `cached_declared_roots`
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:264` - `project_bans_as_imports(scope)`, a property of the project (does `AGENTS.md` declare the `as`-import ban), is called by `check_as_import` (`:301`) once per audit root: 5 calls in one sweep of this repository, each an `exists()` and regex over `AGENTS.md` (text is cached by `read_source`, so the cost is small); not cached

#### A15 (sampled): Duplicate constructor / serialisation logic
- Mode: full
- Inspected: every class defined in the checker, with every constructor call site in source and test files grouped by class and compared by field set (`Candidate`, `Verdict`, `DocTarget`, `Site`, `Scope`, `CallSite`, `Plan`), plus serialisation sites. Review-11 F3 is fixed: `Verdict` test construction is now the one `make_verdict` in `claude/skills/auditme/tests/conftest.py:45`. In source, `Candidate`'s three sites are the per-shape factories in `phaseb/candidates.py:253-265`; `DocTarget`'s two are the factories `node_target` and `path_target`; `Verdict` is built from fresh fields once (`phaseb/batches.py:282`) and decoded once (`phaseb/ledger.py:54`).
- Hits:
  - `claude/skills/auditme/tests/phaseb/test_batches.py:13` - `make_batch_candidate` assembles `Candidate` with the same seven fields and the same `question`, `path`, `start` and `end` values as `make_candidate` in `claude/skills/auditme/tests/conftest.py:41`; the rest of the review-11 F3 pattern, left when Task 3 merged the `Verdict` builders: a field added to `Candidate` needs two test edits

#### A16 (sampled): CLI entry envelope
- Mode: full
- Inspected: `git ls-files '*.py'` for any `cli/*.py` (none in the tree), and every top-level `run_*` function (`checks/audit.py:117` `run_check`, plus test helpers). The question covers only `run_*` functions in `cli/*.py`; no file matches.
- Hits: No hits (no `cli/*.py` module)

#### A18 (sampled): Hot-path setup
- Mode: full
- Inspected: every tracked `.py` and `.sh` file, grepped for `def on_step|on_log|on_evaluate|on_batch_*`. The only callback methods are fixture classes inside test strings (`claude/skills/auditme/tests/test_state_and_effects.py:821`, `:844`) that exercise the sweep's own rule; no production callback exists.
- Hits: No hits

#### A20 (sampled): Mutable module-level singleton
- Mode: full
- Inspected: an AST pass over every tracked `.py` file listing each module-level `dict`/`list`/`set` literal, comprehension or bare-constructor call, and each `frozenset`/`tuple`/`MappingProxyType` value; for each, a search of every tracked file (`claude/`, `tests/`, `bin/`, test trees included) for `from <module> import <name>`, `<module>.<name>` and `sys.modules['<module>'].<name>`. Mutable containers read elsewhere: `core.py` `EMITTED`, `UNREADABLE`, `INDEX_CACHE` and `candidates.py` `REGISTRY`, `KINDS` - all sweep hits (`mutable-module-level-exported`, accepted). `__all__` matches were fixture strings and comments, not reads. `TAKES_DEPTH`, `COMMANDS` (`checks/phaseb.py`), `RULE_HELP` (`checks/changed.py`), `STDLIB`, `DISK_IO_NAMES`, `MUTABLE_VALUE_SHAPES`, `MUTABLE_CONSTRUCTORS`, `STRFTIME_TOKENS`, `PARAMETRIC_NONBUILTIN_GENERICS`, `TYPING_DEPRECATED_ALIASES` are read only in their own module.
- Hits: No hits

#### A21 (sampled): Lazy init race
- Mode: full
- Inspected: every `if X is None:` and `global` statement in non-test `.py` files; the module-level helpers that rebind or fill module state (`core.py` `audit_roots` and `cached_roots` rebinding `ROOT_MODULES`, `INDEX_CACHE` fills, `SOURCE_CACHE`). Searched the tree for `threading`, `concurrent`, `multiprocessing`, `asyncio`, pools: none is used outside rule tables of names, so no code path is called concurrently.
- Hits: No hits

#### A22 (sampled): Fall-through after partial handling
- Mode: full
- Inspected: an AST pass over every non-test `.py` file for `if` branches holding a `try` whose handler raises, checking for a path that falls through to an alternative branch; plus `changed.py` `read_base_ref` (loop of return/raise branches). The one match, `checks/changed.py:196` (`scope_records`), raises `ChangedError` from its handler, so nothing re-runs as the other branch.
- Hits: No hits

#### A23 (sampled): Discarded multi-return
- Mode: full
- Inspected: every function annotated to return a fixed `tuple[...]`, and every non-test call site of one (bare statement, subscript, unpacking). Unpackings name every component (`roots, _ = cached_roots(...)`, `found, _ = read_batch_check(...)`, `ruff, _ = ruff_executable(...)`). Subscripts: `cached_source(path)[0]`/`[1]` (`core.py:175`, `:184`), `privacy(...)[0]` (`core.py:911`), `registered(question)[1]`/`[2]` (`candidates.py:142`, `:161`), `cached_roots(scope)[0]` (`architecture.py:85`, `:622`, `candidates.py:382`). The dropped root modes are not lost: `cached_roots` rebinds `core.ROOT_MODULES`, which `module_dotted` and `all_py_files` read, and its docstring documents no component as changing how the roots are used. The bare `registered(question)` at `candidates.py:151` is called for its raise on an unknown question; its tuple carries no state the caller depends on.
- Hits: No hits

#### A24 (sampled): Identity of subprocess / shell-out calls
- Mode: full
- Inspected: every `subprocess.*` call in non-test `.py` files and every command substitution in `bin/check-foreign-names.sh`, `bin/install-claude.sh`, `claude/hooks/auditme-stop.sh`. `project_hygiene.py:50`, `:104`, `:225` are sweep hits (`subprocess-without-memoisation`, accepted); `:112` is the retry of `:104` with a changed environment. `docrefs.py:301` `tracked_files` runs once per `CorpusIndex.build`, which each Phase B request (one question) calls once, and `candidates.py:640` is the Doc2 lister's single call. `changed.py` `run_git` calls each take different arguments (one `rev-parse` per base candidate, two distinct diffs, merge-base, diff -U0); `sweep` runs once. The Stop hook's `git rev-parse` calls each ask a different repository or question.
- Hits: No hits

#### A25 (sampled): Shallow immutable wrapper
- Mode: full
- Inspected: every module-level `frozenset`/`tuple`/`MappingProxyType` value read from another module: `core.py` `BARE_GENERIC_NAMES`, `EXTRA_ROOT_NAMES`, `ROOT_MODULES` (both bindings, `Path -> str`), `SIDE_EFFECT_CALL_NAMES`; `candidates.py` `T2_ENUM_BASES`; `registry.py` `CHECKS`, `PROJECT_CHECKS` (function objects); `project_hygiene.py` `SPEC_SKIP_PARTS`. Every member is a `str`, `Path` or function.
- Hits: No hits

#### S1 (sampled): Type annotations on every signature
- Mode: full
- Inspected: every tracked `.py` file (`git ls-files '*.py'` at `add7b4c`). Non-test source: `ruff check --isolated --select ANN` (ruff 0.17.4) passes, so every parameter and return is annotated. Files under a `tests/` directory: every `def`/`async def` at any depth parsed with `ast` (positional-only, positional, keyword-only, `*args`, `**kwargs`; a leading `self`/`cls` exempt), cross-checked against `ruff --select ANN` (its two extra hits in `test_imports_and_surfaces.py:823` are ANN401 on parameters annotated `typing.Any`, not missing annotations). Shell files have no signatures to annotate.
- Hits: No hits in non-test source. Test-file count (files under a `tests/` directory, measured 2026-11-22 at `add7b4c`): 129 missing parameter annotations, 32 missing return annotations, 7 modules affected, 27 modules fully annotated.

#### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake
- Mode: full
- Inspected: every tracked `.py` file with `ruff check --isolated --select N` plus a scan of module-level `class`/`def` names, against the Naming section of `claude/rules/auditme/coding-standards.md` (snake_case functions/variables, PascalCase classes, UPPER_SNAKE constants); and the variable names of `bin/check-foreign-names.sh`, `bin/install-claude.sh`, `claude/hooks/auditme-stop.sh`. The only ruff reports are N806 on function-local constant sets (`MUTATING_METHOD_NAMES`, `SAFE_ATTRS`, `STDLIB_EXCS`, `PURE_PREFIXES`, `HOT_IO`, ...) in `rules/duplication.py`, `rules/error_handling.py`, `rules/state_and_effects.py`: constants named UPPER_SNAKE as the rule asks, and no function-local constant in the tree is lower_snake, so one idiom, not a mix. `def {name}(...)` matches are fixture templates. Shell scripts use UPPER_SNAKE for constants (`REPO`, `STOP_HOOK`, `INSTALL_IN_CLAUDE_REV`) and lower_snake for variables throughout.
- Hits: No hits

#### S3 (sampled): TYPE_CHECKING block placement
- Mode: full
- Inspected: every `if typing.TYPE_CHECKING:` in tracked `.py` files. Each real block is module-level, directly after the last import, holding only imports: `audit.py:92`, `changed.py:38`, `phaseb/batches.py:24`, `phaseb/ledger.py:22`, `phaseb/testmap.py:19`, `rules/duplication.py:10`, `rules/error_handling.py:11`, `rules/imports_and_surfaces.py:11`, `rules/style_and_naming.py:10`, `rules/state_and_effects.py:10`, and test modules `conftest.py:37`, `test_docrefs.py:14`, `test_ledger.py:14`, `test_model.py:11`, `test_changed.py:17`, `test_imports_and_surfaces.py:11`. In `changed.py` and `conftest.py` the block follows the `sys.path` set-up and its `noqa: E402` imports, still after the last import. The other matches (`test_t1_candidates.py:120`, `test_imports_and_surfaces.py:163,747`, `core.py:227-232`, `candidates.py:757`) are fixture strings, docstrings or detection code.
- Hits: No hits

#### S4 (sampled): Project-specific rule files
- Mode: full
- Inspected: the rules AGENTS.md references: no-project-names (enforced by the `no-project-names` hook, `bin/check-foreign-names.sh`) and the installed `claude/rules/auditme/coding-standards.md`, `imports.md`, `dependencies.md`. Checked every tracked `.py` file for the parts neither the sweep nor ruff's configured rules check: `as` imports (only fixture strings in `test_imports_and_surfaces.py`), `from __future__` (fixtures only), stdlib `logging` (none), `%`/`.format()` (only the sweep's own pattern data), `typing.Optional`/`Union`/`List` (none; one comment), wildcard imports (fixtures and pattern data), `print` (the stdlib-only checker CLIs' stdout records and stderr errors and `core.emit`; stdlib-only with no loguru is allowed for the checker, as review-1 recorded). Shell scripts: the rule files apply to `**/*.py` only.
- Hits: No hits

#### P1 (sampled): O(n^2) on real-size inputs
- Mode: full
- Inspected: every tracked `.py` and `.sh` file; on 2026-11-22 at `add7b4c` profiled the sweep (`audit.py` under cProfile) and timed every registered lister (`phaseb.py candidates --question` A1, A11, A17, A19, A4, Doc1, Doc2, Doc4, Doc5, T1, T2) on two real projects of 344 and 766 tracked Python files. Profiled sweep: 143 s and 205 s (1.4x for 2.2x the files); no check's time more than about 2.7x, the largest growth being `check_spec_api_signature_drift` (3.7 s to 10.0 s, 5% of the profiled sweep; it scales with spec files, not code). Listers: 1.9-6.9 s and 3.0-10.9 s, none above 2.3x. The A11 per-statement re-walk review-11 reported is fixed (`flags_by_scope` in `architecture.py:291`): A11 on the 344-file project took 6.0 s (review-11: 22.0 s), same 164 candidates. `hit_on_anchor` (`architecture.py:131`) scans the hit set linearly, but only for statements that already form a site and over a hit set restricted to each lister's few checks. The dismissed `check_duplicate_call_sequence` and `check_asymmetric_exception_translation` have no diff since review-11 (`rules/` unchanged since `b1d0482`).
- Hits: No hits

#### P2 (sampled): Blocking I/O in hot paths
- Mode: full
- Inspected: every tracked `.py` and `.sh` file for reads and writes inside training loops, request handlers or callbacks. The tree has none: the checks, listers and CLIs are batch tools run once per command, reading each file once through `core.cached_source`; the Stop hook (`claude/hooks/auditme-stop.sh`) runs `changed.py` once per turn end, which is its job; `bin/check-foreign-names.sh` reads its name list once and runs one `grep` over all files.
- Hits: No hits

#### P3 (sampled): Repeated expensive computation per request
- Mode: full
- Inspected: every tracked `.py` and `.sh` file, with the cProfile runs from P1. Per-file source and trees are cached (`core.cached_source`: 85,333 calls, 47,141 parses on the 766-file project, the parses being the per-root passes of distinct files), corpus-wide indexes are built once per run (`core.corpus_index`: 7-10 calls per sweep), and the listers now resolve audit roots once through `core.cached_roots` (replacing per-call `audit_roots` in `architecture.py`, `candidates.py`, `testmap.py` since review-11). `auditme.core.all_py_files` is unchanged since its review-11 dismissal (`core.py` has no diff since `b1d0482`).
- Hits: No hits

#### Sec1 (sampled): Secrets in source
- Mode: full
- Inspected: every tracked `.py` and `.sh` file, `pyproject.toml`, `.pre-commit-config.yaml`, `.pre-commit-hooks.yaml`, `.github/workflows/ci.yml` and `docs.yml`, searched for key, password, token, secret, private-key and known token-prefix patterns. The only token is `GITHUB_TOKEN` in `.github/workflows/docs.yml:46`, taken from `secrets.GITHUB_TOKEN` at run time; `bin/check-foreign-names.sh` reads its list path from `AUDITOR_FOREIGN_NAMES` and holds no value.
- Hits: No hits

#### Sec2 (sampled): Input validation at system boundaries
- Mode: full
- Inspected: the argparse parsers and checks of `claude/skills/auditme/checks/audit.py`, `changed.py`, `phaseb.py`; `bin/check-foreign-names.sh`, `bin/install-claude.sh` (no path argument; passes extra arguments through to `install-in-claude`), `claude/hooks/auditme-stop.sh` (stdin payload through `jq`). Probed with missing and wrong paths: `audit.py` with no scope, `/nonexistent`, a file, `--package nopkg`, `--extra-root nodir`, `--extra-root ../..` (each exit 2 with a message), an empty directory (project-level checks only, said on stderr); `changed.py /nonexistent`, a file, a non-git directory, `--base nosuchref`, `--scope /nonexistent` (each exit 1 naming the cause); `phaseb.py` every subcommand with root `/nonexistent` and a file (argparse refuses, exit 2), `--question ZZ`, `--depth 0`, `plan --batch-size 0`, `plan --out` under a file and under a missing directory, `check`/`merge` with a missing or file run dir, `dismiss` with an unknown id (each exit 2 with a message); `check-foreign-names.sh` with a missing file (exit 2, names it), a missing list (exit 0, "no list", documented and tested), and a directory as the file argument; the Stop hook with `{}` outside a repository (exit 0).
- Hits:
  - `bin/check-foreign-names.sh:51` - a directory passed as a file argument passes the `[ -r "$file" ]` readability check, and grep's "Is a directory" error is discarded by `2>/dev/null` at line 55, so the script exits 2 with no message at all (reproduced: `AUDITOR_FOREIGN_NAMES=<list> bin/check-foreign-names.sh <dir>` prints nothing, exit 2); `tests/test_check_foreign_names.py` covers only a missing file

#### Sec3 (sampled): Command injection
- Mode: full
- Inspected: every `subprocess` call in the checker (`changed.py:64` `run_git`, `changed.py:236` `sweep`, `auditme/phaseb/docrefs.py:301`, `auditme/rules/project_hygiene.py:50,104,112,225`): each passes an argument list, no `shell=True`, and `changed.py` refuses a `--base` starting with `-` and passes `--end-of-options` before refs; no `os.system`, `eval` or `exec` (only `ast.parse(mode='eval')`). Shell scripts: `bin/check-foreign-names.sh` quotes every expansion and uses `grep -F -e ... --`; `bin/install-claude.sh` passes `"$@"` quoted to `uvx`; `claude/hooks/auditme-stop.sh` quotes every expansion, reads the payload through `jq`, and runs only the installed checker or the same repository's own (trusted by shared git directory). `.github/workflows/*.yml` `run:` steps interpolate no event-controlled fields.
- Hits: No hits

#### Sec4 (sampled): Path traversal
- Mode: full
- Inspected: `audit.py` `--package` (refused unless a bare name, not `.`/`..`) and `--extra-root` (refused outside the scope, reproduced with `../..`); `phaseb.py` `ledger_path` (question checked against the registry before joining); `auditme/phaseb/batches.py` plan and result files (fixed names under the run dir); `auditme/phaseb/docrefs.py:323` `read_path_targets` (document tokens normalised, `..` skipped, matched only against tracked files); `changed.py:198` (paths from `git diff` output under the repository root).
- Hits: No hits

#### Sec5 (sampled): PII in logs
- Mode: full
- Inspected: every tracked `.py` and `.sh` file: no `logging` or `loguru` use outside fixture strings; output is checker hits (paths, lines, code evidence), CLI error messages and the Stop hook's block reason, none carrying user free-form text.
- Hits: No hits

#### T3 (sampled): Integration vs unit balance
- Mode: full
- Inspected: the orchestrators and their end-to-end tests: `checks/audit.py` (`tests/test_driver.py` runs the driver over fixture trees, including as a subprocess), `checks/changed.py` (`tests/test_changed.py` end-to-end against the real checker), `checks/phaseb.py` (`tests/phaseb/test_cli.py` runs candidates, plan, check, merge, report and dismiss), `claude/hooks/auditme-stop.sh` (`tests/test_stop_hook.py`), `bin/install-claude.sh` (`tests/test_install_claude.py`), `bin/check-foreign-names.sh` (`tests/test_check_foreign_names.py`), `.pre-commit-hooks.yaml` (`tests/test_published_hooks.py`).
- Hits: No hits

#### D1 (sampled): Declared in pyproject
- Mode: full
- Inspected: every import in tracked `.py` files outside fixture strings: stdlib, the project's own `auditme`, `audit`, `changed`, `phaseb`, `conftest`, and third-party `pytest` and `hypothesis`, both in `[dependency-groups] dev`. `loguru`, `requests`, `orjson`, `pkg`, `probe` appear only inside fixture strings.
- Hits: No hits

#### D2 (sampled): Unused declarations
- Mode: full
- Inspected: `pyproject.toml` `[dependency-groups]`: `hypothesis`, `pytest` (imported in tests); `ruff` (provided by the `ruff-pre-commit` repo in `.pre-commit-config.yaml`, and run via `subprocess` in `auditme/rules/project_hygiene.py`); `mkdocs` (run in `.github/workflows/docs.yml` `run:` steps); `mkdocs-material` (theme `name: material` in `mkdocs.yml`, the entry point it registers). No `[project] dependencies`.
- Hits: No hits

#### D3 (sampled): Lockfile coherence
- Mode: full
- Inspected: `/tmp/audit-auditor.jsonl` for a `lockfile-drift` hit (none; the only lock mentions are accepted literal and memoisation hits); `uv lock --check` resolves cleanly.
- Hits: No hits

#### Doc3 (sampled): README.md and AGENTS.md consistent
- Mode: full
- Inspected: `README.md` (whole), `AGENTS.md` (whole), at `main` `add7b4c`, clean tree (17:10 UTC); cross-checked their claims against `.pre-commit-hooks.yaml`, `.pre-commit-config.yaml`, `bin/install-claude.sh`, the `bin/` and `claude/` layout, and the overlapping statements in `docs/index.md` (repository description, installer, path table) and `docs/reference/cli.md` (hook table, `no-project-names` hook types). Both files give the same test command, the same component list (checker, pre-commit hooks, Stop hook, `/auditme-project-setup` skill), the same installer behaviour (README omits the Stop hook registration that AGENTS.md and the installer state, an omission, not a contradiction), and the same `no-project-names` stages (`pre-commit`, `commit-msg`).
- Hits: No hits

#### Spec review
- agents/specs/auditme-false-positives/spec.md - no gap (Settings omitted; the template allows that when the component has no settings)
- agents/specs/listed-phase-b-architecture-questions/spec.md - no gap
- agents/specs/listed-phase-b-documentation-questions/spec.md - no gap
- agents/specs/listed-phase-b-test-questions/spec.md - no gap
- agents/specs/project-setup/spec.md - no gap
- agents/specs/raises-section-resolution/spec.md - no gap
- agents/specs/repeatable-phase-b/spec.md - no gap
- agents/specs/index.md - no gap (every spec listed; every link resolves)

## Prior findings re-verified

Review-11's F1-F4 shipped in its task list (`tasks-10.md`): `phaseb.py` refuses a missing root with exit 2; no `audit_roots(` call is left under `phaseb/`; the `Verdict` builders are one `make_verdict` in `conftest.py`; the A11 lister computes `flag_subjects` once per function. F5 stays dismissed. No task list under `agents/tasks/audit-reviews/` has an incomplete task.

## Decisions

None this review.

## Answers

Decided by Claude on 2026-11-22: the operator delegated the loop that day ("keep doing whole-tree audits and fixes in a loop until there are no findings and do not stop waiting for me"), so every item takes its recommendation.

| Item | Answer |
|---|---|
| F1-F4 | Fix |
