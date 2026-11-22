# Audit Review 8

**Date:** 2026-11-22
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`); the sampled questions ran on the lines changed since review-7
**Commit:** 3cef62b1ae2d782dc0f103b8c7a9b0daacc38d00
**Script output:** /tmp/audit-auditor.jsonl (48 hits, 48 accepted, 0 unaccepted)
**Script version:** 20aa7a3a0a8dd524a8eb5827e8d68d769146917bc985c2797c6d969db3b584c1
**Convergence note:** the first audit with no finding. Measured on 2026-11-22: 130 listed candidates judged (A1, A11, A17, Doc1 and Doc2 had none to judge), three changed line ranges in the sampled scope. Every review-7 finding cleared, no verdict changed on unchanged text, and no brief changed. The items are three readings the Doc5 brief does not settle, all on one table row, judged not findings, and one observation outside the sampled scope (O1).
**Review page:** https://claude.ai/artifact/E5S3GT3W5wMfhfnxo6HLkE

## What is being reviewed and how

This is the checker repository's eighth audit of its own code, and the first with no finding. The page asks about O1, the pattern review-7's F4 fixed, still present outside this audit's scope, and about U1-U3: cases the Doc5 brief does not settle, which the default-verdict rule (2026-11-22) judged not findings. Keep that, or flag one to make it a finding.

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 48 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 130 judged (A4 2, A19 1, T1 82, T2 4, Doc4 29, Doc5 12); A1, A11, A17, Doc1 and Doc2 carried every verdict |
| `phaseb.py check` on every listed question | pass, no retries |
| Every sampled question returned a hit list or "no hits" | pass: no hits |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| Prior findings to re-verify | review-7 F1-F4 and O1: shipped and cleared |

## Summary

The sweep reports 48 hits, all accepted. Phase B leaves no listed verdict open, and the sampled questions flag nothing. The spec review finds no gap.

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits.

## Phase B findings (consolidated)

### O1. Six more `contextlib.suppress(Exception)` sites, outside the sampled scope

- **Category:** S. **Question:** S4 (seen outside the sampled scope, by grep on 2026-11-22). **Severity:** low.
- **Locations:**
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py:237`, `:1026`, `:1274`;
  - `claude/skills/auditme/checks/auditme/rules/state_and_effects.py:555`, `:1047`, `:1323`.
- **Description:** review-7's F4 removed the same pattern from `check_sibling_error_no_common_base`; these sites are in functions no change has touched since, so this audit's changed-lines scope did not reach them. Review-9 runs on the whole tree and would report them.
- **Recommendation:** fix them now, as F4 was fixed (remove each, or catch only the exception the wrapped call is known to raise, with a test), so review-9 does not reopen the pattern.

### U1. "A setter" in the `silent-self-mutation` row (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed, unsettled). **Severity:** low.
- **Location:** `docs/guide/checker.md:294`.
- **Description:** the row exempts "a setter"; `check_silent_self_mutation` (`claude/skills/auditme/checks/auditme/rules/state_and_effects.py:150`) exempts a method whose name starts with `set_`, not a property setter or a `setX` name.
- **Recommendation:** dismiss: "a setter" reads fairly as a `set_` method in a Python codebase; not a finding under the default-verdict rule.

### U2. Case-insensitive matching in the same row (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed, unsettled). **Severity:** low.
- **Location:** `docs/guide/checker.md:294`.
- **Description:** the check lower-cases a method's name before matching (`state_and_effects.py:146`), so `Clear` is exempt too; the row lists lower-case names only.
- **Recommendation:** dismiss: Python method names are lower case by convention, so the row describes every name the check will meet; not a finding under the default-verdict rule.

### U3. `__init__` in the same row (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed, unsettled). **Severity:** low.
- **Location:** `docs/guide/checker.md:294`.
- **Description:** the check also skips `__init__` (`state_and_effects.py:144`), which the row does not list.
- **Recommendation:** dismiss: the row is about reassigning an attribute after construction, which `__init__` cannot do; not a finding under the default-verdict rule.

## Phase B per-question results

Listed questions: the verdicts are in `agents/audit-reviews/ledger/`; `phaseb.py report <root> --question <Q>` prints the open ones. No listed question has any.

Verdicts that changed on re-judging, each with the commit that changed what it judged:
- Doc5 `docs/guide/checker.md` `state_and_effects.py` (review-7 F2): cleared by `f114f50`;
- Doc5 `docs/reference/skills.md` `/auditme` (review-7 F1): cleared by `f114f50`.

#### A2 (sampled): Except tuple coverage
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61) - the only try/except (body runs the checks; `except Exception` satisfies); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) has no try; its `json.loads` in capture_hits sits outside any except
- Hits: No hits

#### A3 (sampled): Domain-error layering
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - the only raise is `PhaseBError`, the phaseb domain error
- Hits: No hits

#### A5 (sampled): Two sources of truth
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454)
- Hits: No hits

#### A6 (sampled): Stage method dual-path
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - module functions, no pipeline-stage class
- Hits: No hits

#### A7 (sampled): Constructor purity
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - no `__init__` in range
- Hits: No hits

#### A8 (sampled): Late dataclass mutation
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - no dataclass constructed in range
- Hits: No hits

#### A9 (sampled): Pure-named function side effects
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454); `check_sibling_error_no_common_base` reads files but is a member of `CHECKS` in `checks/auditme/registry.py:31`, so not read as pure-named
- Hits: No hits

#### A10 (sampled): Predicate semantics
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - no predicate functions
- Hits: No hits

#### A12 (sampled): assert misuse
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - no assert outside the test file
- Hits: No hits

#### A13 (sampled): Same value to multiple structural slots
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - `emit(...)` keyword slots each get a distinct value
- Hits: No hits

#### A14 (sampled): Repeated computation per request
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - `cached_roots(scope)` is called per check but resolves once per run through `INDEX_CACHE` (`core.py:801`)
- Hits: No hits

#### A15 (sampled): Duplicate constructor / serialisation logic
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454)
- Hits: No hits

#### A16 (sampled): CLI entry envelope
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - neither is a `run_*` in `cli/*.py`
- Hits: No hits

#### A18 (sampled): Hot-path setup
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - no callback methods
- Hits: No hits

#### A20 (sampled): Mutable module-level singleton
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - no module-level container in the ranges
- Hits: No hits

#### A21 (sampled): Lazy init race
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - no `if X is None: X = ...`
- Hits: No hits

#### A22 (sampled): Fall-through after partial handling
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454)
- Hits: No hits

#### A23 (sampled): Discarded multi-return
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - `roots, _ = auditme.core.cached_roots(scope)` names its discard; other calls return single values
- Hits: No hits

#### A24 (sampled): Identity of subprocess / shell-out calls
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - no subprocess
- Hits: No hits

#### A25 (sampled): Shallow immutable wrapper
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - no module-level wrapper in range
- Hits: No hits

#### S1 (sampled): Type annotations on every signature
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454); `claude/skills/auditme/tests/test_error_handling.py` `test_attribute_call_and_subscript_bases_are_read_without_error` (369-375). Non-test: both signatures fully annotated. Tests: 0 missing parameter annotations, 0 missing return annotations, 0 modules affected, 1 module fully annotated (in-scope range)
- Hits: No hits

#### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454); `claude/skills/auditme/tests/test_error_handling.py` `test_attribute_call_and_subscript_bases_are_read_without_error` (369-375)
- Hits: No hits

#### S3 (sampled): TYPE_CHECKING block placement
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454); `claude/skills/auditme/tests/test_error_handling.py` `test_attribute_call_and_subscript_bases_are_read_without_error` (369-375) - no TYPE_CHECKING block in range
- Hits: No hits

#### S4 (sampled): Project-specific rule files
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454); `claude/skills/auditme/tests/test_error_handling.py` `test_attribute_call_and_subscript_bases_are_read_without_error` (369-375) against AGENTS.md rules (no project names: fixtures use `probe`, `lib`; full import paths: the one `from` import at architecture.py:25 is outside range and a sweep hit)
- Hits: No hits

#### P1 (sampled): O(n^2) on real-size inputs
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - `sibling_names` rebuilt per class inside the partition loop is quadratic in the classes of one `errors.py` (a handful on real projects), negligible; `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61)
- Hits: No hits

#### P2 (sampled): Blocking I/O in hot paths
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - no training loop, handler or callback
- Hits: No hits

#### P3 (sampled): Repeated expensive computation per request
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - `cached_roots` memoised; per-class set rebuild is cheap
- Hits: No hits

#### Sec1 (sampled): Secrets in source
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454); `claude/skills/auditme/tests/test_error_handling.py` `test_attribute_call_and_subscript_bases_are_read_without_error` (369-375)
- Hits: No hits

#### Sec2 (sampled): Input validation at system boundaries
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - no boundary input in range
- Hits: No hits

#### Sec3 (sampled): Command injection
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - no subprocess or shell
- Hits: No hits

#### Sec4 (sampled): Path traversal
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - paths come from `all_py_files(src_root)`, not user-joined
- Hits: No hits

#### Sec5 (sampled): PII in logs
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454) - no logging
- Hits: No hits

#### T3 (sampled): Integration vs unit balance
- Mode: changed lines since 7615d7f
- Inspected: `claude/skills/auditme/checks/auditme/phaseb/architecture.py` `capture_hits` (34-61); `claude/skills/auditme/checks/auditme/rules/error_handling.py` `check_sibling_error_no_common_base` (383-454); `claude/skills/auditme/tests/test_error_handling.py` `test_attribute_call_and_subscript_bases_are_read_without_error` (369-375) - no pipeline orchestrator in range
- Hits: No hits

#### D1 (sampled): Declared in pyproject
- Mode: changed lines since 7615d7f
- Inspected: `git diff 7615d7f HEAD -- pyproject.toml uv.lock .pre-commit-config.yaml` (empty)
- Hits: No hits

#### D2 (sampled): Unused declarations
- Mode: changed lines since 7615d7f
- Inspected: `git diff 7615d7f HEAD -- pyproject.toml uv.lock .pre-commit-config.yaml` (empty)
- Hits: No hits

#### D3 (sampled): Lockfile coherence
- Mode: changed lines since 7615d7f
- Inspected: same diff (empty); `/tmp/audit-auditor.jsonl` holds no lockfile-drift hit
- Hits: No hits

#### Doc3 (sampled): README.md and AGENTS.md consistent
- Mode: changed lines since 7615d7f
- Inspected: `git diff 7615d7f HEAD -- AGENTS.md README.md` (empty: no changed lines)
- Hits: No hits

#### Spec review
- `agents/specs/listed-phase-b-documentation-questions/spec.md`: every template section present and non-empty (Module location outside `src/` by design), API has typed code, Error handling names `PhaseBError`, Settings table has type and default, the relative link `../repeatable-phase-b/spec.md` resolves - no gaps.

## Prior findings re-verified

Review-7's F1-F4 and O1 shipped in the review-7 task list. F1 and F2 cleared on re-judging (above); F3 (`architecture.py:50` unpacks `roots, _`), F4 (no `contextlib.suppress` left in `check_sibling_error_no_common_base`) and O1 (the comment says what the check does) were confirmed by reading the code. No task list under `agents/tasks/audit-reviews/` has an incomplete task.

## Decisions

None this review.

## Answers

Answered on the review page on 2026-11-22. Every item took the recommended option, with no comments.

| Item | Answer |
|---|---|
| O1 | Fix |
| U1-U3 | Not a finding |
