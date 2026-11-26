# auditme checker tests

Tests for the mechanical sweep in [`../../src/auditor/`](../../src/auditor/):
the shared helpers, the check registry, the driver, the `auditor` command and
the individual predicates.

## Running them

The checker is stdlib-only and installed as the `auditor` package, so `uv sync`
is the only setup:

```shell
uv run pytest tests/checker
```

Run it from the repository root.

## What is covered

Every predicate in `CHECKS` is exercised. `test_registry.py` asserts that, so a
check added without tests fails the suite rather than being noticed an audit
cycle later.

| File | Covers |
|------|--------|
| `test_core.py` | acceptance markers (scoped and unscoped), duplicate suppression, the emitted record schema, AGENTS.md lazy-import rows |
| `test_registry.py` | every defined check is registered, none twice, each has tests, and no recorded check has moved within `CHECKS` |
| `test_driver.py` | package discovery under `src/`, extra roots such as `bin/`, per-root passes, `--package`, `--extra-root`, crash isolation, and one end-to-end run of the shipped entry point |
| `test_error_handling.py` | the exception-handling and error-reporting predicates |
| `test_get_container_default.py` | `get-container-default-then-method-call`: each of its guards and each documented non-goal |
| `test_imports_and_surfaces.py` | the import-graph and public-surface predicates |
| `test_annotated_all.py` | `annotated-all-assignment` and its `__all__`-guard precondition |
| `test_state_and_effects.py` | the mutation, side-effect and hidden-state predicates |
| `test_style_and_naming.py` | the naming, ordering and annotation-style predicates |
| `test_leading_underscore_binding.py` | `leading-underscore-binding`: every binding shape, the names it leaves to other rules, and the retired regexes staying retired |
| `test_project_hygiene.py` | ruff, the lockfile, and numbered spec cross-references |
| `phaseb/` | the listed Phase B path: the A1, A4, A11, A17, A19, T1 and T2 listers and the Doc1, Doc2, Doc4 and Doc5 listers, the `docrefs` sections and name resolution, candidate hash, ledger read, merge and dismiss, batch planning and run checking, the command line, and the briefs |
| `phaseb/test_architecture_candidates.py` | the A11, A19, A1 and A17 listers: positive shapes, carve-outs, sweep-hit drops, id stability and content hashes |
| `phaseb/test_testmap.py`, `phaseb/test_t1_candidates.py`, `phaseb/test_t2_candidates.py` | the test tree index (test files, imports, direct tests, caller routes), and the T1 and T2 listers with their content hashes |

Each predicate has at least one case for the shape it fires on and one for the
nearest shape it must not fire on. Where a predicate documents a carve-out -
`isinstance` guards, `type(exc).__name__`, strftime directives, `load_*` names -
the carve-out has its own case, so narrowing a predicate cannot be undone
silently.

## Adding a check

A new predicate needs a test file, or a new module of cases in an existing one,
covering three things: the shape it fires on, every carve-out that must **not**
fire, and what an accept marker scoped to that rule does. The `project` and
`run_check` fixtures in `conftest.py` build a throwaway tree and return the
parsed hits, so a case is usually a source snippet and one assertion.

`registry-order.txt` records the emission order of `CHECKS`. Appending a check
does not require touching it. Removing or moving one does - and that is
deliberate, because reordering changes the emission order of every hit after
it, which the next audit reads as a finding delta.
