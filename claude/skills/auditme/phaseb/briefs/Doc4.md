# Doc4 brief

**Brief version:** 6

You are a reviewer for one batch of a listed audit question. Judge each
candidate in the batch on its own and report one verdict per candidate.

## Security

Never list environment variables (`env`, `printenv`, `set`) or print an env
file. To test that a variable is set, use `[ -n "${VAR:-}" ]` and print only
yes or no.

## The question

**Doc4. Specs match implementation.** Drift between `agents/specs/` and `src/`.

## Input

The batch file holds one JSON object per line, one per candidate. Each has
`id` (`<document>::<heading path>::<target id>`), `path`, `start` and `end`
(the section's lines), and a `payload` with the target (what the section's
name resolved to) and each line of the section that names it. A candidate
whose id ends in `::(unresolved)` is a section with tokens that resolved to
nothing or to more than one definition; its payload lists each token with its
line and any definitions found.

Read the section and the target's source, and judge the section's statements
against the code.

## Thresholds

- Drift is a statement the target's code contradicts: a name, parameters,
  defaults, a return, errors raised, a setting's type or default, an option's
  default, or a file's existence or role.
- Not drift: an omission, unless the section presents a list as complete; a
  dated record or decision; a shorter type spelling; a difference in the
  parameter list, which the sweep's `spec-api-signature-drift` rule reports.
- For an `(unresolved)` candidate, drift is a name the code once had or
  plainly means. A standard-library or third-party name, a command, a value,
  an environment variable, a path outside the repository, or a path created
  at run time is not drift.
- A section or table that states its own date ("as classified on
  <date>", "measured on <date>") is a record of that day: its names, counts
  and line numbers are not checked against today's code, and nothing in it
  is drift.
- For an `(unresolved)` candidate, its section's other statements are
  judged by the thresholds above as well, not only its unresolved tokens.
- A dated sentence inside an undated section is a record of that day for
  its own statements only; the section's other statements are judged.
- "Today" in an implemented spec is not a date: a sentence using it is
  judged against the code like any other.
- A drift that falls under several candidates of one section is reported
  once, under the first of them in the batch's order whose span holds it.
- A spec's header `**Date:**` is when the spec was written; it does not
  date the sections, which are judged unless one states its own date.
- A statement worded as what the spec's own change did ("version 1 when
  written", "puts T1 and T2 on the listed path") is a record of that change,
  not drift. A statement worded as the current state ("the brief is at
  version 1", "the listed questions are ...") is judged.
- A reference to a `TODO.md` item is not drift while its heading is in
  `TODO.md` or `DONE.md`; it is drift only when the heading is in neither.
- A bullet or paragraph that opens with a date ("found on <date>",
  "measured on <date>") is a record of that day for every sentence in it.
- A table whose caption or lead sentence names the change or amendment it
  records is a record of that change, like a dated table.
- A date in a bullet's lead - its bold title and the parenthetical straight
  after it, as "**Title** (amendment 1.4, found on <date>)" - dates the
  bullet like an opening date.
- An instruction to the implementer of the spec's own change, and a draft
  docstring describing the code that change replaced, are records of the
  change, not drift.
- A reproduced file block, or a sentence naming what something has ("T1 has
  a, b and c"), presents itself as complete unless it is marked as an
  excerpt or written with "for example", "such as", "including" or "e.g.": an
  item the code also has is drift.
- A list of steps that is numbered, or joined by "then", presents an order: a
  different order in the code is drift. An unordered list is not.
- A spec's Motivation is a record of the state before its change, and an
  acceptance criterion tagged with an amendment ("1.4:") is a record of that
  amendment; neither is drift.
- A `Raises:` section in a spec's API block is the complete list of what the
  function declares: a declared error the code raises and the section lacks,
  or a missing section where the code declares one, is drift.
- When several candidates of a section share the span that holds a drift,
  report it under the candidate whose target the drift is about, and under
  the first in the batch's order only when none names it.

A threshold that this brief does not settle is not yours to decide: report
it in your reply, name the candidate, and judge the rest as the brief says.

## Output

Write one JSON line per candidate to the result file you are given, with
exactly these keys:

- `id`: the candidate's `id`;
- `findings`: `{"drift": [...]}`, where `drift` holds one string per
  drifting statement, each as `path:line` and what the code does instead,
  and is an empty list when there is none;
- `reason`: one sentence on why.

Every candidate in the batch gets exactly one line, including those with an
empty `drift`.
