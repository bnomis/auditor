# Audit Review 4

**Date:** 2026-11-22
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`). The sampled questions ran on the files changed since review-3.
**Commit:** 0a015804c07b4785e3f07089726517ca89f6361a
**Script output:** /tmp/audit-auditor.jsonl (46 hits, 46 accepted, 0 unaccepted)
**Script version:** c38e0148741ae2f2371b2bd7c07640fd5ee7efab46f6d93e72c3b9c96df33496
**Convergence note:** the checker changed after review-3, in three ways:
- **Review-3's task list:** a shared parse for every check, the `OSError` handling in `changed.py`, and `batches` dropped from `phaseb`'s `__all__`.
- **The `ruff format` fix:** that half of the `ruff` rule now reads ruff's JSON output. It finds no unformatted file in this repository.
- **The default-verdict ruling (2026-11-22, G1):** every brief went up one version, so every listed candidate was judged again, once. G1 also settles every case a brief does not cover as not a finding.

Under G1, reviewers named the cases their briefs do not settle and judged each one not a finding. None of those cases is a finding in this review (see D1).

**Review page:** https://claude.ai/artifact/DY3GgWfi9RRbcsets9gWfn

## What is being reviewed and how

This is the checker repository's fourth audit of its own code. It ran the mechanical sweep, every Phase B question in every category, and the spec review. The sweep is clean.

Phase B found ten groups:

- **Real defects:** two code defects in tools that guard a commit. The `no-project-names` hook passes when its list of names cannot be read (F7). `changed.py`'s `--base` guard can be got past (F6).
- **One review-3 fix moved a finding:** dropping `batches` from `__all__` (F2) turned review-3's S4 finding into an A17 one.
- **Stale docs:** documentation that review-3's own task list left stale.

For each group, choose Fix, which makes it a task, or Dismiss, with your reason. Then answer the decisions. Each answer is recorded in [Answers](#answers).

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 46 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 980 judged (A1 30, A4 49, A11 3, A17 2, A19 1, T1 275, T2 23, Doc1 4, Doc2 3, Doc4 438, Doc5 152) |
| `phaseb.py check` on every listed question | pass, no retries |
| Every sampled question returned a hit list or "no hits" | pass |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| Prior findings to re-verify | none open: review-3's task list (`agents/tasks/audit-reviews/tasks-3.md`) shipped every finding, and F1 was dismissed |

## Summary

The sweep reports 46 hits, and markers accept every one.

| Source | Open findings |
|---|---|
| Listed questions | 12 candidates: A1 1, A17 1, Doc4 2, Doc5 8 |
| Sampled questions | A5 1, A9 1, A14 1, P3 1, Sec3 1 |
| Spec review | 3 gaps |

These questions flag nothing: A4, A11, A19, T1, T2, Doc1 and Doc2.

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits. Every hit is accepted by an inline marker; the full list is in `/tmp/audit-auditor.jsonl`.

## Phase B findings (consolidated)

Each group lists every site. The listed questions' verdicts are in `agents/audit-reviews/ledger/<Q>.jsonl`.

### F1. `cached_source` is flagged a fourth time (A1)

- **Category:** A. **Question:** A1 (listed). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/core.py`, `cached_source`, `path.read_text`.
- **Description:** this site was dismissed as by design on review-2's page and again on review-3's, under review-1's D2, which reports an unreadable file as a hit. Each A1 brief bump judges it again, and the dismissal does not carry across the bump. See D2.
- **Recommendation:** dismiss again, by design.

### F2. `phaseb.py` reads `auditme.phaseb.batches`, which the package's `__all__` leaves out (A17)

- **Category:** A. **Question:** A17 (listed). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/phaseb.py` reads `auditme.phaseb.batches`. It calls `plan_batches`, `write_plan`, `read_plan`, `read_run_check` and `read_run_verdicts`. The verdict is on `claude/skills/auditme/checks/auditme/phaseb/__init__.py`.
- **Description:** review-3's Task 4 took `batches` out of the package's `__all__` to satisfy S4's relative-import rule. That turned the script's import into a bypass under A17's 2026-11-22 ruling.
- **Recommendation:** put `batches` back in `__all__` through the relative form S4 allows (`from . import batches`). That satisfies both rules, since neither then fires.

### F3. A second copy of the root modes in the per-run cache (A5)

- **Category:** A. **Question:** A5 (sampled). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/core.py:759` (`cached_roots`), against the global `ROOT_MODULES` that `core.py:222`, `core.py:230` and `imports_and_surfaces.py:129` read.
- **Description:** on a cache hit, `cached_roots` does not reset `ROOT_MODULES`. So after `audit_roots` has run for another scope, the two copies disagree, and nothing says which one wins. Within one driver run they agree. The clash needs two scopes in one process, as the tests have.
- **Recommendation:** keep one source. Either `cached_roots` sets `ROOT_MODULES` on a hit too, or the readers take the mode from the cache.

### F4. `resolve_name` reads a whole file to count its lines (A9)

- **Category:** A. **Question:** A9 (sampled). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:380` (`resolve_name`), through `read_path_targets` and `file_target` (`:312`, `read_bytes()`).
- **Recommendation:** rename the readers after what they do, or give `file_target` the line count from a cache, so the resolver stays a query.

### F5. Repeated work in `docrefs` (A14, P3)

- **Category:** P. **Questions:** A14, P3 (sampled). **Severity:** low.
- **Locations:**
  - `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:187`: one `CorpusIndex.build` resolves the roots and lists the corpus several times, through `audit_roots`, `corpus_definitions` and `corpus_py_files`. Measured on this repository on 2026-11-22: `declared_roots` ran 4 times and `corpus_py_files` 3 times.
  - `docrefs.py:360`: `resolve_setting` reruns `index.settings_classes()`, a loop that runs until nothing changes, for every unresolved token, although the result depends only on the index.
- **Recommendation:** take the roots and file list from the per-run cache, and compute the settings classes once per index.

### F6. `changed.py`'s `--base` guard can be got past (Sec3)

- **Category:** Sec. **Question:** Sec3 (sampled). **Severity:** medium.
- **Location:** `claude/skills/auditme/checks/changed.py:191` (`option_value_is_flag`), which feeds `changed_files` (`:105`).
- **Description:** the guard misses argparse abbreviations (`--bas=-x`). It also checks only the first `--base`, while argparse keeps the last. Either way, a value starting with `-` reaches `git diff` as an option. The reviewer reproduced both cases, and showed `git diff --output=<path>` writing a file. The tool is a local command line, so the impact is low, but the guard exists to stop exactly this.
- **Recommendation:** check the value argparse parsed, not the raw arguments: refuse a `--base` that starts with `-`. Also pass `--end-of-options`, or put the base after `--`, in the `git diff` call. Add tests for the abbreviation and for a repeated `--base`.

### F7. The `no-project-names` hook passes when its list cannot be read (Doc5)

- **Category:** Sec. **Question:** Doc5 (listed). **Severity:** medium.
- **Location:** `bin/check-foreign-names.sh:31-36`, against `docs/reference/cli.md:83`.
- **Description:** when the list file exists but cannot be read, `grep ... || true` leaves the pattern list empty, and line 36 exits 0 with nothing checked. The case was checked against the code on 2026-11-22. A missing list prints a notice; an unreadable one prints only grep's own error, and the hook passes.
- **Recommendation:** exit 2 with a message when the list exists but cannot be read, add a test, and update the exit table.

### F8. Two spec statements that no longer match the code (Doc4)

- **Category:** Doc. **Question:** Doc4 (listed). **Severity:** low.
- **Locations:** `agents/specs/project-setup/spec.md`:
  - `:356`: it says the spec-drift check is not in `PROJECT_CHECKS`, which both `registry.py:85` and line 351 contradict;
  - `:598`: the `new` step runs `pre-commit install`, which installs no pre-push hook. `SKILL.md:72` installs both types.
- **Recommendation:** correct both.

### F9. User docs that no longer match the code (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed). **Severity:** medium.
- **Locations:**
  - `docs/concepts.md:25`: the commit hook's failures leave out a failing git call and an unresolvable repository root.
  - `docs/guide/checker.md:70`: the exit-1 list leaves out "cannot resolve the repository root", which review-3's Task 1 added.
  - `docs/reference/cli.md:52`: the installer's exit-1 row leaves out a `settings.json` key on the edit path that is not an object, and a `hooks.Stop` that is not a list. The reviewer judged this against the pinned `install-in-claude` commit `fa68deb`.
  - `docs/reference/skills.md`:
    - `:33`: a sampled question runs on the whole tree every third audit and on any audit with no previous `**Commit:**`;
    - `:36`: the "Writes" list leaves out the Phase B ledger;
    - `:73`: the "Stops for" list leaves out three stops: a failing `git ls-remote`, overwriting an existing file, and removing a project-local hook.
  - `docs/setup.md`:
    - `:22`: the project-level checks include `spec-api-signature-drift`;
    - `:275`: outside a git repository the Stop hook exits 0 itself, so that is not a case of `changed.py` failing.
- **Recommendation:** correct each, and add any exit-code change from F6 and F7.

### F10. Spec cross-references written as paths, not links (spec review)

- **Category:** Doc. **Question:** spec review. **Severity:** low.
- **Locations:** the 2026-11-22 amendments cite `agents/specs/repeatable-phase-b/spec.md` as a code-formatted path:
  - `agents/specs/listed-phase-b-architecture-questions/spec.md:59`;
  - `agents/specs/listed-phase-b-documentation-questions/spec.md:242`;
  - `agents/specs/listed-phase-b-test-questions/spec.md:259`.
- **Recommendation:** make each a relative markdown link (`[Repeatable Phase B](../repeatable-phase-b/spec.md)`).

## Phase B per-question results

Listed questions: each verdict is in `agents/audit-reviews/ledger/<Q>.jsonl`; `phaseb.py report . --question <Q>` prints the open ones. Sampled questions: changed files since `6b51a21` (review-3's commit).

### A1 (listed)

- 30 candidates judged, none left out; 1 open finding (F1).

### A4 (listed)

- 49 candidates judged, none left out; 0 open findings.

### A11 (listed)

- 3 candidates judged, none left out; 0 open findings.

### A17 (listed)

- 2 candidates judged, none left out; 1 open finding (F2).

### A19 (listed)

- 1 candidates judged, none left out; 0 open findings.

### T1 (listed)

- 275 candidates judged, none left out; 0 open findings.

### T2 (listed)

- 23 candidates judged, none left out; 0 open findings.

### Doc1 (listed)

- 4 candidates judged, none left out; 0 open findings.

### Doc2 (listed)

- 3 candidates judged, none left out; 0 open findings.

### Doc4 (listed)

- 438 candidates judged, none left out; 2 open findings (F8).

### Doc5 (listed)

- 152 candidates judged, none left out; 8 open findings (F7, F9).

### A2 (sampled): Except tuple coverage
- Mode: changed files since 6b51a21
- Inspected: every `try/except` in the changed non-test files: `auditme/core.py` (stat at 101 and 120, `read_text` at 130, `tomllib.loads` at 315), `auditme/phaseb/docrefs.py` (`read_text` at 86 with `OSError, UnicodeDecodeError`; `git ls-files` at 297; `read_bytes` at 311 with `OSError`, no decode), `auditme/rules/project_hygiene.py` (ruff and uv subprocesses at 42, 96, 216; `json.loads` at 58 with `json.JSONDecodeError`), `changed.py` (git at 54, sweep at 134, `json.loads` at 154 with `json.JSONDecodeError`, repository root at 226). No `contextmanager` or translating-decorator envelope in scope.
- Hits: No hits

### A3 (sampled): Domain-error layering
- Mode: changed files since 6b51a21
- Inspected: every `raise` in the changed non-test files. `core.py` raises `RootsError`; `docrefs.py` raises `PhaseBError`; `changed.py` raises `ChangedError` and `SystemExit(main())` at the entry point. The rules modules raise nothing (the `raise` matches there are docstring text).
- Hits: No hits

### A5 (sampled): Two sources of truth
- Mode: changed files since 6b51a21
- Inspected: module-level state and option/default pairs in the changed files: `core.py` `ROOT_MODULES`, `DECLARATION_IGNORED`, `INDEX_CACHE` and the new `cached_roots`; `changed.py` `--base` / `read_base_ref` and `repo_root` / `git rev-parse --show-toplevel` (precedence explicit in `args.base or ...` and documented in the `--base` help and module docstring).
- Hits:
  - `claude/skills/auditme/checks/auditme/core.py:759` - `cached_roots` stores a second copy of the root-mode mapping in `INDEX_CACHE` beside the global `ROOT_MODULES`, which `py_files` (core.py:222), core.py:230 and `imports_and_surfaces.py:129` still read; a cache hit does not rebind the global, so after an `audit_roots` call for another scope the two disagree, and no documented rule says which one a reader should trust.

### A6 (sampled): Stage method dual-path
- Mode: changed files since 6b51a21
- Inspected: every class in the changed files (`DocSection`, `DocTarget`, `ClassInfo`, `CorpusIndex`, `IndexEntries` in `docrefs.py`; `IfChain` in `state_and_effects.py`; the error classes; test `Result` / `LockResult` stubs). None is a pipeline-stage class; `IndexEntries` methods mutate `self` and return `None` (`class_info` returns a `ClassInfo` and records methods into `self.sites`, a different field).
- Hits: No hits

### A7 (sampled): Constructor purity
- Mode: changed files since 6b51a21
- Inspected: every `__init__` in scope - only the test stubs `Result.__init__` (`test_project_hygiene.py:141`) and `LockResult.__init__` (`test_project_hygiene.py:203`), which assign attributes only. Dataclass-generated constructors have no `__post_init__` in scope.
- Hits: No hits

### A8 (sampled): Late dataclass mutation
- Mode: changed files since 6b51a21
- Inspected: every dataclass construction in scope (`IndexEntries()` at `docrefs.py:185`, `ClassInfo(...)` at `docrefs.py:263`, frozen `DocTarget`/`CorpusIndex`/`IfChain`) and every non-`self` attribute assignment (`x.field = ...`) in the changed files, tests included: none found. `IndexEntries` is filled through its own methods' dict inserts, not by field reassignment.
- Hits: No hits

### A9 (sampled): Pure-named function side effects
- Mode: changed files since 6b51a21
- Inspected: every `def` with a pure prefix in the scoped files (grep over `get_|resolve_|find_|compute_|build_|load_|parse_|is_|has_|validate_|count_|check_|allocate_`), bodies read for each non-`check_` one (`core.py` `is_test_relpath`, `resolve_call`, `is_dunder_all_assignment`, `is_main_guard`; `docrefs.py` `is_path_shaped`, `resolve_dotted/bare/member/setting/option/name`; `duplication.py` `is_pytest_param`, nested `resolve_helper`; `error_handling.py` `is_broad_handler`, `is_categorical_class_name_expr`, `is_tomllib_call`, `is_toml_source`, nested `is_domain`, `is_bound`; `project_hygiene.py` `parse_spec_def`; `style_and_naming.py` `is_stdlib_public_access_only`, `is_fixed_length_tuple`, `is_leading_underscore`; `changed.py` `parse_args`; test helpers `parse_or_none`, `parse_call`). Every `check_*` in the rules files is a member of `CHECKS` in `checks/auditme/registry.py` (checked by name), so none is read as pure-named. No sweep `pure-name-has-side-effect` hit exists for these files.
- Hits: `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:380` - `resolve_name` calls `read_path_targets`, which for a tracked file calls `file_target` (`:312`), reading the whole file (`read_bytes()`) to count its lines; a `resolve_` function that performs file I/O.

### A10 (sampled): Predicate semantics
- Mode: changed files since 6b51a21
- Inspected: every `is_`/`has_`/`should_` function in scope (no `has_` or `should_` function exists in these files): the `is_*` functions listed under A9 plus nested `is_domain` and `is_bound` in `error_handling.py`; each body compared against its name and docstring.
- Hits: No hits

### A12 (sampled): assert misuse
- Mode: changed files since 6b51a21
- Inspected: grep for `assert` statements in the non-test files in scope.
- Hits: No hits (no `assert` statement outside test files)

### A13 (sampled): Same value to multiple structural slots
- Mode: changed files since 6b51a21
- Inspected: AST scan of every call in the scoped files for a non-literal argument passed to two or more slots of a class constructor; the one candidate read by hand.
- Hits: No hits (`docrefs.py:279` `DocTarget(kind, rel, rel, 1, last_line)` passes `rel` as both id and path, but inside the explicit factory `path_target`, whose docstring says a path target's identity is its path)

### A14 (sampled): Repeated computation per request
- Mode: changed files since 6b51a21
- Inspected: `changed.py` `main` flow (root, base ref, changed files and sweep each resolved once); `core.py` root and corpus helpers (`declared_roots`, `audit_roots`, `extra_roots`, `corpus_py_files`, `cached_roots`, `corpus_index`); their callers in `docrefs.py`. Counted calls in one `CorpusIndex.build` on this repository by wrapping `declared_roots` and `corpus_py_files`: 4 and 3 calls respectively.
- Hits: `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:187` - `CorpusIndex.build` resolves the project's roots and corpus file list repeatedly in one build: `audit_roots` (`:181`), `corpus_definitions` (`:183`, via `corpus_index` and `index_definitions`) and this direct `corpus_py_files` call each re-run `declared_roots` (reading `pyproject.toml`) and re-walk the tree, instead of reusing the `('corpus-files', scope, src_root)` list `corpus_index` already caches.

### A15 (sampled): Duplicate constructor / serialisation logic
- Mode: changed files since 6b51a21
- Inspected: every class defined in the non-test scoped files and every call site constructing it (AST scan): `ChangedError`, `RootsError` (single message argument), `ClassInfo`, `DocSection`, `IfChain`, `IndexEntries` (one site each), `DocTarget` (two sites, each in its own factory, `node_target` and `path_target`, with different field values).
- Hits: No hits

### A16 (sampled): CLI entry envelope
- Mode: changed files since 6b51a21
- Inspected: scope list for `cli/*.py` files; none is in scope (`changed.py` is not under `cli/` and has no `run_*` function).
- Hits: No hits

### A18 (sampled): Hot-path setup
- Mode: changed files since 6b51a21
- Inspected: every file in changed-code.txt, searched for `def on_step|on_log|on_evaluate|on_batch_*`; none defines a callback method.
- Hits: No hits

### A20 (sampled): Mutable module-level singleton
- Mode: changed files since 6b51a21
- Inspected: an AST pass over every module-level assignment in the changed files whose value is a `dict`/`list`/`set` literal, comprehension or bare constructor call; for each name, grep across every `[tool.auditme]` root (`claude/skills/auditme/checks/auditme`, `claude/skills/auditme/checks`, `claude/skills/auditme/tests`, `claude/skills/auditme-project-setup/tests`, `tests`) plus `bin/` for `from <module> import <name>`, `<module>.<name>` and `sys.modules[...]` reads. `EMITTED` and `UNREADABLE` (`core.py:29`, `core.py:35`) belong to the sweep (`mutable-module-level-exported`, accepted). `SOURCE_CACHE`, `INDEX_CACHE`, `STDLIB`, `DISK_IO_NAMES`, `MUTABLE_VALUE_SHAPES`, `MUTABLE_CONSTRUCTORS`, `STRFTIME_TOKENS`, `PARAMETRIC_NONBUILTIN_GENERICS`, `TYPING_DEPRECATED_ALIASES`, `RULE_HELP` and the test-module constants (`DOC_BRIEF_VERSIONS`, `DOC_BRIEF_PHRASES`, `DEPTH_COMMANDS`, `EVERY_QUESTION_FILES`, `TWO_MARKERS`, `LOCK_PROJECT`, `CODE_ONLY_FIXTURE_TEXT`) are named only in their own file. No `__all__` list is read by name from another module (the one `module.__all__` text is a fixture string in `tests/test_annotated_all.py`).
- Hits: No hits

### A21 (sampled): Lazy init race
- Mode: changed files since 6b51a21
- Inspected: every `is None:` test and `global` statement in the changed files; module-level caches `SOURCE_CACHE`/`INDEX_CACHE` (`core.py:74`, `core.py:79`) and `global ROOT_MODULES` in `audit_roots` (`core.py:420`); searched the checker for `threading`, `concurrent.futures`, `multiprocessing` and `asyncio` use. No `if X is None: X = ...` lazy initialisation at module scope, and no code path in the checker runs concurrently.
- Hits: No hits

### A22 (sampled): Fall-through after partial handling
- Mode: changed files since 6b51a21
- Inspected: an AST pass over the non-test changed files for `if` branches containing a `try` that do not end in `return`/`raise`/`continue`/`break` (one: `core.py:136`, which only sets `tree = None` on `SyntaxError`); read the retry in `check_lockfile` (`project_hygiene.py:96-106`, a deliberate, documented second run without user config, not a translated error retried) and the error paths of `changed.py:main`.
- Hits: No hits

### A23 (sampled): Discarded multi-return
- Mode: changed files since 6b51a21
- Inspected: every function in the changed files annotated to return a tuple (`cached_source`, `dotted_read`, `cached_roots`, `surface_files`, `privacy`, `read_package_layering`, `ruff_executable`, `ruff_hook_pin`, `parse_spec_def`, `mutable_value_shape`, `module_level_binding`, `wrapped_literal`, `ruff_dunder_all_key`) and each call site in the changed files. Calls either unpack every component or name the discard (`ruff, _ = ruff_executable(scope)`). The indexed reads `cached_source(path)[0]`/`[1]` (`core.py:151`, `core.py:160`) and `privacy(...)[0]` (`core.py:866`) are single-component accessors whose docstrings document no dependency of the kept component on the dropped one. `subprocess.CompletedProcess` reads in `changed.py` and `project_hygiene.py` drop nothing documented.
- Hits: No hits

### A24 (sampled): Identity of subprocess / shell-out calls
- Mode: changed files since 6b51a21
- Inspected: every `subprocess` call in the non-test changed files. `project_hygiene.py:44`, `:98`, `:219` belong to the sweep (`subprocess-without-memoisation`, accepted). `docrefs.py:299` (`tracked_files`) runs once per `CorpusIndex.build`, which each `phaseb.py` request calls once through its single question's lister. `changed.py:55` (`run_git`) runs with different arguments each call (`rev-parse` for each base candidate, two `diff` calls), and `changed.py:135` runs the sweep once per invocation.
- Hits: No hits

### A25 (sampled): Shallow immutable wrapper
- Mode: changed files since 6b51a21
- Inspected: an AST pass over every module-level `frozenset(...)`, `tuple(...)`, tuple literal and `types.MappingProxyType(...)` in the changed files, checking each member of the wrapped literal. Every member is a string constant, except `MEMBER_CONTAINERS` (`state_and_effects.py:804`, members are `ast` node classes, not containers) and `ROOT_MODULES` (`core.py:283`, an empty mapping, rebuilt in `audit_roots` from `Path` keys to `str` modes).
- Hits: No hits

### S1 (sampled): Type annotations on every signature
- Mode: changed files since 6b51a21
- Inspected: every `def` / `async def` in each Python file listed in `review-4/changed-code.txt`, by an AST walk of parameter (positional-only, positional, keyword-only, `*args`, `**kwargs`; `self`/`cls` excepted) and return annotations; non-test files enumerated, `tests/` files counted per the locked scope rule
- Hits: No hits in non-test source (`core.py`, `phaseb/__init__.py`, `phaseb/docrefs.py`, `rules/duplication.py`, `rules/error_handling.py`, `rules/imports_and_surfaces.py`, `rules/project_hygiene.py`, `rules/state_and_effects.py`, `rules/style_and_naming.py`, `changed.py`: every parameter and return annotated)
- Tests (count only): 70 missing parameter annotations, 0 missing return annotations; 1 module affected (`claude/skills/auditme/tests/test_changed.py`, all of them pytest fixture parameters such as `repo`, `stub_sweep`, `capsys`, `tmp_path`, `monkeypatch`); 5 modules fully annotated (`tests/phaseb/test_briefs.py`, `tests/phaseb/test_cli.py`, `tests/test_core.py`, `tests/test_project_hygiene.py`, `tests/test_style_and_naming.py`)

### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake
- Mode: changed files since 6b51a21
- Inspected: every class, function, argument and assignment target in the scoped files (AST walk), module-level names checked against UPPER_SNAKE; leading-underscore names searched
- Hits: No hits. The only PascalCase module-level assignments are type aliases (`rules/error_handling.py:2331` `HandlerLevel`, `tests/phaseb/test_cli.py:20` `Project`, `tests/test_core.py:22` `Builder`, `tests/test_project_hygiene.py:15-16,304` `Builder`/`Runner`/`StubRuff`, `tests/test_style_and_naming.py:12-13` `Builder`/`Runner`), which follow the PascalCase-for-types convention used across the tree; no leading-underscore names

### S3 (sampled): TYPE_CHECKING block placement
- Mode: changed files since 6b51a21
- Inspected: every `if typing.TYPE_CHECKING:` block in the scoped files and the statements before it
- Hits: No hits. Every block uses `import typing` / `if typing.TYPE_CHECKING:` at top level directly after the imports (`rules/duplication.py:10`, `rules/error_handling.py:12`, `rules/imports_and_surfaces.py:11`, `rules/state_and_effects.py:11`, `rules/style_and_naming.py:10`, `changed.py:31`, `tests/test_changed.py:17`, `tests/test_core.py:19`); in `changed.py` it follows the `sys.path` set-up and the E402 imports that need it, still directly after the last import. `core.py:208` is a string literal inside a check, not a block

### S4 (sampled): Project-specific rule files
- Mode: changed files since 6b51a21
- Inspected: `claude/rules/auditme/coding-standards.md`, `claude/rules/auditme/imports.md`, `~/.claude/rules/python/argparse.md`; checked the scoped files for `from X import Y` outside `__init__.py`, relative-only imports in `__init__.py`, `as` imports, `from __future__`, stdlib `logging`, `%`/`.format()` formatting, leading underscores, clean `__init__.py` (no definitions, `__all__` present and sorted), argparse use and its trailing-comma style
- Hits: No hits. `phaseb/__init__.py` holds only relative re-exports and a sorted `__all__`; `changed.py` uses argparse as a stdlib-only checker (allowed by `argparse.md`) with one argument per line and trailing commas; `tests/phaseb/test_cli.py` imports argparse only for `argparse.ArgumentTypeError` in `pytest.raises`; the `print` calls in `changed.py` and `core.py:60` are the checker's machine-read stdout, not logging

### P1 (sampled): O(n^2) on real-size inputs
- Mode: changed files since 6b51a21
- Inspected: every loop in the non-test changed files' diff since 6b51a21 (core.py cached_roots/surface_files, docrefs.py CorpusIndex.build, settings_classes, resolve_setting, IndexEntries; changed.py in_scope/changed_files); test files skimmed for loops over project data
- Hits: No hits (the per-token recomputation of the settings-class fixed point is reported once, under P3)

### P2 (sampled): Blocking I/O in hot paths
- Mode: changed files since 6b51a21
- Inspected: every subprocess.run, read_text and open in the changed files (changed.py run_git/sweep, project_hygiene.py check_ruff/uv lock/ruff --version, docrefs.py git ls-files); the package is a batch CLI with no request handlers, training loops or callbacks
- Hits: No hits

### P3 (sampled): Repeated expensive computation per request
- Mode: changed files since 6b51a21
- Inspected: docrefs.py resolve_name step chain and its caller candidates.py doc_candidates (per-token loop); core.py cached_roots (new memoisation of audit_roots); changed.py sweep (once per run)
- Hits: `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:360` - resolve_setting calls index.settings_classes() (docrefs.py:201, a fixed-point loop over every corpus class, added since 6b51a21) once per backticked token that the earlier steps leave unresolved; the result depends only on the index, which is built once per lister call, so it is recomputed for every such token in every document section

### Sec1 (sampled): Secrets in source
- Mode: changed files since 6b51a21
- Inspected: every changed file, searched for key/token/password assignments, provider key prefixes and PEM headers; matches at state_and_effects.py:73/75/76/345 and error_handling.py:969 read and found to be rule names and docstrings
- Hits: No hits

### Sec2 (sampled): Input validation at system boundaries
- Mode: changed files since 6b51a21
- Inspected: changed.py parse_args/option_value_is_flag/main (the only CLI in scope), phaseb/docrefs.py path tokens read from documents
- Hits: No hits beyond the `--base` guard gap, reported once under Sec3 where its harm lies

### Sec3 (sampled): Command injection
- Mode: changed files since 6b51a21
- Inspected: every subprocess.run in the changed files: changed.py:55 (run_git) and :135 (sweep), project_hygiene.py:44/98/106/219, docrefs.py:299; arguments are lists, no shell=True
- Hits: `claude/skills/auditme/checks/changed.py:191` - option_value_is_flag refuses a `--base` value starting with `-` only for the exact spellings `--base X` and `--base=X`, and only at the first occurrence, while argparse accepts abbreviations and the last occurrence; `--bas=-x` and `--base main --base=-x` both pass the guard with base `-x` (checked by calling option_value_is_flag and parse_args), and changed_files (changed.py:105) then passes f'{base}...HEAD' to `git diff` as an option - e.g. `--output=<path>...HEAD` makes git write a file at that path (confirmed with git diff in the scratchpad). Local CLI, argv under the caller's control, so low impact

### Sec4 (sampled): Path traversal
- Mode: changed files since 6b51a21
- Inspected: docrefs.py read_path_targets (normpath, refuses `..` and `.`, matches only tracked files from git ls-files), docrefs.py:193 is_relative_to root selection, changed.py repo_root/changed_files (git-reported paths, compared not opened)
- Hits: No hits

### Sec5 (sampled): PII in logs
- Mode: changed files since 6b51a21
- Inspected: every print and logger call in the changed files (core.py:60 emits hit JSON; changed.py prints error messages and hit path:line/rule/variant); no user free-form text is logged
- Hits: No hits

### T3 (sampled): Integration vs unit balance. Pipeline orchestrators have at least one end-to-end test.
- Mode: changed files since 6b51a21
- Inspected: of the orchestrators `claude/skills/auditme/checks/audit.py`, `changed.py` and `phaseb.py`, only `changed.py` changed (with `claude/skills/auditme/tests/test_changed.py`); `test_changed.py` has end-to-end tests running `changed.main` on a real git repository against the real checker (`test_end_to_end_against_the_real_checker`, `test_cross_file_hit_on_an_unchanged_file_fails_when_its_peer_changes`, the `start_script_project` tests)
- Hits: No hits

### D1 (sampled): Declared in pyproject. Every imported third-party module is declared.
- Mode: changed files since 6b51a21
- Inspected: `git diff --name-only 6b51a21..HEAD -- pyproject.toml uv.lock` - neither `pyproject.toml` nor `uv.lock` changed
- Hits: No hits (neither `pyproject.toml` nor `uv.lock` changed since 6b51a21)

### D2 (sampled): Unused declarations. Every declared dependency is imported somewhere, or run as a command (with the run-as-command, host-plugin, type-stub and Jupyter-kernel carve-outs).
- Mode: changed files since 6b51a21
- Inspected: `git diff --name-only 6b51a21..HEAD -- pyproject.toml uv.lock` - neither changed
- Hits: No hits (neither `pyproject.toml` nor `uv.lock` changed since 6b51a21)

### D3 (sampled): Lockfile coherence. Already script-checked; flag if the script's lockfile-drift hit appears.
- Mode: changed files since 6b51a21
- Inspected: `git diff --name-only 6b51a21..HEAD -- pyproject.toml uv.lock` - neither changed; rule names in /tmp/audit-auditor.jsonl - no lockfile-drift hit (the two `uv lock` mentions are accepted `non-alphabetical-literal` and `subprocess-without-memoisation` hits in `project_hygiene.py`)
- Hits: No hits (neither `pyproject.toml` nor `uv.lock` changed since 6b51a21, and the sweep has no lockfile-drift hit)

### Doc3 (sampled): README.md and AGENTS.md consistent.
- Mode: changed files since 6b51a21
- Inspected: `git diff --name-only 6b51a21..HEAD -- README.md AGENTS.md` - neither changed
- Hits: No hits (neither README.md nor AGENTS.md changed since 6b51a21)

### Spec review (changed specs)


Specs changed in `6b51a21..HEAD` under `agents/specs/`, checked against the specdev "Spec template" and "Validation criteria" only. Spec size and the "Module location under src/" criterion are dismissed for this repository (review-1, D6). Every template section is present in each spec; every referenced path either exists, is marked as a fixture, a target-project path, a path in the agents repository or a former path; every relative link and anchor resolves. A spec that is linked at its first mention and later named in plain prose ("the test-questions spec") is not counted as a gap.

## agents/specs/listed-phase-b-architecture-questions/spec.md

- gap: Cross-references to other specs use relative markdown links - Module location, the briefs bullet (line 59) cites "`agents/specs/repeatable-phase-b/spec.md` amendment 1.5" as a code-formatted path, not a link (`../repeatable-phase-b/spec.md`)

## agents/specs/listed-phase-b-documentation-questions/spec.md

- gap: Cross-references to other specs use relative markdown links - Implementation (line 242) cites "`agents/specs/repeatable-phase-b/spec.md` amendment 1.5" as a code-formatted path, not a link (the same path inside the Prerequisite's shell command at line 41 is a command argument, not a cross-reference)

## agents/specs/listed-phase-b-test-questions/spec.md

- gap: Cross-references to other specs use relative markdown links - Implementation (line 259) cites "`agents/specs/repeatable-phase-b/spec.md` amendment 1.5" as a code-formatted path, not a link

## agents/specs/project-setup/spec.md

No gaps

## agents/specs/repeatable-phase-b/spec.md

No gaps

### Coverage (sampled)

The sampled sites (A5, A9, A14, P3, Sec3) are in code changed since review-3: coverage, not drift.

## Prior findings re-verified

Every review-3 finding was resolved by `agents/tasks/audit-reviews/tasks-3.md` (all ten tasks done) or dismissed (F1). No task in `agents/tasks/audit-reviews/` is incomplete. Two statements review-3's Task 9 fixed hold; the stale ones under F9 come from code review-3's own tasks changed (Task 1's new error, Task 6's moved check).

## Decisions

### D1. The cases the reviewers named under the default verdict

- **What is being decided:** whether any of the cases this audit's reviewers judged under G1 should be settled as findings.
- **Background:** under G1 (2026-11-22), a case a brief does not settle is judged not a finding and reported. This audit's reviewers named these:
  - **Doc4:** a "Command-line options only" settings table read as a complete list (two specs); a field comment written for A4 read as covering later questions; the mirrored-test-file mapping, where the definition rule and the fair-reading rule pull apart; an output list that applies only conditionally; the `Union[...]` spelling, and `del` on a parameter, in the T2 rules.
  - **Doc5:** the installer's `.orig` renaming at the pinned commit; a cause of a symptom that could report nothing anyway.

  Each was judged the same way in every batch, so the verdicts already agree.
- **What it affects:** nothing, unless one is settled. Settling one bumps its brief, and the next audit judges that question's candidates again.
- **Options:**
  - **Leave them under the default (recommended):** none of them hides a defect the other findings miss, and leaving them is what G1 is for. The list stays in this review as the record.
  - **Settle them:** file a request, and put each case to a decision as before.

### D2. Keep a dismissal across a brief bump while the code is unchanged

- **What is being decided:** whether to file a checker request so that a dismissal recorded with `phaseb.py dismiss` survives a brief version bump while the candidate's content hash is unchanged.
- **Background:** a ledger verdict is current only while its hash and brief version match. A bump judges the candidate again and drops the dismissal, so `cached_source` has been flagged and dismissed in review-2, review-3 and now review-4 (F1). Every brief went up a version on 2026-11-22.
- **What it affects:** `checks/auditme/phaseb/ledger.py` and `report`. A dismissed candidate whose code has not changed stays dismissed when its brief changes, and is judged again once its code changes.
- **Options:**
  - **File the request (recommended):** the dismissal records the operator's judgement about the code, not about the brief's wording, so it holds until the code changes.
  - **Keep dismissing:** each brief bump brings back every dismissed finding for the operator to dismiss again.

## Answers

Answered on the review page on 2026-11-22. Every item took the recommended option, with no comments.

| Item | Answer |
|---|---|
| F1 | Dismiss (by design, review-1 D2; dismissed in the A1 ledger) |
| F2 | Fix |
| F3 | Fix |
| F4 | Fix |
| F5 | Fix |
| F6 | Fix |
| F7 | Fix |
| F8 | Fix |
| F9 | Fix |
| F10 | Fix |
| D1 | Leave them under the default |
| D2 | File the request |
