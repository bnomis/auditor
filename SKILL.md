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

# Code audit

Invoke as:
    /auditme [scope] [--category <category>]

Where `[scope]` is an optional argument specifying what to audit. If no argument is provided, perform a full audit of the entire project.

The `--category` flag restricts the audit to a single checklist category. Valid categories:

- `documentation` -- documentation coherence
- `standards` -- coding standards
- `security` -- security
- `testing` -- testing
- `performance` -- performance
- `dependencies` -- dependencies
- `architecture` -- architecture

When `--category` is provided, only that category is evaluated during the manual audit (step 4). All other workflow steps (context gathering, automated checks, spec review, etc.) still run as normal, but findings are limited to the selected category. The review file title should include the category name (e.g. "Audit Review N (security)").

Scope examples:

- `/auditme` -- full audit (all specs, all source, all docs)
- `/auditme src/<project>/<file>.py` -- audit a single module
- `/auditme <spec>` -- audit a spec and its implementation
- `/auditme docs` -- audit user docs match the implementation
- `/auditme --category security` -- full scope, security category only
- `/auditme src/<project>/<file>.py --category testing` -- single module, testing only

## Workflow

### 1. Establish scope

- **Full audit** (no argument): audit `agents/specs/`, `src/`, `docs/`, `AGENTS.md`, and `README.md`
- **Module audit** (file path given): audit that module, its tests, and any spec that references it
- **Spec audit** (spec name given): resolve to `agents/specs/<SLUG>/spec.md`, audit the spec and its implementation
- **Docs audit**: audit the user documentation in `docs/`, ensure it matches the implementation

If `--category <category>` is present, record the selected category. This does not change the file scope — it restricts which checklist categories are evaluated in step 4.

See the `specdev` skill for `slugification` rules

### 2. Gather context

Spawn multiple agents to do the following:

1. Read `AGENTS.md` and `README.md`
2. Read `agents/specs/index.md` (if it exists) to discover all specs
3. Read the source modules in scope
4. Read rules for coding standards
5. Read existing tests for modules in scope
6. Read use docs in `docs/`
7. Read the audit summary file `agents/audit-reviews/summary.md` (if it exists) to understand prior findings and avoid repeating them. **Do not read individual review files** — the summary is the single source of truth for prior audit history.
8. Grep for incomplete tasks (`- [ ]`) across files in `agents/tasks/audit-reviews/`. Read **only** the files that contain incomplete items. Do not read task files where all items are complete.

### 3. Run automated checks

1. Run `ruff check` on source files in scope -- record any violations
2. Run `ruff format --check` on source files in scope -- record any formatting issues

If ruff reports violations, add a single finding summarising the count and list up to 5 examples. Do not list every violation individually.

### 4. Manual audit

Audit **file-by-file**, not category-by-category. This ensures every file is explicitly reviewed and nothing is skipped due to LLM attention drift.

1. Use `Glob` to build a complete list of source files in scope (e.g. `src/**/*.py`)
2. Divide the files between multiple agents to iterate through each file in the list:
   a. Read the file
   b. If `--category` was specified: evaluate only that category from the [Audit checklist](#audit-checklist) below
   c. If no `--category` was specified: evaluate against **every applicable category** in the checklist
   d. Record all findings with category, severity, location, and a concrete recommendation
3. Track which files you have reviewed — this list is written to the review file (see [Review template](#review-template))

Do not move on from a file until you have checked all applicable checklist categories against it. This prevents the common failure mode of scanning by category and missing files.

### 5. Spec review

For each spec in scope, check it against the validation criteria and spec template in `agents/skills/specdev/SKILL.md`. Do not invoke the `specdev` skill — perform the checks directly and record gaps as findings.

If there are no specs in scope, skip this step.

### 6. Write the review file

Write findings to `agents/audit-reviews/review-N.md` using the [Review template](#review-template) below.

To determine N: check existing files in `agents/audit-reviews/` and use the next available number starting from 1. If the directory does not exist, create it.

**Do not overwrite existing review files.** Always increment N.

Update `agents/audit-reviews/index.md` with the new review file entry (create the index if it doesn't exist)

If you detected incomplete tasks in the context gathering phase, do not assume they are not done, check the source code of the implementation to confirm if they have been done or not. If the implementation is complete modify the previous task files to mark the tasks as done so we don't find them again. If the tasks are not done add a section to the review file to complete the work.

### 6a. Update the audit summary

After writing the review file, update `agents/audit-reviews/summary.md`. This file is a **rolling summary** that replaces the need to read all prior reviews. It must follow the [Audit summary template](#audit-summary-template) below.

Update process:

1. Read the current `summary.md` (if it exists)
2. **Remove** any previously-unresolved findings that this review confirmed are now fixed
3. **Add** new findings from review-N that have not yet been addressed
4. Update the metadata (last review number, date, total reviews conducted)
5. Write the updated `summary.md`

If `summary.md` does not exist, create it from scratch using only the current review's findings. Do not backfill from old review files — the summary starts fresh and accumulates going forward.

### 7. Act on findings

- **If there are recommendations for improvements:** use the `taskdev` skill to create a task list.

```
/taskdev agents/audit-reviews/review-N.md
```

- **If there are no recommendations:** tell the user where the review file was written.

### 8. Version control

1. Check for uncommitted changes with `git status`
2. If uncommitted changes exist, ask the user if they want to commit them first
3. After writing the review, stage it: `git add agents/audit-reviews/review-N.md agents/audit-reviews/summary.md agents/audit-reviews/index.md`
4. Also stage any task files that were modified (marked as done) during the review
5. Ask the user if they'd like to commit
6. Commit with message: `"auditme: add review-N"`
7. Do not push unless the user asks

## Review index

Maintain an index at `agents/audit-reviews/index.md`. When creating or updating a review, add or update its entry. If the index does not exist, create it.

Format:

```markdown
# Review Index

| Scope | Review | Date |
|-------|--------|------|
| full | [review-1.md](review-1.md) | 2026-03-19 |
```

## Audit checklist

Evaluate each category. Skip categories that are out of scope for a focused audit.

### Documentation coherence

- [ ] `AGENTS.md` project structure matches actual directory layout
- [ ] `AGENTS.md` development tools and libraries list is current
- [ ] `README.md` (if it exists) is consistent with `AGENTS.md`
- [ ] Specs in `agents/specs/` match their implementations (drift detection)
- [ ] User docs in `docs/` match the implementation (drift detection)
- [ ] Previous tasks in `agents/tasks/audit-reviews/` are done

### Coding standards

Ruff violations are captured in step 3. Verify the following in addition to ruff output:

- [ ] All function signatures have parameter and return type annotations
- [ ] Naming follows project conventions (snake_case, PascalCase, UPPER_SNAKE_CASE)
- [ ] f-strings used instead of `%` or `.format()`
- [ ] Imports follow isort ordering (stdlib, third-party, local)
- [ ] No wildcard imports
- [ ] Follows coding rules and standards

### Security

- [ ] No secrets, API keys, or credentials hardcoded in source
- [ ] Input validation at system boundaries (user input, external APIs)
- [ ] No command injection vectors (unsanitised input in shell calls)
- [ ] No path traversal vulnerabilities
- [ ] Environment variables used for sensitive configuration

### Testing

Assess by reading test files — do not run the test suite.

- [ ] Test files exist for modules with complex logic
- [ ] Functions with branching logic, error handling, or state transitions have corresponding test cases
- [ ] Property-based tests (hypothesis) used where input domains are well-defined

### Performance

- [ ] No obvious O(n^2) or worse patterns on potentially large inputs
- [ ] No unnecessary blocking I/O in hot paths
- [ ] No redundant file reads or repeated expensive computations

### Dependencies

- [ ] All dependencies declared in `pyproject.toml`
- [ ] No unused dependencies
- [ ] `uv.lock` is committed and up to date

### Architecture

- [ ] Modules have clear, single responsibilities
- [ ] No circular imports
- [ ] Public APIs are minimal and well-defined
- [ ] Error handling follows project convention (let unexpected exceptions propagate)

## Review template

```markdown
# Audit Review N

**Date:** YYYY-MM-DD
**Scope:** <what was audited -- "full" or specific modules/specs>

## Summary

<2-3 sentence overview of findings>

## Findings

### Finding 1: <title>

- **Category:** standards / security / performance / testing / documentation / architecture
- **Severity:** high / medium / low
- **Location:** `path/to/file.py:line` (or "project-wide")
- **Description:** <what the issue is>
- **Recommendation:** <concrete action to fix it>

### Finding 2: <title>

...

## Files reviewed

List every file that was explicitly read and audited during this review. This ensures coverage is visible and reproducible.

- `src/example/module.py` -- checked: standards, security, testing, performance, architecture
- `src/example/other.py` -- checked: standards, security, testing
- ...

## Recommendations

Prioritised summary of recommended actions, ordered by severity

## Clean categories

List categories that were checked and passed cleanly. Only include this section if there are categories with zero findings.
```

## Audit summary template

The summary file (`agents/audit-reviews/summary.md`) is a rolling document. It replaces the need to read all prior individual review files during context gathering, keeping context window usage bounded regardless of how many audits have been conducted.

```markdown
# Audit Summary

**Last updated:** YYYY-MM-DD
**Last review:** review-N
**Total reviews conducted:** N

## Unresolved findings

Findings from prior reviews that have not yet been fixed. Each entry records where it was first raised so it can be traced back if needed.

### <title>

- **Category:** standards / security / performance / testing / documentation / architecture
- **Severity:** high / medium / low
- **Location:** `path/to/file.py:line` (or "project-wide")
- **First raised:** review-N (YYYY-MM-DD)
- **Description:** <what the issue is>
- **Recommendation:** <concrete action to fix it>

### <title>

...

## Recently resolved

Findings confirmed fixed in the most recent 3 reviews. Older resolved findings are removed to keep this file concise.

| Finding | Severity | Raised in | Resolved in |
|---------|----------|-----------|-------------|
| <title> | medium | review-5 | review-8 |

## Recurring patterns

Patterns that have appeared across multiple reviews, even if individual instances were fixed. These indicate systemic issues worth addressing at the project level rather than file-by-file.

- <pattern description> (seen in reviews N, M, P)
```

## Severity guide

- **High:** security vulnerabilities, crashes, data loss, spec contradicts implementation on critical behaviour
- **Medium:** standards violations, missing tests for complex logic, documentation out of date, performance concerns
- **Low:** style nitpicks not caught by ruff, minor documentation gaps, suggestions for clarity
