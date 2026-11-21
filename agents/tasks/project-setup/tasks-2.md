# Tasks: Project setup

**Spec:** `agents/specs/project-setup/spec.md`
**Created:** 2026-10-31
**Version:** 2

Implements amendment 1.2 of the spec only: `audit.py` audits whatever roots
exist instead of refusing a project without `src/<package>/`, and a `.py` file
directly in `src/` is reported as a `src-loose-module` hit. `tasks-1.md`
implemented version 1.1 and is complete.

The motivating finding is the top item in `TODO.md`, "A new project cannot
commit Python without a `src/<package>/` layout". Task 4 moves it to
`DONE.md`.

Nothing here changes another repository or the operator's home directory.
Every test builds its projects in temporary directories.

The repository has no affected-tests tool. Each task names its own test files,
and the last task runs every test tree the checker's change can reach.

---

## Task 1: The driver audits whatever roots exist

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation - Projects without a `src/` package (1.2), steps 1, 2 and 4; Error handling (1.2 rows); Testing (1.2, `test_driver.py`)

**Technical Goal:** Stop `audit.py` from refusing a project with no `src/`, or
with no package under it, so the sweep passes over whatever roots exist. A
mistyped scope must still be an error.

**Subtasks:**

- [x] `tests/test_driver.py`: replace `test_a_missing_src_directory_is_an_error` and `test_an_empty_src_directory_is_an_error` with tests for: a project with only `bin/` is swept over `bin/` and `main()` returns 0; an empty project returns 0 and prints `audit.py: no package under src/ and no extra root; nothing to audit` on stderr; a scope that is not a directory returns 2. Run them and see the first two fail before changing the driver
- [x] `claude/skills/auditme/checks/audit.py` `main()`: replace the `src does not exist` guard with `ERROR: <scope> is not a directory` (exit 2) when the scope is not a directory
- [x] `main()`: when `_audit_roots()` returns no root, print the notice above on stderr and return 0, instead of `ERROR: no package under <scope>/src`
- [x] Leave the `--package` and `--extra-root` errors unchanged, and keep their existing tests (`test_a_named_package_that_does_not_exist_is_an_error`, `test_a_named_extra_root_that_does_not_exist_is_an_error`) passing
- [x] Update `audit.py`'s module docstring: `src/` is optional, and the sweep passes over the packages under it, if any, then the extra roots

**Acceptance Criteria:**

- [x] A project holding only `bin/tool.py` with a leading-underscore function gives that hit and exit 0
- [x] A project with no Python gives no hits, the notice and exit 0
- [x] For a project with a package under `src/`, the output is byte-identical to `3d7aed9`'s on the existing driver fixtures (every other `test_driver.py` test passes unchanged)

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (`ruff-check`, `ruff-format`, `shellcheck`; never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_driver.py -q -p no:cacheprovider` passes

**Notes:**

- Key files: `claude/skills/auditme/checks/audit.py` (`main()`), `claude/skills/auditme/checks/auditme/core.py` (`_audit_roots()`, `_packages_under()`, which already returns `[]` when `src/` is absent)
- A scratch run on 2026-10-31 with both guards removed swept a `bin/`-only project, an empty project and this repository without any `auditme-check-crash` hit

---

## Task 2: Report a module directly in `src/` as `src-loose-module`

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** API - The driver (1.2); Implementation - Projects without a `src/` package (1.2), step 3; Testing (1.2, `test_driver.py`)

**Technical Goal:** A `.py` file directly in `src/` belongs to no audit root,
so it is never audited. Report it as a hit, so the commit names it, rather
than leaving it out unseen.

**Subtasks:**

- [x] Tests first, in `tests/test_driver.py`: a project holding only `src/a.py` gives one hit with `rule='src-loose-module'`, `variant='module directly under src/, outside any package'`, `path='src/a.py'`, `line=1`, `evidence='a.py'`, `accepted=false`; the same with a package beside it; a line-1 `# auditme: accept[src-loose-module] <reason>` marker gives `accepted=true` with that reason; `--package <name>` emits none; two loose files come out in sorted order
- [x] `claude/skills/auditme/checks/auditme/core.py`: add `loose_src_modules(scope: pathlib.Path) -> list[pathlib.Path]` with the spec's signature and docstring: every `*.py` file directly in `<scope>/src/`, sorted, and `[]` when `src/` is absent
- [x] `audit.py` `main()`: before the first pass, and only when `--package` is not given, emit one hit per loose module through `_emit()`, reading acceptance with `_accept_reason(_source_lines(path), 1, rule='src-loose-module')`. Emit it from the driver, not as a check in `CHECKS`, so it also fires when no root exists
- [x] Emit loose-module hits before the no-root notice, so a project holding only `src/a.py` gives the hit, the notice and exit 0
- [x] Document `src-loose-module` in `claude/skills/auditme/SKILL.md` beside the description of extra roots under "Mechanical sweep": what it reports, why the driver emits it, and how to accept one

**Acceptance Criteria:**

- [x] Each case in the first subtask holds
- [x] `CHECKS` and `tests/registry-order.txt` are unchanged
- [x] A project with a package under `src/` and no loose module gives output byte-identical to Task 1's

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (`ruff-check`, `ruff-format`, `shellcheck`; never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_driver.py claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/test_registry.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- Key files: `audit.py`, `auditme/core.py` (`_emit`, `_accept_reason`, `_source_lines`)
- The new name has no leading underscore, following the shared Python rule, although its neighbours in `core.py` have one
- `tests/test_registry.py` checks only the `check_*` functions in `CHECKS`, never rule names, so a driver-level rule needs no change there. `loose_src_modules` is not a check, and must not be named `check_*`

---

## Task 3: The commit hook passes a project without `src/`

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Testing (1.2, `test_changed.py`); Acceptance criteria (1.2)

**Technical Goal:** Prove end to end, through `changed.py` in a real
temporary git repository, that a project with no `src/` can commit a clean
script and is blocked by a hit in one or by a loose `src/` module.

**Subtasks:**

- [x] `claude/skills/auditme/tests/test_changed.py`, using the git helper in `conftest.py`: in a temporary repository with no `src/`, a commit of a clean `bin/tool.py` makes `changed.py` exit 0
- [x] In the same setup, a `bin/tool.py` holding a leading-underscore function makes `changed.py` exit 1, naming `bin/tool.py` and `leading-underscore-def-class`
- [x] A commit adding a loose `src/a.py` makes `changed.py` exit 1, naming `src-loose-module`. With the line-1 accept marker added, it exits 0

**Acceptance Criteria:**

- [x] Each case in the subtasks holds, run through `changed.py`'s `main()` against a temporary repository, not by calling `audit.py` directly

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (`ruff-check`, `ruff-format`, `shellcheck`; never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_changed.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 1 and 2
- `changed.py` itself is unchanged by the spec. If a case needs a change to it, stop the task as `blocked` and name what failed

---

## Task 4: Guide, skill wording, close the item and the spec

**Status:** done
**Priority:** medium
**Complexity:** small
**Spec Reference:** Documentation (amendment 1.2); Acceptance criteria (1.2)

**Technical Goal:** Tell users which files the checker audits, run the whole
checks once, record the finished item, and mark the spec implemented.

**Subtasks:**

- [x] `docs/setup.md`, "What you get": say which files are audited (packages under `src/<package>/` and scripts in `bin/`), that a `.py` file directly in `src/` is reported as `src-loose-module`, and that other directories are not swept
- [x] `claude/skills/auditme/SKILL.md`: drop "the directory containing `src/`" from the `<project-root>` wording, so `src/` reads as optional
- [x] Byte-identity check: in a temporary directory, build a project with a package under `src/` and a `bin/` script, each holding at least one hit. Run `audit.py` from `git show 3d7aed9:claude/skills/auditme/checks/...` (export that tree to a temporary directory) and from the working tree, and compare the two outputs with `cmp`
- [x] Create `DONE.md` from `claude/skills/project-setup/templates/DONE.md`. Move the `TODO.md` item "A new project cannot commit Python without a `src/<package>/` layout" to its end: append its heading and body unchanged, then `Done: 2026-MM-DD - <the commits of Tasks 1-3>; spec amendment 1.2; tasks-2.md.`, using the date of the move. Then remove it from `TODO.md`
- [x] Set the spec's `**Status:**` to `implemented`

**Acceptance Criteria:**

- [x] The `cmp` in the byte-identity subtask reports no difference
- [x] Every acceptance criterion marked 1.2 in the spec holds

**Definition of Done:**

- [x] `pre-commit run --all-files` exits 0
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests claude/skills/project-setup/tests tests -q -p no:cacheprovider` passes
- [x] `git show $(git log --diff-filter=A --format=%H -- agents/tasks/project-setup/tasks-2.md):TODO.md > <scratch>/todo-before.md`, then `python3 claude/skills/todo-review/verify_bodies.py <scratch>/todo-before.md TODO.md DONE.md` exits 0

**Notes:**

- Depends on Tasks 1-3
- `<scratch>` is a temporary directory made for the run (`mktemp -d`), never the repository
