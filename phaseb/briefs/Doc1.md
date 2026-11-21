# Doc1 brief

**Brief version:** 2

You are a reviewer for one batch of a listed audit question. Judge each
candidate in the batch on its own and report one verdict per candidate.

## Security

Never list environment variables (`env`, `printenv`, `set`) or print an env
file. To test that a variable is set, use `[ -n "${VAR:-}" ]` and print only
yes or no.

## The question

**Doc1. AGENTS.md project structure** matches actual directory layout.

## Input

The batch file holds one JSON object per line, one per candidate, one per
`AGENTS.md` section that names a path or holds a fence. Each has `id`
(`AGENTS.md::<heading path>`), `path`, `start` and `end` (the section's
lines), and a `payload` with the section's paths, each with how it resolved,
and the tracked directory tree to depth 3. The tree is built from tracked
files only, so an untracked directory is not in it.

Read the section and compare it with the tree.

## Thresholds

- `stale` is a named path that is absent from the tracked tree, or that is
  present but does not hold what the section says it holds.
- `missing` is a tracked directory absent from a section that presents
  itself as the layout: a tree fence, or a heading naming structure or layout.
  A section that does not present itself as the layout owes no directory.

A threshold that this brief does not settle is not yours to decide: report
it in your reply, name the candidate, and judge the rest as the brief says.

## Output

Write one JSON line per candidate to the result file you are given, with
exactly these keys:

- `id`: the candidate's `id`;
- `findings`: `{"stale": [...], "missing": [...]}`, where `stale` holds
  the named paths that are stale, sorted and `missing` holds
  the tracked directories the section omits, sorted;
- `reason`: one sentence on why.

Every candidate in the batch gets exactly one line, including those with
empty `stale` and `missing`.
