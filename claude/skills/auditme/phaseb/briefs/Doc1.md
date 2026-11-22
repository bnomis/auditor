# Doc1 brief

**Brief version:** 5

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

A line may also have `earlier`, the verdict this candidate last had
(`findings`, `reason`, `brief_version`, `judged`). Judge the candidate on its
own, then compare: if your verdict differs from `earlier`, say in `reason`
what changed your judgement.

## Thresholds

- `stale` is a named path that is absent from the tracked tree, or that is
  present but does not hold what the section says it holds.
- `missing` is a tracked directory absent from a section that presents
  itself as the layout: a tree fence, or a heading naming structure or layout.
  A section that does not present itself as the layout owes no directory.
- A named path the section itself calls ignored or local, and that the
  repository's `.gitignore` ignores, is not stale for being absent from the
  tracked tree. Check the `.gitignore` entry; a path with none is stale.

A case this brief does not settle is not a finding: judge it not flagged,
name the candidate and the case in your reply, and judge the rest as the brief
says. Every reviewer gives an unsettled case the same verdict, so it does not
depend on the batch; the operator settles a reported case when it should count.

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
