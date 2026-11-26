# Default rule catalogue

**Version:** 1.0
**Status:** implemented
**Date:** 2026-11-25

Moves every rule the runner has today into the format of the
[Rules repository](../rules-repository/spec.md) spec. The result is a
catalogue in this repository that new rules repositories are copied from (see
[Rules init](../rules-init/spec.md)). This spec then removes the built-in
registry, so the runner holds no rules of its own and `AUDITOR_RULES_PATH`
becomes required.

It is the third of four specs and requires
[Auditor CLI](../auditor-cli/spec.md) and
[Rules repository](../rules-repository/spec.md) to be implemented.

The move is behaviour-preserving. On the same project, a sweep with the
catalogue as its rules repository gives the same hits as the built-in
registry, and Phase B lists the same candidates.

## Module location

- `src/auditor/catalogue/` (new) - a complete rules repository: `auditor-rules.toml`,
  `packs.toml` (defined by the Rules init spec) and
  `rules/<rule-dir>/`.
- `src/auditor/api/` - gains the shared helpers listed below.
- Removed: `src/auditor/registry.py`, `src/auditor/rules/`, the listers in
  `src/auditor/phaseb/` (`architecture.py`, `docrefs.py`, `testmap.py`, and
  the registrations in `candidates.py`), `src/auditor/briefs/`,
  `claude/rules/auditme/`, `claude/skills/auditme/requests.md` and
  `tests/checker/registry-order.txt`.
- `claude/skills/auditme/SKILL.md` - the Phase B checklist and the
  documented rule conflicts move out (see below).

## What becomes a rule directory

| Today | Becomes |
|-------|---------|
| Each function in `CHECKS` | A `check` rule. The directory is named by its rule id, or by its family when it emits several ids from a table (`check_text_patterns` becomes `text-patterns`) |
| Each function in `PROJECT_CHECKS` | A `project-check` rule |
| Each Phase B question with a lister (the questions registered with `register_question`) | A `question` rule with `brief.md`, `lister.py` and its `kinds`, `batch-size` and `takes-depth` |
| Each other Phase B question in the `SKILL.md` checklist | A `question` rule with only `rule.md` (a sampled question) |
| Each `##` section of `claude/rules/auditme/coding-standards.md`, `imports.md` and `dependencies.md` | A `standard` rule, named `std-<section-slug>` |

`rule.md` of a check holds the rationale from the check's docstring: the
signal, the carve-outs and the dated refinements. The function's docstring
then says only what the function does. A check's `standards` key lists the
standard rules it enforces; for example, `leading-underscore-binding` lists
`std-no-leading-underscores`.

Rule ids that the runner emits itself stay in the runner, and
`RulesRepo.rule_ids` always includes them: `auditme-check-crash`,
`unreadable-file`, `src-loose-module`, `ruff` and `lockfile-drift`. `ruff` and
`lockfile-drift` are emitted by checks that move to the catalogue. Their ids
stay reserved because the never-accepted rule hard-codes them.

## API

These are the helpers promoted to `auditor.api`. They are every helper that a
rule other than its own module's uses, plus everything in `auditor.core`:

```python
# src/auditor/api/__init__.py  -  re-exports, by full path, from:
#   auditor.api.source      read_and_parse, cached_source, source_lines, py_files, all_py_files, relpath, module_dotted
#   auditor.api.project     audit_roots, first_party_dirs, declared_roots, extra_roots, auditme_table, never_accepted
#   auditor.api.accept      accept_reason, is_never_accepted
#   auditor.api.calls       from_import_bindings, call_bindings, reexport_aliases, resolve_call, callable_short_name
#   auditor.api.errors      class_lineage, package_class_parents, is_broad_handler, raises_section_names, translator_envelopes
#   auditor.api.flow        if_chain
#   auditor.api.docs        spec_markdown_files
#   auditor.api.candidates  Candidate, site_candidate, span_candidate, section_candidate
#   auditor.api.report      emit
API_VERSION = (1, 0)
```

The list above is a starting point taken from the cross-module imports on
2026-11-25. The task that splits each family module adds any other helper that
it finds used by two or more rules. A helper used by one rule moves into that
rule's `check.py`.

## Implementation

1. **Baseline.** Before anything moves, save three outputs in the scratchpad:
   - `auditor check` over this repository;
   - `auditor check` over every fixture project the tests create;
   - `auditor phaseb candidates <Q>` for every listed question.

   The fixture runs use the dump that `tests/checker/conftest.py` gives with
   `AUDITOR_DUMP_FIXTURES`, a test-only variable added for this step and
   removed afterwards.
2. **Split by family.** Work one family module at a time: promote the shared
   helpers, write one rule directory per check, and move that check's tests
   into the rule's `tests/`. The tests use `auditor.testing`, today's
   `conftest.py` helpers turned into a pytest plugin. The registry keeps
   running the rules not yet moved, so every step passes the tests.
3. **Phase B.** Each lister moves into its question's `lister.py`, and each
   brief moves into `brief.md`, with its `**Brief version:**` unchanged. The
   ledger entries therefore still match, and no verdict is invalidated.
4. **Prose.** The checklist text of each question, and of each standards
   section, moves into `rule.md` word for word. `SKILL.md` replaces its
   checklist with `auditor rules questions` and its standards references
   with the SessionStart hook. Its "Documented conflicts" entries move into
   the `rule.md` of the rule each one names as the winner. The general
   conflict procedure stays in `SKILL.md`.
5. **Change requests.** `claude/skills/auditme/requests.md` is retired in
   favour of the rules repository's `TODO.md`, as the Rules repository spec
   says under Change requests. Its parts go as follows:
   - **The `## Open` section** is empty at the time of writing (checked on
     2026-11-25), so no item needs to move. If an entry is open when this step
     runs, it is shipped or rejected first, as `requests.md` itself requires.
   - **Each `## Rejected` entry** concerns one rule. It moves into that rule's
     `rule.md`, under `## Rejected widenings`, word for word. Today that is
     the `Call`-values entry for `mutable-module-level-exported`.
   - **The file's prose** on why requests block the next audit moves into
     `SKILL.md` step 3, beside the `auditor rules pending` precondition.
   - **The checklist line in `SKILL.md`'s completion gate** ("`requests.md`'s
     `## Open` section was empty at audit start") becomes "`auditor rules pending`
     exited 0 at audit start".
   - **Every other reference to `requests.md`** is rewritten to point at the
     rules repository's `TODO.md`, or at the rule's `rule.md` for a rejected
     widening. This covers `SKILL.md`, `docs/reference/skills.md`, and the
     comments and docstrings in the moved rule code and its tests.
     `grep -rn requests.md` finds none afterwards.
6. **Remove the built-ins.** Delete the registry and the rule modules. With
   `AUDITOR_RULES_PATH` unset, every command now raises the unset-variable
   `RulesRepoError`.
7. **Equivalence.** With `AUDITOR_RULES_PATH=src/auditor/catalogue`, compare against the
   baseline from step 1:
   - the sweep hits must be equal as sets of `(rule, variant, path, line, evidence, accepted)`;
   - the Phase B candidate lists must be equal, ids and hashes included.

   Any difference is a bug in the move, not a change to accept.
8. **This repository's own audit.** The catalogue is the default set that
   `auditor rules init` copies from, not a rules repository that any project
   audits with. Locally, this repository is audited like any other project:
   its `.envrc` names whichever rules repository the user made with
   `auditor rules init`.
   - The test suite sets `AUDITOR_RULES_PATH` to `src/auditor/catalogue/`
     itself, because the tests need the default set.
   - CI sets `AUDITOR_RULES_PATH` to `src/auditor/catalogue/` too, because CI
     has no access to a user's private rules repository and needs some rules
     to run with.
9. **Sweep coverage of the catalogue.** The rule code under
   `src/auditor/catalogue/rules/` sits inside the `src/auditor` root, but its
   directories are not Python packages: their names have hyphens, and nothing
   imports them by module name. Before step 6, run the sweep and check how it
   names these modules. Then declare `src/auditor/catalogue/rules` in
   `[tool.auditme] roots` with whatever form names each `check.py` and
   `lister.py` by its file, and exclude it from the `src/auditor` root. Both
   the declaration and the reason for it go in the task's commit message.
   Every rule file must be audited in exactly one root: a sweep that skipped
   the catalogue would report rule code as clean without reading it.

## Error handling

- **Missing rules repository:** after step 6, the runner fails as the Rules
  repository spec says: `ERROR: AUDITOR_RULES_PATH is not set: ...`, exit 2.
  This is a breaking change for every project that pins the hooks. Version
  0.3.0 marks it, and `docs/setup.md` gives the upgrade steps.
- **Equivalence failure:** step 7 lists each differing hit or candidate. The
  task stops until each one is fixed in the moved code.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `AUDITOR_RULES_PATH` | env, path | none (now required) | As in the Rules repository spec |
| `[tool.auditme] never-accepted` | list of str | `[]` | Now validated against the loaded repository's `rule_ids()` |

## External dependencies

None beyond those in the Rules repository spec.

## Tests

- Each rule's tests pass under `auditor rules test`, with
  `AUDITOR_RULES_PATH=src/auditor/catalogue`.
- `tests/catalogue/test_catalogue.py` checks the following:
  - `auditor rules check` passes;
  - every rule directory is in exactly one pack (this assertion is added by the Rules init task list, which writes `packs.toml`);
  - `rule_ids()` equals the ids the guide's rule tables document in
    `docs/guide/checker.md` (the file today's `RULE_IDS` test reads), which replaces that test;
  - every `standards` entry names a `standard` rule.
- The equivalence comparison from step 7 is kept as a test over the fixture
  projects. The comparison over this repository's own sweep is run once, in
  the task, because this repository's hits change with its code.
