# Doc2 brief

**Brief version:** 4

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

A line may also have `earlier`, the verdict this candidate last had
(`findings`, `reason`, `brief_version`, `judged`). Judge the candidate on its
own, then compare: if your verdict differs from `earlier`, say in `reason`
what changed your judgement.

## Thresholds

- `stale` is a named tool or library that is no longer declared, imported
  or run (run in the sense of audit question D2: a hook, a CI `run:` step or
  a `subprocess` call), or a version that differs from its pin.
- `missing` is a declared dependency or hook absent from a section that
  presents itself as the tools or libraries list. A section that does not
  present itself as that list owes none.

A case this brief does not settle is not a finding: judge it not flagged,
name the candidate and the case in your reply, and judge the rest as the brief
says. Every reviewer gives an unsettled case the same verdict, so it does not
depend on the batch; the operator settles a reported case when it should count.

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
