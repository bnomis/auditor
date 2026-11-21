# Doc2 brief

**Brief version:** 2

You are a reviewer for one batch of a listed audit question. Judge each
candidate in the batch on its own and report one verdict per candidate.

## Security

Never list environment variables (`env`, `printenv`, `set`) or print an env
file. To test that a variable is set, use `[ -n "${VAR:-}" ]` and print only
yes or no.

## The question

**Doc2. AGENTS.md tools and libraries list** is current.

## Input

The batch file holds one JSON object per line, one per candidate, one per
`AGENTS.md` section holding a backticked token. Each has `id`
(`AGENTS.md::<heading path>`), `path`, `start` and `end` (the section's
lines), and a `payload` with each token matched against the declared
distributions, the pre-commit hook ids and the top-level modules the corpus
imports, plus the tokens that matched none.

Read the section and compare it with those inventories. Look in the
project's own files for a token that matched none.

## Thresholds

- `stale` is a named tool or library that is no longer declared, imported
  or run (run in the sense of audit question D2: a hook, a CI `run:` step or
  a `subprocess` call), or a version that differs from its pin.
- `missing` is a declared dependency or hook absent from a section that
  presents itself as the tools or libraries list. A section that does not
  present itself as that list owes none.

A threshold that this brief does not settle is not yours to decide: report
it in your reply, name the candidate, and judge the rest as the brief says.

## Output

Write one JSON line per candidate to the result file you are given, with
exactly these keys:

- `id`: the candidate's `id`;
- `findings`: `{"stale": [...], "missing": [...]}`, where `stale` holds the
  stale tools or libraries, sorted, and `missing` holds the declared
  dependencies or hooks the section omits, sorted;
- `reason`: one sentence on why.

Every candidate in the batch gets exactly one line, including those with
empty `stale` and `missing`.
