# Review: clearing this repository's audit backlog

**Date:** 2026-11-21
**Review page:** https://claude.ai/artifact/7tKv35vidwVGDm9cm8UMVH

## What is being reviewed and how

`TODO.md`'s "Fix or accept this repository's audit backlog": once this
repository declared its audit roots (amendment 1.11 of
`agents/specs/project-setup/spec.md`), the sweep reported its own checker and
tests unswept until then. On 2026-11-21, `python3
claude/skills/auditme/checks/audit.py .` gave 685 unaccepted hits across 32
rules. Every hit was classified the same day: 473 genuine and to be fixed, 184
false positives of the checker on this repository, 28 genuine but better
accepted. This review asks for an answer to each decision and accept item
below; the fixes the coding standards already settle are listed as the plan,
not asked. Nothing is changed until every item has an answer; then a task
list is written from this review.

## Automatic checks

- `audit.py .` on 2026-11-21: 685 unaccepted, 5 accepted.
- Spot-checked against the source the same day: the `filesystem-envelope-gap`
  handlers skip an unparsable file (`core.py:48`, `core.py:608`); the test
  `literal-duplication` hits are expected values in asserts
  (`tests/phaseb/test_architecture_candidates.py:98-100`); `audit.py` runs the
  project-level checks in `PROJECT_CHECKS` (line 187) and again inside every
  root's `CHECKS` pass (line 203).

## The plan the coding standards settle

These are fixed, not asked: the standards forbid leading underscores and
`from X import Y`, and require alphabetical literals, accurate `Raises:`
sections and letting unexpected exceptions propagate.

- **Raises sections (12 hits, 2 from today's work):** add `RootsError` to the
  six `Raises:` sections it now reaches through `_audit_roots`, and add the six
  missing sections (`declared_roots`, `entry_point_targets`, `target_bytes`,
  `file_target`, `write_ledger`, `resolve_base`).
- **Specs (3 hits):** amend `check_run`, `list_candidates(..., depth=)` and
  `register_question(..., kinds, ...)` in the two implemented specs that still
  show the old signatures.
- **Small mechanical fixes:** `collections.abc` for the typing aliases (3), the
  two bare annotations, `_` for unused bindings (15), the read `_module` loop
  target, sorted literals (16) and fixture dict keys (8),
  `FILESYSTEM_TOUCHING_CALLS` as a frozenset, the two in-function imports, a
  shared `_candidate` fixture helper, the two raw `read_bytes` calls wrapped in
  `PhaseBError`, a shared `SINK_TOKENS` and the other 19 rule-vocabulary
  constants, and a conftest `git()` helper for the 8 repeated git commands.
- **Dead handlers (36 hits):** remove the `try/except Exception` around
  `ast.unparse` of a tree that has just parsed; `run_check` already reports a
  crashing check as a hit. Update the S112 comment in `pyproject.toml`.
- **Renames (about 330 hits):** strip the leading underscore from the 15
  cross-module names (`_emit`, `_relpath`, `_audit_roots`, `_EMITTED` and the
  rest, about 530 references) together with converting the code's
  `from auditme.core import ...` to full paths, one module at a time; then the
  module-local names; then the test helpers and the test `from` imports. A
  name that would collide when stripped (`_types` with the `types` module;
  `_candidate`, `_line`, `_read`, `_verdict`, `_git` in tests; `_members`)
  gets a new name such as `make_candidate`. The five markers in `test_core.py`
  for `leading-underscore-attribute-access` are revisited after the rename.

## Decisions

### R1-R7. Checker refinements for the false positives (184 hits)

Each refinement narrows a rule (a carve-out), so it is a skill change made
between audits, documented in the rule's docstring and SKILL.md's documented
refinements, with a test that the carve-out does not fire. Narrowing removes
hits in every project audited; none adds a hit.

| Id | Refinement | Hits it clears | Recommended |
|---|---|---|---|
| R1 | The line-pattern rules (`leading-underscore-*`, `legacy-typing`, `aliased-imports`, `relative-import-nonpackage`) skip string literals that are not docstrings: a plain string is data, such as a fixture's source | about 21 | ship |
| R2 | `literal-duplication` in test files: **A** skip one-member literals and literals inside `assert` and `pytest.param` (recommended: a test restates the value it expects); **B** skip test files altogether; **C** no change, accept each | about 122 | A |
| R3 | `filesystem-envelope-gap` fires only where the handler translates the error into a project error, as its rationale says; a handler that skips the file is not a gap | 23 | ship |
| R4 | `filesystem-op-without-envelope` accepts a call to a same-module helper that wraps the operation in its own `OSError` handling | 1 | ship |
| R5 | `redundant-sink-caller-plus-callee`: ignore calls inside nested functions and self-recursion, resolve the callee by qualified name, and compare keyword values, not only names | 6 | ship |
| R6 | `get-container-default-then-method-call` skips a mapping that comes from `tomllib`, since TOML has no null | 2 | ship |
| R7 | `in-function-import` labels a module under a declared root as first-party (a label, no count change) | 0 | ship |

### E1. Clearing `except-interpolation` (30 hits)

- **Background:** 23 sites raise `PhaseBError(f'...: {error}') from error`, and
  the command-line entry points (`audit.py`, `changed.py`, `phaseb.py`) print
  only `str(exc)`, so the interpolated cause is today the user's only
  diagnostic. 7 sites build a report message, not an exception.
- **Options:**
  - **A (recommended):** the three entry points also print `exc.__cause__`;
    the 23 raise sites drop `{error}`; the 7 report-message sites are
    accepted. Check first that no test asserts on the system error text.
  - **B:** accept all 30, reason: a standard-library-only command-line tool
    shows only the message, so the cause text is the user's only diagnostic.

### P1. Run the project-level checks once (2 hits)

- **Background:** `check_lockfile` and `check_ruff_version` are in both
  `CHECKS` and `PROJECT_CHECKS` (amendment 1.8), so with this repository's
  five roots `uv lock --check` runs five times; the driver suppresses the
  duplicate output.
- **Options:**
  - **A (recommended):** the driver runs `PROJECT_CHECKS` once for every
    project and they leave `CHECKS`. Removing them from `CHECKS` changes the
    emission order of hits, which the next audit's convergence note must name;
    amendment 1.8's sentence changes to match.
  - **B:** keep both, and accept the two hits.

## Items to accept

Each line gets a scoped `# auditme: accept[<rule>] <reason>` marker.
Recommendation for every item: approve.

| Id | Hit | Reason for accepting |
|---|---|---|
| A1 | `non-alphabetical-literal` on `BASE_CANDIDATES` (`changed.py`) | the order is the priority in which a diff base is tried |
| A2 | `non-alphabetical-literal` on `GIT_ENV_ARGS` | `-c` flag and value pairs, in order |
| A3 | `silent-broad-except` at `audit.py:100` (`run_check`) | reporting a crashing check as a hit is the handler's job |
| A4 | `literal-duplication` on the six finding-kind tuples passed to `@register_question` | each question declares its own kinds; equal values are coincidence |
| A5 | `mutable-module-level-exported` on `REGISTRY` | filled by `@register_question` at import, and patched by a test |
| A6 | `get-container-default-then-method-call` on the two `imports_of` hits | an internal mapping that never holds `None` |
| A7 | `layer-has-domain-error-raises-stdlib` on the six `ValueError`s in `parse_result` | it validates one result line as `json.loads` does; both land in one `except ValueError` that records a problem |
| A8 | `passthrough-shim` on `build_test_map` | public, documented and in `phaseb.__all__` |
| A9 | `empty-init-while-siblings-export` on `rules/__init__.py` | rule modules are reached through `auditme.registry` |
| A10 | `subprocess-without-memoisation` on `check_ruff` | its arguments differ per root |
| A11 | `duplicated-word` on the rule's four `the the` / `not not` fixtures | the duplication is the fixture |
| A12 | `legacy-typing` at `style_and_naming.py:838` and the three docstring mentions of a leading-underscore name | prose about the rule, not a use |

## Answers

Answered by the operator on the review page on 2026-11-21, read back from its database the same day.

| Item | Answer | Comment |
|---|---|---|
| R1 | ship (recommended) | none |
| R2 | A (skip one-member literals and literals inside assert and pytest.param) (recommended) | none |
| R3 | ship (recommended) | none |
| R4 | ship (recommended) | none |
| R5 | ship (recommended) | none |
| R6 | ship (recommended) | none |
| R7 | ship (recommended) | none |
| E1 | A (entry points print the cause; raise sites drop it) (recommended) | none |
| P1 | A (run PROJECT_CHECKS once; drop them from CHECKS) (recommended) | none |
| A1 | approve (recommended) | none |
| A2 | approve (recommended) | none |
| A3 | approve (recommended) | none |
| A4 | approve (recommended) | none |
| A5 | approve (recommended) | none |
| A6 | approve (recommended) | none |
| A7 | approve (recommended) | none |
| A8 | approve (recommended) | none |
| A9 | approve (recommended) | none |
| A10 | approve (recommended) | none |
| A11 | approve (recommended) | none |
| A12 | approve (recommended) | none |
