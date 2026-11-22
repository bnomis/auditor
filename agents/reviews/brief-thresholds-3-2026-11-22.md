# Settling the thresholds review-3's reviewers left open

**Date:** 2026-11-22
**Review page:** https://claude.ai/artifact/UzU9o21y4s2vWvQBirHW6h
**Source:** the `TODO.md` item "Settle the thresholds review-3's reviewers left open" and its entry in `claude/skills/auditme/requests.md`, filed by decision D1 of `agents/audit-reviews/review-3.md` (2026-11-22)

## What is being reviewed and how

Each Phase B brief (`claude/skills/auditme/phaseb/briefs/<Q>.md`) tells its
reviewer to report, not decide, a threshold the brief does not settle. There
have now been three rounds of settling them:

| Round | Review page | Cases settled |
|---|---|---|
| Review-1's | `agents/reviews/brief-thresholds-2026-11-22.md` | 13 |
| Review-2's | `agents/reviews/brief-thresholds-2-2026-11-22.md` | 18 |
| Review-3's | this one | about fifteen new cases |

Settling cases one at a time does not converge: each audit meets the next
case, and until it is settled two batches can judge it differently. The
`todo-review` conventions name this pattern, the same cause described a third
time, as a reason to stop and fix the cause.

The first decision below (G1) fixes the cause: it gives every unsettled case
one default verdict, so a verdict no longer depends on which reviewer judged
it. The others settle the cases this audit met, one at a time. Pick an option
for each. Once every decision has an answer, the chosen wording goes into
the briefs, each changed brief's `**Brief version:**` goes up by one, and so
does `claude/skills/auditme/tests/phaseb/test_briefs.py`.

The recommendations follow the rule the earlier rulings used: a carve-out
needs positive evidence. A case of the same kind as one already settled
extends that ruling.

## Automatic checks

- The briefs named below exist and have a `**Brief version:**` line: pass
  (A1 4, T2 1, Doc4 6, Doc5 6, read on 2026-11-22). The general rule G1
  touches every brief.
- None of the cases below is settled in its brief: pass, read on 2026-11-22.

## Decisions

### G1. A default verdict for a case no brief settles

- **What is being decided:** what a reviewer does with a case its brief
  does not settle.
- **Background:** today the reviewer reports the case and judges it as it
  sees fit, so two batches can judge the same kind of case differently.
  Three audits in a row each met a fresh set of such cases.
- **What it affects:** every listed question's brief, whose version goes up
  by one, so the next audit re-judges every listed candidate once.
  Afterwards, an unsettled case can no longer split verdicts.
- **Options:**
  - **Not a finding, and reported (recommended):** a case the brief does not
    settle is judged not a finding, and the reviewer names it in its reply.
    The verdict is the same in every batch. The operator settles a reported
    case only when it should count, so settling stops being needed for
    determinism.
  - **Keep judging case by case:** the reviewer reports the case and judges
    it as it sees fit; each audit's new cases are settled by a review like
    this one.

### A1-1. A standalone script's own error class

- **What is being decided:** whether a handler that raises the script's own
  error class (`ChangedError` in `checks/changed.py`) translates, when the
  payload's `domain_errors` does not list it.
- **Background:** `domain_errors` lists the package's error classes. A
  standalone script outside the package defines its own. Review-2 and
  review-3 both judged these sites covered.
- **What it affects:** A1 verdicts on scripts.
- **Options:**
  - **Translates (recommended):** a `*Error` class the script defines
    itself counts as a domain error for that script's calls. The class
    definition is the positive evidence.
  - **Does not:** only the payload's `domain_errors` count.

### T2-1. A call through a local alias in a property test

- **What is being decided:** whether `check = module.fn`, then `check(x)`
  inside a `given` test, is a direct call of `fn`.
- **Background:** the T2 index missed these calls. Five helpers are covered
  only this way.
- **What it affects:** T2 verdicts.
- **Options:**
  - **Direct (recommended):** an alias assigned from the candidate itself
    names the same object, as the T1 brief already rules for a re-export.
  - **Not direct:** only a call written with the candidate's own name counts.

### Doc4-1. A present-tense Module location row marked "(new)"

- **What is being decided:** whether the row is a record of the spec's
  change or a statement of what the file holds now.
- **Background:** the project-setup spec says `.pre-commit-hooks.yaml` (new)
  "publishes `auditme-changed` and `auditme-all`". A third hook was added
  later.
- **What it affects:** Doc4 verdicts on Module location sections.
- **Options:**
  - **A record (recommended):** "(new)" marks the row as describing what the
    change added, a record like "version 1 when written".
  - **The current state:** the row is judged as a complete list.

### Doc4-2. A `Raises:` that names an error for one condition, raised for another too

- **What is being decided:** whether a condition missing beside an error
  type the section already names is drift.
- **Background:** Doc4 version 6 makes a `Raises:` section complete as to
  the error types it declares.
- **What it affects:** Doc4 verdicts on API blocks.
- **Options:**
  - **Not drift (recommended):** the section lists types. A further
    condition for a listed type is an omission, unless the section presents
    its conditions as complete.
  - **Drift:** each condition the code raises for must be named.

### Doc4-3. A usage block that leaves an option off

- **What is being decided:** whether a command synopsis without an option
  the command accepts is drift.
- **Background:** Doc4 version 6 makes a reproduced file block complete
  unless it is marked as an excerpt.
- **What it affects:** Doc4 verdicts on CLI synopses.
- **Options:**
  - **Drift unless marked (recommended):** a usage block reproduces the
    command's interface, like a file block, so it is complete unless marked
    as an excerpt.
  - **An omission:** a synopsis shows the common form only.

### Doc4-4. A predicate's definition

- **What is being decided:** whether a definition ("compared with string
  constants, attribute constants or tuples of them") is a complete list.
- **Background:** the code also accepts lists and sets.
- **What it affects:** Doc4 verdicts on definitions.
- **Options:**
  - **Complete (recommended):** a definition says exactly what counts, so a
    case the code also accepts is drift, unless the definition is marked
    "for example".
  - **Not complete:** a definition is read like any other sentence.

### Doc4-5. An undated statement that a dated amendment later in the same section replaces

- **What is being decided:** whether the earlier statement is drift.
- **Background:** the test-questions spec says the test tree is
  `src/tests/` and `tests/`; amendment 1.5, in the same section, replaces
  that.
- **What it affects:** Doc4 verdicts on amended specs.
- **Options:**
  - **Not drift (recommended):** a section is read as a whole. A later
    dated amendment in it that replaces an earlier statement is the
    section's current word.
  - **Drift:** each statement stands alone.

### Doc4-6. A list ending "all else is X's handling"

- **What is being decided:** whether such a list is complete.
- **Background:** the test-questions spec's Error handling list ends that
  way.
- **What it affects:** Doc4 verdicts on error-handling sections.
- **Options:**
  - **Complete with its delegate (recommended):** the catch-all hands the
    rest to X. A case neither listed nor X's is drift; a case X handles is
    not.
  - **Not complete:** the catch-all marks the list as examples.

### Doc4-7. A numbered list of a guide's sections

- **What is being decided:** whether it presents the guide's contents as
  complete, or only their order.
- **Background:** the project-setup spec lists `docs/setup.md`'s sections,
  and the guide has one more.
- **What it affects:** Doc4 verdicts on Documentation sections.
- **Options:**
  - **Both (recommended):** under the rules already settled, a numbered
    list presents an order, and an unmarked list is complete; a section the
    guide also has is drift.
  - **Order only:** only a different order is drift.

### Doc4-8. A spec's Testing section

- **What is being decided:** whether it is an instruction for the spec's
  change, and so a record, or a description of the tests to check.
- **Background:** one bullet in the raises-section-resolution spec names
  `ProbeError`, where the tests use its subclass.
- **What it affects:** Doc4 verdicts on Testing sections.
- **Options:**
  - **A record (recommended):** a Testing section tells the implementer what
    to write, like an implementation step, which Doc4 version 6 makes a
    record.
  - **A description:** each bullet is checked against the tests.

### Doc4-9. A shared drift whose section's candidates are split across batches

- **What is being decided:** which reviewer reports it.
- **Background:** the shared-span rule speaks of "the batch's order", and
  one project-setup section was split.
- **What it affects:** which ledger entry carries the finding, and whether
  it is reported twice.
- **Options:**
  - **In each batch, by its own rule (recommended):** each reviewer applies
    the shared-span rule to the candidates in its own batch. The orchestrator
    merges the duplicates into one finding in the review.
  - **Only the batch holding the first candidate:** a reviewer whose batch
    lacks it reports nothing.

### Doc4-10. A command spelled with fewer flags than the code uses

- **What is being decided:** whether, for example, `pre-commit install` in a
  spec is drift when the skill runs it with two `--hook-type` options.
- **Background:** the project-setup spec shows `pre-commit install`; the
  skill runs `pre-commit install --hook-type pre-commit --hook-type pre-push`.
- **What it affects:** Doc4 verdicts on commands.
- **Options:**
  - **Drift when it does something different (recommended):** a command
    that, run as written, would do something other than what the code does
    (here, install no pre-push hook) is drift. One that only leaves out an
    optional extra is not.
  - **Never drift:** a command in prose is a sketch.

### Doc4-11. A wording that both readings fit

- **What is being decided:** whether a sentence that one reading makes true
  and another false is drift.
- **Background:** "numbered by order of appearance within the qualname";
  the code numbers per qualname and site part.
- **What it affects:** Doc4 verdicts on ambiguous sentences.
- **Options:**
  - **Not drift (recommended):** drift is a statement the code contradicts.
    A sentence that one fair reading makes true is not contradicted.
  - **Drift:** the stricter reading is judged.

### Doc5-1. A "Stops for" list

- **What is being decided:** whether a skill's list of the points where it
  stops is a list of the conditions under which it stops.
- **Background:** `docs/reference/skills.md`'s list for
  `/auditme-project-setup` leaves out three of its stops.
- **What it affects:** Doc5 verdicts on skill references.
- **Options:**
  - **It is one (recommended):** like a troubleshooting list (Doc5
    version 6), it lists the conditions that produce the stop, and is
    complete unless marked.
  - **It is not:** it names the main stops only.

### Doc5-2. The docs' account of an external tool pinned elsewhere

- **What is being decided:** how the docs' description of a tool this
  repository runs from another repository, pinned to a commit, is judged.
- **Background:** the installer `install-in-claude`, pinned at commit
  `fa68deb`, has exit cases the exit table leaves out.
- **What it affects:** Doc5 verdicts on `bin/install-claude.sh`'s section.
- **Options:**
  - **Against the pinned version (recommended):** the pin names the code.
    Judge against it when it can be read, and drift is what that version
    contradicts. When it cannot be read, the description is not judged, and
    the reviewer says so.
  - **Not judged:** another repository's tool is out of scope.

## Answers

Answered on the review page on 2026-11-22. Every decision took the
recommended option, with no comments.

| Decision | Answer | |
|---|---|---|
| G1 | Not a finding, and reported | recommended |
| A1-1 | Translates | recommended |
| T2-1 | Direct | recommended |
| Doc4-1 | A record | recommended |
| Doc4-2 | Not drift | recommended |
| Doc4-3 | Drift unless marked | recommended |
| Doc4-4 | Complete | recommended |
| Doc4-5 | Not drift | recommended |
| Doc4-6 | Complete with its delegate | recommended |
| Doc4-7 | Both | recommended |
| Doc4-8 | A record | recommended |
| Doc4-9 | In each batch, by its own rule | recommended |
| Doc4-10 | Drift when it does something different | recommended |
| Doc4-11 | Not drift | recommended |
| Doc5-1 | It is one | recommended |
| Doc5-2 | Against the pinned version | recommended |
