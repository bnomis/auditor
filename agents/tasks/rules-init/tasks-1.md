# Tasks: Rules init

**Spec:** `agents/specs/rules-init/spec.md`
**Created:** 2026-11-25
**Version:** 1

This list implements the whole spec, version 1.0, which was approved on
2026-11-25 (`agents/specs/runner-rules-split-review.md`). It is the last of
four lists for the runner and rules split, and needs the other three finished,
`agents/tasks/default-rule-catalogue/tasks-1.md` last of them.

Task 1 stops the list for the operator, who reviews which pack each rule
belongs to. Its answers are handed back outside the unattended run, as its
last subtask says. Where a task meets a case the spec does not name, it stops
as `blocked` for the operator, naming the case.

---

## Task 1: Propose the pack membership for review

**Status:** todo
**Priority:** high
**Complexity:** medium
**Spec Reference:** Packs

**Technical Goal:** Recommend one pack for every catalogue rule, and publish
the proposal as a review page.

**Subtasks:**

- [ ] Starting-point check: `test ! -e src/auditor/catalogue/packs.toml` succeeds, and `grep -rnwE 'rulesinit|RulesInitError' src/auditor` prints nothing. Otherwise stop as `blocked`
- [ ] For each rule directory in `src/auditor/catalogue/rules/`, recommend one of the spec's proposed packs, with a one-line reason. State the rule the recommendations follow: a rule goes to the pack of the topic its `rule.md` names first, and a standard goes with the checks that enforce it
- [ ] Write `agents/reviews/rules-init-packs.md`, as the shared `reviews.md` rule describes: one item per rule, giving its kind, title and recommended pack, and an empty Answers section
- [ ] Publish the interactive page:
  - each item has the spec's packs as options, its recommendation preselected by the accept-all button, and a comment box;
  - answers save to the artifact's database.

  Put `**Review page:** <URL>` in the document's header
- [ ] Commit the review document, then stop the list as `blocked`, waiting for review
- [ ] Once every item has an answer, an operator session reads the page's answers and copies each into the document's Answers section, with the date. It commits that, and only then restarts the list

**Acceptance Criteria:**

- [ ] Every catalogue rule is an item with a recommendation, and the page's URL is in the document's header

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest tests/catalogue -q -p no:cacheprovider` passes (the quick form for a task that stops for review)

**Notes:**

- Depends on `agents/tasks/default-rule-catalogue/tasks-1.md` being finished

---

## Task 2: Write `packs.toml` from the answers

**Status:** todo
**Priority:** high
**Complexity:** small
**Spec Reference:** Packs; Tests (the pack membership test moved here from the catalogue spec)

**Technical Goal:** `src/auditor/catalogue/packs.toml` holds the reviewed
membership, and a test keeps every rule in exactly one pack.

**Subtasks:**

- [ ] Read the answers from the Answers section of `agents/reviews/rules-init-packs.md`. If that section is empty, or missing an item, stop as `blocked`, naming the missing items. Never read the page
- [ ] Write `packs.toml`, giving each pack a `description` and its `rules` in name order. A pack the answers leave empty is left out
- [ ] Add to `tests/catalogue/test_catalogue.py`: every rule directory is in exactly one pack, and every listed name is a rule directory

**Acceptance Criteria:**

- [ ] The new test passes, and the membership matches the Answers section exactly

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest tests/catalogue -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1, and on the operator's hand-back

---

## Task 3: Write the selection file

**Status:** todo
**Priority:** high
**Complexity:** small
**Spec Reference:** API (`write_selection`, `auditor rules init`, `auditor rules packs`); Implementation (The selection file, `init`); Error handling

**Technical Goal:** `auditor rules init <dest> [--pack P]...` writes
`selection.txt`. The chosen packs' rules are bare lines, and every other rule
is commented out. Each pack has a heading, and each rule line ends with its
title. `auditor rules packs` lists the packs.

**Subtasks:**

- [ ] Tests first, in `tests/rulesinit/test_init.py`:
  - with one pack, only its rules are uncommented;
  - with no pack, every rule is uncommented;
  - an unknown pack fails with the spec's message;
  - a `<dest>` that holds `rules/` or `auditor-rules.toml` is refused, and nothing is written
- [ ] Write `RulesInitError`, `write_selection` and the `init` and `packs` commands in `src/auditor/rulesinit.py` and `src/auditor/rulescli.py`

**Acceptance Criteria:**

- [ ] The new tests pass. `init` never prompts, and prints the next command to run

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest tests/rulesinit/test_init.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 2

---

## Task 4: Apply the selection

**Status:** todo
**Priority:** high
**Complexity:** medium
**Spec Reference:** API (`apply_selection`, `auditor rules apply`); Implementation (`apply`); Error handling; Tests

**Technical Goal:** `auditor rules apply <dest>` validates the whole selection,
then writes the files the spec lists:

- the copied rule directories;
- `auditor-rules.toml`, with `api` and a `[source]` table;
- `TODO.md` and `DONE.md`;
- `README.md` and `.gitignore`.

It then runs `git init` when needed, makes no commit, and runs
`auditor rules check` on the result.

**Subtasks:**

- [ ] Tests first, in `tests/rulesinit/test_apply.py`:
  - exactly the uncommented names are copied, tests included;
  - the result passes `auditor rules check` and `auditor rules pending` (exit 0);
  - a misspelt name names the line;
  - a selected rule whose standard is not selected is refused;
  - a `<dest>/rules` that already exists is refused;
  - after each error, `<dest>` is byte-identical
- [ ] Write `apply_selection` and the `apply` command. The `TODO.md` and `DONE.md` headers are copied from this repository's own two files' opening paragraphs

**Acceptance Criteria:**

- [ ] The new tests pass

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest tests/rulesinit -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 3

---

## Task 5: Prove a full init equals the catalogue, document it and close

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Spec Reference:** Tests; Module location (the setup skill); Implementation (pointing a project at the repository)

**Technical Goal:** A repository made from every pack sweeps the same as the
catalogue, and the wheel holds the catalogue. The setup skill and the docs
show how to create a rules repository, and the spec is closed.

**Subtasks:**

- [ ] Write `tests/rulesinit/test_full_init.py`:
  - `init` with no pack, then `apply`, into `tmp_path`;
  - a sweep of a fixture project with `AUDITOR_RULES_PATH` set to the result gives the same hits as with `src/auditor/catalogue`
- [ ] Write `tests/rulesinit/test_wheel.py`: `uv build --wheel` into `tmp_path`, and the wheel lists `auditor/catalogue/packs.toml` and every rule directory
- [ ] In `claude/skills/auditme-project-setup/SKILL.md`, when `AUDITOR_RULES_PATH` is unset, offer the steps of `auditor rules init <dir>`, editing `selection.txt`, `auditor rules apply <dir>`, and the `.envrc` line. The skill gives these as steps for the user and never edits `.envrc`
- [ ] Add a "Create a rules repository" section to `docs/setup.md`, and add `init`, `apply` and `packs` to `docs/reference/cli.md`
- [ ] Set the spec's `**Status:**` to `implemented`

**Acceptance Criteria:**

- [ ] Both new tests pass, and the docs build

**Definition of Done:**

- [ ] `pre-commit run --all-files` exits 0
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [ ] `uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider` passes
- [ ] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Depends on Task 4

---
