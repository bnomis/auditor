# Audit Review 6

**Date:** 2026-11-22
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`); every sampled question ran on the whole tree
**Commit:** 996bbb33a1c8861b68500ae2de9936725cbe8f3d
**Script output:** /tmp/audit-auditor.jsonl (48 hits, 48 accepted, 0 unaccepted)
**Script version:** e5d95235f166aec74a8cd3b3d3cc8617ce2edf4bcd8b2e3e53a608091cab6836
**Convergence note:** this is the whole-tree audit (every third), and the review-5 task list raised every brief's version, so every listed candidate was judged again, each shown its earlier verdict for the first time. Measured on 2026-11-22: 993 candidates judged; no reviewer changed a verdict on unchanged text, and every changed verdict names the commit that changed the code or doc under it. Review-5's three doc fixes and its two stale verdicts (F4) all cleared. Every open finding comes from one of two sources:
- the review-5 task list's own new code and doc lines (F1-F6, F8);
- whole-tree coverage of older code that the sampled passes did not reach (F7, F9, F10).
**Review page:** https://claude.ai/artifact/D6J5HWPusD2cDQ2FkUbbaJ

## What is being reviewed and how

This is the checker repository's sixth audit of its own code, and the first whole-tree pass since review-3. The sweep is clean. For each finding, choose Fix (it becomes a task) or Dismiss (with your reason). The items marked U are cases a brief does not settle, which the default-verdict rule (2026-11-22) judged not findings: approve that, or flag one to make it a finding. Then answer the decision.

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 48 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 993 judged (A1 26, A4 55, A11 3, A17 2, A19 1, T1 281, T2 24, Doc1 4, Doc2 3, Doc4 440, Doc5 154) |
| `phaseb.py check` on every listed question | pass, no retries |
| Every sampled question returned a hit list or "no hits" | pass |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| Prior findings to re-verify | review-5 F1, F2, F3, F5, F6, F8 shipped and confirmed; F4's two verdicts cleared on re-judging; F7 stays dismissed |

## Summary

The sweep reports 48 hits, all accepted. Phase B leaves 12 listed verdicts open (A1 1, T1 1, T2 3, Doc4 5, Doc5 2). The sampled questions flag A9 1, A14 2, P1 2, P3 3 and Doc3 1. The spec review finds no gap. `cached_source`'s A1 verdict is still dismissed, as review-1's D2 chose.

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits.

## Phase B findings (consolidated)

### F1. `cached_bytes` lets `OSError` escape and has no direct test (A1, T1)

- **Category:** A, T. **Questions:** A1, T1 (listed). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/core.py`, `cached_bytes`, added by Task 3 of the review-5 task list.
- **Description:** `cached_bytes` is public (in core's `__all__`). Its `path.stat` and `path.read_bytes` calls let `OSError` reach the caller untranslated, and no test calls it directly; the tests reach it only through `docrefs`.
- **Recommendation:** translate `OSError` into the error its callers already raise for an unreadable file, or drop it from `__all__` if only package code uses it; add a direct test that a file is read once per run and again after it is rewritten.

### F2. The new `--scope` helpers have no property tests (T2)

- **Category:** T. **Question:** T2 (listed). **Severity:** low.
- **Locations:** `claude/skills/auditme/checks/changed.py`, `enclosing_ranges`, `merge_ranges` and `widen`, added by Task 5 of the review-5 task list.
- **Description:** each has an invariant a property test can check:
  - `merge_ranges`: sorted, no two ranges overlap or touch, covers exactly the union of the input, and merging again changes nothing;
  - `widen`: one range per hunk line, each holding its line, the shortest enclosing function (or class) or the line itself;
  - `enclosing_ranges`: every range within the source, starting at its decorator line.
- **Recommendation:** add a hypothesis test for each.

### F3. Three specs state brief version numbers that went stale (Doc4)

- **Category:** Doc. **Question:** Doc4 (listed). **Severity:** low.
- **Locations:**
  - `agents/specs/listed-phase-b-architecture-questions/spec.md:59` (A1 5, A17 3, A11 and A19 2; now 6, 4, 3, 3);
  - `agents/specs/listed-phase-b-test-questions/spec.md:259` (T1 5, T2 2; now 6, 3);
  - `agents/specs/repeatable-phase-b/spec.md:303` ("The A4 brief is at version 7"; now 8; reported under two candidates of the section).
- **Description:** Task 6 of the review-5 task list raised every brief's version by one and left these lines. Each future brief change would break them again.
- **Recommendation:** remove the figures and say that each brief's `**Brief version:**` line holds its version, as the counts-in-prose rule asks.

### F4. A spec API block leaves out a declared `Raises:` (Doc4)

- **Category:** Doc. **Question:** Doc4 (listed). **Severity:** low.
- **Location:** `agents/specs/listed-phase-b-documentation-questions/spec.md:79`.
- **Description:** the API block gives `read_name_targets` (renamed by Task 3 of the review-5 task list) no `Raises:` section, but its docstring in `claude/skills/auditme/checks/auditme/phaseb/docrefs.py` declares `PhaseBError` when a matching file cannot be read.
- **Recommendation:** add the `Raises:` line.

### F5. The CLI reference misses two `--scope` behaviours (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed). **Severity:** low.
- **Locations:** `docs/reference/cli.md:226` and `:231`.
- **Description:**
  - line 226 says all output goes to stdout except argparse's usage errors, but `--scope` prints its no-diff-base message to stderr;
  - line 231's exit-1 list leaves out `--scope` failing to read a changed Python file.
- **Recommendation:** add both.

### F6. The `silent-self-mutation` row lists fewer exempt methods than the check (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed). **Severity:** low.
- **Location:** `docs/guide/checker.md:294`.
- **Description:** the row names the methods the rule skips, but `check_silent_self_mutation` also skips `__post_init__` and `__setattr__`. The earlier verdict judged only the section's rule ids.
- **Recommendation:** add both names.

### F7. `AGENTS.md` says "both hook types" before a command naming three (Doc3)

- **Category:** Doc. **Question:** Doc3 (sampled). **Severity:** low.
- **Location:** `AGENTS.md:31`.
- **Description:** the command on line 33 installs `pre-commit`, `pre-push` and `commit-msg`.
- **Recommendation:** say "all three hook types", or drop the count.

### F8. A test helper's name hides a read (A9)

- **Category:** A. **Question:** A9 (sampled). **Severity:** low.
- **Location:** `claude/skills/auditme/tests/phaseb/test_docrefs.py:206`.
- **Description:** the helper `resolve_token` wraps `docrefs.read_name_targets`, which reads a file. Task 3 of the review-5 task list renamed the source function and left the helper.
- **Recommendation:** rename it `read_token`.

### F9. The same value worked out again within one run (A14, P3)

- **Category:** A, P. **Questions:** A14, P3 (sampled). **Severity:** low.
- **Locations:**
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py:50`: `capture_hits` calls `audit_roots(scope)` once per check, 5 times in one A1 listing and 4 in one A17 listing;
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py:37`: `ruff_executable(scope)` is worked out once per root, and again by `check_ruff_version`;
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py:446`: `check_sibling_error_no_common_base` rebuilds `caught_elsewhere`, a walk of every file, once per `errors.py`;
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:173`: `check_in_function_imports` calls `declared_root_modules()` once per file;
  - `claude/skills/auditme/checks/auditme/phaseb/testmap.py:231`: `TestIndex.refs` reruns the same `reach` search once for every test that calls a function.
- **Description:** each depends only on a value fixed for the run. This is coverage from the whole-tree pass, not regressions. Measured on 2026-11-22 under a profiler on this repository: `check_in_function_imports` took 1.2 s of a 25 s sweep.
- **Recommendation:** compute each once per run (the per-run cache already holds the roots).

### F10. Two checks compare every function with every other (P1)

- **Category:** P. **Question:** P1 (sampled). **Severity:** low.
- **Locations:**
  - `claude/skills/auditme/checks/auditme/rules/duplication.py:616`: `check_duplicate_call_sequence` compares every pair of function signatures in a root;
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py:352`: `check_asymmetric_exception_translation` scans the whole function index with `endswith` for every call that is not an exact key.
- **Description:** measured on 2026-11-22 under a profiler on this repository: 0.65 s and 1.5 s of a 25 s sweep. The pairwise comparison is what the duplicate check is; the suffix scan can be indexed.
- **Recommendation:** dismiss: neither is a cost at real size, and the measured share of the sweep is small.

### U1. A synopsis that leaves out an option documented in a later amendment (Doc4)

- **Category:** Doc. **Question:** Doc4 (listed, unsettled). **Severity:** low.
- **Location:** `agents/specs/project-setup/spec.md:181`.
- **Description:** the `changed.py` synopsis leaves out `--scope`; the same spec documents it in a dated amendment at line 298, in another section.
- **Recommendation:** dismiss: the amendment documents it; not a finding under the default-verdict rule.

### U2. An installer crash after some links are made (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed, unsettled). **Severity:** low.
- **Location:** `docs/reference/cli.md:52`.
- **Description:** an uncaught `OSError` while linking makes the pinned installer exit 1 after some links exist; the row says nothing changed. The brief does not say whether a crash is a failure condition the code has.
- **Recommendation:** dismiss: an uncaught crash is not a documented exit path; not a finding under the default-verdict rule.

### U3. An excluded-directory list ending "among others" (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed, unsettled). **Severity:** low.
- **Location:** `docs/guide/checker.md:82`.
- **Description:** the list leaves out `node_modules` and `__pycache__`, which `SPEC_SKIP_PARTS` holds; "among others" marks it as incomplete in plain words.
- **Recommendation:** dismiss: the list says it is partial; not a finding under the default-verdict rule.

### U4. A test-path mapping that shows one of two accepted forms (Doc4)

- **Category:** Doc. **Question:** Doc4 (listed, unsettled). **Severity:** low.
- **Location:** `agents/specs/listed-phase-b-test-questions/spec.md:221`.
- **Description:** the mapping gives `src/tests/<pkg>/test_<f>.py`; `TestIndex.mirrored` also accepts the form that keeps the project directory.
- **Recommendation:** dismiss: an illustration of the mapping; not a finding under the default-verdict rule.

### U5. A complete rule list with two extra rejecting cases in the code (Doc4)

- **Category:** Doc. **Question:** Doc4 (listed, unsettled). **Severity:** low.
- **Location:** `agents/specs/listed-phase-b-test-questions/spec.md`, "T2 candidates".
- **Description:** rules 1-4 are the whole positive rule; `is_t2_candidate` also rejects a `del` of a parameter's attribute or subscript, and a module-level function whose first parameter is `self` or `cls`.
- **Recommendation:** dismiss: the extra cases narrow the list, and `del` is a form of assignment; not a finding under the default-verdict rule.

## Phase B per-question results

Listed questions: the verdicts are in `agents/audit-reviews/ledger/`; `phaseb.py report <root> --question <Q>` prints the open ones. A11, A17, A19, Doc1 and Doc2 have none; A4 has none.

Verdicts that changed on re-judging, each with the commit that changed what it judged:
- Doc4 `project-setup/spec.md` (review-5 F4): cleared, the hash fix let it be judged again;
- Doc5 `docs/concepts.md` (review-5 F4): cleared, likewise;
- Doc4 `repeatable-phase-b/spec.md` synopsis (review-5 F3): cleared by `7b82266`;
- Doc5 `docs/setup.md` troubleshooting (review-5 F2): cleared by `7b82266`;
- Doc5 `docs/reference/cli.md` installer row (review-5 F1): cleared by `7b82266`;
- Doc4 F3's sections: flagged, after `a9767d2` raised the brief versions;
- Doc5 the `changed.py` section: flagged, after `abe42a6` added `--scope`;
- Doc5 the `state_and_effects.py` section: flagged; the earlier verdict judged only its rule ids.

#### A2 (sampled): Except tuple coverage
- Mode: full
- Inspected: every `try` statement in the non-test source under `claude/skills/auditme/checks/` (found by an AST walk), with each body read for disk access, `json.load*`, `pd.read_*`, `.gz` and text decoding: core.py (stat, `read_text` with `except OSError, UnicodeDecodeError`), phaseb/architecture.py, batches.py, candidates.py, docrefs.py, ledger.py, testmap.py, rules/project_hygiene.py, changed.py, audit.py, phaseb.py. No translating decorator or `with` over a project contextmanager exists in the source, so there is no non-lexical envelope to check. Bodies that call `json.loads` on subprocess output or on text that was already read do not touch disk. `architecture.py:44` is a try/finally with no except. Test files were not checked: the question is about production envelopes.
- Hits: No hits

#### A3 (sampled): Domain-error layering
- Mode: full
- Inspected: every `raise` in the non-test source (from an AST walk). It raises `RootsError` (core.py), `PhaseBError` (phaseb/*, phaseb.py), `ChangedError` (changed.py), `SystemExit` at the entry points and `argparse.ArgumentTypeError` in the `type=` callables in phaseb.py. The `ValueError` raises in batches.py:181-198 are the sweep's (layer-has-domain-error-raises-stdlib, accepted), not mine.
- Hits: No hits

#### A5 (sampled): Two sources of truth
- Mode: full
- Inspected: state that a stored value and a parameter both hold. Plan depth: `--depth` in phaseb.py against `Plan.depth` in batches.py. `run_merge` refuses a mismatch, `depth_of` gives the default, and the listers' `depth` defaults are all `DEFAULT_DEPTH`. Brief version: computed from the brief and written to the plan. Roots: `[tool.auditme]` in core.py `cached_roots` against the `src_root` parameters. Each precedence is explicit and enforced.
- Hits: No hits

#### A6 (sampled): Stage method dual-path
- Mode: full
- Inspected: every class in the non-test source and every method that assigns to `self` (from an AST walk). Only `SiteCounter` (phaseb/architecture.py:95) has a method that both mutates and returns: `next` increments a counter and returns an int. It is not a pipeline-stage class, and it does not return a tuple. `IndexEntries` methods mutate and return None. `TestIndex.reverse` is a `functools.cached_property`.
- Hits: No hits

#### A7 (sampled): Constructor purity
- Mode: full
- Inspected: every `__init__`. In non-test source there is only `SiteCounter.__init__` (phaseb/architecture.py:102), which makes an empty Counter. The test files' `__init__`s were checked too: tests/test_project_hygiene.py `Result`/`LockResult` stubs assign constants, and the `__init__`s in test_state_and_effects.py and test_style_and_naming.py are fixture source strings, not code.
- Hits: No hits

#### A8 (sampled): Late dataclass mutation
- Mode: full
- Inspected: every dataclass in the non-test source. Most are `frozen=True`. Only `ClassInfo`, `IndexEntries` and `TestIndex` are not frozen, and I checked where each is constructed (docrefs.py:186, docrefs.py:265, testmap.py:343). I also grepped for attribute assignment on non-`self` names and for `object.__setattr__`: neither occurs. `IndexEntries` is filled only through its own methods (container updates, never `x.field = ...`), and changed copies go through `dataclasses.replace`.
- Hits: No hits

#### A9 (sampled): Pure-named function side effects
- Mode: full
- Inspected: every tracked `.py` file. AST pass over every function with a pure prefix (`get_`, `resolve_`, `find_`, `compute_`, `build_`, `load_`, `parse_`, `is_`, `has_`, `validate_`, `count_`, `check_`, `allocate_`), checked for direct I/O calls, and for I/O reached through project helpers. The I/O helpers were found by mapping every filesystem, subprocess, date, print and env line in source to the function that holds it, then following callers transitively. Every `check_` function in source is a member of `CHECKS` or `PROJECT_CHECKS` in `checks/auditme/registry.py`, so none is read as pure-named. `load_test_index` and `load_test_map` (`phaseb/testmap.py:288`, `:347`) read the package and test tree under the `root` they are given, so they are not hits. Test helpers with pure prefixes were read by hand.
- Hits:
  - `claude/skills/auditme/tests/phaseb/test_docrefs.py:206` - test helper `resolve_token` wraps `docrefs.read_name_targets`, which reads a tracked file to count its lines (through `read_path_targets` and `read_file_target`; it raises PhaseBError when the read fails). The production code names that path `read_`, and the wrapper renames it `resolve_`.

#### A10 (sampled): Predicate semantics
- Mode: full
- Inspected: the body and docstring of every `is_*`, `has_*` and `should_*` function in every tracked `.py` file (core, phaseb architecture/candidates/docrefs/testmap, rules duplication/error_handling/style_and_naming, the nested `is_domain` and `is_bound`, and the test helper `is_candidate_source`). In each one, every conjunct is part of the question its name asks, and the docstring states it.
- Hits: No hits

#### A12 (sampled): assert misuse
- Mode: full
- Inspected: grep for `assert` statements in every tracked `.py` file outside `tests/` directories. Every file outside them is non-test source.
- Hits: No hits (no `assert` statement outside test files)

#### A13 (sampled): Same value to multiple structural slots
- Mode: full
- Inspected: AST pass over every call to a capitalised callable (class or constructor) in every tracked `.py` file, flagging a non-constant expression passed to 2+ positional or keyword slots. Only one site matched: `phaseb/docrefs.py:281` `DocTarget(kind, rel, rel, 1, last_line)`. It sits in the explicit factory `path_target`, whose docstring and the `id` field comment ("'path' for a file or directory") document it, so it is not a hit.
- Hits: No hits

#### A14 (sampled): Repeated computation per request
- Mode: full
- Inspected: every call site of the project-state helpers (`audit_roots`, `cached_declared_roots`/`declared_roots`, `ruff_executable`, `read_pyproject`, `tracked_files`, `agents_document`, `corpus_index`, `corpus_py_files`, `extra_roots`, `load_test_index`, `entry_point_targets`, `run_git` and others), traced through each CLI or lister flow (`phaseb.py` run_* via `list_candidates` (one question per request), and the `audit.py` sweep driver). The sweep's `subprocess-without-memoisation` hits (`project_hygiene.py:44`, `:98`, `:219`) are excluded.
- Hits:
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py:50` - `capture_hits` calls `auditme.core.audit_roots(scope)` once per check in its loop. Together with `read_audited_files` (`:84`) and the lister's own call, one A1 request (`list_a1_candidates`, `:614-618`, three `A1_CHECKS`) resolves the roots 5 times, and one A17 request (`list_a17_candidates`, `:770-774`) resolves them 4 times. Only the `[tool.auditme]` read is cached (`cached_declared_roots`). Each call reassigns the `ROOT_MODULES` global, and an undeclared project rescans `src/` every time (`packages_under` + `extra_roots`). This is a candidate for resolving the roots once per lister.
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py:37` - `check_ruff` is a per-root `CHECKS` entry and calls `ruff_executable(scope)` on every root pass. `check_ruff_version` (`:217`) calls it once more. The result depends only on `scope`, yet one sweep resolves it once per root plus once (more than twice whenever the project has 2+ roots; this repository declares 5).

#### A15 (sampled): Duplicate constructor / serialisation logic
- Mode: full
- Inspected: AST count of the constructor call sites of every class defined in source, with their field sets. `Candidate` is built in three factories (`phaseb/candidates.py:255`, `:260`, `:265`), `DocTarget` in two (`phaseb/docrefs.py:276`, `:281`), and `Site`, `Scope`, `SiteCounter` and `Verdict` in 2-3 sites each. Every class built with substantially the same field set has no field defaults, so a new field fails at every site at once rather than drifting silently. `Verdict`'s second site (`ledger.py:54`) builds from `dataclasses.fields`, so it cannot drift. The error classes take one message argument each.
- Hits: No hits

#### A16 (sampled): CLI entry envelope
- Mode: full
- Inspected: `git ls-files` for any `cli/` directory and grep for `cappa` across the tracked `.py` files. No `cli/*.py` file is tracked. The only `cappa` mention is the rule text in `rules/error_handling.py`. The `run_*` functions in `checks/phaseb.py` are not in `cli/*.py`, so they are outside the question.
- Hits: No hits

#### A18 (sampled): Hot-path setup
- Mode: full
- Inspected: every tracked `.py` and `.sh` file, searched for callback methods (`def on_*`). The only `on_log` definitions are fixture source strings inside `claude/skills/auditme/tests/test_state_and_effects.py` (lines 821, 844), not code that runs.
- Hits: No hits

#### A20 (sampled): Mutable module-level singleton
- Mode: full
- Inspected: an AST listing of every module-level `dict`/`set`/`list` literal, comprehension or bare-constructor assignment in every tracked `.py` file, tests included. Each name was then grepped (whole word, which covers `from <module> import <name>` and `<module>.<name>`) across the whole tree, along with every `sys.modules[...]` use. Names checked: `SOURCE_CACHE`, `INDEX_CACHE`, `TAKES_DEPTH`, `STDLIB`, `DISK_IO_NAMES`, `MUTABLE_VALUE_SHAPES`, `MUTABLE_CONSTRUCTORS`, `STRFTIME_TOKENS`, `PARAMETRIC_NONBUILTIN_GENERICS`, `TYPING_DEPRECATED_ALIASES`, `RULE_HELP`, `COMMANDS`, `NAMES_HOOK`, and every test-module constant. Each is read only in its own module. `COMMANDS` also appears in `test_annotated_all.py`, but only inside fixture strings. The sweep's own sites (`core.py:29` `EMITTED`, `core.py:35` `UNREADABLE`, `candidates.py:59` `REGISTRY`, `candidates.py:61` `KINDS`) were left out as accepted sweep hits.
- Hits: No hits

#### A21 (sampled): Lazy init race
- Mode: full
- Inspected: every `if X is None:` in non-test code, every `global` statement (`core.py:454`, `core.py:799` rebind `ROOT_MODULES` when roots are read), and the module-level cache helpers `cached_bytes`, `cached_corpus_files`, `corpus_index` and `cached_source` in `core.py`. No tracked file uses `threading`, `concurrent`, `multiprocessing` or `asyncio`. Every run is a single-threaded CLI invocation, so no code path is called concurrently.
- Hits: No hits

#### A22 (sampled): Fall-through after partial handling
- Mode: full
- Inspected: an AST scan of every non-test function for an `if` branch that holds a `try` whose handler raises and that does not leave before the code after it. The only match is `changed.py:196` (`scope_records`). It re-raises as `ChangedError` and never falls through to retry. Also read every tracked shell script: `claude/hooks/auditme-stop.sh`, `bin/check-foreign-names.sh` and `bin/install-claude.sh`.
- Hits: No hits

#### A23 (sampled): Discarded multi-return
- Mode: full
- Inspected: every non-test function annotated to return a `tuple[...]`, and every call to one in the whole tree, flagged where the call is discarded, indexed, or unpacked with `_`. Also the dataclass returns `RunCheck`, `MergeResult` and `Plan`, with their call sites in `phaseb.py` and `batches.py`. Three kinds of site turned up. The indexed calls (`core.py:173`, `core.py:182`, `core.py:903`, `candidates.py:142`, `candidates.py:161`) are documented one-field accessors, and none of their dropped components changes how the kept one is used. The bare `registered(question)` at `candidates.py:151` is a validation call. `_` unpacks are explicitly named. `read_run_check(...).problems` (`batches.py:268`) reads a dataclass whose only field is `problems`.
- Hits: No hits

#### A24 (sampled): Identity of subprocess / shell-out calls
- Mode: full
- Inspected: every `subprocess.run` in non-test code. `docrefs.py:301` (`tracked_files`) runs once per `CorpusIndex.build`, and once in the Doc2 lister at `candidates.py:640`. Each `phaseb` command lists one question, so it runs once per request. `changed.py:64` (`run_git`) is called with different arguments at each call site; `read_base_ref` tries a different ref on each pass. `changed.py:236` runs the sweep once. `project_hygiene.py:106` runs a second, different command with `UV_NO_CONFIG` set. The shell git calls in `claude/hooks/auditme-stop.sh` each run on a different directory. The sweep's own sites (`project_hygiene.py:44`, `:98`, `:219`) were left out as accepted sweep hits.
- Hits: No hits

#### A25 (sampled): Shallow immutable wrapper
- Mode: full
- Inspected: every module-level `types.MappingProxyType(...)`, `frozenset(...)`, `tuple(...)` and tuple literal in every tracked `.py` file (AST listing). Their members are strings, AST node classes, check functions or tuples of strings. `ROOT_MODULES` (`core.py:305`) wraps `{}` and is rebound with `str` values. `ledger.py:27` `REQUIRED` is a tuple of field-name strings. No member is a `dict`/`list`/`set`, a mutable container one tuple deep, or an instance of a dataclass defined here without `frozen=True`.
- Hits: No hits

#### S1 (sampled): Type annotations on every signature
- Mode: full
- Inspected: every tracked non-test Python file (`git ls-files '*.py'` outside `tests/` directories), via `ruff check --isolated --select ANN` (ruff 0.17.4) and by reading; test files counted, not enumerated, as the question requires. Shell files have no signatures to annotate.
- Hits: No hits (non-test source: every signature annotated)
- Test count (files under a `tests/` directory, `ruff check --isolated --select ANN --statistics`): 130 missing parameter annotations (126 ANN001, 3 ANN003, 1 ANN002), 32 missing return annotations (30 ANN201, 2 ANN202); 10 modules affected, 24 of 34 test modules fully annotated. No AGENTS.md test-annotation exemption to drift-check.

#### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake
- Mode: full
- Inspected: every tracked Python file with `ruff check --isolated --select N`, plus a scan of function-local constant collections against `claude/rules/auditme/coding-standards.md` (Naming); variable and function names in `bin/check-foreign-names.sh`, `bin/install-claude.sh`, `claude/hooks/auditme-stop.sh`.
- Hits: No hits. Ruff's N806 reports function-local UPPER_SNAKE names (e.g. `state_and_effects.py:282 PURE_PREFIXES`), but each is a constant collection, which the coding standards name UPPER_SNAKE, and every function-local constant collection in the tree uses that form, so the tree is consistent. Shell scripts: script constants upper, working variables lower, functions lower_snake.

#### S3 (sampled): TYPE_CHECKING block placement
- Mode: full
- Inspected: every `if typing.TYPE_CHECKING:` block in tracked Python files (source and tests), compared with the last top-level import of its file.
- Hits: No hits. Every block uses `if typing.TYPE_CHECKING:` immediately after the module's imports; the indented occurrences in `tests/phaseb/test_t1_candidates.py:120` and `tests/test_imports_and_surfaces.py:163,747` are inside fixture source strings.

#### S4 (sampled): Project-specific rule files
- Mode: full
- Inspected: rules AGENTS.md references - `claude/rules/auditme/coding-standards.md`, `imports.md` (installed from `claude/rules/auditme`), the argparse allowance in `~/.claude/rules/python/argparse.md` that coding-standards.md points to, and the no-project-names rule. Checked the parts the sweep has no rule for: stdlib `logging` imports, `print()` outside CLI entry points, argparse use and its trailing-comma form, legacy typing, definitions in `__init__.py`; ran `bin/check-foreign-names.sh` over every in-scope file.
- Hits: No hits. argparse in `checks/audit.py`, `checks/phaseb.py`, `checks/changed.py` falls under the stdlib-only checker allowance, and every multi-argument call is one per line with a trailing comma; no `logging` import; the `print` in `auditme/core.py:60` is the checker's machine-readable JSON-lines output; the project-name check printed no match.

#### P1 (sampled): O(n^2) on real-size inputs
- Mode: full
- Inspected: every nested loop and multi-generator comprehension in non-test Python source (AST scan, then read each one whose inner iterable is a project-wide collection); shell scripts.
- Hits:
  - `claude/skills/auditme/checks/auditme/rules/duplication.py:616` - `check_duplicate_call_sequence` compares every function signature with every later one (`signatures[i + 1 :]`), O(F^2) pairs over all functions of a root, each surviving pair then running an O(n*m) LCS.
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py:352` - `check_asymmetric_exception_translation` scans the whole `function_index` with `endswith` for every call node in every file whose callee is not an exact key, O(calls x functions) over the tree; a short-name index (as `check_inconsistent_error_translation` builds with `short_to_full`) makes it a lookup.

#### P2 (sampled): Blocking I/O in hot paths
- Mode: full
- Inspected: every tracked Python and shell file for training loops, request handlers and callbacks; the checker is a batch CLI and the Stop hook (`claude/hooks/auditme-stop.sh`) runs the checker once per turn by design.
- Hits: No hits

#### P3 (sampled): Repeated expensive computation per request
- Mode: full
- Inspected: every non-test Python source file, for values recomputed inside loops whose inputs do not change (file walks, parses, globs, graph searches); sites the sweep reports under `subprocess-without-memoisation` excluded.
- Hits:
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py:446` - `check_sibling_error_no_common_base` rebuilds `caught_elsewhere` (an `ast.walk` and `ast.unparse` over every file of the root) once per `errors.py` file, though it depends only on `src_root`.
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:173` - `check_in_function_imports` calls `declared_root_modules()` (a glob, `iterdir` and `is_file` per entry of each top-level root) once per audited file; the result is the same for every file.
  - `claude/skills/auditme/checks/auditme/phaseb/testmap.py:231` - `TestIndex.refs` runs `reach(self.direct, [via], depth)` per test per direct target, recomputing the same breadth-first search for a function every test that calls it.

#### Sec1 (sampled): Secrets in source
- Mode: full
- Inspected: every tracked .py and .sh file (grep for api_key/password/secret/token assignments, read each match), `pyproject.toml`, `.pre-commit-config.yaml`, `.pre-commit-hooks.yaml`, `.github/workflows/ci.yml`, `.github/workflows/docs.yml` (the deploy token comes from `secrets.GITHUB_TOKEN`, not source)
- Hits: No hits

#### Sec2 (sampled): Input validation at system boundaries
- Mode: full
- Inspected: the CLI parsers and their validation in `claude/skills/auditme/checks/audit.py` (`--package` name check, `--extra-root` containment), `checks/changed.py` (`--base` refused when it starts with `-`, `repo_root`), `checks/phaseb.py` (`--question` via `registered_question`, `--depth` via `positive_int`, `--batch-size` checked in `plan_batches`), `[tool.auditme]` roots in `checks/auditme/core.py:declared_roots`, the Stop hook's JSON payload in `claude/hooks/auditme-stop.sh`, the arguments of `bin/check-foreign-names.sh` and `bin/install-claude.sh`
- Hits: No hits

#### Sec3 (sampled): Command injection
- Mode: full
- Inspected: every `subprocess` call (`checks/changed.py` run_git and sweep, `checks/auditme/rules/project_hygiene.py` ruff and uv calls, `checks/auditme/phaseb/docrefs.py` git ls-files): all argv lists, no `shell=True`, `--base` guarded against option injection; shell scripts `bin/check-foreign-names.sh` (quoted, `grep -F -e` and `--`), `bin/install-claude.sh` (quoted `exec uvx`), `claude/hooks/auditme-stop.sh` (quoted, payload read by `jq`, a project's own `changed.py` run only when it shares the installed checker's git directory)
- Hits: No hits

#### Sec4 (sampled): Path traversal
- Mode: full
- Inspected: `checks/audit.py` (`--package` must be a bare name, `--extra-root` checked with `path_inside`), `checks/auditme/core.py:declared_roots` (roots outside the project refused), `checks/auditme/phaseb/docrefs.py:read_path_targets` (`..` refused, only tracked files read), `checks/phaseb.py:ledger_path` (question restricted to registered names), `checks/auditme/phaseb/batches.py` (batch and result names formatted from integers)
- Hits: No hits

#### Sec5 (sampled): PII in logs
- Mode: full
- Inspected: every tracked .py and .sh file for `logging`/`logger.` calls (none in non-test code outside rule text and string literals) and for printed raw input
- Hits: No hits

#### T3 (sampled): Integration vs unit balance
- Mode: full
- Inspected: orchestrators and their tests - `checks/audit.py` (`tests/test_driver.py` runs `audit.main()` over fixture trees), `checks/changed.py` (`tests/test_changed.py::test_end_to_end_against_the_real_checker` and the real-sweep tests after it), `checks/phaseb.py` (`tests/phaseb/test_cli.py` runs candidates, plan, check, merge, report and dismiss as a subprocess), `claude/hooks/auditme-stop.sh` (`tests/test_stop_hook.py`), `bin/install-claude.sh` (`tests/test_install_claude.py`), `bin/check-foreign-names.sh` (`tests/test_check_foreign_names.py`), published hooks (`tests/test_published_hooks.py`)
- Hits: No hits

#### D1 (sampled): Declared in pyproject
- Mode: full
- Inspected: every top-level import in every tracked .py file (AST walk, stdlib filtered by `sys.stdlib_module_names`): third-party imports are `hypothesis` and `pytest`, both in the `dev` group of `pyproject.toml`; the rest (`audit`, `auditme`, `changed`, `conftest`, `phaseb`) are first-party
- Hits: No hits

#### D2 (sampled): Unused declarations
- Mode: full
- Inspected: `pyproject.toml` dependency groups against imports and commands - `hypothesis` and `pytest` imported in tests (pytest also run in `.github/workflows/ci.yml`); `ruff` run by `project_hygiene.py` as a subprocess's first argument and provided by the ruff-pre-commit repo in `.pre-commit-config.yaml`; `mkdocs` run in `.github/workflows/docs.yml`; `mkdocs-material` registers `material` in `mkdocs.themes` (its `entry_points.txt` in the uv cache) and `mkdocs.yml` names `theme: name: material`
- Hits: No hits

#### D3 (sampled): Lockfile coherence
- Mode: full
- Inspected: /tmp/audit-auditor.jsonl for a `lockfile-drift` hit (none); `uv lock --check` resolves cleanly
- Hits: No hits

#### Doc3 (sampled): README.md and AGENTS.md consistent
- Mode: full
- Inspected: README.md, AGENTS.md, docs/index.md, docs/concepts.md, docs/setup.md, docs/reference/cli.md, docs/reference/rules.md, docs/reference/skills.md, docs/guide/checker.md (AGENTS.md/README.md mentions); cross-checked against .pre-commit-hooks.yaml, .pre-commit-config.yaml, bin/install-claude.sh and the claude/ tree. README.md and AGENTS.md agree on the test command, the install script and what it links, the hooks and the agents-repository split; docs agree with both.
- Hits:
  - `AGENTS.md:31` - "install both hook types with" is followed (line 33) by a command naming three hook types (`pre-commit`, `pre-push`, `commit-msg`); the sentence contradicts its own command.

#### Spec review
- agents/specs/auditme-false-positives/spec.md - no gap
- agents/specs/listed-phase-b-architecture-questions/spec.md - no gap
- agents/specs/listed-phase-b-documentation-questions/spec.md - no gap
- agents/specs/listed-phase-b-test-questions/spec.md - no gap
- agents/specs/project-setup/spec.md - no gap
- agents/specs/raises-section-resolution/spec.md - no gap
- agents/specs/repeatable-phase-b/spec.md - no gap
- agents/specs/index.md - no gap (every spec listed; every relative link resolves)

## Prior findings re-verified

Review-5's F1, F2, F3, F5, F6 and F8 shipped in the review-5 task list and are confirmed in the code and docs. F4's two verdicts were judged again after the hash fix and are no longer flagged. F7 (`t1_reasons`) stays dismissed. No task list under `agents/tasks/audit-reviews/` has an incomplete task.

## Decisions

### D1. Leave the briefs as they are for the cases they do not settle

- **What is being decided:** whether to refine the Doc4 and Doc5 briefs so that U1-U5's kinds of case are settled by the brief, not by the default-verdict rule.
- **Background:** the default-verdict rule (2026-11-22) judges a case a brief leaves open as not a finding and has the reviewer report it, so each is still seen on the page. U1-U5 are five such cases this audit. Any brief change raises its version, so the next audit judges every candidate of that question again.
- **What it affects:** `claude/skills/auditme/phaseb/briefs/Doc4.md` and `Doc5.md`, and review-7's size: about 600 Doc candidates judged again if either brief changes.
- **Options:**
  - **Leave the briefs (recommended):** the rule already decides these cases the same way each time and the page shows them, so a re-judge of every Doc candidate would buy no change in outcome.
  - **Refine the briefs:** each kind becomes a written rule, and review-7 judges every Doc candidate again.

## Answers

Answered on the review page on 2026-11-22. Every item took the recommended option, with no comments.

| Item | Answer |
|---|---|
| F1-F9 | Fix |
| F10 | Dismiss (measured small) |
| U1-U5 | Not a finding |
| D1 | Leave the briefs |
