# Audit Review 11

**Date:** 2026-11-22
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`); every sampled question ran on the whole tree, at the operator's request (the cadence would have run it on changed lines, with review-12 the next whole-tree audit)
**Commit:** 8181700f3c39b58cacafa80bc175dac49d53e338
**Script output:** /tmp/audit-auditor.jsonl (48 hits, 48 accepted, 0 unaccepted)
**Script version:** 1bb90d0b792eb64d904d311e8e5b2ca4e8c3b4088081ef14384e5bd4ef22a28d
**Convergence note:** the listed questions stay at zero: 3 candidates judged (Doc4 1, Doc5 2), none flagged, none changed. Every finding is from the whole-tree sampled questions, in code no change has touched since before review-9, so each is coverage, not a regression. Three are what a whole-tree reviewer reads differently from the last one (Sec2, A15, P1); one is the rest of a pattern review-6 fixed at one site (A14).
**Review page:** https://claude.ai/artifact/CqGK5DakXTgPwpGpJbP5pJ

## What is being reviewed and how

This is the checker repository's eleventh audit of its own code, run on the whole tree because the operator asked. The sweep, every listed question and the spec review are clean. For each finding, choose Fix (it becomes a task) or Dismiss (with your reason). The recommendations follow one rule for performance findings, the one review-6 used: fix a cost that is a large share of its run on a real-size project, dismiss one under about a tenth.

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 48 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 3 judged (Doc4 1, Doc5 2); every other listed question carried every verdict |
| `phaseb.py check` on every listed question | pass, no retries |
| Every sampled question returned a hit list or "no hits" | pass |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| Prior findings to re-verify | none open; review-10 raised none |

## Summary

The sweep reports 48 hits, all accepted. Phase B leaves no listed verdict open. The sampled questions flag Sec2 1, A14 2, A15 1, P1 1 and P3 1. The spec review finds no gap.

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits.

## Phase B findings (consolidated)

### F1. `phaseb.py` accepts a root that does not exist (Sec2)

- **Category:** Sec. **Question:** Sec2 (sampled). **Severity:** medium.
- **Location:** `claude/skills/auditme/checks/phaseb.py:96`, and the same in `plan` (`:107`), `merge` (`:145`), `report` (`:161`) and `dismiss` (`:172`).
- **Description:** no subcommand checks that its root is an existing directory. Checked on 2026-11-22: `phaseb.py candidates /nonexistent/xyz --question A1` exits 0 and prints nothing, and `report` exits 0 with "0 open findings", so a mistyped path reads as a clean result. `audit.py` refuses the same path with exit 2.
- **Recommendation:** check the root once, where the subcommands parse it, and exit 2 with a message naming the path, as `audit.py` does; test each subcommand; add the case to `docs/reference/cli.md`'s exit table.

### F2. The audit roots are worked out again in one listing (A14)

- **Category:** A. **Question:** A14 (sampled). **Severity:** low.
- **Locations:** direct `auditme.core.audit_roots(scope)` calls, each scanning `src/` and the extra roots again:
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py:85` (`read_audited_files`), `:619` (`list_a1_candidates`), `:772` (`list_a17_candidates`): three times in one A1 or A17 listing, with `capture_hits` (`:50`) the only call already using `cached_roots`;
  - the same call at `phaseb/candidates.py:382`, `:611` and `phaseb/testmap.py:312`, found by grep on 2026-11-22.
- **Description:** review-6's F9 moved `capture_hits` to `auditme.core.cached_roots` and left the other sites.
- **Recommendation:** route every `audit_roots` call under `phaseb/` through `cached_roots`, so a later whole-tree pass does not reopen the pattern.

### F3. One test builder copied into three files (A15)

- **Category:** A. **Question:** A15 (sampled). **Severity:** low.
- **Locations:** `make_ledger_verdict` (`claude/skills/auditme/tests/phaseb/test_ledger.py:18`), `make_model_verdict` (`test_model.py:19`), `make_batch_verdict` (`test_batches.py:18`).
- **Description:** each builds a `Verdict` with the same fields and defaults; a field added to `Verdict` needs three edits.
- **Recommendation:** one `make_verdict` in `claude/skills/auditme/tests/conftest.py`, beside `make_candidate`, used by all three.

### F4. The A11 lister walks a function once per statement in it (P1)

- **Category:** P. **Question:** P1 (sampled). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/phaseb/architecture.py:297`, `list_a11_candidates` calling `flag_subjects(function)` for every statement.
- **Description:** each call walks the whole function, so the cost grows with the square of its length. Measured on 2026-11-22: on one project of 340 files the A11 listing took 22.0 s, 6.6 s with `flag_subjects` computed once per function (same 164 candidates); on one of 760 files, 15.6 s and 7.6 s.
- **Recommendation:** compute `flag_subjects` once per function.

### F5. `all_py_files` lists its root again on every call (P3)

- **Category:** P. **Question:** P3 (sampled). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/core.py:245`, called from 76 sites.
- **Description:** one sweep lists each root's files about 70 times, though `cached_corpus_files` lists the corpus once per run. Measured on 2026-11-22 on one project of 760 files: 3.5 s of a 70 s sweep.
- **Recommendation:** dismiss: about a twentieth of the sweep, under the rule this review states; record it so the next whole-tree reviewer is told.

## Phase B per-question results

Listed questions: the verdicts are in `agents/audit-reviews/ledger/`; `phaseb.py report <root> --question <Q>` prints the open ones. No listed question has any, and no verdict changed.

#### A2 (sampled): Except tuple coverage
- Mode: full
- Inspected: every `try` statement in every tracked non-test `.py` file at `8181700` (AST listing of each `try` body with its handler types), each body read by hand: `audit.py`, `changed.py`, `phaseb.py`, `auditme/core.py`, `auditme/phaseb/{architecture,batches,candidates,docrefs,ledger,testmap}.py`, `auditme/rules/project_hygiene.py`. Every disk body catches `OSError` (or `Exception`), adds `UnicodeDecodeError` where it decodes (`read_text` at `core.py:154`, `architecture.py:87`, `batches.py:148,207`, `candidates.py:194`, `ledger.py:67`, `testmap.py:56`, `changed.py:197`; `cached_bytes(...).decode` at `candidates.py:397`, `docrefs.py:86`; `read_bytes().decode` at `candidates.py:575`), and `json.JSONDecodeError` where it parses a file (`batches.py:148`). Byte-only bodies (`core.py:97,125,144`, `candidates.py:82,411,603`, `docrefs.py:316`) and write bodies (`batches.py:129`, `ledger.py:91,105`) need only `OSError`. `json.loads`/`tomllib.loads` on text already read or on subprocess output (`ledger.py:76`, `changed.py:255`, `project_hygiene.py:64`, `core.py:345`) do not touch disk; subprocess-only bodies (`changed.py:63,235`, `project_hygiene.py:48,102,222`, `docrefs.py:299`) are not disk bodies; `batches.py:219` catches `ValueError`, the base of `JSONDecodeError`. `architecture.py:44` is a try/finally with no except tuple. No translating decorator or contextmanager `with` envelope in source. The only change since review-9 (`testmap.py`, the `TestIndex.importers` property) adds no `try`. Test-file `try` blocks are fakes and fixture text.
- Hits: No hits

#### A3 (sampled): Domain-error layering
- Mode: full
- Inspected: every `raise` in every tracked non-test `.py` file (AST listing of raised types). Raised domain errors: `auditme.core.RootsError`, `auditme.core.CachedReadError` (`core.py:103`), `auditme.phaseb.errors.PhaseBError`, `changed.ChangedError`. Other raises: `SystemExit` at the entry points (`audit.py:246`, `changed.py:366`, `phaseb.py:287`) and `argparse.ArgumentTypeError` in the argparse `type=` callables (`phaseb.py:45,67,69`). The `ValueError`s at `auditme/phaseb/batches.py:181,184,187,191,195,198` are the sweep's (`layer-has-domain-error-raises-stdlib`, accepted), not judged here. No `rules/` module raises. Test-file raises are fakes.
- Hits: No hits

#### A5 (sampled): Two sources of truth
- Mode: full
- Inspected: module state rebound by the driver against the parameters that read it: `auditme.core.EXTRA_ROOT_NAMES` / `DECLARATION_IGNORED` (rebound at `audit.py:175-176` before any root is read) against `extra_roots(scope, names=None)` (docstring at `core.py:423`: `names` defaults to the current `EXTRA_ROOT_NAMES`, read at call time) and `declared_roots` (`core.py:340`); `ROOT_MODULES` rebound together with the roots it describes in `audit_roots` and `cached_roots` (`core.py:465-467`, `813`); `phaseb.py` `--depth` against `Plan.depth` and the listers' `depth=None` defaults; `today=None` parameters in `ledger` and `batches`. Each precedence is stated and enforced. The new `TestIndex.importers` (`testmap.py:235`) is derived from `self.tests` only and has no competing source.
- Hits: No hits

#### A6 (sampled): Stage method dual-path
- Mode: full
- Inspected: every class in every tracked `.py` file and each method that assigns to `self.<attr>` (AST listing). The project has no pipeline-stage class. Self-mutating methods: `SiteCounter.next` (`auditme/phaseb/architecture.py:106`, returns an int, not a tuple) and `IndexEntries.record` (`auditme/phaseb/docrefs.py:241`, returns `None`). `TestIndex.importers` (`testmap.py:235`) is a `functools.cached_property` that returns a tuple and assigns no named field.
- Hits: No hits

#### A7 (sampled): Constructor purity
- Mode: full
- Inspected: every `__init__` in every tracked `.py` file (AST listing): `SiteCounter.__init__` (`auditme/phaseb/architecture.py:103`, an empty `Counter`), and the test fakes `Result.__init__` (`tests/test_project_hygiene.py:142`) and `LockResult.__init__` (`tests/test_project_hygiene.py:204`), which assign constants and arguments. No `__post_init__` in source. No I/O, no expensive compute, no argument mutated.
- Hits: No hits

#### A8 (sampled): Late dataclass mutation
- Mode: full
- Inspected: every `@dataclass` in the tracked `.py` files (all `frozen=True` except `ClassInfo` and `IndexEntries` in `auditme/phaseb/docrefs.py` and `TestIndex` in `auditme/phaseb/testmap.py`), and every attribute assignment whose target is not `self`/`cls`, `setattr` or `object.__setattr__` across every tracked file, tests included (AST scan). The only non-self attribute assignments are the module rebinds at `audit.py:175-176` and `tests/conftest.py:71` (not dataclass instances) and `tests/phaseb/test_model.py:60,62`, which assert `FrozenInstanceError`. `ClassInfo` is built complete at `docrefs.py:265`; `IndexEntries()` at `docrefs.py:186` is filled through its own methods before the frozen `CorpusIndex` is built from it; `TestIndex` is built complete at `testmap.py:356`. Changed copies go through `dataclasses.replace`.
- Hits: No hits

#### A9 (sampled): Pure-named function side effects
- Mode: full
- Inspected: every function and method in every tracked non-test `.py` file whose name (leading underscores stripped) starts with a pure prefix, listed by AST walk with every call in its body; the `check_` carve-out applied against `CHECKS` and `PROJECT_CHECKS` in `claude/skills/auditme/checks/auditme/registry.py` (every `check_` function in the tree is a member, none is unregistered). Pure-prefixed helpers in test files also read (`is_candidate_source`, `parse_call`, `parse_modules`, `parse_or_none`: AST parsing only). `load_test_index` / `load_test_map` (`phaseb/testmap.py:301`, `:360`) read the package and test tree under the `root` they are given, which is what a `load_` name says it loads; `build_parser`, `parse_args`, `parse_result`, `parse_verdict`, `parse_spec_def` and every `is_`/`resolve_` function do no I/O.
- Hits: No hits

#### A10 (sampled): Predicate semantics
- Mode: full
- Inspected: every `is_*`, `has_*` and `should_*` function in the tree (source and test files), body read against its name and docstring: `core.py` (`is_test_relpath`, `is_dunder_all_assignment`, `is_main_guard`), `phaseb/architecture.py` (`is_constant_operand`, `is_enum_class`, `is_under`, `is_external_call`), `phaseb/candidates.py` (`is_stub`, `is_builtin_call`, `is_overload`, `is_frozen_dataclass`, `is_well_defined_class`, `is_well_defined_type`, `is_t2_candidate`), `phaseb/docrefs.py` (`is_path_shaped`), `phaseb/testmap.py` (`is_test_path`, `is_fixture`, `is_property_test`), `rules/duplication.py` (`is_pytest_param`), `rules/error_handling.py` (`is_broad_handler`, `is_categorical_class_name_expr`, `is_tomllib_call`, `is_toml_source`, nested `is_domain`, `is_bound`), `rules/style_and_naming.py` (`is_stdlib_public_access_only`, `is_fixed_length_tuple`, `is_leading_underscore`), `tests/phaseb/test_t2_candidates.py` (`is_candidate_source`). Each conjunct is part of the question its name asks (`is_builtin_call`'s not-imported/not-defined test is what makes a bare name a builtin; `is_t2_candidate`'s conjuncts are the T2 candidacy definition its docstring states).
- Hits: No hits

#### A12 (sampled): assert misuse
- Mode: full
- Inspected: AST walk for `ast.Assert` over every tracked non-test `.py` file (`claude/skills/auditme/checks/**`), plus a grep for `^\s*assert`.
- Hits: No hits (no `assert` outside test files)

#### A13 (sampled): Same value to multiple structural slots
- Mode: full
- Inspected: AST walk over every tracked `.py` file (source and tests) for calls to a capitalised callee passing the same non-constant expression to two or more positional or keyword slots. One site found, `phaseb/docrefs.py:281` `DocTarget(kind, rel, rel, 1, last_line)` (`id` and `path` both `rel`): it sits inside the explicit factory `path_target`, whose docstring and the `DocTarget.id` field comment (`'path' for a file or directory`) state the equality, so it meets the question's own remedy.
- Hits: No hits

#### A14 (sampled): Repeated computation per request
- Mode: full
- Inspected: project-state helpers in the checker (`auditme.core.audit_roots`, `cached_roots`, `declared_roots` / `cached_declared_roots`, `phaseb.docrefs.tracked_files`, `candidates.read_pyproject`, `imports_and_surfaces.project_bans_as_imports` / `project_has_all_guard`) and every call site; then each registered Phase B lister run once against this repository with call counters on `audit_roots`, `declared_roots`, `packages_under` and `tracked_files`, cache cleared between listers. The sweep's `subprocess-without-memoisation` hits in `rules/project_hygiene.py` are the sweep's and not repeated here.
- Hits:
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py:605` - `list_a1_candidates` resolves `auditme.core.audit_roots(scope)` three times in one listing (via `read_audited_files` at :85, directly at :619, and via `capture_hits` -> `cached_roots` at :50); only the `[tool.auditme]` read is cached, and with no declaration each call repeats the `src/` and extra-root `rglob` scan and rebinds `ROOT_MODULES`; `auditme.core.cached_roots` exists for single resolution
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py:755` - `list_a17_candidates` resolves `auditme.core.audit_roots(scope)` three times in one listing (via `read_audited_files` at :85, directly at :772, and via `capture_hits` -> `cached_roots` at :50); same uncached directory scan, `cached_roots` not used

#### A15 (sampled): Duplicate constructor / serialisation logic
- Mode: full
- Inspected: every class defined in the checker, with every constructor call site in source and test files grouped by class and compared by field set (`Candidate`, `Verdict`, `DocTarget`, `Site`, `Scope`, `SiteCounter`, `Plan`, the error classes, and the rest), plus every `dataclasses.asdict` / `json.dumps` serialisation site. In source, `Candidate`'s three sites are the three per-shape factories `site_candidate`, `span_candidate` and `section_candidate` (`phaseb/candidates.py:253-265`); `DocTarget`'s two are the factories `node_target` and `path_target`; `Verdict` is built from fresh fields once (`phaseb/batches.py:282`) and decoded once (`phaseb/ledger.py:54`); verdict serialisation lives only in `write_ledger`.
- Hits:
  - `claude/skills/auditme/tests/phaseb/test_ledger.py:18` - `make_ledger_verdict` assembles `Verdict` with the same field set and the same values as `make_model_verdict` (`tests/phaseb/test_model.py:19`) and `make_batch_verdict` (`tests/phaseb/test_batches.py:18`); three per-file copies of one test builder, not factored into `claude/skills/auditme/tests/conftest.py` beside `make_candidate`

#### A16 (sampled): CLI entry envelope
- Mode: full
- Inspected: `git ls-files '*.py'` for any `cli/*.py` (none in the tree), and every top-level `run_*` function (`checks/audit.py`, `checks/changed.py`, `checks/phaseb.py`, test helpers). The question covers only `run_*` functions in `cli/*.py`; no file matches.
- Hits: No hits (no `cli/*.py` module)

#### A18 (sampled): Hot-path setup
- Mode: full
- Inspected: every tracked `.py` and `.sh` file grepped for `def on_step|on_log|on_evaluate|on_batch_*`; the only matches (`claude/skills/auditme/tests/test_state_and_effects.py:821`, `:844`) are fixture source strings handed to the checker, not callback methods of this project.
- Hits: No hits

#### A20 (sampled): Mutable module-level singleton
- Mode: full
- Inspected: every module-level assignment in non-test `.py` files (and `claude/skills/auditme/tests/conftest.py`, the one test module other modules import); for each `dict`/`set`/`list` literal, comprehension or bare-constructor value, grepped all tracked `.py` and `.sh` files for `from <module> import <name>`, `<module>.<name>` and `sys.modules['<module>'].<name>`. Read elsewhere and mutable: `core.py` `EMITTED`, `UNREADABLE`, `SOURCE_CACHE`, `INDEX_CACHE` and `phaseb/candidates.py` `REGISTRY`, `KINDS` - all sweep hits (`mutable-module-level-exported`, accepted), so not mine. Mutable but read only in their own module: `candidates.py` `TAKES_DEPTH`; `imports_and_surfaces.py` `STDLIB`; `state_and_effects.py` `DISK_IO_NAMES`, `MUTABLE_VALUE_SHAPES`, `MUTABLE_CONSTRUCTORS`; `style_and_naming.py` `STRFTIME_TOKENS`, `PARAMETRIC_NONBUILTIN_GENERICS`, `TYPING_DEPRECATED_ALIASES`; `changed.py` `RULE_HELP`; `phaseb.py` `COMMANDS` (the `test_annotated_all.py` mention is fixture text); `conftest.py` `GIT_ENV_ARGS`. `__all__` lists are read by the import system, not by name.
- Hits: No hits

#### A21 (sampled): Lazy init race
- Mode: full
- Inspected: every `is None:` test in non-test `.py` files and every `global` statement; none is an `if X is None: X = ...` lazy initialisation of module state (the `ROOT_MODULES` rebinding in `core.py` `audit_roots`/`cached_roots` is an unconditional per-run assignment, and the per-run caches use `key not in CACHE`). No threading, multiprocessing, `concurrent.futures` or asyncio use in the code (only as names in checker tables); the CLIs are single-threaded.
- Hits: No hits

#### A22 (sampled): Fall-through after partial handling
- Mode: full
- Inspected: AST scan of every non-test `.py` file for an `if` branch holding a `try` whose handler raises, where the branch does not leave and statements follow; one site (`claude/skills/auditme/checks/changed.py:196`, `scope_records`) - its handler re-raises `ChangedError`, so nothing after it runs with the untranslated state. Read the three `.sh` files (`bin/check-foreign-names.sh`, `bin/install-claude.sh`, `claude/hooks/auditme-stop.sh`) by hand: each failing branch exits.
- Hits: No hits

#### A23 (sampled): Discarded multi-return
- Mode: full
- Inspected: every non-test function annotated `-> tuple[...]` and every call site of it, plus callers of the dataclass-returning `read_plan`, `read_run_check`, `merge_verdicts`, and the `subprocess.run` results in `changed.py`, `docrefs.py` and `project_hygiene.py`. Discards are named (`roots, _ =`, `ruff, _ =`, `found, _ =`, `_, records =`, `lister, _, _ =`) or are single-purpose projections whose dropped components are not documented as changing the kept one (`read_source`/`read_and_parse` on `cached_source`, `read_is_private` on `privacy`, `question_brief`/`question_batch_size` on `registered`, `read_run_check(...).problems`).
- Hits: No hits

#### A24 (sampled): Identity of subprocess / shell-out calls
- Mode: full
- Inspected: every `subprocess.run`/`check_output`/`Popen` in non-test `.py` files and every `git`/external call in the `.sh` files. `project_hygiene.py:50`, `:104`, `:225` are sweep hits (`subprocess-without-memoisation`, accepted), not mine; `project_hygiene.py:112` is the one conditional retry inside the `:104` site with a different environment. `docrefs.py:301` (`tracked_files`) runs once per Phase B invocation (one question per command; `CorpusIndex.build` or `list_doc2_candidates`, never both for one question). `changed.py:64` (`run_git`) is called with distinct arguments each time per run. `auditme-stop.sh` calls `git_dir` on two different directories.
- Hits: No hits

#### A25 (sampled): Shallow immutable wrapper
- Mode: full
- Inspected: every module-level `MappingProxyType(...)`, `frozenset(...)`, `tuple(...)` and tuple literal in non-test `.py` files read from another module (`core.py` `BARE_GENERIC_NAMES`, `LITERAL_DISPATCH_TYPE_NAMES`, `EXTRA_ROOT_NAMES`, `ROOT_MODULES`, `SIDE_EFFECT_CALL_NAMES`; `registry.py` `CHECKS`, `PROJECT_CHECKS`; `architecture.py` `A*_CHECKS`/`A*_RULES`; `candidates.py` `T2_*`; `error_handling.py` and `style_and_naming.py` frozensets; `testmap.py` `TEST_TREES`; `ledger.py` `REQUIRED`). Every member is a `str`, a `pathlib.Path`, a function or an `ast` class; none is a `dict`/`list`/`set`, a container one tuple deep, or an instance of a non-frozen project dataclass.
- Hits: No hits

#### S1 (sampled): Type annotations on every signature
- Mode: full
- Inspected: every tracked `.py` file (`git ls-files '*.py'`), every `def`/`async def` at any depth, parsed with `ast`: each parameter (positional-only, positional, keyword-only, `*args`, `**kwargs`; a leading `self`/`cls` exempt) and each return annotation. Shell files have no signatures to annotate.
- Hits: No hits in non-test source (every signature annotated). Test-file count (files under a `tests/` directory): 130 missing parameter annotations, 32 missing return annotations, 8 modules affected, 26 modules fully annotated.

#### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake
- Mode: full
- Inspected: every tracked `.py` file via `ast`: class names, function and method names, parameter names, local bindings, module-level bindings; and the variable names of `bin/check-foreign-names.sh`, `bin/install-claude.sh`, `claude/hooks/auditme-stop.sh`. Module-level PascalCase names (`Check`, `FunctionNode`, `Lister`, `HandlerLevel`, the tests' `Builder`/`Runner`/`Project`/`Node`/`StubRuff`) are type aliases, named as types; `pytestmark` is the name pytest requires; function-local constants are UPPER_SNAKE throughout the tree (one idiom, not a mix); shell scripts use UPPER_SNAKE for constants and lower_snake for variables consistently.
- Hits: No hits

#### S3 (sampled): TYPE_CHECKING block placement
- Mode: full
- Inspected: every `if typing.TYPE_CHECKING:` block in tracked `.py` files. Each is module-level, directly after the imports, holding only imports (`audit.py:92`, `changed.py:38`, `phaseb/batches.py:24`, `phaseb/ledger.py:22`, `phaseb/testmap.py:19`, the five `rules/*.py` at lines 10-11, and the test modules `conftest.py:37`, `test_docrefs.py:14`, `test_ledger.py:14`, `test_model.py:11`, `test_changed.py:17`, `test_imports_and_surfaces.py:11`). In `changed.py` and `conftest.py` the block follows the `sys.path` set-up and the `noqa: E402` imports that need it, still after the last import. The other matches are fixture strings and docstrings.
- Hits: No hits

#### S4 (sampled): Project-specific rule files
- Mode: full
- Inspected: the rules AGENTS.md references: the no-project-names rule (enforced by the `no-project-names` hook, `bin/check-foreign-names.sh`), and `claude/rules/auditme/coding-standards.md`, `imports.md`, `dependencies.md` (installed from `claude/rules/auditme`), plus `~/.claude/rules/python/argparse.md` which coding-standards names. Checked every tracked `.py` file for the parts the sweep and ruff do not check: `as` imports (only in fixture strings), `from __future__` (none outside fixtures/prose), stdlib `logging` (none), `%`/`.format()` (only `.format` on named template constants in `tests/test_error_handling.py`, which the sweep's `legacy-formatting-format` rule deliberately exempts), wildcard imports (fixtures only), `from X import Y` outside `__init__.py` (only the four sweep-reported, accepted sites, and fixture strings), `print` (machine-readable stdout of the stdlib-only checker's CLIs and `core.emit`), argparse (used only in the stdlib-only checker scripts, as argparse.md allows; every call with arguments has a trailing comma). Fixture names are neutral (`pkg`, `probe`, `Probe`).
- Hits: No hits

#### P1 (sampled): O(n^2) on real-size inputs
- Mode: full
- Inspected: every tracked `.py` and `.sh` file; measured the sweep (`audit.py`, per-check wall time) and every registered Phase B lister (`phaseb.py candidates --question <Q>` for A1, A11, A17, A19, A4, Doc1, Doc2, Doc4, Doc5, T1, T2) on two real projects of about 340 and 760 tracked Python files (about 111k and 229k lines), on 2026-11-22. The sweep took 48 s and 70 s: doubling the input raised each check's time by 1.1-2.3x, so no check grows quadratically. The previously dismissed `check_duplicate_call_sequence` and `check_asymmetric_exception_translation` are unchanged since review-6 (no diff in either function since `eba7404`). A17's `read_entries` re-sorts the whole reads index once per `__init__.py` (64 sorts of 11,230 keys: 0.5 s of 12.6 s), small.
- Hits:
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py:297` - `list_a11_candidates` calls `flag_subjects(function)` for every statement of a function, and `flag_subjects` (line 180) `ast.walk`s the whole function, so the work is statements x nodes per function (quadratic in function length). Measured on 2026-11-22: on the 340-file project, 49,134 calls for 5,804 distinct functions; the A11 lister took 22.0 s as written against 6.6 s with `flag_subjects` memoised per function (same 164 candidates); on the 760-file project, 78,902 calls for 15,583 functions, 15.6 s against 7.6 s.

#### P2 (sampled): Blocking I/O in hot paths
- Mode: full
- Inspected: every tracked `.py` and `.sh` file for reads and writes inside loops of a training step, request handler or callback. The tree has none of those: the checks, listers and CLIs are batch tools run once per command; the Stop hook (`claude/hooks/auditme-stop.sh`) runs the checker once per turn end, which is its job, and skips the sweep when no changed file can carry a hit.
- Hits: No hits

#### P3 (sampled): Repeated expensive computation per request
- Mode: full
- Inspected: every tracked `.py` and `.sh` file, with the profiles and timings from P1 (cProfile of the sweep and of the A1, A11, A17, Doc4 and T1 listers on the 760-file project). Per-file source and trees are cached (`core.cached_source`), corpus-wide indexes are built once per run (`core.corpus_index`), and `spec_markdown_files` is called once per sweep and once per Doc lister. The A11 per-statement re-walk is reported under P1, not again here.
- Hits:
  - `claude/skills/auditme/checks/auditme/core.py:245` - `all_py_files` re-lists its root with `rglob`/`glob` on every call, and every check calls it once per root, so one sweep lists the same root's files about 70 times (214 calls in one sweep on the 760-file project), though `cached_corpus_files` already lists the corpus once per run. Measured on 2026-11-22: 72 listings of each of the 3 roots of the 760-file project took 3.5 s, against 70 s for the whole sweep (about 5% of each sweep, and the sweep runs at every commit, every push and every Stop-hook turn end).

#### Sec1 (sampled): Secrets in source
- Mode: full
- Inspected: every tracked file (`git ls-files`, at 8181700), searched for `api_key`/`secret`/`password`/`passwd`/`token` assigned to string literals of 12+ characters, token prefixes (`ghp_`, `gho_`, `github_pat_`, `sk-`, `AKIA`) and PEM private-key headers; `.github/workflows/ci.yml` and `docs.yml`. Matches were review prose and the `ghp_import` wheel name in `uv.lock`; `docs.yml` passes `secrets.GITHUB_TOKEN` through `env` to the deploy step only, with `persist-credentials: false` on every checkout.
- Hits: No hits

#### Sec2 (sampled): Input validation at system boundaries
- Mode: full
- Inspected: the CLI parsers and their checks in `claude/skills/auditme/checks/audit.py` (`scope` checked `is_dir`, `--package` checked as a bare name, `--extra-root` checked for containment), `claude/skills/auditme/checks/changed.py` (`--base` refused when it starts with `-`, `repo_root` resolved through git), `claude/skills/auditme/checks/phaseb.py` (`--question` checked against the registry, `--depth` positive, `--batch-size` checked by `plan_batches`); `bin/check-foreign-names.sh`, `bin/install-claude.sh`, `claude/hooks/auditme-stop.sh` (hook payload read through `jq`). Probed `phaseb.py candidates|report|plan /nonexistent/xyz --question T1` (and `Doc1`, `A4` for `candidates`): each exits 0 with no candidates, "0 open findings" or "0 planned in 0 batches".
- Hits:
  - `claude/skills/auditme/checks/phaseb.py:96` - the `root` positional of every subcommand (`candidates` 96, `plan` 107, `merge` 145, `report` 161, `dismiss` 172) is never checked to be an existing directory, so a mistyped root gives an empty candidate list and exit 0, read as "no findings" (`audit.py` refuses the same mistake with exit 2)

#### Sec3 (sampled): Command injection
- Mode: full
- Inspected: every `subprocess` call in tracked Python (`changed.py:64` and `:236`, `auditme/rules/project_hygiene.py:50`, `:104`, `:112`, `:225`, `auditme/phaseb/docrefs.py:301`, and the tests' runners): all take an argument list with no `shell=True`; no `os.system`, `eval` or `exec`. Shell scripts: `bin/check-foreign-names.sh` (names passed to `grep -F -e`, files after `--`), `bin/install-claude.sh` (quoted `exec uvx`), `claude/hooks/auditme-stop.sh` (payload only through `jq`, checker path quoted, `python3 -I`).
- Hits: No hits

#### Sec4 (sampled): Path traversal
- Mode: full
- Inspected: path joins from CLI input in `audit.py` (`--package` refused unless a bare name other than `.`/`..`; `--extra-root` checked with `auditme.core.path_inside`), `phaseb.py` `ledger_path` (question validated against the registry before the join), `auditme/phaseb/batches.py` batch/result/plan names (built from integers and a constant), `changed.py:198` (paths from `git diff` output under the repository root), `auditme-stop.sh` (a worktree's own checker run only when its git common directory matches the installed checker's).
- Hits: No hits

#### Sec5 (sampled): PII in logs
- Mode: full
- Inspected: every tracked Python and shell file for `logging`, `logger`, `loguru` and log-level calls: no shipped code logs (`loguru` appears only inside fixture source strings in `tests/phaseb/test_architecture_candidates.py`, and `LOGGER_NAMES` in `architecture.py` is a detection list); output is hit records and error lines on stdout/stderr.
- Hits: No hits

#### T3 (sampled): Integration vs unit balance
- Mode: full
- Inspected: the orchestrating entry points and their tests: `audit.py` (`tests/test_driver.py` runs the shipped script as a subprocess on fixture projects), `phaseb.py` (`tests/phaseb/test_cli.py` runs it as a subprocess through plan, check, merge and report on a fixture project), `changed.py` (`tests/test_changed.py` calls `changed.main` on real git fixture repositories, running the real sweep), `auditme-stop.sh` (`tests/test_stop_hook.py`), `bin/install-claude.sh` (`tests/test_install_claude.py`), `bin/check-foreign-names.sh` (`tests/test_check_foreign_names.py`).
- Hits: No hits

#### D1 (sampled): Declared in pyproject
- Mode: full
- Inspected: every top-level import in tracked Python against the standard library, the project's own modules (`auditme`, `audit`, `changed`, `phaseb`, `conftest`) and `pyproject.toml`'s `[dependency-groups]`: third-party imports are `pytest` and `hypothesis`, both declared in `dev`; `loguru`, `requests`, `orjson`, `probe`, `pkg` and `gitutils` occur only inside fixture source strings.
- Hits: No hits

#### D2 (sampled): Unused declarations
- Mode: full
- Inspected: `pyproject.toml` `dev` (`hypothesis`, `pytest` imported in tests; `ruff` run by the `ruff-pre-commit` repo in `.pre-commit-config.yaml` and as `ruff` by `project_hygiene.py`) and `docs` (`mkdocs` run as `uv run mkdocs` in `.github/workflows/docs.yml`; `mkdocs-material` loaded as `theme: name: material` in `mkdocs.yml`).
- Hits: No hits

#### D3 (sampled): Lockfile coherence
- Mode: full
- Inspected: the sweep hits in `/tmp/audit-auditor.jsonl` (no lockfile-drift hit); `uv lock --check` resolved with no drift.
- Hits: No hits

#### Doc3 (sampled): README.md and AGENTS.md consistent
- Mode: full
- Inspected: `README.md` (all), `AGENTS.md` (all); checked their shared statements against `.pre-commit-hooks.yaml` (hook ids `auditme-changed`, `auditme-all`, `no-project-names` and their stages), `.pre-commit-config.yaml` (stages incl. `pre-push`, `commit-msg`), `bin/install-claude.sh` (links `claude/` and appends the Stop hook to `~/.claude/settings.json`), the `claude/` tree, and the `docs/` statements on the same points (`docs/index.md`, `docs/concepts.md:55`, `docs/setup.md`, `docs/reference/cli.md:246-253`, `docs/reference/skills.md`, `docs/reference/rules.md`). Both files give the same test command (`README.md:19`, `AGENTS.md:22`), the same install contents, and the same account of the agents repository supplying the other rules and skills.
- Hits: No hits

#### Spec review
- agents/specs/auditme-false-positives/spec.md - no gap (Settings omitted, allowed)
- agents/specs/listed-phase-b-architecture-questions/spec.md - no gap
- agents/specs/listed-phase-b-documentation-questions/spec.md - no gap
- agents/specs/listed-phase-b-test-questions/spec.md - no gap
- agents/specs/project-setup/spec.md - no gap
- agents/specs/raises-section-resolution/spec.md - no gap
- agents/specs/repeatable-phase-b/spec.md - no gap
- agents/specs/index.md - no gap (every entry's link resolves)

## Prior findings re-verified

No finding was open: review-10 raised none, and review-9's F1 shipped before it. No task list under `agents/tasks/audit-reviews/` has an incomplete task.

## Decisions

None this review.

## Answers

Answered on the review page on 2026-11-22. Every item took the recommended option, with no comments.

| Item | Answer |
|---|---|
| F1-F4 | Fix |
| F5 | Dismiss (about a twentieth of the sweep) |
