# Audit Review 3

**Date:** 2026-11-22
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`); every sampled question ran on the whole tree
**Commit:** 6b51a218a24cec0bfe359dfdc8aa7a4bd54208e7
**Script output:** /tmp/audit-auditor.jsonl (45 hits, 45 accepted, 0 unaccepted)
**Script version:** 1187649b552c2cf9fc9737c169f408c05bedc11781ee2d2c528449fb4c025abf
**Convergence note:** the checker changed after review-2, both through review-2's task list and through the review-2 threshold rulings.
- Review-2's task list made these changes:
  - the `no-project-names` hook's exit codes;
  - the `--depth` rule;
  - a missing `uv` or `ruff` is now reported as a hit;
  - the renamed readers;
  - `check_spec_api_signature_drift` moved to the project-level checks.
- The threshold rulings (2026-11-22) bumped the A1, A4, A17, Doc4 and Doc5 briefs, so every candidate of those questions was judged again as new.
- This is the third audit counted from review-1, so every sampled question ran on the whole tree. A sampled finding in code review-2 did not sample is coverage, not drift.
**Review page:** https://claude.ai/artifact/CqyCoh9zRAweMi2wqKGoDy

## What is being reviewed and how

This is the checker repository's third audit of its own code. It ran the mechanical sweep, every Phase B question in every category over the whole tree, and the spec review. The sweep is clean.

Phase B found ten groups:

- **Stale docs and specs.** Most findings, as in review-2, are stale statements: some predate review-2's task list, and some describe behaviour that list changed.
- **Performance.** Every rule check parses every file again (F6), which takes about 5.4 s of a 12.2 s sweep.
- **Code.** A few small code findings.

For each group, choose Fix, which makes it a task, or Dismiss, with a reason, and answer the decision. Every answer is recorded in [Answers](#answers).

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 45 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 948 judged (A1 30, A4 49, A17 2, T1 260, T2 23, Doc4 433, Doc5 151). A11, A19, Doc1 and Doc2 carried every verdict |
| `phaseb.py check` on every listed question | pass, no retries |
| Every sampled question returned a hit list or "no hits" | pass |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| Prior findings to re-verify | none open: every review-2 finding was resolved by `agents/tasks/audit-reviews/tasks-2.md` (all ten tasks done) or dismissed |

## Summary

The sweep reports 45 hits, all accepted by markers. Phase B flags 27 listed candidates: A1 1, T2 1, Doc4 13 and Doc5 12. A4, A11, A17, A19, T1, Doc1 and Doc2 flag none. The sampled questions flag A2 1, A8 2, A14 1, P3 1, S2 2 and S4 4. The spec review finds no gap.

One more defect was found outside the checklist: the `ruff format` half of the `ruff` rule never fires. It is filed as a checker request (see [Checker request](#checker-request)). The reviewers again reported thresholds their briefs do not settle (D1).

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits. Every hit is accepted by an inline marker; the full list is in `/tmp/audit-auditor.jsonl`.

## Phase B findings (consolidated)

Each group lists every site. The listed questions' verdicts are in `agents/audit-reviews/ledger/<Q>.jsonl`.

### F1. `cached_source` returns `None` for an unreadable file, again (A1)

- **Category:** A. **Question:** A1 (listed). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/core.py`, `cached_source`, `path.read_text`.
- **Description:** review-2 dismissed this site as by design (F2), following review-1's D2 (2026-11-21), which reports an unreadable file as a hit. The A1 brief went to version 4, so the candidate was judged again, and a judgement under a new brief version does not carry the dismissal. `cached_source` is not a registered check, so the 2026-11-22 ruling for registered checks does not cover it.
- **Recommendation:** dismiss again, by design (review-1 D2).

### F2. `positive_int` has no property test (T2)

- **Category:** T. **Question:** T2 (listed). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/phaseb.py::positive_int`. It arrived with review-2's Task 2.
- **Description:** only the CLI tests reach it, by running `phaseb.py` with `--batch-size` or `--depth`. The property to test: it returns `int(value)` exactly when the value parses to 1 or more, and raises `argparse.ArgumentTypeError` otherwise.
- **Recommendation:** add a hypothesis test in `claude/skills/auditme/tests/phaseb/test_cli.py`.

### F3. `changed.py`'s entry envelope misses `OSError` (A2)

- **Category:** A. **Question:** A2 (sampled, full). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/changed.py:220`.
- **Description:** `main`'s `try` catches only `ChangedError`. Its body calls `pathlib.Path.cwd()` (line 224) and `repo_root.resolve()` (line 225), and either can raise `OSError`. Such an error would escape as a traceback, not the gate's one-line error.
- **Recommendation:** translate `OSError` from those calls to `ChangedError`, and add a test.

### F4. Two dataclasses filled after construction (A8)

- **Category:** A. **Question:** A8 (sampled, full). **Severity:** low.
- **Locations:** `claude/skills/auditme/checks/auditme/phaseb/docrefs.py`:
  - `:227`, where `ClassInfo(target, bases, {}, {})` gets its `members` and `field_types` filled afterwards (lines 231 to 238);
  - `:185`, where `CorpusIndex.build` builds the frozen `CorpusIndex` with empty dicts and then fills them through `add_module` (line 197). `frozen=True` does not stop that.
- **Recommendation:** build each dict first and construct the dataclass once, or make `build` assemble the index before constructing it.

### F5. `surface_files` resolves the audit roots on every call (A14)

- **Category:** A. **Question:** A14 (sampled, full). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/core.py:771`. It is reached through `privacy`, from the T1 lister (`candidates.py:817`) and the A1 lister (`architecture.py:601`).
- **Description:** each call reads and parses `pyproject.toml` and lists `src/` again. Measured on this repository on 2026-11-22: one T1 listing resolved the roots 275 times for 274 candidates, and one A1 listing 35 times for 30. Review-2's Task 6 removed the same repetition from the test index, but not from this path.
- **Recommendation:** pass the resolved roots down through `privacy` to `surface_files`, or take them from the per-run cache Task 6 added.

### F6. Every rule check parses every file again (P3)

- **Category:** P. **Question:** P3 (sampled, full). **Severity:** medium.
- **Location:** the per-root checks in `claude/skills/auditme/checks/auditme/rules/*.py`. Each calls `ast.parse('\n'.join(lines))` itself; `error_handling.py:48` is one example.
- **Description:** `auditme.core.read_and_parse` already returns a tree each run caches and shares, but the checks do not use it. Measured on one sweep of this repository on 2026-11-22: `ast.parse` ran 2462 times, taking 5.4 s of the sweep's 12.2 s. Review-1's Task 13 added the cache, but moved only some checks onto it.
- **Recommendation:** move every check onto `read_and_parse`, keeping the hits unchanged. Compare a sorted sweep before and after, and measure the run time again.

### F7. Two function-local constants named lower_snake (S2)

- **Category:** S. **Question:** S2 (sampled, full). **Severity:** low.
- **Locations:** `claude/skills/auditme/checks/auditme/rules/error_handling.py`, `:249` (`stdlib_excs`) and `:92` (`safe_attrs`).
- **Description:** the same kind of set at `:665` is `STDLIB_EXCS`, and the tree's other function-local constants are UPPER_SNAKE.
- **Recommendation:** rename both to UPPER_SNAKE.

### F8. Absolute from-imports in `phaseb/__init__.py` (S4)

- **Category:** S. **Question:** S4 (sampled, full). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/phaseb/__init__.py`, lines 10, 11, 20 and 21.
- **Description:** `claude/rules/auditme/imports.md` allows `from X import Y` in an `__init__.py` only in the relative form `from .module import Symbol`. These four lines use absolute forms, and line 10 imports the submodule `batches`, not a symbol from it.
- **Recommendation:** use relative imports (`from .candidates import ...`), and either re-export the `batches` names that are needed or drop the submodule from `__all__`, checking the readers first.

### F9. Specs that no longer match the code (Doc4)

- **Category:** Doc. **Question:** Doc4 (listed). **Severity:** medium.
- **Locations:**
  - `agents/specs/project-setup/spec.md`:
    - `:205` and `:266`: the ruff version check is silent with no ruff. Since review-2's Task 3 it reports a hit;
    - `:157`: `changed_files` returns only the paths in `base...HEAD`. It also adds uncommitted changes in the index and working tree;
    - `:346` and `:352`: the project-level checks are given as `check_lockfile` and `check_ruff_version`. Since review-2's Task 6, `check_spec_api_signature_drift` is one too;
    - `:297-302`: the list of rules that set `related` leaves out `raises-section-drift`;
    - `:477`: the reproduced `.pre-commit-hooks.yaml` leaves out the `no-project-names` hook;
    - `:523`: CI writes `Host github-auditor` with `HostName github.com`, not `Host github.com`;
    - `:581-583`: the list of what `templates/ci.yml` holds leaves out three of its steps: `uv tool install pre-commit`, the `.venv/bin` PATH step and the step that removes the deploy key;
    - `:627`: the list of the guide's sections leaves out "Moving a project from agents".
  - `agents/specs/listed-phase-b-architecture-questions/spec.md:147-148`: the A11 subject test also accepts lists and sets.
  - `agents/specs/listed-phase-b-documentation-questions/spec.md:90`: `register_question` has no `Raises:`; the code declares `PhaseBError`.
  - `agents/specs/listed-phase-b-test-questions/spec.md`:
    - `:87-88`: `load_test_map`'s `Raises:` leaves out `RootsError`;
    - `:120`: the T1 payload also has `private` and `privacy`.
- **Recommendation:** correct each statement. Where it records the spec's own change, word it as that record.

### F10. User docs that no longer match the code (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed). **Severity:** medium.
- **Locations:**
  - `docs/concepts.md`:
    - `:19-20`: the dependency list leaves out git, which `changed.py` runs;
    - `:25-27`: the "Fails on" column leaves out git and sweep failures;
    - `:25`: "the whole tree is swept" leaves out the skip when no diff base resolves or no reportable file changed.
  - `docs/guide/checker.md`:
    - `:55-58`: the exit-2 list leaves out argparse's usage error;
    - `:81`: a changed `.md` does not always trigger the sweep. `reportable()` ignores one under a hidden, `tasks` or `audit-reviews` directory;
    - `:112`: the `accepted_reason` values leave out `null`;
    - `:184-187`: "Hits a marker cannot accept" leaves out `unreadable-file`;
    - `:194-196`: the hits `audit.py` itself emits (`src-loose-module`, `unreadable-file`, `auditme-check-crash`) have no `check_*` docstring;
    - `:210`: the `unreadable-file` evidence is always `cannot read <name>`, and gives no reason;
    - `:280`: `silent-self-mutation` does not exempt `load`, and does exempt `update`, `mutate`, `merge`, `replace`, `apply`, `patch` and `override`;
    - `:296-297`: one `leading-underscore-def-class` form comes from an AST check, not a line regex.
  - `docs/reference/cli.md`:
    - `:109`: the project-level checks include `spec-api-signature-drift`;
    - `:224`: argparse writes its errors to stderr, not stdout;
    - `:229`: the failure list still leaves out "the audit sweep could not start". Review-2's Task 9 was meant to add it.
  - `docs/setup.md:268`: the troubleshooting list leaves out two causes: no diff base resolves, and the directory is not a git repository.
- **Recommendation:** correct each statement, checking each against the code.

## Phase B per-question results

Listed questions: each verdict is in `agents/audit-reviews/ledger/<Q>.jsonl`; `phaseb.py report . --question <Q>` prints the open ones. Sampled questions: mode full (the third audit counted from review-1).

### A1 (listed)

- 30 candidates judged, none left out; 1 open finding (F1).

### A4 (listed)

- 49 candidates judged, none left out; 0 open findings.

### A11 (listed)

- no candidate re-planned; every verdict carried; 0 open findings.

### A17 (listed)

- 2 candidates judged, none left out; 0 open findings.

### A19 (listed)

- no candidate re-planned; every verdict carried; 0 open findings.

### T1 (listed)

- 260 candidates judged, none left out; 0 open findings.

### T2 (listed)

- 23 candidates judged, none left out; 1 open finding (F2).

### Doc1 (listed)

- no candidate re-planned; every verdict carried; 0 open findings.

### Doc2 (listed)

- no candidate re-planned; every verdict carried; 0 open findings.

### Doc4 (listed)

- 433 candidates judged, none left out; 13 open findings (F9).

### Doc5 (listed)

- 151 candidates judged, none left out; 12 open findings (F10).

### A2 (sampled): Except tuple coverage
- Mode: full
- Inspected: every `try` statement in every tracked `.py` file (AST listing of each `try` with its handler types and the calls in its body), then read each body that touches disk, TOML/JSON parsers or subprocess: `audit.py`, `changed.py`, `phaseb.py`, `auditme/core.py`, `auditme/phaseb/{architecture,batches,candidates,docrefs,ledger,testmap}.py`, `auditme/rules/project_hygiene.py`; the command dispatch envelope in `phaseb.py:main` traced into each `run_*` command and the readers/writers it calls (`read_ledger`, `write_plan`, `read_plan`, `read_run_check`, `read_run_verdicts`, `merge_verdicts`); searched for translating decorators and `with` contextmanagers (none outside fixture strings). The `try` blocks in test files are fakes or fixture text and match no branch except `tests/test_project_hygiene.py:25` (subprocess, `FileNotFoundError`, no disk read).
- Hits:
  - `claude/skills/auditme/checks/changed.py:220` - the `main` envelope catches only `ChangedError`, but its body calls `pathlib.Path.cwd()` (line 224) and `repo_root.resolve()` (line 225) directly, which raise `OSError` (`FileNotFoundError` when the working directory has been removed); the locked set's `OSError` is missing, so that failure escapes as a traceback instead of the `changed.py:` message and exit 1.

### A3 (sampled): Domain-error layering
- Mode: full
- Inspected: every `raise` statement in every tracked `.py` file (AST listing of each raised type); domain errors are `auditme.core.RootsError`, `auditme.phaseb.errors.PhaseBError` and `changed.ChangedError`. The only stdlib raises in non-test code are the six `ValueError`s in `auditme/phaseb/batches.py:163-180`, already reported by the sweep under `layer-has-domain-error-raises-stdlib`, and `SystemExit` at the three entry points. Test-file raises (`RuntimeError`, `OSError`, `AssertionError`) are fakes standing in for failures.
- Hits: No hits

### A5 (sampled): Two sources of truth
- Mode: full
- Inspected: module-level state rebound by the driver (`auditme.core.EXTRA_ROOT_NAMES`, `DECLARATION_IGNORED`, `ROOT_MODULES`) against the parameters that read them (`extra_roots(names=None)`, `declared_roots`, `audit_roots`), and `audit.py`'s `--extra-root`/`--package` handling; `phaseb.py`'s `--depth`, `--batch-size` and question arguments against the values recorded in a plan (`Plan.depth`, `Plan.question`, `Plan.brief_version`) through `run_plan`, `run_merge`, `depth_of`, `list_candidates` and every `takes_depth` lister's default. Each precedence is stated in a docstring or comment and enforced (`names` defaults to the current `EXTRA_ROOT_NAMES`; a merge refuses a question or depth that differs from the plan's; `None` depth and every lister default to `DEFAULT_DEPTH`; verdicts take the plan's brief version by design).
- Hits: No hits

### A6 (sampled): Stage method dual-path
- Mode: full
- Inspected: every class in every tracked `.py` file and each method that assigns or mutates `self.<attr>` (AST listing). The project has no pipeline-stage class; the only methods that mutate `self` are `SiteCounter.next` (`auditme/phaseb/architecture.py:105`, a counter returning the new count, not a tuple) and `CorpusIndex.add_module`/`record` (`auditme/phaseb/docrefs.py:200,216`, return `None`).
- Hits: No hits

### A7 (sampled): Constructor purity
- Mode: full
- Inspected: every `__init__` in every tracked `.py` file: `SiteCounter.__init__` (`auditme/phaseb/architecture.py:102`) and the test fakes `Result.__init__` (`tests/test_project_hygiene.py:102`) and `LockResult.__init__` (`tests/test_project_hygiene.py:164`). Each only assigns attributes from its arguments or constants: no I/O, no compute, no argument mutated.
- Hits: No hits

### A8 (sampled): Late dataclass mutation
- Mode: full
- Inspected: every `@dataclass` defined in the tracked `.py` files, every construction of one bound to a local name inside a function, and every later attribute assignment, item assignment, mutating method call or `setattr` on that name (AST scan over all files, tests included), then read each site.
- Hits:
  - `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:227` - `ClassInfo(target, bases, {}, {})` is built with empty `members` and `field_types` and then filled after construction (`info.members[...] = ...` at lines 231, 234 and 238, `info.field_types[...] = ...` at line 235); the dicts could be built first and passed to the constructor.
  - `claude/skills/auditme/checks/auditme/phaseb/docrefs.py:185` - `CorpusIndex.build` constructs the `frozen=True` `CorpusIndex` with empty `sites`, `by_dotted`, `classes` and `options` dicts and then fills them through `index.add_module(...)` (line 197, via `record` and `class_info`); `frozen=True` does not stop this, so the instance is mutated after construction despite being declared frozen.

### A9 (sampled): Pure-named function side effects
- Mode: full
- Inspected: every function in every tracked `.py` file (tests included) whose name, without leading underscores, starts with a pure prefix, found by an AST walk; functions named in `CHECKS` (`claude/skills/auditme/checks/auditme/registry.py`) skipped as registered checks. Each remaining body's calls were listed and read. The only I/O reached is in `load_test_index` (`claude/skills/auditme/checks/auditme/phaseb/testmap.py:288`) and `load_test_map`, which read the package and test tree under the `root` they are given: a `load_` reading what it says it loads. Other `walk`/`replace` hits were `ast.walk` and `dataclasses.replace`.
- Hits: No hits

### A10 (sampled): Predicate semantics
- Mode: full
- Inspected: every `is_*`, `has_*` and `should_*` function in every tracked `.py` file (non-test and the test helper `is_candidate_source`), body read against its name and docstring, including the nested `is_domain` and `is_bound` in `claude/skills/auditme/checks/auditme/rules/error_handling.py`.
- Hits: No hits

### A12 (sampled): assert misuse
- Mode: full
- Inspected: `grep` for `assert` statements across every tracked non-test `.py` file.
- Hits: No hits (no `assert` statement outside test files)

### A13 (sampled): Same value to multiple structural slots
- Mode: full
- Inspected: every call to a capitalised callee in every tracked `.py` file whose non-constant arguments repeat, found by an AST walk. Two sites: `DocTarget(kind, rel, rel, 1, last_line)` (`claude/skills/auditme/checks/auditme/phaseb/docrefs.py:267`) is already inside the explicit factory `path_target`, whose docstring says a file's target is its path; `ClassInfo(target, bases, {}, {})` (`docrefs.py:227`) passes two distinct fresh dicts, not one value.
- Hits: No hits

### A14 (sampled): Repeated computation per request
- Mode: full
- Inspected: every non-test call site of the project-state helpers `auditme.core.audit_roots`, `declared_roots`, `corpus_py_files`, `extra_roots`, `load_test_index`, `run_git`/`git_lines` and the `tomllib` readers, traced through `privacy` and `surface_files`; checked against `corpus_index`/`INDEX_CACHE` caching. Measured by wrapping `declared_roots` and running the listers on this repository (2026-11-22): one `list_t1_candidates` run resolved the roots 275 times for 274 candidates, one `list_a1_candidates` run 35 times for 30 candidates.
- Hits:
  - `claude/skills/auditme/checks/auditme/core.py:771` - `surface_files` calls `audit_roots(root)` on every call, which re-reads and re-parses `pyproject.toml` (`declared_roots`) and re-lists `src/`; it is reached once per site through `privacy` from the T1 lister (`claude/skills/auditme/checks/auditme/phaseb/candidates.py:817`) and the A1 lister (`claude/skills/auditme/checks/auditme/phaseb/architecture.py:601`), so one lister run resolves the same roots once per candidate instead of once.

### A15 (sampled): Duplicate constructor / serialisation logic
- Mode: full
- Inspected: every constructor call of a project-defined class in every tracked non-test `.py` file, grouped by class with each site's field set. Classes built at 2+ sites: `Candidate` (three named factories `site_candidate`, `span_candidate`, `section_candidate` in `candidates.py`, each deriving the fields differently), `DocTarget` (factories `node_target`, `path_target`), `Verdict` (`batches.py:264` by keyword, `ledger.py:49` from a parsed record), `Site` (two calls in `module_sites` with different qualname and class), `Scope` and `SiteCounter` (different values per site, no shared assembly).
- Hits: No hits

### A16 (sampled): CLI entry envelope
- Mode: full
- Inspected: `git ls-files` for any `cli/` path, and every top-level `run_*` function in the tracked `.py` files. No `cli/*.py` file exists; the `run_*` functions in `claude/skills/auditme/checks/phaseb.py`, `audit.py` and `changed.py` are outside the question's scope.
- Hits: No hits

### A18 (sampled): Hot-path setup
- Mode: full
- Inspected: every tracked Python file (`git ls-files '*.py'`), searched for `def on_(step|log|evaluate|batch*)` and any `def on_`. The only matches are inside fixture source strings in `claude/skills/auditme/tests/test_state_and_effects.py` (lines 821, 844), which are test input, not callback methods.
- Hits: No hits

### A20 (sampled): Mutable module-level singleton
- Mode: full
- Inspected: an AST pass over every tracked Python file listing each module-level assignment whose value is a `dict`/`list`/`set` literal, comprehension or bare-builtin constructor call; for each, grep across every audit root in `[tool.auditme]` (checks/auditme, checks top-level, both test trees, tests/) for `from <module> import <name>`, `<module>.<name>` and `sys.modules['<module>'].<name>`. Cross-module readers exist only for `auditme.core.EMITTED`, `auditme.core.UNREADABLE`, `auditme.phaseb.candidates.REGISTRY` and `auditme.phaseb.candidates.KINDS`, all already reported by the sweep (`mutable-module-level-exported`, accepted). `SOURCE_CACHE`, `INDEX_CACHE`, `TAKES_DEPTH`, `STDLIB`, `DISK_IO_NAMES`, `MUTABLE_VALUE_SHAPES`, `MUTABLE_CONSTRUCTORS`, `STRFTIME_TOKENS`, `PARAMETRIC_NONBUILTIN_GENERICS`, `TYPING_DEPRECATED_ALIASES`, `RULE_HELP`, `COMMANDS` and the test-module constants have no reader in another module (same-named constants in other test files are their own definitions; `sys.modules` appears only in docstrings). `__all__` lists are not read by name.
- Hits: No hits

### A21 (sampled): Lazy init race
- Mode: full
- Inspected: every `is None:` test outside the test trees, every `global` statement (only `core.py:420`, `audit_roots` rebinding `ROOT_MODULES` unconditionally, not a lazy init), and the module-level caches in `core.py` (`SOURCE_CACHE`, `INDEX_CACHE`, filled by `not in` checks). No `if X is None: X = ...` lazy initialisation at module scope or in a module-level helper; the package has no thread, process-pool or concurrent call path (`threading`/`multiprocessing`/`concurrent` appear only as name lists in rule tables).
- Hits: No hits

### A22 (sampled): Fall-through after partial handling
- Mode: full
- Inspected: an AST pass over every tracked Python file for an `if`/`else` branch that holds a `try` (with or without a raising handler), does not end in `return`/`raise`/`continue`/`break`, and is followed by further statements. Two sites: `claude/skills/auditme/checks/audit.py:186` (the `RootsError` handler returns 2, then loose-module reporting runs only on success) and `claude/skills/auditme/checks/auditme/core.py:136` (`SyntaxError` sets `tree = None`, then the cache is written). Neither re-runs the first branch's work as if the condition were false.
- Hits: No hits

### A23 (sampled): Discarded multi-return
- Mode: full
- Inspected: every function in tracked Python files whose return annotation is a `tuple[...]` or a dataclass/NamedTuple the project defines, and every call site that discards the result, indexes it or reads one attribute. Non-test sites: `core.py:151`/`:160` (`cached_source(path)[0]`/`[1]`, text and tree independent), `core.py:852` (`privacy(...)[0]`, the second is only the deciding rule's name), `candidates.py:142`/`:161` (`registered(question)[1]`/`[2]`), `candidates.py:151` (`registered(question)` called for its raise), `batches.py:250` (`read_run_check(run_dir).problems`, the only field; `retry` derives from it), `testmap.py:359` (`load_test_index(root).refs(depth)`, a method call). None drops a component documented as changing how the used one is read. Test-tree discards sit inside `pytest.raises` or are setup calls.
- Hits: No hits

### A24 (sampled): Identity of subprocess / shell-out calls
- Mode: full
- Inspected: every `subprocess.*` call in tracked Python files outside the test trees. The sweep's `subprocess-without-memoisation` hits (`project_hygiene.py:42`, `:99`, `:220`) are excluded. Remaining: `project_hygiene.py:107` (a one-off retry with a different environment inside the same once-per-sweep check), `changed.py:55` (`run_git`, called with distinct arguments per call), `changed.py:135` (one sweep per run), `phaseb/docrefs.py:287` (`tracked_files`, called once per `CorpusIndex.build` or Doc2 lister, and a `phaseb.py` request lists one question).
- Hits: No hits

### A25 (sampled): Shallow immutable wrapper
- Mode: full
- Inspected: every module-level `types.MappingProxyType(...)`, `frozenset(...)`, `tuple(...)` and tuple literal in tracked Python files (from the same AST pass as A20). Members are strings, functions, `ast` node classes, tuples of strings, or (for `core.py:283` `ROOT_MODULES`, rebound at `core.py:423`) a comprehension mapping paths to strings. No `dict`/`list`/`set` member, none one tuple deep, and no non-frozen project dataclass instance.
- Hits: No hits

### S1 (sampled): Type annotations on every signature
- Mode: full
- Inspected: every `def` / `async def` (positional-only, positional, keyword-only, `*args`, `**kwargs`, returns; a leading `self`/`cls` exempt; nested functions included) in every file of `git ls-files '*.py'` at 6b51a21, parsed with `ast`. ruff's `ANN` rules are not selected in pyproject.toml, so nothing upstream enforces this.
- Hits: No hits in non-test source (every signature under `claude/skills/auditme/checks/` is fully annotated).
- Tests (count only, not enumerated): 34 test modules (files under a `tests/` directory, conftest included); 104 missing parameter annotations, 29 missing return annotations; 8 modules affected, 26 fully annotated.

### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake
- Mode: full
- Inspected: every module path, class name, function name, parameter name, class-body binding, attribute store, module-level binding and function-local assigned name in every tracked Python file, via `ast`. PascalCase module-level bindings (`Check`, `FunctionNode`, `Lister`, `HandlerLevel`, test-module `Builder` / `Runner` / `Project` / `StubRuff`) are type aliases, which take class-style names; `__all__`, `__test__` and `pytestmark` are language/pytest names; `ROOT_MODULES` in core.py:420-425 is a `global` module constant rebound, not a local. Function-local fixed literal collections are named two ways: UPPER_SNAKE at duplication.py:175 `MUTATING_METHOD_NAMES`, error_handling.py:665 `STDLIB_EXCS`, error_handling.py:1131 `STDLIB_WRITE_CALLS`, state_and_effects.py:97 `MUTATING_METHOD_NAMES`, :284 `PURE_PREFIXES`, :285 `MUTATION_METHODS`, :364 `PURE_PREFIXES`, :622 `BUILD_SIDE_EFFECTS`, :1042 `HOT_IO`, :1318 `PURE_PREFIXES`, :1319 `CACHE_DECORATORS` (the majority form); lower_snake at the two sites below. ruff's `N` rules are not selected.
- Hits:
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py:249` - function-local constant set of stdlib exception names is `stdlib_excs`, while the same kind of set in the same file at :665 is `STDLIB_EXCS` and the tree's other function-local literal constants are UPPER_SNAKE
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py:92` - function-local constant tuple `safe_attrs` is lower_snake, out of step with the UPPER_SNAKE function-local constants listed above

### S3 (sampled): TYPE_CHECKING block placement
- Mode: full
- Inspected: every module-level `TYPE_CHECKING` block in every tracked Python file (audit.py, changed.py, phaseb/batches.py, phaseb/testmap.py, rules/duplication.py, rules/error_handling.py, rules/imports_and_surfaces.py, rules/state_and_effects.py, rules/style_and_naming.py, and the test modules conftest.py, test_doc_candidates.py, test_docrefs.py, test_ledger.py, test_model.py, test_changed.py, test_core.py, test_imports_and_surfaces.py). Each is `if typing.TYPE_CHECKING:` at module level after the last import, with no import after it, holding only plain `import x` statements - the idiom coding-standards.md shows. conftest.py's block follows its `sys.path` set-up and the imports that need it, still after the last import. Blocks inside functions in test_imports_and_surfaces.py and test_t1_candidates.py are fixture text or tests of the guard.
- Hits: No hits

### S4 (sampled): Project-specific rule files
- Mode: full
- Inspected: claude/rules/auditme/coding-standards.md, claude/rules/auditme/imports.md and ~/.claude/rules/python/argparse.md (named by coding-standards.md's Data structures section), checked against every tracked Python file. Left to the sweep or ruff: from-import outside `__init__.py`, as-import, every leading-underscore form, `__future__`, stdlib logging, legacy typing / `Optional` / `Union`, %-formatting / `.format`, alphabetical literals and dict keys, definitions in `__init__.py`, import order, quotes, wildcard and unused imports; the sweep's accepted from-import hits (phaseb/architecture.py:25, phaseb/batches.py:17, phaseb/ledger.py:17) are not repeated. An `ast` pass found no leading-underscore name in any binding, parameter, attribute store or definition. argparse in audit.py, changed.py and phaseb.py is allowed (standard-library-only checker scripts), and every argparse call with arguments (`ArgumentParser`, `add_argument`, `add_parser`, `add_subparsers`) ends in a trailing comma. `print` in those entry points and in auditme/core.py:60 (the JSON-line hit output) is machine-consumable stdout/stderr in a stdlib-only tool, as review-2 judged. The sweep's `from-import` check skips every `__init__.py` (imports_and_surfaces.py:361), so the form of the imports in an `__init__.py` is not checked mechanically.
- Hits (imports.md: inside `__init__.py`, relative `from .module import Symbol` re-exports are "the only permitted use of `from X import Y`"; coding-standards.md's Clean `__init__.py` example uses the same relative form):
  - `claude/skills/auditme/checks/auditme/phaseb/__init__.py:10` - absolute `from auditme.phaseb import batches`, not the relative form (and imports a submodule rather than re-exporting a symbol)
  - `claude/skills/auditme/checks/auditme/phaseb/__init__.py:11` - absolute `from auditme.phaseb.candidates import (...)`, not `from .candidates import`
  - `claude/skills/auditme/checks/auditme/phaseb/__init__.py:20` - absolute `from auditme.phaseb.errors import PhaseBError`, not `from .errors import`
  - `claude/skills/auditme/checks/auditme/phaseb/__init__.py:21` - absolute `from auditme.phaseb.ledger import ...`, not `from .ledger import`

### P1 (sampled): O(n^2) on real-size inputs
- Mode: full
- Inspected: every nested loop in the checker code (`claude/skills/auditme/checks/audit.py`, `changed.py`, `phaseb.py`, `auditme/core.py`, `auditme/registry.py`, `auditme/rules/*.py`, `auditme/phaseb/*.py`), the shell scripts (`bin/check-foreign-names.sh`, `bin/install-claude.sh`, `claude/hooks/auditme-stop.sh`), the tests, both CI workflows, `pyproject.toml` and `.pre-commit-config.yaml`. The one pairwise loop over project data, `check_duplicate_call_sequence` (`auditme/rules/duplication.py:616-617`, every function signature against every later one), filters generic calls and pairs before its LCS; the whole sweep of this repository runs in about 12 s (measured 2026-11-22). Callee walks in `phaseb/candidates.py` and `phaseb/testmap.py` are depth-bounded. Tests, workflows and config hold no loops over project data.
- Hits: No hits

### P2 (sampled): Blocking I/O in hot paths
- Mode: full
- Inspected: every in-scope file for I/O inside training loops, request handlers or callbacks. The code is a batch CLI checker, a pre-commit hook script, a Stop hook script and their tests; it has no request handlers, training loops or callbacks. Source reads go through `auditme.core.cached_source` and `corpus_index`.
- Hits: No hits

### P3 (sampled): Repeated expensive computation per request
- Mode: full
- Inspected: every `ast.parse`, `read_text`, `read_bytes`, `rglob` and `functools.cache` site in the non-test Python files; the `cached_source` / `read_and_parse` / `corpus_index` caches in `auditme/core.py`; the registry's split into per-root `CHECKS` and run-once `PROJECT_CHECKS`; the review-2 P3 sites (`check_spec_api_signature_drift` is now in `PROJECT_CHECKS`; `phaseb/testmap.py:299` resolves `audit_roots` once and passes it down). Profiled one whole sweep of this repository with `ast.parse` instrumented (2026-11-22).
- Hits:
  - `claude/skills/auditme/checks/auditme/rules/error_handling.py:48` - representative of the per-file `tree = ast.parse('\n'.join(lines))` pattern across the per-root checks in `auditme/rules/*.py` (list them with `grep -rn "ast.parse('\\\\n'.join" claude/skills/auditme/checks/auditme`): each check re-parses every file it visits although `auditme.core.read_and_parse` already returns the run-wide cached tree of the same file, parsed once by `cached_source` (`auditme/core.py:112-142`). In one sweep of this repository `ast.parse` ran 2462 times for 5.4 s of the 12.2 s sweep (measured 2026-11-22), most of it re-deriving trees already in `SOURCE_CACHE`.

### Sec1 (sampled): Secrets in source
- Mode: full
- Inspected: every in-scope file, searched for `api_key`, `secret`, `password`, `passwd`, `token`, PEM private-key headers, `ghp_` and `sk-` prefixes. Matches are identifiers and prose; `.github/workflows/docs.yml:46` passes `secrets.GITHUB_TOKEN` through `env` to the deploy step only, with `persist-credentials: false` on every checkout.
- Hits: No hits

### Sec2 (sampled): Input validation at system boundaries
- Mode: full
- Inspected: CLI parsing in `audit.py` (`scope` must be a directory, `--package` a bare name and not `.`/`..`, `--extra-root` contained in the scope), `changed.py` (`--base` refused when its value starts with `-`), `phaseb.py` (`--question` checked against the registry, `--depth` and integer options refused below 1, `root`, `run_dir`, `--out`); plan, batch and ledger reading in `phaseb/batches.py` and `phaseb/ledger.py`; the Stop hook's JSON payload (`claude/hooks/auditme-stop.sh:7-12`, read with `jq`) and its checker trust test (shared git directory); `bin/check-foreign-names.sh` argument and list handling. The review-2 `--depth` hit is fixed (`phaseb.py:62-69`).
- Hits: No hits

### Sec3 (sampled): Command injection
- Mode: full
- Inspected: every `subprocess` call in scope (`changed.py:55`, `changed.py:135`, `auditme/rules/project_hygiene.py:42, 99, 107, 220`, `auditme/phaseb/docrefs.py:287`): all pass argument lists, none uses `shell=True`; the only user value reaching git (`--base`) is refused when it starts with `-`. Shell scripts quote every expansion; `bin/check-foreign-names.sh` passes names to `grep -F -e` and files after `--`; `bin/install-claude.sh` passes a fixed revision to `uvx` and forwards `"$@"` quoted; the Stop hook builds its JSON with `jq -Rs`. Workflow `run:` steps interpolate no event data.
- Hits: No hits

### Sec4 (sampled): Path traversal
- Mode: full
- Inspected: `audit.py` `--extra-root` (`path_inside` check, `audit.py:178`) and `--package` (bare name); `auditme/core.py` extra and declared roots; `phaseb.py` ledger paths (question validated against the registry before it names a file); `phaseb/docrefs.py:306-319` (document tokens normalised, `..` refused, then looked up in the `git ls-files` set); `phaseb/candidates.py:83` (test file names from the repository's own test index); `phaseb/batches.py` batch and result paths (fixed names under the operator-chosen run directory); the Stop hook's `$root/claude/skills/auditme/checks/changed.py`, run only when its git common directory matches the installed checker's.
- Hits: No hits

### Sec5 (sampled): PII in logs
- Mode: full
- Inspected: every in-scope file for `logging` / `logger` calls and for `print` of input text. No code configures or calls a logger (the matches are rule docstrings and the regexes that detect logger calls); output is hit records and error messages naming paths, refs and exit statuses.
- Hits: No hits

### T3 (sampled): Integration vs unit balance
- Mode: full
- Inspected: every orchestrator (`claude/skills/auditme/checks/audit.py`, `changed.py`, `phaseb.py`, `claude/hooks/auditme-stop.sh`, `bin/install-claude.sh`, `bin/check-foreign-names.sh`) against every test tree (`claude/skills/auditme/tests/`, `claude/skills/auditme-project-setup/tests/`, `tests/`). End-to-end tests found: `audit.py` - `claude/skills/auditme/tests/test_driver.py:468` runs the real script as a subprocess on a fixture project; `changed.py` - `claude/skills/auditme/tests/test_changed.py:216` `test_end_to_end_against_the_real_checker` (plus the cross-file and no-`src` cases after it), and `tests/test_stop_hook.py` real-checker cases; `phaseb.py` - `claude/skills/auditme/tests/phaseb/test_cli.py` runs it as a subprocess on a fixture project; `auditme-stop.sh` - `tests/test_stop_hook.py` runs the hook against a temporary HOME, including with a link to the real `changed.py`; `install-claude.sh` - `tests/test_install_claude.py:52` `test_the_real_installer_links_the_files_and_registers_the_hook`; `check-foreign-names.sh` - `tests/test_check_foreign_names.py` runs the script with `bash` on temporary files.
- Hits: No hits

### D1 (sampled): Declared in pyproject
- Mode: full
- Inspected: `pyproject.toml` (no `[project].dependencies`; groups `dev` = hypothesis, pytest, ruff; `docs` = mkdocs, mkdocs-material), `uv.lock`, and the top-level imports of every tracked `.py` file (`git ls-files '*.py'`, parsed with `ast`, absolute imports only, filtered against `sys.stdlib_module_names`). Non-stdlib modules imported: `hypothesis`, `pytest` (both declared in `dev`), and the project's own `audit`, `auditme`, `changed`, `conftest`, `phaseb` (local modules under the configured roots).
- Hits: No hits

### D2 (sampled): Unused declarations
- Mode: full
- Inspected: each declared dependency against imports, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `.github/workflows/docs.yml`, `mkdocs.yml` and subprocess calls. `hypothesis` - imported in `claude/skills/auditme/tests/phaseb/` tests; `pytest` - imported throughout the tests and run in `ci.yml` (`uv run pytest ...`); `ruff` - run as a command: the `ruff-check`/`ruff-format` hooks of `astral-sh/ruff-pre-commit` in `.pre-commit-config.yaml`, and `subprocess` calls in `claude/skills/auditme/checks/auditme/rules/project_hygiene.py`; `mkdocs` - run as a command in `docs.yml` (`uv run mkdocs build --strict`, `uv run mkdocs gh-deploy`); `mkdocs-material` - loaded as a theme: mkdocs is a declared host, `mkdocs.yml` sets `theme: name: material`, and the package's `entry_points.txt` registers `material = material.templates` in `[mkdocs.themes]` (read from the cached 9.7.7 `.dist-info` in the uv cache, as the `docs` group is not synced into `.venv`; `uv.lock` pins 9.8.0). No type-stub or kernel package is declared.
- Hits: No hits

### D3 (sampled): Lockfile coherence
- Mode: full
- Inspected: `/tmp/audit-auditor.jsonl` (the sweep; every hit accepted), counted by rule. The rule names present are duplicated-word, empty-init-while-siblings-export, except-interpolation, filesystem-op-without-envelope, from-import, get-container-default-then-method-call, layer-has-domain-error-raises-stdlib, leading-underscore-attribute-access, legacy-typing, literal-duplication, mutable-module-level-exported, non-alphabetical-literal, passthrough-shim, silent-broad-except, subprocess-without-memoisation. No `lockfile-drift` hit appears (the two hits mentioning `lock` are a `non-alphabetical-literal` and a `subprocess-without-memoisation` hit on the `uv lock --check` call in `project_hygiene.py`, not drift).
- Hits: No hits

### Doc3 (sampled): README.md and AGENTS.md consistent
- Mode: full
- Inspected: `README.md` and `AGENTS.md` as on disk at 07:06 UTC (HEAD `6b51a21`, working tree clean). Compared: what the repository holds (checker, `auditme-changed`/`auditme-all` hooks, `no-project-names` hook, Stop hook, `/auditme-project-setup` skill) - consistent; when the Stop hook runs ("before a turn ends" / "at the end of a turn") - consistent; what `bin/install-claude.sh` installs (README: skills, rules, Stop hook into `~/.claude/`; AGENTS.md: the same paths plus registering the hook in `~/.claude/settings.json`) - consistent, AGENTS.md more detailed; other shared rules come from the agents repository - consistent; the test command - identical in both (`README.md:19`, `AGENTS.md:22`).
- Hits: No hits

### Spec review (every spec)

No gaps in any of the seven specs (`agents/specs/*/spec.md`), against the specdev template and validation criteria, with review-1's D6 carve-outs.

### Coverage (sampled)

The sampled questions ran on the whole tree. Their sites in code that review-2 did not sample (A2, A8, A14, P3, S2, S4) are coverage, not drift, and none is marked missed by review-2.

## Checker request

The reviewer for Doc5 batches 1-2 reported, outside its brief, that the `ruff format --check` half of the `ruff` rule never produces a hit. I checked it on 2026-11-22. `check_ruff` (`claude/skills/auditme/checks/auditme/rules/project_hygiene.py:72`) emits a hit only for an output line containing `Would reformat` or ending in `.py`. Ruff 0.17.4, the version `.pre-commit-config.yaml` pins, and the 0.17.6 on `PATH` both print `unformatted: File would be reformatted` and ` --> <path>:<line>:<col>`. On a scratch project with an unformatted file, the sweep emitted no `ruff-format` hit. The parser also takes the hit's `path` from the text before the first colon, so older output would give a path of `Would reformat ...`. No test feeds the parser real format output: the two tests naming the variant only check the "ruff not installed" path. This is a defect in an existing check, so it is filed in `claude/skills/auditme/requests.md` after this review, as the skill requires, and the next audit waits on it.

## Prior findings re-verified

Every review-2 finding was resolved by `agents/tasks/audit-reviews/tasks-2.md`, whose ten tasks are all done, or dismissed (F2). Summary.md's Unresolved table was empty at audit start. No task in `agents/tasks/audit-reviews/` is incomplete. Two statements review-2 asked to fix are still stale, and are listed under F10: the failure list at `cli.md:229`, and `concepts.md:25`.

## Decisions

### D1. Settle the thresholds this audit's reviewers could not

- **What is being decided:** whether to file one request in `claude/skills/auditme/requests.md` that settles, in the briefs, the thresholds this audit's reviewers reported as unsettled.
- **Background:** each brief tells its reviewer to report, not decide, a threshold the brief does not settle. Thirty-one were settled on 2026-11-22. The briefs then met new cases:
  - **A1:** a standalone script's own error class (`ChangedError`), which is not among the payload's `domain_errors`.
  - **T2:** whether a call through a local alias in a `given` test is a direct call. It decides whether five helpers are covered.
  - **Doc4:**
    - a present-tense Module location row marked "(new)";
    - a `Raises:` that lists an error for one condition when the code raises it for another too;
    - a usage block that leaves an option off;
    - a predicate's definition, read as "X has a, b and c";
    - an undated statement replaced by a dated amendment later in the same section;
    - a list ending "all else is X's handling";
    - a numbered list of a guide's sections, read as complete or as order only;
    - a Testing section, read as an instruction or as a description;
    - a shared drift whose section's candidates are split across batches;
    - a command spelled with fewer flags than the code uses;
    - an ambiguous wording that both readings fit.
  - **Doc5:**
    - a "Stops for" list, as a list of when a command stops;
    - the docs' account of an external tool pinned in another repository.
- **What it affects:** the briefs' versions, since a bump re-judges every candidate of that question. The next audit cannot start until the request is shipped or rejected.
- **Options:**
  - **File the request (recommended):** one entry listing each threshold, settled between audits as before.
  - **Leave them:** reviewers keep judging them case by case.

## Answers

Answered on the review page on 2026-11-22. Every item took the recommended option, with no comments.

| Item | Answer |
|---|---|
| F1 | Dismiss (by design, review-1 D2; dismissed in the A1 ledger) |
| F2 | Fix |
| F3 | Fix |
| F4 | Fix |
| F5 | Fix |
| F6 | Fix |
| F7 | Fix |
| F8 | Fix |
| F9 | Fix |
| F10 | Fix |
| D1 | File the request |
