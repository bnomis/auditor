# Settling the thresholds review-2's reviewers left open

**Date:** 2026-11-22
**Review page:** https://claude.ai/artifact/6n7qtif6m1FYEWcpTaHbye
**Source:** the `TODO.md` item "Settle the thresholds review-2's reviewers left open" and its entry in `claude/skills/auditme/requests.md`, filed by decision D1 of `agents/audit-reviews/review-2.md` (2026-11-22)

## What is being reviewed and how

Each Phase B brief (`claude/skills/auditme/phaseb/briefs/<Q>.md`) tells its
reviewer to report, not decide, a threshold the brief does not settle. The
thirteen thresholds review-1's reviewers reported were settled on 2026-11-22
(`agents/reviews/brief-thresholds-2026-11-22.md`). In review-2, the same day,
the reviewers of the A1, A4, A17, Doc4 and Doc5 questions met new cases. Until
a brief settles them, each is judged case by case and can get a different
verdict in another batch.

Each decision below settles one threshold. Pick an option for each. Once
every decision has an answer, the chosen wording goes into its brief, each
changed brief's `**Brief version:**` goes up by one, and so does
`claude/skills/auditme/tests/phaseb/test_briefs.py`. The request entry and
the `TODO.md` item then close.

The recommendations follow the rule the earlier rulings used: a carve-out
needs positive evidence the reviewer can point at, such as an argument, a
registration or a wording. Where a case is the same kind as one already
settled, the recommendation extends that ruling, so the briefs stay
consistent.

## Automatic checks

- The briefs named below exist and have a `**Brief version:**` line: pass
  (A1 3, A4 5, A17 1, Doc4 5, Doc5 5, read on 2026-11-22).
- None of the cases below is settled in its brief: pass, read on 2026-11-22.

## Decisions

### A1-1. A handler for the only `SubprocessError` subclass the call can raise

- **What is being decided:** whether `except TimeoutExpired` covers a call
  with a `timeout` and `check` false, and `except CalledProcessError` a call
  with `check=True` and no `timeout`.
- **Background:** the A1 brief (version 3) says a `timeout` or `check=True`
  brings `subprocess.SubprocessError` into the failure class. With only one
  of them, only one subclass can be raised. Review-2's reviewer judged both
  such sites covered (`changed.py::sweep`, `docrefs.py::tracked_files`).
- **What it affects:** A1 verdicts on `subprocess` calls.
- **Options:**
  - **Covered (recommended):** when the call's own arguments leave only one
    `SubprocessError` subclass possible, a handler for that subclass, with
    `OSError`, covers the call. The arguments are the positive evidence.
  - **Not covered:** a call with either argument always needs
    `SubprocessError` itself caught.

### A1-2. A failure a registered check reports as a hit

- **What is being decided:** whether a check that turns a failure into an
  emitted hit, or records it where the driver reports it as a hit,
  translates it.
- **Background:** review-2's D2 made `check_lockfile` and `check_ruff_version`
  report a missing `uv` or `ruff` as a hit, as `check_ruff` did. The A1 brief
  counts only a raised domain error, or a documented returned failure, as
  translation, so A1 still flags these sites. Review-2 dismissed the
  `cached_source` site as by design (F2).
- **What it affects:** A1 verdicts on the checker's own checks and on any
  project whose checks report through hits.
- **Options:**
  - **Translated for a registered check (recommended):** a function the
    project registers as a check translates a failure when its handler emits
    a hit naming the failure, or records it in a structure the driver
    reports as a hit. The registration is the positive evidence, as in A9's
    2026-11-22 carve-out.
  - **Not translated:** only a raised domain error, or a documented return,
    translates.

### A1-3. A call to the package's own translating wrapper

- **What is being decided:** whether a call such as `candidates.read_text(path)`,
  whose callee is a package function that translates the failure itself,
  needs an envelope of its own.
- **Background:** the lister names calls by their callee's text. Review-2's
  reviewer judged three such calls covered, because the callee raises
  `PhaseBError`.
- **What it affects:** A1 verdicts on calls through a package's own readers.
- **Options:**
  - **Covered (recommended):** a call to a function the package defines,
    whose body catches the failure class and raises a domain error, is
    covered by that function. Name it in the reason.
  - **Judged on its own envelope:** only the call site's own `try` or
    envelope counts.

### A4-1. A decorator's raise that happens at import time

- **What is being decided:** whether an error a decorator raises when it is
  applied reaches the decorated function's caller.
- **Background:** `register_question` raises `PhaseBError` for a bad
  registration when the decorated module is imported, never when the
  decorated function is called. Review-2's reviewer judged it not owed.
- **What it affects:** A4 verdicts on decorated functions.
- **Options:**
  - **Not owed (recommended):** a raise in the decorator's own body runs
    when the function is defined. Only a raise in the wrapper the decorator
    returns, which runs at each call, reaches the caller.
  - **Owed:** a decorator's raises are listed in the decorated function's
    `Raises:`.

### A17-1. A reach past a non-empty subpackage's `__all__`

- **What is being decided:** whether, and where, A17 reports a module that
  reads a submodule a package's `__all__` leaves out.
- **Background:** A17's text asks about each `__all__`'s symbols being used
  outside, and about consumers that reach past an empty `__init__.py`.
  Review-2's reviewer reported `phaseb.py` reading `auditme.phaseb.candidates`
  on the parent `auditme` package, because the brief names only the empty
  case. Review-2's Task 4 has since removed that reach.
- **What it affects:** A17 verdicts on packages with an `__all__`.
- **Options:**
  - **A bypass, on the package bypassed (recommended):** a read from outside
    a package of a submodule its non-empty `__all__` leaves out bypasses the
    canonical owning module, and is reported on that package's own
    `__init__.py` candidate.
  - **Not A17's:** A17 reports reach-ins only past an empty `__init__.py`.

### Doc4-1. A bullet that opens with a bold title, then "(amendment 1.x, found <date>)"

- **What is being decided:** whether the date in the bullet's lead dates it.
- **Background:** the Doc4 brief (version 5) makes a bullet that opens with a
  date a record of that day. The project-setup spec's amendment bullets
  open with a bold title, followed by a parenthetical that carries the
  amendment and the date.
- **What it affects:** Doc4 verdicts on amendment bullets.
- **Options:**
  - **Dated (recommended):** a date in a bullet's lead, its title and the
    parenthetical straight after it, dates the bullet like an opening date.
  - **Not dated:** only a bullet whose first words are the date.

### Doc4-2. A spec's step instruction or draft docstring for its own change

- **What is being decided:** whether these are records of the change.
- **Background:** Doc4 version 5 makes a statement worded as what the spec's
  change did a record. Review-2 met an instruction ("look it up by the
  qualname `resolve` already returns") and a draft docstring ("as the drift
  rule's closure does today") that describe the code as it stood when the
  change was made.
- **What it affects:** Doc4 verdicts on implementation steps and API drafts
  in implemented specs.
- **Options:**
  - **A record (recommended):** an instruction to the implementer of the
    spec's own change, and a draft docstring that describes the code it
    replaces, are records of that change.
  - **Judged:** both are checked against today's code.

### Doc4-3. A reproduced file block, or "X has a, b and c"

- **What is being decided:** whether either presents itself as complete.
- **Background:** Doc5 (version 5) makes a list complete unless it is marked
  "for example", "such as", "including" or "e.g.". Doc4 has no such rule.
  Review-2 met a spec showing `.pre-commit-hooks.yaml` with two of its three
  hooks, and "T1 has `reasons`, `tests`, `callers` and `test_files`" where the
  payload has two more keys.
- **What it affects:** Doc4 verdicts on spec listings.
- **Options:**
  - **Complete unless marked (recommended):** the same rule as Doc5's. A
    reproduced file block, or a sentence naming what something has, is
    complete unless marked as an excerpt or with "for example", "such as",
    "including" or "e.g.".
  - **An omission:** neither is drift; only a wrong item is.

### Doc4-4. A changed step order

- **What is being decided:** whether a spec's list of steps in an order
  different from the code's is drift.
- **Background:** the project-setup spec lists the CI steps as deploy key
  before tests; the template runs the tests first.
- **What it affects:** Doc4 verdicts on procedures.
- **Options:**
  - **Drift when presented as an order (recommended):** a list numbered, or
    joined by "then", presents an order, and a different order in the code
    is drift. An unordered list is not.
  - **Never drift:** only a missing or wrong step is.

### Doc4-5. A Motivation paragraph, or an acceptance criterion tagged with an amendment

- **What is being decided:** whether either is a record.
- **Background:** a Motivation section describes the state that led to the
  change. An acceptance criterion tagged "1.4:" belongs to that amendment.
  Review-2 flagged both kinds, as present-tense statements, and review-2's
  Task 8 then reworded the ones it found.
- **What it affects:** Doc4 verdicts on Motivation sections and acceptance
  criteria.
- **Options:**
  - **Both are records (recommended):** a spec's Motivation is a record of
    the state before its change, and a criterion tagged with an amendment is
    a record of that amendment, like a table naming its change.
  - **Both are judged:** each is checked against today's code.

### Doc4-6. A missing or short `Raises:` in a spec's API block

- **What is being decided:** whether it is drift.
- **Background:** the Doc4 brief counts errors raised as drift and an
  omission as not, unless a list presents itself as complete. A spec's API
  block shows each function's docstring, and a `Raises:` section is that
  docstring's list of errors.
- **What it affects:** Doc4 verdicts on API blocks.
- **Options:**
  - **Drift (recommended):** a `Raises:` section is the complete list of the
    errors it declares. A declared error the code also raises, missing from
    it, is drift. So is a `Raises:` missing where the code declares one.
  - **An omission:** only a wrongly named error is drift.

### Doc4-7. Which candidate holds a drift when every candidate of a section has the same span

- **What is being decided:** where such a drift is reported.
- **Background:** the brief reports a drift once, under the first candidate in
  the batch's order whose span holds it. When every candidate of a section
  has the same span, that is always the section's first candidate, even when
  another candidate names the drifted target.
- **What it affects:** which ledger entry carries the finding.
- **Options:**
  - **Under the candidate naming its target (recommended):** report it under
    the candidate whose target the drift is about, and under the first
    candidate only when none names it.
  - **Always the first:** keep the literal rule.

### Doc5-1. A troubleshooting list

- **What is being decided:** whether a list under a symptom ("The Stop hook
  does not fire") is a list of the conditions under which a command fails or
  exits.
- **Background:** Doc5 version 5 makes such lists complete unless marked.
  Review-2's reviewer did not apply it to a troubleshooting list, which left
  out one case.
- **What it affects:** Doc5 verdicts on troubleshooting sections.
- **Options:**
  - **It is one (recommended):** a list of causes under a symptom is a list
    of the conditions that produce it, and is complete unless marked.
  - **It is not:** troubleshooting lists are advice.

### Doc5-2. A JSON value shown in prose

- **What is being decided:** whether inline JSON in a sentence is an example
  of printed output, which must match line for line.
- **Background:** the guide shows the Stop hook's block output on one line in
  a sentence; `jq` prints it over several lines.
- **What it affects:** Doc5 verdicts on inline values.
- **Options:**
  - **Content, not layout (recommended):** inline JSON in a sentence shows
    the keys and values, which are judged. Its line breaks and spacing are
    not. Only an example in a code block is judged line for line.
  - **An output example:** judged line for line like a code block.

### Doc5-3. A list that begins "any failure:"

- **What is being decided:** whether the catch-all makes the list after it
  examples.
- **Background:** `docs/reference/cli.md` lists `changed.py`'s failures after
  "any failure:".
- **What it affects:** Doc5 verdicts on failure lists.
- **Options:**
  - **Still complete (recommended):** the words before the colon do not mark
    it as examples; only "for example", "such as", "including" or "e.g."
    do.
  - **Examples:** "any" marks what follows as examples.

### Doc5-4. A claim narrower than the code

- **What is being decided:** whether a statement that describes less than the
  code does is drift.
- **Background:** Doc5 version 5 makes a claim broader than the code drift.
  Review-2 met "a sweep over `src/` and `bin/`", which describes only the
  default, when declared roots replace it.
- **What it affects:** Doc5 verdicts on summaries.
- **Options:**
  - **Drift when it says "only" (recommended):** a narrower claim is an
    omission, unless it states its scope as the whole ("only", "just",
    "never"), or the guide nowhere describes the rest.
  - **Always drift:** any narrower claim is drift.

### Doc5-5. An admonition list

- **What is being decided:** whether a list inside a note or warning box
  presents itself as complete.
- **Background:** the checker guide's "Hits a marker cannot accept" note names
  three rules; `unreadable-file` cannot be accepted by a marker either.
- **What it affects:** Doc5 verdicts on notes.
- **Options:**
  - **The same rule (recommended):** a list in an admonition is complete
    unless marked, like any other.
  - **Examples:** an admonition only highlights.

### Doc5-6. A concepts row about a project's set-up

- **What is being decided:** whether `docs/concepts.md`'s table row for
  `git push` is judged against the published hook manifest, or against the
  setup skill's template.
- **Background:** `.pre-commit-hooks.yaml` publishes `auditme-all` at the
  `manual` stage; the `/auditme-project-setup` template adds `pre-push`.
- **What it affects:** Doc5 verdicts on the concepts page.
- **Options:**
  - **Against what the section names (recommended):** a row or section that
    describes a project set up by the setup skill is judged against that
    skill's template; one that describes the published hooks is judged
    against the manifest. The section's own wording is the evidence.
  - **Always the manifest:** the published hooks are the code.

## Answers

Answered on the review page on 2026-11-22. Every decision took the
recommended option, with no comments.

| Decision | Answer | |
|---|---|---|
| A1-1 | Covered | recommended |
| A1-2 | Translated for a registered check | recommended |
| A1-3 | Covered | recommended |
| A4-1 | Not owed | recommended |
| A17-1 | A bypass, on the package bypassed | recommended |
| Doc4-1 | Dated | recommended |
| Doc4-2 | A record | recommended |
| Doc4-3 | Complete unless marked | recommended |
| Doc4-4 | Drift when presented as an order | recommended |
| Doc4-5 | Both are records | recommended |
| Doc4-6 | Drift | recommended |
| Doc4-7 | Under the candidate naming its target | recommended |
| Doc5-1 | It is one | recommended |
| Doc5-2 | Content, not layout | recommended |
| Doc5-3 | Still complete | recommended |
| Doc5-4 | Drift when it says "only" | recommended |
| Doc5-5 | The same rule | recommended |
| Doc5-6 | Against what the section names | recommended |
