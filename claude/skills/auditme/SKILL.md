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

1. **Script grew between runs.** A new `check_*` was added to `auditor/rules/`, so historical debt that was previously invisible suddenly appears. Cure: the script-coverage backlog (see `summary.md`) must be drained into real check functions BEFORE any audit cycle starts. The script does not change during an audit. New patterns surfaced mid-audit are deferred to the next skill update, not the next audit cycle.
2. **Phase B was non-deterministic.** A reviewer agent applied different judgment than last round on the same files. Cure: Phase B fan-out is per-question, not per-file. One agent owns one question across all files in scope, so a single judgment threshold applies per predicate.
3. **Category-scoped runs.** A previous run used `--category X` and missed everything outside X. Cure: the canonical audit always runs every category. Use `--category` only for re-checking a single rule family during fix verification.
4. **Predicate drift.** A Phase B question's "should-have-caught" set quietly grew between cycles (e.g., A2 originally meant "missing `OSError`", later expanded to also mean "missing `ParserError`"). Cure: every predicate has a fixed enumeration encoded in this file. Expanding a predicate is a skill change, never a per-cycle adjustment.
5. **Rule conflict.** Fixing a finding under rule X created a finding under rule Y on the same line (e.g., moving `mkdir` from a callback into `__init__` swaps `A18` for `constructor-disk-io`). Cure: see [Rule conflict resolution](#rule-conflict-resolution).

The convergence rule applies in full to listed questions: a listed question's brief and lister do not change during an audit, and a carried verdict is reused only while its candidate's hash and the brief version are unchanged.

Convergence is non-negotiable. "We found more this time" is the failure signal, not progress.

## Workflow

### 1. Scope

- **Full audit** (no argument): `agents/specs/`, `src/`, `bin/`, `docs/`, `AGENTS.md`, `README.md`
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

**Rules repository identity.** When `AUDITOR_RULES_PATH` is set, run
`auditor rules identity` first and record its JSON as the review's
`**Auditor identity:**` line.

- If `rules_dirty` is true, the audit does not start: the rules repository has
  uncommitted changes, and a dirty tree is not a fixed version. Ask the user to
  commit or discard them.
- Compare the identity with the previous review's. When any field differs, the
  review's convergence note reads `Rules changed since review N: <the fields
  that changed>`, and the review is not counted as a convergence measurement,
  because new findings may come from new rules rather than from the code.

**Precondition: no open change requests, with `AUDITOR_RULES_PATH` set.** Run
`auditor rules pending`. It lists each open item of the rules repository's
`TODO.md` and exits 1 when there is one; the audit does not start while it
does. Ship each item (see Change requests below) or reject it, then run the
command again. The rest of this step is the precondition for the built-in
path, when `AUDITOR_RULES_PATH` is unset.

**Precondition: no open change requests, built-in path.** Before running, read
[`requests.md`](requests.md), beside this file. If its `## Open` section has any
entry, the audit is not allowed to start. Either:

1. Ship it - implement the check, run the sweep, land fixes or accept markers for the catch-up surface it exposes, delete the entry, and note the change in the affected projects' `summary.md`; or
2. Reject it explicitly - delete the entry and record the reason under `## Rejected`, so a later audit does not raise it a third time.

This precondition is the cure for failure mode 1. Without it, every audit cycle
ships another "next time we'll add this check" and convergence is impossible.

Requests live in the skill rather than in a project's `summary.md` because the
work is in the skill: a new check benefits every project, and burying it in the
notes of the one that noticed hides it from the repository where it would be
done.

Then run the shipped audit script:

```bash
auditor check <project-root> [--package <pkg>] [--extra-root <dir>]
```

`<project-root>` is the project's top directory; `src/` is optional. `--package`
restricts the run to one package; it defaults to **every** package under
`src/`, each audited in its own pass, followed by every extra root.

Do not pass `--package` for a normal audit. A project whose `src/` holds both
the library and the test tree has two packages, and auditing one of them
reports a partial scope as a complete one. Until 2026-08-14 the default was
"the alphabetically-first directory under `src/`", which on one project meant
`src/tests/` was never read: every hit in it stayed invisible across several
audit cycles while the sweep looked clean. The same default would have picked
`__pycache__` on a project that had one.

A project whose Python is not under `src/` and `bin/` declares its roots in
`[tool.auditme]` in `pyproject.toml` (`roots = [{ path = "...", modules =
"package" | "top-level" }]`). The declared list replaces the defaults, and
`--extra-root` replaces it for one run. See `docs/reference/cli.md`.

An **extra root** is auditable Python that is not a package under `src/`.
`bin/` is the default one, used whenever it exists and holds `.py` files, and
`--extra-root <dir>` (repeatable, relative to the project root) replaces that
default set. The same under-coverage had a second instance here: enumerating
packages *under `src/`* gave a project whose scripts live in `bin/` no rows at
all for them - accepted or otherwise - while consecutive audit summaries
recorded "`bin/` remains at zero unaccepted hits" as though a
measurement had been taken. A named `--extra-root` that does not exist is an
error rather than an empty pass, because a typo would reinstate exactly that.
`--package` asks for one package, so it drops the extra roots too.

A `.py` file directly in `src/` belongs to no root, so no pass would read it.
The driver reports it as a `src-loose-module` hit (not a registered check: a
check runs once per root, and a project holding only `src/a.py` has none), and
`--package` emits none. Move the file into a package, or accept it with
`# auditme: accept[src-loose-module] <reason>` on line 1.

A file a check cannot read (removed mid-run, permission denied, not UTF-8) is
reported by the driver as an `unreadable-file` hit naming the path; the check
skips it and still reports its other hits.

The `ruff-version-drift` check sits beside the existing ruff check. It is
project-level: it compares the version `ruff --version` prints for the ruff
the audit runs with the `rev` of the `ruff-pre-commit` repo in
`.pre-commit-config.yaml`, and reports `the ruff the audit runs differs from
the ruff-pre-commit rev` at the `rev:` line when they differ, so the commit
hook and the audit cannot disagree about formatting. The audit runs the
project's own `.venv/bin/ruff` when it is an executable file, and `ruff` from
`PATH` only otherwise, so the answer does not depend on which ruff a shell
finds first; the hit's evidence names which one ran. A `rev` that is a commit SHA
uses the version in its `# frozen: <version>` comment. Two variants say the
check cannot verify: `the ruff-pre-commit rev names no version` (a SHA with no
`frozen` comment, or no `rev:` at all) and `ruff --version printed no
version`. It is silent when there is no config, no `ruff-pre-commit` repo, or
no ruff to run (the ruff check reports that). Clear a hit by making the
two equal; to accept one, put `# auditme: accept[ruff-version-drift] <reason>`
on the `rev:` line or the line above it.

Each root is audited in its own pass rather than in one pass rooted at
`src/`, because `src_root.name` is the package's dotted root - several checks
build module names from it - so a single pass over `src/` would rename every
module to `src.<pkg>.<mod>` and break the import-graph checks and every
AGENTS.md acceptance row. Duplicate hits from project-level checks (the
lockfile, and anything reading AGENTS.md) are suppressed by the driver.

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
  "accepted_reason": null,
  "related": ["src/foo/baz.py"]
}
```

`related` appears only on a hit from a rule that compares two or more files:
the other locations' repository-relative paths, sorted, never the hit's own
path. A hit from any other rule has no `related` key. A scope filter such as
`auditor changed` reports a hit when its `path` or any `related` path is in
scope.

**Rules:**

1. Save the full JSONL output to `/tmp/audit-<project>.jsonl`.
2. Every hit with `accepted: false` MUST appear in the review file as a finding (grouped by rule, enumerated individually with `path:line`).
3. Hits with `accepted: true` are dismissed with their `accepted_reason`. Do not re-litigate them.
4. You may NOT filter, sample, or dismiss `accepted: false` hits. "Pre-existing", "project norm", "seems intentional" are NOT acceptable dismissals. To accept a pattern:
   - one site: inline `# auditme: accept <reason>` comment on the hit line or the line above
   - many sites of the same class: AGENTS.md table entry, then re-run the script
5. **Do not extend the script during the audit.** If Phase B surfaces a new mechanically-detectable pattern, write it down in the review's "Script coverage notes" but do not add it to `auditor/rules/` until the current task list ships and the next audit on unchanged code shows zero mechanical delta. This is the cure for the perpetual "the audit keeps finding new things" loop: the script stays still, the next run is clean, then the script grows.

The full set of rules the script catches is documented in the checker itself -
read the docstring of each `check_*` function for the predicate it encodes.
`auditor check` is only the entry point; the checks live in the `auditor`
package's `rules/` directory (`src/auditor/rules/` in the auditor repository), one module per family of defect (`project_hygiene.py`; the duplication, style and naming, imports and surfaces, state and effects and error handling checks have moved to `src/auditor/catalogue/rules/`), with the shared helpers in
`auditor/core.py` and the run order in `auditor/registry.py`.
The checker's own tests live in [`tests/`](tests/README.md) and run with
`uv run --no-project --with pytest pytest ~/.claude/skills/auditme/tests`.

**`CHECKS`'s order is the emission order, and therefore part of the output.**
Adding an entry is free; moving an existing one reorders every subsequent hit
and will read as a diff in the next audit even though nothing was found
differently.

### 4. Interpretive review (per-question fan-out)

Phase B is **not** free-form reading. It is a fixed checklist applied across every file in scope. Two audit runs of the same checklist over the same code must produce the same finding set.

**Fan out by question, not by file.** Spawn one subagent per Phase B question (or per small bundle of related questions within one category). Each subagent owns ONE predicate across ALL files in scope. The subagent's task: "apply predicate Q across these files, return the list of `path:line` instances."

This is the cure for failure mode 2. When 24 architecture questions are split across reviewers by file, each reviewer applies a slightly different judgment threshold to its slice of the corpus, and a different threshold to a different question, multiplying variance. With per-question fan-out, one reviewer applies one threshold to one predicate, eliminating cross-question and cross-file judgment drift.

**Listed questions.** A question with a lister is judged candidate by candidate, not by sampling. The listed questions are A1, A4, A11, A17, A19, T1, T2, Doc1, Doc2, Doc4 and Doc5. For a listed question, run `auditor phaseb` (with `<root>` the project root) in this order:

1. `auditor phaseb plan <root> --question <Q> --out <dir>` writes `batch-NN.jsonl` and `plan.json` (which records the `--depth` it listed at; `merge` refuses a different one). A candidate whose ledger verdict is current (same content hash, same brief version) is left out; `--rejudge` includes it again. A candidate planned again that the ledger holds a verdict for carries it as `earlier` in its batch line.
2. Spawn one reviewer per batch, each given the question's brief (`briefs/<Q>.md` in the `auditor` package, named in `plan.json`) and its batch file. Each writes `result-NN.jsonl` in `<dir>`.
3. `auditor phaseb check <dir>` exits 1 and names each batch with a problem. Send a failing batch to a fresh reviewer, up to two retries per batch. A batch still failing after that is reported in the review, never merged.
4. `auditor phaseb merge <root> --question <Q> <dir>` writes the verified results into the project's ledger.
5. `auditor phaseb report <root> --question <Q>` prints the open findings, new and carried.

`--question` accepts each listed question; `--depth` applies to A4 only. A site a sweep rule for the same question reports, accepted or not, is not judged in Phase B, and is judged as new once the hit is fixed.

A listed question's findings are its flagged ledger verdicts, new or carried. A carried finding is not a regression and is never marked "missed by" a review. When the operator dismisses a finding on the review page, record it with `phaseb.py dismiss <root> --question <Q> <id> --reason <text>`.

Every other question is sampled: mark it `(sampled)` in the review. A new site found by a sampled question is coverage, not drift: it goes under "Coverage (sampled)" and is never marked "missed by" a review.

**Sampled cadence.** Between whole-tree audits, each sampled reviewer is given the changed lines of each changed file since the previous review's `**Commit:**` (`auditor changed --scope --base <commit>` prints them, each hunk widened to its enclosing function or class) and judges only those lines. Every third audit, counted from the first audit after the Doc questions were listed, and any audit with no previous `**Commit:**`, runs it on the whole tree. The review records each sampled question's mode: "changed lines since <commit>", or full.

**First audit after the Doc questions were listed.** It judges every Doc candidate. Its findings in unchanged code are catch-up, not regressions; this includes README findings, because Doc5's predicate now covers `README.md` as well as `docs/`. Its Convergence note names the newly listed questions.

**First audit after T1 and T2 were listed.** It judges every T1 and T2 candidate as new. Its findings are coverage, not drift: a candidate with no test case, or a domain with no property test, in unchanged code is catch-up, not a regression. Its Convergence note names T1 and T2 as newly listed.

**First audit after A11, A19, A1 and A17 were listed.** It judges every candidate of those questions as new. Its findings are coverage, not drift: a site in unchanged code is catch-up, not a regression. Its Convergence note names A11, A19, A1 and A17 as newly listed.

Putting a question on the listed path (its lister, brief and tests) is a skill change made between audits, never during one.

Rules for reviewers:

- Apply ONE predicate to ALL files. Do not range across questions; do not skip files.
- The predicate's enumeration in this file is exhaustive. If the predicate says "covers `OSError, PermissionError, FileNotFoundError`", do not also flag missing `ValueError` - that is a different predicate and a different reviewer's job.
- Output one row per hit: `path:line - one-line description`. No prose.
- "No hits" is a valid result; record it explicitly so the orchestrator can confirm the predicate was actually run.
- **Do not invent findings.** If you observe something no predicate asks about, drop it. The skill - not the audit - is where new predicates are added. The previous "Out-of-checklist observations" mechanism is removed because it created perpetual discovery loops; new predicates land via skill update between cycles, never mid-cycle.
- Do not self-edit. Low-severity findings still go in the review.

### 5. Spec review

For each spec in scope, check it against the validation criteria and spec template in the specdev skill (`~/.claude/skills/specdev/SKILL.md`, installed from the agents repository). Record gaps as findings. Skip if no specs in scope.

### 6. Re-verify prior findings

For each unresolved finding in `summary.md`, grep or read to confirm: still present, or now resolved. If resolved, mark closed in `summary.md` and (if applicable) mark the corresponding task file done.

For each incomplete task in `agents/tasks/audit-reviews/*.md`, verify against source: actually incomplete (re-flag in the review) or shipped (mark done in the task file).

### 7. Completion gate

Before writing the review file, confirm:

- [ ] `requests.md`'s `## Open` section was empty at audit start (every entry shipped or rejected)
- [ ] `auditor check` was executed and its full JSONL output saved
- [ ] Every `accepted: false` hit appears in the review (no sampling, no silent dismissals)
- [ ] Phase B ran with per-question fan-out covering EVERY question in EVERY category (`--category` was NOT used unless the user explicitly asked for a partial verification)
- [ ] Every Phase B subagent returned an explicit hit list (or "no hits") - no question silently skipped
- [ ] Every listed question has a current verdict for every candidate, or the review names each id not judged
- [ ] Every sampled question ran in its cadence's mode (the lines changed since the previous review, each widened to its enclosing function, or the whole tree on every third audit and on any audit with no previous `**Commit:**`), and the review records the mode
- [ ] Every unresolved `summary.md` finding was re-verified
- [ ] Every incomplete task file was re-verified against source
- [ ] No new check was added to `auditor/rules/` during this audit (script-coverage delta is zero)
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
5. Commit message: `docs(audit): add review-N`
6. Do not push unless asked

## Acceptance mechanism

The script treats a hit as `accepted: true` only when one of these exists:

1. **Inline comment** on the hit line or the preceding line, optionally scoped to a single rule:
   - `# auditme: accept[<rule-name>] <reason>` - answers for that rule only
   - `# auditme: accept <reason>` - answers for every rule that fires on the line
   - several markers on one line each answer for their own rule: `# auditme: accept[rule-a] <reason>  # auditme: accept[rule-b] <reason>`, each reason ending where the next marker begins
2. **AGENTS.md table row** pairing the importer and imported module in backticks (for in-function imports). The importer module path is computed without a leading `src.` prefix (e.g. `pkg.config.structures`, not `src.pkg.config.structures`); AGENTS.md rows should use the same form.

A project can refuse markers for named rules with `[tool.auditme] never-accepted` in `pyproject.toml` (rule names, or families ending in `*`): a hit of such a rule stays `accepted: false` and carries the marker's text in `refused_reason`. `ruff` and `lockfile-drift` hits are never accepted by a marker either.

Nothing else acts as acceptance - not a decision note under `agents/audit-reviews/`, not a prior review that "agreed" the pattern is fine, not an assumption about HF / sklearn / PEP conventions.

### Scope your markers to a rule

**Write new markers in the scoped form.** An unscoped marker accepts every rule
that fires on its line, including rules that did not exist when it was written -
so a decision weighed about one predicate silently excuses a different one later.
This is not hypothetical: on one project, a marker reasoning entirely
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
- **A2. Except tuple coverage.** For every `try/except` whose body touches disk or pandas/json parsers: does the except tuple include EVERY exception in the locked set below? Locked set: `OSError` (covers `PermissionError`, `FileNotFoundError`, `IsADirectoryError`); `UnicodeDecodeError` if the body decodes text; `pandas.errors.ParserError` if the body calls `pd.read_*`; `json.JSONDecodeError` if the body calls `json.load*`; `gzip.BadGzipFile` if the body opens `.gz`. Bare `Exception` also satisfies. Flag any tuple missing one of the above when the body matches that branch. The envelope need not be a lexical `try` - a translating decorator or a `with` block over a contextmanager is one too, and is the shape the reviewer has to read a second file to judge. Do not extend this set during an audit; expansion is a skill change.
  The `translator-envelope-gap` check now covers the non-lexical form mechanically, for the branches a machine can recognise without judgement: `json.load*`, `pd.read_*`, `gzip.open`, `read_text` and the filesystem primitives. Text decoding through any other route - `.decode()`, a codec, a library that reads bytes and returns `str` - is still this question's to answer by hand.
- **A3. Domain-error layering.** For every `raise` statement: is the raised type the package's domain `*Error` (or a `*Error` from a strictly lower layer)? Flag stdlib `FileNotFoundError`/`KeyError`/`RuntimeError`/`TypeError`/`ValueError` raised in a package that defines its own `*Error` class.
- **A4. Docstring `Raises` accuracy.** For every function whose docstring has a `Raises:` section: does the body actually raise each declared exception type, and only those? Flag mismatches. A declared type is raised if the body raises it, or calls a function in the same package that raises it and does not catch it; an undeclared domain error that reaches the caller that way is a mismatch. The sweep's `raises-section-drift` rule checks the mechanical part: it follows each same-package callee (and each callee in a library that `[tool.auditme] first-party` lists), including `<ClassName>.<method>(...)` for a class the package defines, through its declared `Raises:`, and follows a callee with no section into its own raises and callees, up to three calls deep; it nets out handlers that catch without re-raising, and reports each omitted name, and each declared name that a handler in the function catches and nothing else raises. It skips a callee error guarded only by optional arguments the call leaves unset (`if strict: raise ...` called without `strict`). Phase B reviews the other value-dependent cases (fixed names, pre-checked values, dispatch types) and what the sweep cannot resolve: calls on instances, `cls.<method>()` calls, inherited methods, callables passed in, errors stored and raised later, and declared names reaching only through those.
- **A5. Two sources of truth.** For every state value that has both a config field and a method parameter (or two attributes that should always agree): is the precedence rule documented and enforced? Flag silent precedence (whichever path wins by coincidence of execution order).
- **A6. Stage method dual-path.** For every method on a pipeline-stage class: does it both return a value AND mutate `self.<attr>` for the same field? Flag tuple-returning methods that also self-mutate.
- **A7. Constructor purity.** For every `__init__`: does it perform I/O (open, mkdir, read_text, subprocess, network, expensive compute)? Does it mutate any of its arguments? Flag both.
- **A8. Late dataclass mutation.** For every `@dataclass` instance constructed inside a function: is it mutated after construction (`x = Foo(...); x.field = ...`)? Flag late mutations - they bypass `__post_init__` and any `frozen=True` would have caught them.
- **A9. Pure-named function side effects.** For every function whose name starts with a pure prefix (`get_`, `resolve_`, `find_`, `compute_`, `build_`, `make_`, `load_`, `parse_`, `is_`, `has_`, `validate_`, `count_`, `check_`, `allocate_`): does the body call I/O / subprocess / `datetime.now()` / network? Flag naming-vs-implementation gaps. Normalising a path (`Path.resolve`, `Path.absolute`, `Path.expanduser`, `os.path.realpath`) is not I/O; opening a file, reading its contents, testing for existence and writing are. A `load_` function that reads the file, module or directory its name or arguments say it loads is not a hit; any other I/O in it is. A function the project registers as a check is not read as pure-named by its `check_` prefix: its name is a member of the project's check registry (a tuple, list or mapping of check functions a runner calls, such as `CHECKS` in this checker's `auditor/registry.py`), or it is decorated by a function that adds it to such a registry. The registration is the positive evidence; the `check_` prefix alone is not, and an unregistered `check_` function is still read as pure-named.
- **A10. Predicate semantics.** For every predicate function (`is_X`, `has_X`, `should_X`): does the body answer exactly the question the name asks, with no hidden conjuncts? Flag conflated predicates (e.g. `side_channel_active` returning `enabled and imputation != 'median'`).
- **A11. Exhaustion via assert_never.** For every `if/elif/else` chain over a `typing.Literal` or enum: is the unreachable branch handled with `typing.assert_never`? Flag chains that end in `raise <SomeError>(...)` instead - the type-checker cannot verify exhaustion. A two-way split on a bool computed from a `Literal` or enum value counts as a chain over that value.
- **A12. assert misuse.** For every `assert` outside test files: is it a developer-only invariant that `python -O` may safely remove? Flag asserts used as runtime validation; those should be `if not X: raise DomainError(...)`.
- **A13. Same value to multiple structural slots.** For every constructor call that takes positional / keyword arguments for distinguishable slots (`train`, `val`, `test`): is the same value passed to 2+ slots? Flag (e.g. `DatasetSplits(train=ds, val=ds, test=ds)`) and require either an explicit factory or a docstring.
- **A14. Repeated computation per request.** For every helper function whose value is a property of the project state (HEAD SHA, primary metric, resolved config): is it called more than twice in a single request flow? Flag candidates for memoisation / single-resolution.
- **A15. Duplicate constructor / serialisation logic.** For every class whose constructor is called from 2+ sites with substantially the same field set: is the construction factored into one helper? Flag duplicated assembly that would silently drift on field addition.
- **A16. CLI entry envelope.** For every top-level `run_*` function in `cli/*.py` that returns `int` or takes a cappa-typed parameter: does the body's `try/except` cover every `raise` in the function (including validation `raise`s before the try)? Flag `raise` statements outside the envelope.
- **A17. Public-surface drift.** For every `__init__.py` with `__all__`: is every symbol in `__all__` used outside the package? For every empty `__init__.py`: do consumers reach into private submodules? Flag bypasses of the canonical owning module. A submodule with a module-level `__all__` is judged the same way as an `__init__.py` with one: is every symbol in its `__all__` used outside the module?
- **A18. Hot-path setup.** For every callback method (`on_step`, `on_log`, `on_evaluate`, `on_batch_*`): does it perform setup (mkdir, file open) that should live in `__init__`? Flag per-event side effects.
- **A19. Wrong logger level for broad-except.** For every `except Exception` / `except BaseException`: does the body use `logger.exception` (not `warning`/`error`/`info`/`debug`)? And conversely, is `logger.exception` reserved for unexpected failures, not expected graceful-degradation paths? A broad handler that degrades gracefully fails one half of this question whichever level it uses; the fix is to remove or narrow it - see [Conflicts with no winner](#conflicts-with-no-winner).
- **A20. Mutable module-level singleton.** For every module-level mutable container that is read by name from another module: is it immutable per the locked set below? Locked set: `dict` -> must be `types.MappingProxyType(...)`; `set` -> must be `frozenset(...)`; `list` -> must be `tuple(...)`, whether the value is written as a literal, as a comprehension or as a call to the bare builtin constructor - `{k: f(k) for ...}` and `dict(a=1)` are the same mutable `dict` that `{...}` is. Any other call (`get_defaults()`) is out: it does not state its type. The predicate is "read elsewhere", and a project that mandates full import paths writes every one of those reads dotted: verify with grep for **all three** of `from <module> import <name>`, `<module>.<name>` and `sys.modules['<module>'].<name>`, across **every** root the sweep reads - every package under `src/` and `bin/` - not just the package under audit. A reader in the test tree is a reader, and so is a script. The `sys.modules` form is not exotic: it is the documented way to reach a module without importing it, so the projects most careful about import cycles are the ones a scan that missed it under-reported. Do not extend this predicate to private (non-read) module-level containers, nor to a value whose type is not knowable from the assignment (`DEFAULTS = get_defaults()`); those are different rules. A container the wrapper only *appears* to freeze is A25's.
- **A21. Lazy init race.** For every `if X is None: X = ...` pattern at module scope (or in a module-level helper): is the assignment thread-safe under concurrent invocation? Flag idempotent-but-racy patterns in code paths that may be called concurrently (Optuna trials, multiprocessing).
- **A22. Fall-through after partial handling.** For every `if/else` chain whose branches partly raise and partly return: is there a fall-through path where a raised-and-translated error in the first branch silently retries in the second? Flag with-block-or-elif-fall-through patterns (e.g. `if gz: ... except: raise` then code that re-runs as if `gz=False`).
- **A23. Discarded multi-return.** For every call to a function that returns a tuple/dataclass: are all returned components used or explicitly named (`a, _ = f()`)? Flag silent discard of secondary returns that signal hidden state dependencies. Reading one attribute of a returned object discards the others when the function documents one of them as changing how the first is used; an attribute read that drops nothing documented is a use. The `discarded-tuple-return` rule is the mechanical part: a bare-statement call to a package function annotated `-> tuple[A, B, ...]`. The dataclass and partial-use cases stay Phase B.
- **A24. Identity of subprocess / shell-out calls.** For every `subprocess.run` / `git`-shelling-out helper: is its result memoised when the source is invariant within a request? Flag repeated subprocess invocations per request.
- **A25. Shallow immutable wrapper.** For every module-level container that A20 accepts as immutable - `types.MappingProxyType(...)`, `frozenset(...)`, `tuple(...)` - and that is read by name from another module: is every member of the wrapped literal itself immutable? Every one of those wrappers freezes the container it is given and nothing inside it, so `types.MappingProxyType({'a': []})` satisfies A20 and still hands each caller the same live `list`. Flag a `dict`/`list`/`set` member, a member one tuple deep, and a member that is an instance of a dataclass this project defines without `frozen=True`. The enumeration stops where A20's does: a member whose type the assignment does not state (`MappingProxyType({'a': build()})`) is not this question's. A20 and A25 are accepted separately - a marker that answers "this is wrapped" has not answered "and its members are frozen".

### Standards (S)

- **S1. Type annotations on every signature.** Parameter and return annotations everywhere. Flag bare untyped signatures. **Scope is locked and asymmetric.** Enumerate every missing annotation individually, with `path:line`, for non-test source only. For files under a `tests/` directory, do NOT enumerate: report a single count line (missing parameter annotations, missing return annotations, modules affected, modules fully annotated). Consecutive reviews of one project each chose differently here - one skipped tests, the next enumerated every one of them, the third counted - and the swing is the single largest source of apparent finding-count movement between cycles. If the project records a standing exemption for test annotations (as an AGENTS.md note that `ANN` is not enabled for tests), the count also serves as a drift check on that note's own figures; a discrepancy is a documentation finding under Doc1, not an S1 finding.
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
- **D2. Unused declarations.** Every declared dependency is imported somewhere, or run as a command. A dependency the project runs as a command is used though nothing imports it - a type checker, linter, formatter or hook runner declared so the environment installs it. It counts as run when the executable it installs is named in `.pre-commit-config.yaml` (a hook's `entry`, or the tool a hook's `repo` provides), in a CI workflow `run:` step, or as the first argument of a `subprocess` call in the project's own code, directly or through `uv run`, `python -m` or `pre-commit run`. A dependency a host tool loads as a plugin or theme is used too, when a declared dependency is that host and the plugin's installed metadata (`entry_points.txt` in its `.dist-info`) registers an entry point in a group the host loads. pytest loads every `pytest11` entry point, so a pytest plugin counts unless the project's pytest config disables it (`-p no:<name>`). mkdocs loads only what `mkdocs.yml` names, so an entry point in `mkdocs.themes` or `mkdocs.plugins` counts only when its name is the `theme: name:` or listed under `plugins:` (`mkdocs-material` registers `material`). A package name that merely resembles a tool's name, with no such entry point, is not evidence. A type-stub package (`*-stubs`, `types-*`) is used when the project runs a type checker (mypy, pyright or pyre) by the rule above, and a Jupyter kernel package (`ipykernel`) is used when a declared dependency executes notebooks (`nbclient`, `nbconvert`, `papermill`, `nbmake`); without that evidence each is flagged like any other. Flag a dependency that is neither imported, run nor loaded anywhere.
- **D3. Lockfile coherence.** Already script-checked; flag if the script's lockfile-drift hit appears.

### Documentation (Doc)

- **Doc1. AGENTS.md project structure** matches actual directory layout.
- **Doc2. AGENTS.md tools and libraries list** is current.
- **Doc3. README.md and AGENTS.md** consistent.
- **Doc4. Specs match implementation.** Drift between `agents/specs/` and `src/`.
- **Doc5. User docs match implementation.** Drift between `docs/` or `README.md` and `src/`.

## Review template

```markdown
# Audit Review N

**Date:** YYYY-MM-DD
**Scope:** <"full" or specific modules/specs>
**Commit:** <the audited `HEAD`>
**Auditor identity:** <the output of `auditor rules identity`, as JSON; only when `AUDITOR_RULES_PATH` is set>
**Script output:** /tmp/audit-<project>.jsonl (N hits, M accepted, K unaccepted)
**Convergence note:** <"clean - script unchanged since review-(N-1)" OR "script extended since review-(N-1) by these checks: [list]; expect mechanical delta">
**Rules changed:** <only when the identity differs from review-(N-1)'s: `Rules changed since review N-1: <fields>`. Such a review is not a convergence measurement>

## Summary

<2-3 sentences. Mention script hit counts by rule and the interpretive findings count.>

## Mechanical findings (from `auditor check`)

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

### A2 (sampled): Except tuple coverage

- **Mode:** <changed lines since commit <hash>, or full>
- **Subagent ran on:** all 103 src files
- **Hits:**
  - `path:line` - `except UnicodeDecodeError` body calls `read_text`; `OSError` missing
  - `path:line` - ...
- **No-hit confirmation:** N files inspected, M had no matching `try/except`

(Repeat for every question - A1..A25, S1..S4, etc. A sampled question carries `(sampled)` and its mode; a listed question names its candidates judged, and any id not judged.)

### Coverage (sampled)

New sites found by sampled questions: coverage, not drift. Never marked "missed by" a review.

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

- `src/example/module.py` - questions A1-A25, S1-S4
- ...

## Prior findings re-verified

From summary.md's unresolved list:

- <title> - resolved at `path:line` / still present at `path:line`

## Recommendations

Prioritised by severity.

## Script coverage notes

Phase B has no script-coverage notes section in this template by design. The previous mechanism (note candidate predicates per audit) created a perpetual queue. New predicates are added by editing this skill between cycles, not by leaving notes for future audits.

If during this audit you genuinely identified a missing predicate, file it
after the review is written, as the Change requests section below says, and
tell the user. Do not add it to the review, and do not change the checker
now - that is failure mode 1.
```

## Change requests

This section applies only when `AUDITOR_RULES_PATH` is set. With it unset, the
built-in path keeps using [`requests.md`](requests.md) until the rule
catalogue replaces it.

A pattern an audit finds that the sweep should check is a change request on
the rules repository. An audit never changes a rule while it runs (failure
mode 1).

- **Filing.** After the review is written, file each new request with the
  `todo-add` skill in `$AUDITOR_RULES_PATH/TODO.md`: dated, checked against the
  code, and merged into an existing item when the two share a cause. Before
  filing, search `$AUDITOR_RULES_PATH/DONE.md` and the relevant rule's
  `rule.md` so an idea already rejected is not raised again.
- **The precondition.** Step 3 runs `auditor rules pending` before the sweep.
  The audit does not start while it exits 1: a rules repository's `TODO.md`
  holds only rule work, so every open item blocks.
- **Shipping.** Implement the rule, run the sweep on a real project, land fixes
  or accept markers for what it newly finds, then move the item to `DONE.md`
  with its `Done:` line.
- **Rejecting.** Move the item to `DONE.md` with
  `Done: rejected on <date> - <reason>`. When it concerns one rule, also add
  the reason under a `## Rejected widenings` heading in that rule's `rule.md`.
- **Runner requests.** A request whose fix is in the runner or the skill, not
  in a rule, goes in the auditor repository's own `TODO.md`. It does not block
  audits.

## Summary template

```markdown
# Audit Summary

**Last updated:** YYYY-MM-DD
**Last review:** review-N
**Total reviews conducted:** N
**Last script run hit count:** K (J accepted)
**Auditor identity:** <the output of `auditor rules identity`, as JSON, when `AUDITOR_RULES_PATH` is set; otherwise the digest of the whole checker:

```bash
printf '%s %s\n' "$(auditor --version)" "$(git --git-dir="$(cat ~/.claude/auditor-source)" rev-parse HEAD)"
```

The version alone does not change when a check is edited, so the digest adds the
commit of the auditor repository that `bin/install-claude.sh` installed the
tool from (recorded in `~/.claude/auditor-source`).>

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

## Checker changes since the last review

Only what a reader needs to interpret the next convergence note: which checks
were added, removed or refined, and the resulting expected delta. Open requests
do not belong here - they live in the skill's own
[`requests.md`](requests.md), because the work is there rather than in this
project.

- (none since review-N)
```

## Extending the script (skill-update, not audit)

Adding a check is a skill change. It happens between audit cycles, with no in-flight audit, and no queued backlog deferred to "next time".

Process:

1. User raises a candidate predicate (or this skill is updated to add a new Phase B question).
2. Implement the predicate as a `check_*` function in the matching `auditor/rules/` module immediately, and append it to `CHECKS` in `auditor/registry.py`. Append - never insert, see [`CHECKS`'s order](#3-mechanical-sweep-scripted).
3. Add tests under [`tests/`](tests/README.md): the shape it fires on, every carve-out that must not fire, and the behaviour of an accept marker scoped to the rule. Run `uv run --no-project --with pytest pytest ~/.claude/skills/auditme/tests`.
4. Run the script on the project. The result is the catch-up surface. Land fixes (or accept markers) for everything it returns.
5. After fixes, run the audit normally. Convergence is restored.

The previous "queue, defer, audit, defer again" rhythm was the dominant cause of perpetual cycles: every cycle promoted a new queued item AND surfaced new Phase B items, so backlog never reached zero. The new rule is **drain immediately or reject explicitly**. There is no permitted state where the backlog is non-empty and an audit is starting.

### Refining a predicate (narrowing, not expanding)

Refinements are different from extensions. An extension grows a predicate's "should-have-caught" set and is forbidden mid-audit (predicate drift, failure mode 4). A refinement narrows the set by carving out a sanctioned sub-pattern that should not fire - the predicate's enumeration in this file is updated to name the carve-out, and the script implements the skip.

A refinement is a skill change too: same process as above (drain immediately, then run the audit). Each refinement is documented in the predicate's docstring inside its `auditor/rules/` module, and given a test case that asserts the carve-out does not fire, so future readers see why a sub-pattern is skipped and cannot silently un-skip it.

Documented refinements:

- **`except-interpolation`:** the predicate skips interpolation expressions of the form `type(<bound>).__name__` / `__qualname__` and `<bound>.__class__.__name__` / `__qualname__`. The class-name string is a categorical hint, not a lossy duplication of the message body. See `is_categorical_class_name_expr` in `src/auditor/catalogue/rules/except-interpolation/check.py`.
- **`empty-init-while-siblings-export`:** the predicate is file-level. The accept-marker scan walks every line in the file rather than just the docstring opener, so a docstring-only `__init__.py` can be accepted by adding a comment-only `# auditme: accept <reason>` line anywhere in the file.
- **`asymmetric-exception-translation` (2026-11-24):** a callee is a hit only when its own body (nested defs skipped) calls a `FILESYSTEM_TOUCHING_CALLS` name or a call rooted at a module imported from outside the swept package, and does not call a same-module function `translator_envelopes` lists. Pure string or arithmetic work is not a hit. See `has_something_to_translate` in `src/auditor/catalogue/rules/asymmetric-exception-translation/check.py`.
- **`legacy-typing` (2026-10-14):** the predicate skips `Set[` when it is preceded by `collections.abc.`. `collections.abc.Set` is the modern ABC, not the deprecated `typing.Set`. See the `legacy-typing` pattern in `check` in `src/auditor/catalogue/rules/text-patterns/check.py`.
- **`aliased-imports`, `legacy-typing`, `relative-import-nonpackage` and the `leading-underscore-*` line-pattern rules (2026-11-21):** a line is read with the text of every plain string literal blanked, so fixture source or a regex held in a string is data, not code. A docstring is still read, and code on the same line as a string still fires. See `CODE_ONLY_RULES` and `mask_string_literals` in `src/auditor/catalogue/rules/text-patterns/check.py`.
- **`literal-duplication` (2026-11-21):** in a test file (a `tests` directory, `test_*.py`, `*_test.py` or `conftest.py`) a one-member literal and a literal inside an `assert` statement or a `pytest.param(...)` call are expectations, not shared data, and are not counted. A multi-member literal in test set-up still counts, and so does any literal in source. See `test_expectation_nodes` in `src/auditor/catalogue/rules/literal-duplication/check.py`.
- **`filesystem-envelope-gap` (2026-11-21):** a `try` is flagged only when one of its handlers raises with an exception (`raise X`): the rule's rationale is a wrapper that promises to translate to a project error. A handler that continues, returns or logs, and a bare `raise`, are not a gap.
- **`filesystem-op-without-envelope` (2026-11-21):** a call by bare name to a function defined in the same module whose own body has a `try` with a handler for `OSError` (or `IOError`, `Exception`, `BaseException`, or a bare `except`) is not counted as a filesystem primitive, since the helper holds the envelope.
- **`get-container-default-then-method-call` (2026-11-21):** a mapping produced by `tomllib.load` or `tomllib.loads` is skipped, since TOML has no null. The receiver counts when it is such a call, a call to a same-module function that returns one (and otherwise only a dict literal, such as `{}` for an absent file), a name the scope assigns from either, or a parameter of a module-level function that every same-module call passes one.
- **`redundant-sink-caller-plus-callee` (2026-11-21):** a call inside a def nested in the caller or the helper belongs to that nested def and is not counted; a call from a function to itself is not a helper call; a helper is resolved by qualified name (a dotted callee matches only a function whose module path ends in it, a bare name matches the calling module's function, else the single project function of that name, and an ambiguous bare name matches nothing); and keyword values are compared as well as keyword names. See `resolve_helper` in `check` in `src/auditor/catalogue/rules/redundant-sink-caller-plus-callee/check.py`.
- **`in-function-import` (2026-11-21):** the variant labels a module under a declared root (`[tool.auditme]`, either mode) `first-party`, as well as the importer's own package. A label only: the hit count does not change. See `declared_root_modules` in `auditor/api/project.py`.
- **`filesystem-envelope-gap` (2026-11-01):** a bare name in a handler's type, alone or inside a tuple, that names a module-level tuple literal assigned once in the same file is read as that tuple's members, one level deep, so `except READ_ERRORS:` with `READ_ERRORS = (OSError, ValueError)` closes the gap. Another module's name, a call's result, a name assigned twice and a constant nested in another keep the name test. See `module_tuple_constants` in `auditor/errorsites.py`.
- **`raises-section-drift` (2026-11-01):** a callee's declared error is not reported as omitted when every `raise` of it in the callee's own body sits under an `if` or `match` that tests a parameter with a default which the call leaves unset, as `if strict: raise ParseError(...)` called as `load('x')`. Omissions only. A guard on a parameter without a default, a module-level name, a raise outside the guard, or a call passing the argument (or `*args` / `**kwargs`) keeps the hit. A def nested directly in the subject and called by bare name also counts, one level deep, under the call's handlers; a raise inside a def, lambda or class defined in a handler does not make that handler re-raise. See `unset_optional_guard` in `src/auditor/catalogue/rules/raises-section-drift/check.py` and `nested_call_sites` in `auditor/errorsites.py`.
- **`raises-section-drift` (2026-11-24):** a combined `Raises:` entry (`ParseError, FetchError: <when>`) declares each name, and a handler naming a module-level tuple of classes the package defines (`except errors.HANDLED_ERRORS:`) catches each member, in the function's own handlers and around its calls. As for `filesystem-envelope-gap`, a name assigned twice in its module, a member read more than one level deep, and a name two modules bind to different members keep the name test. See `raises_section_names` in `auditor/errorsites.py`, and `tuple_constants` and `expand_level` in `auditor/errorsites.py`.
- **`missing-raises-section` (2026-11-01):** a raise that a handler around it catches without re-raising, by its own class or a base class in the package's class tree (a bare `except:`, `Exception` and `BaseException` catch all), does not reach the caller and does not count, as `try: raise ParseError(...) except ParseError: ...`. A handler that re-raises, one for an unrelated class, or no handler keeps the hit. A nested def counts only where it is called by bare name, under that call's handlers. See `package_class_parents` and `class_lineage` in `auditor/errorsites.py`, and `nested_call_sites` in `auditor/errorsites.py`.
- **`passthrough-shim` (2026-11-01):** only real forwarding is flagged. Every keyword value must be a bare parameter of the wrapper, no parameter may be passed twice (`table.get(name, name)` computes), and a decorated function is skipped, since the decorator registers it for something else (a fixture, a command, a route). A `**` keyword or a computed value keeps the function out of the rule too. See `check` in `src/auditor/catalogue/rules/passthrough-shim/check.py`.
- **`non-alphabetical-literal` (2026-11-01):** an `__all__` assignment also passes when its members are in the order ruff's RUF022 writes: SCREAMING_SNAKE names first, then CamelCase, then the rest, each group in natural order. Any other name keeps the plain `sorted()` test, and so does an `__all__` in neither order. See `ruff_dunder_all_key` in `src/auditor/catalogue/rules/non-alphabetical-literal/check.py` and `is_dunder_all_assignment` in `auditor/core.py`.
- **T2 candidate rule (2026-11-20):** T2's lister reads "domains that are well-defined (data shapes, config combinations)" as a function that is pure (no side effects, yields or awaits), has fully annotated parameters and a non-`None` return type, and uses only well-defined types (builtins, and the package's own data classes and config shapes), with logic a property can test. Methods taking `self` or `cls` are not candidates. See `is_t2_candidate` in `auditor/phaseb/candidates.py`. The brief's threshold, not the lister, decides whether a candidate is flagged.
- **A9 (2026-11-22):** the Phase B predicate does not read `check_` as a pure prefix for a function the project registers as a check, by membership of its check registry or a decorator that registers it. A registered check validates by reading the tree and reporting what it finds, so its name promises a check, not purity. The registration is the positive evidence; the prefix alone is not. Decided on 2026-11-21 (`agents/audit-reviews/review-1.md`, D3). A9 has no script check, so the carve-out lives only in the predicate's text.
- **D2 (2026-10-31):** the Phase B predicate skips a declared dependency the project runs as a command (a pre-commit hook, a CI `run:` step, a `subprocess` call in its own code). Such a tool is used without being imported, and flagging it made each audit re-raise a finding the user had declined. D2 has no script check, so the carve-out lives only in the predicate's text.
- **D2 (2026-11-02):** the Phase B predicate also skips a declared dependency a declared host tool loads as a plugin or theme, shown by an entry point in a group that host loads: `pytest11` for pytest, and `mkdocs.themes` or `mkdocs.plugins` for mkdocs when `mkdocs.yml` names the entry. The entry point is the positive evidence; a name that looks like a plugin's is not. As before, the carve-out lives only in the predicate's text.
- **D2 (2026-11-21):** the Phase B predicate also skips a type-stub package (`*-stubs`, `types-*`) when the project runs a type checker, and a Jupyter kernel package when a declared dependency executes notebooks (`nbclient`, `nbconvert`, `papermill`, `nbmake`). The type checker's run and the executor's declaration are the positive evidence; the package's name alone is not. Decided on 2026-11-21 (`agents/reviews/checker-requests-2026-11-21.md`, D13).

## Rule conflict resolution

A rule conflict exists when fixing a finding under rule X creates a finding under rule Y on the same code (e.g. `A18 callbacks-open-file-per-event` says move `mkdir` from `on_log` into `__init__`; `constructor-disk-io` then fires on the new location).

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

### Conflicts with no winner

Some conflicts are settled by removing the code both rules fire on, not by
accepting one of them. Neither rule is auto-accepted at these sites.

| Rules | Site pattern | Ruling |
|-------|--------------|--------|
| `broad-except-wrong-level` and `logger-exception-graceful-degradation` (A19) | a handler for `Exception`, `BaseException` or a bare `except` that logs and then returns a default so the run carries on | Remove the handler and let the failure propagate, as the coding standard's "let unexpected exceptions propagate" asks. Do not change the logger level: `logger.warning` fires the first rule and `logger.exception` the second, so each change swaps one hit for the other. If the failure is expected and recoverable, catch that specific exception type and log it with `logger.warning`; neither rule fires on that. If the user decides a broad handler has to stay, keep `logger.exception`, since a failure nobody named is by definition unexpected and its traceback is wanted, and accept `logger-exception-graceful-degradation` with a scoped marker giving the user's reason. |

Background: an audit found broad handlers in a pipeline orchestrator that
could satisfy neither rule. Its decision was answered by removing the handlers
rather than picking a winner, and this ruling generalises that answer
(2026-10-14).

## Severity guide

- **High:** security vulnerabilities, crashes, data loss, spec contradicts implementation on critical behaviour
- **Medium:** standards violations with real maintenance cost (widespread duplication, broken error reporting), missing tests for complex logic, docs out of date
- **Low:** local style nitpicks, minor doc gaps, suggestions for clarity

## Why this skill is structured this way

Earlier iterations relied on Claude to run greps and AST walks by hand, which agents reliably skipped, sampled, or silently filtered. The script fixed Phase A: agents cannot fake what a subprocess outputs. Acceptance is explicit (inline comment or AGENTS.md), not a decision-note argument.

A first Phase B fix replaced "report every concern" with a fixed checklist; that closed one source of variance but left four others that kept one project's audits from converging for dozens of cycles:

1. **Per-file fan-out** spread judgment thresholds across reviewers (one agent's "yes" was another agent's "no" on the same predicate). Cured by per-question fan-out.
2. **Category-restricted runs** meant each lens found new things in code that prior lenses had ignored. Cured by always running every category in one pass.
3. **Script-coverage backlog** as a perpetual queue meant every cycle shipped one new check (catch-up debt) AND one new queued item (next cycle's debt). Cured by draining or rejecting the backlog before any audit cycle starts.
4. **Predicate drift** silently expanded "should-have-caught" sets between cycles. Cured by locking each predicate's enumeration in this file.
5. **Rule conflicts** (fix under rule X triggers rule Y) ping-ponged forever. Cured by named-winner conflict resolution with auto-accept on the loser.

With these five fixes, a single audit on unchanged code produces the same finding set as the next audit on unchanged code. The audit converges in one pass, not 34.
