# Audit Review 5

**Date:** 2026-11-22
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`); the sampled questions ran on the files changed since review-4
**Commit:** dbb9780ca307a11b2a475ee6c967850c865c67d2
**Script output:** /tmp/audit-auditor.jsonl (46 hits, 46 accepted, 0 unaccepted)
**Script version:** fc14e84b155f4e38e691282d6d45784a5c47fb88adf32f58411ea12bd463bec0
**Convergence note:** this is the first audit with no brief change since the one before it. Review-4's task list and the dismissal fix changed the checker's code, but not a brief or a lister's rules, so only candidates whose content changed were judged: 227 of about 980. Seven listed questions flag nothing. The open findings come from three sources:
- the review-4 fixes themselves;
- a checker defect that keeps two fixed findings open;
- new coverage in one file that changed by two lines.
**Review page:** https://claude.ai/artifact/EqM6JvhCwtK2pVfc8NQjEx

## What is being reviewed and how

This is the checker repository's fifth audit of its own code. The sweep is clean, and the listed questions are nearly so. The review also explains why the loop has not reached zero, and asks three decisions that would let it.

For each finding, choose Fix (it becomes a task) or Dismiss (with your reason), then answer the decisions.

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 46 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 227 judged (A1 6, A4 17, A17 1, T1 102, T2 8, Doc4 72, Doc5 21); A11, A19, Doc1 and Doc2 carried every verdict |
| `phaseb.py check` on every listed question | pass, no retries |
| Every sampled question returned a hit list or "no hits" | pass |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| Prior findings to re-verify | review-4 F1-F10: shipped or dismissed. Two of its doc fixes landed, but their verdicts stay open (F4 below), and one was left undone (F1) |

## Summary

The sweep reports 46 hits, all accepted. Phase B leaves 5 listed verdicts open (Doc4 2, Doc5 3); every other listed question has none. The sampled questions flag A9 2, A14 1, P1 1, P3 9 and S4 2. The spec review finds no gap.

The audit also found a checker defect: a Doc candidate's hash leaves out parts of the section a reviewer reports on, so a fixed statement is not judged again. It is filed as a request (see [Checker request](#checker-request)).

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits.

## Phase B findings (consolidated)

### F1. The installer's exit-1 row leaves out two cases (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed, carried from review-4 F9). **Severity:** low.
- **Location:** `docs/reference/cli.md:52`.
- **Description:** review-4's Task 7 left this row as it was, because it could not read the pinned installer. It was read here on 2026-11-22: `install-in-claude` at the pinned commit `fa68deb` also exits 1, before changing anything, in two more cases:
  - a key on the edit path that is not an object (`settings.py:137`);
  - a `hooks.Stop` that is not a list (`settings.py:164`).
- **Recommendation:** add both cases to the row.

### F2. A troubleshooting cause left out (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed). **Severity:** low.
- **Location:** `docs/setup.md:268` ("The Stop hook does not fire").
- **Description:** when no reportable file changed, `changed.py` skips the sweep and exits 0 (`changed.py:229-231`), so the hook does not block. Review-4's reviewer judged the same case unsettled and did not flag it. This time the section had changed, so it was judged again, and this reviewer read it as covered by the 2026-11-22 ruling that a troubleshooting list is complete. See D3.
- **Recommendation:** add the cause.

### F3. The phaseb synopsis leaves out `--depth` (Doc4)

- **Category:** Doc. **Question:** Doc4 (listed). **Severity:** low.
- **Location:** `agents/specs/repeatable-phase-b/spec.md:214-219`.
- **Description:** the command synopsis is not marked as an excerpt, and it leaves out `--depth`. The `candidates`, `plan`, `merge` and `report` subcommands all accept it. The earlier verdict on this candidate, under the same brief version 7, did not flag it. See D3.
- **Recommendation:** add `[--depth N]` to the four subcommands.

### F4. Two verdicts left open after their fix landed (Doc4, Doc5)

- **Category:** Doc. **Questions:** Doc4, Doc5 (listed, carried). **Severity:** low.
- **Locations:**
  - `agents/specs/project-setup/spec.md:598`, fixed by review-4's Task 6; line 599 now runs the full `pre-commit install --hook-type ...` command.
  - `docs/concepts.md:25`, fixed by review-4's Task 7; its "Fails on" column now names the git and root-resolution failures.
- **Description:** both were checked by hand on 2026-11-22. Their candidates' hashes did not change, so nothing re-judged them. The cause is the checker defect below.
- **Recommendation:** dismiss both as fixed, with that reason, until the hash fix lets them be judged again.

### F5. `resolve_path` reads a file under a pure name (A9)

- **Category:** A. **Question:** A9 (sampled). **Severity:** low.
- **Locations:** `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:328` (`resolve_path`) and `:390` (`resolve_name`). Both reach `file_target`, which reads a tracked file with `read_bytes()` the first time it sees it.
- **Description:** review-4's Task 5 renamed `read_path_targets` to `resolve_path`, which is a pure-sounding prefix, and cached the line count. The first lookup still reads the file, so review-4's F4 is only partly fixed, and the rename brought A9 back.
- **Recommendation:** take the line counts from where the corpus is already read, or keep a name that says the function reads (`read_path_targets`).

### F6. The Phase B listers read, parse and resolve the same things repeatedly (A14, P3)

- **Category:** P. **Questions:** A14, P3 (sampled). **Severity:** low.
- **Locations:** in `claude/skills/auditme/checks/auditme/phaseb/candidates.py` unless named otherwise.
  - **Files read again:**
    - `:439` `target_bytes` reads a target's file for every (section, target) pair. Measured on 2026-11-22: one Doc4 listing read `auditme/core.py` 41 times, and one Doc5 listing read `.pre-commit-config.yaml` 15 times.
    - `:465` a document is read up to three times.
    - `:572` and `:676`/`:687` `AGENTS.md` is read twice.
    - `:816` and `:1075` a candidate's test files are read again for each candidate.
  - **Files parsed again instead of using `auditme.core.read_and_parse`:** `docrefs.py:191`, and `candidates.py:302` and `:655`.
  - **Work done twice:**
    - `:348` `calls_of` re-resolves the calls `direct` (`:330`) already resolved;
    - `:1062` a module's text is joined again for every T2 site.
- **Description:** `candidates.py` came into the sample because two lines of it changed. These sites are in its unchanged code, and the whole-tree P3 pass in review-3 did not report them. They are coverage, not regressions. See D1.
- **Recommendation:** read each file once per listing (through the cache that `read_and_parse` uses), and compute each resolution once.

### F7. `t1_reasons` walks every method once per method (P1)

- **Category:** P. **Question:** P1 (sampled). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/phaseb/candidates.py:775`.
- **Description:** for a class with m methods, the walk costs O(m^2). In this repository no class has more than a few dozen methods.
- **Recommendation:** dismiss. P1 is about real-size inputs, and a class's method count is not data-shaped. The cost does not grow with the corpus.

### F8. Two imports used only in annotations, outside `TYPE_CHECKING` (S4)

- **Category:** S. **Question:** S4 (sampled). **Severity:** low.
- **Locations:** `claude/skills/auditme/checks/auditme/core.py:5` (`collections.abc`), `claude/skills/auditme/checks/auditme/phaseb/ledger.py:18` (`Candidate`).
- **Recommendation:** move both under `if typing.TYPE_CHECKING:`, as the coding standard asks.

## Phase B per-question results

Listed questions: each verdict is in `agents/audit-reviews/ledger/<Q>.jsonl`. Sampled questions: changed files since `0a01580` (review-4's commit).

### A1 (listed)

- 6 candidates judged, none left out; 0 open findings.

### A4 (listed)

- 17 candidates judged, none left out; 0 open findings.

### A11 (listed)

- no candidate re-planned; every verdict carried; 0 open findings.

### A17 (listed)

- 1 candidates judged, none left out; 0 open findings.

### A19 (listed)

- no candidate re-planned; every verdict carried; 0 open findings.

### T1 (listed)

- 102 candidates judged, none left out; 0 open findings.

### T2 (listed)

- 8 candidates judged, none left out; 0 open findings.

### Doc1 (listed)

- no candidate re-planned; every verdict carried; 0 open findings.

### Doc2 (listed)

- no candidate re-planned; every verdict carried; 0 open findings.

### Doc4 (listed)

- 72 candidates judged, none left out; 2 open findings (F3, and F4 carried).

### Doc5 (listed)

- 21 candidates judged, none left out; 3 open findings (F1 and F4 carried, F2).

Python files in scope (from changed-code.txt): `claude/skills/auditme/checks/auditme/core.py`, `auditme/phaseb/__init__.py`, `auditme/phaseb/candidates.py`, `auditme/phaseb/docrefs.py`, `auditme/phaseb/ledger.py`, `claude/skills/auditme/checks/changed.py`; tests `claude/skills/auditme/tests/phaseb/test_docrefs.py`, `tests/phaseb/test_ledger.py`, `tests/test_changed.py`, `tests/test_core.py`, `tests/test_check_foreign_names.py`. Each source file was read end to end. Paths below are relative to `claude/skills/auditme/checks/` unless they are given in full.

### A2 (sampled): Except tuple coverage
- Mode: changed files since 0a01580
- Inspected: every `try/except` in the scoped source files. `core.py`: `stat` at 106 and 126 (`OSError`), `read_text` at 136 (`OSError, UnicodeDecodeError`), `tomllib.loads` at 321. `ledger.py`: `read_text` at 63 (`OSError, UnicodeDecodeError`), `json.loads` at 72 (`json.JSONDecodeError`), `unlink` at 87 and mkdir/mkstemp/fdopen/replace at 100-108 (`OSError`). `docrefs.py`: `read_text` at 87 (`OSError, UnicodeDecodeError`), `git ls-files` at 303, `read_bytes` at 321 (`OSError`, no decoding), `ast.parse` over `source_lines` at 191 (`source_lines` handles its own read errors). `candidates.py`: `read_bytes` at 82, 448, 653; `read_text` at 185, 393 (`OSError, UnicodeDecodeError`); `read_bytes().decode` + `tomllib.loads` at 637 (`OSError, UnicodeDecodeError, TOMLDecodeError`). `changed.py`: git at 55, sweep at 135, `json.loads` at 155 (`json.JSONDecodeError`), repository root at 216 (`OSError`). No `contextmanager` or translating-decorator envelope in scope.
- Hits: No hits

### A3 (sampled): Domain-error layering
- Mode: changed files since 0a01580
- Inspected: every `raise` in the scoped source files: `core.py` raises `RootsError`; `ledger.py`, `docrefs.py` and `candidates.py` raise `PhaseBError`; `changed.py` raises `ChangedError` and `SystemExit(main())` at the entry point.
- Hits: No hits

### A5 (sampled): Two sources of truth
- Mode: changed files since 0a01580
- Inspected: module-level state and option/default pairs: `core.py` `ROOT_MODULES` beside the `('audit-roots', scope)` entry in `INDEX_CACHE` (`cached_roots` now rebinds the global from the cache on every call, `core.py:788`, so the two agree after each call; review-4's hit there no longer holds), `DECLARATION_IGNORED`, `EXTRA_ROOT_NAMES` versus the `names` parameter of `extra_roots` (documented default); `candidates.py` `REGISTRY`/`KINDS`/`TAKES_DEPTH` (kept in step by `register_question`) and `depth` versus `DEFAULT_DEPTH`; `ledger.py` `today` versus `datetime.date.today()`; `changed.py` `--base` versus `read_base_ref` (explicit `args.base or ...`, documented in the help).
- Hits: No hits

### A6 (sampled): Stage method dual-path
- Mode: changed files since 0a01580
- Inspected: every class in scope (`Candidate`, `Verdict`, `Site`, `MergeResult`, `DocSection`, `DocTarget`, `ClassInfo`, `CorpusIndex`, `IndexEntries`, `RootsError`, `ChangedError`). None is a pipeline-stage class; `IndexEntries` methods fill `self`'s dicts and return `None` or a separate `ClassInfo`.
- Hits: No hits

### A7 (sampled): Constructor purity
- Mode: changed files since 0a01580
- Inspected: grep for `__init__(self` in every scoped file, tests included: none. Dataclass constructors have no `__post_init__`.
- Hits: No hits

### A8 (sampled): Late dataclass mutation
- Mode: changed files since 0a01580
- Inspected: every dataclass construction in scope (`IndexEntries()` at `docrefs.py:187`, `ClassInfo(...)` at 267, `CorpusIndex` via `cls(...)` at 202, `DocTarget`, `Candidate`, `Site`, `MergeResult`, `Verdict` via `dataclasses.replace`) and every non-`self` attribute assignment in the scoped files, tests included. None reassigns a field after construction. `file_target` (`docrefs.py:324`) inserts into the `line_counts` dict field of a frozen `CorpusIndex`, a container insert rather than a field reassignment, so outside this question's shape.
- Hits: No hits

### A9 (sampled): Pure-named function side effects
- Mode: changed files since 0a01580
- Inspected: every `def` with a pure prefix in the scoped files: `core.py` `is_test_relpath`, `resolve_call`, `is_dunder_all_assignment`, `is_main_guard`; `docrefs.py` `is_path_shaped`, `resolve_path` (renamed from `read_path_targets` since 0a01580), `resolve_dotted`, `resolve_bare`, `resolve_member`, `resolve_setting`, `resolve_option`, `resolve_name`; `candidates.py` `is_stub`, `is_builtin_call`, `is_overload`, `is_frozen_dataclass`, `is_well_defined_class`, `is_well_defined_type`, `is_t2_candidate`; `ledger.py` `parse_verdict`; `changed.py` `parse_args` (argparse only, as judged in review-4); test helpers `resolve_token` (`test_docrefs.py:206`, which reaches the I/O below only through `resolve_name`) and `parse_call` (`test_core.py:474`, pure). No `check_` function in scope. `CorpusIndex.build` is named `build`, not `build_...`.
- Hits:
  - `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:328` - `resolve_path`, now carrying a `resolve_` name, calls `file_target` (`:309`) for a tracked file, which reads the whole file (`read_bytes()`, `:321`) on its first lookup to count its lines; file I/O in a pure-named function.
  - `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:390` - `resolve_name` reaches the same read through its first step, `resolve_path` (review-4's hit at this function, still present; the line count is now cached on the index, but the first lookup still reads the file).

### A10 (sampled): Predicate semantics
- Mode: changed files since 0a01580
- Inspected: every `is_`/`has_`/`should_` function in scope (the `is_*` functions listed under A9; no `has_` or `should_` function exists), each body compared with its name and docstring. `Verdict.flagged` is a property, not a predicate-named function.
- Hits: No hits

### A12 (sampled): assert misuse
- Mode: changed files since 0a01580
- Inspected: grep for `assert` statements in the non-test scoped files.
- Hits: No hits (no `assert` outside test files)

### A13 (sampled): Same value to multiple structural slots
- Mode: changed files since 0a01580
- Inspected: every constructor call in the scoped files (`Candidate`, `Site`, `DocTarget`, `DocSection`, `ClassInfo`, `MergeResult`, `CorpusIndex`, error classes).
- Hits: No hits (`docrefs.py:283` `DocTarget(kind, rel, rel, 1, last_line)` passes `rel` as both id and path, inside the explicit factory `path_target`, and `DocTarget.id`'s comment documents that a file or directory's id is its path)

### A14 (sampled): Repeated computation per request
- Mode: changed files since 0a01580
- Inspected: `changed.py` `main` (root, base ref, changed files and sweep each resolved once); `core.py` root and corpus helpers (`cached_declared_roots`, `audit_roots`, `cached_roots`, `cached_corpus_files`, `corpus_index`); `CorpusIndex.build` (now uses `cached_roots` and `cached_corpus_files`; review-4's hit at `docrefs.py:187` is resolved); the Doc listers in `candidates.py` (`doc_candidates`, `list_doc1_candidates`, `list_doc2_candidates`, `imported_modules`). Measured on 2026-11-22 on this repository by wrapping `target_bytes` and running `list_candidates('Doc4', ...)` and `list_candidates('Doc5', ...)` in-process: one Doc4 request read 336 target files across 55 distinct paths (`auditme/core.py` 41 times, `auditme/rules/error_handling.py` 33 times); one Doc5 request read 85 across 21 (`.pre-commit-config.yaml` 15 times).
- Hits:
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py:439` - `target_bytes`, called once per (section, target) candidate from `doc_candidates` (`:489`), re-reads the target's whole file each time (`read_bytes()`, `:448`), so one Doc4 or Doc5 request reads the same source file dozens of times; the same change cached `file_target`'s line count on the index (`CorpusIndex.line_counts`) but not these bytes.

### A15 (sampled): Duplicate constructor / serialisation logic
- Mode: changed files since 0a01580
- Inspected: every class defined in the non-test scoped files and each construction site: `Candidate` (three factories, `site_candidate`, `span_candidate`, `section_candidate`, with different sources), `DocTarget` (two factories, `node_target` and `path_target`), `Site` (two adjacent calls in `module_sites`, all fields positional with no defaults, so a new field fails both loudly), `Verdict` (one site, `parse_verdict`), `MergeResult`, `ClassInfo`, `IndexEntries`, `DocSection`, `CorpusIndex` (one site each).
- Hits: No hits

### A16 (sampled): CLI entry envelope
- Mode: changed files since 0a01580
- Inspected: scope list for `cli/*.py` files; none is in scope (`changed.py` is not under `cli/` and defines no `run_*` function).
- Hits: No hits

### A18 (sampled): Hot-path setup
- Mode: changed files since 0a01580
- Inspected: grep for `def on_` in every scoped file; no callback method is defined.
- Hits: No hits

### A20 (sampled): Mutable module-level singleton
- Mode: changed files since 0a01580
- Inspected: every module-level `dict`/`list`/`set` literal, comprehension or bare-constructor assignment in the scoped files, tests included. `EMITTED`, `UNREADABLE` (`core.py:29`, `:35`) and `REGISTRY`, `KINDS` (`candidates.py:59`, `:61`) belong to the sweep (`mutable-module-level-exported`, accepted). For `SOURCE_CACHE`, `INDEX_CACHE` (`core.py:74`, `:79`), `TAKES_DEPTH` (`candidates.py:63`), `RULE_HELP` (`changed.py:41`), `FIXTURE` (`test_docrefs.py:144`) and `TWO_MARKERS` (`test_core.py:50`), grepped across every root (`claude/`, `tests/`, `bin/`) for `from <module> import <name>`, `<module>.<name>` and `sys.modules[...]` reads: none is read outside its own module.
- Hits: No hits

### A21 (sampled): Lazy init race
- Mode: changed files since 0a01580
- Inspected: every `is None` test and `global` statement in the scoped files (`global ROOT_MODULES` in `audit_roots` and `cached_roots`; `INDEX_CACHE` fills; `file_target`'s per-index `line_counts` fill, not module scope); grep for `threading`, `multiprocessing`, `concurrent`: none. No module-scope `if X is None: X = ...` in a concurrently called path.
- Hits: No hits

### A22 (sampled): Fall-through after partial handling
- Mode: changed files since 0a01580
- Inspected: every `if`/`else` chain that holds a `try` or raises in one branch and returns in another: `core.py` `cached_source` (130-148), `declared_roots`; `ledger.py` `write_ledger` (`finally` cleanup only), `merge_verdicts`; `docrefs.py` `file_target`; `candidates.py` `list_candidates`, `target_bytes`; `changed.py` `main`. None retries a translated error down another branch.
- Hits: No hits

### A23 (sampled): Discarded multi-return
- Mode: changed files since 0a01580
- Inspected: every function in scope returning a tuple or a dataclass (`cached_source`, `dotted_read`, `cached_roots`, `surface_files`, `privacy`, `declared_roots`, `registered`, `root_sites`, `agents_document`, `merge_verdicts`, `dismiss_verdict`, `parse_verdict`, `CorpusIndex.build`) and each call site in the scoped files, tests included. Calls unpack every component or name the discard (`roots, _ = ...cached_roots(scope)` at `docrefs.py:184`, `lister, _, _ = registered(question)` at `candidates.py:173`, `root, _ = indexed` in tests). The indexed reads `cached_source(path)[0]`/`[1]`, `privacy(...)[0]`, `registered(question)[1]`/`[2]` and the bare `registered(question)` called for its raise were judged not hits in review-1 and review-3 for the same reason, and nothing documented in them has changed. `list_doc2_candidates` calls `tracked_files(scope)` for its raise, but it returns a `frozenset`, not a tuple or dataclass.
- Hits: No hits

### A24 (sampled): Identity of subprocess / shell-out calls
- Mode: changed files since 0a01580
- Inspected: every `subprocess` call in the scoped files. `docrefs.py:303` (`tracked_files`) runs once per `CorpusIndex.build`, called once per Doc1/Doc4/Doc5 lister request; `list_doc2_candidates` calls it once and builds no index. `changed.py:55` (`run_git`) runs with different arguments each call, and `changed.py:135` runs the sweep once per invocation. The `git` and `bash` calls in `test_docrefs.py:191` and `tests/test_check_foreign_names.py:20` are test setup and the script under test.
- Hits: No hits

### A25 (sampled): Shallow immutable wrapper
- Mode: changed files since 0a01580
- Inspected: every module-level `frozenset(...)`, `tuple(...)` or `types.MappingProxyType(...)` in scope that another module reads (`BARE_GENERIC_NAMES`, `SIDE_EFFECT_CALL_NAMES`, `EXTRA_ROOT_NAMES`, `ROOT_MODULES` in `core.py`; `docrefs.py` `PATH_EXTENSIONS`, `OPTION_CALLS`; `candidates.py` `T2_*` sets and tuples). Every member is a `str`, a `Path` key with a `str` value, an `ast` class or a tuple of `str`.
- Hits: No hits

### S1 (sampled): Type annotations on every signature
- Mode: changed files since 0a01580
- Inspected: every `def` in the Python files of `changed-code.txt`, walked with an AST script (parameters other than `self`/`cls`, and returns); ruff does not select `ANN` in `pyproject.toml`, so nothing here is ruff's. `bin/check-foreign-names.sh` is shell and has no signatures.
- Hits (non-test source): No hits (`core.py`, `phaseb/__init__.py`, `phaseb/candidates.py`, `phaseb/docrefs.py`, `phaseb/ledger.py` and `changed.py` are fully annotated)
- Tests count: 106 missing parameter annotations, 28 missing return annotations; 3 modules affected (`claude/skills/auditme/tests/phaseb/test_docrefs.py` 31 params / 27 returns, `claude/skills/auditme/tests/test_changed.py` 74 params / 1 return, `claude/skills/auditme/tests/phaseb/test_ledger.py` 1 param / 0 returns); 2 modules fully annotated (`claude/skills/auditme/tests/test_core.py`, `tests/test_check_foreign_names.py`)

### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake
- Mode: changed files since 0a01580
- Inspected: every class, function, module constant and type alias in the in-scope Python files (read end to end for the source files; grep for camelCase / lower-case class / capitalised def in the tests)
- Hits: No hits

### S3 (sampled): TYPE_CHECKING block placement
- Mode: changed files since 0a01580
- Inspected: every `if typing.TYPE_CHECKING:` block in scope (`changed.py:31`, `tests/phaseb/test_docrefs.py:14`, `tests/phaseb/test_ledger.py:14`, `tests/test_changed.py:17`, `tests/test_core.py:19`); each sits directly after the import block, as elsewhere in the tree. Typing-only imports kept outside a block are reported under S4.
- Hits: No hits

### S4 (sampled): Project-specific rule files
- Mode: changed files since 0a01580
- Inspected: `claude/rules/auditme/coding-standards.md`, `claude/rules/auditme/imports.md`, `~/.claude/rules/python/argparse.md`, checked against every in-scope Python file; rules the sweep enforces (from-import, as-import, leading underscores, legacy formatting, alphabetical literals, def-in-init, etc.) and ruff's rules left to them. The rule files apply to `**/*.py`, so `bin/check-foreign-names.sh` is outside them. `changed.py`'s argparse use is allowed (stdlib-only checker) and follows the trailing-comma layout.
- Hits:
  - `claude/skills/auditme/checks/auditme/core.py:5` - `import collections.abc` is used only in annotations (lines 96, 395, 486-487, 514-516, 734, 776) but is imported at runtime, not in a `TYPE_CHECKING` block as the coding standards' Type annotations section requires (`changed.py:31` does it the required way); the sweep has no typing-only-import rule and ruff's TC rules do not flag it
  - `claude/skills/auditme/checks/auditme/phaseb/ledger.py:18` - `Candidate` is imported at runtime but used only in the annotation at line 114; it belongs in a `TYPE_CHECKING` block (ruff's non-strict TC mode skips it because `Verdict` from the same module is a runtime import)

### P1 (sampled): O(n^2) on real-size inputs
- Mode: changed files since 0a01580
- Inspected: every loop and comprehension in the in-scope source files, especially the fixed-point loops (`core.reexport_aliases`, `docrefs.settings_classes`), `candidates.root_candidates.reach`, `candidates.doc_candidates`, `candidates.t1_reasons`, `candidates.referenced_types`
- Hits:
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py:775` - `t1_reasons` walks every other method of the class with `tested_attributes` for each method that assigns `self` attributes, and `list_t1_candidates` calls it for every method, so a class with m methods costs O(m^2) method walks; each method's tested attributes could be computed once per class

### P2 (sampled): Blocking I/O in hot paths
- Mode: changed files since 0a01580
- Inspected: the in-scope source files for training loops, request handlers and callbacks; they are one-shot command-line and lister code with no such hot path
- Hits: No hits

### P3 (sampled): Repeated expensive computation per request
- Mode: changed files since 0a01580
- Inspected: every read, parse and derived value inside the listers and the corpus index, against the per-run caches in `core.py` (`cached_source`, `corpus_index`, `cached_roots`)
- Hits:
  - `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:191` - `CorpusIndex.build` re-parses every corpus file with `ast.parse('\n'.join(source_lines(path)))`, although `core.read_and_parse` holds the cached tree and `corpus_definitions` (line 186) has just parsed the same files through it
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py:302` - `root_sites` re-parses each module from its lines instead of using the cached tree from `core.read_and_parse`
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py:655` - `imported_modules` re-parses every corpus file the same way
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py:348` - `calls_of(site)` resolves every call of a site a second time, after `direct` (line 330) already resolved them all for every site
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py:448` - `target_bytes` reads the target's file from disk for every (section, target) pair, so a module many sections name is read once per pair; `docrefs.file_target` caches line counts on the index, but these bytes are not cached
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py:465` - `doc_candidates` reads each document with `read_text`, then `read_sections` (line 466) reads and decodes it again; for Doc4 specs `IMPLEMENTED_RE.search(read_text(path))` at line 513 is a third read
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py:572` - `list_doc1_candidates` reads `AGENTS.md` through `agents_document` (line 564) and then again through `read_sections`; `list_doc2_candidates` does the same at lines 676 and 687
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py:816` - `read_test_files` reads every test file of a candidate from disk per candidate, so a test file reaching many functions is read once per function (same at line 1075 for T2)
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py:1062` - `'\n'.join(site.lines)` rebuilds the whole module text for every accepted T2 site, once per site rather than once per module

### Sec1 (sampled): Secrets in source
- Mode: changed files since 0a01580
- Inspected: every in-scope file, including `bin/check-foreign-names.sh` (reads its list path from `AUDITOR_FOREIGN_NAMES`, holds no value)
- Hits: No hits

### Sec2 (sampled): Input validation at system boundaries
- Mode: changed files since 0a01580
- Inspected: `changed.py` arguments (`--base` refused when it starts with `-`, and passed after `--end-of-options`; `repo_root` resolved and used only as `cwd`); `bin/check-foreign-names.sh` options (`--allow=`, `--`, file arguments after `--` to grep, patterns as fixed strings with `-F`); `ledger.dismiss_verdict` (candidate id checked against the ledger); `core.declared_roots` (every `[tool.auditme]` key and type validated)
- Hits: No hits

### Sec3 (sampled): Command injection
- Mode: changed files since 0a01580
- Inspected: every `subprocess.run` (`changed.run_git`, `changed.sweep`, `docrefs.tracked_files`) - all list-form, no shell; the shell script's `grep` calls (quoted, `-e`/`--`, `-F`)
- Hits: No hits

### Sec4 (sampled): Path traversal
- Mode: changed files since 0a01580
- Inspected: `core.declared_roots` (root must resolve inside the project), `docrefs.resolve_path` (normalised, `..` and `.` refused, lookup only among tracked files), `docrefs.file_target` and `candidates.target_bytes` (paths come from the tracked-file index), `candidates.read_test_files` (names from the test index), `ledger.write_ledger` (path from the caller, temporary file in its own directory)
- Hits: No hits

### Sec5 (sampled): PII in logs
- Mode: changed files since 0a01580
- Inspected: every `print` and stderr `echo` in scope; there is no logger, and output is hits, paths, git error text and matched lines of the user's own files
- Hits: No hits

### T3 (sampled): Integration vs unit balance. Pipeline orchestrators have at least one end-to-end test.

- Mode: sampled, files changed since `0a01580` (`git diff --name-only 0a01580..HEAD`)
- Inspected: `claude/skills/auditme/checks/changed.py` against `claude/skills/auditme/tests/test_changed.py` (`test_end_to_end_against_the_real_checker`, `test_cross_file_hit_on_an_unchanged_file_fails_when_its_peer_changes` and the `start_script_project` cases run `changed.main` on a real git repository with the real checker); `bin/check-foreign-names.sh` against `tests/test_check_foreign_names.py` (every test runs the script with `bash` via `subprocess`, including the new unreadable-list case `test_an_unreadable_list_fails_and_names_it`)
- Hits: No hits

### D1 (sampled): Declared in pyproject. Every imported third-party module is declared.

- Mode: sampled, files changed since `0a01580`
- Inspected: the changed-file list; neither `pyproject.toml` nor `uv.lock` is in it
- Hits: No hits (neither `pyproject.toml` nor `uv.lock` changed since `0a01580`)

### D2 (sampled): Unused declarations. Every declared dependency is imported somewhere, or run as a command.

- Mode: sampled, files changed since `0a01580`
- Inspected: the changed-file list; neither `pyproject.toml` nor `uv.lock` is in it
- Hits: No hits (neither `pyproject.toml` nor `uv.lock` changed since `0a01580`)

### D3 (sampled): Lockfile coherence. Already script-checked; flag if the script's lockfile-drift hit appears.

- Mode: sampled, files changed since `0a01580`, plus the sweep output `/tmp/audit-auditor.jsonl`
- Inspected: the changed-file list (no `pyproject.toml` or `uv.lock`); every rule in `/tmp/audit-auditor.jsonl` (no `lockfile-drift` hit; the only lines mentioning the lockfile are two accepted hits on `rules/project_hygiene.py:83` and `:98`, rules `non-alphabetical-literal` and `subprocess-without-memoisation`)
- Hits: No hits

### Doc3 (sampled): README.md and AGENTS.md consistent.

- Mode: sampled, files changed since `0a01580`
- Inspected: the changed-file list; neither `README.md` nor `AGENTS.md` is in it
- Hits: No hits (neither file changed since `0a01580`)

### Spec review

Checked against the "Spec template" and "Validation criteria" of `/Users/simonb/.claude/skills/specdev/SKILL.md`: header fields, every template section present and non-empty, a type-annotated signature in a `python` block under API, named exceptions or failure modes under Error handling, name/type/default for each setting, referenced paths existing (or fixtures, historical names or other repositories' paths named as such), relative links resolving, and an entry in `agents/specs/index.md`. Spec size and "Module location under src/" are excluded (dismissed by review-1's D6).

- `agents/specs/listed-phase-b-architecture-questions/spec.md`: No gaps
- `agents/specs/listed-phase-b-documentation-questions/spec.md`: No gaps
- `agents/specs/listed-phase-b-test-questions/spec.md`: No gaps
- `agents/specs/project-setup/spec.md`: No gaps
- `agents/specs/repeatable-phase-b/spec.md`: No gaps

### Coverage (sampled)

The sampled sites in `candidates.py` (F6, F7) are in its unchanged code; the file came into scope because two of its lines changed. They are coverage, not drift.

## Prior findings re-verified

Review-4's findings: F2, F3, F5, F6, F7, F8 (its `:356`) and F10 hold. F4 is partly fixed (F5 here). F9's `concepts.md:25` and F8's `spec.md:598` are fixed, but their verdicts stay open (F4 here). F9's `cli.md:52` was left undone (F1 here). No task in `agents/tasks/audit-reviews/` is incomplete.

## Checker request

The carried F4 verdicts led to a defect, which I checked on 2026-11-22. For a Doc4 or Doc5 candidate with a named target, `doc_candidates` (`candidates.py:479-489`) hashes only the blocks of the section that name that target, plus the target's file. A reviewer, though, reports each drift in the section under the candidate whose target it is about, or under the first candidate of the section. So a drift can sit outside the hashed blocks.

When such a drift is fixed, the hash does not change, nothing judges the candidate again, and the finding stays open. For example, `project-setup/spec.md`'s candidate for `SKILL.md` has hash `d014b790` both at `0a01580`, before the fix, and at `dbb9780`, after it.

It is filed in `claude/skills/auditme/requests.md`, as the skill requires. The next audit waits on it.

## Decisions

### D1. Sample a changed file's changed lines, not the whole file

- **What is being decided:** whether to file a request so that, between whole-tree audits, a sampled question judges only the lines that changed in a changed file (with their enclosing function), not the whole file.
- **Background:** every audit samples each changed file whole, so a small edit reopens the whole file to every sampled question. Review-4 changed two lines of `candidates.py`, and this audit found ten sites in its unchanged code (F6, F7). Every third audit still runs the whole tree, and it is meant to be what catches older code.
- **What it affects:** `checks/changed.py`'s diff base, and the sampled cadence in `SKILL.md`. Review-to-review deltas would shrink to what actually changed.
- **Options:**
  - **File the request (recommended):** sampled findings between whole-tree audits would follow the change, which is what the sampled cadence was meant to do. That removes the main source of new findings in unchanged code.
  - **Keep sampling whole files:** each audit goes on finding older sites in any file it touches.

### D2. Treat the Doc hash defect as blocking the next audit

- **What is being decided:** nothing extra to choose. The checker request above is filed, and like every open request it blocks review-6 until it ships or is rejected. This is listed so you can reject it instead, if you would rather the next audit went ahead.
- **Background:** see [Checker request](#checker-request).
- **What it affects:** review-6's start.
- **Options:**
  - **Ship it before review-6 (recommended):** fixed doc statements stop staying open, which is needed for the count to reach zero.
  - **Reject it:** record why in `requests.md`. Stale Doc verdicts are then dismissed by hand each time.

### D3. Show a re-judged candidate's earlier verdict to its reviewer

- **What is being decided:** whether to file a request so that `phaseb.py plan` puts a re-planned candidate's earlier verdict and reason in its batch, with the brief telling the reviewer to give its reason whenever its verdict differs.
- **Background:** F2 and F3 each flipped from not flagged to flagged when their section changed elsewhere and a fresh reviewer read the same statement. The text was the same, and the brief version was the same. The default-verdict ruling settled the cases a brief leaves open, but not two reviewers reading a settled rule differently.
- **What it affects:** `phaseb/batches.py` (the batch payload), every brief's Input section (a version bump, so the next audit judges every candidate again once), and the ledger's convergence.
- **Options:**
  - **File the request (recommended):** a reviewer that disagrees with the earlier verdict must say why, so a flip is a decision and not chance.
  - **Leave it:** a re-judged candidate can flip with no record of why.

## Answers

Answered on the review page on 2026-11-22. Every item took the recommended option, with no comments.

| Item | Answer |
|---|---|
| F1 | Fix |
| F2 | Fix |
| F3 | Fix |
| F4 | Dismiss (already fixed; both verdicts dismissed in the Doc4 and Doc5 ledgers) |
| F5 | Fix |
| F6 | Fix |
| F7 | Dismiss (not real-size) |
| F8 | Fix |
| D1 | File the request |
| D2 | Ship it before review-6 |
| D3 | File the request |
