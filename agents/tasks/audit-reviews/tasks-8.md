# Tasks: Audit review 8

**Source:** `agents/audit-reviews/review-8.md`
**Created:** 2026-11-22
**Version:** 8

Fixes the one observation the operator approved on review-8's page on
2026-11-22 (O1; U1-U3 were kept as not findings). The answers are in
review-8's Answers section. No task changes a brief in
`claude/skills/auditme/phaseb/briefs/`.

---

## Task 1: Stop swallowing `ast.unparse` failures in the rule checks

**Status:** done
**Priority:** medium
**Complexity:** small
**Source Reference:** O1

**Technical Goal:** no rule check wraps `ast.unparse` in
`contextlib.suppress(Exception)`, as review-7's F4 fixed for
`check_sibling_error_no_common_base`.

**Subtasks:**

- [x] Record `python3 claude/skills/auditme/checks/audit.py .` outside the repository
- [x] Remove each `with contextlib.suppress(Exception):` around an `ast.unparse` call, keeping the call: `claude/skills/auditme/checks/auditme/rules/error_handling.py` (lines 237, 1026, 1274 on 2026-11-22) and `claude/skills/auditme/checks/auditme/rules/state_and_effects.py` (lines 555, 1047, 1323). `ast.unparse` of a node taken from a parsed tree does not fail; if a case is found that does, catch only that exception and test it
- [x] Drop each module's `import contextlib` if nothing else uses it
- [x] `grep -rn 'suppress(Exception)' claude/skills/auditme/checks` prints nothing
- [x] Run the audit again and diff it against the record

**Acceptance Criteria:**

- [x] The audit output is identical before and after
- [x] No `contextlib.suppress(Exception)` is left under `claude/skills/auditme/checks/`

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/test_state_and_effects.py -q -p no:cacheprovider` passes

**Notes:**

- Find each site by its text; the line numbers are from 2026-11-22
- Key files: `claude/skills/auditme/checks/auditme/rules/error_handling.py`, `claude/skills/auditme/checks/auditme/rules/state_and_effects.py`

---

## Task 2: Run the whole-tree checks and update the summary

**Status:** done
**Priority:** medium
**Complexity:** small
**Source Reference:** all

**Technical Goal:** the branch passes every whole-tree check before it
merges, and the audit summary records what this list resolved.

**Subtasks:**

- [x] Run `python3 claude/skills/auditme/checks/phaseb.py candidates . --question Doc4` and `--question Doc5`, take the candidates that name a code file this list changed (`git diff --name-only <base>...HEAD`), and check their statements against the code by hand; fix any that no longer matches. Record what was checked in the task's Notes
- [x] In `agents/audit-reviews/summary.md`, move O1 to Recently resolved, naming Task 1; replace the Unresolved table with the sentence "No finding is unresolved: review-8 raised none, and its observation O1 shipped (below)." rather than an empty row

**Acceptance Criteria:**

- [x] The Unresolved section holds only items that did not ship, each with its reason

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `pre-commit run --all-files` passes
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` passes (the pre-push whole-tree audit)
- [x] `uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes
- [x] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Depends on Task 1
- Doc4 and Doc5 candidates checked: the only candidates naming `error_handling.py` or `state_and_effects.py` are spec/guide statements about function names, signatures and rule behaviour. Task 1 only removed `contextlib.suppress(Exception)` wrappers, and a grep of `docs`, `agents/specs` and the skill docs for `suppress(Exception)` and `ast.unparse` finds no statement about them, so none needed a fix

---
