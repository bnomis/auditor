# Audit Review 7

**Date:** 2026-11-22
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`); the sampled questions ran on the lines changed since review-6
**Commit:** 7615d7ffa639b2c7a8af40308b949c50f7bf70f2
**Script output:** /tmp/audit-auditor.jsonl (48 hits, 48 accepted, 0 unaccepted)
**Script version:** 5d34604984d6779110ff32f37bf49065e4de9416d9fc5bb0c6e0abe33723a2c0
**Convergence note:** the first audit whose sampled questions judged only changed lines (`changed.py --scope`, widened to each enclosing function). Measured on 2026-11-22: 352 listed candidates judged, 14 changed files in the sampled scope. Every review-6 finding cleared, and no brief changed, so nothing was judged again for a brief change. Ten of eleven listed questions have no open finding. The four findings below are all in lines or docs the review-6 and review-5 task lists touched.
**Review page:** https://claude.ai/artifact/PDvdpYzVf7r714sxu5Qv2x

## What is being reviewed and how

This is the checker repository's seventh audit of its own code. The sweep is clean, and so is every listed question but Doc5. For each finding, choose Fix (it becomes a task) or Dismiss (with your reason). O1 is something a reviewer saw that no checklist question asks about: Fix makes it part of the task list, Dismiss drops it. U1 is a case the Doc5 brief does not settle, which the default-verdict rule (2026-11-22) judged not a finding.

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 48 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 352 judged (A1 23, A4 16, A19 1, T1 212, T2 19, Doc1 1, Doc2 1, Doc4 59, Doc5 20); A11 and A17 carried every verdict |
| `phaseb.py check` on every listed question | pass, no retries |
| Every sampled question returned a hit list or "no hits" | pass |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| `cached_source`'s dismissed A1 verdict carried across a content change | pass |
| Prior findings to re-verify | review-6 F1-F9: shipped and cleared; F10 stays dismissed |

## Summary

The sweep reports 48 hits, all accepted. Phase B leaves 2 listed verdicts open (Doc5). The sampled questions flag A23 1 and S4 1. The spec review finds no gap.

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits.

## Phase B findings (consolidated)

### F1. Two places still say sampled questions run on changed files (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed). **Severity:** low.
- **Locations:**
  - `docs/reference/skills.md:32`: "a sampled question runs on the files changed since the previous review";
  - `claude/skills/auditme/SKILL.md:252`, the completion gate: "Every sampled question ran in its cadence's mode (changed files, ...)". Doc5 does not cover `SKILL.md`; it is named so the fix reaches both.
- **Description:** since Task 5 of the review-5 task list (`abe42a6`), the Sampled cadence section gives each sampled reviewer only the changed lines from `changed.py --scope`. Both lines predate it.
- **Recommendation:** say "the lines changed since the previous review, each widened to its enclosing function" in both.

### F2. The `silent-self-mutation` row leaves out the prefix exemption (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed). **Severity:** low.
- **Location:** `docs/guide/checker.md:294`.
- **Description:** `check_silent_self_mutation` (`state_and_effects.py:148`) also exempts a method whose name starts with one of the listed words and `_` (`update_cache`). Review-6's F6 fix added `__post_init__` and `__setattr__`; this reviewer read the rule further.
- **Recommendation:** add the prefix form to the row.

### F3. A root lookup drops the modes with a bare subscript (A23)

- **Category:** A. **Question:** A23 (sampled). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/phaseb/architecture.py:50`, added by Task 4 of the review-6 task list.
- **Description:** `cached_roots(scope)[0]` drops each root's mode without naming it. The checks it runs still get the modes only because `cached_roots` sets `auditme.core.ROOT_MODULES` as a side effect. The other callers name both parts (`core.py:829`, `docrefs.py:183`).
- **Recommendation:** unpack it as `roots, _modes = ...`, as the other callers do.

### F4. A `contextlib.suppress(Exception)` swallows any failure (S4)

- **Category:** S. **Question:** S4 (sampled). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/rules/error_handling.py:418`, in `check_sibling_error_no_common_base`.
- **Description:** the suppress wraps `ast.unparse(base)`; the project's coding standards (`claude/rules/auditme/coding-standards.md`) say unexpected exceptions propagate. The line is older code, in scope because Task 4 of the review-6 task list changed its function.
- **Recommendation:** drop the suppress, or catch only the exception `ast.unparse` is known to raise for a base expression, with a test.

### O1. Comments describe a scan that never ran (outside the checklist)

- **Category:** none. **Question:** none (observed by the S and P reviewer). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/rules/error_handling.py:442-446`.
- **Description:** the comments speak of a sibling "not caught together by any call site". Before Task 4 of the review-6 task list the function built a table of caught exceptions and never read it; Task 4 deleted the table, so the check's output did not change (checked on 2026-11-22 against `996bbb3`), but the comments still describe the matching.
- **Recommendation:** fix it with F4: make the comments say what the check does (one finding per `errors.py` holding two or more unrelated error roots).

### U1. A row's normal-case exit beside an exit table (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed, unsettled). **Severity:** low.
- **Location:** `docs/reference/cli.md:208`.
- **Description:** the `--scope` row says "Exit `0`"; it exits 1 on the failures the section's exit table at line 231 lists. The brief does not say whether a row is judged alone or with the section's table.
- **Recommendation:** dismiss: the section's exit table states the failures; not a finding under the default-verdict rule.

## Phase B per-question results

Listed questions: the verdicts are in `agents/audit-reviews/ledger/`; `phaseb.py report <root> --question <Q>` prints the open ones. Every listed question but Doc5 has none.

Verdicts that changed on re-judging, each with the commit that changed what it judged:
- A1 and T1 `core.py::cached_bytes` (review-6 F1): cleared by `93b95e0`;
- T2 `changed.py` `enclosing_ranges`, `merge_ranges`, `widen` (review-6 F2): cleared by `84f1b42`;
- Doc4 the three specs' brief-version lines and `read_name_targets` (review-6 F3, F4): cleared by `df88e6a`;
- Doc5 `docs/reference/cli.md` `changed.py` section (review-6 F5): cleared by `df88e6a`;
- Doc5 `docs/guide/checker.md` `state_and_effects.py` (review-6 F6): its two names cleared by `df88e6a`; flagged again for F2;
- Doc5 `docs/reference/skills.md` `/auditme`: flagged (F1), after `abe42a6`.

#### A2 (sampled): Except tuple coverage
- Mode: changed lines since 996bbb3
- Inspected: try/except blocks in range: core.py `cached_bytes` (stat + read_bytes, `except OSError`, no decode); architecture.py `capture_hits` (inner try runs checks, `except Exception`; `json.loads` sits under a try/finally with no except, so no tuple to judge); error_handling.py `contextlib.suppress(Exception)` around `ast.unparse` (no disk/parser).
- Hits: No hits

#### A3 (sampled): Domain-error layering
- Mode: changed lines since 996bbb3
- Inspected: Every raise in range: core.py:103 `CachedReadError` (domain, subclass of OSError); architecture.py:53 `PhaseBError` (domain). Tests excluded.
- Hits: No hits

#### A5 (sampled): Two sources of truth
- Mode: changed lines since 996bbb3
- Inspected: Config-vs-parameter pairs in range: `capture_hits` (scope only), `declared_root_modules` (reads `ROOT_MODULES` only), `ruff_executable` (scope only), `cached_bytes`.
- Hits: No hits

#### A6 (sampled): Stage method dual-path
- Mode: changed lines since 996bbb3
- Inspected: Methods in range: testmap.py `TestIndex.refs` (returns, does not mutate self).
- Hits: No hits

#### A7 (sampled): Constructor purity
- Mode: changed lines since 996bbb3
- Inspected: No `__init__` in any range.
- Hits: No hits

#### A8 (sampled): Late dataclass mutation
- Mode: changed lines since 996bbb3
- Inspected: Dataclass constructions in range: testmap.py `TestRef(...)` at 220 (copied via `dataclasses.replace`, never mutated).
- Hits: No hits

#### A9 (sampled): Pure-named function side effects
- Mode: changed lines since 996bbb3
- Inspected: Pure-prefixed names in range: `check_sibling_error_no_common_base` (registered in registry.py:31, so not pure-named). `cached_bytes`, `capture_hits`, `declared_root_modules`, `ruff_executable`, `read_token` carry no pure prefix.
- Hits: No hits

#### A10 (sampled): Predicate semantics
- Mode: changed lines since 996bbb3
- Inspected: No `is_`/`has_`/`should_` function defined in any range.
- Hits: No hits

#### A12 (sampled): assert misuse
- Mode: changed lines since 996bbb3
- Inspected: Non-test ranges contain no `assert`.
- Hits: No hits

#### A13 (sampled): Same value to multiple structural slots
- Mode: changed lines since 996bbb3
- Inspected: Constructor calls in range: `TestRef(...)`, `CachedReadError(...)`, `PhaseBError(...)`, `hypothesis.strategies.tuples(LINE, LINE)` in test_changed.py:466 (two independent draws, not distinguishable structural slots).
- Hits: No hits

#### A14 (sampled): Repeated computation per request
- Mode: changed lines since 996bbb3
- Inspected: Project-state helpers called in range: `cached_roots` (per check in `capture_hits`, memoised in INDEX_CACHE); `reach` memoised per `via` in `refs`; `declared_root_modules` and `ruff_executable` memoised.
- Hits: No hits

#### A15 (sampled): Duplicate constructor / serialisation logic
- Mode: changed lines since 996bbb3
- Inspected: Constructions in range: `TestRef` built once per test in `refs`, variants via `dataclasses.replace`; emit calls are keyword calls to a function, not a class.
- Hits: No hits

#### A16 (sampled): CLI entry envelope
- Mode: changed lines since 996bbb3
- Inspected: No file under `cli/` in scope.
- Hits: No hits

#### A18 (sampled): Hot-path setup
- Mode: changed lines since 996bbb3
- Inspected: No callback method (`on_*`) in any range.
- Hits: No hits

#### A20 (sampled): Mutable module-level singleton
- Mode: changed lines since 996bbb3
- Inspected: Module-level assignments in range: core.py:916 is a string entry of `__all__`; project_hygiene.py:9 is an import; test_changed.py module-level `LINE`, `SPANS`, `SCOPES`, `KINDS`, `DECORATORS`, `NODES` are hypothesis strategies, not dict/set/list containers.
- Hits: No hits

#### A21 (sampled): Lazy init race
- Mode: changed lines since 996bbb3
- Inspected: `if key not in INDEX_CACHE: ...` patterns in `cached_bytes`, `ruff_executable`, `declared_root_modules`; grep of checks/ finds no threading, concurrent.futures or multiprocessing use, so no concurrent caller.
- Hits: No hits

#### A22 (sampled): Fall-through after partial handling
- Mode: changed lines since 996bbb3
- Inspected: if/else chains in range: error_handling.py 427-439 (all branches append, none raise); `ruff_executable`; `declared_root_modules`. None raise in one branch and fall through to another.
- Hits: No hits

#### A23 (sampled): Discarded multi-return
- Mode: changed lines since 996bbb3
- Inspected: Calls returning tuples in range: `cached_roots` (architecture.py:50), `TestIndex.reached` items, `rooted_at_stdlib[0]` unpacked with `_` (error_handling.py:451), `indexed` fixture unpacked in test_docrefs.py. Compared with the other `cached_roots` callers (core.py:829 `roots, modes = ...`, docrefs.py:183 `roots, _ = ...`).
- Hits: `claude/skills/auditme/checks/auditme/phaseb/architecture.py:50` - `auditme.core.cached_roots(scope)[0]` silently drops the per-root mode mapping by subscript; the checks it runs depend on that mode only through `cached_roots` rebinding `auditme.core.ROOT_MODULES` as a side effect (the other callers name it: `roots, modes` at core.py:829, `roots, _` at docrefs.py:183)

#### A24 (sampled): Identity of subprocess / shell-out calls
- Mode: changed lines since 996bbb3
- Inspected: No `subprocess.run` or git shell-out inside any range (`run_git` in test_docrefs.py:190-203 is outside the ranges).
- Hits: No hits

#### A25 (sampled): Shallow immutable wrapper
- Mode: changed lines since 996bbb3
- Inspected: No `MappingProxyType`/`frozenset`/`tuple` module-level wrapper in any range (core.py:307 `ROOT_MODULES` is outside the ranges).
- Hits: No hits

#### S1 (sampled): Type annotations on every signature
- Mode: changed lines since 996bbb3
- Inspected: every scope range in `scope.jsonl`; each `def` signature in the non-test ranges (`core.py` 87-104, `phaseb/architecture.py` 34-60, `phaseb/testmap.py` 213-237, `rules/error_handling.py` 383-461, `rules/imports_and_surfaces.py` 121-140, `rules/project_hygiene.py` 14-29) and in the test ranges.
- Hits: No hits in non-test source.
- Test files (count only, not hits): in `claude/skills/auditme/tests/phaseb/test_docrefs.py` 206-297, 17 missing parameter annotations and 15 missing return annotations (`read_token`'s `indexed`; `test_one_index_build_resolves_the_roots_once` and its nested `counting`; the 13 `read_token` tests from `test_tracked_path_relative_to_root` to `test_each_target_carries_path_and_lines`). Modules affected: 1 (`test_docrefs.py`). Modules fully annotated in their scope ranges: 7 (`test_architecture_candidates.py`, `test_testmap.py`, `test_changed.py`, `test_core.py`, `test_error_handling.py`, `test_imports_and_surfaces.py`, `test_project_hygiene.py`).

#### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake
- Mode: changed lines since 996bbb3
- Inspected: every name defined or assigned in the scope ranges (`CachedReadError`, `cached_bytes`, `capture_hits`, `refs`, `declared_root_modules`, `ruff_executable`, module constants `LINE`, `SPANS`, `SCOPES`, `KINDS`, `DECORATORS`, `NODES`, type alias `Node`, test helpers and locals).
- Hits: No hits

#### S3 (sampled): TYPE_CHECKING block placement
- Mode: changed lines since 996bbb3
- Inspected: scope ranges of every file; the only `TYPE_CHECKING` blocks in these modules (`rules/error_handling.py:12`, `rules/imports_and_surfaces.py:11`, `phaseb/testmap.py:19`) lie outside the ranges; no range adds or moves one.
- Hits: No hits

#### S4 (sampled): Project-specific rule files
- Mode: changed lines since 996bbb3
- Inspected: `claude/rules/auditme/coding-standards.md`, `imports.md`, `dependencies.md` (installed by `bin/install-claude.sh`, named in AGENTS.md) and the AGENTS.md no-project-names rule, against every scope range (full import paths, f-strings, no leading underscores, naming, error handling, comments, logging; fixture names are neutral: `pkg`, `probe`, `Probe`, `AppSettings`, `AlphaError`, `BetaError`).
- Hits:
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py:418` - `with contextlib.suppress(Exception): base_names.append(ast.unparse(base))` silently swallows any exception, against coding-standards.md "Error handling: let unexpected exceptions propagate rather than silently catching them"; `ast.unparse` of a parsed base has no expected failure to tolerate.
- Note (outside the enumeration, not a hit): the comments at `rules/error_handling.py:442-446` ("Emit one finding per class whose sibling is not caught together by any call site", "if a class C is caught at site S ...") describe the except-clause scan this change deleted; the code now emits one finding per file without looking at catch sites.

#### P1 (sampled): O(n^2) on real-size inputs
- Mode: changed lines since 996bbb3
- Inspected: loops in all scope ranges; `check_sibling_error_no_common_base` (rebuilds `sibling_names` per class at 433, quadratic only in the number of `*Error` classes in one `errors.py`, a handful on real projects); `TestIndex.refs` (per-test loops over reached targets, with `reach` now memoised per `via` in `reached_from`); `capture_hits` (checks x roots, linear).
- Hits: No hits

#### P2 (sampled): Blocking I/O in hot paths
- Mode: changed lines since 996bbb3
- Inspected: I/O in scope ranges (`cached_bytes` stat/read, `declared_root_modules` glob/iterdir, `ruff_executable` is_file/access); none sits in a training loop, request handler or callback, and each is cached per run.
- Hits: No hits

#### P3 (sampled): Repeated expensive computation per request
- Mode: changed lines since 996bbb3
- Inspected: `capture_hits` (calls `auditme.core.cached_roots(scope)` once per check, a cached lookup; the test at `test_architecture_candidates.py:901` asserts one `audit_roots` resolution), `refs` (`reach` memoised in `reached_from`), `check_sibling_error_no_common_base` (the per-errors-file walk of the whole root was removed), `declared_root_modules` and `ruff_executable` (cached in `INDEX_CACHE`), `cached_bytes` (one `stat` per call, read once per mtime/size).
- Hits: No hits

#### Sec1 (sampled): Secrets in source
- Mode: changed lines since 996bbb3
- Inspected: every string literal in the scope ranges.
- Hits: No hits

#### Sec2 (sampled): Input validation at system boundaries
- Mode: changed lines since 996bbb3
- Inspected: scope ranges for CLI args, HTTP bodies and user file paths; none parses a command line or request; paths come from the audit scope and the project's declared roots.
- Hits: No hits

#### Sec3 (sampled): Command injection
- Mode: changed lines since 996bbb3
- Inspected: `ruff_executable` (`rules/project_hygiene.py:14-29`) returns a fixed path under the scope (`.venv/bin/ruff`) or the literal `ruff`, used as an argv element with no shell; no other subprocess call in the ranges.
- Hits: No hits

#### Sec4 (sampled): Path traversal
- Mode: changed lines since 996bbb3
- Inspected: path joins in scope ranges (`scope / '.venv' / 'bin' / 'ruff'`, `p / '__init__.py'`, `cached_bytes(path)` callers' paths); none joins user-supplied text to a project path.
- Hits: No hits

#### Sec5 (sampled): PII in logs
- Mode: changed lines since 996bbb3
- Inspected: scope ranges for logging calls; none logs; `CachedReadError` message holds only a file path.
- Hits: No hits

#### T3 (sampled): Integration vs unit balance
- Mode: changed lines since 996bbb3
- Inspected: orchestrators in scope - `capture_hits` (runs sweep checks over every root; exercised end to end with real checks by existing lister tests and by `test_capture_hits_resolves_the_audit_roots_once_for_all_its_checks`), `TestIndex.refs` (end to end through `load_test_index` in `test_testmap.py:586`); the other ranges are helpers and single checks.
- Hits: No hits

#### D1 (sampled): Declared in pyproject
- Mode: changed lines since 996bbb3
- Inspected: `git -C /Users/simonb/src/auditor diff 996bbb3 HEAD -- pyproject.toml uv.lock .pre-commit-config.yaml` (empty); third-party imports in the scope ranges (`hypothesis`, `pytest` in `tests/test_core.py:15-17`), both already used by the test suite before this range.
- Hits: No hits

#### D2 (sampled): Unused declarations
- Mode: changed lines since 996bbb3
- Inspected: the same dependency diff (empty: no declaration added or removed).
- Hits: No hits

#### D3 (sampled): Lockfile coherence
- Mode: changed lines since 996bbb3
- Inspected: the same dependency diff (empty); no lockfile-drift hit in `/tmp/audit-auditor.jsonl`.
- Hits: No hits

#### Doc3 (sampled): README.md and AGENTS.md consistent
- Mode: changed lines since 996bbb3
- Inspected: `git diff 996bbb3 HEAD -- AGENTS.md README.md docs/` (AGENTS.md:29-33, the "No project names" paragraph with its hook-install command; docs/guide/checker.md:294 and docs/reference/cli.md:226-231, neither part of README.md or AGENTS.md); README.md in full, which has no hook-install instruction or other counterpart to the changed AGENTS.md line, so nothing for it to contradict. README.md has no changed lines.
- Hits: No hits

#### Spec review
- agents/specs/listed-phase-b-architecture-questions/spec.md - no gap (every template section is present and non-empty, API has a python block, all 8 relative links resolve)
- agents/specs/listed-phase-b-documentation-questions/spec.md - no gap (every template section is present and non-empty, API has a python block, both relative links resolve)
- agents/specs/listed-phase-b-test-questions/spec.md - no gap (every template section is present and non-empty, API has a python block, all 6 relative links resolve)
- agents/specs/repeatable-phase-b/spec.md - no gap (every template section is present and non-empty, API has a python block, no relative links; the review files it cites in `agents/reviews/` exist)

## Prior findings re-verified

Review-6's F1-F9 shipped in the review-6 task list and their verdicts cleared on re-judging (above); F7 (`AGENTS.md:32`) and F8 (`read_token`) were confirmed by reading the files. F10 stays dismissed. No task list under `agents/tasks/audit-reviews/` has an incomplete task.

## Decisions

None this review.

## Answers

Answered on the review page on 2026-11-22. Every item took the recommended option, with no comments.

| Item | Answer |
|---|---|
| F1-F4 | Fix |
| O1 | Fix |
| U1 | Not a finding |
