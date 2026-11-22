# Audit Summary

**Last updated:** 2026-11-22
**Last review:** review-2
**Total reviews conducted:** 2
**Last script run hit count:** 44 (44 accepted)
**Script version:** 48066ec1d87ecdbbbc9e0f98b351f039f675ea3cd07656c1b50bdb752bc70c8c

## How to reproduce the sweep

```bash
python3 ~/.claude/skills/auditme/checks/audit.py /Users/simonb/src/auditor
find -L ~/.claude/skills/auditme/checks -name '*.py' | sort | xargs cat | shasum -a 256
```

## Convergence note for review-3

- **Sampled mode:** review-3 is the third audit counted from review-1, so every sampled question runs on the whole tree.
- **Listed questions:** review-2 judged every re-planned candidate and wrote the verdicts to `agents/audit-reviews/ledger/`. Review-3 re-judges only candidates whose hash or brief version changed; a carried finding is not a regression.
- **Precondition:** review-3 cannot start until every entry in `claude/skills/auditme/requests.md` is shipped or rejected.

## Unresolved findings

Each group is described in full, with every site, in [review-2](review-2.md#phase-b-findings-consolidated).

None. Every finding review-2 raised was fixed (see below) or dismissed.

Dismissed on review-2's page (2026-11-22): F2, `cached_source` returning `None` for an unreadable file, which review-1's D2 chose.

## Recently resolved

| Finding | Severity | Raised in | Resolved in |
|---------|----------|-----------|-------------|
| F1 a read failure that a helper lets escape | low | review-2 | Task 4 of the review-2 task list |
| F3 checks return silently when `uv` or `ruff` cannot run | low | review-2 | Task 3 of the review-2 task list |
| F4 `phaseb.py` reaches past `auditme.phaseb`'s `__all__` | low | review-2 | Task 4 of the review-2 task list |
| F5 two helpers without the test the questions ask for | low | review-2 | Task 7 of the review-2 task list |
| F6 `--depth` with a question that takes no depth crashes | medium | review-2 | Task 2 of the review-2 task list |
| F7 specs that state the current state wrongly | medium | review-2 | Task 8 of the review-2 task list |
| F8 the `no-project-names` hook passes when a file cannot be read | medium | review-2 | Task 1 of the review-2 task list |
| F9 user docs that no longer match the code | medium | review-2 | Task 9 of the review-2 task list |
| F10 pure-named functions that read files | low | review-2 | Task 5 of the review-2 task list |
| F11 `Candidate` built inline at four sites | low | review-2 | Task 5 of the review-2 task list |
| F12 root configuration and specs re-read on every call | low | review-2 | Task 6 of the review-2 task list |
| F13 argparse calls without trailing commas | low | review-2 | Task 2 of the review-2 task list |
| F14 a setting without its type and default | low | review-2 | Task 8 of the review-2 task list |
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

- Pure-named functions that read files (A9): review-1 F3, review-2 F10. Each task that adds a reader names it as a pure query.
- Docs and specs left stale by the task list that changed the code (Doc4, Doc5): review-1 F6-F8, review-2 F7, F9.

## Checker changes since the last review

- `check_spec_api_signature_drift` moved from `CHECKS` to `PROJECT_CHECKS`: it runs once per sweep, before the per-root passes, so its hits are emitted earlier in the output (review-2 F12, Task 6 of the review-2 task list). The set of hits is unchanged.
- 2026-11-22: the `no-project-names` hook exits non-zero when a file it checks cannot be read, even when another file matched (review-2 F8, Task 1 of the review-2 task list).
- 2026-11-22: `phaseb.py candidates` passes `--depth` only to listers that take it, and refuses a bad depth with an error instead of a `TypeError` (review-2 F6, Task 2 of the review-2 task list).
- 2026-11-22: a missing `uv` or `ruff` is a hit from the checks that call them, not a silent return (review-2 F3, Task 3 of the review-2 task list).
- 2026-11-22: the A17 lister reads through the package's translating reader, so an unreadable file raises `PhaseBError` (review-2 F1, Task 4 of the review-2 task list).
- 2026-11-22: file readers are renamed to say that they read, and `Candidate` is built in one place (review-2 F10 and F11, Task 5 of the review-2 task list).
- 2026-11-22, `agents/reviews/brief-thresholds-2-2026-11-22.md`: the A1, A4, A17, Doc4 and Doc5 briefs settle the thresholds review-2's reviewers reported (A1 4, A4 6, A17 2, Doc4 6, Doc5 6). Each bump re-judges every candidate of its question in review-3.
