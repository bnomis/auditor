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

`--category` restricts the interpretive review (step 4) to one of: `standards`, `architecture`, `performance`, `security`, `testing`, `dependencies`, `documentation`. The mechanical sweep (step 3) always runs in full.

## Convergence is the success criterion

Two consecutive audit runs on unchanged code MUST produce the same findings. If run N+1 surfaces findings that run N did not, one of two failures has happened:

1. **Script grew between runs.** A new check was added to `checks/audit.py`, so a class of historical debt that was previously invisible suddenly appears. This looks like "the audit found new issues" but it is the script catching up. Cure: the script does NOT change during an active audit-fix loop. Add new checks only after the current task list has shipped and the next audit is clean.
2. **Phase B was non-deterministic.** A reviewer agent applied different judgment than last round on the same files. Cure: Phase B is a fixed checklist, not free-form reading. Two reviewers running the checklist on the same file must produce the same finding set.

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

Run the shipped audit script:

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

The full set of rules the script catches is documented in `checks/audit.py` itself - read the docstring of each `check_*` function for the predicate it encodes.

### 4. Interpretive review (per-file checklist)

Phase B is **not** free-form reading. It is a fixed checklist applied to every file in scope. Two reviewers running this checklist on the same file must converge on the same finding set.

For each file in scope, divide files across multiple agents (parallel) and have each agent answer **every** question on the [Phase B checklist](#phase-b-checklist) for **every** assigned file. The output is structured: per file, per question, an explicit yes/no and (if yes) a list of locations.

Rules for reviewers:

- Answer EVERY question for EVERY file. Skipping a question is a Phase B failure.
- "No issue" is a valid answer; record it explicitly. The audit needs to see the question was asked.
- Findings are grouped by question, not invented from scratch. If you observe something the checklist does not ask about, add it to "Out-of-checklist observations" at the end of the file's report - this is the seed for a future checklist item, not a finding.
- Do not self-edit. Low-severity / stylistic findings still go in the review.
- Do not read with the goal of "finding concerns". Read with the goal of "answering the checklist".

### 5. Spec review

For each spec in scope, check it against the validation criteria and spec template in `agents/skills/specdev/SKILL.md`. Record gaps as findings. Skip if no specs in scope.

### 6. Re-verify prior findings

For each unresolved finding in `summary.md`, grep or read to confirm: still present, or now resolved. If resolved, mark closed in `summary.md` and (if applicable) mark the corresponding task file done.

For each incomplete task in `agents/tasks/audit-reviews/*.md`, verify against source: actually incomplete (re-flag in the review) or shipped (mark done in the task file).

### 7. Completion gate

Before writing the review file, confirm:

- [ ] `checks/audit.py` was executed and its full JSONL output saved
- [ ] Every `accepted: false` hit appears in the review (no sampling, no silent dismissals)
- [ ] Phase B answered EVERY checklist question for EVERY file in scope (the per-file structured table is in the review)
- [ ] Every unresolved summary.md finding was re-verified
- [ ] Every incomplete task file was re-verified against source
- [ ] No new check was added to `checks/audit.py` during this audit (script-coverage delta is zero unless explicitly authorised)

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

1. **Inline comment** on the hit line or the preceding line: `# auditme: accept <reason>`
2. **AGENTS.md table row** pairing the importer and imported module in backticks (for in-function imports). The importer module path is computed without a leading `src.` prefix (e.g. `featmo.config.structures`, not `src.featmo.config.structures`); AGENTS.md rows should use the same form.

Nothing else acts as acceptance - not a decision note under `agents/audit-reviews/`, not a prior review that "agreed" the pattern is fine, not an assumption about HF / sklearn / PEP conventions.

## Phase B checklist

The questions below are the entire Phase B surface. Each question is asked of every file in scope. The answer is `none` (no instances) or a list of `path:line` locations with a one-line description.

Questions are organised by category. The `--category` flag restricts which sections run; if absent, all sections run.

### Architecture (A)

Each question is a deterministic predicate. The reviewer reads the file end-to-end and answers each question.

- **A1. External call envelope.** For every call to a third-party library that can do I/O (HTTP, MLflow, S3, database, subprocess, file system, HuggingFace `from_pretrained` / `save_pretrained` / `download_artifacts`, pandas `read_*` / `to_*`, torch `load` / `save`): is the call inside a `try/except` that translates the exception to the package's domain `*Error` class? Flag any external-IO call that lets a third-party exception escape.
- **A2. Except tuple coverage.** For every `try/except` whose body touches disk: does the except tuple include `OSError` (or the `Exception` base)? Flag narrow except tuples (e.g. `except UnicodeDecodeError`) that miss disk-level failures.
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
- **A20. Mutable module-level singleton.** For every module-level mutable container (`dict`, `list`, `set`) that is consumed by name from outside: is it wrapped in `types.MappingProxyType` / `frozenset` / `tuple`? Flag mutable globals that callers can rebind.
- **A21. Lazy init race.** For every `if X is None: X = ...` pattern at module scope (or in a module-level helper): is the assignment thread-safe under concurrent invocation? Flag idempotent-but-racy patterns in code paths that may be called concurrently (Optuna trials, multiprocessing).
- **A22. Fall-through after partial handling.** For every `if/else` chain whose branches partly raise and partly return: is there a fall-through path where a raised-and-translated error in the first branch silently retries in the second? Flag with-block-or-elif-fall-through patterns (e.g. `if gz: ... except: raise` then code that re-runs as if `gz=False`).
- **A23. Discarded multi-return.** For every call to a function that returns a tuple/dataclass: are all returned components used or explicitly named (`a, _ = f()`)? Flag silent discard of secondary returns that signal hidden state dependencies.
- **A24. Identity of subprocess / shell-out calls.** For every `subprocess.run` / `git`-shelling-out helper: is its result memoised when the source is invariant within a request? Flag repeated subprocess invocations per request.

### Standards (S)

- **S1. Type annotations on every signature.** Parameter and return annotations everywhere. Flag bare untyped signatures.
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

## Phase B per-file answers

For each file reviewed, the structured checklist response:

### `src/example/module.py`

- A1 External call envelope: none
- A2 Except tuple coverage: `src/example/module.py:42` - `except UnicodeDecodeError` body calls `read_text`; `OSError` leaks
- A3 Domain-error layering: none
- A4 Docstring Raises accuracy: none
- ... (every question that runs in this audit's --category)

(Repeat for every file in scope.)

## Phase B findings (consolidated)

For every "yes" answer above, surface as a finding with the standard structure:

### Finding: <title>

- **Category:** A / S / P / Sec / T / D / Doc
- **Question:** A2 / A9 / etc.
- **Severity:** high / medium / low
- **Location:** `path:line`
- **Description:** <what the issue is>
- **Recommendation:** <concrete action>

## Out-of-checklist observations

Things reviewers noticed that the checklist does not ask about. These are NOT findings; they are seeds for future checklist items.

- <observation> at `path:line` - candidate question: <draft>

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

Mechanically-detectable patterns surfaced via Phase B that the script does not currently catch. Do NOT add these to the script during this audit cycle. Add them only after the current task list ships AND the next audit on unchanged code shows zero mechanical delta.

- <pattern> first seen via question <Q-id> at `path:line`. Candidate predicate: <sketch>.
```

## Summary template

```markdown
# Audit Summary

**Last updated:** YYYY-MM-DD
**Last review:** review-N
**Total reviews conducted:** N
**Last script run hit count:** K (J accepted)
**Script version:** <git SHA of checks/audit.py at the time of the last review>

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

Greppable patterns Phase B has surfaced that are NOT yet in the script. Each becomes a check function in `checks/audit.py` only after the current task list ships and the next audit on unchanged code is mechanical-delta-zero.

- <pattern> - first seen review-N. Candidate predicate: <sketch>. Status: queued / scheduled-for-version-X / shipped-in-script-vY.
```

## Extending the script (between audit cycles)

When a Phase B run surfaces a class of greppable drift the script does not catch, write the candidate predicate into the review's "Script coverage notes" - DO NOT add it to `checks/audit.py` mid-cycle.

The script extension cycle is:

1. Audit run N completes; review-N captures script-coverage notes.
2. Task list tasks-N ships; codebase fixes are merged.
3. Audit run N+1 executes the SAME script as run N. The mechanical delta MUST be zero. Findings should equal: prior-cycle Phase B items not yet fixed, plus any genuinely new Phase B observations on the new code.
4. Once run N+1 is clean, add the queued check functions to `checks/audit.py` and bump the script version.
5. Audit run N+2 will surface historical debt for the new checks. That run is the "catch-up" run for those checks. After fixes, run N+3 should again be clean.

This rhythm separates "the audit is finding new things" (intended, on a fresh check) from "the audit is non-deterministic" (not intended, never).

## Severity guide

- **High:** security vulnerabilities, crashes, data loss, spec contradicts implementation on critical behaviour
- **Medium:** standards violations with real maintenance cost (widespread duplication, broken error reporting), missing tests for complex logic, docs out of date
- **Low:** local style nitpicks, minor doc gaps, suggestions for clarity

## Why this skill is structured this way

Earlier iterations relied on Claude to run greps and AST walks by hand, which agents reliably skipped, sampled, or silently filtered. The script fixed Phase A: agents cannot fake what a subprocess outputs. Acceptance is explicit (inline comment or AGENTS.md), not a decision-note argument.

The Phase B fix in this revision addresses a different failure mode: open-ended "report every concern" produced different findings on different runs of the same code, because reviewer agents applied different judgment thresholds. The fixed checklist makes Phase B deterministic. Two reviewers running the checklist on the same file converge on the same finding set.

The remaining variance - new code, new patterns, new checklist items added between cycles - is intentional and bounded. The audit-fix loop converges in finite steps because the script does not grow during a cycle and Phase B is a fixed set of questions.
