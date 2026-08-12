---
name: auditme
description: Perform a structured code, spec and documentation audit with findings and recommendations
when_to_use: |
    Use this skill whenever the user mentions:
        - audit the code
        - code audit
        - full code review
        - review the codebase
        - audit the codebase
        - audit the docs

allowed_tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion, Skill]
---

# auditme

Invoke as:
    /auditme [scope] [--category <category>]

`[scope]` is optional. With no argument, audit the full project (specs, source, docs). With a path or spec name, restrict the scope.

`--category` is a debugging knob - it restricts Phase B to one of `standards`, `architecture`, `performance`, `security`, `testing`, `dependencies`, `documentation`. **Do not use `--category` in the normal converge-in-one-pass workflow.** Running category-scoped audits serially is the dominant cause of historical "the audit keeps finding new things": each category is a different lens, and switching lenses surfaces issues that were always present. The default invocation (no flag) runs every category in one pass and is the only invocation that can converge.

## Convergence is the success criterion

Two consecutive audit runs on unchanged code MUST produce the same findings. The audit is designed to converge in **one** pass. If run N+1 surfaces findings that run N did not, one of these failures has happened:

1. **Script grew between runs.** A new `check_*` was added to `checks/audit.py`, so historical debt that was previously invisible suddenly appears. Cure: the script-coverage backlog (see `summary.md`) must be drained into real check functions BEFORE any audit cycle starts. The script does not change during an audit. New patterns surfaced mid-audit are deferred to the next skill update, not the next audit cycle.
2. **Phase B was non-deterministic.** A reviewer agent applied different judgment than last round on the same files. Cure: Phase B fan-out is per-question, not per-file. One agent owns one question across all files in scope, so a single judgment threshold applies per predicate.
3. **Category-scoped runs.** A previous run used `--category X` and missed everything outside X. Cure: the canonical audit always runs every category. Use `--category` only for re-checking a single rule family during fix verification.
4. **Predicate drift.** A Phase B question's "should-have-caught" set quietly grew between cycles (e.g., A2 originally meant "missing `OSError`", later expanded to also mean "missing `ParserError`"). Cure: every predicate has a fixed enumeration encoded in this file. Expanding a predicate is a skill change, never a per-cycle adjustment.
5. **Rule conflict.** Fixing a finding under rule X created a finding under rule Y on the same line (e.g., moving `mkdir` from a callback into `__init__` swaps `A18` for `constructor-disk-io`). Cure: see [Rule conflict resolution](#rule-conflict-resolution).

Convergence is non-negotiable. "We found more this time" is the failure signal, not progress.

## Workflow

### 1. Scope

- **Full audit** (no argument): `agents/specs/`, `src/`, `docs/`, `AGENTS.md`, `README.md`
- **Module** (file path): that file, its tests, any spec referencing it
- **Spec** (slug): `agents/specs/<slug>/spec.md` and its implementation
- **Docs**: user docs in `docs/`

### 2. Gather context

Run these in parallel:

1. Read `AGENTS.md` and `README.md`
2. Read `agents/specs/index.md` if present
3. Read coding-standards rule files referenced by AGENTS.md
4. Read `agents/audit-reviews/summary.md` if present. Note unresolved findings - step 6 re-verifies them.
5. Grep for `- [ ]` in `agents/tasks/audit-reviews/*.md`; read only files with incomplete items.

### 3. Mechanical sweep (scripted)

**Precondition: backlog drained.** Before running, read `summary.md`'s `## Script coverage backlog` section. If any entry is marked `Status: queued`, the audit is not allowed to start. Either:

1. Promote the queued predicate to a real `check_*` function in `checks/audit.py` (and update the backlog entry to `shipped-in-script-vN`), or
2. Reject it explicitly: edit `summary.md` to mark it `rejected: <reason>` and remove it from the backlog.

This precondition is the cure for failure mode 1. Without it, every audit cycle ships another "next time we'll add this check" and convergence is impossible.

Then run the shipped audit script:

```bash
python3 ~/.claude/skills/auditme/checks/audit.py <project-root> [--package <pkg>]
```

`<project-root>` is the directory containing `src/` and `agents/`. `--package` defaults to the single directory under `src/`.

The script outputs one JSON object per line (JSONL). Each line is a hit.

Schema:

```json
{
  "rule": "<rule-family>",
  "variant": "<syntactic variant>",
  "path": "src/foo/bar.py",
  "line": 42,
  "evidence": "source snippet",
  "accepted": false,
  "accepted_reason": null
}
```

**Rules:**

1. Save the full JSONL output to `/tmp/audit-<project>.jsonl`.
2. Every hit with `accepted: false` MUST appear in the review file as a finding (grouped by rule, enumerated individually with `path:line`).
3. Hits with `accepted: true` are dismissed with their `accepted_reason`. Do not re-litigate them.
4. You may NOT filter, sample, or dismiss `accepted: false` hits. "Pre-existing", "project norm", "seems intentional" are NOT acceptable dismissals. To accept a pattern:
   - one site: inline `# auditme: accept <reason>` comment on the hit line or the line above
   - many sites of the same class: AGENTS.md table entry, then re-run the script
5. **Do not extend the script during the audit.** If Phase B surfaces a new mechanically-detectable pattern, write it down in the review's "Script coverage notes" but do not add it to `checks/audit.py` until the current task list ships and the next audit on unchanged code shows zero mechanical delta. This is the cure for the perpetual "the audit keeps finding new things" loop: the script stays still, the next run is clean, then the script grows.

The full set of rules the script catches is documented in the checker itself -
read the docstring of each `check_*` function for the predicate it encodes.
`checks/audit.py` is only the entry point; the checks live in
`checks/auditme/rules/`, one module per family of defect (`error_handling.py`,
`duplication.py`, `state_and_effects.py`, `imports_and_surfaces.py`,
`style_and_naming.py`, `project_hygiene.py`), with the shared helpers in
`checks/auditme/core.py` and the run order in `checks/auditme/registry.py`.

**`CHECKS`'s order is the emission order, and therefore part of the output.**
Adding an entry is free; moving an existing one reorders every subsequent hit
and will read as a diff in the next audit even though nothing was found
differently.

### 4. Interpretive review (per-question fan-out)

Phase B is **not** free-form reading. It is a fixed checklist applied across every file in scope. Two audit runs of the same checklist over the same code must produce the same finding set.

**Fan out by question, not by file.** Spawn one subagent per Phase B question (or per small bundle of related questions within one category). Each subagent owns ONE predicate across ALL files in scope. The subagent's task: "apply predicate Q across these files, return the list of `path:line` instances."

This is the cure for failure mode 2. When 24 architecture questions are split across reviewers by file, each reviewer applies a slightly different judgment threshold to its slice of the corpus, and a different threshold to a different question, multiplying variance. With per-question fan-out, one reviewer applies one threshold to one predicate, eliminating cross-question and cross-file judgment drift.

Rules for reviewers:

- Apply ONE predicate to ALL files. Do not range across questions; do not skip files.
- The predicate's enumeration in this file is exhaustive. If the predicate says "covers `OSError, PermissionError, FileNotFoundError`", do not also flag missing `ValueError` - that is a different predicate and a different reviewer's job.
- Output one row per hit: `path:line - one-line description`. No prose.
- "No hits" is a valid result; record it explicitly so the orchestrator can confirm the predicate was actually run.
- **Do not invent findings.** If you observe something no predicate asks about, drop it. The skill - not the audit - is where new predicates are added. The previous "Out-of-checklist observations" mechanism is removed because it created perpetual discovery loops; new predicates land via skill update between cycles, never mid-cycle.
- Do not self-edit. Low-severity findings still go in the review.

### 5. Spec review

For each spec in scope, check it against the validation criteria and spec template in `agents/skills/specdev/SKILL.md`. Record gaps as findings. Skip if no specs in scope.

### 6. Re-verify prior findings

For each unresolved finding in `summary.md`, grep or read to confirm: still present, or now resolved. If resolved, mark closed in `summary.md` and (if applicable) mark the corresponding task file done.

For each incomplete task in `agents/tasks/audit-reviews/*.md`, verify against source: actually incomplete (re-flag in the review) or shipped (mark done in the task file).

### 7. Completion gate

Before writing the review file, confirm:

- [ ] `summary.md` script-coverage backlog was empty at audit start (every queued item shipped or rejected)
- [ ] `checks/audit.py` was executed and its full JSONL output saved
- [ ] Every `accepted: false` hit appears in the review (no sampling, no silent dismissals)
- [ ] Phase B ran with per-question fan-out covering EVERY question in EVERY category (`--category` was NOT used unless the user explicitly asked for a partial verification)
- [ ] Every Phase B subagent returned an explicit hit list (or "no hits") - no question silently skipped
- [ ] Every unresolved `summary.md` finding was re-verified
- [ ] Every incomplete task file was re-verified against source
- [ ] No new check was added to `checks/audit.py` during this audit (script-coverage delta is zero)
- [ ] No Phase B predicate had its enumeration expanded during this audit

If any is no, finish it before writing the review.

### 8. Write the review file

`agents/audit-reviews/review-N.md`, using the [Review template](#review-template). N is the next available integer.

Update `agents/audit-reviews/index.md` (create if missing).

### 8a. Update the summary

Rewrite `agents/audit-reviews/summary.md` using the [Summary template](#summary-template):

1. Remove findings confirmed resolved in this review
2. Add findings from review-N
3. Update metadata (last review number, date, total count)

### 8b. Refresh after task completion

After the review's task list has been shipped (tasks-N all done), update `summary.md` again: move resolved findings from Unresolved to Recently resolved.

### 9. Act on findings

If there are findings: `/taskdev agents/audit-reviews/review-N.md`. If none: tell the user where the review was written.

### 10. Version control

1. `git status`
2. If there are uncommitted changes, ask the user to commit them first
3. Stage: `git add agents/audit-reviews/review-N.md agents/audit-reviews/summary.md agents/audit-reviews/index.md` plus any task files you marked done
4. Ask the user if they would like to commit
5. Commit message: `auditme: add review-N`
6. Do not push unless asked

## Acceptance mechanism

The script treats a hit as `accepted: true` only when one of these exists:

1. **Inline comment** on the hit line or the preceding line, optionally scoped to a single rule:
   - `# auditme: accept[<rule-name>] <reason>` - answers for that rule only
   - `# auditme: accept <reason>` - answers for every rule that fires on the line
2. **AGENTS.md table row** pairing the importer and imported module in backticks (for in-function imports). The importer module path is computed without a leading `src.` prefix (e.g. `featmo.config.structures`, not `src.featmo.config.structures`); AGENTS.md rows should use the same form.

Nothing else acts as acceptance - not a decision note under `agents/audit-reviews/`, not a prior review that "agreed" the pattern is fine, not an assumption about HF / sklearn / PEP conventions.

### Scope your markers to a rule

**Write new markers in the scoped form.** An unscoped marker accepts every rule
that fires on its line, including rules that did not exist when it was written -
so a decision weighed about one predicate silently excuses a different one later.
This is not hypothetical: on the litrev project, a marker reasoning entirely
about traceback diagnosability (written for
`logger-exception-graceful-degradation`) was found pre-accepting the newly added
`failure-as-absence` check on the same line, hiding a defect three prior reviews
had flagged by hand. Scoping the marker turned it back into a real finding.

It is the same distinction as `# noqa` versus `# noqa: E501`, and it fails the
same way: silently, and only when the tooling gets smarter.

The unscoped form is retained so no existing marker needs migrating, and a
project with many of them does not have to convert them in one pass. Convert
opportunistically - when a hit turns out to be accepted by a marker whose reason
plainly addresses a different question, scope that marker rather than widening
the reason. Adding a check is the moment this surfaces, so check the new check's
accepted hits before concluding the catch-up surface is empty.

## Phase B checklist

The questions below are the entire Phase B surface. Each question is asked of every file in scope. The answer is `none` (no instances) or a list of `path:line` locations with a one-line description.

Questions are organised by category. The `--category` flag restricts which sections run; if absent, all sections run.

### Architecture (A)

Each question is a deterministic predicate. The reviewer reads the file end-to-end and answers each question.

- **A1. External call envelope.** For every call to a third-party library that can do I/O (HTTP, MLflow, S3, database, subprocess, file system, HuggingFace `from_pretrained` / `save_pretrained` / `download_artifacts`, pandas `read_*` / `to_*`, torch `load` / `save`): is the call inside a `try/except` that translates the exception to the package's domain `*Error` class? Flag any external-IO call that lets a third-party exception escape.
- **A2. Except tuple coverage.** For every `try/except` whose body touches disk or pandas/json parsers: does the except tuple include EVERY exception in the locked set below? Locked set: `OSError` (covers `PermissionError`, `FileNotFoundError`, `IsADirectoryError`); `UnicodeDecodeError` if the body decodes text; `pandas.errors.ParserError` if the body calls `pd.read_*`; `json.JSONDecodeError` if the body calls `json.load*`; `gzip.BadGzipFile` if the body opens `.gz`. Bare `Exception` also satisfies. Flag any tuple missing one of the above when the body matches that branch. Do not extend this set during an audit; expansion is a skill change.
- **A3. Domain-error layering.** For every `raise` statement: is the raised type the package's domain `*Error` (or a `*Error` from a strictly lower layer)? Flag stdlib `ValueError`/`RuntimeError`/`KeyError`/`TypeError` raised in a package that defines its own `*Error` class.
- **A4. Docstring `Raises` accuracy.** For every function whose docstring has a `Raises:` section: does the body actually raise each declared exception type, and only those? Flag mismatches.
- **A5. Two sources of truth.** For every state value that has both a config field and a method parameter (or two attributes that should always agree): is the precedence rule documented and enforced? Flag silent precedence (whichever path wins by coincidence of execution order).
- **A6. Stage method dual-path.** For every method on a pipeline-stage class: does it both return a value AND mutate `self.<attr>` for the same field? Flag tuple-returning methods that also self-mutate.
- **A7. Constructor purity.** For every `__init__`: does it perform I/O (open, mkdir, read_text, subprocess, network, expensive compute)? Does it mutate any of its arguments? Flag both.
- **A8. Late dataclass mutation.** For every `@dataclass` instance constructed inside a function: is it mutated after construction (`x = Foo(...); x.field = ...`)? Flag late mutations - they bypass `__post_init__` and any `frozen=True` would have caught them.
- **A9. Pure-named function side effects.** For every function whose name starts with a pure prefix (`get_`, `resolve_`, `find_`, `compute_`, `build_`, `load_`, `parse_`, `is_`, `has_`, `validate_`, `count_`, `check_`, `allocate_`): does the body call I/O / subprocess / `datetime.now()` / network? Flag naming-vs-implementation gaps.
- **A10. Predicate semantics.** For every predicate function (`is_X`, `has_X`, `should_X`): does the body answer exactly the question the name asks, with no hidden conjuncts? Flag conflated predicates (e.g. `side_channel_active` returning `enabled and imputation != 'median'`).
- **A11. Exhaustion via assert_never.** For every `if/elif/else` chain over a `typing.Literal` or enum: is the unreachable branch handled with `typing.assert_never`? Flag chains that end in `raise <SomeError>(...)` instead - the type-checker cannot verify exhaustion.
- **A12. assert misuse.** For every `assert` outside test files: is it a developer-only invariant that `python -O` may safely remove? Flag asserts used as runtime validation; those should be `if not X: raise DomainError(...)`.
- **A13. Same value to multiple structural slots.** For every constructor call that takes positional / keyword arguments for distinguishable slots (`train`, `val`, `test`): is the same value passed to 2+ slots? Flag (e.g. `DatasetSplits(train=ds, val=ds, test=ds)`) and require either an explicit factory or a docstring.
- **A14. Repeated computation per request.** For every helper function whose value is a property of the project state (HEAD SHA, primary metric, resolved config): is it called more than twice in a single request flow? Flag candidates for memoisation / single-resolution.
- **A15. Duplicate constructor / serialisation logic.** For every class whose constructor is called from 2+ sites with substantially the same field set: is the construction factored into one helper? Flag duplicated assembly that would silently drift on field addition.
- **A16. CLI entry envelope.** For every top-level `run_*` function in `cli/*.py` that returns `int` or takes a cappa-typed parameter: does the body's `try/except` cover every `raise` in the function (including validation `raise`s before the try)? Flag `raise` statements outside the envelope.
- **A17. Public-surface drift.** For every `__init__.py` with `__all__`: is every symbol in `__all__` used outside the package? For every empty `__init__.py`: do consumers reach into private submodules? Flag bypasses of the canonical owning module.
- **A18. Hot-path setup.** For every callback method (`on_step`, `on_log`, `on_evaluate`, `on_batch_*`): does it perform setup (mkdir, file open) that should live in `__init__`? Flag per-event side effects.
- **A19. Wrong logger level for broad-except.** For every `except Exception` / `except BaseException`: does the body use `logger.exception` (not `warning`/`error`/`info`/`debug`)? And conversely, is `logger.exception` reserved for unexpected failures, not expected graceful-degradation paths?
- **A20. Mutable module-level singleton.** For every module-level mutable container that is imported by name from another module: is it immutable per the locked set below? Locked set: `dict` -> must be `types.MappingProxyType(...)`; `set` -> must be `frozenset(...)`; `list` -> must be `tuple(...)`. The predicate is "imported elsewhere" - verify with grep for `from <module> import <name>` before flagging. Do not extend this predicate to private (non-imported) module-level containers; that is a different rule.
- **A21. Lazy init race.** For every `if X is None: X = ...` pattern at module scope (or in a module-level helper): is the assignment thread-safe under concurrent invocation? Flag idempotent-but-racy patterns in code paths that may be called concurrently (Optuna trials, multiprocessing).
- **A22. Fall-through after partial handling.** For every `if/else` chain whose branches partly raise and partly return: is there a fall-through path where a raised-and-translated error in the first branch silently retries in the second? Flag with-block-or-elif-fall-through patterns (e.g. `if gz: ... except: raise` then code that re-runs as if `gz=False`).
- **A23. Discarded multi-return.** For every call to a function that returns a tuple/dataclass: are all returned components used or explicitly named (`a, _ = f()`)? Flag silent discard of secondary returns that signal hidden state dependencies.
- **A24. Identity of subprocess / shell-out calls.** For every `subprocess.run` / `git`-shelling-out helper: is its result memoised when the source is invariant within a request? Flag repeated subprocess invocations per request.

### Standards (S)

- **S1. Type annotations on every signature.** Parameter and return annotations everywhere. Flag bare untyped signatures. **Scope is locked and asymmetric.** Enumerate every missing annotation individually, with `path:line`, for non-test source only. For files under a `tests/` directory, do NOT enumerate: report a single count line (missing parameter annotations, missing return annotations, modules affected, modules fully annotated). Reviews 3, 4 and 5 each chose differently here - review-3 skipped tests, review-4 enumerated 1916 of them, review-5 counted - and the swing is the single largest source of apparent finding-count movement between cycles. If the project records a standing exemption for test annotations (as an AGENTS.md note that `ANN` is not enabled for tests), the count also serves as a drift check on that note's own figures; a discrepancy is a documentation finding under Doc1, not an S1 finding.
- **S2. PascalCase / UPPER_SNAKE / lower_snake.** Names match project convention. Flag inconsistencies.
- **S3. TYPE_CHECKING block placement.** Same idiom as the rest of the tree (top-of-file, after imports, etc.).
- **S4. Project-specific rule files.** Any rule referenced by AGENTS.md not enforced by the script. Read the rule file; check the file under review.

### Performance (P)

- **P1. O(n^2) on real-size inputs.** Nested loops over project-data-shaped collections.
- **P2. Blocking I/O in hot paths.** Reads / writes inside training loops, request handlers, callbacks.
- **P3. Repeated expensive computation per request.** Same value derived more than once. (Overlaps A14 / A24.)

### Security (Sec)

- **Sec1. Secrets in source.** API keys, passwords, tokens.
- **Sec2. Input validation at system boundaries.** CLI args, HTTP bodies, file paths from user.
- **Sec3. Command injection.** Unsanitised input passed to `subprocess` or shell-execution helpers.
- **Sec4. Path traversal.** User-supplied paths joined to project paths without containment.
- **Sec5. PII in logs.** Raw text inputs at INFO level or above.

### Testing (T)

Assess by reading test files - do not run the suite.

- **T1. Test coverage of branchy logic.** Every function with `if`/`try`/`except`/state transitions has at least one test case.
- **T2. Property-based tests.** Domains that are well-defined (data shapes, config combinations) have hypothesis tests.
- **T3. Integration vs unit balance.** Pipeline orchestrators have at least one end-to-end test.

### Dependencies (D)

- **D1. Declared in pyproject.** Every imported third-party module is declared.
- **D2. Unused declarations.** Every declared dependency is imported somewhere.
- **D3. Lockfile coherence.** Already script-checked; flag if the script's lockfile-drift hit appears.

### Documentation (Doc)

- **Doc1. AGENTS.md project structure** matches actual directory layout.
- **Doc2. AGENTS.md tools and libraries list** is current.
- **Doc3. README.md and AGENTS.md** consistent.
- **Doc4. Specs match implementation.** Drift between `agents/specs/` and `src/`.
- **Doc5. User docs match implementation.** Drift between `docs/` and `src/`.

## Review template

```markdown
# Audit Review N

**Date:** YYYY-MM-DD
**Scope:** <"full" or specific modules/specs>
**Script output:** /tmp/audit-<project>.jsonl (N hits, M accepted, K unaccepted)
**Convergence note:** <"clean - script unchanged since review-(N-1)" OR "script extended since review-(N-1) by these checks: [list]; expect mechanical delta">

## Summary

<2-3 sentences. Mention script hit counts by rule and the interpretive findings count.>

## Mechanical findings (from checks/audit.py)

Group by rule. Enumerate every `accepted: false` hit. Do NOT sample.

### Rule: <rule-family> - <variant or summary>

- **Severity:** high / medium / low
- **Instance count:** N
- **Locations:**
  - `path:line` - evidence snippet
  - `path:line` - evidence snippet
  - ... (every one)
- **Recommendation:** <fix or add `# auditme: accept <reason>`>

## Phase B per-question results

For each Phase B question (subagent fan-out), one block. Include EVERY question across EVERY category that was run, including questions with zero hits.

### A2: Except tuple coverage

- **Subagent ran on:** all 103 src files
- **Hits:**
  - `path:line` - `except UnicodeDecodeError` body calls `read_text`; `OSError` missing
  - `path:line` - ...
- **No-hit confirmation:** N files inspected, M had no matching `try/except`

(Repeat for every question - A1..A24, S1..S4, etc.)

## Phase B findings (consolidated)

For every hit above, surface as a finding:

### Finding: <title>

- **Category:** A / S / P / Sec / T / D / Doc
- **Question:** A2 / A9 / etc.
- **Severity:** high / medium / low
- **Location:** `path:line`
- **Description:** <what the issue is>
- **Recommendation:** <concrete action>

## Files reviewed (Phase B)

Every file the checklist was applied to.

- `src/example/module.py` - questions A1-A24, S1-S4
- ...

## Prior findings re-verified

From summary.md's unresolved list:

- <title> - resolved at `path:line` / still present at `path:line`

## Recommendations

Prioritised by severity.

## Script coverage notes

Phase B has no script-coverage notes section in this template by design. The previous mechanism (note candidate predicates per audit) created a perpetual queue. New predicates are now added by editing this skill between cycles, not by leaving notes for future audits. If during this audit you genuinely identified a missing predicate, raise it with the user as a skill-update request after the audit completes - do not add it to the review.
```

## Summary template

```markdown
# Audit Summary

**Last updated:** YYYY-MM-DD
**Last review:** review-N
**Total reviews conducted:** N
**Last script run hit count:** K (J accepted)
**Script version:** <digest of the whole checker:

```bash
find -L ~/.claude/skills/auditme/checks -name '*.py' | sort | xargs cat | shasum -a 256
```

A single-file hash no longer identifies it: `checks/audit.py` is only the entry
point and the checks live in `checks/auditme/`, so hashing that one file would
report "script unchanged" after a check was edited. The command above follows
the symlink, needs no git, and gives the same digest wherever it is run from.>

## Unresolved findings

Findings from prior reviews not yet addressed.

### <title>

- **Rule or category:** <script rule family / Phase B question id>
- **Severity:** high / medium / low
- **Location:** `path:line` or project-wide
- **First raised:** review-N (YYYY-MM-DD)
- **Description:** <what the issue is>
- **Recommendation:** <concrete action>

## Recently resolved

Findings confirmed fixed in the most recent 3 reviews.

| Finding | Severity | Raised in | Resolved in |
|---------|----------|-----------|-------------|
| <title> | medium | review-5 | review-8 |

## Recurring patterns

Patterns that have appeared across multiple reviews even when individual instances were fixed. Candidates for AGENTS.md entries, pre-commit rules, or script extensions (queued for AFTER the current audit-fix loop).

- <pattern> (reviews N, M, P)

## Script coverage backlog

This section MUST be empty when an audit starts (see [Mechanical sweep precondition](#3-mechanical-sweep-scripted)). Entries here exist only between a skill-update request and the corresponding `audit.py` change. Either ship or reject within the same skill-update session - never carry state across audit cycles.

- (empty in steady state)
```

## Extending the script (skill-update, not audit)

Adding a check is a skill change. It happens between audit cycles, with no in-flight audit, and no queued backlog deferred to "next time".

Process:

1. User raises a candidate predicate (or this skill is updated to add a new Phase B question).
2. Implement the predicate as a `check_*` function in `checks/audit.py` immediately.
3. Run the script on the project. The result is the catch-up surface. Land fixes (or accept markers) for everything it returns.
4. After fixes, run the audit normally. Convergence is restored.

The previous "queue, defer, audit, defer again" rhythm was the dominant cause of perpetual cycles: every cycle promoted a new queued item AND surfaced new Phase B items, so backlog never reached zero. The new rule is **drain immediately or reject explicitly**. There is no permitted state where the backlog is non-empty and an audit is starting.

### Refining a predicate (narrowing, not expanding)

Refinements are different from extensions. An extension grows a predicate's "should-have-caught" set and is forbidden mid-audit (predicate drift, failure mode 4). A refinement narrows the set by carving out a sanctioned sub-pattern that should not fire - the predicate's enumeration in this file is updated to name the carve-out, and the script implements the skip.

A refinement is a skill change too: same process as above (drain immediately, then run the audit). Each refinement is documented in the predicate's docstring inside `checks/audit.py` so future readers see why a sub-pattern is skipped.

Documented refinements:

- **`except-interpolation` (review-36):** the predicate skips interpolation expressions of the form `type(<bound>).__name__` / `__qualname__` and `<bound>.__class__.__name__` / `__qualname__`. The class-name string is a categorical hint, not a lossy duplication of the message body. See `_is_categorical_class_name_expr` in `checks/audit.py`.
- **`empty-init-while-siblings-export` (review-36):** the predicate is file-level. The accept-marker scan walks every line in the file rather than just the docstring opener, so a docstring-only `__init__.py` can be accepted by adding a comment-only `# auditme: accept <reason>` line anywhere in the file.

## Rule conflict resolution

A rule conflict exists when fixing a finding under rule X creates a finding under rule Y on the same code (e.g., review-34: `A18 callbacks-open-file-per-event` says move `mkdir` from `on_log` into `__init__`; `constructor-disk-io` then fires on the new location).

When a conflict is detected:

1. Document it in this section (below) with the two rule names.
2. Pick the winning rule and the losing rule. The winner is the one whose fix the user actually wants.
3. The losing rule's hit at the conflict site is auto-`# auditme: accept`-ed with reason `conflict-with-<winning-rule>`.
4. Future audits dismiss the loser's hit at that site without re-litigation.

Without this mechanism, audits ping-pong between the two rules forever - moving the line back and forth produces "new" findings each cycle.

### Documented conflicts

| Winner | Loser | Site pattern | Reason |
|--------|-------|--------------|--------|
| `A18` callbacks hot-path setup | `constructor-disk-io` | callback class `__init__` performing `mkdir` of a path that the callback writes to | one-time mkdir per Trainer instance is preferable to per-event mkdir; loser auto-accepted |

## Severity guide

- **High:** security vulnerabilities, crashes, data loss, spec contradicts implementation on critical behaviour
- **Medium:** standards violations with real maintenance cost (widespread duplication, broken error reporting), missing tests for complex logic, docs out of date
- **Low:** local style nitpicks, minor doc gaps, suggestions for clarity

## Why this skill is structured this way

Earlier iterations relied on Claude to run greps and AST walks by hand, which agents reliably skipped, sampled, or silently filtered. The script fixed Phase A: agents cannot fake what a subprocess outputs. Acceptance is explicit (inline comment or AGENTS.md), not a decision-note argument.

A first Phase B fix replaced "report every concern" with a fixed checklist; that closed one source of variance but left four others that drove the feathf project to 34 cycles before convergence:

1. **Per-file fan-out** spread judgment thresholds across reviewers (one agent's "yes" was another agent's "no" on the same predicate). Cured by per-question fan-out.
2. **Category-restricted runs** meant each lens found new things in code that prior lenses had ignored. Cured by always running every category in one pass.
3. **Script-coverage backlog** as a perpetual queue meant every cycle shipped one new check (catch-up debt) AND one new queued item (next cycle's debt). Cured by draining or rejecting the backlog before any audit cycle starts.
4. **Predicate drift** silently expanded "should-have-caught" sets between cycles. Cured by locking each predicate's enumeration in this file.
5. **Rule conflicts** (fix under rule X triggers rule Y) ping-ponged forever. Cured by named-winner conflict resolution with auto-accept on the loser.

With these five fixes, a single audit on unchanged code produces the same finding set as the next audit on unchanged code. The audit converges in one pass, not 34.
