# Audit Summary

**Last updated:** 2026-11-22
**Last review:** review-3
**Total reviews conducted:** 3
**Last script run hit count:** 45 (45 accepted)
**Script version:** 1187649b552c2cf9fc9737c169f408c05bedc11781ee2d2c528449fb4c025abf

## How to reproduce the sweep

```bash
python3 ~/.claude/skills/auditme/checks/audit.py /Users/simonb/src/auditor
find -L ~/.claude/skills/auditme/checks -name '*.py' | sort | xargs cat | shasum -a 256
```

## Convergence note for review-4

- **Sampled mode:** review-3's `**Commit:**` is `6b51a21`. Review-4 samples the files changed since then; the sixth audit counted from review-1 runs the whole tree.
- **Listed questions:** review-3 judged every re-planned candidate and wrote the verdicts to `agents/audit-reviews/ledger/`. Review-4 re-judges only candidates whose hash or brief version changed; a carried finding is not a regression.
- **Precondition:** review-4 cannot start until every entry in `claude/skills/auditme/requests.md` is shipped or rejected. Review-3 filed one (the `ruff format` parser), and D1 may file a second.

## Unresolved findings

Each group is described in full, with every site, in [review-3](review-3.md#phase-b-findings-consolidated).

| Finding | Question | Severity | First raised |
|---|---|---|---|
| (none: every review-3 finding shipped or was dismissed) | | | |

Dismissed on review-2's page (2026-11-22, F2) and again on review-3's (F1, after the A1 brief changed): `cached_source` returning `None` for an unreadable file, which review-1's D2 chose.

## Recently resolved

| Finding | Severity | Raised in | Resolved in |
|---------|----------|-----------|-------------|
| F2 `positive_int` has no property test | low | review-3 | Task 2 of the review-3 task list |
| F3 `changed.py`'s entry envelope misses `OSError` | low | review-3 | Task 1 of the review-3 task list |
| F4 two dataclasses filled after construction | low | review-3 | Task 3 of the review-3 task list |
| F5 `surface_files` resolves the audit roots on every call | low | review-3 | Task 5 of the review-3 task list |
| F6 every rule check parses every file again | medium | review-3 | Tasks 6 and 7 of the review-3 task list |
| F7 two function-local constants named lower_snake | low | review-3 | Task 4 of the review-3 task list |
| F8 absolute from-imports in `phaseb/__init__.py` | low | review-3 | Task 4 of the review-3 task list |
| F9 specs that no longer match the code | medium | review-3 | Task 8 of the review-3 task list |
| F10 user docs that no longer match the code | medium | review-3 | Task 9 of the review-3 task list |
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
- Docs and specs left stale by the task list that changed the code (Doc4, Doc5): review-1 F6-F8, review-2 F7, F9, review-3 F9, F10. Two statements review-2's Task 9 was meant to fix were still stale in review-3.
- A cache added for some callers, not all (A14, P3): review-1 F15, review-2 F12, review-3 F5, F6.
- New brief thresholds after each settlement (D1): review-1, review-2 and review-3 each reported a fresh set.

## Checker changes since the last review

- 2026-11-22: `changed.py`'s entry translates an `OSError` (for example a removed working directory) to its `changed.py:` message and exit 1 (review-3 F3, Task 1).
- 2026-11-22: every rule check takes its tree from the shared `read_and_parse` instead of parsing each file again; the sorted sweep is unchanged, and the median of three runs fell from 12.2 s to 6.55 s on this repository (review-3 F6, Tasks 6 and 7).
- 2026-11-22: `phaseb/__init__.py` no longer re-exports `batches`; readers import `auditme.phaseb.batches` directly (review-3 F8, Task 4).
- 2026-11-22: the `ruff` rule's `ruff format` half reads ruff's JSON output, so a file ruff would reformat is a `ruff-format` hit at its path and line; before, it never fired. Review-4 reports any unformatted file in scope as catch-up.
- 2026-11-22, `agents/reviews/brief-thresholds-3-2026-11-22.md`: every brief gives a case it does not settle a default verdict, not a finding, reported (G1); every listed question's brief went up one version, so review-4 re-judges every listed candidate once. A1, T2, Doc4 and Doc5 also settle review-3's cases.
