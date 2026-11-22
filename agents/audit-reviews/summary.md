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
- **Precondition:** review-2 cannot start until every entry in `claude/skills/auditme/requests.md` is shipped or rejected.

## Unresolved findings

Each group is described in full, with every site, in [review-1](review-1.md#phase-b-findings-consolidated).

| Finding | Question | Severity | First raised |
|---|---|---|---|
| (none) | | | |

Dismissed on review-1's page (2026-11-21): F2, the 68 A9 `check_*` sites (the registry's convention; a refinement is filed), F16 (the whole-tree sweep is by design), and 14 of F20's spec gaps (size and module location, from this repository's layout).

## Recently resolved

| Finding | Severity | Raised in | Resolved in |
|---------|----------|-----------|-------------|
| F1 an unreadable file crashes a check instead of being reported | medium | review-1 | Task 6 of the review-1 task list |
| F3 other pure-named functions that do I/O | low | review-1 | Task 12 of the review-1 task list |
| F4 helpers without a direct test | medium | review-1 | Task 9 of the review-1 task list |
| F5 pure helpers without a property test | low | review-1 | Task 11 of the review-1 task list |
| F6 specs name renamed helpers and moved settings | low | review-1 | Task 3 of the review-1 task list |
| F7 user guides out of date | medium | review-1 | Task 2 of the review-1 task list |
| F8 README and AGENTS.md disagree | low | review-1 | Task 2 of the review-1 task list |
| F9 `list_candidates` omits `RootsError` | low | review-1 | Task 4 of the review-1 task list |
| F10 `phaseb/__init__.py` exports names only tests use | low | review-1 | Task 9 of the review-1 task list |
| F11 missing annotations in checker source | low | review-1 | Task 4 of the review-1 task list |
| F12 type-only imports outside `TYPE_CHECKING` | low | review-1 | Task 5 of the review-1 task list |
| F13 `merge` can hash at a different depth from the plan | medium | review-1 | Task 7 of the review-1 task list |
| F14 construction duplicated or completed late | low | review-1 | Task 12 of the review-1 task list |
| F17 arguments and declared roots not contained | low | review-1 | Task 8 of the review-1 task list |
| F18 Stop hook and installer lack an end-to-end test | low | review-1 | Task 10 of the review-1 task list |
| F19 `pytest` not declared | low | review-1 | Task 1 of the review-1 task list |
| F20 spec-template gaps (the five D6 keeps) | low | review-1 | Task 3 of the review-1 task list |
| F15 repeated reads, parses and quadratic scans | low | review-1 | Task 13 of the review-1 task list (a per-run parse cache, shared corpus indexes, the length test before the LCS, one reverse call graph) |

## Recurring patterns

- (none yet: one review)

## Checker changes since the last review

- 2026-11-21, the review-1 task list: an unreadable file is reported as a hit instead of crashing its check (Task 6); `phaseb.py merge` refuses a depth different from its plan (Task 7); arguments and declared roots must stay inside the project (Task 8); the sweep caches parses and shared indexes for the run (Task 13).
- 2026-11-22, amendment 1.5 of `agents/specs/listed-phase-b-test-questions/spec.md`: the T1 and T2 test index now reads tests from every audit root, so review-2's T1 and T2 verdicts are re-judged where `test_files` grew.
