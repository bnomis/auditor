# Queue decisions 1: runner and rules split

**Order:** `agents/tasks/order-runner-rules-split.md`
**Created:** 2026-11-26
**Review page:** https://claude.ai/artifact/71KKLGao3fAY4cpCAk9upc

## What is being reviewed and how

While the order ran its four lists with `/rro`, each queue stop that was not reserved for you was decided by Claude, recorded in the task list as "decided by Claude, not yet reviewed", and committed with a `Queue-decision:` trailer. All four lists have since merged and the final checkpoint passed. Approve each decision, or flag it with a comment saying what should change; a flagged decision becomes follow-up work, since the code is already on `main`.

## Automatic checks

- Every decision commit carries a `Queue-decision:` trailer: pass (`bin/rro.sh decisions --since 1fa536f` lists all seven).
- The final checkpoint after row 4 passed on `main` (782 passed, 1 skipped; every hook passed; docs build strict): pass.

## Items

### 1. Fold Tasks 3 and 4 into Task 2's commit (`01ce68c`, auditor-cli Task 2)

- **Stop:** Moving the checker into the auditor package left the published-hook and Stop-hook tests on old paths, and a duplicate-helper hit, so Task 2 could not commit. The queue offered: fold Tasks 3 and 4 into Task 2, or relax Task 2's checks.
- **Decision:** Folded Tasks 3 and 4 into Task 2's single commit.
- **Why:** Relaxing the checks still cannot give a commit (the changed-files audit hook refuses the hit and --no-verify is never used); folding keeps every commit passing its hooks and tests.
- **Recommendation:** approve.

### 2. Accept the changed fixture hits in tests/test_stop_hook.py (`1c86aa5`, auditor-cli Task 6)

- **Stop:** The equivalence check found five accepted build-name-has-side-effect hits where the baseline had four, all in tests/test_stop_hook.py.
- **Decision:** Accepted it as the effect of the Task 4 rewrite of that file's fixtures.
- **Why:** Every other hit matched the baseline, so the checker is unchanged; restoring the old fixtures would undo the new Stop-hook tests the spec asks for.
- **Recommendation:** approve.

### 3. Accept the T1, Doc4 and Doc5 candidate changes (`3bdb631`, auditor-cli Task 6)

- **Stop:** Three Phase B questions listed different candidates after the move: one new T1 candidate (the dispatcher), and Doc4 and Doc5 ids that moved.
- **Decision:** Accepted them as the effect of Tasks 2 and 5.
- **Why:** The other eight questions, every exit status and changed --all matched. Doc4 now points at real drift: older specs still name claude/skills/auditme/checks/... (a follow-up, not yet filed).
- **Recommendation:** approve.

### 4. Keep src/auditor as the one sweep root for catalogue rules (`dba4e46`, default-rule-catalogue Task 2)

- **Stop:** Spec step 9 asks for a roots entry for src/auditor/catalogue/rules excluded from src/auditor; the checker cannot exclude a subdirectory from a root.
- **Decision:** Kept src/auditor as the one root, with a test that a catalogue rule file is swept exactly once by its path.
- **Why:** The step's requirement, each rule file audited in exactly one root, already holds; an exclude key would change root handling for no gain.
- **Recommendation:** approve.

### 5. Let the family tasks grow the rule API (`8939445`, default-rule-catalogue Tasks 3-9)

- **Stop:** Two tests from rules-repository Task 1 pinned the API's starting state: no module may import auditor.api, and __all__ is a fixed list. Both block every family move.
- **Decision:** The import test also skips src/auditor/catalogue/; the exports test compares __all__ with the union of the submodules' own __all__ plus API_VERSION and checks the spec's names. SINK_TOKENS goes to auditor.api.calls. API_VERSION stays (1, 0).
- **Why:** The catalogue spec says each family task adds any helper two or more rules use, so the API is meant to grow; no release has shipped it yet.
- **Recommendation:** approve.

### 6. Place AST-shape helpers in auditor.api.flow (`5e296ec`, default-rule-catalogue Tasks 4-9)

- **Stop:** leading_underscore_names, shared by two rules, fits none of the spec's API submodules.
- **Decision:** Put it in auditor.api.flow beside if_chain, and let later helpers that only read AST node shape go there too.
- **Why:** Both read node shape rather than source, calls, errors or docs; a helper that fits no submodule still stops the task.
- **Recommendation:** approve.

### 7. Fold the nested def/class check into text-patterns (`d8c4815`, default-rule-catalogue Task 4)

- **Stop:** The nested leading-underscore def/class check emits leading-underscore-def-class, which text-patterns already emits, and the catalogue refuses one id in two directories.
- **Decision:** Moved it into text-patterns/check.py as a second function its check runs.
- **Why:** The id and every accept marker stay unchanged, and the spec already lets one directory emit several ids; the alternatives change rule ids or the repository format.
- **Recommendation:** approve.

## Decisions

None beyond approving or flagging each item.

## Answers

Answered on the review page on 2026-11-26, copied here on 2026-11-26. Every
decision was approved, and none has a comment.

- 1. Fold Tasks 3 and 4 into Task 2's commit (`01ce68c`, auditor-cli Task 2): approved
- 2. Accept the changed fixture hits in tests/test_stop_hook.py (`1c86aa5`, auditor-cli Task 6): approved
- 3. Accept the T1, Doc4 and Doc5 candidate changes (`3bdb631`, auditor-cli Task 6): approved
- 4. Keep src/auditor as the one sweep root for catalogue rules (`dba4e46`, default-rule-catalogue Task 2): approved
- 5. Let the family tasks grow the rule API (`8939445`, default-rule-catalogue Tasks 3-9): approved
- 6. Place AST-shape helpers in auditor.api.flow (`5e296ec`, default-rule-catalogue Tasks 4-9): approved
- 7. Fold the nested def/class check into text-patterns (`d8c4815`, default-rule-catalogue Task 4): approved
