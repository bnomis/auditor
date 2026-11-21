# Review: the three open checker requests

**Date:** 2026-11-21
**Review page:** https://claude.ai/artifact/TrXmZBz4YcGyzdu8gBUZA4

## What is being reviewed and how

`claude/skills/auditme/requests.md` has three entries under `## Open`, filed in
`dfc34b2` and each raised by an audit on 2026-11-21. The auditme skill lets no
audit start while any entry is open, and this repository's first audit waits
on them (`TODO.md`, "Ship or reject the three open checker requests"). Each
entry leaves the checker or skill by being shipped or rejected. This review
asks for one answer per decision below: pick an option, or flag it with a
comment. Nothing is built until every decision has an answer.

The recommendations follow one rule: settle a threshold the way that keeps a
reviewer's judgement smallest and the answer the same for every batch, and
prefer a brief or predicate change over a new check where the question needs
judgement a script would have to guess.

## Automatic checks

- `requests.md` `## Open` holds exactly these three entries (2026-11-21): pass.
- Brief versions on 2026-11-21, from each brief's `**Brief version:**` line:
  T1 1, A4 3, Doc4 3, Doc5 3. Each brief a ruling below changes moves to the
  next version, so the next audit re-judges that question's carried
  verdicts.

## Decisions

### D1. How a user guide's parameter list is checked (request 1)

- **Background:** Doc5's brief says "a difference in the parameter list" is not
  drift because the sweep's `spec-api-signature-drift` rule reports it, but
  that rule reads only `def` lines in a spec's `## API` block. A README or
  `docs/` example that calls a public function with one keyword per line is
  read by neither, so a parameter added to the function and missing from the
  guide passes both (seen 2026-11-21).
- **Affects:** `phaseb/briefs/Doc5.md`, or `checks/auditme/rules/project_hygiene.py`.
- **Options:**
  - **A (recommended): widen Doc5's threshold.** A call example in `README.md`
    or `docs/` that names more than one keyword of a public function presents
    itself as the full keyword list; a keyword the function takes and the
    example lacks is drift. Doc5 to the next version; the next audit
    re-judges every Doc5 candidate. No new check and no spec.
  - **B: extend `spec-api-signature-drift`** to calls of a uniquely named public
    function in fenced blocks of `README.md` and `docs/`. A spec amendment,
    tests, and a catch-up in every project; whether an example "presents
    itself as the full signature" is a judgement the rule would have to guess.
  - **C: reject**, with the reason recorded under `## Rejected`.

### D2-D12. Thresholds the listed briefs leave open (request 2)

- **Background:** in one audit on 2026-11-21, reviewers of different batches
  of the same listed question settled these in opposite ways, so verdicts
  differed by batch until the orchestrator re-judged them. Each ruling goes
  into the brief's Thresholds, with a version bump.
- **Affects:** `phaseb/briefs/T1.md`, `A4.md`, `Doc4.md`, `Doc5.md`, and for
  D7 the T1 lister in `checks/auditme/phaseb/testmap.py`.

| Id | Question | Recommended ruling | Alternative |
|---|---|---|---|
| D2 | T1: a test calls a package re-export of the candidate | counts: it is the same object | does not count |
| D3 | T1: a test calls through a `singledispatch` generic, a dispatch table or a parametrised name | covers each implementation the test's own arguments reach | never covers |
| D4 | T1: a dunder run by constructing, printing or attribute access | counts as a call of that dunder | only an explicit call counts |
| D5 | T1: a one-line `__str__` that forwards to `summary()` | a test of `str()` covers `__str__` only; a public `summary` needs its own test | covers both |
| D6 | T1: calls made from a helper defined in the test file | count as the calling test's own | do not count |
| D7 | T1 lister: a test file that imports only the top-level package which re-exports the candidate | listed in the candidate's `test_files` | left out, as now |
| D8 | A4: a `singledispatch` entry point's `Raises:` | owes the domain errors its registered implementations raise | owes only its own body's |
| D9 | A4: a raise the candidate's own checks make unreachable (an invariant guard) | not owed; name the guard in the `reason` | owed |
| D10 | Doc4 and Doc5: one dated sentence inside an undated section | a record of that day for its own statements only; the rest is judged | makes the whole section a record |
| D11 | Doc4 and Doc5: "today" in an implemented spec | not a date; the sentence is judged against the code | a dated record |
| D12 | Doc4 and Doc5: a drift that falls under several candidates of one section | reported once, under the first candidate in plan order that contains it | reported under each |

### D13. A D2 carve-out for type-stub packages and notebook kernels (request 3)

- **Background:** D2 flags a declared dependency that is neither imported, run
  nor loaded through an entry point. A `*-stubs` or `types-*` package the type
  checker reads, and an `ipykernel` a notebook runner starts, are used but
  match no carve-out (seen 2026-11-21 in a project that runs mypy and executes
  notebooks in its tests).
- **Affects:** D2's predicate text in `claude/skills/auditme/SKILL.md` and its
  documented refinements; D2 has no script check.
- **Options:**
  - **A (recommended): ship, with positive guards.** A `*-stubs` or `types-*`
    package is used when the project runs a type checker (mypy, pyright or
    pyre counts as run under D2's existing rule). A Jupyter kernel package is
    used when a declared dependency executes notebooks (`nbclient`,
    `nbconvert`, `papermill`, `nbmake`). A name alone is not evidence.
  - **B: reject**, with the reason recorded under `## Rejected`.

## Answers

Answered by the operator on the review page on 2026-11-21, read back from its database the same day.

| Decision | Answer | Comment |
|---|---|---|
| D1 | A (recommended) | none |
| D2 | A (recommended) | none |
| D3 | A (recommended) | none |
| D4 | A (recommended) | none |
| D5 | A (recommended) | none |
| D6 | A (recommended) | none |
| D7 | A (recommended) | none |
| D8 | A (recommended) | none |
| D9 | A (recommended) | none |
| D10 | A (recommended) | none |
| D11 | A (recommended) | none |
| D12 | A (recommended) | none |
| D13 | A (recommended) | none |
