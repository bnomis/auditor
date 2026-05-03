---
name: auditme
description: Perform a structured code, spec and documentation audit with findings and recommendations
when_to_use: |
    Use this skill whenever the user mentions:
        - audit the code
        - code audit
        - full code review
        - review the codebase
        - audit the docs

allowed_tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion, Skill]
---

# auditme

Invoke as:
    /auditme [scope] [--category <category>]

`[scope]` is optional. With no argument, audit the full project (specs, source, docs). With a path or spec name, restrict the scope.

`--category` restricts the interpretive review (step 4) to one of: `standards`, `architecture`, `performance`, `security`, `testing`, `dependencies`, `documentation`. The mechanical sweep (step 3) always runs in full.

## Core principle

The audit must find every mechanical issue in one run. If a finding surfaces on run 2 on unchanged code, the audit failed. To make this reliable, the mechanical checks are a Python script (`checks/audit.py`, shipped with this skill) that you run and transcribe. You do not run the mechanical checks yourself - agents reliably skip, sample, or silently filter greps and AST walks.

Only interpretive findings (logic bugs, spec drift, architectural concerns) require reading.

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
3. Read source modules in scope
4. Read coding-standards rule files referenced by AGENTS.md
5. Read tests for modules in scope
6. Read user docs in `docs/`
7. Read `agents/audit-reviews/summary.md` if present. Note unresolved findings - step 6 re-verifies them.
8. Grep for `- [ ]` in `agents/tasks/audit-reviews/*.md`; read only files with incomplete items.

### 3. Mechanical sweep (scripted)

Run the shipped audit script:

```bash
python3 ~/.claude/skills/auditme/checks/audit.py <project-root> [--package <pkg>]
```

Where `<project-root>` is the directory containing `src/` and `agents/`. `--package` defaults to the single directory under `src/`.

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
4. You may NOT filter, sample, or dismiss `accepted: false` hits for any other reason. "Pre-existing", "project norm", "seems intentional" are NOT acceptable dismissals. If you believe a hit is legitimate, either:
   - fix the code in the same worktree (if the fix is tiny and obvious), OR
   - add an inline `# auditme: accept <reason>` comment at the hit site and re-run the script (the hit will flip to `accepted: true` on re-run), OR
   - add an entry to `AGENTS.md` (see "Acceptance mechanism" below) and re-run the script.

**What the script catches:**

Standards / syntactic drift:
- ruff (check + format)
- wildcard imports, `from __future__`, aliased imports, legacy typing generics, `.format()` / `%`-style formatting, stdlib `logging`
- relative imports outside `__init__.py`, `def`/`class` inside `__init__.py`, `from typing import` outside `__init__.py`
- 8 leading-underscore variants (module def/class, UPPER constants, lower constants, `self._x`, destructured LHS, both for-loop positions, attribute access)
- in-function imports (classified stdlib / first-party / third-party; AGENTS.md table auto-accepts)
- silent broad-except (no logger, no raise)
- caught-exception interpolated into f-strings or logger positional args
- literal duplication (same tuple/list/set/frozenset of strings in 2+ locations, anywhere)
- non-alphabetical enum-like literals at module scope
- unused `import X.Y.Z` submodule imports (ruff F401 misses these)
- paired sibling helpers with structurally identical bodies (cross-file `is_X` / `_is_X` duplication)
- duplicated words in comments / docstrings (typos like "the the")
- lockfile drift

Architecture / structural drift:
- **layering violations** (parsed from AGENTS.md "Package layering" section + accepted-exceptions table)
- **broad-except wrong level** (broad-except body uses `logger.warning`/`logger.error`/`logger.info`/`logger.debug` instead of `logger.exception`)
- **mixed raise types** (one method raises both stdlib (`RuntimeError`/`ValueError`) and project error types - callers cannot establish a clean catch envelope)
- **migration-shim consumers** (a module re-exports `X = canonical.X`; the script flags every other module that imports `X` via the shim instead of the canonical home)
- **constructor disk I/O** (`__init__` calls `open()`, `read_text`, `mkdir`, `iterdir`, etc.)
- **pass-through shim functions** (function whose body is exactly `return f(<args>)` with the same parameter names)
- **empty `__init__.py` while siblings export** (a subpackage exports nothing while at least one sibling exports >=5 symbols - inconsistent public-surface contract)

Architecture findings the script CANNOT catch are listed in the [Architecture](#architecture) interpretive checklist below.

### 4. Interpretive review (per-file reading)

Things the script cannot catch: logic bugs, spec contradictions, architectural concerns, missing tests for complex code, behavioural mismatches, docs that are wrong vs the implementation.

1. Use `Glob` to build the file list in scope
2. Divide files across multiple agents (parallel)
3. Each agent reads each file end-to-end and evaluates against the [Interpretive checklist](#interpretive-checklist) below, restricted by `--category` if present
4. Track every file read - the list goes in the review file

Do not substitute reading with grep-or-AST: that is Phase A's job. Phase B requires reading.

### 5. Spec review

For each spec in scope, check it against the validation criteria and spec template in `agents/skills/specdev/SKILL.md`. Record gaps as findings. Skip if no specs in scope.

### 6. Re-verify prior findings

For each unresolved finding in `summary.md`, grep or read to confirm: still present, or now resolved. If resolved, mark the finding closed in `summary.md` and (if applicable) mark the corresponding task file done.

For each incomplete task in `agents/tasks/audit-reviews/*.md`, verify against source: actually incomplete (re-flag in the review) or shipped (mark done in the task file).

### 7. Completion gate

Before writing the review file, confirm:

- [ ] `checks/audit.py` was executed and its full JSONL output saved
- [ ] Every `accepted: false` hit appears in the review (no sampling, no silent dismissals)
- [ ] Phase B read every file in scope end-to-end; the file list is written
- [ ] Every unresolved summary.md finding was re-verified
- [ ] Every incomplete task file was re-verified against source

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
2. **AGENTS.md table row** pairing the importer and imported module in backticks (for in-function imports). Any table with two `|`-separated columns where the first column's backticked module matches the importer and the second column's backticked module matches the imported module counts.

Nothing else acts as acceptance - not a decision note under `agents/audit-reviews/`, not a prior review that "agreed" the pattern is fine, not an assumption about HF / sklearn / PEP conventions. If the user wants to accept a pattern:

- One site: inline `# auditme: accept <reason>` comment
- Many sites of the same class: AGENTS.md entry OR loop through each site adding the comment

A prior decision note (e.g. `leading-underscore-decision.md`) is not enough. If the user wants to accept leading-underscore privacy project-wide, the fix is an AGENTS.md entry plus a pre-commit or `# auditme: accept` convention - not a decision note the script cannot read.

## Interpretive checklist

Phase B (step 4) reading-level checks. Mechanical items moved to the script; these remain because they require judgement.

### Coding standards

- All function signatures have parameter and return type annotations (visible on read)
- Naming follows project conventions where ambiguous (PascalCase for types; UPPER_SNAKE_CASE for constants)
- TYPE_CHECKING block placement matches idiom in the rest of the tree
- Project coding rules not covered by the script (check `AGENTS.md` and referenced rule files)

### Architecture

The script catches the mechanical patterns: layering violations (parsed from AGENTS.md), broad-except using the wrong logger level, mixed raise types within one method, migration-shim consumers, constructor disk I/O, pass-through shim functions, empty `__init__.py` while siblings export. Phase B's job is what reading reveals that grep cannot:

**Error envelope review.** For every `with` block, every `try/except`, every external-service call (HTTP, MLflow, S3, database, subprocess, file system in CLI entry points), trace the error path:
- What exception types can the call raise?
- Are they caught at the right layer?
- Does the catch translate to a project error type, or does the third-party exception leak?
- If the call is in a context manager, does its `__enter__` failure abort more work than intended? (e.g. `open_batch_run` failing inside `with` aborts the whole training run)
- Does the error message preserve enough context to debug, without leaking sensitive data?

**Orchestration review.** For every multi-stage operation (e.g. `load_data -> tokenize -> train -> evaluate`), check:
- Stage ordering: does each stage's prerequisite get checked, or is there a silent fallback that masks a programming error?
- Two paths to the same data: is `config.input_path` ever both patched onto a config AND passed explicitly? When the two diverge, which wins?
- Is there a single source of truth for each piece of state, or is it written in two places that can drift?
- Do CLI commands share a `pipeline -> finalise -> report` skeleton? If so, is it factored into a helper or duplicated?

**API surface review.** For every `__init__.py` that has an `__all__`:
- Is every symbol in `__all__` actually used outside the package? `grep -rn "from <pkg> import" outside the package`
- Are internal helpers (`flatten`, `merge_layers`, `coerce_types`) exposed by accident?
- Conversely, when `__init__.py` is empty, do consumers reach into private submodules? The empty surface is itself a contract that "anything inside is public".
- For Settings / dataclasses: do consumers construct them, or only read them? If only read, narrowing the public surface to read-only views is cheap.

**Naming vs implementation.** For every predicate function (`is_X`, `has_X`, `should_X`):
- Does the body actually answer the question the name asks?
- A function called `side_channel_active(config)` returning `enabled and imputation != 'median'` is a latent bug. Split into two predicates.

**Single-responsibility for `__init__`.** Constructors should accept already-loaded data, not perform I/O. The script catches `open()`, `read_text`, `mkdir`, `iterdir`. Phase B catches: subprocess calls, network calls, expensive computation, side effects on global state.

**Implicit state mutations.** For every method that takes a `config` argument: does it mutate the config? Does it persist a mutated copy? Is the mutation point obvious?

### Performance

- No obvious O(n^2) patterns on large inputs
- No blocking I/O in hot paths
- No redundant file reads or repeated expensive computations

### Security

- No secrets / API keys in source
- Input validation at system boundaries
- No command injection (unsanitised input in shell calls)
- No path traversal
- Environment variables used for sensitive config

### Testing

Assess by reading test files - do not run the suite.

- Test files exist for modules with complex logic
- Functions with branching / error handling / state transitions have test cases
- Property-based tests where input domains are well-defined

### Dependencies

- Every dependency declared in `pyproject.toml`
- No unused dependencies (import graph vs declared)
- `uv.lock` present and coherent (the script already checks drift)

### Documentation coherence

- `AGENTS.md` project structure matches actual directory layout
- `AGENTS.md` tools and libraries list is current
- `README.md` consistent with `AGENTS.md`
- Specs in `agents/specs/` match implementations (drift detection)
- User docs in `docs/` match the implementation (drift detection)

## Review template

```markdown
# Audit Review N

**Date:** YYYY-MM-DD
**Scope:** <"full" or specific modules/specs>
**Script output:** /tmp/audit-<project>.jsonl (N hits, M accepted, K new findings)

## Summary

<2-3 sentences. Mention script hit counts by rule and the interpretive findings.>

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

### Rule: <next rule>

...

## Interpretive findings (from per-file reading)

### Finding: <title>

- **Category:** standards / security / performance / testing / documentation / architecture
- **Severity:** high / medium / low
- **Location:** `path:line` (or "project-wide")
- **Description:** <what the issue is, why reading reveals it, why the script could not>
- **Recommendation:** <concrete action>

## Files reviewed (Phase B)

Every file read end-to-end in step 4.

- `src/example/module.py` - checked: standards, security, testing
- ...

## Prior findings re-verified

From summary.md's unresolved list:

- <title> - resolved at `path:line` / still present at `path:line`
- ...

## Recommendations

Prioritised by severity.

## Clean categories

Categories where Phase B found nothing. The mechanical sweep's zero-hit rules are implicit (see script output).
```

## Summary template

```markdown
# Audit Summary

**Last updated:** YYYY-MM-DD
**Last review:** review-N
**Total reviews conducted:** N
**Last script run hit count:** K (J accepted)

## Unresolved findings

Findings from prior reviews not yet addressed.

### <title>

- **Rule or category:** <script rule family / interpretive category>
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

Patterns that have appeared across multiple reviews even when individual instances were fixed. Candidates for AGENTS.md entries, pre-commit rules, or script extensions.

- <pattern> (reviews N, M, P)

## Script coverage notes

If the script missed a class of drift that interpretive review caught, note here so it can be added to `checks/audit.py`:

- <rule class> - first seen in review-N. Candidate predicate: <sketch>.
```

## Extending the script

When Phase B surfaces a new class of greppable drift that the script does not catch, add a check function to `~/.claude/skills/auditme/checks/audit.py` and call it from `main()`. The pattern:

```python
def check_NEW_RULE(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        # walk / grep / parse; for every hit:
        accept = _accept_reason(lines, lineno)
        _emit(
            rule="new-rule-name",
            variant="variant name",
            path=rel,
            line=lineno,
            evidence=snippet[:200],
            accepted=bool(accept),
            accepted_reason=accept,
        )
```

Then add `check_NEW_RULE` to the tuple in `main()`. The next audit run catches every instance mechanically.

This is how the script grows: never re-derive the predicate in a review, always add it to the script so the next audit inherits it automatically.

## Severity guide

- **High:** security vulnerabilities, crashes, data loss, spec contradicts implementation on critical behaviour
- **Medium:** standards violations with real maintenance cost (widespread duplication, broken error reporting), missing tests for complex logic, docs out of date
- **Low:** local style nitpicks, minor doc gaps, suggestions for clarity

## Why this skill is structured this way

Previous iterations of this skill relied on Claude to run greps and AST walks by hand. Agents reliably:

- skipped checks they found tedious
- silently sampled rather than enumerated
- accepted hits as "pre-existing" without written justification
- claimed to have run AST walks they never ran
- dismissed whole finding classes with filters ("members >= 3") to reduce output

Five consecutive reviews of featmo (60-64) and four of feathf (18-21) each surfaced new findings on substantially-unchanged code. Every finding existed in prior audits; each round sampled a different slice.

The fix: ship the mechanical work as a script. Agents can't fake what a subprocess outputs. Acceptance is explicit (inline comment or AGENTS.md), not a decision-note argument. The skill is now short because it no longer needs to coach agents through dozens of rule families - the script encodes them.

If a new drift class appears, extend the script (`checks/audit.py`) rather than adding prose to this file.
