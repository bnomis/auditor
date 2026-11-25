# Tasks: Auditor CLI

**Spec:** `agents/specs/auditor-cli/spec.md`
**Created:** 2026-11-25
**Version:** 1

This list implements the whole spec, version 1.0, which was approved on
2026-11-25 (`agents/specs/runner-rules-split-review.md`, every item approved),
together with its amendment of the same day for this repository's own hooks
and CI. It is the first of four lists for the runner and rules split. The
other three (`agents/tasks/rules-repository/tasks-1.md`,
`agents/tasks/default-rule-catalogue/tasks-1.md` and
`agents/tasks/rules-init/tasks-1.md`) each need this one finished.

The list moves code and changes how it is invoked, and nothing else. Three
rules hold for every task:

- **No behaviour change.** A task in which any sweep hit, Phase B candidate,
  exit status or existing test's expected output changes stops as `blocked`,
  naming the difference. It never edits a test to make it pass.
- **No decisions.** Where a task meets a case the spec does not name, it stops
  as `blocked` for the operator, naming the case.
- **The baseline.** The baseline directory is `$BASELINE`, set to
  `${TMPDIR:-/tmp}/auditor-cli-baseline`, which is outside the repository.
  Every task that reads it sets the variable the same way.

---

## Task 1: Record the baseline

**Status:** todo
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation (Equivalence)

**Technical Goal:** Save the output of today's scripts, so that Task 6 can
prove the move changed nothing.

**Subtasks:**

- [ ] Starting-point check: `test ! -e src/auditor` succeeds, and `grep -nw 'auditor.cli' pyproject.toml` prints nothing. If either fails, stop as `blocked` and name what exists
- [ ] `mkdir -p "$BASELINE"`
- [ ] `python3 -I claude/skills/auditme/checks/audit.py . > "$BASELINE/sweep.jsonl"`, recording its exit status in `"$BASELINE/sweep.status"`
- [ ] Get each listed question from `auditme.phaseb.candidates.registered_questions()`. For each, run `python3 -I claude/skills/auditme/checks/phaseb.py candidates --question <Q> . > "$BASELINE/candidates-<Q>.jsonl"`
- [ ] `python3 -I claude/skills/auditme/checks/changed.py --all . > "$BASELINE/changed-all.txt"`, recording its exit status

**Acceptance Criteria:**

- [ ] `$BASELINE` holds the sweep output, one candidates file per registered question, the `changed --all` output, and their exit statuses
- [ ] Nothing in the repository changed (`git status --porcelain` prints nothing)

**Definition of Done:**

- [ ] `git status --porcelain` prints nothing (this task makes no commit)

**Notes:**

- The baseline lives outside the repository so that no generated data is committed

---

## Task 2: Move the checker into the `auditor` package

**Status:** todo
**Priority:** high
**Complexity:** large
**Spec Reference:** Module location; API; Error handling (Unknown command); Implementation (Package, Imports, Briefs; This repository's own hooks)

**Technical Goal:** Everything under `claude/skills/auditme/checks/` becomes the
installed package `src/auditor/`, imported by full path, with no `sys.path`
manipulation.

**Subtasks:**

- [ ] Move the files with `git mv`, so that history follows them:
  - `claude/skills/auditme/checks/auditme/` to `src/auditor/`
  - `checks/audit.py` to `src/auditor/sweep.py`
  - `checks/changed.py` to `src/auditor/changed.py`
  - `checks/phaseb.py` to `src/auditor/phasebcli.py`
  - `claude/skills/auditme/phaseb/briefs/` to `src/auditor/briefs/`
  - `claude/skills/auditme/tests/` to `tests/checker/`
- [ ] In `pyproject.toml`:
  - add `[build-system]` with `requires = ["uv_build>=0.13.0,<0.14"]` and `build-backend = "uv_build"`;
  - add `[project.scripts] auditor = "auditor.cli:main"`;
  - update the `[tool.ruff.lint.per-file-ignores]` paths and the `[tool.auditme] roots` to the new locations
- [ ] Rewrite every `import auditme...` and `auditme.` reference in code to `auditor.`, by full path. Remove every `sys.path.insert` from the moved modules and from `tests/checker/conftest.py`
- [ ] Each moved script keeps a `main(argv) -> int` that the dispatcher of Task 3 can call. The `if __name__ == '__main__'` blocks go
- [ ] Find the briefs with `importlib.resources.files('auditor') / 'briefs'`
- [ ] Tests first, in `tests/checker/test_cli.py`:
  - `auditor --version` prints `auditor <version>`, with the version read from `importlib.metadata.version('auditor')`;
  - `auditor check <fixture>` emits the same lines as `auditor.sweep.main([<fixture>])`;
  - an unknown command exits 2;
  - all three run as a subprocess of the installed entry point
- [ ] Write `src/auditor/cli.py` with `main(argv)`, which hands the remaining arguments to the chosen command's `main` unchanged
- [ ] `uv sync`, then `uv run auditor --version`
- [ ] In `.pre-commit-config.yaml`, set the local `auditme-changed` and `auditme-all` hooks to `language: system` and `entry: uv run auditor changed` (with `--all` for `auditme-all`), so that this commit's own hooks run the moved checker
- [ ] Update the test command in `AGENTS.md` and `README.md` to `uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider`

**Acceptance Criteria:**

- [ ] The full test command passes with every existing test unchanged apart from import paths and file paths
- [ ] `grep -rnw 'auditme' src/auditor --include=*.py` finds only rule ids, accept markers and the `[tool.auditme]` table name, never a module path

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider` passes
- [ ] `uv run auditor check .` exits as `$BASELINE/sweep.status` records

**Notes:**

- Depends on Task 1
- Key files: `pyproject.toml`, `src/auditor/core.py`, `tests/checker/conftest.py`
- The move, the dispatcher and the local hook entries are one commit, because no smaller step leaves the hooks able to run

---

## Task 3: Point the published hooks and CI at `auditor`

**Status:** todo
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation (pre-commit hooks; This repository's own hooks and CI); Tests

**Technical Goal:** The published hooks and CI run the CLI.

**Subtasks:**

- [ ] Tests first: in `tests/test_published_hooks.py`, check that `auditme-changed` and `auditme-all` are `language: python` with an `entry` starting `auditor changed`. Update the path expectations in `tests/checker/test_hooks_manifest.py`
- [ ] In `.pre-commit-hooks.yaml`, set `language: python` and `entry: auditor changed` (with `--all` for `auditme-all`)
- [ ] In `.github/workflows/ci.yml`, change the pytest step to `uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider`
- [ ] `pre-commit try-repo . auditme-changed --all-files` runs the published hook from a fresh install of this checkout

**Acceptance Criteria:**

- [ ] `try-repo` installs the package and exits 0, and the tests pass

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest tests/test_published_hooks.py tests/checker/test_hooks_manifest.py -q -p no:cacheprovider` passes
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0

**Notes:**

- Depends on Task 2

---

## Task 4: The Stop hook and installer use the CLI

**Status:** todo
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation (Stop hook, Installer); Error handling (`auditor` not on PATH); Tests

**Technical Goal:** `claude/hooks/auditme-stop.sh` runs `auditor changed`, and
`bin/install-claude.sh` installs the tool and records its source.

**Subtasks:**

- [ ] Tests first in `tests/test_stop_hook.py`, covering:
  - `auditor` missing from PATH blocks once with the spec's message;
  - an opted-in project runs `auditor changed` from PATH;
  - a worktree of the repository recorded in `~/.claude/auditor-source` (under a test `HOME`) runs `uv run --project <root> auditor changed`;
  - another repository holding a `src/auditor/` never does
- [ ] Rewrite the checker lookup in the hook, keeping its opt-in test, its block-once logic and its rule of trusting the shared git directory
- [ ] In `bin/install-claude.sh`:
  - run `uv tool install --editable "$REPO"`;
  - write `git -C "$REPO" rev-parse --path-format=absolute --git-common-dir` to `~/.claude/auditor-source`;
  - do both before `install-in-claude`.

  Extend `tests/test_install_claude.py` to cover both

**Acceptance Criteria:**

- [ ] Every case above passes, and the existing Stop hook tests pass with only the checker path in their setup changed

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest tests/test_stop_hook.py tests/test_install_claude.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 2

---

## Task 5: Update the skills and docs to the new commands

**Status:** todo
**Priority:** medium
**Complexity:** medium
**Spec Reference:** Implementation (Skill and docs)

**Technical Goal:** No document tells a reader to run a script path that no
longer exists.

**Subtasks:**

- [ ] Replace each `python3 ~/.claude/skills/auditme/checks/<script>.py` command with its `auditor <command>`. This covers `claude/skills/auditme/SKILL.md`, `claude/skills/auditme-project-setup/` (the skill and its templates), `docs/`, `README.md` and `AGENTS.md`
- [ ] Update `docs/setup.md` to describe installing the tool: run `bin/install-claude.sh`, or `uv tool install git+https://github.com/bnomis/auditor@<tag>` without Claude Code
- [ ] `git grep -nE 'checks/(audit|changed|phaseb)\.py|skills/auditme/checks' -- '*.md' '*.sh' '*.yaml' '*.py' ':!agents'` prints nothing

**Acceptance Criteria:**

- [ ] The grep above is empty, and `uv run --group docs mkdocs build --strict` passes

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run pytest claude/skills/auditme-project-setup/tests -q -p no:cacheprovider` passes
- [ ] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Depends on Tasks 3 and 4
- `agents/` holds dated records (reviews, task lists), which keep the old paths as they were written

---

## Task 6: Prove equivalence and close the spec

**Status:** todo
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation (Equivalence); Tests

**Technical Goal:** The CLI gives the same results as the scripts did, and the
spec is closed.

**Subtasks:**

- [ ] `uv run auditor check . > "$BASELINE/sweep-after.jsonl"`, then compare it with `$BASELINE/sweep.jsonl`. Ignore paths that the move changed. To do so, map each path in the old file through the moves of Task 2 before comparing. Any other difference stops the task as `blocked`, naming the hit
- [ ] Do the same for each `auditor phaseb candidates --question <Q> .` and for `auditor changed --all .`, including the exit statuses
- [ ] Set `version = "0.2.0"` in `pyproject.toml` (the bump is made at the list's last task, against `main`, so that the order's lists merge cleanly)
- [ ] Set the spec's `**Status:**` to `implemented`
- [ ] Save the full test run for the run order's merge gate, from the repository root of this worktree: `MAIN=$(git worktree list --porcelain | sed -n '1s/^worktree //p'); LOG="$MAIN/logs/rro/auditor-cli/tasks-1/final-tests.log"; mkdir -p "$(dirname "$LOG")"; uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider 2>&1 | tee "$LOG"; [ "${PIPESTATUS[0]}" -eq 0 ] && echo 'all selected test directories passed' | tee -a "$LOG"`, and the log ends with `all selected test directories passed`

**Acceptance Criteria:**

- [ ] Every comparison matches after the path mapping

**Definition of Done:**

- [ ] `pre-commit run --all-files` exits 0
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [ ] `uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider` passes
- [ ] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Depends on Tasks 1 to 5
- Hits that this repository's own code changes produce (a moved file that is now in a different root) are differences. The task stops for them; it does not accept them

---
