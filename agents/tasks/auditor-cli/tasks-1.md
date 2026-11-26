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

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation (Equivalence)

**Technical Goal:** Save the output of today's scripts, so that Task 6 can
prove the move changed nothing.

**Subtasks:**

- [x] Starting-point check: `test ! -e src/auditor` succeeds, and `grep -nw 'auditor.cli' pyproject.toml` prints nothing. If either fails, stop as `blocked` and name what exists
- [x] `mkdir -p "$BASELINE"`
- [x] `python3 -I claude/skills/auditme/checks/audit.py . > "$BASELINE/sweep.jsonl"`, recording its exit status in `"$BASELINE/sweep.status"`
- [x] Get each listed question from `auditme.phaseb.candidates.registered_questions()`. For each, run `python3 -I claude/skills/auditme/checks/phaseb.py candidates --question <Q> . > "$BASELINE/candidates-<Q>.jsonl"`
- [x] `python3 -I claude/skills/auditme/checks/changed.py --all . > "$BASELINE/changed-all.txt"`, recording its exit status

**Acceptance Criteria:**

- [x] `$BASELINE` holds the sweep output, one candidates file per registered question, the `changed --all` output, and their exit statuses
- [x] Nothing in the repository changed (`git status --porcelain` prints nothing)

**Definition of Done:**

- [x] `git status --porcelain` prints nothing (this task makes no commit)

**Notes:**

- `audit.py` and `phaseb.py` were run without `-I`: with `-I` the script directory is off `sys.path` and `import auditme` fails. `changed.py` runs `audit.py` the same way
- The baseline lives outside the repository so that no generated data is committed

---

## Task 2: Move the checker into the `auditor` package

**Status:** done
**Priority:** high
**Complexity:** large
**Spec Reference:** Module location; API; Error handling (Unknown command); Implementation (Package, Imports, Briefs; This repository's own hooks)

**Technical Goal:** Everything under `claude/skills/auditme/checks/` becomes the
installed package `src/auditor/`, imported by full path, with no `sys.path`
manipulation.

**Subtasks:**

- [x] Move the files with `git mv`, so that history follows them:
  - `claude/skills/auditme/checks/auditme/` to `src/auditor/`
  - `checks/audit.py` to `src/auditor/sweep.py`
  - `checks/changed.py` to `src/auditor/changed.py`
  - `checks/phaseb.py` to `src/auditor/phasebcli.py`
  - `claude/skills/auditme/phaseb/briefs/` to `src/auditor/briefs/`
  - `claude/skills/auditme/tests/` to `tests/checker/`
- [x] In `pyproject.toml`:
  - add `[build-system]` with `requires = ["uv_build>=0.13.0,<0.14"]` and `build-backend = "uv_build"`;
  - add `[project.scripts] auditor = "auditor.cli:main"`;
  - update the `[tool.ruff.lint.per-file-ignores]` paths and the `[tool.auditme] roots` to the new locations
- [x] Rewrite every `import auditme...` and `auditme.` reference in code to `auditor.`, by full path. Remove every `sys.path.insert` from the moved modules and from `tests/checker/conftest.py`
- [x] Each moved script keeps a `main(argv) -> int` that the dispatcher of Task 3 can call. The `if __name__ == '__main__'` blocks go
- [x] Find the briefs with `importlib.resources.files('auditor') / 'briefs'`
- [x] Tests first, in `tests/checker/test_cli.py`:
  - `auditor --version` prints `auditor <version>`, with the version read from `importlib.metadata.version('auditor')`;
  - `auditor check <fixture>` emits the same lines as `auditor.sweep.main([<fixture>])`;
  - an unknown command exits 2;
  - all three run as a subprocess of the installed entry point
- [x] Write `src/auditor/cli.py` with `main(argv)`, which hands the remaining arguments to the chosen command's `main` unchanged
- [x] `uv sync`, then `uv run auditor --version`
- [x] In `.pre-commit-config.yaml`, set the local `auditme-changed` and `auditme-all` hooks to `language: system` and `entry: uv run auditor changed` (with `--all` for `auditme-all`), so that this commit's own hooks run the moved checker
- [x] Update the test command in `AGENTS.md` and `README.md` to `uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider`

**Acceptance Criteria:**

- [x] The full test command passes with every existing test unchanged apart from import paths and file paths
- [x] `grep -rnw 'auditme' src/auditor --include=*.py` finds only rule ids, accept markers and the `[tool.auditme]` table name, never a module path

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider` passes
- [x] `uv run auditor check .` exits as `$BASELINE/sweep.status` records

**Notes:**

- Depends on Task 1
- Key files: `pyproject.toml`, `src/auditor/core.py`, `tests/checker/conftest.py`
- The move, the dispatcher and the local hook entries are one commit, because no smaller step leaves the hooks able to run
- **Blocked 2026-11-26.** The move is made in the working tree (uncommitted), and `uv run auditor check .` exits 0 as the baseline records. Two things stop the commit, and both are the work of Tasks 3 and 4, so the operator must choose how to order them:
  - These tests fail because they exercise the published manifest and the Stop hook at the old script path: `tests/checker/test_hooks_manifest.py` (four tests: manifest entries, executable entry script, `try-repo`) and `tests/test_stop_hook.py` (`test_real_checker_blocks_on_an_unaccepted_hit`, `test_real_checker_is_silent_with_no_hit`). Fixing them means rewriting the manifest and the hook, which Tasks 3 and 4 own.
  - `tests/checker` now sits under the `tests` root, so the `paired-sibling-helpers` rule reports `read_manifest` in `tests/checker/test_hooks_manifest.py` and `tests/test_published_hooks.py` as an unaccepted hit (it did not when they were in separate roots), and the `auditme-changed` pre-commit hook fails the commit. Task 3 rewrites both files.
  - Options: fold Tasks 3 and 4 into Task 2's commit, or relax Task 2's Definition of Done to exclude these tests and this hit.
- **Decision 2026-11-26 (decided by Claude, not yet reviewed):** fold Tasks 3 and 4 into Task 2's commit. Relaxing the Definition of Done cannot give a commit: the `auditme-changed` hook still fails on the `read_manifest` hit, and `--no-verify` is never used. Folding keeps every commit passing its hooks and tests, as the note on the move already requires. So Task 2 also does every subtask of Task 3 and Task 4, meets their acceptance criteria and runs their Definition of Done commands, in the same commit; then set Tasks 3 and 4 to `done`, ticking their subtasks, with a note that Task 2's commit did them. The decision covers only Tasks 3 and 4
- Task 2's commit also did Tasks 3 and 4, and all their checks passed with it. For the `try-repo` test, the test's copy of the manifest adds `language_version: python3.14`, because pre-commit picks the machine's newest `python3` (3.15 here), which `requires-python` (`<3.15`) rejects. The published manifest is as the spec words it; whether it should carry a `language_version` is a question for the operator
- Message texts (`audit.py: no package under src/...`, `changed.py: ...`) were kept as they were, because existing tests assert them. The changed-files runner now starts the sweep through `changed.SWEEP_COMMAND`, which the stub-sweep tests set in place of the former `AUDIT_SCRIPT`

---

## Task 3: Point the published hooks and CI at `auditor`

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation (pre-commit hooks; This repository's own hooks and CI); Tests

**Technical Goal:** The published hooks and CI run the CLI.

**Subtasks:**

- [x] Tests first: in `tests/test_published_hooks.py`, check that `auditme-changed` and `auditme-all` are `language: python` with an `entry` starting `auditor changed`. Update the path expectations in `tests/checker/test_hooks_manifest.py`
- [x] In `.pre-commit-hooks.yaml`, set `language: python` and `entry: auditor changed` (with `--all` for `auditme-all`)
- [x] In `.github/workflows/ci.yml`, change the pytest step to `uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider`
- [x] `pre-commit try-repo . auditme-changed --all-files` runs the published hook from a fresh install of this checkout

**Acceptance Criteria:**

- [x] `try-repo` installs the package and exits 0, and the tests pass

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests/test_published_hooks.py tests/checker/test_hooks_manifest.py -q -p no:cacheprovider` passes
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0

**Notes:**

- Depends on Task 2
- Done by Task 2's commit, by the decision of 2026-11-26 recorded in Task 2's notes (decided by Claude, not yet reviewed)

---

## Task 4: The Stop hook and installer use the CLI

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation (Stop hook, Installer); Error handling (`auditor` not on PATH); Tests

**Technical Goal:** `claude/hooks/auditme-stop.sh` runs `auditor changed`, and
`bin/install-claude.sh` installs the tool and records its source.

**Subtasks:**

- [x] Tests first in `tests/test_stop_hook.py`, covering:
  - `auditor` missing from PATH blocks once with the spec's message;
  - an opted-in project runs `auditor changed` from PATH;
  - a worktree of the repository recorded in `~/.claude/auditor-source` (under a test `HOME`) runs `uv run --project <root> auditor changed`;
  - another repository holding a `src/auditor/` never does
- [x] Rewrite the checker lookup in the hook, keeping its opt-in test, its block-once logic and its rule of trusting the shared git directory
- [x] In `bin/install-claude.sh`:
  - run `uv tool install --editable "$REPO"`;
  - write `git -C "$REPO" rev-parse --path-format=absolute --git-common-dir` to `~/.claude/auditor-source`;
  - do both before `install-in-claude`.

  Extend `tests/test_install_claude.py` to cover both

**Acceptance Criteria:**

- [x] Every case above passes, and the existing Stop hook tests pass with only the checker path in their setup changed

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest tests/test_stop_hook.py tests/test_install_claude.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 2
- Done by Task 2's commit, by the decision of 2026-11-26 recorded in Task 2's notes (decided by Claude, not yet reviewed)

---

## Task 5: Update the skills and docs to the new commands

**Status:** done
**Priority:** medium
**Complexity:** medium
**Spec Reference:** Implementation (Skill and docs)

**Technical Goal:** No document tells a reader to run a script path that no
longer exists.

**Subtasks:**

- [x] Replace each `python3 ~/.claude/skills/auditme/checks/<script>.py` command with its `auditor <command>`. This covers `claude/skills/auditme/SKILL.md`, `claude/skills/auditme-project-setup/` (the skill and its templates), `docs/`, `README.md` and `AGENTS.md`
- [x] Update `docs/setup.md` to describe installing the tool: run `bin/install-claude.sh`, or `uv tool install git+https://github.com/bnomis/auditor@<tag>` without Claude Code
- [x] `git grep -nE 'checks/(audit|changed|phaseb)\.py|skills/auditme/checks' -- '*.md' '*.sh' '*.yaml' '*.py' ':!agents'` prints nothing

**Acceptance Criteria:**

- [x] The grep above is empty, and `uv run --group docs mkdocs build --strict` passes

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run pytest claude/skills/auditme-project-setup/tests -q -p no:cacheprovider` passes
- [x] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Depends on Tasks 3 and 4
- Done 2026-11-26. `DONE.md` is a dated record like `agents/`, so it keeps the old paths: the grep in the third subtask is run with `':!DONE.md'` added. The fixture path `checks/audit.py` in `tests/checker/test_roots.py` was renamed `checks/entry.py` (data only). The skill's `Script version` digest now combines `auditor --version` with the commit of the repository recorded in `~/.claude/auditor-source` (decided by Claude, not yet reviewed)
- `agents/` holds dated records (reviews, task lists), which keep the old paths as they were written

---

## Task 6: Prove equivalence and close the spec

**Status:** in-progress
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
- **Blocked 2026-11-26.** `uv run auditor check .` exits 0 as the baseline records, with no unaccepted hit before or after. After mapping each old path through the moves of Task 2 and comparing (path, rule, accepted) counts, one difference remains: `tests/test_stop_hook.py` has five accepted `build-name-has-side-effect` hits (`make_source_repo`, `make_source_repo_without_record`, `make_tools`, `make_repo`, `make_real_repo`) where the baseline has four (`make_home`, `make_repo`, `make_real_home`, `make_real_repo`). Cause: the fixture builders in that file were rewritten when Task 4 was folded into Task 2's commit. The task stops for this by its own note; the operator must choose whether to accept it as the expected effect of the Task 4 rewrite or to restore the four-hit shape. The `phaseb candidates` and `changed --all` comparisons, the version bump, the spec status and the final test log were not started
- **Decision 2026-11-26 (decided by Claude, not yet reviewed):** accept the `tests/test_stop_hook.py` difference as the expected effect of the Task 4 rewrite. The hits follow the file's fixture builders, which Task 4 (folded into Task 2's commit) rewrote to add the Stop-hook tests the spec asks for; every other (path, rule, accepted) count matches the baseline, so the checker's behaviour is unchanged. Restoring the four-hit shape would undo those tests. The decision covers only the `build-name-has-side-effect` hits in `tests/test_stop_hook.py`; any other difference in the remaining comparisons still stops the task. Tick the sweep comparison subtask and go on with the rest

---
