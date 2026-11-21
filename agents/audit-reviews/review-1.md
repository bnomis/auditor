# Audit Review 1

**Date:** 2026-11-21
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`)
**Commit:** 83e59c0e61f85d5997909aa7faa8e97d59952e8a
**Script output:** /tmp/audit-auditor.jsonl (43 hits, 43 accepted, 0 unaccepted)
**Script version:** 074b2d235c6133f1cd0c742d84442f3b67fc20c3e9cdba0e9e943cb71e8472a8
**Convergence note:** first audit of this repository. There is no earlier review, so every sampled question ran on the whole tree, and every listed question (A1, A4, A11, A17, A19, T1, T2, Doc1, Doc2, Doc4, Doc5) judged every candidate as new. Every finding is catch-up, not drift.
**Review page:** https://claude.ai/artifact/PVuGCXFgsm6sbyBfja6BvX

## What is being reviewed and how

This is the checker repository's first full audit of its own code: the mechanical sweep, every Phase B question in every category, and the spec review. The sweep is clean. Phase B found real work, most of it in a few shared causes. For each finding group below, approve it (it becomes a task) or flag it (dismissed, with your reason recorded). Then answer the decisions. Each answer is recorded in [Answers](#answers).

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 43 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 953 candidates judged, none left out |
| `phaseb.py check` on every listed question | pass, after one retry (Doc4 batch 7 wrote four non-string `reason` values; a fresh reviewer redid it) |
| Every sampled question returned a hit list or "no hits" | pass |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| Prior findings to re-verify | none: no `summary.md`, no `agents/tasks/audit-reviews/` |

## Summary

The sweep reports 43 hits, all accepted by markers. Phase B flags 159 listed candidates (A1 35, A4 1, A17 1, T1 68, T2 23, Doc4 21, Doc5 10; none for A11, A19, Doc1 or Doc2). The sampled questions flag further sites under A2, A5, A8, A9, A13-A15, S1, S4, P1-P3, Sec2, Sec4, T3, D1 and Doc3 (each counted in its section), and the spec review finds 19 template gaps. Most findings fall into a few groups:

- the checker crashes rather than reporting when a file it reads cannot be read (A1, A2);
- registered `check_*` functions count as pure-named functions that do I/O (A9: 68 of its 79 hits);
- helpers without a direct test, and pure helpers without a property test (T1, T2);
- names in specs and docs that went stale after renames (Doc4, Doc5).

The audit also found a checker defect: the Phase B test index never reads this repository's tests (see [Checker request](#checker-request)).

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits. Hits by rule, all accepted:

| Rule | Hits (all accepted) |
|---|---|
| `duplicated-word` | 4 |
| `empty-init-while-siblings-export` | 1 |
| `except-interpolation` | 7 |
| `from-import` | 3 |
| `get-container-default-then-method-call` | 2 |
| `layer-has-domain-error-raises-stdlib` | 6 |
| `leading-underscore-attribute-access` | 1 |
| `legacy-typing` | 1 |
| `literal-duplication` | 6 |
| `mutable-module-level-exported` | 3 |
| `non-alphabetical-literal` | 4 |
| `passthrough-shim` | 1 |
| `silent-broad-except` | 1 |
| `subprocess-without-memoisation` | 3 |

## Phase B per-question results

The listed questions' verdicts are in `agents/audit-reviews/ledger/<Q>.jsonl`; every flagged one is listed below. The sampled questions ran on the whole tree (mode: full, first audit).


### A1 (listed): External call envelope

- **Candidates judged:** 59 of 59; none left unjudged
- **Flagged:** 35
- **Hits:**
  - `claude/skills/auditme/checks/auditme/core.py::accepted_lazy_imports::call:agents.read_text#1` - agents.read_text sits in no try and the function has no envelope, so OSError and UnicodeDecodeError escape; wrap the read in try/except (OSError, UnicodeDecodeError) and raise a domain error such as RootsError.
  - `claude/skills/auditme/checks/auditme/core.py::all_names::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/core.py::declared_roots::call:pyproject.read_text#1` - pyproject.read_text sits outside the try that translates TOMLDecodeError, so OSError and UnicodeDecodeError escape; move the read into a try that raises RootsError for (OSError, UnicodeDecodeError).
  - `claude/skills/auditme/checks/auditme/core.py::reads_by_module_and_name::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/core.py::script_entry_points::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/core.py::source_lines::call:path.read_text#1` - The handler catches only UnicodeDecodeError and returns [] rather than translating, and OSError escapes; catch OSError too and raise a domain error (or document that a default is wanted).
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py::list_a17_candidates.read_entries::call:path.read_text#1` - path.read_text in the nested read_entries has no try, and both calls from list_a17_candidates sit outside any envelope; wrap the read in try/except (OSError, UnicodeDecodeError) raising PhaseBError.
  - `claude/skills/auditme/checks/auditme/phaseb/batches.py::check_batch::call:path.read_text#1` - The handler catches (OSError, UnicodeDecodeError) but returns the failure as a problem string instead of raising PhaseBError, and callers check_run and read_run_verdicts call it outside any envelope; raise PhaseBError or record that reporting is the intended handling.
  - `claude/skills/auditme/checks/auditme/rules/duplication.py::check_duplicate_call_sequence::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/duplication.py::check_literal_duplication::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/duplication.py::check_paired_sibling_helpers::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/duplication.py::check_recompile_duplication::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/duplication.py::check_redundant_sink_caller_plus_callee::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/duplication.py::check_redundant_sink_caller_plus_callee::call:path.read_text#2` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::check_asymmetric_exception_translation::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::check_asymmetric_exception_translation::call:path.read_text#2` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::check_filesystem_op_without_envelope::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::check_filesystem_op_without_envelope::call:path.read_text#2` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::check_inconsistent_error_translation::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::check_inconsistent_error_translation::call:path.read_text#2` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::check_layer_has_domain_error_but_raises_stdlib::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::check_sibling_error_no_common_base::call:src.read_text#1` - src.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::translator_envelopes::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py::check_empty_init_with_exporting_siblings::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py::check_migration_shim_consumers::call:path.read_text#1` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py::check_migration_shim_consumers::call:path.read_text#2` - path.read_text is inside a try that catches only SyntaxError and UnicodeDecodeError and skips or returns None, so OSError escapes and nothing is translated; catch OSError and raise a domain error (PhaseBError or RootsError).
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py::check_reexport_in_non_init::call:path.read_text#1` - path.read_text sits in a try that catches only SyntaxError and UnicodeDecodeError, so an OSError escapes untranslated, and the handler continues rather than raising a domain error; catch OSError and raise a domain *Error (or accept the skip with a marker if skipping unreadable files is intended).
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py::parse_package_layering::call:agents.read_text#1` - agents.read_text has no try and no envelope, so an OSError or UnicodeDecodeError reading AGENTS.md escapes; wrap it in try/except (OSError, UnicodeDecodeError) that raises a domain *Error.
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py::project_bans_as_imports::call:agents.read_text#1` - The OSError/UnicodeDecodeError handler returns False instead of translating; raise a domain *Error from it, or mark the default return as accepted if a missing AGENTS.md should read as no ban.
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py::project_has_all_guard::call:path.read_text#1` - The OSError/UnicodeDecodeError handler continues instead of translating; raise a domain *Error, or accept the skip with a marker if it is intended.
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py::check_lockfile::call:subprocess.run#1` - The handler catches only FileNotFoundError and returns, so other OSError and SubprocessError escape and the missing-tool case is not translated; catch OSError (and subprocess.SubprocessError) and raise a domain *Error, or accept the silent return with a marker.
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py::check_lockfile::call:subprocess.run#2` - The retry run sits in the same try, whose handler catches only FileNotFoundError and returns; catch OSError and subprocess.SubprocessError and raise a domain *Error, or accept the return with a marker.
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py::check_ruff::call:subprocess.run#1` - The handler catches only FileNotFoundError and emits a finding then continues, so other OSError and SubprocessError escape; catch OSError and subprocess.SubprocessError and raise a domain *Error, or accept the emit-and-continue with a marker.
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py::check_ruff_version::call:subprocess.run#1` - The handler catches only FileNotFoundError and returns, so other OSError and SubprocessError escape; catch OSError and subprocess.SubprocessError and raise a domain *Error, or accept the return with a marker.
  - `claude/skills/auditme/checks/auditme/rules/state_and_effects.py::dataclass_frozen_by_name::call:path.read_text#1` - path.read_text sits in a try that catches only SyntaxError and UnicodeDecodeError and continues, so an OSError escapes untranslated; catch OSError and raise a domain *Error, or accept the skip with a marker if it is intended.

### A4 (listed): Docstring Raises accuracy

- **Candidates judged:** 46 of 46; none left unjudged
- **Flagged:** 1
- **Hits:**
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py::list_candidates` - RootsError

### A11 (listed): Exhaustion via assert_never

- **Candidates judged:** 3 of 3; none left unjudged
- **Flagged:** 0
- **Hits:** none

### A17 (listed): Public-surface drift

- **Candidates judged:** 2 of 2; none left unjudged
- **Flagged:** 1
- **Hits:**
  - `claude/skills/auditme/checks/auditme/phaseb/__init__.py` - __all__ exports Candidate, Lister, MergeResult, TestRef, Verdict, architecture, build_test_map, question_kinds and register_question, but no code outside auditme/phaseb/ and outside the test tree reads any of them, and no literal getattr, importlib.import_module or entry point does either (only tests use them; architecture.py registers its listers via candidates.register_question, not the package surface): drop them from __all__ (keep the `architecture` import for its registration side effect), or give the tests a documented test surface instead of the public one.

### A19 (listed): Wrong logger level for broad-except

- **Candidates judged:** 1 of 1; none left unjudged
- **Flagged:** 0
- **Hits:** none

### T1 (listed): Test coverage of branchy logic

- **Candidates judged:** 268 of 268; none left unjudged
- **Flagged:** 68
- **Hits:**
  - `claude/skills/auditme/checks/auditme/core.py::all_names` - a direct test of all_names, including a module whose __all__ cannot be read
  - `claude/skills/auditme/checks/auditme/core.py::call_bindings` - a direct test of call_bindings on a module and an __init__.py
  - `claude/skills/auditme/checks/auditme/core.py::dotted_read` - a direct test of dotted_read on a dotted attribute read and a non-dotted expression
  - `claude/skills/auditme/checks/auditme/core.py::extra_roots` - a direct test of extra_roots with present, absent and declaration-ignored roots
  - `claude/skills/auditme/checks/auditme/core.py::from_import_bindings` - a direct test of from_import_bindings including a relative import in an __init__.py
  - `claude/skills/auditme/checks/auditme/core.py::is_main_guard` - a direct test of is_main_guard on a __main__ guard and on other if statements
  - `claude/skills/auditme/checks/auditme/core.py::py_files` - a direct test of py_files skipping excluded directories
  - `claude/skills/auditme/checks/auditme/core.py::reads_by_module_and_name` - a direct test of reads_by_module_and_name on attribute and from-import reads
  - `claude/skills/auditme/checks/auditme/core.py::reexport_aliases` - a direct test of reexport_aliases on a package re-export and a non-function binding
  - `claude/skills/auditme/checks/auditme/core.py::resolve_call` - a direct test of resolve_call on a bare name, a module attribute, a method and an unresolvable call
  - `claude/skills/auditme/checks/auditme/core.py::script_entry_points` - a direct test of script_entry_points with and without a __main__ guard
  - `claude/skills/auditme/checks/auditme/core.py::surface_files` - a direct test of surface_files on a package with and without __all__
  - `claude/skills/auditme/checks/auditme/core.py::sys_modules_key` - a direct test of sys_modules_key on a sys.modules subscript and a non-matching expression
  - `claude/skills/auditme/checks/auditme/phaseb/batches.py::read_plan` - read_plan on a run directory: a valid plan.json read back, and an absent, non-JSON and malformed plan raising PhaseBError
  - `claude/skills/auditme/checks/auditme/rules/duplication.py::test_expectation_nodes` - test_expectation_nodes marking assert and pytest.param literals in a test file
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::a2_branches_for_call` - a2_branches_for_call on a call with and without branch-bearing arguments
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::callable_short_name` - callable_short_name for a name, an attribute, a call and an unsupported expression
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::clean_absence_return` - a direct test of clean_absence_return exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::empty_container_default` - a direct test of empty_container_default exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::enveloped_functions` - a direct test of enveloped_functions exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::guarded_body_nodes` - a direct test of guarded_body_nodes exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::handler_catches` - a direct test of handler_catches exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::handler_translates` - a direct test of handler_translates exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::handler_types` - a direct test of handler_types exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::is_toml_source` - a direct test of is_toml_source exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::level_catches` - a direct test of level_catches exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::module_tuple_constants` - a direct test of module_tuple_constants exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::name_is_reguarded` - a direct test of name_is_reguarded exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::name_scopes` - a direct test of name_scopes exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::nested_call_sites` - a direct test of nested_call_sites exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::none_hostile_use` - a direct test of none_hostile_use exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::raised_name` - a direct test of raised_name exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::raises_section_names` - a direct test of raises_section_names exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::receiver_is_toml_mapping` - a direct test of receiver_is_toml_mapping exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::records_visible_failure` - a direct test of records_visible_failure exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::status_failure_branch` - a direct test of status_failure_branch exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::stmt_end_by_lineno` - a direct test of stmt_end_by_lineno exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::toml_returning_functions` - a direct test of toml_returning_functions exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::translator_envelopes` - a direct test of translator_envelopes exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::unset_optional_guard` - a direct test of unset_optional_guard exercising its if-branches
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py::declared_root_modules` - declared_root_modules returns a package root's directory name and a top-level root's module names, and nothing when no root is declared
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py::maybe_emit_layering` - maybe_emit_layering emits for an upward import and returns without emitting for a module outside the package root or an accepted pair
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py::parse_package_layering` - parse_package_layering reads the layer order and exception rows from AGENTS.md and returns empty results when the section is absent
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py::project_bans_as_imports` - project_bans_as_imports is True when AGENTS.md declares the ban and False when AGENTS.md is missing or silent
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py::project_has_all_guard` - project_has_all_guard is True for a file reading another module's __all__ and False for a project with none or an unparseable file
  - `claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py::walk_function_scopes` - walk_function_scopes yields sync and async defs and skips other nodes
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py::parse_spec_def` - parse_spec_def joins a wrapped def across lines and returns None for an unparseable block
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py::ruff_executable` - ruff_executable returns the project .venv/bin/ruff when it is executable and PATH ruff otherwise
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py::ruff_hook_pin` - ruff_hook_pin returns repo line, rev line and version for a pinned entry, None parts for a missing rev, and None with no ruff-pre-commit entry
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py::signature_params` - signature_params renders positional, keyword-only marker and defaulted parameters, and returns None for a non-def node
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py::spec_markdown_files` - spec_markdown_files lists markdown under scope and skips hidden directories and record files
  - `claude/skills/auditme/checks/auditme/rules/state_and_effects.py::branch_overrides` - branch_overrides is True for a branch assigning the variable before reading it and False for one reading it first
  - `claude/skills/auditme/checks/auditme/rules/state_and_effects.py::dataclass_decorator` - dataclass_decorator returns True for @dataclass(frozen=True), False for bare @dataclass and None for another decorator
  - `claude/skills/auditme/checks/auditme/rules/state_and_effects.py::dataclass_frozen_by_name` - dataclass_frozen_by_name maps frozen and non-frozen dataclasses by name and treats a name defined twice as frozen if any definition is
  - `claude/skills/auditme/checks/auditme/rules/state_and_effects.py::member_hazard` - member_hazard names a mutable literal or non-frozen dataclass member and returns None for an immutable one
  - `claude/skills/auditme/checks/auditme/rules/state_and_effects.py::member_nodes` - member_nodes returns the elements of a literal and the single element of a comprehension
  - `claude/skills/auditme/checks/auditme/rules/state_and_effects.py::module_level_binding` - module_level_binding returns (name, value) for single-name Assign and AnnAssign and (None, None) for other statements
  - `claude/skills/auditme/checks/auditme/rules/state_and_effects.py::mutable_members` - mutable_members finds mutable members through a nested tuple and dedupes them
  - `claude/skills/auditme/checks/auditme/rules/state_and_effects.py::mutable_value_shape` - mutable_value_shape returns the shape and wrap for dict, list and set literals and builtin calls, and None for an immutable value
  - `claude/skills/auditme/checks/auditme/rules/state_and_effects.py::walk_chain` - walk_chain is True when every arm of an if/elif/else chain overrides the variable and False when an arm or the else is missing
  - `claude/skills/auditme/checks/auditme/rules/state_and_effects.py::wrapped_literal` - wrapped_literal returns the wrapper name and literal for MappingProxyType({...}) and None for a non-literal argument
  - `claude/skills/auditme/checks/auditme/rules/style_and_naming.py::bare_nonbuiltin_generic_annotation_in_file` - bare_nonbuiltin_generic_annotation_in_file emits for a bare non-builtin generic annotation and skips a file with a syntax error
  - `claude/skills/auditme/checks/auditme/rules/style_and_naming.py::bare_parametric_annotation_in_file` - a direct test of bare_parametric_annotation_in_file, including a file that does not parse
  - `claude/skills/auditme/checks/auditme/rules/style_and_naming.py::docstring_nodes` - a direct test of docstring_nodes on module, function and class docstrings and a body whose first statement is not a string
  - `claude/skills/auditme/checks/auditme/rules/style_and_naming.py::is_fixed_length_tuple` - a direct test of is_fixed_length_tuple for tuple[X, Y], Final[tuple[...]], tuple[X, ...] and a non-tuple annotation
  - `claude/skills/auditme/checks/auditme/rules/style_and_naming.py::leading_underscore_bindings` - a direct test of leading_underscore_bindings, including the module-level assignment it leaves to the regexes
  - `claude/skills/auditme/checks/auditme/rules/style_and_naming.py::literal_format_lines` - a direct test of literal_format_lines, including a file that does not parse
  - `claude/skills/auditme/checks/auditme/rules/style_and_naming.py::mask_string_literals` - a direct test of mask_string_literals, including a file that does not parse and a multi-line or non-ASCII literal

### T2 (listed): Property-based tests

- **Candidates judged:** 23 of 23; none left unjudged
- **Flagged:** 23
- **Hits:**
  - `claude/skills/auditme/checks/auditme/core.py::accept_reason` - property test
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py::child_qualname` - property test
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py::hit_on_anchor` - property test
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py::is_under` - property test
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py::reaches_exception` - property test
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py::type_source_of` - property test
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py::inverse_names` - property test
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py::section_blocks` - property test
  - `claude/skills/auditme/checks/auditme/phaseb/docrefs.py::api_fence_name` - property test
  - `claude/skills/auditme/checks/auditme/phaseb/docrefs.py::backticked_tokens` - property test
  - `claude/skills/auditme/checks/auditme/phaseb/docrefs.py::code_shaped` - property test
  - `claude/skills/auditme/checks/auditme/phaseb/testmap.py::reach` - property test
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::class_lineage` - property test
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::is_categorical_class_name_expr` - property test
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py::raises_section_names` - property test
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py::ruff_hook_pin` - property test
  - `claude/skills/auditme/checks/auditme/rules/state_and_effects.py::hazard_summary` - property test
  - `claude/skills/auditme/checks/auditme/rules/style_and_naming.py::is_stdlib_public_access_only` - property test
  - `claude/skills/auditme/checks/auditme/rules/style_and_naming.py::literal_format_lines` - property test
  - `claude/skills/auditme/checks/auditme/rules/style_and_naming.py::mask_string_literals` - property test
  - `claude/skills/auditme/checks/auditme/rules/style_and_naming.py::ruff_dunder_all_key` - property test
  - `claude/skills/auditme/checks/changed.py::option_value_is_flag` - property test
  - `claude/skills/auditme/checks/changed.py::reportable` - property test

### Doc1 (listed): AGENTS.md project structure

- **Candidates judged:** 4 of 4; none left unjudged
- **Flagged:** 0
- **Hits:** none

### Doc2 (listed): AGENTS.md tools and libraries list

- **Candidates judged:** 3 of 3; none left unjudged
- **Flagged:** 0
- **Hits:** none

### Doc4 (listed): Specs match implementation

- **Candidates judged:** 402 of 402; none left unjudged
- **Flagged:** 21
- **Hits:**
  - `agents/specs/auditme-false-positives/spec.md::Auditme false positives > API::(unresolved)` - agents/specs/auditme-false-positives/spec.md:107 names `_reach_sites(func.body)` in the `nested_call_sites` docstring; the helper is now `reach_sites` (claude/skills/auditme/checks/auditme/rules/error_handling.py:2367), and the code's docstring says `reach_sites(func.body)`
  - `agents/specs/auditme-false-positives/spec.md::Auditme false positives > Implementation::(unresolved)` - agents/specs/auditme-false-positives/spec.md:150 names `_reach_sites(node.body)`; the helper is now `reach_sites` (claude/skills/auditme/checks/auditme/rules/error_handling.py:2367); agents/specs/auditme-false-positives/spec.md:152 names `_handler_passes_on`; the function is now `handler_passes_on` (claude/skills/auditme/checks/auditme/rules/error_handling.py:2304); agents/specs/auditme-false-positives/spec.md:168 names `_level_catches`; the function is now `level_catches` (claude/skills/auditme/checks/auditme/rules/error_handling.py:2355)
  - `agents/specs/auditme-false-positives/spec.md::Auditme false positives > Module location::(unresolved)` - agents/specs/auditme-false-positives/spec.md:56 lists `_handler_passes_on` in error_handling.py; the function is now `handler_passes_on` (claude/skills/auditme/checks/auditme/rules/error_handling.py:2304)
  - `agents/specs/auditme-false-positives/spec.md::Auditme false positives > Module location::claude/skills/auditme/checks/auditme/rules/style_and_naming.py` - agents/specs/auditme-false-positives/spec.md:57 names `_handler_passes_on` in rules/error_handling.py; the code defines it public as `handler_passes_on` (error_handling.py:2304)
  - `agents/specs/listed-phase-b-architecture-questions/spec.md::Listed Phase B architecture questions > Implementation > Hoists::(unresolved)` - agents/specs/listed-phase-b-architecture-questions/spec.md:113 says `check_assert_never_missing` passes `_extract_string_eq_var`; the function is public `extract_string_eq_var` (rules/state_and_effects.py:583) and the rule calls `if_chain(node, extract_string_eq_var)` at line 545
  - `agents/specs/listed-phase-b-architecture-questions/spec.md::Listed Phase B architecture questions > Module location::(unresolved)` - agents/specs/listed-phase-b-architecture-questions/spec.md:59 says the A11, A19, A1 and A17 briefs are version 1; claude/skills/auditme/phaseb/briefs/A1.md:3 is at Brief version 2
  - `agents/specs/listed-phase-b-architecture-questions/spec.md::Listed Phase B architecture questions > Settings::claude/skills/auditme/checks/phaseb.py::--depth` - agents/specs/listed-phase-b-architecture-questions/spec.md:260 says --depth applies to A4 only; list_candidates (claude/skills/auditme/checks/auditme/phaseb/candidates.py:153) hands --depth to any lister, and list_t1_candidates and list_t2_candidates (candidates.py:764, :994) take a depth too
  - `agents/specs/listed-phase-b-documentation-questions/spec.md::Listed Phase B documentation questions > API::claude/skills/auditme/checks/auditme/phaseb/docrefs.py::DocTarget` - agents/specs/listed-phase-b-documentation-questions/spec.md:62 lists DocTarget kinds as function, class, method, setting, option, file or directory; claude/skills/auditme/checks/auditme/phaseb/docrefs.py:139 adds field, which field_target produces
  - `agents/specs/listed-phase-b-documentation-questions/spec.md::Listed Phase B documentation questions > Error handling::(unresolved)` - agents/specs/listed-phase-b-documentation-questions/spec.md:110 says a syntax-error file is skipped 'as `_source_definitions` does now'; that function was hoisted into core.py as `corpus_definitions` (commit c96e76c) and no longer exists
  - `agents/specs/listed-phase-b-documentation-questions/spec.md::Listed Phase B documentation questions > Implementation > Doc4 and Doc5 candidates::(unresolved)` - agents/specs/listed-phase-b-documentation-questions/spec.md:153 says a def or class target is hashed as `ast.get_source_segment` with decorators; target_bytes in claude/skills/auditme/checks/auditme/phaseb/candidates.py hashes whole source lines from the first decorator's line to the end line instead
  - `agents/specs/listed-phase-b-test-questions/spec.md::Listed Phase B test questions > Implementation > Briefs::(unresolved)` - agents/specs/listed-phase-b-test-questions/spec.md:232 says each brief has '**Brief version:** 1', but claude/skills/auditme/phaseb/briefs/T1.md carries '**Brief version:** 3'.
  - `agents/specs/project-setup/spec.md::Project setup > Implementation > The ruff version check (1.4)::(unresolved)` - agents/specs/project-setup/spec.md:414: says check_ruff_version runs on every pass, emitting the same hit that emit()'s de-duplication reduces to one, and is appended to CHECKS; registry.py puts it in PROJECT_CHECKS, which the driver (audit.py) runs once before the per-root passes, and not in CHECKS
  - `agents/specs/project-setup/spec.md::Project setup > Module location::(unresolved)` - agents/specs/project-setup/spec.md:147: says check_ruff_version is appended to CHECKS; claude/skills/auditme/checks/auditme/registry.py lists it in PROJECT_CHECKS, whose comment says none of its checks is in CHECKS
  - `agents/specs/raises-section-resolution/spec.md::Raises section resolution > Implementation::(unresolved)` - agents/specs/raises-section-resolution/spec.md:113 says a raise that escapes f gets chain `(f,)`; escapes adds `(qualname, '')` instead, a trailing '' sentinel marking the raiser (error_handling.py:2621), which describe() reads to say 'raised by'
  - `agents/specs/raises-section-resolution/spec.md::Raises section resolution > Prerequisite::agents/tasks/repeatable-phase-b/tasks-1.md` - agents/specs/raises-section-resolution/spec.md:43: says the shared resolver is "called by the rule at the default"; error_handling.py:2625 and :2663 call auditme.core.resolve_call(..., class_methods=True); agents/specs/raises-section-resolution/spec.md:46: says `grep -n class_methods` on error_handling.py prints nothing; it prints lines 2625 and 2663, which pass class_methods=True
  - `agents/specs/repeatable-phase-b/spec.md::Repeatable Phase B > API::claude/skills/auditme/checks/auditme/phaseb/batches.py::check_run` - agents/specs/repeatable-phase-b/spec.md:183: says check_run "raises nothing"; batches.py check_run calls read_plan and question_kinds and documents Raises: PhaseBError when the plan cannot be read or names an unregistered question
  - `agents/specs/repeatable-phase-b/spec.md::Repeatable Phase B > API::claude/skills/auditme/checks/auditme/phaseb/candidates.py::list_candidates` - agents/specs/repeatable-phase-b/spec.md:183 says check_run raises nothing, but check_run (batches.py) raises PhaseBError when the plan cannot be read or names an unregistered question
  - `agents/specs/repeatable-phase-b/spec.md::Repeatable Phase B > Error handling::(unresolved)` - agents/specs/repeatable-phase-b/spec.md:219 says PhaseBError is in phaseb/__init__.py, but it is defined in claude/skills/auditme/checks/auditme/phaseb/errors.py and only re-exported from __init__.py
  - `agents/specs/repeatable-phase-b/spec.md::Repeatable Phase B > Implementation > The result line (1.2)::claude/skills/auditme/checks/auditme/phaseb/batches.py::check_run` - agents/specs/repeatable-phase-b/spec.md:292-296 give brief versions A4 3, Doc4/Doc5 2, Doc1 2, T1 and A1 unchanged, but the briefs now carry A4 4, Doc4 4, Doc5 4, Doc1 3, T1 3 and A1 2
  - `agents/specs/repeatable-phase-b/spec.md::Repeatable Phase B > Module location::(unresolved)` - agents/specs/repeatable-phase-b/spec.md:100 says check_raises_section_drift keeps the shared resolver's default class_methods=False so its output does not change; the rule in claude/skills/auditme/checks/auditme/rules/error_handling.py now calls auditme.core.resolve_call(..., class_methods=True) at lines 2625 and 2663
  - `agents/specs/repeatable-phase-b/spec.md::Repeatable Phase B > Settings::claude/skills/auditme/checks/phaseb.py::--batch-size` - agents/specs/repeatable-phase-b/spec.md:350 gives --batch-size a default of 48; claude/skills/auditme/checks/phaseb.py defaults it to None and uses the question's registered batch size (question_batch_size), which is 48 for A4 but 24 for Doc4 and Doc5 and 12 for Doc1 and Doc2 (candidates.py DOC_BATCH_SIZE, AGENTS_BATCH_SIZE)

### Doc5 (listed): User docs match implementation

- **Candidates judged:** 142 of 142; none left unjudged
- **Flagged:** 10
- **Hits:**
  - `docs/guide/checker.md::The audit checker > Reading the output::(unresolved)` - docs/guide/checker.md:104 says `accepted` is true when an AGENTS.md row covers the hit, but maybe_emit_layering (claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py) returns without emitting anything when the (importer, imported) pair is in the AGENTS.md accepted-exceptions table, so an AGENTS.md-covered layering-violation is never printed with accepted: true (only in-function-import emits an accepted hit for an AGENTS.md row).
  - `docs/guide/checker.md::The audit checker > The rules > Project-level checks::.pre-commit-config.yaml` - docs/guide/checker.md:326-330 lists layering-violation, as-import, in-function-import and spec-api-signature-drift as project-level checks that ask about the project rather than a package, but claude/skills/auditme/checks/auditme/registry.py puts their check functions in CHECKS, run once per root, and PROJECT_CHECKS (run once per sweep) holds only check_lockfile and check_ruff_version; their hits appear once only through core.emit's duplicate suppression.
  - `docs/guide/checker.md::The audit checker > What it audits::(unresolved)` - docs/guide/checker.md:35 says "No other directory is swept" after listing src/ packages and bin/ as the roots, but auditme.core.audit_roots sweeps exactly the roots a project declares in [tool.auditme] in pyproject.toml (any directory, replacing src/ packages and bin/), and --extra-root names further directories
  - `docs/reference/cli.md::Command line and hooks > The Stop hook::(unresolved)` - docs/reference/cli.md:264 says the hook always runs the installed checker ($HOME/.claude/skills/auditme/checks/changed.py); claude/hooks/auditme-stop.sh now runs the repository's own claude/skills/auditme/checks/changed.py instead when the root is a worktree sharing the git directory the installed checker links into
  - `docs/reference/cli.md::Command line and hooks > `claude/skills/auditme/checks/audit.py` > Declared roots::(unresolved)` - docs/reference/cli.md:157 gives the invalid-TOML message as `pyproject.toml: <parse error>`; core.declared_roots raises 'pyproject.toml: not valid TOML' and audit.py prints it via describe_error as `ERROR: pyproject.toml: not valid TOML (<parse error>)`
  - `docs/reference/cli.md::Command line and hooks > `claude/skills/auditme/checks/audit.py` > Declared roots::claude/skills/auditme/checks/audit.py::--package` - docs/reference/cli.md:157 shows the parse-error message as `pyproject.toml: <parse error>`; core.declared_roots raises RootsError('pyproject.toml: not valid TOML') chained to the tomllib error, so audit.py prints `ERROR: pyproject.toml: not valid TOML (<parse error>)`
  - `docs/reference/cli.md::Command line and hooks > `claude/skills/auditme/checks/changed.py`::(unresolved)` - docs/reference/cli.md:209 says all output goes to stdout; an argument error is printed by argparse's parser.error on stderr (changed.py main catches only the SystemExit), so not all output goes to stdout
  - `docs/reference/skills.md::Skills > /auditme {#auditme}::(unresolved)` - docs/reference/skills.md:40 gives the commit message as `auditme: add review-N`; claude/skills/auditme/SKILL.md step 10 uses `docs(audit): add review-N`
  - `docs/reference/skills.md::Skills > /auditme {#auditme}::claude/skills/auditme/requests.md` - docs/reference/skills.md:40 says /auditme commits as `auditme: add review-N`; claude/skills/auditme/SKILL.md step 10 commits as `docs(audit): add review-N`
  - `docs/reference/skills.md::Skills > /auditme-project-setup {#auditme-project-setup}::(unresolved)` - docs/reference/skills.md:59-60 says `new` asks before overwriting any existing file; claude/skills/auditme-project-setup/SKILL.md asks only for .pre-commit-config.yaml, .github/workflows/ci.yml, AGENTS.md, TODO.md and DONE.md, not for CLAUDE.md or claude/rules/README.md

Scope: every non-test .py file under `claude/skills/auditme/checks/` (21 files: audit.py, changed.py,
phaseb.py, the `auditme` package with its `phaseb/` and `rules/` subpackages).
Domain errors found: `RootsError` (auditme/core.py), `PhaseBError`
(auditme/phaseb/errors.py), `ChangedError` (changed.py).

### A2 (sampled): Except tuple coverage

- **Mode:** full (first audit)

Files inspected: 21. Every try/except was listed by AST and each one whose body
touches disk or json was read. No translating decorator or `with`
contextmanager envelope exists in scope. Not counted: `subprocess.run` bodies
(project_hygiene.py:32, :85, :195; changed.py:51, :131; docrefs.py:281), since
running a program is not one of the locked set's branches.

Every hit: body calls `path.read_text(encoding='utf-8')` (disk), handler
catches `SyntaxError, UnicodeDecodeError` (or `UnicodeDecodeError` alone);
`OSError` missing.

- claude/skills/auditme/checks/auditme/core.py:68 - `source_lines`: `except UnicodeDecodeError` around `read_text`; `OSError` missing
- claude/skills/auditme/checks/auditme/core.py:529 - `read_text` + `ast.parse`; `OSError` missing
- claude/skills/auditme/checks/auditme/core.py:634 - `read_text` + `ast.parse` (after an `is_file` check, still racy); `OSError` missing
- claude/skills/auditme/checks/auditme/core.py:707 - `read_text` + `ast.parse` (after an `is_file` check); `OSError` missing
- claude/skills/auditme/checks/auditme/rules/duplication.py:46 - `read_text` + `ast.parse`; `OSError` missing
- claude/skills/auditme/checks/auditme/rules/duplication.py:114 - same
- claude/skills/auditme/checks/auditme/rules/duplication.py:323 - same
- claude/skills/auditme/checks/auditme/rules/duplication.py:372 - same
- claude/skills/auditme/checks/auditme/rules/duplication.py:521 - same
- claude/skills/auditme/checks/auditme/rules/duplication.py:682 - same
- claude/skills/auditme/checks/auditme/rules/error_handling.py:281 - same
- claude/skills/auditme/checks/auditme/rules/error_handling.py:305 - same
- claude/skills/auditme/checks/auditme/rules/error_handling.py:445 - same (`src.read_text`)
- claude/skills/auditme/checks/auditme/rules/error_handling.py:665 - same
- claude/skills/auditme/checks/auditme/rules/error_handling.py:745 - same
- claude/skills/auditme/checks/auditme/rules/error_handling.py:783 - same
- claude/skills/auditme/checks/auditme/rules/error_handling.py:1148 - same
- claude/skills/auditme/checks/auditme/rules/error_handling.py:1169 - same
- claude/skills/auditme/checks/auditme/rules/error_handling.py:2103 - same
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:568 - same
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:631 - same
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:667 - same
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:730 - same
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:979 - same

### A3 (sampled): Domain-error layering

- **Mode:** full (first audit)

Files inspected: 21.

- claude/skills/auditme/checks/auditme/phaseb/batches.py:145 - `parse_result` raises `ValueError` in a package defining `PhaseBError` (carries an accept marker for `layer-has-domain-error-raises-stdlib`)
- claude/skills/auditme/checks/auditme/phaseb/batches.py:148 - same, `ValueError` (accepted by marker)
- claude/skills/auditme/checks/auditme/phaseb/batches.py:151 - same, `ValueError` (accepted by marker)
- claude/skills/auditme/checks/auditme/phaseb/batches.py:155 - same, `ValueError` (accepted by marker)
- claude/skills/auditme/checks/auditme/phaseb/batches.py:159 - same, `ValueError` (accepted by marker)
- claude/skills/auditme/checks/auditme/phaseb/batches.py:162 - same, `ValueError` (accepted by marker)

All other raises are `RootsError`, `PhaseBError`, `ChangedError` or `SystemExit(main())`.

### A5 (sampled): Two sources of truth

- **Mode:** full (first audit)

Files inspected: 21.

- claude/skills/auditme/checks/phaseb.py:144 - `run_merge` re-lists candidates with the merge's own `--depth`, while the plan was built with the plan run's `--depth`; `plan.json` does not record depth, so the two can disagree silently (depth changes a candidate's callees and so its hash, and the verdict takes the merge-time hash). The plan's question is checked against `--question` at line 146; depth has no such check.

Considered, not hits: `--batch-size` vs the registered size (phaseb.py, precedence stated in the help); `--base` vs `resolve_base` (changed.py, stated in the help); `--extra-root`/`--package` vs `[tool.auditme]` roots (audit.py, explicit `DECLARATION_IGNORED` and comments); `read_run_verdicts` taking the current candidate hash rather than the batch file's (batches.py, documented in its docstring).

### A6 (sampled): Stage method dual-path

- **Mode:** full (first audit)

Files inspected: 21. No pipeline-stage class in scope (the only classes with
methods are `CorpusIndex`, `TestIndex`, `SiteCounter`, `RunCheck`, `Verdict`,
`Site`; none returns a value and also assigns the same `self` field).

No hits.

### A7 (sampled): Constructor purity

- **Mode:** full (first audit)

Files inspected: 21. The only `__init__` is `SiteCounter.__init__`
(claude/skills/auditme/checks/auditme/phaseb/architecture.py:102), which creates an empty Counter: no I/O,
no argument mutation.

No hits.

### A8 (sampled): Late dataclass mutation

- **Mode:** full (first audit)

Files inspected: 21.

- claude/skills/auditme/checks/auditme/phaseb/docrefs.py:198 - `CorpusIndex.build` constructs `index = cls(...)` at line 185, then assigns `index.aliases = ...` after construction

Not counted: item assignment into a field's container (`info.members[...] = ...`, docrefs.py:232-239), which reassigns no field.

Mode: full tree. Scope: every non-test `.py` file under `claude/skills/auditme/checks/` (`audit.py`, `changed.py`, `phaseb.py`, and the `auditme` package with its `phaseb/` and `rules/` subpackages). Each question was applied to every file in scope.

### A9 (sampled): Pure-named function side effects

- **Mode:** full (first audit)

Files inspected: 21

Reading is counted where it happens in the function's body or in a same-package helper the body calls (marked "through"). No `load_` function exists in scope, so the `load_` exemption applies to none.

Outside the rule registry:

- claude/skills/auditme/checks/changed.py:70 - `resolve_base` runs `git rev-parse` through `run_git` (`subprocess.run`)
- claude/skills/auditme/checks/auditme/core.py:744 - `is_private` reads `pyproject.toml` and every `__init__.py` above the module through `privacy` -> `surface_files`/`all_names` (`is_file`, `read_text`)
- claude/skills/auditme/checks/auditme/phaseb/architecture.py:74 - `parse_audited_files` lists the roots and calls `path.read_text` on every file
- claude/skills/auditme/checks/auditme/phaseb/batches.py:166 - `check_batch` calls `path.is_file` and `path.read_text` on the batch output
- claude/skills/auditme/checks/auditme/phaseb/batches.py:201 - `check_run` reads the plan through `read_plan` (`path.read_text`) and every batch file through `check_batch`
- claude/skills/auditme/checks/auditme/phaseb/docrefs.py:302 - `resolve_path` reads the resolved file through `file_target` (`read_bytes`) to count its lines
- claude/skills/auditme/checks/auditme/phaseb/testmap.py:47 - `parse_file` calls `path.read_text`
- claude/skills/auditme/checks/auditme/phaseb/testmap.py:106 - `parse_test_tree` calls `tree_root.rglob` and reads each file through `parse_file`
- claude/skills/auditme/checks/auditme/phaseb/testmap.py:286 - `build_index` reads `pyproject.toml` and every source and test file through `source_sites` and `parse_test_tree`
- claude/skills/auditme/checks/auditme/phaseb/testmap.py:343 - `build_test_map` does the same reading through `build_index`
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:374 - `parse_package_layering` calls `agents.exists` and `agents.read_text` on `AGENTS.md`

The rule registry: every `check_*` rule function in `rules/` walks its root on disk, reads each source file and prints its hits. The `check_` prefix is the registry's naming convention for "run this check", so these share one cause and one fix (a rename of the convention or an acceptance of it), but each is a hit under the predicate as written:

- claude/skills/auditme/checks/auditme/rules/duplication.py:34 - `check_literal_duplication` calls `path.read_text` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/duplication.py:110 - `check_paired_sibling_helpers` calls `path.read_text` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/duplication.py:148 - `check_duplicate_side_effect_per_target` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/duplication.py:251 - `check_redundant_sink_caller_plus_callee` calls `path.read_text` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/duplication.py:502 - `check_duplicate_call_sequence` calls `path.read_text` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/duplication.py:663 - `check_recompile_duplication` calls `path.read_text` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:34 - `check_silent_broad_except` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:90 - `check_except_interpolation` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:171 - `check_broad_except_wrong_level` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:209 - `check_mixed_raise_types` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:262 - `check_asymmetric_exception_translation` calls `path.read_text` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:380 - `check_sibling_error_no_common_base` calls `src.read_text` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:478 - `check_cli_entry_missing_error_envelope` calls `cli_dir.is_dir`, `cli_dir.rglob` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:559 - `check_try_wrapping_with_too_broad` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:637 - `check_layer_has_domain_error_but_raises_stdlib` calls `path.read_text` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:724 - `check_inconsistent_error_translation` calls `path.read_text` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:968 - `check_filesystem_envelope_gap` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:1090 - `check_filesystem_op_without_envelope` calls `path.read_text` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:1245 - `check_logger_exception_graceful_degradation` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:1386 - `check_docstring_raises_mismatch` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:1507 - `check_missing_raises_section` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:1598 - `check_bare_except_in_module_with_narrow_errors` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:1735 - `check_failure_as_absence` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:1964 - `check_get_container_default_then_method_call` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:2178 - `check_translator_envelope_gap` reaches the filesystem through `translator_envelopes` (`path.read_text`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/error_handling.py:2490 - `check_raises_section_drift` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:14 - `check_def_class_in_init` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:129 - `check_in_function_imports` reaches the filesystem through `auditme.core.accepted_lazy_imports` (`agents.exists`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:196 - `check_unused_submodule_imports` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:263 - `check_as_import` reaches the filesystem through `project_bans_as_imports` (`agents.exists`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:322 - `check_from_import` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:424 - `check_layering_violations` reaches the filesystem through `parse_package_layering` (`agents.exists`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:492 - `check_passthrough_shim` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:550 - `check_empty_init_with_exporting_siblings` calls `path.read_text` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:615 - `check_migration_shim_consumers` calls `path.read_text` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:720 - `check_reexport_in_non_init` calls `path.read_text` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:787 - `check_annotated_all_assignment` reaches the filesystem through `project_has_all_guard` (`src.is_dir`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/project_hygiene.py:26 - `check_ruff` calls `subprocess.run` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/project_hygiene.py:80 - `check_lockfile` calls `pyproject.exists`, `uvlock.exists`, `subprocess.run`, `os.environ` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/project_hygiene.py:162 - `check_ruff_version` calls `config.exists`, `emit`, `subprocess.run` directly; its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/project_hygiene.py:214 - `check_phase_section_doc_reference` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/project_hygiene.py:354 - `check_spec_api_signature_drift` reaches the filesystem through `auditme.core.corpus_definitions` (`src.is_dir`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:43 - `check_constructor_disk_io` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:83 - `check_silent_self_mutation` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:170 - `check_return_value_shadows_instance_attr` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:266 - `check_parameter_mutation` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:343 - `check_pure_name_has_side_effect` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:407 - `check_mutable_store_without_copy` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:520 - `check_assert_never_missing` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:599 - `check_build_name_has_side_effect` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:715 - `check_mutable_module_level_exported` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:812 - `check_mutable_members_in_immutable_wrapper` reaches the filesystem through `dataclass_frozen_by_name` (`path.read_text`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:1016 - `check_callback_hotpath_io` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:1086 - `check_dataclass_optional_always_set` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:1212 - `check_dead_local_init` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:1297 - `check_subprocess_without_memoisation` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/style_and_naming.py:83 - `check_text_patterns` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/style_and_naming.py:171 - `check_percent_formatting` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/style_and_naming.py:234 - `check_nonalphabetical_literals` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/style_and_naming.py:293 - `check_non_alphabetical_dict_keys` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/style_and_naming.py:336 - `check_bare_parametric_annotation` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/style_and_naming.py:407 - `check_duplicated_word` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/style_and_naming.py:450 - `check_bare_nonbuiltin_generic_annotation` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/style_and_naming.py:560 - `check_underscore_unpack_target_read` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/style_and_naming.py:616 - `check_underscore_forloop_target_read` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/style_and_naming.py:692 - `check_leading_underscore_nested_def_class` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/style_and_naming.py:806 - `check_leading_underscore_binding` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`
- claude/skills/auditme/checks/auditme/rules/style_and_naming.py:892 - `check_typing_deprecated_alias` reaches the filesystem through `auditme.core.all_py_files` (`root.glob`); its hits are printed to stdout through `auditme.core.emit`

### A10 (sampled): Predicate semantics

- **Mode:** full (first audit)

Files inspected: 21

Every `is_` / `has_` / `should_` function in scope was read (no `has_` or `should_` function exists). Each answers the question its name and docstring state. The narrower readings (`is_constant_operand` accepting only string constants and dotted attributes, `is_leading_underscore` excluding `_`, dunders and mangled names, `is_builtin_call` excluding shadowed builtins) are stated in their docstrings, not hidden conjuncts.

No hits

### A12 (sampled): assert misuse

- **Mode:** full (first audit)

Files inspected: 21

No `assert` statement in any non-test file in scope (checked by parsing every file for `ast.Assert`).

No hits

### A13 (sampled): Same value to multiple structural slots

- **Mode:** full (first audit)

Files inspected: 21

Every call passing one expression to two or more arguments was enumerated by parsing; the constructor calls among them were judged.

- claude/skills/auditme/checks/auditme/phaseb/architecture.py:820 - `candidates.Candidate(question='A17', id=file.rel, path=file.rel, ...)` passes `file.rel` to both `id` and `path`; `Candidate.id` is documented only as `'<repo-relative path>::<qualname>'` (`claude/skills/auditme/checks/auditme/phaseb/candidates.py:27`), so the file-level id form has neither a factory nor a docstring

Considered and not flagged: `DocTarget('file', rel, rel, ...)` at `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:299` (inside the `file_target` factory) and `DocTarget('directory', rel, rel, 1, 1)` at `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:314`; the `DocTarget.id` field comment documents `'path' for a file or directory`.

### A14 (sampled): Repeated computation per request

- **Mode:** full (first audit)

Files inspected: 21

No helper in scope is memoised (no `functools.cache`/`lru_cache` in non-test code).

- claude/skills/auditme/checks/auditme/core.py:127 - `all_py_files(src_root)` re-globs the same root once per registered check in one `audit.py` sweep (`claude/skills/auditme/checks/audit.py:209` runs every `auditme.registry.CHECKS` entry per root, and each entry calls it)
- claude/skills/auditme/checks/auditme/core.py:67 - `source_lines(path)` re-reads every source file once per registered check in one `audit.py` sweep
- claude/skills/auditme/checks/auditme/core.py:310 - `audit_roots(scope)` (reads `pyproject.toml` through `declared_roots`) runs many times in one Phase B lister call: in `list_a1_candidates` once through `parse_audited_files` (`claude/skills/auditme/checks/auditme/phaseb/architecture.py:614`), once per check in `capture_hits` (`claude/skills/auditme/checks/auditme/phaseb/architecture.py:50`), again at `claude/skills/auditme/checks/auditme/phaseb/architecture.py:618`, and once per private-helper call site through `privacy` -> `surface_files` (`claude/skills/auditme/checks/auditme/core.py:664`); the T1 lister repeats it per site at `claude/skills/auditme/checks/auditme/phaseb/candidates.py:791`
- claude/skills/auditme/checks/auditme/core.py:630 - `all_names(path)` re-reads and re-parses the same `__init__.py` files for every `privacy` call (one per candidate site in the A1 and T1 listers)
- claude/skills/auditme/checks/auditme/core.py:440 - `corpus_py_files` (re-reads `pyproject.toml` and re-globs the corpus) runs four times per root in one sweep: twice through `reads_by_module_and_name` (`claude/skills/auditme/checks/auditme/rules/state_and_effects.py:779`, `:865`), once directly (`claude/skills/auditme/checks/auditme/rules/state_and_effects.py:978`) and once through `corpus_definitions` (`check_spec_api_signature_drift`)

### A15 (sampled): Duplicate constructor / serialisation logic

- **Mode:** full (first audit)

Files inspected: 21

- claude/skills/auditme/checks/auditme/phaseb/testmap.py:96 - the `Site` assembly for top-level functions and class methods (lines 96 and 99) copies `claude/skills/auditme/checks/auditme/phaseb/candidates.py:253` and `:256` field for field, including the qualname format; a field added to `Site` must be added in both modules
- claude/skills/auditme/checks/auditme/phaseb/candidates.py:304 - `Candidate(id=site.id, path=site.path, start=site.start, end=site.end, ...)` is repeated for each site-based question (`claude/skills/auditme/checks/auditme/phaseb/candidates.py:304`, `:793`, `:1055`) with no `Site` -> `Candidate` helper
- claude/skills/auditme/checks/auditme/phaseb/candidates.py:548 - `Candidate(path=section.doc, start=section.start, end=section.end, ...)` is repeated for each section-based question (`claude/skills/auditme/checks/auditme/phaseb/candidates.py:435`, `:452`, `:548`, `:678`), with the `f'{section.doc}::{section.heading_path}'` id built twice (`:550`, `:680`)
- claude/skills/auditme/checks/auditme/phaseb/docrefs.py:205 - `DocTarget(kind, f'{rel}::<qualname>', rel, start, end)` is assembled by hand at `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:205`, `:207`, `:214`, `:231` and `:257`, each rebuilding the `rel::qualname` id format

### A16 (sampled): CLI entry envelope

- **Mode:** full (first audit)

Files inspected: 21

The predicate covers top-level `run_*` functions in `cli/*.py`. No `cli/` directory exists in scope (the `run_*` functions in `claude/skills/auditme/checks/phaseb.py` and `claude/skills/auditme/checks/audit.py` are not in a `cli/` module).

No hits

### A18 (sampled): Hot-path setup

- **Mode:** full (first audit)

Files inspected: 21

No callback method (`on_step`, `on_log`, `on_evaluate`, `on_batch_*`, or any `on_*` method) exists in non-test code in scope.

No hits

Scope: every non-test `.py` file under `claude/skills/auditme/checks/` (the
`auditme` package, `auditme/rules/`, `auditme/phaseb/`, and `audit.py`,
`changed.py`, `phaseb.py`). Reads by name for A20/A25 were grepped in all three
forms (`from <module> import <name>`, `<module>.<name>`,
`sys.modules['<module>'].<name>`) across `claude/skills/auditme/checks/`,
`claude/skills/auditme/tests/`, `claude/skills/auditme-project-setup/tests/` and
`tests/`.

### A20 (sampled): Mutable module-level singleton

- **Mode:** full (first audit)

Files inspected: 21

- claude/skills/auditme/checks/auditme/core.py:28 - `EMITTED: set[str] = set()` (bare builtin `set` constructor) is read by name from auditme/phaseb/architecture.py:42-59 (`auditme.core.EMITTED` copied, cleared, updated) and from tests (conftest.py:51, test_project_hygiene.py:396, phaseb/test_architecture_candidates.py:54-59); not a `frozenset`. Carries an existing `accept[mutable-module-level-exported]` marker (process-lifetime state the driver fills and the tests clear).
- claude/skills/auditme/checks/auditme/phaseb/candidates.py:59 - `REGISTRY: dict[...] = {}` (dict literal) is read by name from tests (phaseb/test_model.py:33-151, test_batches.py:196, test_briefs.py:13-114, test_cli.py:203-257, including `monkeypatch.setitem`); not a `MappingProxyType`. Carries an existing `accept[mutable-module-level-exported]` marker on line 58 (filled by `@register_question` at import, patched by a test).
- claude/skills/auditme/checks/auditme/phaseb/candidates.py:61 - `KINDS: dict[...] = {}` (dict literal) is read by name from tests (phaseb/test_model.py:34-128, cleared and updated); not a `MappingProxyType`. Carries an existing `accept[mutable-module-level-exported]` marker on line 60.

Judged and not hits (mutable, but no read by name from another module in any of the three forms): `__all__` lists in auditme/phaseb/__init__.py:25, auditme/phaseb/batches.py:259, auditme/phaseb/ledger.py:156 (the only `module.__all__` text in the test tree is a fixture string in test_annotated_all.py); `STDLIB` (rules/imports_and_surfaces.py:40); `DISK_IO_NAMES`, `MUTABLE_VALUE_SHAPES`, `MUTABLE_CONSTRUCTORS` (rules/state_and_effects.py:12, 681, 694); `STRFTIME_TOKENS`, `PARAMETRIC_NONBUILTIN_GENERICS`, `TYPING_DEPRECATED_ALIASES` (rules/style_and_naming.py:168, 434, 855); `RULE_HELP` (changed.py:38); `COMMANDS` (phaseb.py:175). `ROOT_MODULES` (core.py:187, rebound at 323/325) is always a `types.MappingProxyType`; `EXTRA_ROOT_NAMES` (core.py:179, rebound by audit.py:146 and tests/conftest.py:66) is always a tuple.

### A21 (sampled): Lazy init race

- **Mode:** full (first audit)

Files inspected: 21

No hits. No `if X is None: X = ...` initialisation of a module-level name exists at module scope or in a module-level helper; the only `global` statement (auditme/core.py:320, `ROOT_MODULES` in `audit_roots`) rebinds unconditionally, not lazily.

### A22 (sampled): Fall-through after partial handling

- **Mode:** full (first audit)

Files inspected: 21

No hits. Every `try` whose handler raises (translation to `PhaseBError`, `RootsError` or `ChangedError`) either returns from its branch or leaves the function on the raise; no `if/elif` branch holding a translating `try` falls through into a second branch or later code that redoes the work (AST scan of every `if` chain and every `try`, plus reading each raising `try`).

### A23 (sampled): Discarded multi-return

- **Mode:** full (first audit)

Files inspected: 21

No hits. Every call to a tuple- or dataclass-returning function either unpacks all components or names the dropped ones `_` (e.g. batches.py:215/240, candidates.py:152, project_hygiene.py:27). Judged and not hits: core.py:746 `privacy(...)[0]` (drops the label of the rule that decided, which does not change how the bool is used); candidates.py:121/140 `registered(question)[1]`/`[2]` and candidates.py:130 bare `registered(question)` (table accessors and a raise-on-unknown check; the other members are sibling registry entries, not state the read depends on); batches.py:232 `check_run(run_dir).problems` (`retry` is derived from `problems`); testmap.py:355 `build_index(root).refs(depth)` (a method call on the index, nothing documented dropped).

### A24 (sampled): Identity of subprocess / shell-out calls

- **Mode:** full (first audit)

Files inspected: 21

No hits. Each shell-out runs once per request or with differing arguments: changed.py `run_git`/`git_lines` (rev-parse per base candidate, two different diffs, one show-toplevel), changed.py:132 `sweep` (once); auditme/phaseb/docrefs.py:283 `tracked_files` (once per lister: through `CorpusIndex.build` in `doc_candidates` (Doc4, Doc5) and the Doc1 lister, or directly in the Doc2 lister at candidates.py:652; no lister reaches it twice); rules/project_hygiene.py:34 (arguments differ per root, accepted), :87/:95 (second run only under a different environment), :198 (a PROJECT_CHECKS entry, once per sweep).

### A25 (sampled): Shallow immutable wrapper

- **Mode:** full (first audit)

Files inspected: 21

No hits. Every module-level `frozenset(...)`, `tuple`, `tuple(...)` and `types.MappingProxyType(...)` holds only string constants, nested tuples of strings (candidates.py:946 `T2_INVERSES`), a starred tuple of strings (architecture.py:424), function or class references (`*_CHECKS`, `CHECKS`, `PROJECT_CHECKS`, `LEAVING_STATEMENTS`, `T2_BRANCHES`, `MEMBER_CONTAINERS`), or is empty; no `dict`/`list`/`set` member, none one tuple deep, and no instance of a non-frozen project dataclass. `ROOT_MODULES` at core.py:323 wraps a comprehension whose member type the assignment does not state, which is outside this question.

### S1 (sampled): Type annotations on every signature

- **Mode:** full (first audit)

Files inspected: 55 (21 non-test source, 34 test). Found with `ruff check --select ANN` and confirmed by reading each line.

Non-test source (14 missing annotations):

- claude/skills/auditme/checks/auditme/core.py:41 - `emit(related, **kwargs)`: `**kwargs` has no annotation
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:465 - `maybe_emit_layering`: no return annotation
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:465 - `maybe_emit_layering`: parameter `rel` unannotated
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:465 - `maybe_emit_layering`: parameter `lines` unannotated
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:465 - `maybe_emit_layering`: parameter `lineno` unannotated
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:465 - `maybe_emit_layering`: parameter `importer_pkg` unannotated
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:465 - `maybe_emit_layering`: parameter `module_name` unannotated
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:465 - `maybe_emit_layering`: parameter `rank` unannotated
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:465 - `maybe_emit_layering`: parameter `accepted` unannotated
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:465 - `maybe_emit_layering`: parameter `package_root_name` unannotated
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:377 - nested `walk_non_nested`: no return annotation
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:377 - nested `walk_non_nested`: parameter `n` unannotated
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:651 - nested `walk_non_nested` (second copy): no return annotation
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:651 - nested `walk_non_nested` (second copy): parameter `n` unannotated

Test files (count only): 99 missing parameter annotations (96 ANN001 + 3 `**overrides` ANN003), 28 missing return annotations; 7 modules affected (claude/skills/auditme/tests/phaseb/test_batches.py, test_docrefs.py, test_ledger.py, test_model.py; claude/skills/auditme/tests/test_changed.py, test_registry.py; tests/test_install_claude.py), 27 of 34 test modules fully annotated. AGENTS.md records no standing test-annotation exemption, so there is no figure to drift-check.

### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake

- **Mode:** full (first audit)

Files inspected: 55. AST scan of every function, method, parameter, class, assigned name and attribute store, then each oddity read by hand. Module-level PascalCase names (`Check`, `FunctionNode`, `Lister`, `HandlerLevel`, `Project`, `Builder`, `Runner`, `StubRuff`) are all type aliases, which follow the class convention; `pytestmark` is pytest's required name. No leading-underscore names.

No hits.

### S3 (sampled): TYPE_CHECKING block placement

- **Mode:** full (first audit)

Files inspected: 55. No file in scope has a real `if typing.TYPE_CHECKING:` block; every occurrence is inside a docstring or a fixture string (core.py:109, imports_and_surfaces.py:332, candidates.py:771, and test fixtures). With no blocks there is no placement to be inconsistent.

No hits.

### S4 (sampled): Project-specific rule files

- **Mode:** full (first audit)

Files inspected: 55 .py files plus bin/check-foreign-names.sh, bin/install-claude.sh, claude/hooks/auditme-stop.sh. Rule files read: AGENTS.md, claude/rules/auditme/coding-standards.md, claude/rules/auditme/imports.md. Rules the checker already enforces (from-import, as-import, future-annotations, legacy typing, %/.format formatting, leading underscores, stdlib-logging, def/class in `__init__.py`, alphabetical literals, wildcard imports) and the no-project-names hook were not re-reviewed; stdlib-only (no loguru, no cappa) is allowed for the checker and not flagged. Both rule files apply to `**/*.py` only, and AGENTS.md sets no rule for shell scripts beyond the hook-enforced no-project-names, so the shell scripts have no hits.

Unenforced rule found broken: coding-standards.md "Type annotations" - "If an import is needed only for type annotation, import inside of a TYPE_CHECKING block". No checker rule covers it and ruff's `TC` rules are not selected in pyproject.toml. Each import below is a module-level import whose every use is in an annotation (found by AST scan, spot-checked by grep; `typing` itself is excluded, since the guard needs it):

- claude/skills/auditme/checks/audit.py:85 - `collections.abc` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/checks/auditme/core.py:5 - `collections.abc` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/checks/auditme/phaseb/batches.py:14 - `pathlib` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/checks/auditme/phaseb/testmap.py:10 - `collections.abc` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/checks/auditme/rules/duplication.py:5 - `pathlib` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/checks/auditme/rules/error_handling.py:5 - `collections.abc` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/checks/auditme/rules/error_handling.py:7 - `pathlib` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:5 - `collections.abc` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/checks/auditme/rules/imports_and_surfaces.py:6 - `pathlib` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:4 - `collections.abc` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:7 - `pathlib` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/checks/auditme/rules/style_and_naming.py:5 - `pathlib` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/checks/changed.py:19 - `collections.abc` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/tests/conftest.py:10 - `collections.abc` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/tests/phaseb/test_doc_candidates.py:3 - `pathlib` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/tests/phaseb/test_docrefs.py:3 - `pathlib` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/tests/phaseb/test_ledger.py:6 - `pathlib` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/tests/phaseb/test_model.py:3 - `collections.abc` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/tests/phaseb/test_model.py:5 - `pathlib` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/tests/test_changed.py:7 - `collections.abc` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/tests/test_changed.py:9 - `pathlib` used only in annotations, not under TYPE_CHECKING
- claude/skills/auditme/tests/test_core.py:15 - `pytest` used only in annotations (`pytest.CaptureFixture`, `pytest.MonkeyPatch`), not under TYPE_CHECKING
- claude/skills/auditme/tests/test_imports_and_surfaces.py:9 - `pytest` used only in annotations (other `pytest.` text is inside fixture strings), not under TYPE_CHECKING

Scope for P1-P3 and Sec2-Sec5: the 21 non-test `.py` files under
`claude/skills/auditme/checks/` (driver scripts `audit.py`, `changed.py`,
`phaseb.py` and the `auditme` package) and the shell scripts
`bin/check-foreign-names.sh`, `bin/install-claude.sh`,
`claude/hooks/auditme-stop.sh`. Sec1 also covers every tracked file
(`git ls-files`).

### P1 (sampled): O(n^2) on real-size inputs

- **Mode:** full (first audit)

Files inspected: 24

- claude/skills/auditme/checks/auditme/rules/duplication.py:611 - `check_duplicate_call_sequence` runs a full O(len_a x len_b) LCS (allocating a fresh `(n+1)x(m+1)` back-pointer table, line 570) for every cross-file pair of functions with 5+ calls: O(F^2) pairs per root; the cheap 0.7 length-ratio tests at lines 639-642 run only after the LCS, though a length ratio below 0.7 already rules a pair out.
- claude/skills/auditme/checks/auditme/rules/error_handling.py:349 - `check_asymmetric_exception_translation`: for every `ast.Call` in every file whose callee text is not an exact key, scans every entry of `function_index` with `endswith` - O(calls x functions) per root; a short-name index (as `check_inconsistent_error_translation` builds with `short_to_full`, line 773) would make it a lookup.
- claude/skills/auditme/checks/auditme/phaseb/testmap.py:243 - `TestIndex.caller_sites` rebuilds the reverse call graph from every edge of `self.direct` on every call; it is called for every candidate site (via `test_files`, candidates.py:789/1051, and `callers`, candidates.py:802), so the T1/T2 listers cost O(sites x edges).
- claude/skills/auditme/checks/auditme/phaseb/testmap.py:266 - `test_files` scans every test file's imports against every module of the site and its callers, and line 264 scans every alias, once per candidate site: O(sites x test files x modules).

### P2 (sampled): Blocking I/O in hot paths

- **Mode:** full (first audit)

Files inspected: 24

- claude/hooks/auditme-stop.sh:45 - the Claude Code Stop hook (a callback run at the end of every turn) blocks the turn on `changed.py`, which, whenever any reportable file differs from the base, runs the whole-tree sweep synchronously (changed.py:132, timeout 600 s), including `uv lock --check` (rules/project_hygiene.py:87, run again at :95), which may resolve against the package index over the network.

### P3 (sampled): Repeated expensive computation per request

- **Mode:** full (first audit)

Files inspected: 24

- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:779 - `check_mutable_module_level_exported` calls `reads_by_module_and_name`, which reads and parses the whole corpus (core.py:528); `corpus_py_files` does not depend on `src_root`, yet the check runs once per root, so the identical index is rebuilt on every root pass.
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:865 - `check_mutable_members_in_immutable_wrapper` rebuilds the same corpus-wide `reads_by_module_and_name` index again, per root (two full corpus parses per root for one value).
- claude/skills/auditme/checks/auditme/rules/state_and_effects.py:841 - `dataclass_frozen_by_name` (defined line 970) re-parses the whole corpus on every root pass; the result does not depend on the root.
- claude/skills/auditme/checks/auditme/rules/project_hygiene.py:398 - `check_spec_api_signature_drift` is in the per-root `CHECKS` (registry.py:72) but builds the corpus-wide `corpus_definitions` and re-reads every spec file (line 402) on every root pass; `emit`'s de-duplication (core.py:50) hides the identical repeat hits.
- claude/skills/auditme/checks/audit.py:208 - no parse cache is shared between checks: each check in `CHECKS` reads and `ast.parse`s every file of the root itself (77 `ast.parse(` sites under `rules/` and `core.py`), so every file is parsed once per check per root.
- claude/skills/auditme/checks/auditme/phaseb/candidates.py:802 - the T1 lister calls `index.callers(site.id, depth)` after `index.test_files(site.id, depth)` (line 789) has already computed `caller_sites` for the same site and depth; the reverse graph and BFS are derived twice per site.
- claude/skills/auditme/checks/auditme/phaseb/candidates.py:790 - `read_test_files` reads each test file from disk again for every candidate site that maps to it (also line 1052 for T2), rather than once per run.

### Sec1 (sampled): Secrets in source

- **Mode:** full (first audit)

Files inspected: 135 (every tracked file)

No hits. Searched for known token formats (AWS, GitHub, OpenAI-style, Slack, Google, Hugging Face, JWT, private-key blocks), for key/secret/password/token names assigned a literal of 16+ characters, and for tracked credential files (`.env`, `.pem`, `.key`, SSH keys, `.netrc`, `.pypirc`). The only token references are `${{ secrets.GITHUB_TOKEN }}` interpolations in `.github/workflows/docs.yml`, which hold no value.

### Sec2 (sampled): Input validation at system boundaries

- **Mode:** full (first audit)

Files inspected: 24

- claude/skills/auditme/checks/phaseb.py:170 - `dismiss` builds the ledger path from `--question` without checking that it is a registered question; every other subcommand validates it first through `list_candidates`/`question_brief` (`registered`, candidates.py:103), so `dismiss --question ../../x` reads and rewrites `<root>/agents/x.jsonl` if it parses as a ledger.
- claude/skills/auditme/checks/audit.py:182 - `--package` is not checked to be a single package name (`../..` or an absolute path is accepted), and line 192 checks only `exists()`, so a regular file passes and every check then runs against it.
- claude/skills/auditme/checks/auditme/core.py:247 - a `[tool.auditme]` root `path` read from the project's `pyproject.toml` is checked for being a directory with `.py` files, but not for being relative or inside the project (see Sec4).

### Sec3 (sampled): Command injection

- **Mode:** full (first audit)

Files inspected: 24

No hits. Every `subprocess.run` passes an argument list without `shell=True` (changed.py:52, :132; phaseb/docrefs.py:283; rules/project_hygiene.py:34, :87, :95, :198); the one user-supplied value reaching git, `changed.py --base`, is refused when it starts with `-` (`option_value_is_flag`, changed.py:188, checked at :210) before it reaches `git diff`; the shell scripts quote every expansion and pass file arguments after `--` (bin/check-foreign-names.sh:39). Note, not a hit: rules/project_hygiene.py:20-22 runs the audited project's own `.venv/bin/ruff` when present, so the Stop hook and pre-commit hooks execute a binary from the project's tree; that is the project's own tool by design, not unsanitised input.

### Sec4 (sampled): Path traversal

- **Mode:** full (first audit)

Files inspected: 24

- claude/skills/auditme/checks/auditme/core.py:247 - `root = scope / path` joins a project-supplied `[tool.auditme]` root with no containment check: `path = "../other"` or an absolute path makes the sweep (including the Stop hook's) read and report files outside the project, and the overlap error at core.py:257 then raises an uncaught `ValueError` from `relative_to(scope)` instead of a `RootsError`.
- claude/skills/auditme/checks/audit.py:149 - each `--extra-root` value is joined as `scope / name` without containment; an absolute path or `..` audits a directory outside the scope.
- claude/skills/auditme/checks/audit.py:182 - `scope / 'src' / args.package` with an unchecked `--package` value (`..`, absolute path) escapes `src/`.
- claude/skills/auditme/checks/phaseb.py:33 - `ledger_path` joins the unvalidated `--question` of `dismiss` (phaseb.py:170) into `<root>/agents/audit-reviews/ledger/<question>.jsonl`, so `../` in the value reads and rewrites a file outside the ledger directory.

### Sec5 (sampled): PII in logs

- **Mode:** full (first audit)

Files inspected: 24

No hits. The checker uses no logging framework; its `print` output is hit records, file paths and error messages, and the shell scripts print hit lines, paths and the checker's report. None of it logs raw user text.

### T3 (sampled): Integration vs unit balance

- **Mode:** full (first audit)

Inspected: each named orchestrator against its tests.

- `claude/skills/auditme/checks/audit.py` - `claude/skills/auditme/tests/test_driver.py:448` runs the shipped `audit.py` as a subprocess over a fixture project and checks the JSON records (end-to-end present).
- `claude/skills/auditme/checks/changed.py` - `claude/skills/auditme/tests/test_changed.py:211` `test_end_to_end_against_the_real_checker` runs the runner against the real `audit.py` in a git fixture (present).
- `claude/skills/auditme/checks/phaseb.py` - `claude/skills/auditme/tests/phaseb/test_cli.py:47` runs `phaseb.py` as a subprocess; `test_every_registered_question_round_trips_plan_check_and_merge` (line 258) drives plan, check and merge (present).
- `claude/hooks/auditme-stop.sh` - `tests/test_stop_hook.py` runs the real hook script, but every case writes a stub `changed.py` (`write_checker`, `make_home`) that prints a canned report; no case runs the hook through the real `changed.py` and `audit.py`.
- `bin/install-claude.sh` - `tests/test_install_claude.py` replaces `uvx` with a stub that records its arguments (`run_with_stub_uvx`); no case installs into a temporary HOME and checks the links and the `settings.json` Stop-hook entry. (The real run fetches the pinned `install-in-claude` over git+ssh, which is likely why.)

Hits:

- tests/test_stop_hook.py:21 - the Stop hook (`claude/hooks/auditme-stop.sh`) has no end-to-end test: every case stubs `changed.py`, so hook -> runner -> checker is never run together
- tests/test_install_claude.py:18 - the installer (`bin/install-claude.sh`) has no end-to-end test: `uvx` is always stubbed, so no test shows the skills, rules and Stop hook actually land in `~/.claude` and `settings.json`

### D1 (sampled): Declared in pyproject

- **Mode:** full (first audit)

Inspected: top-level imports of every tracked `.py` file (`git ls-files '*.py'`), parsed with `ast`, minus `sys.stdlib_module_names` and the project's own modules (`auditme`, `audit`, `changed`, `phaseb`, `conftest`). The only third-party import is `pytest`. `pyproject.toml` declares no runtime dependencies and the groups `dev = ["ruff==0.17.4"]` and `docs = ["mkdocs", "mkdocs-material"]`; pytest is in none of them. The tests are run with `uv run --no-project --with pytest` (README.md:18, AGENTS.md, `.github/workflows/ci.yml`), so pytest is supplied ad hoc and unpinned rather than declared.

Hits:

- pyproject.toml:84 - `pytest` is imported by every test module (first at claude/skills/auditme/tests/conftest.py:19; also tests/test_stop_hook.py:9) but declared in no dependency group; it comes only from `uv run --with pytest`, unpinned and absent from `uv.lock`

### D2 (sampled): Unused declarations

- **Mode:** full (first audit)

Inspected: every declared dependency in `pyproject.toml` (`[dependency-groups]`), against `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `.github/workflows/docs.yml`, `mkdocs.yml` and the installed metadata of mkdocs-material.

- `ruff` (dev) - run as a command: `.pre-commit-config.yaml` uses `astral-sh/ruff-pre-commit` (hooks `ruff-check`, `ruff-format`), and the checker runs `ruff` from PATH (`project_hygiene.py`, per the pyproject per-file-ignores and `ci.yml`'s PATH step). Used.
- `mkdocs` (docs) - run as a command in CI `run:` steps: `uv run mkdocs build --strict` and `uv run mkdocs gh-deploy ...` in `.github/workflows/docs.yml`. Used.
- `mkdocs-material` (docs) - a plugin of the declared host `mkdocs`: its `entry_points.txt` (mkdocs_material-9.7.7.dist-info, read from the uv cache) registers `material = material.templates` in `mkdocs.themes`, and `mkdocs.yml` has `theme: name: material`. Used.

No hits.

### D3 (sampled): Lockfile coherence

- **Mode:** full (first audit)

Inspected: the sweep's lockfile-drift result, as reported by the caller (no unaccepted hit).

No hits.

### Doc3 (sampled): README.md and AGENTS.md consistent

- **Mode:** full (first audit)

Inspected: README.md (whole file) against AGENTS.md (whole file), with `.pre-commit-hooks.yaml` and `claude/hooks/auditme-stop.sh:2` to settle which side is right.

Consistent: the install script and what it links into `~/.claude`, the agents repository as the source of the other shared rules and skills, and the test command (identical in both).

Hits:

- AGENTS.md:5 - says the Stop hook runs the checker "at the end of a session", while README.md:4-5 says "before a turn ends"; the hook's own header (claude/hooks/auditme-stop.sh:2, "block the end of a turn") agrees with README, so AGENTS.md is the inaccurate one
- README.md:3 - the opening list of what the repository provides names only the `auditme-changed` and `auditme-all` pre-commit hooks, while AGENTS.md ("No project names") says the `no-project-names` hook is published here too, and `.pre-commit-hooks.yaml:15` does publish it

## Spec review

Criteria from /Users/simonb/.claude/skills/specdev/SKILL.md. Size guideline: ~200 lines or more than 8 top-level sections. Every spec's Module location section says "The checker is not under `src/`" (or lists `claude/...` paths only); the repository has no `src/` package, so this fails the skill's literal criterion and is recorded once per spec.

### agents/specs/index.md

No gaps (format matches the skill's index table; every spec directory has an entry and every link resolves).

### agents/specs/auditme-false-positives/spec.md

- agents/specs/auditme-false-positives/spec.md:whole file - Spec size - 218 lines, over the ~200-line guideline
- agents/specs/auditme-false-positives/spec.md:50 - Module location references a path under `src/` - lists `claude/skills/auditme/...` paths only, states it is not under `src/`

### agents/specs/listed-phase-b-architecture-questions/spec.md

- agents/specs/listed-phase-b-architecture-questions/spec.md:whole file - Spec size - 284 lines and 9 top-level sections, over both guidelines
- agents/specs/listed-phase-b-architecture-questions/spec.md:48 - Module location references a path under `src/` - lists `claude/skills/auditme/...` paths only, states it is not under `src/`
- agents/specs/listed-phase-b-architecture-questions/spec.md:257 - Settings includes name, type and default for each entry - `--question`, `--batch-size`, `--depth` given in prose with no types (and `--question`/`--depth` with no defaults); no table or list

### agents/specs/listed-phase-b-documentation-questions/spec.md

- agents/specs/listed-phase-b-documentation-questions/spec.md:whole file - Spec size - 278 lines, over the ~200-line guideline
- agents/specs/listed-phase-b-documentation-questions/spec.md:25 - Module location references a path under `src/` - lists `claude/skills/auditme/...` paths only, states it is not under `src/`
- agents/specs/listed-phase-b-documentation-questions/spec.md:253 - Settings includes name, type and default for each entry - `--batch-size`, `--depth` and the Doc1 depth constant named in prose without types or (for the options) defaults; section also carries dependency and test-command text that belongs elsewhere

### agents/specs/listed-phase-b-test-questions/spec.md

- agents/specs/listed-phase-b-test-questions/spec.md:whole file - Spec size - 306 lines and 9 top-level sections, over both guidelines
- agents/specs/listed-phase-b-test-questions/spec.md:45 - Module location references a path under `src/` - lists `claude/skills/auditme/...` paths only, states it is not under `src/`
- agents/specs/listed-phase-b-test-questions/spec.md:60 - Cross-references use relative markdown links - names "the architecture-questions spec" (also line 298) with no link to ../listed-phase-b-architecture-questions/spec.md anywhere in the file

### agents/specs/project-setup/spec.md

- agents/specs/project-setup/spec.md:whole file - Spec size - 750 lines and 10 top-level sections, far over both guidelines
- agents/specs/project-setup/spec.md:130 - Module location references a path under `src/` - lists `claude/...`, `bin/`, `docs/` and repository-root paths only
- agents/specs/project-setup/spec.md:whole file - Every template section present (Settings omitted only if not applicable) - no Settings section, though the spec defines configurable behaviour (`--base`, `--all`, `--package`, `--extra-root`, declared audit roots, Stop-hook opt-in) with no name/type/default table

### agents/specs/raises-section-resolution/spec.md

- agents/specs/raises-section-resolution/spec.md:whole file - Spec size - 240 lines and 11 top-level sections, over both guidelines
- agents/specs/raises-section-resolution/spec.md:50 - Module location references a path under `src/` - lists `claude/skills/auditme/...` and `docs/` paths only, states it is not under `src/`

### agents/specs/repeatable-phase-b/spec.md

- agents/specs/repeatable-phase-b/spec.md:whole file - Spec size - 357 lines, over the ~200-line guideline
- agents/specs/repeatable-phase-b/spec.md:79 - Module location references a path under `src/` - lists `claude/skills/auditme/...` paths only, states it is not under `src/`

### Coverage (sampled)

This is the first audit, so every sampled site is coverage; none is marked as missed by a review.

## Phase B findings (consolidated)

Each group carries a recommendation. The per-question sections above list every site.

### F1. An unreadable file crashes the checker instead of being reported

- **Category:** A
- **Question:** A1 (35 listed), A2 (24 sampled)
- **Severity:** medium
- **Location:** every `path.read_text` site listed under A1 and A2, mostly in `claude/skills/auditme/checks/auditme/rules/` and `core.py`; the `subprocess.run` calls in `rules/project_hygiene.py` (`check_lockfile`, `check_ruff`, `check_ruff_version`)
- **Description:** each rule reads source with `path.read_text` inside a `try` that catches `SyntaxError` and `UnicodeDecodeError` but not `OSError`. A file removed or made unreadable mid-run (an editor's swap file, a permission change) ends that check for the whole root: `audit.py`'s `run_check` reports one `auditme-check-crash` hit carrying the error text, every other hit that check would have found in the root is lost, and `changed.py` fails the gate on the crash hit. The `subprocess` handlers catch only `FileNotFoundError`.
- **Recommendation:** one shared reader in `core.py` that every rule uses, giving one place to decide what an unreadable file means (see decision D2). Widen the `subprocess` handlers to `OSError`.

### F2. Registered `check_*` functions read as pure-named functions doing I/O

- **Category:** A
- **Question:** A9 (68 of 79 sampled hits)
- **Severity:** low
- **Location:** every `check_*` function in `claude/skills/auditme/checks/auditme/rules/`
- **Description:** A9 treats `check_` as a pure prefix. In the registry, `check_` means "run this check", and every one reads the tree and prints hits. All 68 hits have this one cause.
- **Recommendation:** see decision D3.

### F3. Other pure-named functions that do I/O

- **Category:** A
- **Question:** A9 (11 sampled hits)
- **Severity:** low
- **Location:** `changed.py:70` `resolve_base`; `core.py:744` `is_private`; `phaseb/architecture.py:74` `parse_audited_files`; `phaseb/batches.py:166` `check_batch`, `:201` `check_run`; `phaseb/docrefs.py:302` `resolve_path`; `phaseb/testmap.py:47` `parse_file`, `:106` `parse_test_tree`, `:286` `build_index`, `:343` `build_test_map`; `rules/imports_and_surfaces.py:374` `parse_package_layering`
- **Description:** each name promises a pure computation; each reads files or runs git.
- **Recommendation:** rename the ones that read (`read_*`, `load_*` where the predicate's `load_` exemption applies), or record each as accepted on this page.

### F4. Helpers without a direct test

- **Category:** T
- **Question:** T1 (68 listed)
- **Severity:** medium
- **Location:** listed under T1 above; mostly `core.py` (13), `rules/error_handling.py` (25) and `rules/state_and_effects.py` (10)
- **Description:** these helpers count as public: `core.py`, the `rules/` modules and the `auditme` package's `__init__.py` declare no `__all__` (only `phaseb/__init__.py`, `phaseb/batches.py` and `phaseb/ledger.py` do), and the project bans leading underscores, so the underscore rule finds nothing private. A public function needs a direct test, and tests reach these only through their callers. The verdicts were made with an empty test index (see [Checker request](#checker-request)); the reviewers read the test files themselves.
- **Recommendation:** see decision D4.

### F5. Pure helpers without a property test

- **Category:** T
- **Question:** T2 (23 listed)
- **Severity:** low
- **Location:** listed under T2 above
- **Description:** every T2 candidate has a well-defined domain (string masking, name sorting, graph reach, class lineage) and no hypothesis test. The repository declares neither `hypothesis` nor `pytest` (D1).
- **Recommendation:** see decision D5.

### F6. Specs name renamed helpers and moved settings

- **Category:** Doc
- **Question:** Doc4 (21 listed)
- **Severity:** low
- **Location:** listed under Doc4 above, in the specs for false positives, the listed architecture, documentation and test questions, project setup, raises-section resolution and repeatable Phase B
- **Description:** mostly helpers whose leading underscore was removed (`_reach_sites`, `_handler_passes_on`, `_extract_string_eq_var`, `_source_definitions`). Also: `check_ruff_version` is said to be in `CHECKS` but sits in `PROJECT_CHECKS`; `check_run` is said to raise nothing; `PhaseBError` is placed in the wrong module; a `--batch-size` default; and brief-version lines that later bumps overtook.
- **Recommendation:** fix each line in place, with an amendment note where the spec records history.

### F7. User guides out of date

- **Category:** Doc
- **Question:** Doc5 (10 listed)
- **Severity:** medium
- **Location:** `docs/guide/checker.md:35`, `:104`, `:326-330`; `docs/reference/cli.md:157`, `:209`, `:264`; `docs/reference/skills.md:40`, `:59-60`
- **Description:** among them: the Stop hook runs a trusted worktree's own `changed.py`, not always the installed one; the invalid-TOML message text; "no other directory is swept" ignores declared roots; the `/auditme` commit message is `docs(audit): add review-N`, not `auditme: add review-N`; four checks called project-level run once per root.
- **Recommendation:** fix each in the guide.

### F8. README and AGENTS.md disagree

- **Category:** Doc
- **Question:** Doc3 (2 sampled)
- **Severity:** low
- **Location:** `AGENTS.md:5` ("at the end of a session", but the hook runs at the end of a turn); `README.md:3` (omits the published `no-project-names` hook)
- **Recommendation:** fix both lines.

### F9. `list_candidates` does not declare `RootsError`

- **Category:** A
- **Question:** A4 (1 listed)
- **Severity:** low
- **Location:** `claude/skills/auditme/checks/auditme/phaseb/candidates.py` `list_candidates`
- **Description:** every lister it dispatches to raises `RootsError`; its `Raises:` section omits it.
- **Recommendation:** add `RootsError` to the section.

### F10. `phaseb/__init__.py` exports names only tests use

- **Category:** A
- **Question:** A17 (1 listed)
- **Severity:** low
- **Location:** `claude/skills/auditme/checks/auditme/phaseb/__init__.py`
- **Description:** `Candidate`, `Lister`, `MergeResult`, `TestRef`, `Verdict`, `architecture`, `build_test_map`, `question_kinds` and `register_question` have no non-test consumer.
- **Recommendation:** drop them from `__all__` (keep the `architecture` import for its registration side effect), and have tests import them from their submodules.

### F11. Missing annotations in checker source

- **Category:** S
- **Question:** S1 (14 sampled)
- **Severity:** low
- **Location:** `core.py:41` (`**kwargs`); `rules/imports_and_surfaces.py:465` `maybe_emit_layering` (9); `rules/state_and_effects.py:377`, `:651` (two nested `walk_non_nested`, 2 each)
- **Recommendation:** annotate them. For tests, as a count only: 99 parameter and 28 return annotations are missing in 7 modules.

### F12. Type-only imports outside a `TYPE_CHECKING` block

- **Category:** S
- **Question:** S4 (23 sampled)
- **Severity:** low
- **Location:** listed under S4 above (13 in checker source, 10 in tests)
- **Description:** `claude/rules/auditme/coding-standards.md` asks for type-only imports under `TYPE_CHECKING`. Nothing enforces it: no checker rule, and ruff's `TC` rules are not selected.
- **Recommendation:** select ruff's `TC` rules in `pyproject.toml` so the hook enforces the rule, then fix the hits.

### F13. `phaseb.py merge` can hash verdicts at a different depth from the plan

- **Category:** A
- **Question:** A5 (1 sampled)
- **Severity:** medium
- **Location:** `claude/skills/auditme/checks/phaseb.py:144` `run_merge`
- **Description:** `plan.json` does not record the `--depth` the plan used, and `merge` re-lists with its own `--depth`. A merge run with a different depth writes verdicts whose hashes match no candidate, so they are re-judged next time without any warning.
- **Recommendation:** record the depth in `plan.json` and refuse a merge whose depth differs.

### F14. Construction duplicated or completed after the fact

- **Category:** A
- **Question:** A8 (1), A13 (1), A15 (4), sampled
- **Severity:** low
- **Location:** `phaseb/docrefs.py:198` (`index.aliases` set after `CorpusIndex` is built); `phaseb/architecture.py:820` (`file.rel` passed as both `id` and `path`); `phaseb/testmap.py:96`/`:99` and `phaseb/candidates.py:253`/`:256` (the same `Site` construction); the site-to-`Candidate` construction (3 copies) and section-to-`Candidate` construction (4 copies) in `phaseb/candidates.py`; `DocTarget` built by hand five times in `phaseb/docrefs.py`
- **Recommendation:** one factory per shape; build `CorpusIndex` complete; document the A1/A17 id form or give it its own id.

### F15. Repeated reads, parses and quadratic scans per run

- **Category:** P
- **Question:** A14 (5), P1 (4), P3 (7), sampled
- **Severity:** low
- **Location:** listed under A14, P1 and P3 above
- **Description:** every check re-globs its root and re-reads each file; corpus-wide indexes are rebuilt for each root; `audit_roots` and `all_names` re-read the same files on every `privacy` call; a full LCS runs on each cross-file function pair before the cheap length test; the test index rebuilds the reverse call graph for each site.
- **Recommendation:** a per-run parse cache in `core.py`, the indexes built once, and the length test before the LCS. Measure the sweep's run time on this repository before and after.

### F16. The Stop hook runs a whole-tree sweep at the end of a turn

- **Category:** P
- **Question:** P2 (1 sampled)
- **Severity:** low
- **Location:** `claude/hooks/auditme-stop.sh:45`
- **Description:** `changed.py` sweeps the whole tree when any changed file can carry a hit, including `uv lock --check`, which can reach the network. The turn waits on it.
- **Recommendation:** accept: the whole-tree sweep is what lets cross-file rules see every file (`changed.py`'s docstring). Measure the hook's time on a real project before changing it.

### F17. Arguments and declared roots are not contained

- **Category:** Sec
- **Question:** Sec2 (3), Sec4 (4), sampled
- **Severity:** low
- **Location:** `phaseb.py:170` and `:33` (`dismiss --question` builds the ledger path unchecked); `audit.py:149` (`--extra-root`), `:182` (`--package`); `core.py:247` (`[tool.auditme]` roots may point outside the project, and an absolute one makes the overlap error raise `ValueError`, not `RootsError`)
- **Recommendation:** check `--question` against the registry; require roots and `--package` to resolve inside the project, raising `RootsError`.

### F18. The Stop hook and the installer have no end-to-end test

- **Category:** T
- **Question:** T3 (2 sampled)
- **Severity:** low
- **Location:** `claude/hooks/auditme-stop.sh` (tests always substitute a fake `changed.py`); `bin/install-claude.sh` (tests always substitute a fake `uvx`)
- **Recommendation:** one test each that runs the real checker or installer in a temporary home.

### F19. `pytest` is not declared

- **Category:** D
- **Question:** D1 (1 sampled)
- **Severity:** low
- **Location:** `pyproject.toml`
- **Description:** the test modules import `pytest`, which arrives only through `uv run --with pytest`, unpinned.
- **Recommendation:** declare it in a `dev` dependency group (with `hypothesis` if D5 is answered that way), pinned per the resolver's `exclude-newer`.

### F20. Spec-template gaps

- **Category:** Doc
- **Question:** spec review (19 gaps)
- **Severity:** low
- **Location:** every `agents/specs/*/spec.md` (listed under [Spec review](#spec-review))
- **Description:** every spec exceeds the specdev skill's size guideline (7 gaps); every spec's module location is outside `src/` (7 gaps); two Settings sections give options in prose without types; `project-setup/spec.md` has no Settings section; `listed-phase-b-test-questions/spec.md:60` mentions the architecture spec without a link.
- **Recommendation:** see decision D6.

### Dismissed

- **A3, 6 sites in `phaseb/batches.py:145-162`:** each carries an `accept[layer-has-domain-error-raises-stdlib]` marker; accepted sweep hits are not re-litigated.
- **A20, 3 sites (`core.py:28` `EMITTED`, `phaseb/candidates.py:59` `REGISTRY`, `:61` `KINDS`):** each carries an `accept[mutable-module-level-exported]` marker.

## Decisions

### D1. Settle the thresholds reviewers could not

- **What is being decided:** whether to file one request in `claude/skills/auditme/requests.md` to settle, in the briefs, the thresholds this audit's reviewers reported as unsettled.
- **Background:** each brief tells its reviewer to report, not decide, a threshold it does not settle. This audit's reviewers reported these: A1, whether a `subprocess.run(check=False)` handler that catches only `OSError` covers the call, and whether returning a failure as a problem string counts; A4, a call dispatched through a registry lookup; T1, a test that runs a script by path as a subprocess, a call made inside a conftest fixture, and a function passed as a callable argument; Doc4, whether a spec header's date dates its sections, whether an implemented spec's "brief version 1" or list of listed questions is drift once later changes move on, whether a TODO item moved to `DONE.md` is drift, and a "found <date>" bullet's present-tense sentence; Doc5, whether a parenthetical list or a list of exit conditions claims to be complete, and an "any existing file" claim.
- **What it affects:** the briefs' versions (a bump re-judges every candidate of that question); the next audit cannot start until the request is shipped or rejected.
- **Options:**
  - **File the request (recommended):** one entry listing each threshold; settling them is a skill change between audits, as on 2026-11-21 for the earlier set.
  - **Leave them:** reviewers keep judging them case by case, and the same question can get different verdicts in different batches.

### D2. What the checker does with a file it cannot read

- **What is being decided:** the behaviour behind F1's shared reader.
- **Background:** today a read that raises `OSError` ends the check for that root; `audit.py` (`run_check`) turns it into one `auditme-check-crash` hit with the error text and goes on with the next check, so the gate fails, but the check's other hits in that root are never reported. A file with a syntax error, by contrast, is skipped silently.
- **What it affects:** every rule module, the `changed.py` gate, and A1/A2's open findings (59 sites).
- **Options:**
  - **Report it as a hit (recommended):** the reader returns nothing, and the driver emits one `unreadable-file` hit naming the path, so the gate fails with a message and no file is silently skipped.
  - **Stop with a domain error:** the sweep exits with one error naming the file; a single unreadable file stops every check.
  - **Accept the crash hit:** dismiss F1; a crash hit stays the report, and the check's other hits in that root stay lost.

### D3. A9 and the registry's `check_*` functions

- **What is being decided:** how to clear F2's 68 hits.
- **Background:** `check_` is both A9's pure prefix and the registry's naming convention for a check (`claude/skills/auditme/checks/auditme/registry.py`). Every project's audit sees the same conflict wherever a function named `check_*` validates and reads.
- **What it affects:** 68 open A9 sites now, and A9's predicate for every project.
- **Options:**
  - **Dismiss here and file a predicate refinement (recommended):** record the 68 as dismissed with this reason, and file a request to carve out a function registered as a check (a narrowing, so a skill change between audits).
  - **Rename the convention:** rename every `check_*` to `run_*` or similar; a large change that moves the registry, every test name and the docs.
  - **Dismiss here only:** the same conflict comes back in the next audit.

### D4. How the T1 helpers get covered

- **What is being decided:** F4's fix.
- **Background:** the project bans leading underscores and asks for `__all__` (`claude/rules/auditme/coding-standards.md`). `core.py`, the `rules/` modules and `auditme/__init__.py` declare no `__all__`, so every helper in them is public, and a public function needs a direct test. The privacy rule that reads `__all__` was settled in the T1 spec's decision 1 (2026-11-20).
- **What it affects:** 68 T1 findings; the modules of `claude/skills/auditme/checks/auditme/`.
- **Options:**
  - **Declare `__all__` per module, then test what stays public (recommended):** each module names what other modules and tests use; helpers outside it become private and are covered through their callers' tests; the next audit re-judges T1.
  - **Write a direct test for each of the 68:** no change to the modules; many tests that repeat what the callers' tests already show.

### D5. Property tests for the T2 helpers

- **What is being decided:** whether the repository takes `hypothesis` as a test dependency.
- **Background:** the shared testing rule asks for hypothesis tests on well-defined domains (`claude/rules/python/testing.md` in the agents repository). The checker itself is standard-library only, but its tests may have dependencies; today they need only `pytest`, undeclared (F19).
- **What it affects:** 23 T2 findings; `pyproject.toml` and `uv.lock`; the test command in `AGENTS.md` and CI.
- **Options:**
  - **Add `pytest` and `hypothesis` to a `dev` group and write the tests (recommended):** the test command becomes `uv run pytest ...`, and both are pinned.
  - **Dismiss T2 for this repository:** record each as dismissed with the reason that the test suite stays dependency-free.

### D6. Spec-template gaps that come from this repository's layout

- **What is being decided:** which of F20's 19 gaps to fix.
- **Background:** the specdev skill expects code under `src/` and specs of about 200 lines. Here the checker lives beside its skill, under `claude/skills/auditme/checks/`, and every spec is implemented and carries dated amendments, which is why each runs long.
- **What it affects:** the 7 specs under `agents/specs/`.
- **Options:**
  - **Dismiss the size and module-location gaps; fix the other five (recommended):** the 14 layout and size gaps are dismissed with that reason; the Settings, link and missing-section gaps get fixed.
  - **Fix all 19:** split each spec and restate every module location, which rewrites every spec.

## Checker request

The Phase B test index (`claude/skills/auditme/checks/auditme/phaseb/testmap.py`, `TEST_TREES = ('src/tests', 'tests')`) reads tests only from `src/tests/` and `tests/`. This repository's checker tests live in `claude/skills/auditme/tests/`, which `[tool.auditme]` declares as an audit root, so every T1 and T2 candidate here had empty `tests` and `test_files`: checked on batch 1 of T1, 48 of 48 empty. The reviewers judged from the test files directly, but nothing a declared test root holds reaches a lister. Per the skill, this goes into `requests.md` after this review is written, and the next audit cannot start until it is shipped or rejected.

## Files reviewed (Phase B)

- every non-test `.py` file under `claude/skills/auditme/checks/` - questions A1-A25, S1-S4, P1-P3, Sec2-Sec5, T1, T2
- every `.py` file under `claude/skills/auditme/tests/`, `claude/skills/auditme-project-setup/tests/` and `tests/` - S1 (count), S4, T1-T3, A20/A25 readers
- `bin/install-claude.sh`, `bin/check-foreign-names.sh`, `claude/hooks/auditme-stop.sh` - P2, Sec2-Sec4, T3, S4
- every tracked file - Sec1
- `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, `.github/workflows/*.yml`, `mkdocs.yml` - D1-D3
- `agents/specs/**` - Doc4, spec review
- `docs/**`, `README.md` - Doc5, Doc3
- `AGENTS.md` - Doc1, Doc2, Doc3

## Prior findings re-verified

None: this is the repository's first review, and it has no `agents/tasks/audit-reviews/`.

## Recommendations

1. F1 with D2: the gate should report an unreadable file, not crash.
2. F13: refuse a merge at a different depth, so verdict hashes stay meaningful.
3. F7, F6, F8: the user guides first, then the specs.
4. F4 with D4, F5 with D5, F19: test coverage and declared test dependencies.
5. F12 (enable ruff `TC`), F11, F9, F10, F17, F18.
6. F14, F15, F3: refactors, after a timing of the sweep.

## Answers

Answered on the review page on 2026-11-21, with no comments; every answer is the recommended one.

| Item | Answer |
|---|---|
| F1, F3-F15, F17-F20 | approved |
| F2 | flagged: dismissed, `check_` is the registry's convention (D3 files the refinement) |
| F16 | flagged: dismissed, the whole-tree sweep is by design (`changed.py`'s docstring) |
| D1 | file one request to settle the unsettled thresholds |
| D2 | report an unreadable file as a hit |
| D3 | dismiss the 68 A9 `check_*` sites here and file a predicate refinement |
| D4 | declare `__all__` per module, then test what stays public |
| D5 | add `pytest` and `hypothesis` to a `dev` group and write the property tests |
| D6 | dismiss the 14 size and module-location spec gaps; fix the other five |

Filed in `claude/skills/auditme/requests.md` on 2026-11-21: the test-index request, D1's threshold request and D3's refinement.

