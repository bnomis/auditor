# Audit Review 2

**Date:** 2026-11-22
**Scope:** full (`claude/skills/auditme/checks/`, every test tree, `bin/`, `claude/hooks/`, `docs/`, `agents/specs/`, `AGENTS.md`, `README.md`); the sampled questions ran on the files changed since review-1
**Commit:** 9c0b7b59befc1bec8840144a78ce2afcb52a2de0
**Script output:** /tmp/audit-auditor.jsonl (44 hits, 44 accepted, 0 unaccepted)
**Script version:** 48066ec1d87ecdbbbc9e0f98b351f039f675ea3cd07656c1b50bdb752bc70c8c
**Convergence note:** the checker changed since review-1, by its task list and three requests, so a delta is expected. The task list made two changes. An unreadable file is now a hit, and arguments and declared roots are now contained. The requests made three. The T1 and T2 test index now reads tests from every audit root. A9 no longer reads a registered check as pure-named. The A1, A4, T1, Doc4 and Doc5 briefs were bumped (2026-11-22). Every candidate of a bumped question, and every T1 and T2 candidate whose tests changed, was judged again as new. A finding from that is catch-up, not a regression.
**Review page:** https://claude.ai/artifact/9TkMDk6nuYdY8h2ZwQKzga

## What is being reviewed and how

This is the checker repository's second audit of its own code. It ran the mechanical sweep, every Phase B question in every category, and the spec review. The sweep is clean. Phase B found two real defects in the code, both of them in the error paths of tools. It also found docs and specs that went stale while review-1's task list moved the code on. For each finding group below, approve it, which makes it a task, or flag it, which dismisses it and records your reason. Then answer the decisions. Each answer is recorded in [Answers](#answers).

## Automatic checks

| Check | Result |
|---|---|
| `requests.md` `## Open` empty at audit start | pass |
| `checks/audit.py` run, full JSONL saved | pass: 44 hits, 0 unaccepted |
| Every listed question has a verdict for every candidate | pass: 963 candidates judged (A1 31, A4 48, A17 2, T1 272, T2 24, Doc1 4, Doc2 3, Doc4 429, Doc5 150); A11 and A19 carried every verdict unchanged |
| `phaseb.py check` on every listed question | pass, no retries |
| Every sampled question returned a hit list or "no hits" | pass |
| No check added to `checks/auditme/rules/`, no predicate widened during the audit | pass |
| Prior findings to re-verify | none open: every review-1 finding was resolved by its task list (`agents/tasks/audit-reviews/tasks-1.md`, all done) |

## Summary

The sweep reports 44 hits, all accepted by markers. Phase B flags 32 listed candidates: A1 6, A17 1, T1 1, T2 1, Doc4 9 and Doc5 13. A4, A11, A19, Doc1 and Doc2 flag none. The sampled questions flag A9 4, A13 1, A14 2, A15 1, S4 15, P3 1 and Sec2 1, and the spec review finds 1 gap. Two findings are defects a user would meet:

- `phaseb.py candidates --question A11 --depth 3` crashes with a `TypeError` (F6);
- the `no-project-names` hook passes a commit that names a project when another file it checks cannot be read (F8).

The reviewers also reported thresholds their briefs do not settle (D1).

## Mechanical findings (from checks/audit.py)

No `accepted: false` hits. Every hit is accepted by an inline marker; the full list is in `/tmp/audit-auditor.jsonl`.

## Phase B findings (consolidated)

Each group lists every site. The listed questions' verdicts are in `agents/audit-reviews/ledger/<Q>.jsonl`.

### F1. A read failure that a helper lets escape (A1)

- **Category:** A. **Question:** A1 (listed). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/phaseb/architecture.py`, `list_a17_candidates.read_entries`, `path.read_text`.
- **Description:** the nested helper reads an `__init__.py`'s entries with no `try`, and neither of its call sites in `list_a17_candidates` has one. A file that cannot be read raises `OSError` or `UnicodeDecodeError` out of `phaseb.py candidates`, not `PhaseBError`.
- **Recommendation:** read through the package's translating reader (`candidates.read_text`, which raises `PhaseBError`).

### F2. `cached_source` returns `None` and records the path, by design (A1)

- **Category:** A. **Question:** A1 (listed). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/core.py`, `cached_source`, `path.read_text`.
- **Description:** the reviewer flagged that the handler returns `None`. The path goes into `UNREADABLE`, which the driver reports as an `unreadable-file` hit. That is the behaviour review-1's decision D2 chose (2026-11-21): report the file as a hit rather than stop. The docstring says the text is None "when it cannot be had" and names `UNREADABLE`. The A1 brief's rule for a documented failure return needs the returned value to carry the error, and `None` does not.
- **Recommendation:** dismiss as by design (review-1 D2). Record it with `phaseb.py dismiss`.

### F3. The checker's own checks return silently when `uv` or `ruff` cannot run (A1)

- **Category:** A. **Question:** A1 (listed). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/auditme/rules/project_hygiene.py`:
  - `check_lockfile`, both `subprocess.run(UV_LOCK_CHECK)` calls, under `except OSError: return`;
  - `check_ruff_version`, `subprocess.run([ruff, '--version'])`, under `except OSError: return`;
  - `check_ruff`, `subprocess.run(cmd)`, under a handler that emits a `ruff not installed` hit and goes on.
- **Description:** the first two are silent when the tool is missing. `check_ruff` reports it as a hit. The A1 brief counts neither silence nor an emitted hit as translation. See D2.
- **Recommendation:** as D2 decides.

### F4. `phaseb.py` reaches past `auditme.phaseb`'s `__all__` (A17)

- **Category:** A. **Question:** A17 (listed). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/phaseb.py` reads `auditme.phaseb.candidates.REGISTRY` and `auditme.phaseb.candidates.DEFAULT_DEPTH`. The verdict is filed on `claude/skills/auditme/checks/auditme/__init__.py`.
- **Description:** `candidates` is not in `auditme.phaseb.__all__`, so the command-line script reads a private submodule.
- **Recommendation:** export a registered-questions accessor and `DEFAULT_DEPTH` from `auditme/phaseb/__init__.py`, and read those.

### F5. Two helpers without the test the questions ask for (T1, T2)

- **Category:** T. **Questions:** T1, T2 (listed). **Severity:** low.
- **Locations:**
  - `claude/skills/auditme/checks/auditme/core.py::corpus_index` (T1): public under the `all` rule, with caller tests only. Missing: a direct test that it builds each index once per run, and rebuilds it when a corpus file changes.
  - `claude/skills/auditme/checks/phaseb.py::registered_question` (T2): no property test. The property is that it returns its input unchanged exactly when the value is a registered question, and raises `argparse.ArgumentTypeError` otherwise.
- **Recommendation:** add both tests.

### F6. `--depth` with a question that takes no depth crashes (Doc4, Sec2)

- **Category:** A. **Questions:** Doc4 (listed), Sec2 (sampled). **Severity:** medium.
- **Locations:**
  - `claude/skills/auditme/checks/auditme/phaseb/candidates.py`, `list_candidates`, passes `--depth` to every lister. `phaseb.py candidates . --question A11 --depth 3` raises `TypeError: list_a11_candidates() takes 1 positional argument but 2 were given` (reproduced on 2026-11-22).
  - `agents/specs/listed-phase-b-architecture-questions/spec.md:271` says it hands `--depth` only to the listers that take one (A4, T1, T2).
  - `claude/skills/auditme/checks/phaseb.py:59`: `--depth` takes any `int`, a negative one included.
- **Recommendation:** pass `--depth` only to the listers that take it, as the spec says. Refuse `--depth` for any other question, and refuse a value below 1, each with a usage error. Add tests.

### F7. Specs that state the current state wrongly (Doc4)

- **Category:** Doc. **Question:** Doc4 (listed). **Severity:** medium.
- **Locations:**
  - `agents/specs/listed-phase-b-architecture-questions/spec.md:19` says every question but A4 is still sampled. Eleven questions are now listed (`SKILL.md:199`).
  - `agents/specs/listed-phase-b-test-questions/spec.md:17` says the same: "Only A4 is listed".
  - `agents/specs/listed-phase-b-architecture-questions/spec.md:213` says each brief holds version 1. The A1 brief is at 3.
  - `agents/specs/listed-phase-b-documentation-questions/spec.md:177-179` says each Doc brief carries version 1. They are at 3, 2, 5 and 5.
  - `agents/specs/listed-phase-b-documentation-questions/spec.md:104-105` says `PhaseBError` is raised when `.pre-commit-config.yaml` cannot be parsed. The code never parses that file: hook ids are read by regex.
  - `agents/specs/project-setup/spec.md:260` gives invalid TOML's message as `pyproject.toml: <the parser's message>`. The code prints `pyproject.toml: not valid TOML (<the parser's message>)`.
  - `agents/specs/project-setup/spec.md:752` says this repository's CI passes with ruff at `rev: v0.17.1`. `.pre-commit-config.yaml:4` pins `v0.17.4`.
  - `agents/specs/repeatable-phase-b/spec.md:157` lists only `PhaseBError` under `list_candidates`'s `Raises:`. `RootsError` is declared too.
  - `agents/specs/repeatable-phase-b/spec.md:170` shows `plan_batches` with no `Raises:`. It raises `PhaseBError` when `size < 1`.
  - (The ninth Doc4 verdict is the spec half of F6.)
- **Recommendation:** correct each statement. Where one describes the spec's own change, reword it as the change ("version 1 when written") rather than as the present.

### F8. The `no-project-names` hook passes when a file cannot be read (Doc5)

- **Category:** Sec. **Question:** Doc5 (listed). **Severity:** medium.
- **Location:** `bin/check-foreign-names.sh:39`, against `docs/reference/cli.md:84`.
- **Description:** the hook runs `if grep ... -- "$@"; then exit 1`. grep exits 2 when any named file cannot be read, even if another file matched. So a matching file checked beside an unreadable one prints the match, and the hook exits 0. The reviewer reproduced this with a matching file and a missing one.
- **Recommendation:** fail on a match whatever else grep reports. Capture grep's status: exit 1 on 0, and exit 2 with a message on 2. Add a test beside the hook's existing tests.

### F9. User docs that no longer match the code (Doc5)

- **Category:** Doc. **Question:** Doc5 (listed). **Severity:** medium.
- **Locations:**
  - `docs/concepts.md:25-26`:
    - `auditme-changed` checks every file changed on the branch (`<base>...HEAD`), not only the commit's;
    - the published `auditme-all` hook is `manual` only, and runs at `git push` only when a project's own config adds `pre-push`.
  - `docs/guide/checker.md:34-36` says the project-level checks read `AGENTS.md`. Neither of them does; only per-root checks do.
  - `docs/guide/checker.md:55`: the exit-2 list for `audit.py` leaves out three cases:
    - a `--package` that is not a plain name;
    - an `--extra-root` outside the root;
    - an invalid `[tool.auditme]`.
  - `docs/guide/checker.md:68-69`: the failure list for `changed.py` leaves out four cases:
    - a sweep that could not start;
    - JSON that is not an object;
    - git that cannot run;
    - a diff or `rev-parse` that fails.
  - `docs/guide/checker.md:108-109`:
    - an `AGENTS.md` row does not accept an `as-import` hit;
    - `accepted_reason` is not always the marker's reason.
  - `docs/guide/checker.md:191-193` says every rule's predicate is in its `check_*` docstring. These seven have none:
    - `check_paired_sibling_helpers`
    - `check_silent_broad_except`
    - `check_def_class_in_init`
    - `check_unused_submodule_imports`
    - `check_ruff`
    - `check_lockfile`
    - `check_duplicated_word`
  - `docs/guide/checker.md:327-328` says `ruff-version-drift` is silent with no ruff installed. It still reports a `rev` that names no version.
  - `docs/reference/cli.md:36`: the list of `claude/`'s directories leaves out `rules/`.
  - `docs/reference/cli.md:151`: the exit-2 list for `audit.py` leaves out the same three cases as above, and a root that is not a directory.
  - `docs/reference/cli.md:215-223`:
    - the accept instructions are not printed for `ruff` or `lockfile-drift` hits;
    - the failure list leaves out a sweep that could not start.
  - `docs/reference/skills.md:31` says the checklist runs one subagent per question across every file. Listed questions run one reviewer per batch, and sampled questions run on changed files.
  - `docs/setup.md:97` says every sweep reports `ruff not installed` without ruff. A project with no audit root runs only the project-level checks, and gets no such hit.
  - (The thirteenth Doc5 verdict is F8.)
- **Recommendation:** correct each statement. For the seven checks without a docstring, add one rather than weaken the guide.

### F10. Pure-named functions that read files (A9)

- **Category:** A. **Question:** A9 (sampled; changed files since `83e59c0`). **Severity:** low.
- **Locations:**
  - `claude/skills/auditme/checks/auditme/core.py:149` `parse_source`: reads the file through `cached_source`, not only parses it.
  - `claude/skills/auditme/checks/auditme/core.py:625` `build_reads`, `:675` `build_definitions`, and `claude/skills/auditme/checks/auditme/rules/state_and_effects.py:983` `build_frozen_by_name`: each lists and reads every corpus file.
- **Description:** `parse_source` arrived with review-1's Task 6 and the other three with its Task 13. Task 12 renamed the earlier functions of this kind, so these are the same pattern again.
- **Recommendation:** rename them after what they do (for example `read_and_parse`, `index_reads`, `index_definitions`, `index_frozen_classes`), as Task 12 did.

### F11. `Candidate` built inline at four sites, one with an undocumented id (A13, A15)

- **Category:** A. **Questions:** A13, A15 (sampled). **Severity:** low.
- **Locations:** `claude/skills/auditme/checks/auditme/phaseb/architecture.py`, at `:306` (A11), `:398` (A19), `:698` (A1) and `:824` (A17). Each builds `candidates.Candidate(...)` with the same derivations: `path`, `start`, `end` and the hash. The one at `:824` passes `file.rel` as both `id` and `path`, and `Candidate.id` documents only the `<path>::<qualname>` form.
- **Recommendation:** build them through one helper beside `candidates.site_candidate`, and document the path-only id the A17 lister uses.

### F12. Root configuration and specs re-read on every call (A14, P3)

- **Category:** P. **Questions:** A14, P3 (sampled). **Severity:** low.
- **Locations:**
  - `claude/skills/auditme/checks/auditme/phaseb/testmap.py:293`: one `load_test_index` call resolves `audit_roots` at least three times, re-reading `pyproject.toml` each time. The calls go through `source_sites`, `read_test_tree` and `test_tree_roots`.
  - `claude/skills/auditme/checks/auditme/core.py:94`: `corpus_index` calls `corpus_py_files` on every lookup, which lists the files and re-reads `[tool.auditme]`.
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py:354`: `check_spec_api_signature_drift` is registered per root but never uses its root, so it rescans every spec on each pass.
- **Recommendation:** resolve the roots once per run, and pass them down. Move `check_spec_api_signature_drift` to `PROJECT_CHECKS`; that changes emission order, which the convergence note must then name.

### F13. argparse calls without the trailing comma the rule asks for (S4)

- **Category:** S. **Question:** S4 (sampled). **Severity:** low.
- **Location:** `claude/skills/auditme/checks/phaseb.py`, lines 70, 72, 73, 77, 78, 99, 100, 102, 103, 106, 108, 109, 113, 114 and 116.
- **Description:** `~/.claude/rules/python/argparse.md`, to which the coding standards refer, asks for a trailing comma so that each argument formats on its own line. These 15 calls are each on one line.
- **Recommendation:** add the trailing commas and let ruff format them.

### F14. A setting without its type and default (spec review)

- **Category:** Doc. **Question:** spec review. **Severity:** low.
- **Location:** `agents/specs/listed-phase-b-test-questions/spec.md:308`. `--question` is given only its values (`T1` or `T2`), with no type or default.
- **Recommendation:** give it as `str`, required, with no default.

## Phase B per-question results

Listed questions: each verdict is in `agents/audit-reviews/ledger/<Q>.jsonl`; `phaseb.py report . --question <Q>` prints the open ones. Sampled questions: changed files since `83e59c0` (review-1's commit), the second audit counted from review-1.

### A1 (listed)

- 31 candidates judged, none left out; 6 open findings (F1, F2, F3).

### A4 (listed)

- 48 candidates judged, none left out; 0 open findings.

### A11 (listed)

- no candidate re-planned; every verdict carried, none left out; 0 open findings.

### A17 (listed)

- 2 candidates judged, none left out; 1 open finding (F4).

### A19 (listed)

- no candidate re-planned; every verdict carried, none left out; 0 open findings.

### T1 (listed)

- 272 candidates judged, none left out; 1 open finding (F5).

### T2 (listed)

- 24 candidates judged, none left out; 1 open finding (F5).

### Doc1 (listed)

- 4 candidates judged, none left out; 0 open findings.

### Doc2 (listed)

- 3 candidates judged, none left out; 0 open findings.

### Doc4 (listed)

- 429 candidates judged, none left out; 9 open findings (F6, F7).

### Doc5 (listed)

- 150 candidates judged, none left out; 13 open findings (F8, F9).

### A2 (sampled): Except tuple coverage
- Mode: changed files since 83e59c0
- Inspected: every `try` in the in-scope non-test `.py` files (listed by an AST scan with handler types and body calls); read in full each whose body touches disk or a JSON/TOML parser: `auditme/core.py` (`cached_source`, `declared_roots`, stat loops), `auditme/phaseb/architecture.py:44-60` (try/finally over `json.loads`, no except tuple), `:86`, `:739`, `auditme/phaseb/batches.py:111`, `:130`, `:189`, `:201` (`parse_result`, whose `json.loads` raises a `ValueError` subclass), `auditme/phaseb/candidates.py:70`, `:167`, `:363`, `:415`, `:582`, `:610` (`read_bytes`, no decode), `auditme/phaseb/docrefs.py:86`, `:299`, `auditme/phaseb/testmap.py:56`, `auditme/rules/project_hygiene.py:47`, `changed.py:154`, `changed.py:220` (envelope over git subprocess calls). Grepped for translating decorators and `@contextmanager` envelopes: none in the in-scope code.
- Hits: No hits

### A3 (sampled): Domain-error layering
- Mode: changed files since 83e59c0
- Inspected: every `raise` in the in-scope non-test `.py` files (grep for `raise`, filtered to types other than `PhaseBError`, `RootsError` and `ChangedError`). Left: `auditme/phaseb/batches.py:163-180` (`ValueError`, already reported by the sweep under `layer-has-domain-error-raises-stdlib`, accepted), `phaseb.py:44` (`argparse.ArgumentTypeError` from an argparse `type=` callable, not one of the flagged stdlib types), `SystemExit(main())` entry points.
- Hits: No hits

### A5 (sampled): Two sources of truth
- Mode: changed files since 83e59c0
- Inspected: `phaseb.py` (`--depth` vs `DEFAULT_DEPTH` via `depth_of`, the plan's recorded depth checked in `run_merge`; `--batch-size` vs the registered batch size), `audit.py:160-195` and `auditme/core.py:270-360` (`--extra-root` vs the `[tool.auditme]` declaration via `DECLARATION_IGNORED`, documented at its definition; `--package` vs declared roots), `auditme/phaseb/batches.py` `read_plan` (absent depth read as the default, documented). Each precedence is stated and enforced in code.
- Hits: No hits

### A6 (sampled): Stage method dual-path
- Mode: changed files since 83e59c0
- Inspected: every method of every class in the in-scope non-test `.py` files (AST scan of returns and `self.<attr>` mutations): `SiteCounter`, `RunCheck`, `Verdict`, `Site`, `CorpusIndex`, `TestIndex`. No pipeline-stage class; no method both returns a tuple and mutates `self`. `SiteCounter.next` (`auditme/phaseb/architecture.py:105`) returns an int from the counter it bumps, which is its whole purpose and not a tuple.
- Hits: No hits

### A7 (sampled): Constructor purity
- Mode: changed files since 83e59c0
- Inspected: every `__init__` in scope - only `SiteCounter.__init__` (`auditme/phaseb/architecture.py:102`), which builds an empty `Counter`; no `__post_init__` in scope. Test files hold no `__init__` outside fixture source strings.
- Hits: No hits

### A8 (sampled): Late dataclass mutation
- Mode: changed files since 83e59c0
- Inspected: every construction of a dataclass in scope (`ClassInfo`, `CorpusIndex`, `TestIndex`, the frozen ones in `batches`, `candidates`, `architecture`, `testmap`, `docrefs`) and every non-`self` attribute assignment (grep). `docrefs.py:227` builds `ClassInfo(target, bases, {}, {})` and then fills its dicts by item assignment (`info.members[...] = ...`); no field is rebound, so it is not the `x.field = ...` shape the question asks about. Frozen dataclasses are changed only through `dataclasses.replace`. Dataclasses in test files appear only as fixture source text.
- Hits: No hits

### A9 (sampled): Pure-named function side effects
- Mode: changed files since 83e59c0
- Inspected: every function with a pure prefix in the non-test Python files of `changed-code.txt` (AST listing, then a name-based transitive scan for file, subprocess, clock and directory calls through same-package callees); the test files' helpers (only `is_candidate_source`, which calls `ast.walk`). Registered checks (members of `CHECKS` / `PROJECT_CHECKS` in `checks/auditme/registry.py`) excluded per the 2026-11-22 carve-out; no unregistered `check_` function exists in scope. `load_test_index` / `load_test_map` read the package and test tree they say they load (exempt). No sweep hit for this predicate.
- Hits:
  - `claude/skills/auditme/checks/auditme/core.py:149` - `parse_source` reads the file from disk (via `cached_source` -> `path.stat()` and a read), not only parses; the `load_` exemption does not cover `parse_`.
  - `claude/skills/auditme/checks/auditme/core.py:625` - `build_reads` reads every corpus file (`corpus_py_files` directory scan, then `parse_source` on each).
  - `claude/skills/auditme/checks/auditme/core.py:675` - `build_definitions` reads every corpus file (`corpus_py_files`, then `parse_source`).
  - `claude/skills/auditme/checks/auditme/rules/state_and_effects.py:983` - `build_frozen_by_name` reads every corpus file (`auditme.core.corpus_py_files`, then `auditme.core.parse_source`).

### A10 (sampled): Predicate semantics
- Mode: changed files since 83e59c0
- Inspected: the full body of every `is_` / `has_` / `should_` function (including nested ones) in the non-test files, against its name and docstring.
- Hits: No hits

### A12 (sampled): assert misuse
- Mode: changed files since 83e59c0
- Inspected: grep for `assert` statements in every non-test file in scope.
- Hits: No hits

### A13 (sampled): Same value to multiple structural slots
- Mode: changed files since 83e59c0
- Inspected: every call to a capitalised (class) name in all files in scope, checked for one non-literal expression passed to two or more slots; `DocTarget(kind, rel, rel, ...)` at `docrefs.py:267` is built by the `path_target` factory and its `id` field comment documents the path-only form, so it is not a hit.
- Hits:
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py:824` - the A17 `candidates.Candidate(...)` passes `file.rel` to both `id` and `path`, inline, with no factory; `Candidate.id` is documented only as `'<repo-relative path>::<qualname>'`, so the path-only id is undocumented.

### A14 (sampled): Repeated computation per request
- Mode: changed files since 83e59c0
- Inspected: project-state helpers in scope - `auditme.core.declared_roots` / `audit_roots` / `corpus_py_files` (resolved `[tool.auditme]` config), `read_pyproject`, `entry_point_targets`, `tracked_files`, `changed.py`'s git helpers - and their call sites per command flow. The subprocess-repetition cases are the sweep's (`subprocess-without-memoisation`) and A24's, not counted here.
- Hits:
  - `claude/skills/auditme/checks/auditme/phaseb/testmap.py:293` - one `load_test_index` call (the A4/T1/T2 `phaseb.py candidates` flow) resolves `auditme.core.audit_roots` at least three times - via `source_sites` (line 97), `read_test_tree` -> `test_tree_roots` (line 82) and `test_tree_roots` again (line 312), plus `TestIndex.refs` (line 286) - each re-parsing and re-validating `pyproject.toml`, re-scanning the extra roots and rebinding `ROOT_MODULES`.
  - `claude/skills/auditme/checks/auditme/core.py:94` - `corpus_index` calls `corpus_py_files` (and so `declared_roots`, re-parsing `[tool.auditme]`, and a full file listing) on every lookup, so one sweep run resolves the root configuration once per corpus-index lookup per check per root.

### A15 (sampled): Duplicate constructor / serialisation logic
- Mode: changed files since 83e59c0
- Inspected: every class in scope constructed from two or more sites (`Candidate`, `Site`, `Scope`, `DocTarget`, `SiteCounter`), compared by field set and assembly; `DocTarget` is factored into `node_target` / `path_target`, and `candidates.py` uses `site_candidate` / `section_candidate`.
- Hits:
  - `claude/skills/auditme/checks/auditme/phaseb/architecture.py:306` - `candidates.Candidate(...)` is assembled inline with the same field set and the same derivations (`path=file.rel`, `start=node.lineno`, `end=node.end_lineno or node.lineno`, `hash=candidates.digest([part.encode('utf-8') for part in ...])`) here (A11), at `:398` (A19), `:698` (A1) and `:824` (A17), with no shared helper of the kind `candidates.py` has (`site_candidate`, `section_candidate`).

### A16 (sampled): CLI entry envelope
- Mode: changed files since 83e59c0
- Inspected: searched for `cli/*.py` files in the repository (none) and for top-level `run_*` functions in scope; those found (`audit.py:117`, `changed.py:53`, `phaseb.py:125-190`, test helpers) are not in a `cli/*.py` module, so the question's enumeration does not reach them.
- Hits: No hits

### A18 (sampled): Hot-path setup
- Mode: changed files since 83e59c0
- Inspected: every Python file in changed-code.txt, grepped for callback methods (`def on_*`). The only matches (`claude/skills/auditme/tests/test_state_and_effects.py:821` and `:844`) are inside fixture strings passed to the `callback-hotpath-io` check, not callbacks of this project.
- Hits: No hits

### A20 (sampled): Mutable module-level singleton
- Mode: changed files since 83e59c0
- Inspected: an AST listing of every module-level assignment in the changed files whose value is a `dict`/`set`/`list` literal, comprehension or bare-constructor call; for each name, grep across every `[tool.auditme]` root (`claude/skills/auditme/checks/auditme`, `claude/skills/auditme/checks`, `claude/skills/auditme/tests`, `claude/skills/auditme-project-setup/tests`, `tests`) for `from <module> import <name>`, `<module>.<name>` and `sys.modules[...].<name>`. The sweep already reports `core.py:29` (`EMITTED`), `core.py:35` (`UNREADABLE`), `phaseb/candidates.py:59` (`REGISTRY`) and `phaseb/candidates.py:61` (`KINDS`) under `mutable-module-level-exported`, so those are skipped. Every other mutable container (`SOURCE_CACHE`, `INDEX_CACHE`, `STDLIB`, `DISK_IO_NAMES`, `MUTABLE_VALUE_SHAPES`, `MUTABLE_CONSTRUCTORS`, `STRFTIME_TOKENS`, `PARAMETRIC_NONBUILTIN_GENERICS`, `TYPING_DEPRECATED_ALIASES`, `RULE_HELP`, `COMMANDS`, the test-module fixtures, and each `__all__`) has no reader in another module; the one `module.__all__` match (`tests/test_annotated_all.py:41`) is inside a fixture string.
- Hits: No hits

### A21 (sampled): Lazy init race
- Mode: changed files since 83e59c0
- Inspected: every `is None:` test and every `global` statement in the changed non-test files. No module-scope `if X is None: X = ...` lazy initialiser exists; `core.py:415` (`global ROOT_MODULES`) rebinds unconditionally in `audit_roots`, and the `SOURCE_CACHE`/`INDEX_CACHE` lookups are dict caches, not None-guarded singletons. No module in any audit root imports `threading`, `multiprocessing`, `concurrent` or `asyncio`, so no concurrent path calls them.
- Hits: No hits

### A22 (sampled): Fall-through after partial handling
- Mode: changed files since 83e59c0
- Inspected: an AST scan of the changed non-test files for (a) `except` handlers that raise on one path and fall through on another, and (b) `if`/`else` branches containing a raising `try`/`with` that do not end in `return`/`raise` before following code; no match. Read by hand: `changed.py` (`run_git`, `git_lines`, `read_base_ref`, `sweep`, `main`), `rules/project_hygiene.py` (`check_ruff`, `check_lockfile` retry with `UV_NO_CONFIG`, ruff-version check), `phaseb/docrefs.py` `tracked_files`, `core.py` `cached_source`. Each raising branch exits; the lockfile retry is a deliberate re-run on a named uv message, not a translated error retried.
- Hits: No hits

### A23 (sampled): Discarded multi-return
- Mode: changed files since 83e59c0
- Inspected: every function in the audit roots annotated to return a `tuple[...]`, and every call site in the changed files that discards the whole result or indexes one component; the dataclasses in `phaseb/` for single-attribute reads of a call result. Sites read: `phaseb/candidates.py:121`, `:130`, `:140` (`registered(...)` accessors; `:130` calls it only for its `PhaseBError`), `core.py:146`, `:155` (`cached_source(...)[0]` / `[1]`, independent components), `core.py:847` (`privacy(...)[0]`, drops the deciding rule's name, which does not change how the bool is used), `tests/phaseb/test_testmap.py:266` (`read_test_tree(root)[0]`), `phaseb/batches.py:250` (`read_run_check(...).problems`, `RunCheck`'s only field). None drops a component documented as changing how the kept one is used.
- Hits: No hits

### A24 (sampled): Identity of subprocess / shell-out calls
- Mode: changed files since 83e59c0
- Inspected: every `subprocess.*` call in the changed non-test files and its callers. Skipped as sweep hits under `subprocess-without-memoisation`: `rules/project_hygiene.py:34`, `:87`, `:198`. Others: `rules/project_hygiene.py:95` (a conditional re-run of `uv lock --check` with a different environment, at most once per sweep), `changed.py:55` (`run_git`, called with different arguments each time per invocation), `changed.py:135` (one sweep per invocation), `phaseb/docrefs.py:287` (`tracked_files`, called once per question lister, and each CLI request lists one question).
- Hits: No hits

### A25 (sampled): Shallow immutable wrapper
- Mode: changed files since 83e59c0
- Inspected: an AST scan of every module-level `types.MappingProxyType(...)`, `frozenset(...)`, `tuple(...)` and tuple literal in the changed files for a `dict`/`list`/`set`/comprehension member or a call member at any depth; none. `core.py:278` / `:418` `ROOT_MODULES` (read from `rules/imports_and_surfaces.py:123` and tests) maps `pathlib.Path` to `str`, both immutable. The `frozenset` wrappers hold string literals only.
- Hits: No hits

### S1 (sampled): Type annotations on every signature
- Mode: changed files since 83e59c0
- Inspected: every `def` / `async def` (parameters including `*args`, `**kwargs`, keyword-only; returns; `self`/`cls` exempt) in the Python files of changed-code.txt, parsed with `ast`. ruff's `ANN` rules are not selected in pyproject.toml, so nothing upstream enforces this.
- Hits: No hits in non-test source (every signature in `claude/skills/auditme/checks/**` in scope is fully annotated).
- Tests (count only, not enumerated): 25 test modules in scope; 104 missing parameter annotations, 29 missing return annotations; 8 modules affected, 17 fully annotated.

### S2 (sampled): PascalCase / UPPER_SNAKE / lower_snake
- Mode: changed files since 83e59c0
- Inspected: every class name, function name, parameter name, assigned name and module-level binding in the in-scope Python files, via `ast`. PascalCase module-level bindings found (`Check`, `FunctionNode`, `Lister`, `HandlerLevel`, test-module `Builder` / `Runner` / `Project` / `StubRuff`) are type aliases, which take class-style names; `__all__`, `__test__` and `pytestmark` are language/pytest dunders and conventions.
- Hits: No hits

### S3 (sampled): TYPE_CHECKING block placement
- Mode: changed files since 83e59c0
- Inspected: every `TYPE_CHECKING` block in the in-scope files (source and tests). Each is `if typing.TYPE_CHECKING:` at module level, after all imports and before any other code, holding only plain `import x` statements - the same idiom throughout and the one coding-standards.md shows.
- Hits: No hits

### S4 (sampled): Project-specific rule files
- Mode: changed files since 83e59c0
- Inspected: claude/rules/auditme/coding-standards.md, claude/rules/auditme/imports.md, and ~/.claude/rules/python/argparse.md (which coding-standards.md's Data structures section names as the rule governing argparse use), checked against every in-scope Python file. Items the sweep already enforces (from-import, as-import, leading underscores, `__future__`, stdlib logging, legacy typing, %-formatting / `.format`, alphabetical literals, definitions in `__init__.py`) were left to it; its accepted hits at phaseb/architecture.py:25 and phaseb/batches.py:17 are not repeated. argparse in audit.py, changed.py and phaseb.py is allowed (standard-library-only checker scripts); `print` in those entry points and in auditme/core.py:60 (JSON-line hit output) is machine-consumable stdout/stderr in a stdlib-only tool, which the rule permits.
- Hits (argparse.md: arguments to argparse functions end in a trailing comma so they format one per line; these calls are on one line with no trailing comma; the sweep has no rule for this):
  - `claude/skills/auditme/checks/phaseb.py:70` - `parser.add_subparsers(dest='command', required=True)` on one line, no trailing comma
  - `claude/skills/auditme/checks/phaseb.py:72` - `commands.add_parser('candidates', help=...)` on one line
  - `claude/skills/auditme/checks/phaseb.py:73` - `candidates.add_argument('root', type=pathlib.Path)` on one line
  - `claude/skills/auditme/checks/phaseb.py:77` - `commands.add_parser('plan', help=...)` on one line
  - `claude/skills/auditme/checks/phaseb.py:78` - `plan.add_argument('root', type=pathlib.Path)` on one line
  - `claude/skills/auditme/checks/phaseb.py:99` - `commands.add_parser('check', help=...)` on one line
  - `claude/skills/auditme/checks/phaseb.py:100` - `check.add_argument('run_dir', type=..., metavar='dir')` on one line
  - `claude/skills/auditme/checks/phaseb.py:102` - `commands.add_parser('merge', help=...)` on one line
  - `claude/skills/auditme/checks/phaseb.py:103` - `merge.add_argument('root', type=pathlib.Path)` on one line
  - `claude/skills/auditme/checks/phaseb.py:106` - `merge.add_argument('run_dir', type=..., metavar='dir')` on one line
  - `claude/skills/auditme/checks/phaseb.py:108` - `commands.add_parser('report', help=...)` on one line
  - `claude/skills/auditme/checks/phaseb.py:109` - `report.add_argument('root', type=pathlib.Path)` on one line
  - `claude/skills/auditme/checks/phaseb.py:113` - `commands.add_parser('dismiss', help=...)` on one line
  - `claude/skills/auditme/checks/phaseb.py:114` - `dismiss.add_argument('root', type=pathlib.Path)` on one line
  - `claude/skills/auditme/checks/phaseb.py:116` - `dismiss.add_argument('candidate_id', metavar='id')` on one line

### P1 (sampled): O(n^2) on real-size inputs
- Mode: changed files since 83e59c0
- Inspected: every nested loop in the in-scope checker code (`checks/auditme/rules/*.py`, `checks/auditme/phaseb/*.py`, `checks/auditme/core.py`, `audit.py`, `changed.py`, `phaseb.py`); searched for `combinations`/`product`/`permutations` (none). The one pairwise loop over project data, `check_duplicate_call_sequence` (`rules/duplication.py:607-608`, every function against every other), has a length-ratio prefilter before its LCS and took 0.37 s over this repository's largest root; the whole per-check sweep totals about 20 s. Callee walks (`candidates.py:303`, `testmap.py:196`) are depth-bounded BFS. Tests, CI workflow and `pyproject.toml` hold no such loops over project data.
- Hits: No hits

### P2 (sampled): Blocking I/O in hot paths
- Mode: changed files since 83e59c0
- Inspected: all in-scope files for I/O inside training loops, request handlers or callbacks. The code is a batch CLI checker and its tests; it has no request handlers, training loops or callbacks. File reads go through the `cached_source` / `corpus_index` caches in `core.py`.
- Hits: No hits

### P3 (sampled): Repeated expensive computation per request
- Mode: changed files since 83e59c0
- Inspected: every check in `auditme.registry.CHECKS` (run once per audit root) for use of its `src_root` argument (AST scan of each check's body); the `corpus_index` cache in `core.py`; `TestIndex.refs` in `phaseb/testmap.py` (271 `reach` calls for 69 distinct starts, 0.01 s: repeated but not expensive); `capture_hits` in `phaseb/architecture.py`.
- Hits:
  - `claude/skills/auditme/checks/auditme/rules/project_hygiene.py:354` - `check_spec_api_signature_drift` is registered in the per-root `CHECKS` but never uses its root (only via the corpus-wide, cached `corpus_definitions`): every pass re-runs `spec_markdown_files(scope)`'s `rglob('*.md')` and re-parses every spec API block with identical results, about 0.58 s per pass and 2.9 s over this repository's five roots, the slowest check in the sweep. Duplicate output is suppressed only by `emit`'s `EMITTED` set; it belongs with the run-once `PROJECT_CHECKS`, or its spec scan needs caching.

### Sec1 (sampled): Secrets in source
- Mode: changed files since 83e59c0
- Inspected: all in-scope files, searched for token prefixes (`ghp_`, `github_pat_`, `sk-`, `AKIA`, `xox`), PEM headers, long quoted base64-like literals, and `password`/`secret`/`api_key`/`token` assignments to string literals. Matches were rule names and identifiers only. CI workflow uses no secrets (`persist-credentials: false`, `contents: read`).
- Hits: No hits

### Sec2 (sampled): Input validation at system boundaries
- Mode: changed files since 83e59c0
- Inspected: CLI parsing in `audit.py` (`scope`, `--package` checked as a bare name, `--extra-root` checked for containment), `changed.py` (`--base` refused when it starts with `-`, `repo_root`), `phaseb.py` (`--question` checked against the registry, `--batch-size` checked by `plan_batches`, `--depth`, `root`, `run_dir`, `--out`, `candidate_id` checked against the ledger); the `[tool.auditme]` roots table in `core.py:305-352`; plan/batch file reading in `phaseb/batches.py`.
- Hits:
  - `claude/skills/auditme/checks/phaseb.py:59` - `--depth` takes any `int` with no lower bound: `--depth -5` is accepted, runs as depth 0 (`range(-5)` is empty at `candidates.py:303`, `testmap.py:196`) and exits 0, and `plan` records the negative depth in `plan.json`, whereas `--batch-size` below 1 is refused.

### Sec3 (sampled): Command injection
- Mode: changed files since 83e59c0
- Inspected: every `subprocess` call in scope: `changed.py:55` (`git` argv list; the only user value, `--base`, is refused if it starts with `-`), `changed.py:135` (interpreter and `audit.py` path), `rules/project_hygiene.py:34, 87, 95, 198` (`ruff`/`uv` argv lists, fixed arguments plus a resolved path), `phaseb/docrefs.py:287` (`git ls-files -z`). All use argument lists, none uses `shell=True`. Test files run shipped scripts by fixed paths.
- Hits: No hits

### Sec4 (sampled): Path traversal
- Mode: changed files since 83e59c0
- Inspected: `audit.py` `--extra-root` (`path_inside` check) and `--package` (must be a bare name, not `.`/`..`); declared roots (`core.py:341`, `path_inside`); `phaseb.py` `ledger_path` (question validated against the registry before it names a file); `phaseb/docrefs.py:306-319` (document tokens normalised, `..` refused, then looked up in the `git ls-files` set). `--out` and `run_dir` are operator-chosen output directories, not paths joined to the project.
- Hits: No hits

### Sec5 (sampled): PII in logs
- Mode: changed files since 83e59c0
- Inspected: all in-scope files for `logging`/`logger` calls and for `print` of input text. No in-scope code configures or calls a logger (the matches are docstrings describing rules); output is the checker's own hit records and error messages about paths and refs.
- Hits: No hits

### T3 (sampled): Integration vs unit balance
- Mode: changed files since 83e59c0
- Inspected: the orchestrators `claude/skills/auditme/checks/audit.py` (`main()`), `changed.py` and `phaseb.py`, against the changed tests `claude/skills/auditme/tests/test_driver.py` (drives `audit.main()` on fixture projects, and runs the shipped entry point as a subprocess at line 468), `claude/skills/auditme/tests/test_changed.py` (runs `changed.main()` in temporary git repositories with real commits and branches) and `claude/skills/auditme/tests/phaseb/test_cli.py` (runs `phaseb.py` as a subprocess on a fixture project); the other changed tests under `claude/skills/auditme/tests/` and `tests/` were checked only for whether they cover an orchestrator.
- Hits: No hits

### D1 (sampled): Declared in pyproject
- Mode: changed files since 83e59c0
- Inspected: `pyproject.toml` (no `[project].dependencies`; `dev` group: hypothesis, pytest, ruff; `docs` group: mkdocs, mkdocs-material) and `uv.lock`, against the top-level imports of every tracked `.py` file (from `git ls-files '*.py'`, parsed with `ast`, stdlib removed by `sys.stdlib_module_names`). The only non-stdlib imports are the first-party `audit`, `auditme`, `changed`, `conftest` and `phaseb`, and the declared `hypothesis` and `pytest`.
- Hits: No hits

### D2 (sampled): Unused declarations
- Mode: changed files since 83e59c0
- Inspected: each declared dependency in `pyproject.toml` against the imports above, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `.github/workflows/docs.yml`, `mkdocs.yml` and the `entry_points.txt` of mkdocs-material 9.8.0 (the version in `uv.lock`). hypothesis and pytest are imported in the tests; ruff is run as a command (the `astral-sh/ruff-pre-commit` hooks, and `subprocess` in `claude/skills/auditme/checks/auditme/rules/project_hygiene.py`); mkdocs is run in `docs.yml`'s `run:` steps (`uv run mkdocs build`, `uv run mkdocs gh-deploy`); mkdocs-material registers `material` in `mkdocs.themes`, and `mkdocs.yml` sets `theme: name: material`, so the plugin carve-out applies.
- Hits: No hits

### D3 (sampled): Lockfile coherence
- Mode: changed files since 83e59c0
- Inspected: the sweep output `/tmp/audit-auditor.jsonl` (its rule ids, against `rule='lockfile-drift'` emitted by `check_lockfile` in `claude/skills/auditme/checks/auditme/rules/project_hygiene.py`). No `lockfile-drift` hit appears; the only lockfile-related lines are accepted hits of other rules (`non-alphabetical-literal`, `subprocess-without-memoisation`) on the `uv lock --check` call itself.
- Hits: No hits

### Doc3 (sampled): README.md and AGENTS.md consistent
- Mode: changed files since 83e59c0
- Inspected: `README.md` and `AGENTS.md` in full. Both describe the same components (the auditme checker, the pre-commit hooks, the Stop hook that runs before or at the end of a turn, the `/auditme-project-setup` skill, the `no-project-names` hook), the same installer behaviour (`bin/install-claude.sh` links into `~/.claude`, other rules from the agents repository), and give the same test command.
- Hits: No hits

### Spec review (changed specs)


Specs changed since 83e59c0, checked against the specdev skill's Spec template
and Validation criteria. Size and "Module location under `src/`" gaps are not
reported (review-1, decision D6).

## agents/specs/auditme-false-positives/spec.md

No gaps (no Settings section; the spec changes no configurable behaviour, so the omission is allowed).

## agents/specs/listed-phase-b-architecture-questions/spec.md

No gaps

## agents/specs/listed-phase-b-documentation-questions/spec.md

No gaps

## agents/specs/listed-phase-b-test-questions/spec.md

- gap: Settings includes setting name, type and default for each entry - `## Settings` (line 308): `--question` is given only its values (`T1` or `T2`), with no type and no default (the architecture and repeatable-phase-b specs give `str`, "none, required"); the section is prose rather than a table or list

## agents/specs/project-setup/spec.md

No gaps

## agents/specs/raises-section-resolution/spec.md

No gaps

## agents/specs/repeatable-phase-b/spec.md

No gaps

## Notes on what was checked

- Every template section (Module location, API, Error handling, Implementation, External dependencies; Settings where applicable) present and non-empty in each spec; header Version/Status/Date present.
- Each API section has at least one `python` code block with type-annotated signatures.
- Every relative link `](../...)` resolves; every other spec a spec mentions is linked at least once in it.
- Paths that do not exist in this repository are fixture names (`src/a.py`, `docs/guide.md`), files of the agents repository named as such (`git-conventions.md`, `rule-scope.md`, `claude/rules/python/testing.md`), or the renamed `bin/install-claude.py` recorded as history (1.10).

### Coverage (sampled)

New sites found by sampled questions (A9, A13, A14, A15, S4, P3, Sec2) are coverage, not drift; none is marked missed by review-1.

## Prior findings re-verified

Every finding in review-1's summary was resolved by `agents/tasks/audit-reviews/tasks-1.md` (all 13 tasks done) and is in summary.md's Recently resolved. No task in `agents/tasks/audit-reviews/` is incomplete.

## Decisions

### D1. Settle the thresholds this audit's reviewers could not

- **What is being decided:** whether to file one request in `claude/skills/auditme/requests.md` that settles, in the briefs, the thresholds this audit's reviewers reported as unsettled.
- **Background:** each brief tells its reviewer to report, not decide, a threshold the brief does not settle. On 2026-11-22 the thirteen thresholds from review-1 were settled. The briefs then met new cases:
  - **A1:**
    - a handler for the only `SubprocessError` subclass the call can raise (`TimeoutExpired` with a `timeout`, `CalledProcessError` with `check=True`);
    - a failure reported as an emitted hit or through a registry;
    - a call to the package's own translating wrapper.
  - **A4:** a decorator's raise that happens at import time.
  - **A17:** a reach past a non-empty subpackage's `__all__`. Today it is reported on the parent package.
  - **Doc4:**
    - a bullet with a bold title, then "(amendment 1.x, found <date>)";
    - a spec's step instruction or draft docstring for its own change;
    - a reproduced file block as a complete list;
    - a changed step order;
    - a Motivation paragraph describing the state before the change;
    - an acceptance criterion tagged with an amendment;
    - "X has a, b and c" as a complete list;
    - a missing `Raises:` in a spec's API block;
    - which candidate holds a drift when every candidate of a section has the same span.
  - **Doc5:**
    - a troubleshooting list as a list of exit conditions;
    - a JSON value shown in prose as an output example;
    - a list that begins "any failure:";
    - a claim narrower than the code;
    - an admonition list as complete;
    - a concepts row judged against the published manifest or the setup template.
- **What it affects:** the briefs' versions; a bump re-judges every candidate of that question. The next audit cannot start until the request is shipped or rejected.
- **Options:**
  - **File the request (recommended):** one entry listing each threshold. It is settled between audits, as on 2026-11-22.
  - **Leave them:** reviewers keep judging them case by case, and the same question can get different verdicts in different batches.

### D2. What a check does when `uv` or `ruff` cannot run

- **What is being decided:** the behaviour behind F3.
- **Background:** `check_lockfile` and `check_ruff_version` return silently when `uv` or `ruff` is missing. `check_ruff` reports `ruff not installed` as a hit. Review-1's D2 (2026-11-21) made the checker report an unreadable file as a hit rather than skip it silently.
- **What it affects:** the three call sites in F3, the gate's result on a machine without `uv` or `ruff`, and the A1 verdicts on them.
- **Options:**
  - **Report it as a hit (recommended):** both checks emit a hit naming the missing tool, as `check_ruff` does. Then A1 counts an emitted hit as the check's translation, which is one of D1's thresholds. A machine without `uv` fails the gate on a project with a `uv.lock`, which is the behaviour `check_ruff` already has.
  - **Stay silent:** accept the three call sites with scoped markers, giving the reason that a missing tool is reported elsewhere. A missing `uv` then passes the gate unnoticed.

## Answers

Answered on the review page on 2026-11-22. Every item took the recommended option, with no comments.

| Item | Answer |
|---|---|
| F1 | Fix |
| F2 | Dismiss (by design, review-1 D2; dismissed in the A1 ledger) |
| F3 | Fix (as D2) |
| F4 | Fix |
| F5 | Fix |
| F6 | Fix |
| F7 | Fix |
| F8 | Fix |
| F9 | Fix |
| F10 | Fix |
| F11 | Fix |
| F12 | Fix |
| F13 | Fix |
| F14 | Fix |
| D1 | File the request |
| D2 | Report it as a hit |
