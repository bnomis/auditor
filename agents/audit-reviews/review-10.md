# Audit Review 10

**Date:** 2026-11-22
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`); the sampled questions ran on the lines changed since review-9
**Commit:** 6a237037d559d435a16424bbf36effd5ca78a8f3
**Script output:** /tmp/audit-auditor.jsonl (48 hits, 48 accepted, 0 unaccepted)
**Script version:** 1bb90d0b792eb64d904d311e8e5b2ca4e8c3b4088081ef14384e5bd4ef22a28d
**Convergence note:** no finding, no observation and no unsettled case. Measured on 2026-11-22: 61 listed candidates judged (T1 48, T2 2, Doc4 8, Doc5 3), no verdict changed; the sampled scope was two changed ranges, in `testmap.py` and its test. The next whole-tree audit is review-12.
**Review page:** https://claude.ai/artifact/KkS83hqfC6TdDrEZdpWQqV

## What is being reviewed and how

This is the checker repository's tenth audit of its own code. It found nothing: there is no item to answer. The page records the result; the review is committed as the record.

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 48 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 61 judged (T1 48, T2 2, Doc4 8, Doc5 3); every other listed question carried every verdict |
| `phaseb.py check` on every listed question | pass, no retries |
| Every sampled question returned a hit list or "no hits" | pass: no hits |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| Prior findings to re-verify | review-9 F1: shipped (`1e702f9`); `test_files` reads the per-file import index |

## Summary

The sweep reports 48 hits, all accepted. Phase B leaves no listed verdict open, and the sampled questions flag nothing. Nothing in the spec review's scope changed.

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits.

## Phase B findings (consolidated)

None.

## Phase B per-question results

Listed questions: the verdicts are in `agents/audit-reviews/ledger/`; `phaseb.py report <root> --question <Q>` prints the open ones. No listed question has any, and no verdict changed on re-judging.

### Sampled questions (changed lines since 2fb0d4b)

Questions not run here (excluded by the brief): A1, A4, A11, A17, A19, T1, T2, Doc1, Doc2, Doc4, Doc5. Spec review: no spec or doc changed since 2fb0d4b, nothing in scope. Sweep hit in scope (`testmap.py:360` passthrough-shim, accepted) is outside these line ranges and not re-reported.

#### A2 (sampled): Except tuple coverage
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); no `try/except`, translating decorator or contextmanager `with` in scope
- Hits: No hits

#### A3 (sampled): Domain-error layering
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); no `raise` statement in scope
- Hits: No hits

#### A5 (sampled): Two sources of truth
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `TestIndex` fields `root`/`tree_roots` and `sites`/`by_id` are both derived once in `load_test_index` and never compete for precedence; no config field paired with a method parameter
- Hits: No hits

#### A6 (sampled): Stage method dual-path
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `TestIndex` is not a pipeline-stage class; the `cached_property` members memoise, they do not return-and-mutate a named field
- Hits: No hits

#### A7 (sampled): Constructor purity
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `TestIndex` has no hand-written `__init__` (dataclass-generated)
- Hits: No hits

#### A8 (sampled): Late dataclass mutation
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); `TestRef` built at 215 and copied with `dataclasses.replace` at 231, never mutated
- Hits: No hits

#### A9 (sampled): Pure-named function side effects
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); no function in scope has a pure prefix (`mirrored` does `is_file` but is not pure-named)
- Hits: No hits

#### A10 (sampled): Predicate semantics
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); no `is_`/`has_`/`should_` function in scope
- Hits: No hits

#### A12 (sampled): assert misuse
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); no `assert` in non-test scope (the test file's asserts are in a test file)
- Hits: No hits

#### A13 (sampled): Same value to multiple structural slots
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); `TestRef(...)` at 215-223 passes distinct values to each slot
- Hits: No hits

#### A14 (sampled): Repeated computation per request
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`) and its callers `candidates.py:775,785,1035`; `importers` and `reverse` are cached once per index, `reach` per `via` is memoised in `refs`
- Hits: No hits

#### A15 (sampled): Duplicate constructor / serialisation logic
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); `TestRef` is constructed at one site (215) and derived by `replace`
- Hits: No hits

#### A16 (sampled): CLI entry envelope
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); no `cli/*.py` `run_*` function in scope
- Hits: No hits

#### A18 (sampled): Hot-path setup
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); no callback methods in scope
- Hits: No hits

#### A20 (sampled): Mutable module-level singleton
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); no module-level container in scope
- Hits: No hits

#### A21 (sampled): Lazy init race
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); no module-scope `if X is None: X = ...`; `cached_property` is per instance
- Hits: No hits

#### A22 (sampled): Fall-through after partial handling
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); no branch chain mixing raise and return
- Hits: No hits

#### A23 (sampled): Discarded multi-return
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); `by_module, by_name = self.importers` (280) uses both; test 580 discards a `list`, not a tuple/dataclass
- Hits: No hits

#### A24 (sampled): Identity of subprocess / shell-out calls
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); no subprocess or git call
- Hits: No hits

#### A25 (sampled): Shallow immutable wrapper
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); no module-level wrapped container in scope
- Hits: No hits

#### S1 (sampled): Type annotations on every signature
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`)
- Hits: No hits in non-test source (every signature in scope annotated). Test-file count (in-scope range only): 0 missing parameter annotations, 0 missing return annotations, 0 modules affected, 1 module fully annotated in scope (`test_testmap.py`)

#### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`)
- Hits: No hits

#### S3 (sampled): TYPE_CHECKING block placement
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `collections.abc` annotations resolve via the file's top-of-file `TYPE_CHECKING` block (line 19, out of scope), same idiom as the tree
- Hits: No hits

#### S4 (sampled): Project-specific rule files
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`) against the rule `AGENTS.md` references (No project names, enforced by the `no-project-names` hook); fixtures use neutral names (`pkg`, `mod`, `mid`)
- Hits: No hits

#### P1 (sampled): O(n^2) on real-size inputs
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`) with its callers `candidates.py:775,1035` (one `test_files` call per candidate site). `test_files` scans `self.aliases` per site (sites x re-exports: thousands x at most hundreds of cheap compares, tens of ms); `refs` is bounded by output size
- Hits: No hits

#### P2 (sampled): Blocking I/O in hot paths
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `mirrored` stat calls (`is_file`) run once per candidate in an audit planner, not in a training loop, handler or callback
- Hits: No hits

#### P3 (sampled): Repeated expensive computation per request
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`) with callers `candidates.py:775,785`. `caller_sites` (a depth-bounded `reach`) runs in both `test_files` and `callers` for each T1 candidate, and `mirrored` repeats the same 2-per-tree-root `is_file` stats for every function of one module; judged on a project with hundreds of source and test files, both are microseconds-to-tens-of-ms against the per-candidate whole-file reads in `read_test_files`, so not expensive
- Hits: No hits

#### Sec1 (sampled): Secrets in source
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`)
- Hits: No hits

#### Sec2 (sampled): Input validation at system boundaries
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); no CLI argument, HTTP body or user path enters in scope
- Hits: No hits

#### Sec3 (sampled): Command injection
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); no subprocess or shell call
- Hits: No hits

#### Sec4 (sampled): Path traversal
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `mirrored` joins parts of a repo-relative source path found by the tree walk to a test-tree root, not a user-supplied path
- Hits: No hits

#### Sec5 (sampled): PII in logs
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); no logging
- Hits: No hits

#### T3 (sampled): Integration vs unit balance
- Mode: changed lines since 2fb0d4b
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/testmap.py:180-298` (line 180 widened to `reach`, 181-188; 191-298 is the `TestIndex` class: `refs`, `importers`, `reverse`, `caller_sites`, `callers`, `test_files`, `mirrored`); `claude/skills/auditme/tests/phaseb/test_testmap.py:562-583` (`test_each_test_files_imports_are_computed_once_however_many_functions_are_listed`, with its inner `counting`); no pipeline orchestrator in scope
- Hits: No hits

#### D1 (sampled): Declared in pyproject
- Mode: changed lines since 2fb0d4b
- Inspected: No dependency file changed since 2fb0d4b; no import line in scope
- Hits: Nothing in scope

#### D2 (sampled): Unused declarations
- Mode: changed lines since 2fb0d4b
- Inspected: No dependency file changed since 2fb0d4b
- Hits: Nothing in scope

#### D3 (sampled): Lockfile coherence
- Mode: changed lines since 2fb0d4b
- Inspected: No dependency file or lockfile changed since 2fb0d4b
- Hits: Nothing in scope

#### Doc3 (sampled): README.md and AGENTS.md consistent
- Mode: changed lines since 2fb0d4b
- Inspected: Neither `README.md` nor `AGENTS.md` changed since 2fb0d4b
- Hits: Nothing in scope

## Prior findings re-verified

Review-9's F1 shipped in the review-9 task list: `TestIndex.test_files` looks its modules up in the `importers` index built once per run, and `test_testmap.py` checks that each test file's names are computed once. No task list under `agents/tasks/audit-reviews/` has an incomplete task.

## Decisions

None this review.

## Answers

Nothing to answer.
