# Settling the brief cases reviewers left open (round 4)

**Date:** 2026-11-23
**Review page:** https://claude.ai/artifact/9jhmJNMQMKWAomPN3CjtgR
**Source:** the `TODO.md` item "Settle the brief cases reviewers left open" and its entry in `claude/skills/auditme/requests.md` ("Settle the brief cases reviewers left open (filed 2026-11-23)"), filed after an audit on one project

## What is being reviewed and how

An audit on one project, run after the 2026-11-22 brief settlements, found
batch reviewers naming cases the Doc4, Doc5, T1, A17 and A19 briefs
(`claude/skills/auditme/phaseb/briefs/<Q>.md`) do not settle. Since round 3's
general rule (G1 in `agents/reviews/brief-thresholds-3-2026-11-22.md`), an
unsettled case is judged "not a finding" and reported, so the verdicts no
longer split between batches. What is left is for you to decide which of
these cases should count.

Pick an option for each decision. Once every decision has an answer:

- the chosen wording goes into each brief;
- each changed brief's `**Brief version:**` goes up by one, and so does its
  expectation in `claude/skills/auditme/tests/phaseb/test_briefs.py`;
- A19-1, if chosen as recommended, changes the A19 lister and gets a test;
- each settlement is recorded as a dated amendment in the spec that owns the
  question;
- the request entry is deleted from `requests.md`, and the `TODO.md` item
  moves to `DONE.md`.

The recommendations follow the rule the earlier rounds used: a case of the
same kind as one already settled extends that ruling, and a carve-out needs
positive evidence. Where a case could be decided either by a reviewer's
judgement or by a mechanical rule, the mechanical rule is recommended,
because it cannot vary between batches.

## Automatic checks

- The briefs named below exist and have a `**Brief version:**` line: pass
  (Doc4 8, Doc5 8, T1 6, A17 4, A19 3, read on 2026-11-23).
- None of the cases below is settled in its brief: pass, read on 2026-11-23.
- The A19 lister (`list_a19_candidates` in
  `claude/skills/auditme/checks/auditme/phaseb/architecture.py`) leaves out
  a handler only when a sweep rule reports a hit on its lines: confirmed on
  2026-11-23. The sweep rule `logger-exception-graceful-degradation` fires
  only on a handler that ends in, or falls through to, `return <constant>`.

## Decisions

### Doc-1. A Module location row that says what a module holds

- **What is being decided:** whether a spec's Module location row that says what a module holds or becomes ("`core.py` - the shared helpers and the cache") presents a complete list of its contents, for Doc4 and Doc5.
- **Background:** the Doc4 brief already counts "a sentence naming what something has" as complete unless marked, and treats a row marked "(new)" as a record. A Module location row is a one-line summary of a file, and a module usually holds more than its summary names.
- **What it affects:** the Doc4 and Doc5 briefs. Treating rows as complete would turn every helper a row does not name into drift.
- **Options:**
  - **A role, not a list (recommended):** the row is judged for the file's existence and role, as drift already defines; something more the module holds is an omission, not drift.
  - **Complete unless marked:** the row counts as a sentence naming what something has; anything more the module holds is drift.

### Doc-2. "Its only input is X" and "its input is X"

- **What is being decided:** whether a sentence giving a component's input ("its only input is X and Y", "its input is X") presents the inputs as complete, for Doc4 and Doc5.
- **Background:** the Doc5 brief counts a claim stated as the whole ("only", "just", "never") as complete, and the Doc4 brief counts "a sentence naming what something has" as complete unless marked. Reviewers split on the form without "only".
- **What it affects:** the Doc4 and Doc5 briefs.
- **Options:**
  - **Both complete (recommended):** each names what the component has, so an input the code also reads is drift, with "only" or without it; "for example" or "such as" marks it as partial.
  - **Only with "only":** "its only input is X" is complete; "its input is X" is not, and a further input is an omission.

### Doc-3. A table of kinds

- **What is being decided:** whether a table listing the kinds of something (rule families, record types, variants) presents the kinds as complete, for Doc4 and Doc5.
- **Background:** the Doc5 brief already counts a list of the values a field takes as complete unless marked. A table of kinds is the same list set out in rows.
- **What it affects:** the Doc4 and Doc5 briefs.
- **Options:**
  - **Complete unless marked (recommended):** a kind the code also has is drift, unless the table or its lead sentence says "for example", "such as" or "including".
  - **Not complete:** a missing kind is an omission.

### Doc-4. An API block drawn from several files

- **What is being decided:** whether a spec's API block that shows functions from several files presents the set of functions as complete, for Doc4 and Doc5.
- **Background:** the Doc4 brief counts a reproduced file block as complete unless marked. An API block gathered from several files is a selection, not a copy of any one file. The sweep's `spec-api-signature-drift` rule already checks each signature's parameters.
- **What it affects:** the Doc4 and Doc5 briefs.
- **Options:**
  - **Complete per signature, not per set (recommended):** each function shown is judged (its name, return, errors and docstring claims); a function the files also define and the block leaves out is an omission, whether the block is drawn from one file or several.
  - **Complete unless marked:** the block lists every public function of the files it draws on, and a missing one is drift.

### Doc-5. A cited line number that is off by one

- **What is being decided:** whether a cited `path:line` that points one line away from what it cites is drift, for Doc4 and Doc5.
- **Background:** a dated section's line numbers are already not checked. An undated line number is a claim about today's file, and line numbers rot without anyone noticing; the shared counts-in-prose rule says to drop such figures or date them.
- **What it affects:** the Doc4 and Doc5 briefs. The fix for such a drift is to drop the line number or date the sentence.
- **Options:**
  - **Drift at any distance (recommended):** an undated line number whose line does not hold what it cites is drift, whether it is off by one or by a hundred.
  - **Allow one line:** a line number off by one is not drift; further off is.

### Doc-6. An example row of a file the code writes

- **What is being decided:** whether an example line of a file the code writes (a JSONL record, a ledger row) must be whole, as an example of printed output must, for Doc4 and Doc5.
- **Background:** the Doc5 brief says an example of output the code prints is presented whole. Some keys are written only in some cases: the sweep writes `related` only for a rule that compares files.
- **What it affects:** the Doc4 and Doc5 briefs.
- **Options:**
  - **Whole for keys always written (recommended):** an example row that leaves out a key the code writes on every row, or shows a key's value in another form, is drift; a key written only in some cases may be left out.
  - **Whole for every key:** any key the code can write and the row lacks is drift.
  - **Not whole:** a missing key is an omission.

### T1-1. A function a framework runs

- **What is being decided:** whether a test reaches a function a framework runs for it, such as a pydantic validator, for T1.
- **Background:** the T1 brief already says a dunder the language runs is called by the test that triggers it (`__post_init__` by constructing). A validator is run the same way: by building the model with the field it validates.
- **What it affects:** the T1 brief.
- **Options:**
  - **Covered by the triggering test (recommended):** a test that does what makes the framework run the function on the path the test takes (constructing the model with that field) calls it, as for a dunder.
  - **Direct calls only:** only a test that calls the function itself covers it.

### T1-2. A function that runs at import to build a constant

- **What is being decided:** whether a test reaches a function that runs once at import to build a module constant, for T1.
- **Background:** every test that imports the module runs the function, but importing alone checks nothing about what it built.
- **What it affects:** the T1 brief.
- **Options:**
  - **Covered by a test that reads the constant (recommended):** a test that reads the constant the function built calls it; a test that only imports the module does not.
  - **Covered by any import:** a test in a file that imports the module covers it.

### T1-3. A property getter

- **What is being decided:** whether reading a property calls its getter, for T1.
- **Background:** the language runs the getter when the attribute is read, as it runs `__getattr__` for a missing attribute, which the brief already counts.
- **What it affects:** the T1 brief.
- **Options:**
  - **Reading it calls it (recommended):** a test that reads the property calls its getter, and a test that assigns to it calls its setter.
  - **Direct calls only:** reading the property does not count.

### T1-4. A function a third-party library calls back

- **What is being decided:** whether a test reaches a function that a third-party library calls back (a handler registered with a library, a key function passed to it), for T1.
- **Background:** the T1 brief already says a test that passes the candidate to a package function covers it when that function calls the argument on the test's path; the reviewer reads the receiver.
- **What it affects:** the T1 brief.
- **Options:**
  - **As for a package receiver (recommended):** the test covers the function when it calls the library entry point that calls it back on the test's path, judged from the library's documented behaviour; registering it alone does not.
  - **Not covered:** a call from outside the project never covers a candidate.

### T1-5. A function reached through a server over a socket

- **What is being decided:** whether a test reaches a handler through a server it talks to over a socket, for T1.
- **Background:** the T1 brief already counts a test that runs a script as a subprocess as a caller test of what the script's entry point reaches.
- **What it affects:** the T1 brief.
- **Options:**
  - **Covered when the test starts the server (recommended):** a test that starts the server itself, in its body or in a fixture it uses, and sends the request that routes to the handler covers it; a server the test did not start does not count.
  - **Not covered:** a socket boundary ends the test's reach.

### A17-1. A documented project exception for a submodule read

- **What is being decided:** whether a project's prose exception (an import-cycle carve-out, scripts treated as whitebox tooling) settles a read of a submodule that the package's `__all__` leaves out, for A17.
- **Background:** `SKILL.md`'s acceptance mechanism says only an inline marker or an AGENTS.md import-table row accepts a hit, and that nothing else does: not a decision note, not a prior review. For a Phase B verdict, the operator's dismissal (`phaseb.py dismiss`) records the decision, and it holds while the candidate is unchanged.
- **What it affects:** the A17 brief.
- **Options:**
  - **Still a finding, dismissed once (recommended):** the read is reported; the operator dismisses it with the exception as the reason, and the dismissal holds until the candidate changes.
  - **The exception settles it:** a read the project's documents name as an exception is not a finding.

### A19-1. A handler carrying the scoped graceful-degradation marker

- **What is being decided:** how A19 treats a broad handler that carries `accept[logger-exception-graceful-degradation]`, the marker the 2026-10-14 ruling in `SKILL.md` ("Conflicts with no winner") prescribes for a handler the user decided to keep.
- **Background:** the sweep rule for that marker fires only when the handler ends in, or falls through to, `return <constant>`. A handler that keeps the marker but ends in `continue`, `pass` or a non-constant return gets no sweep hit, so the lister passes it to Phase B, and the brief flags it at any level, against the user's recorded decision.
- **What it affects:** the A19 lister and its tests, or the A19 brief.
- **Options:**
  - **The lister leaves it out (recommended):** a handler whose lines, the line above its `except`, or its fall-through `return` carry an accept marker for one of the A19 rules is left out, as a sweep hit is. This is mechanical, so it cannot vary between batches.
  - **The brief reads the marker:** the reviewer judges a marked handler not a finding.

## Answers

Answered on the review page on 2026-11-23. Every decision took the
recommended option, with no comments.

| Decision | Answer | |
|---|---|---|
| Doc-1 | A role, not a list | recommended |
| Doc-2 | Both complete | recommended |
| Doc-3 | Complete unless marked | recommended |
| Doc-4 | Complete per signature, not per set | recommended |
| Doc-5 | Drift at any distance | recommended |
| Doc-6 | Whole for keys always written | recommended |
| T1-1 | Covered by the triggering test | recommended |
| T1-2 | Covered by a test that reads the constant | recommended |
| T1-3 | Reading it calls it | recommended |
| T1-4 | As for a package receiver | recommended |
| T1-5 | Covered when the test starts the server | recommended |
| A17-1 | Still a finding, dismissed once | recommended |
| A19-1 | The lister leaves it out | recommended |
