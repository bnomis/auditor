# Audit Review 13

**Date:** 2026-11-22
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`); every sampled question ran on the whole tree
**Commit:** b0166c2e65eb8f901879f9dda99fae5c4482bd49
**Script output:** /tmp/audit-auditor.jsonl (48 hits, 48 accepted, 0 unaccepted)
**Script version:** 749b6cf647a5f6d10d9066c4e01bc16ceceda08291aed6adf65ec845433a359c
**Convergence note:** the second loop the operator delegated on 2026-11-22. Measured on 2026-11-22: 139 listed candidates judged (T1 113, Doc5 12, Doc4 8, T2 6). Two of the five findings were made by the last two fixes themselves: loop 1's root-caching task wrote `cached_roots(scope)[0]`, the subscript review-7 F3 removed (F3 here), and review-12's F1 fix added a closed list of exit causes that is incomplete again (F4). Each fix below adds a guard so it cannot recur: a test that fails on the pattern, or a rule stated instead of a list.
**Review page:** https://claude.ai/artifact/DCDaePsYs1x8GgUZMhVN47

## What is being reviewed and how

This is the checker repository's thirteenth audit of its own code, a whole-tree pass. The operator delegated the loop on 2026-11-22, so Claude answers this page by taking each recommendation, and records that in the Answers section.

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 48 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 139 judged; every other listed question carried every verdict |
| `phaseb.py check` on every listed question | pass, no retries |
| Every sampled question returned a hit list or "no hits" | pass |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| Prior findings to re-verify | review-12 F1-F4: shipped; F1's paragraph is incomplete again (F4 below) |

## Summary

The sweep reports 48 hits, all accepted. Phase B leaves 2 listed verdicts open (T1 1, Doc5 1). The sampled questions flag Sec2 1, A23 3 and A14 1. The spec review finds no gap.

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits.

## Phase B findings (consolidated)

### F1. `cached_per_run` has no direct test (T1)

- **Category:** T. **Question:** T1 (listed). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/core.py:452`, added by Task 2 of the review-12 task list.
- **Description:** it is public (in core's `__all__`) and is reached only through `project_has_all_guard`.
- **Recommendation:** test it directly: one computation per name and scope in a run, a fresh one after the per-run cache is cleared.

### F2. The names hook passes a commit when its list path is a directory (Sec2)

- **Category:** Sec. **Question:** Sec2 (sampled). **Severity:** medium.
- **Location:** `bin/check-foreign-names.sh:26`.
- **Description:** `[ ! -f "$list" ]` sends every path that is not a regular file, a directory included, to "no list ...; nothing checked" and exit 0, so the commit passes unchecked; the "cannot read" exit 2 at line 31 is never reached for it. Reproduced on 2026-11-22.
- **Recommendation:** exit 0 only when nothing exists at the path (`[ ! -e "$list" ]`), and exit 2 for one that exists but is not a readable regular file; test both; keep `docs/reference/cli.md`'s exit table in step.

### F3. Three root lookups drop the modes with a bare subscript again (A23)

- **Category:** A. **Question:** A23 (sampled). **Severity:** low.
- **Locations:** `claude/skills/auditme/checks/auditme/phaseb/architecture.py:85`, `:622`; `claude/skills/auditme/checks/auditme/phaseb/candidates.py:382`.
- **Description:** `cached_roots(scope)[0]` drops each root's mode; the `all_py_files` calls that follow get it only through the `ROOT_MODULES` side effect. Task 2 of the review-11 task list wrote these lines, bringing back the pattern review-7's F3 removed at `architecture.py:50`.
- **Recommendation:** unpack each into named parts (`roots, _modes = ...`), and add a test that fails if any `cached_roots(...)[` subscript appears under `claude/skills/auditme/checks/`, so a later fix cannot bring it back.

### F4. The `phaseb.py` exit-2 paragraph is a closed list again (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed). **Severity:** low.
- **Location:** `docs/reference/cli.md:176`, added by Task 1 of the review-12 task list.
- **Description:** the paragraph lists exit-2 causes without "for example"; the code also exits 2 on a merge whose batches still fail `check` (`batches.py:270`) or that names an id no longer a candidate (`:280`), a `dismiss` of an id with no verdict (`ledger.py:157`), a sweep check raising inside an A lister (`architecture.py:54`), and a failing `git ls-files` (`docrefs.py:303`). Any list of every error goes stale with the next one added.
- **Recommendation:** state the rule (`phaseb.py` exits 2, with the error's message, whenever a Phase B step fails) and mark the cases that follow as examples.

### F5. The lazy-import table is parsed once per audit root (A14)

- **Category:** A. **Question:** A14 (sampled). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/core.py:263` (`accepted_lazy_imports`), from `check_in_function_imports` (`rules/imports_and_surfaces.py:151`).
- **Description:** the review-12 caching task found its helpers by one signature pattern and missed this one; the other helpers reading `AGENTS.md` already go through `cached_per_run`.
- **Recommendation:** route it through `cached_per_run`; then grep `checks/auditme/` for every helper that reads `AGENTS.md` or `pyproject.toml` and check each is cached per run.

## Phase B per-question results

Listed questions: the verdicts are in `agents/audit-reviews/ledger/`; `phaseb.py report <root> --question <Q>` prints the open ones: T1 (F1) and Doc5 (F4).

#### A2 (sampled): Except tuple coverage
- Mode: full
- Inspected: every `try` in every tracked non-test `.py` file at `b0166c2`, listed by AST with its handler types and body calls (`audit.py`, `changed.py`, `phaseb.py`, `auditme/core.py`, `auditme/phaseb/{architecture,batches,candidates,docrefs,ledger,testmap}.py`, `auditme/rules/project_hygiene.py`), plus the Python diff since review-12's `add7b4c` (`cached_per_run` in `core.py`, the `scan_*` splits in `rules/imports_and_surfaces.py`), which adds no `try`. Every decoding disk body catches `OSError` and `UnicodeDecodeError` (`core.py:154`, `architecture.py:87,743`, `batches.py:148,207`, `candidates.py:194,397,575`, `docrefs.py:86`, `ledger.py:67`, `testmap.py:56`, `changed.py:197`); `batches.py:148` also catches `json.JSONDecodeError`. Byte-only bodies (`core.py:97,125,144`, `candidates.py:82,411,603`, `docrefs.py:316`) and write bodies (`batches.py:129`, `ledger.py:91,105`) catch `OSError`. In-memory `json.loads`/`tomllib.loads` bodies (`ledger.py:76`, `changed.py:255`, `project_hygiene.py:64`, `core.py:345`) touch no disk; subprocess-only bodies are not disk bodies; `batches.py:219` catches `ValueError`, the base of `JSONDecodeError`; `architecture.py:44` is try/finally. No translating decorator or contextmanager envelope. No `pandas` or `.gz` use.
- Hits: No hits

#### A3 (sampled): Domain-error layering
- Mode: full
- Inspected: every `raise` in every tracked non-test `.py` file at `b0166c2` (grep for `raise` statements, inline ones included). Raised types: `auditme.core.RootsError`, `auditme.core.CachedReadError`, `auditme.phaseb.errors.PhaseBError` (every `phaseb/` module, `phaseb.py:240,242`), `changed.ChangedError`; `SystemExit` at the entry points (`audit.py:246`, `changed.py:366`, `phaseb.py:300`); `argparse.ArgumentTypeError` in the argparse `type=` callables (`phaseb.py:46,58,80,82`), the type argparse requires. The `ValueError`s at `auditme/phaseb/batches.py:181-198` are sweep hits (`layer-has-domain-error-raises-stdlib`, accepted). No `rules/` module raises; the new `cached_per_run` raises nothing. Test-file raises are fakes.
- Hits: No hits

#### A5 (sampled): Two sources of truth
- Mode: full
- Inspected: module state rebound by the driver (`auditme.core.EXTRA_ROOT_NAMES` / `DECLARATION_IGNORED` at `audit.py:175-176`, after `clear_source_cache()` and before any root is read) against `extra_roots(names=None)`, `declared_roots` and `cached_roots`; `ROOT_MODULES` rebound with its roots; `phaseb.py` `--depth` against `Plan.depth` (mismatch refused at `phaseb.py:241-242`); `today=None` parameters in `ledger` and `batches`; and the new `core.cached_per_run` (`core.py:452`) with its callers `project_bans_as_imports`, `read_package_layering`, `project_has_all_guard` in `rules/imports_and_surfaces.py` - the cached answer and the `scan_*` computation are one value keyed on `(name, scope)` in `INDEX_CACHE`, which the driver clears each run, with the once-per-run rule stated in each docstring. Each precedence is stated and enforced.
- Hits: No hits

#### A6 (sampled): Stage method dual-path
- Mode: full
- Inspected: every class in every tracked `.py` file and every method that assigns to `self.<attr>` or mutates a `self` container (AST listing plus reading). No pipeline-stage class. Self-mutating methods: `SiteCounter.next` (`auditme/phaseb/architecture.py:106`, returns an `int`, not a tuple) and `IndexEntries.add_module` / `record` (`auditme/phaseb/docrefs.py:224,241`, return `None`); `IndexEntries.class_info` returns a `ClassInfo` and mutates only through `record`, a different field. `TestIndex.importers` / `reverse` in `testmap.py` are `functools.cached_property` members.
- Hits: No hits

#### A7 (sampled): Constructor purity
- Mode: full
- Inspected: every `__init__` and `__post_init__` in every tracked `.py` file (AST listing): `SiteCounter.__init__` (`auditme/phaseb/architecture.py:103`, an empty `Counter`), and the test fakes `Result.__init__` (`tests/test_project_hygiene.py:142`) and `LockResult.__init__` (`tests/test_project_hygiene.py:204`), which assign constants and arguments. No `__post_init__`. No I/O, no expensive compute, no argument mutated.
- Hits: No hits

#### A8 (sampled): Late dataclass mutation
- Mode: full
- Inspected: every `@dataclass` in the tracked `.py` files (all `frozen=True` except `ClassInfo` and `IndexEntries` in `auditme/phaseb/docrefs.py:149,217` and `TestIndex` in `auditme/phaseb/testmap.py:192`), and every attribute store whose target is not `self`/`cls`, every `setattr` and `__setattr__` call across every tracked file, tests included (AST scan). Non-self stores: module rebinds at `audit.py:175-176` and `tests/conftest.py:87` (not dataclass instances), and `tests/phaseb/test_model.py:48,50`, which assert `FrozenInstanceError`. `ClassInfo` is built complete at `docrefs.py:265`; `IndexEntries()` at `docrefs.py:186` is filled through its own methods before the frozen `CorpusIndex` is built from it; `TestIndex` is built complete in `testmap.py`. The new `conftest.make_candidate(**overrides)` updates a plain `dict` before constructing the frozen `Candidate`.
- Hits: No hits

#### A9 (sampled): Pure-named function side effects
- Mode: full
- Inspected: every function in every tracked `.py` file whose name (leading underscores stripped) starts with a pure prefix, found by an AST walk; each body's calls listed and read. Functions named in `CHECKS` or `PROJECT_CHECKS` in `claude/skills/auditme/checks/auditme/registry.py` excluded under the registered-check carve-out (every `check_*` with I/O, such as `check_ruff`, `check_lockfile`, `check_ruff_version` and `check_cli_entry_missing_error_envelope`, is registered). Read in full: `load_test_index` and `load_test_map` (`phaseb/testmap.py`; they read the package, its test tree and the roots declaration, which is what they say they load), `parse_result` (`phaseb/batches.py`; `json.loads` on a string), `resolve_setting` (`phaseb/docrefs.py`; `dataclasses.replace`, not I/O), `parse_args` (`changed.py`) and `build_parser` (`phaseb.py`; argparse only), and the test helpers `is_candidate_source`, `parse_call`, `parse_modules` and `parse_or_none` (all parse strings in memory).
- Hits: No hits

#### A10 (sampled): Predicate semantics
- Mode: full
- Inspected: every `is_*`, `has_*` and `should_*` function outside the test trees, each body read against its name and docstring: `core.py` (`is_test_relpath`, `is_dunder_all_assignment`, `is_main_guard`), `phaseb/architecture.py` (`is_constant_operand`, `is_enum_class`, `is_under`, `is_external_call`), `phaseb/candidates.py` (`is_stub`, `is_builtin_call`, `is_overload`, `is_frozen_dataclass`, `is_well_defined_class`, `is_well_defined_type`, `is_t2_candidate`), `phaseb/docrefs.py` (`is_path_shaped`), `phaseb/testmap.py` (`is_test_path`, `is_fixture`, `is_property_test`), `rules/duplication.py` (`is_pytest_param`), `rules/error_handling.py` (`is_broad_handler`, `is_categorical_class_name_expr`, `is_tomllib_call`, `is_toml_source`, nested `is_domain` and `is_bound`, the latter read against its use in `declared_reach` and `unset_optional_guard`), `rules/style_and_naming.py` (`is_stdlib_public_access_only`, `is_fixed_length_tuple`, `is_leading_underscore`; its exclusion of a bare `_`, dunders and mangled names is stated in its one-line docstring, so it is not a hidden conjunct). No `should_*` function exists.
- Hits: No hits

#### A12 (sampled): assert misuse
- Mode: full
- Inspected: `git grep -n -E '^\s*assert\b'` over every tracked `.py` file outside `claude/skills/auditme/tests/`, `claude/skills/auditme-project-setup/tests/` and `tests/`.
- Hits: No hits (no `assert` statement outside the test trees)

#### A13 (sampled): Same value to multiple structural slots
- Mode: full
- Inspected: an AST walk of every call in every tracked `.py` file for a non-constant argument expression passed to two or more slots, plus a second pass over calls to classes and `*candidate`/`*target` factories that also counted repeated constants. Read: `run_check(check, scope, scope)` in `checks/audit.py` (a comment says the scope stands in for the root project checks ignore), `candidates.span_candidate('A17', file.rel, file.rel, ...)` in `phaseb/architecture.py` (the `Candidate.id` field comment documents that A17 uses the path alone as its id), `DocTarget(kind, rel, rel, 1, last_line)` in `phaseb/docrefs.py` (inside the explicit factory `path_target`, with the `DocTarget.id` comment documenting it). The rest are `dict.get(key, key)` defaults and hypothesis strategies.
- Hits: No hits

#### A14 (sampled): Repeated computation per request
- Mode: full
- Inspected: every helper that takes only `scope` (or `scope` and `src_root`) and reads project state (pyproject roots, `AGENTS.md` tables, `git ls-files`, corpus listings, the ruff executable), and their call sites in the sweep driver (`checks/audit.py`: project checks once, `CHECKS` once per root; this repository declares several roots in `[tool.auditme]`) and in each `phaseb.py` command (one question's lister per invocation). Cached through `INDEX_CACHE`/`cached_per_run`/`corpus_index`: `cached_roots`, `cached_declared_roots`, `cached_corpus_files`, `ruff_executable`, `project_bans_as_imports`, `read_package_layering`, `project_has_all_guard`, `dataclass_frozen_by_name`, the read and definition indexes. `CorpusIndex.build` and `tracked_files` run once per `phaseb.py` command. Previously dismissed `auditme.core.all_py_files` (review-11 F5) is unchanged and not reported again.
- Hits:
  - `claude/skills/auditme/checks/auditme/core.py:263` - `accepted_lazy_imports(scope)` re-reads and re-parses the `AGENTS.md` lazy-import table on every call, and `check_in_function_imports` (`claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:151`), a per-root check, calls it once per root, so a sweep computes the same project-level answer once per declared root. Its sibling `AGENTS.md` readers in the same module (`project_bans_as_imports`, `read_package_layering`) go through `auditme.core.cached_per_run`; this one was left out of the review-12 work that cached them ("work out project-level answers once per sweep", commit `21916df`). The text read is cached, so the cost is small.

#### A15 (sampled): Duplicate constructor / serialisation logic
- Mode: full
- Inspected: every call to a class defined in the repository, grouped by class with each site's argument and keyword set, in both source and test trees. Source: `Candidate` (built only in the three factories `site_candidate`, `span_candidate` and `section_candidate` in `phaseb/candidates.py`), `Verdict` (`phaseb/batches.py` from a reviewer record, `phaseb/ledger.py` from a ledger row: different inputs), `Site`, `Scope`, `DocTarget` and `SiteCounter` (field sets differ per site, or one function), and the exception classes (message only). Tests: `Candidate`/`Verdict` only through the shared `make_candidate`/`make_verdict` builders in `claude/skills/auditme/tests/conftest.py`; `LockResult` and `subprocess.CompletedProcess` in `test_project_hygiene.py` take one or two positional values.
- Hits: No hits

#### A16 (sampled): CLI entry envelope
- Mode: full
- Inspected: `git ls-files '*.py'` for any `cli/*.py` (none) and `git grep cappa` (only a mention in `rules/error_handling.py`, the checker's own rule text). The `run_*` functions in `claude/skills/auditme/checks/phaseb.py` are not in a `cli/` module, so the question's enumeration does not reach them.
- Hits: No hits

#### A18 (sampled): Hot-path setup
- Mode: full
- Inspected: every tracked `.py` and `.sh` file (`git ls-files '*.py' '*.sh'`), searched for callback methods (`def on_*`, including `on_step`, `on_log`, `on_evaluate`, `on_batch_*`).
- Hits: No hits (no callback method is defined anywhere in the tree).

#### A20 (sampled): Mutable module-level singleton
- Mode: full
- Inspected: an AST pass over every tracked `.py` file for module-level bindings to a `dict`/`set`/`list` literal, comprehension or bare builtin constructor call, and to `MappingProxyType`/`frozenset`/`tuple`, and for each a grep across every tracked `.py` file (source, `bin/` and tests) for `from <module> import <name>`, `<module>.<name>` and `sys.modules['<module>'].<name>`. The mutable containers read from elsewhere (`core.py` `EMITTED`, `UNREADABLE`, `INDEX_CACHE`; `phaseb/candidates.py` `REGISTRY`, `KINDS`) are all sweep hits (`mutable-module-level-exported`, accepted), so they are not this reviewer's. Every other one read from elsewhere is wrapped (`frozenset`, `MappingProxyType`, tuple).
- Hits: No hits

#### A21 (sampled): Lazy init race
- Mode: full
- Inspected: every `if X is None:` and every `global` rebinding in non-test `.py` files (`core.py` `ROOT_MODULES` in `audit_roots`/`cached_roots`, the `INDEX_CACHE`/`SOURCE_CACHE` fill-on-miss helpers), plus a search for `threading`, `multiprocessing`, `concurrent` and `Pool(` in code. The tool is a single-threaded CLI: no code path starts a thread or a process that could call these helpers concurrently.
- Hits: No hits

#### A22 (sampled): Fall-through after partial handling
- Mode: full
- Inspected: an AST pass over every non-test `.py` file for an `if`/`else` whose branches hold a `try` with a raising handler, do not all end in `return`/`raise`, and are followed by more statements. The one match, `claude/skills/auditme/checks/changed.py:196` (`scope_records`), raises a translated `ChangedError` and never falls through to a retry. Shell files have no raise/return chains of this shape.
- Hits: No hits

#### A23 (sampled): Discarded multi-return
- Mode: full
- Inspected: every non-test function annotated `-> tuple[...]` (fixed length), and every call to one that does not unpack the result into names: `[0]`/`[1]` subscripts, bare expression calls and single-name assignments (each checked for a later unpack). The `cached_source` wrappers (`read_source`, `read_and_parse`), `read_is_private` (`privacy(...)[0]`) and the `registered(...)` accessors are named, documented projections with no hidden state. The three hits below drop the root-mode mapping that `cached_roots` returns, and the code after them depends on that mapping through the `ROOT_MODULES` global, which the call rebinds as a side effect. `phaseb/docrefs.py:183` names the same discard explicitly (`roots, _ = ...`).
- Hits:
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py:85` - `cached_roots(scope)[0]` silently drops each root's mode, but `all_py_files`/`module_dotted` below depend on it through the `ROOT_MODULES` global that the call sets
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py:622` - `cached_roots(scope)[0]` silently drops the modes; `translator_envelopes(src_root)` walks each root by `all_py_files`, which reads the mode from `ROOT_MODULES`
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py:382` - `cached_roots(scope)[0]` silently drops the modes; `root_candidates` -> `root_sites` walks each root by `all_py_files`/`module_dotted`, which read the mode from `ROOT_MODULES`

#### A24 (sampled): Identity of subprocess / shell-out calls
- Mode: full
- Inspected: every `subprocess.run`/`check_output`/`Popen` and every `git` shell-out in non-test `.py` and `.sh` files: `phaseb/docrefs.py:301` `tracked_files` (one call per `CorpusIndex.build` or Doc2 listing, and `phaseb.py` lists exactly one question per invocation), `changed.py` `run_git`/`git_lines` (each `git` command runs once per invocation with different arguments) and `sweep` (once), `rules/project_hygiene.py:50,104,112,225` (sweep hits, accepted; line 112 re-runs with a different environment), `claude/hooks/auditme-stop.sh` (`git rev-parse` on different directories), `bin/check-foreign-names.sh`, `bin/install-claude.sh`.
- Hits: No hits

#### A25 (sampled): Shallow immutable wrapper
- Mode: full
- Inspected: every module-level `MappingProxyType(...)`/`frozenset(...)`/`tuple` read by name from another module: `core.py` `BARE_GENERIC_NAMES`, `EXTRA_ROOT_NAMES`, `ROOT_MODULES` (an empty literal at line 307; rebound at line 477 from a comprehension of `Path` -> `str`), `SIDE_EFFECT_CALL_NAMES`; `phaseb/candidates.py` `T2_ENUM_BASES`; `registry.py` `CHECKS`, `PROJECT_CHECKS` (function references); `rules/project_hygiene.py` `SPEC_SKIP_PARTS`. Every member is a string, a path or a function.
- Hits: No hits

#### S1 (sampled): Type annotations on every signature
- Mode: full
- Inspected: every tracked `.py` file (`git ls-files '*.py'`), every `def`/`async def` walked with `ast` for unannotated parameters (bar `self`/`cls`) and missing returns; cross-checked with `ruff check --select ANN --statistics` (same totals; its 2 ANN401 are `Any` uses, not missing annotations). No AGENTS.md note records a test-annotation exemption, so there is no figure to drift-check.
- Hits: non-test source: No hits. Tests (count only): 130 missing parameter annotations, 32 missing return annotations, 7 test modules affected, 27 of 34 test modules fully annotated.

#### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake
- Mode: full
- Inspected: every class, function, parameter, module-level and function-local binding in every tracked `.py` file (ast scan against `coding-standards.md` Naming); variable case in the four tracked `.sh` files. Function-local literal constants are UPPER_SNAKE everywhere they occur (no lower-case counterpart), `ROOT_MODULES` in `core.py` is a `global`, `pytestmark` is pytest's required name.
- Hits: No hits

#### S3 (sampled): TYPE_CHECKING block placement
- Mode: full
- Inspected: every `if typing.TYPE_CHECKING:` at module level in tracked `.py` files (checks, phaseb, rules, tests); each sits directly after the last import, including `changed.py` and `tests/conftest.py`, whose last imports follow a `sys.path` set-up. Indented occurrences are fixture strings or tests of the rule. No real `from __future__ import annotations` (only fixture string constants).
- Hits: No hits

#### S4 (sampled): Project-specific rule files
- Mode: full
- Inspected: rules AGENTS.md points to (`claude/rules/auditme/coding-standards.md`, `imports.md`, `dependencies.md`) and the shared python rules they reference (`argparse.md`, `asserts.md`, `logging`); checked across non-test source for what the sweep does not enforce: `as` imports, wildcard imports, stdlib `logging`, `%`/`.format()` formatting, `assert` in product code, argparse use and trailing-comma style, non-machine `print()`, leading-underscore defs, clean `__init__.py`. argparse is allowed (the checker is stdlib-only; every import under `checks/` is stdlib or first-party); `print()` writes JSON lines / CLI summaries to stdout; both `__init__.py` files hold only docstring, re-exports and `__all__`.
- Hits: No hits

#### P1 (sampled): O(n^2) on real-size inputs
- Mode: full
- Inspected: every rule and phaseb module; measured on one project with 766 tracked Python files: full sweep 64.0 s unprofiled, per-check timing with the largest `check_asymmetric_exception_translation` 5.7 s (8.9%, dismissed in review-6), then `check_spec_api_signature_drift` 4.65 s (7.3%), `check_duplicate_call_sequence` 4.0 s (6.3%, dismissed); every Phase B lister timed (5.4-13.8 s each) and A1/T1 profiled. Nested walks in `translator_envelopes` / `check_translator_envelope_gap` (`rules/error_handling.py`) scale with nesting depth, not corpus size, and the check is 5.1% of the sweep.
- Hits: No hits

#### P2 (sampled): Blocking I/O in hot paths
- Mode: full
- Inspected: all tracked `.py` and `.sh` files for reads/writes in loops, handlers and callbacks; the only callback is the Stop hook (`claude/hooks/auditme-stop.sh`), which runs `git` once and `changed.py` once per turn end (0.4 s with no changes); file reads in the checker go through `core.cached_source`, read once per file per run.
- Hits: No hits

#### P3 (sampled): Repeated expensive computation per request
- Mode: full
- Inspected: shared derivations across the sweep (`corpus_index`, `cached_source`, `cached_roots`, `translator_envelopes` once per root) and within each Phase B lister. `list_a1_candidates` (`phaseb/architecture.py:623`) recomputes `translator_envelopes` per root after `capture_hits` already ran it inside `check_translator_envelope_gap`: measured 1.22 s repeat on the 766-file project against a 13.8 s A1 run (8.9%), under a tenth, so not a hit. Re-listing candidates in separate `plan`/`merge`/`report` invocations is one derivation per process.
- Hits: No hits

#### Sec1 (sampled): Secrets in source
- Mode: full
- Inspected: every tracked Python and shell file, `pyproject.toml`, `.pre-commit-config.yaml`, `.pre-commit-hooks.yaml`, `.github/workflows/*.yml` and the setup templates, searched for key, password, secret and token words and for key-shaped literals (`ghp_`, `sk-`, `AKIA`, private-key headers). The only credential references are `${{ secrets.GITHUB_TOKEN }}` in `.github/workflows/docs.yml` and `${{ secrets.AUDITOR_DEPLOY_KEY }}` in the setup templates, both read from the CI secret store at run time.
- Hits: No hits

#### Sec2 (sampled): Input validation at system boundaries
- Mode: full
- Inspected: argument parsing in `claude/skills/auditme/checks/audit.py`, `changed.py` and `phaseb.py` (every subcommand), `bin/check-foreign-names.sh`, `bin/install-claude.sh` and `claude/hooks/auditme-stop.sh`. Ran each entry point with a missing path, a file where a directory is expected and a directory where a file is expected: `audit.py` (scope, `--extra-root`, `--package`), `changed.py` (repo_root, `--base`), `phaseb.py candidates|plan|check|merge|report|dismiss` (root, dir, `--out`, `--question`, `--depth`) all reject the bad input with a message naming it and a non-zero exit. `check-foreign-names.sh` was run with the list (`$AUDITOR_FOREIGN_NAMES`) missing, unreadable and a directory, and with file arguments missing and a directory. `install-claude.sh` takes no path of its own (arguments pass through to the pinned installer), and the Stop hook takes none.
- Hits:
  - `bin/check-foreign-names.sh:26` - a list path that names a directory is taken for "no list": the hook prints "no list at <dir>; nothing checked" and exits 0, so nothing is checked and the commit passes. Reproduced with `AUDITOR_FOREIGN_NAMES=<a directory> bin/check-foreign-names.sh hit.txt` (exit 0, where an unreadable list file exits 2). The guard meant to catch a non-file list (`[ ! -f "$list" ]` at line 31) can never be true, because line 26 has already exited for every path that is not a regular file.

#### Sec3 (sampled): Command injection
- Mode: full
- Inspected: every `subprocess` call in the shipped checker (`changed.py` `run_git` and the sweep run, `auditme/rules/project_hygiene.py` ruff and `uv lock --check` runs, `auditme/phaseb/docrefs.py` `git ls-files`): each passes an argument list with no `shell=True`; no `os.system` or `os.popen` anywhere. Shell scripts: every expansion in `bin/check-foreign-names.sh`, `bin/install-claude.sh` and `claude/hooks/auditme-stop.sh` is quoted, with no `eval`, `bash -c` or `sh -c`; `changed.py --base` reaches git after `--end-of-options`.
- Hits: No hits

#### Sec4 (sampled): Path traversal
- Mode: full
- Inspected: every join of a caller-supplied value onto a project path: `audit.py` `--extra-root` (checked with `auditme.core.path_inside`; `../../..` refused) and `--package` (refused unless a name directly under `src/`; `../../outside` refused), `[tool.auditme] roots` in `auditme/core.py` (checked with `path_inside`), `phaseb.py` ledger path (question checked against the registry before it names a file), `changed.py` joins of paths git reports.
- Hits: No hits

#### Sec5 (sampled): PII in logs
- Mode: full
- Inspected: every Python and shell file for logging calls. The shipped code imports no logging library; `loguru` and `logger` appear only in rule text and in test fixture strings. Output goes to stdout and stderr as audit hits and error messages naming paths.
- Hits: No hits

#### T3 (sampled): Integration vs unit balance
- Mode: full
- Inspected: the orchestrators and their tests: `audit.py` (`tests/test_driver.py`), `changed.py` (`tests/test_changed.py`, one case running the real `audit.py`), `phaseb.py` (`tests/phaseb/test_cli.py`, which runs the script as a subprocess and round-trips plan, check and merge for every registered question), `claude/hooks/auditme-stop.sh` (`tests/test_stop_hook.py`, run as a subprocess in a git repository), `bin/install-claude.sh` (`tests/test_install_claude.py`, including the real installer) and `bin/check-foreign-names.sh` (`tests/test_check_foreign_names.py`).
- Hits: No hits

#### D1 (sampled): Declared in pyproject
- Mode: full
- Inspected: every top-level import in tracked Python files against `pyproject.toml`. Third-party modules imported in real code: `pytest` and `hypothesis` (tests only), both in the `dev` group. `loguru`, `orjson`, `requests`, `gitutils` and the `pkg`/`probe` modules occur only inside fixture source strings written to temporary projects; everything else is stdlib or the project's own `auditme`, `audit`, `changed`, `phaseb` and `conftest`.
- Hits: No hits

#### D2 (sampled): Unused declarations
- Mode: full
- Inspected: each declared dependency in `pyproject.toml`: `hypothesis` and `pytest` are imported by tests; `ruff` is run by the checker as a subprocess (`auditme/rules/project_hygiene.py`) and put on PATH for it in `.github/workflows/ci.yml`; `mkdocs` is run in `.github/workflows/docs.yml` (`uv run mkdocs build`, `mkdocs gh-deploy`); `mkdocs-material` is the theme `mkdocs.yml` names (`theme: name: material`).
- Hits: No hits

#### D3 (sampled): Lockfile coherence
- Mode: full
- Inspected: `/tmp/audit-auditor.jsonl` for a lockfile-drift hit (none; the only `uv lock` entry is an accepted `subprocess-without-memoisation` hit at `auditme/rules/project_hygiene.py:104`), and `uv lock --check` (resolves without change).
- Hits: No hits

#### Doc3 (sampled): README.md and AGENTS.md consistent
- Mode: full
- Inspected: `README.md` (all), `AGENTS.md` (all); cross-checked their shared claims against `.pre-commit-hooks.yaml`, `.pre-commit-config.yaml`, `bin/install-claude.sh`, `claude/` layout, and the repository descriptions in `docs/index.md`, `docs/concepts.md`, `docs/setup.md` and `docs/reference/cli.md`. Shared statements compared: what the repository holds (checker, `auditme-changed`/`auditme-all` hooks, `no-project-names` hook, Stop hook, `/auditme-project-setup` skill, `claude/rules/auditme/`), what `bin/install-claude.sh` installs (skills, rules and Stop hook into `~/.claude`, Stop hook registered), where the other shared rules come from (agents repository), and the test command (identical in `README.md:19` and `AGENTS.md:22`).
- Hits: No hits

#### Spec review
- `agents/specs/auditme-false-positives/spec.md` - no gap (Settings omitted; allowed when nothing is configurable)
- `agents/specs/listed-phase-b-architecture-questions/spec.md` - no gap
- `agents/specs/listed-phase-b-documentation-questions/spec.md` - no gap
- `agents/specs/listed-phase-b-test-questions/spec.md` - no gap
- `agents/specs/project-setup/spec.md` - no gap
- `agents/specs/raises-section-resolution/spec.md` - no gap
- `agents/specs/repeatable-phase-b/spec.md` - no gap
- `agents/specs/index.md` - every spec directory has an entry; every link resolves

## Prior findings re-verified

Review-12's F2-F4 shipped in its task list (`tasks-11.md`) and are confirmed in the code. F1 shipped, but its new paragraph is incomplete (F4 here). Earlier dismissals stand. No task list under `agents/tasks/audit-reviews/` has an incomplete task.

## Decisions

None this review.

## Answers

Decided by Claude on 2026-11-22: the operator delegated the loop that day ("keep doing whole-tree audits and fixes in a loop until there are no findings and do not stop waiting for me"), so every item takes its recommendation.

| Item | Answer |
|---|---|
| F1-F5 | Fix |
