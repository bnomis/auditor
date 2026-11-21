# Tasks: Project setup

**Spec:** `agents/specs/project-setup/spec.md`
**Created:** 2026-11-21
**Version:** 4

Implements the mechanism of amendment 1.11 of the spec ("Declared audit
roots"): `[tool.auditme] roots` in `pyproject.toml`, read once by
`_audit_roots()` so `audit.py`, the hooks' `changed.py` and the Phase B
listers all follow it, with per-root `modules` modes, the errors, and the
documentation. `tasks-1.md` to `tasks-3.md` are complete; 1.5 to 1.10 were done
without a task list.

Declaring this repository's own roots is `tasks-5.md`, which runs after this
list is merged to `main`. On a branch the commit hook's diff base is
`origin/main`, so once the roots are declared it would check every file this
list changes - checker modules that carry the backlog - and block every
commit on hits the commit did not add. Nothing here declares roots, so every
commit on this branch is swept as today.

The motivating finding is the top item in `TODO.md`, "The audit reads none of
this repository's own Python". It stays open until `tasks-5.md` closes it.
Every test builds its projects in temporary directories. Nothing here changes
another repository or the operator's home directory.

The repository has no affected-tests tool. Each task names its own test files,
and the last task runs every test tree the change can reach.

---

## Task 1: Read the declared roots

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation - Declared audit roots (1.11); Error handling (the 1.11 rows)

**Technical Goal:** `_audit_roots()` returns the roots a project declares in
`[tool.auditme]`, in order, replacing the defaults, and the helpers name and
walk each root by its mode, so every consumer follows the declaration with no
call site changed.

**Subtasks:**

- [x] Check the starting point: `grep -rnwE 'ROOT_MODULES|RootsError|declared_roots' claude/skills/auditme/checks` finds nothing; if it does, stop the list as `blocked`, naming what exists
- [x] In `claude/skills/auditme/checks/auditme/core.py`: a `RootsError(Exception)`, and `declared_roots(scope) -> list[tuple[pathlib.Path, str]] | None` that reads `<scope>/pyproject.toml` with `tomllib`, returns `None` when the file or the `[tool.auditme]` table is absent, and otherwise each `(scope / path, mode)` in order, `mode` defaulting to `package`
- [x] Validation, each raising `RootsError` with the spec's message: `[tool.auditme]` not a table; `roots` not a list of tables; an entry with no `path`, an unknown key, or a `modules` other than `package` or `top-level`; a root that does not exist or holds no `.py` file (for a `top-level` root, no `.py` file directly in it); two `package` roots where one contains the other; a `top-level` root inside a `package` root. Invalid TOML raises `RootsError` only when the file's text contains `[tool.auditme`; otherwise `declared_roots` returns `None`
- [x] `ROOT_MODULES: types.MappingProxyType[pathlib.Path, str]`, empty by default, rebound (never mutated) whenever `_audit_roots()` reads declared roots
- [x] `_audit_roots(scope)`: the declared roots when `declared_roots` returns a list, else today's packages under `src/` then extras
- [x] `_all_py_files(root)`: for a root `ROOT_MODULES` marks `top-level`, the `.py` files directly in it, sorted; otherwise unchanged
- [x] `module_dotted(path, root)`: for a `top-level` root, the parts below the root without the root's name (`audit.py` is `audit`); otherwise unchanged
- [x] `corpus_py_files(scope, root)`: the files of every declared root when roots are declared; otherwise unchanged
- [x] New `claude/skills/auditme/tests/test_roots.py`: a declared list is returned in order and replaces `src/` and `bin/`; a `top-level` root sweeps only its own files, named by stem, and a package inside it only as its own root; a `package` root names modules after the root; no table, and no `pyproject.toml`, give today's roots; every error row raises `RootsError` with its message; invalid TOML without `[tool.auditme` gives the defaults; `corpus_py_files` spans the declared roots

**Acceptance Criteria:**

- [x] Each case in `test_roots.py` passes
- [x] A project with no `[tool.auditme]` gets exactly the roots it got before (the existing `test_driver.py` passes unchanged)

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_roots.py claude/skills/auditme/tests/test_driver.py -q -p no:cacheprovider` passes

**Notes:**

- Key file: `claude/skills/auditme/checks/auditme/core.py` (`_audit_roots`, `_extra_roots`, `_all_py_files`, `module_dotted`, `corpus_py_files`, `EXTRA_ROOT_NAMES`)
- The checker is standard-library only: `tomllib` is in the standard library from Python 3.11
- A root absent from `ROOT_MODULES` is a `package` root, which keeps every test that builds a root by hand working

---

## Task 2: The driver's errors and `--extra-root`

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation - Declared audit roots (1.11); Error handling (the 1.11 rows)

**Technical Goal:** `audit.py` turns a `RootsError` into its message and exit
2, and `--extra-root` replaces the declared list for one run.

**Subtasks:**

- [x] In `main()` of `claude/skills/auditme/checks/audit.py`: catch `RootsError` from reading the roots, print `ERROR: <message>` on stderr, return 2
- [x] With `--extra-root`, sweep only the named roots, each as a `package` root, ignoring `[tool.auditme]`; `--package` unchanged
- [x] The no-root notice and the project-level-only pass (1.8) apply when no root is declared and none is found; a declared list is never empty after validation
- [x] Tests in `claude/skills/auditme/tests/test_driver.py`: a project with `[tool.auditme]` sweeps its declared roots and not `src/`; each `RootsError` exits 2 with `ERROR: ` and nothing on stdout; `--extra-root` overrides the declaration; a `top-level` root's hits name its files by their paths

**Acceptance Criteria:**

- [x] Each case above passes
- [x] A project without `[tool.auditme]` gets the same output as before

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_driver.py claude/skills/auditme/tests/test_roots.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1

---

## Task 3: The hooks and Phase B follow the declaration

**Status:** todo
**Priority:** high
**Complexity:** small
**Spec Reference:** Implementation - Declared audit roots (1.11) (every consumer reads `_audit_roots()`)

**Technical Goal:** Show, with tests, that `changed.py` and `phaseb.py plan`
see the declared roots, and that a `RootsError` stops each the way a failed
sweep does.

**Subtasks:**

- [ ] `claude/skills/auditme/tests/test_changed.py`: on a fixture whose Python lives only in a declared root, `changed.py --all` reports an unaccepted hit there and exits 1; a malformed `[tool.auditme]` makes the sweep fail (exit 1, naming the `audit.py` error)
- [ ] `claude/skills/auditme/tests/phaseb/` (the test module for `plan`): on the same fixture, `phaseb.py plan` lists a candidate from the declared root for A4
- [ ] `phaseb.py`: if `plan` (or any subcommand that reads roots) meets a `RootsError`, print `ERROR: <message>` on stderr and exit 2; add a test
- [ ] Change code only where a test shows a consumer not following `_audit_roots()`

**Acceptance Criteria:**

- [ ] Each case above passes

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_changed.py claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 2
- `sweep()` in `changed.py` runs `audit.py <repo-root>` with no options, so it follows the declaration once Task 1 is in

---

## Task 4: Document the declared roots

**Status:** todo
**Priority:** medium
**Complexity:** small
**Spec Reference:** Documentation (amendment 1.11)

**User Story:** As a maintainer of a project whose Python is not under `src/`
or `bin/`, I want the guide to show how to declare my roots, so that the
audit and the hooks cover my code.

**Subtasks:**

- [ ] `docs/setup.md`, "What you get": a project whose Python lives elsewhere declares its roots in `[tool.auditme]`, with the spec's example, and undeclared directories are not swept
- [ ] `docs/reference/cli.md`, the `audit.py` section: the table, both `modules` values, that the list replaces the defaults, how `--extra-root` overrides it, and the new exit-2 errors in its exit table
- [ ] `claude/skills/auditme/SKILL.md`: name `[tool.auditme]` beside the description of roots in the mechanical sweep
- [ ] `uv run --group docs mkdocs build --strict`

**Acceptance Criteria:**

- [ ] Every error the spec's 1.11 rows name appears in `docs/reference/cli.md`
- [ ] The docs build passes

**Definition of Done:**

- [ ] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [ ] `uv run --group docs mkdocs build --strict` exits 0

**Notes:**

- Depends on Task 2

---

## Task 5: Whole-branch checks

**Status:** todo
**Priority:** medium
**Complexity:** small
**Spec Reference:** Testing (1.11)

**Technical Goal:** Check the whole branch before it merges, so `tasks-5.md`
starts from a `main` that holds the mechanism.

**Subtasks:**

- [ ] Hoist anything the new code duplicates: grep `claude/skills/auditme/checks` for each constant and one-line helper Task 1 added, and import rather than copy
- [ ] Confirm the spec's 1.11 Testing bullet is covered by `test_roots.py`, `test_driver.py`, `test_changed.py` and the Phase B tests
- [ ] Leave the spec's `**Status:**` and the `TODO.md` item alone: `tasks-5.md` closes both

**Acceptance Criteria:**

- [ ] Every check below passes

**Definition of Done:**

- [ ] `pre-commit run --all-files` exits 0
- [ ] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [ ] `uv run --no-project --with pytest pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 1 to 4
- The whole-tree audit still sees no roots here, since nothing declares them yet; that is `tasks-5.md`
