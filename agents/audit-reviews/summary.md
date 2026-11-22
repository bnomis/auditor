# Audit Summary

**Last updated:** 2026-11-22
**Last review:** review-6
**Total reviews conducted:** 6
**Last script run hit count:** 48 (48 accepted)
**Script version:** e5d95235f166aec74a8cd3b3d3cc8617ce2edf4bcd8b2e3e53a608091cab6836

## How to reproduce the sweep

```bash
python3 ~/.claude/skills/auditme/checks/audit.py /Users/simonb/src/auditor
find -L ~/.claude/skills/auditme/checks -name '*.py' | sort | xargs cat | shasum -a 256
```

## Convergence note for review-7

- **Sampled mode:** review-7 is not a whole-tree audit, so each sampled question judges only the changed lines since review-6's commit, from `checks/changed.py --scope`.
- **Listed questions:** review-7 re-judges only candidates whose hash or brief version changed.
- **Precondition:** review-7 cannot start until every entry in `claude/skills/auditme/requests.md` is shipped or rejected.

## Unresolved findings

Each group is described in full, with every site, in [review-6](review-6.md#phase-b-findings-consolidated).

| Finding | Question | Severity | First raised |
|---------|----------|----------|--------------|
| F1 `cached_bytes` lets `OSError` escape and has no direct test | A1, T1 | low | review-6 |
| F2 the new `--scope` helpers have no property tests | T2 | low | review-6 |
| F3 three specs state brief version numbers that went stale | Doc4 | low | review-6 |
| F4 a spec API block leaves out a declared `Raises:` | Doc4 | low | review-6 |
| F5 the CLI reference misses two `--scope` behaviours | Doc5 | low | review-6 |
| F6 the `silent-self-mutation` row lists fewer exempt methods than the check | Doc5 | low | review-6 |
| F7 `AGENTS.md` says "both hook types" before a command naming three | Doc3 | low | review-6 |
| F8 a test helper's name hides a read | A9 | low | review-6 |
| F9 the same value worked out again within one run | A14, P3 | low | review-6 |

Dismissed (2026-11-22): `cached_source` returning `None` for an unreadable file, on the pages of review-2 to review-4, as review-1's D2 chose. On review-5's page: F4 and F7. On review-6's page: F10 (two pairwise checks, measured small).

## Recently resolved

| Finding | Severity | Raised in | Resolved in |
|---------|----------|-----------|-------------|
| F1 the installer's exit-1 row leaves out two cases | low | review-5 | Task 1 of the review-5 task list |
| F2 a troubleshooting cause left out | low | review-5 | Task 1 of the review-5 task list |
| F3 the phaseb synopsis leaves out `--depth` | low | review-5 | Task 1 of the review-5 task list |
| F8 two imports used only in annotations | low | review-5 | Task 2 of the review-5 task list |
| F5 `resolve_path` reads a file under a pure name | low | review-5 | Task 3 of the review-5 task list (the reading functions renamed `read_*`) |
| F6 the listers read, parse and resolve the same things repeatedly | low | review-5 | Task 3 of the review-5 task list |
| F2 `phaseb.py` reads `auditme.phaseb.batches` outside `__all__` | low | review-4 | Task 3 of the review-4 task list |
| F3 a second copy of the root modes in the per-run cache | low | review-4 | Task 4 of the review-4 task list |
| F4 `resolve_name` reads a whole file to count its lines | low | review-4 | Task 5 of the review-4 task list |
| F5 repeated work in `docrefs` | low | review-4 | Task 5 of the review-4 task list |
| F6 `changed.py`'s `--base` guard can be got past | medium | review-4 | Task 2 of the review-4 task list |
| F7 the `no-project-names` hook passes when its list cannot be read | medium | review-4 | Task 1 of the review-4 task list |
| F8 two spec statements that no longer match the code | low | review-4 | Task 6 of the review-4 task list |
| F9 user docs that no longer match the code | medium | review-4 | Task 7 of the review-4 task list |
| F10 spec cross-references written as paths | low | review-4 | Task 6 of the review-4 task list |
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

- Version figures in prose (Doc4): review-6 F3. A brief bump left three specs stating the old versions; each brief's `**Brief version:**` line is the only place a version is stated.
- Pure-named functions that read files (A9): review-1 F3, review-2 F10. Each task that adds a reader names it as a pure query.
- Docs and specs left stale by the task list that changed the code (Doc4, Doc5): review-1 F6-F8, review-2 F7, F9, review-3 F9, F10. Two statements review-2's Task 9 was meant to fix were still stale in review-3.
- A cache added for some callers, not all (A14, P3): review-1 F15, review-2 F12, review-3 F5, F6.
- New brief thresholds after each settlement (D1): review-1, review-2 and review-3 each reported a fresh set.
- A fix for one rule that moves the finding to another (A17 after S4): review-3 F8, review-4 F2.
- A renaming or reshaping fix that brings a finding back (A9 after review-4's rename, A17 after review-3's import change): review-4 F2, review-5 F5.
- A verdict that flips when a fresh reviewer reads the same text under the same brief: review-5 F2, F3.

## Checker changes since the last review

- 2026-11-22: a Doc candidate's hash covers the whole section's text, not only the blocks naming its target (Task 4 of the review-5 task list).
- 2026-11-22: sampled reviewers between whole-tree audits are given the changed lines, from `changed.py --scope` (Task 5 of the review-5 task list).
- 2026-11-22: a candidate that is planned again carries its earlier verdict as `earlier` in its batch line, and every brief's version rose by one (Task 6 of the review-5 task list).
