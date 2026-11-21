# Tasks: Project setup

**Spec:** `agents/specs/project-setup/spec.md`
**Created:** 2026-10-31
**Version:** 1

Implements the whole spec at version 1.1: the `related` field, the
changed-files runner, the published hooks, the Stop hook and its registration,
the `/project-setup` skill and its templates, and the user guide.

`changed.py` is modelled on a project-local runner in another repository (the
spec's Motivation); the spec restates everything needed from it, so no task
reads that repository. Task 9 carries the deduplication subtask the sibling
model calls for.

**Nothing here changes another repository or the operator's home directory.**
Tests that exercise `bin/install-claude.py` and the Stop hook run against a
temporary `HOME`. Running the installer for real, and adopting the hooks in
other projects, is the operator's work after this list merges (Task 9 Notes).

The repository has no affected-tests tool. Each task names its own test files;
the last task runs both test trees in full.

---

## Task 1: Cross-file hits carry `related`

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation - The changed-files runner ("Cross-file hits carry `related`"); Testing

**Technical Goal:** Give every hit from a rule that compares two or more files a
structured `related` list of the other locations' paths, so a scope filter can
report a hit when only its peer changed. Hits without it stay byte-identical.

**Subtasks:**

- [x] `claude/skills/auditme/checks/auditme/core.py`: `_emit()` accepts an optional `related: list[str]` of repository-relative paths, sorted and de-duplicated, and omits the key when the list is empty
- [x] Pass `related` from each cross-file rule: `literal-duplication` and `paired-sibling-helpers`, `duplicate-call-sequence` and `recompile-duplication` (`rules/duplication.py`); `spec-api-signature-drift` (`rules/project_hygiene.py`, the source file); `asymmetric-exception-translation` (`rules/error_handling.py`, the callee's file); `mutable-module-level-exported` (`rules/state_and_effects.py`, the reading modules). A location's own path is never in its `related`
- [x] Extend each rule's existing test to assert the `related` of its hits (`tests/test_duplication.py`, `tests/test_project_hygiene.py`, `tests/test_nested_underscore_and_spec_signatures.py` where the spec-drift tests live, `tests/test_error_handling.py`, `tests/test_state_and_effects.py`)
- [x] `tests/test_registry.py`: assert that the set of rules emitting `related` across a fixture project equals the seven named above, so a cross-file rule added later without it fails
- [x] `tests/test_core.py`: a hit with no `related` serialises exactly as before (no key, same bytes)

**Acceptance Criteria:**

- [x] Every hit of the seven rules on a two-file fixture names the other file in `related`
- [x] A hit from any other rule has no `related` key, and its JSON line is byte-identical to the previous commit's for the same input
- [x] `registry-order.txt` and `CHECKS`' order are unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (`ruff-check`, `ruff-format`, `shellcheck`; never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/test_registry.py claude/skills/auditme/tests/test_duplication.py claude/skills/auditme/tests/test_project_hygiene.py claude/skills/auditme/tests/test_nested_underscore_and_spec_signatures.py claude/skills/auditme/tests/test_error_handling.py claude/skills/auditme/tests/test_state_and_effects.py` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/auditme/core.py` (`_emit` builds the line with `json.dumps(kwargs, sort_keys=True)`), the four rule modules above
- The skill's own `SKILL.md` documents the JSONL schema under "Mechanical sweep"; add `related` to that schema block in this task
- This changes the checker's output for the seven rules. It is a checker change between audit cycles, which the auditme skill allows; nothing else in this list depends on the old bytes

---

## Task 2: The changed-files runner

**Status:** done
**Priority:** high
**Complexity:** large
**Spec Reference:** API - The runner; Implementation - The changed-files runner; Error handling; Testing

**Technical Goal:** `claude/skills/auditme/checks/changed.py`, a stdlib-only
runner that sweeps the whole tree and fails on any unaccepted hit in scope - the
files changed since the diff base, or everything with `--all` - counting a hit as
in scope when its path or any `related` path changed, and failing (not skipping)
when the sweep cannot run.

**Subtasks:**

- [x] Create `changed.py` with `#!/usr/bin/env python3`, executable (`git update-index --chmod=+x`), exposing `changed_files()`, `in_scope()`, `main()` and `ChangedError` with the spec's signatures and docstrings
- [x] Argument parsing: `[--all] [--base <ref>] [<repo-root>]`; `<repo-root>` defaults to `git rev-parse --show-toplevel` of the working directory; a `--base` starting with `-` exits 1 before git runs
- [x] Diff base: the first of `@{upstream}`, `origin/main`, `main` that resolves with `git rev-parse --verify --quiet`; none resolving exits 0 with a message
- [x] Reportable-path filter: `.py`, `.md` outside the checker's spec-skip directories (read `_SPEC_SKIP_PARTS` from `auditme.rules.project_hygiene`, plus any hidden directory), and `uv.lock`; a scope with none of them exits 0 without sweeping
- [x] Run the sweep as `[sys.executable, <dir of changed.py>/audit.py, <repo-root>]`, list form, timeout 600 seconds; a timeout, an exception, a non-zero exit, a non-JSON line or an `auditme-check-crash` hit exits 1 naming the cause
- [x] Report each in-scope unaccepted hit as `path:line  rule` then its variant, sorted by path and line, then the accept-marker form and `SKIP=auditme-changed git commit`
- [x] `claude/skills/auditme/tests/test_changed.py`, each case in a temporary git repository with a stub `audit.py` where the case is about the runner rather than the checker: scope from the diff base; `--all`; a hit reported only through `related`; `--base -x` refused; no base resolves; sweep crash, timeout (a stub that sleeps past a monkeypatched timeout) and non-JSON line each exit 1; nothing reportable changed skips the sweep; one end-to-end case against the real `audit.py` on a fixture project

**Acceptance Criteria:**

- [x] A changed file with an unaccepted hit exits 1; an unchanged file's hit exits 0 without `--all` and 1 with it
- [x] A cross-file hit naming an unchanged file exits 1 when its `related` file changed
- [x] No failure path exits 0 except "no base resolves" and "nothing reportable changed"

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (`ruff-check`, `ruff-format`, `shellcheck`; never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_changed.py` passes

**Notes:**

- Depends on Task 1 (`in_scope` reads `related`)
- `tests/conftest.py` already puts `../checks` on `sys.path`, so `import changed` works in the tests

---

## Task 3: Publish the hooks

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation - The published hooks

**Technical Goal:** A `.pre-commit-hooks.yaml` at the repository root, so a
project can pin `auditme-changed` and `auditme-all` by revision.

**Subtasks:**

- [x] Write `.pre-commit-hooks.yaml` with the two hooks exactly as the spec gives them (`language: script`, `pass_filenames: false`, `always_run: true`, stages `pre-commit` and `manual`)
- [x] `claude/skills/auditme/tests/test_hooks_manifest.py`: parse the file (stdlib only - a minimal reader for this flat shape, or compare against the expected text) and assert both ids, entries, languages and stages; assert each `entry`'s script exists and is executable in the git index
- [x] A smoke test, skipped when `pre-commit` is not on `PATH`: in a temporary clone of this repository at `HEAD`, create a throwaway project with one unaccepted hit and run `pre-commit try-repo <clone> auditme-all --hook-stage manual --all-files`; it exits non-zero and names the hit

**Acceptance Criteria:**

- [x] `pre-commit try-repo` runs both hooks from this repository against a throwaway project
- [x] `auditme-all` fails on a hit in a file the throwaway project's last commit did not touch

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (`ruff-check`, `ruff-format`, `shellcheck`; never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_hooks_manifest.py` passes

**Notes:**

- Depends on Task 2
- `language: script` runs the file with its shebang; the interpreter on `PATH` must meet `requires-python` in `pyproject.toml`

---

## Task 4: The Stop hook

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Implementation - The Stop hook

**Technical Goal:** `claude/hooks/auditme-stop.sh`, which blocks the end of a
Claude Code turn once while an opted-in project's changed files carry unaccepted
hits, and does nothing anywhere else.

**Subtasks:**

- [x] Write the script: read the payload from stdin; exit 0 when `stop_hook_active` is true (`jq -r '.stop_hook_active // false'`); exit 0 unless the working directory is inside a git repository whose `.pre-commit-config.yaml` contains `id: auditme-changed`; otherwise run `python3 -I "$HOME/.claude/skills/auditme/checks/changed.py"` and, on exit 1, print `{"decision": "block", "reason": ...}` built with `jq -Rs` from the runner's output; `set -uo pipefail`
- [x] `tests/test_stop_hook.py` at the repository root (new directory `tests/`): run the script with `bash`, a temporary `HOME` holding a stub `changed.py`, and stub payloads, in an opted-in and a not-opted-in temporary repository: blocks once with the runner's text; passes when `stop_hook_active` is true; silent when not opted in; silent when the stub exits 0. Skip when `jq` is missing

**Acceptance Criteria:**

- [x] The script is silent and exits 0 in a repository without `auditme-changed`
- [x] It blocks at most once per turn
- [x] `shellcheck` passes on it

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (`ruff-check`, `ruff-format`, `shellcheck`; never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest tests/test_stop_hook.py` passes

**Notes:**

- Depends on Task 2 (the runner it calls)
- `bin/install-claude.py` symlinks every entry under `claude/` into `~/.claude/`, so `claude/hooks/` is installed as `~/.claude/hooks/` with no code change; Task 5 registers it

---

## Task 5: Register the Stop hook from the installer

**Status:** done
**Priority:** medium
**Complexity:** medium
**Spec Reference:** Implementation - The Stop hook (the `bin/install-claude.py` bullet); Error handling

**Technical Goal:** `bin/install-claude.py` adds the Stop hook to
`~/.claude/settings.json` once, keeping everything else in the file.

**Subtasks:**

- [x] After linking, read `~/.claude/settings.json` (absent means `{}`); refuse with a message naming the file, writing nothing, when it is not valid JSON or not an object
- [x] Add a `hooks.Stop` entry running `bash "$HOME/.claude/hooks/auditme-stop.sh"` unless an existing `Stop` hook command already names `auditme-stop.sh`
- [x] The first time the file is changed, copy the original to `settings.json.orig` (never overwrite an existing `.orig`); write the new file atomically (temporary file in the same directory, then `os.replace`)
- [x] `tests/test_install_claude.py` with `HOME` (or the installer's destination function) pointed at a temporary directory: added once on two runs; every other key and every other hook kept; invalid JSON refused with the file unchanged; `.orig` written once

**Acceptance Criteria:**

- [x] Running the installer twice leaves one Stop entry for the hook
- [x] An existing settings file's other content is unchanged byte for byte apart from the added entry's structure

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (`ruff-check`, `ruff-format`, `shellcheck`; never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest tests/test_install_claude.py` passes

**Notes:**

- Depends on Task 4
- Key file: `bin/install-claude.py` (`install_claude()`, `dest_claude_dir()`)
- Never run the installer against the real `~/.claude` in this task

---

## Task 6: The setup templates

**Status:** done
**Priority:** medium
**Complexity:** medium
**Spec Reference:** Implementation - The `/project-setup` skill (the `new` steps); The published hooks - CI

**Technical Goal:** The files `/project-setup` writes, as templates under
`claude/skills/project-setup/templates/`, project-agnostic, with placeholders
the skill fills.

**Subtasks:**

- [x] `pre-commit-config.yaml`: ruff check and format, shellcheck, and the `git@github.com:bnomis/agents.git` repo block with `auditme-changed` and `auditme-all`, `rev: {{AGENTS_REV}}`
- [x] `ci.yml`: checkout; the deploy-key step installing `AGENTS_DEPLOY_KEY` under the `github-agents` host alias with `IdentitiesOnly yes`, and the `url."git@github-agents:bnomis/agents.git".insteadOf "git@github.com:bnomis/agents.git"` rewrite; Python and uv; `uv sync`; `pre-commit run --all-files`; `pre-commit run auditme-all --hook-stage manual --all-files`; `{{TEST_COMMAND}}`. Each step commented with why, briefly
- [x] `ci-audit-step.yml`: the deploy-key step and the `auditme-all` step alone, for `adopt` to paste into an existing workflow
- [x] `AGENTS.md`, `CLAUDE.md` (`@AGENTS.md`), `TODO.md` and `DONE.md` (each with the convention header the shared todo skills expect), and `claude/rules/README.md` (what belongs there, pointing at `rule-scope.md`), with `{{PROJECT_NAME}}`
- [x] `claude/skills/project-setup/tests/test_templates.py`: every template exists; every placeholder is one of the documented set; the YAML templates' structure is checked as in Task 3

**Acceptance Criteria:**

- [x] No template names a project, path or date of any real project
- [x] The two CI templates use the same host alias and secret name as the spec

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (`ruff-check`, `ruff-format`, `shellcheck`; never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/project-setup/tests/test_templates.py` passes

**Notes:**

- Depends on Task 3 (the hook ids)
- The TODO.md/DONE.md headers follow `claude/skills/todo-review/conventions.md`

---

## Task 7: The `/project-setup` skill

**Status:** done
**Priority:** medium
**Complexity:** medium
**Spec Reference:** API - The skill; Implementation - The `/project-setup` skill

**User Story:** As an operator, I want one command that sets up a new project,
or adopts the shared guards into an existing one, so that every project gets the
same checks without my remembering each step.

**Subtasks:**

- [x] `claude/skills/project-setup/SKILL.md` with frontmatter matching the other skills (`name`, `description`, `when_to_use`, `allowed_tools: [Read, Write, Edit, Bash, AskUserQuestion]`)
- [x] `new`: the four steps in the spec, filling `{{AGENTS_REV}}` from `git ls-remote git@github.com:bnomis/agents.git refs/heads/main`, `{{PROJECT_NAME}}` from the directory name (confirmed) and `{{TEST_COMMAND}}` (asked)
- [x] `adopt`: the four steps in the spec - show and remove a project-local runner or Stop hook doing the same job; count unaccepted hits by rule with `pre-commit run auditme-all --hook-stage manual --all-files`; at zero add `ci-audit-step.yml` and the deploy-key steps, above zero file one `TODO.md` item by the todo-add conventions (dated count by rule; Fix direction: fix or accept every hit, then add the CI step)
- [x] Deploy-key steps exactly as the spec gives them, each confirmed before it runs, the key in the session's scratch directory, both files deleted after, the private key never printed
- [x] A "Do not" list: push; enable the CI gate over a non-zero count; run a step that changes GitHub without confirmation; print a key

**Acceptance Criteria:**

- [x] Every outward-facing step (deploy key, secret, commit) has a confirmation in the skill text
- [x] `adopt` never adds the CI step while the count is above zero

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (`ruff-check`, `ruff-format`, `shellcheck`; never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/project-setup/tests/test_templates.py` passes

**Notes:**

- Depends on Task 6
- Follows the shared rules on asking questions (`claude/rules/asking-questions.md`) and on secrets (`claude/rules/security.md`)

---

## Task 8: The user guide

**Status:** done
**Priority:** medium
**Complexity:** medium
**Spec Reference:** Documentation

**User Story:** As a new user, or an operator on a new machine or starting a new
project, I want a guide that takes me from nothing to working guards, so that I
can set everything up without having followed how it was built.

**Subtasks:**

- [x] `docs/setup.md`, the seven sections in the spec's order, each with runnable commands and placeholders saying where values come from: what you get; a new machine (prerequisites, clone, `bin/install-claude.py`, how to check it); a new user (access, SSH key, shared versus project rules); a new project (`/project-setup new`); an existing project (`/project-setup adopt`, the backlog step, enabling the gate); upgrading the checker (`pre-commit autoupdate --repo git@github.com:bnomis/agents.git`, catch-up in the same commit); troubleshooting (clone failures and the host alias, the Stop hook not firing, hits after an upgrade, `SKIP=auditme-changed`)
- [x] The "why" for each behaviour a user might want to change: changed-files scope at commit versus whole tree in CI; the pinned checker; the global opt-in Stop hook running the installed checker; no gate over a backlog
- [x] `README.md`: a short section saying what the repository is, linking `docs/setup.md`
- [x] Check every command in the guide against the code it describes (flags, paths, hook ids, secret name, host alias)

**Acceptance Criteria:**

- [x] Every command in `docs/setup.md` names a flag, path or id that exists in this repository
- [x] No count in prose is undated or ungenerated (`claude/rules/counts-in-prose.md`)

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (`ruff-check`, `ruff-format`, `shellcheck`; never `--no-verify`)

**Notes:**

- Depends on Tasks 3-7
- Follows `claude/rules/user-guides.md` and `claude/rules/markdown.md`

---

## Task 9: End-to-end check, deduplication, close the spec

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Acceptance criteria

**Technical Goal:** Prove the setup works from nothing in throwaway
repositories, remove duplication the new modules introduced, and mark the spec
implemented.

**Subtasks:**

- [x] In temporary directories with a temporary `HOME`, walk `docs/setup.md`'s "a new machine" and "a new project" sections as written, using a local clone of this repository in place of GitHub where a step needs the remote (`pre-commit try-repo`), and record anything the guide got wrong; fix the guide (walked by hand on 2026-10-31, after the queue; fixed in `3607aa2` and amendment 1.2; the deploy-key steps were not walked, see `TODO.md`, "Adopt the shared guards in each project")
- [x] Against a throwaway project: a commit adding an unaccepted hit fails `auditme-changed`; `auditme-all` fails on a hit in an untouched file; a cross-file hit whose named file is unchanged fails when its peer changed
- [x] Hoist anything `changed.py`, the Stop hook test helpers and the installer test helpers duplicate (constants, temporary-repository builders) to a single owner: grep each literal collection and one-line helper the new modules define, and import rather than copy; prefer a module the consumer already imports
- [x] Set the spec's `**Status:**` to `implemented`

**Acceptance Criteria:**

- [x] Every acceptance criterion in the spec holds in the throwaway repositories, apart from the GitHub-side parts (a real CI run, a real deploy key), which are listed in the commit body as the operator's to check
- [x] The guide's walked sections needed no step it does not state (true since amendment 1.2 stated the `src/` layout, 2026-10-31)

**Definition of Done:**

- [x] `pre-commit run --all-files` exits 0
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests claude/skills/project-setup/tests tests` passes

**Notes:**

- Depends on Tasks 1-8
- After the merge, outside this list and the operator's to run: `bin/install-claude.py` on the real machine; `/project-setup adopt` in each project, the motivating one first (its review task list replaces its own runner and Stop hook with these); adding `AGENTS_DEPLOY_KEY` to each project that enables the CI gate

---
