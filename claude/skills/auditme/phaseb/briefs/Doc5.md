# Doc5 brief

**Brief version:** 8

You are a reviewer for one batch of a listed audit question. Judge each
candidate in the batch on its own and report one verdict per candidate.

## Security

Never list environment variables (`env`, `printenv`, `set`) or print an env
file. To test that a variable is set, use `[ -n "${VAR:-}" ]` and print only
yes or no.

## The question

**Doc5. User docs match implementation.** Drift between `docs/` or `README.md` and `src/`.

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

A line may also have `earlier`, the verdict this candidate last had
(`findings`, `reason`, `brief_version`, `judged`). Judge the candidate on its
own, then compare: if your verdict differs from `earlier`, say in `reason`
what changed your judgement.

## Thresholds

- Drift is a statement the target's code contradicts: a name, parameters,
  defaults, a return, errors raised, a setting's type or default, an option's
  default, or a file's existence or role.
- An example in the section that would fail against the code is drift.
- Not drift: an omission, unless the section presents a list as complete; a
  dated record or decision; a shorter type spelling; a call example
  naming one keyword only, which does not present itself as the full list.
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
- An example of output the code prints is presented whole: one that leaves
  out a line the code prints, or shows a line differently, is drift.
- A list of the values a field or setting takes, written without "for
  example", "such as" or "including", presents itself as complete: a value
  the code also produces is drift.
- A call example in `README.md` or `docs/` that names more than one
  keyword of a public function presents itself as the full keyword list: a
  keyword the function takes and the example lacks is drift. The sweep's
  `spec-api-signature-drift` rule reads only a spec's `## API` block, so it
  does not cover a guide.
- A dated sentence inside an undated section is a record of that day for
  its own statements only; the section's other statements are judged.
- "Today" in an implemented spec is not a date: a sentence using it is
  judged against the code like any other.
- A drift that falls under several candidates of one section is reported
  once, under the first of them in the batch's order whose span holds it.
- A parenthetical list, and a list of the conditions under which a command
  fails or exits, present themselves as complete unless written with "for
  example", "such as", "including" or "e.g.": a case the code also has is
  drift.
- A claim broader than the code is drift: a statement that a command acts on
  "any existing file" when the code checks named files only is one the code
  contradicts.
- A list of causes under a symptom ("The Stop hook does not fire") is a list
  of the conditions that produce it, and presents itself as complete unless
  marked.
- Inline JSON in a sentence shows keys and values, which are judged; its line
  breaks and spacing are not. Only an example in a code block is judged line
  for line.
- Words before a list ("any failure:") do not mark it as examples; only "for
  example", "such as", "including" or "e.g." do.
- A claim narrower than the code is an omission, unless it states its scope
  as the whole ("only", "just", "never") or the guide nowhere describes the
  rest; then it is drift.
- A list inside a note or warning box follows the same rule as any other
  list.
- A row or section that describes a project set up by the project's setup
  skill is judged against that skill's template; one that describes the
  published hooks is judged against the manifest. The section's own wording
  is the evidence.
- A "Stops for" list in a skill's reference lists the conditions under
  which the skill stops, and is complete unless marked.
- A tool the repository runs from another repository, pinned to a commit, is
  judged against that pinned version when it can be read; when it cannot, the
  description is not judged, and the reviewer says so.

A case this brief does not settle is not a finding: judge it not flagged,
name the candidate and the case in your reply, and judge the rest as the brief
says. Every reviewer gives an unsettled case the same verdict, so it does not
depend on the batch; the operator settles a reported case when it should count.

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
