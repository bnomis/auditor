# Doc5 brief

**Brief version:** 2

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

## Thresholds

- Drift is a statement the target's code contradicts: a name, parameters,
  defaults, a return, errors raised, a setting's type or default, an option's
  default, or a file's existence or role.
- An example in the section that would fail against the code is drift.
- Not drift: an omission, unless the section presents a list as complete; a
  dated record or decision; a shorter type spelling; a difference in the
  parameter list, which the sweep's `spec-api-signature-drift` rule reports.
- For an `(unresolved)` candidate, drift is a name the code once had or
  plainly means. A standard-library or third-party name, a command, a value,
  an environment variable, a path outside the repository, or a path created
  at run time is not drift.

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
