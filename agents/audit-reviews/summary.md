# Audit Summary

**Last updated:** 2026-11-21
**Last review:** review-1
**Total reviews conducted:** 1
**Last script run hit count:** 43 (43 accepted)
**Script version:** 074b2d235c6133f1cd0c742d84442f3b67fc20c3e9cdba0e9e943cb71e8472a8

## How to reproduce the sweep

```bash
python3 ~/.claude/skills/auditme/checks/audit.py /Users/simonb/src/auditor
find -L ~/.claude/skills/auditme/checks -name '*.py' | sort | xargs cat | shasum -a 256
```

## Convergence note for review-2

- **Sampled mode:** review-1's `**Commit:**` is `83e59c0`. Review-2 samples the files changed since then; the third audit counted from review-1 runs the whole tree.
- **Listed questions:** review-1 judged every candidate and wrote the verdicts to `agents/audit-reviews/ledger/`. Review-2 re-judges only candidates whose hash or brief version changed; a carried finding is not a regression.
- **Precondition:** review-1 files a checker request about the test index (it reads tests only from `src/tests/` and `tests/`). Review-2 cannot start until that is shipped or rejected, and its T1 and T2 verdicts will change once the index sees `claude/skills/auditme/tests/`.

## Unresolved findings

Each group is described in full, with every site, in [review-1](review-1.md#phase-b-findings-consolidated).

| Finding | Question | Severity | First raised |
|---|---|---|---|
| F1 an unreadable file crashes a check instead of being reported | A1, A2 | medium | review-1 |
| F3 other pure-named functions that do I/O | A9 | low | review-1 |
| F4 helpers without a direct test | T1 | medium | review-1 |
| F5 pure helpers without a property test | T2 | low | review-1 |
| F6 specs name renamed helpers and moved settings | Doc4 | low | review-1 |
| F7 user guides out of date | Doc5 | medium | review-1 |
| F8 README and AGENTS.md disagree | Doc3 | low | review-1 |
| F9 `list_candidates` omits `RootsError` | A4 | low | review-1 |
| F10 `phaseb/__init__.py` exports names only tests use | A17 | low | review-1 |
| F11 missing annotations in checker source | S1 | low | review-1 |
| F12 type-only imports outside `TYPE_CHECKING` | S4 | low | review-1 |
| F13 `merge` can hash at a different depth from the plan | A5 | medium | review-1 |
| F14 construction duplicated or completed late | A8, A13, A15 | low | review-1 |
| F15 repeated reads, parses and quadratic scans | A14, P1, P3 | low | review-1 |
| F17 arguments and declared roots not contained | Sec2, Sec4 | low | review-1 |
| F18 Stop hook and installer lack an end-to-end test | T3 | low | review-1 |
| F19 `pytest` not declared | D1 | low | review-1 |
| F20 spec-template gaps (the five D6 keeps) | spec review | low | review-1 |

Dismissed on review-1's page (2026-11-21): F2, the 68 A9 `check_*` sites (the registry's convention; a refinement is filed), F16 (the whole-tree sweep is by design), and 14 of F20's spec gaps (size and module location, from this repository's layout).

## Recently resolved

| Finding | Severity | Raised in | Resolved in |
|---------|----------|-----------|-------------|
| (none yet) | | | |

## Recurring patterns

- (none yet: one review)

## Checker changes since the last review

- (none since review-1)
