# Settling the thresholds review-1's reviewers left open

**Date:** 2026-11-22
**Review page:** https://claude.ai/artifact/SQ2EYQGwf5PBS7CGuGxsTM
**Source:** the `TODO.md` item "Settle the thresholds review-1's reviewers left open" and its entry in `claude/skills/auditme/requests.md`, filed by decision D1 of `agents/audit-reviews/review-1.md` (2026-11-21)

## What is being reviewed and how

Each Phase B brief (`claude/skills/auditme/phaseb/briefs/<Q>.md`) tells its
reviewer to report, not decide, a threshold the brief does not settle. In
this repository's first full audit (review-1, 2026-11-21) the reviewers of
the A1, A4, T1, Doc4 and Doc5 questions reported thirteen such thresholds.
Until a brief settles them, each is judged case by case and can get a
different verdict in another batch. That is the non-determinism the auditme
skill's convergence rule forbids (failure mode 2).

Each decision below settles one threshold. Pick an option for each. Once
every decision has an answer, the chosen wording goes into its brief, each
changed brief's `**Brief version:**` goes up by one, and so do
`claude/skills/auditme/tests/phaseb/test_briefs.py` and the version pointers
in the three listed-question specs. The request entry and the `TODO.md` item
then close.

The recommendations follow one rule, the one the shared `design.md` rule and
the checker's earlier refinements use: a carve-out needs positive evidence
that the reviewer can point at in the code or the text (an argument, a
registration, a wording), never only the absence of a reason to flag.

## Automatic checks

- Every brief named below exists and has a `**Brief version:**` line: pass
  (A1 2, A4 4, T1 3, Doc4 4, Doc5 4, read on 2026-11-22).
- None of the thirteen cases is already settled in its brief, except part of
  T1-1: brief version 3 counts a script run by path through `runpy` or
  `spec_from_file_location`, but not one run as a subprocess. Pass, read on
  2026-11-22.

## Decisions

### A1-1. A `subprocess.run(..., check=False)` with no timeout, under a handler for `OSError` only

- **What is being decided:** whether that handler covers the call.
- **Background:** the A1 brief counts `OSError` and `subprocess.SubprocessError`
  as `subprocess`'s failure class. `subprocess.run` raises a
  `SubprocessError` only through `check=True` (`CalledProcessError`) or a
  `timeout` (`TimeoutExpired`); without either, a missing or unrunnable
  program raises `OSError` and nothing else does.
- **What it affects:** A1 verdicts on every `subprocess` call in a project,
  including the checker's own calls in
  `checks/auditme/rules/project_hygiene.py`.
- **Options:**
  - **Covered (recommended):** when the call's own arguments show `check`
    false or absent and no `timeout`, `OSError` is the whole failure class.
    The arguments are the positive evidence.
  - **Not covered:** a `subprocess` call always needs both classes caught,
    whatever its arguments.

### A1-2. A function that turns a read failure into a problem it returns, by design

- **What is being decided:** whether returning the failure counts as
  translating it.
- **Background:** the brief says logging, returning a default or a bare
  re-raise is not translation. Some functions are built to collect problems
  instead of raising: they catch the `OSError` and return it, or its message,
  as one of the problems the caller reports.
- **What it affects:** A1 verdicts on validators and loaders that return a
  list of problems.
- **Options:**
  - **Translated when documented (recommended):** not a hit when the handler
    returns a value carrying the error (the exception or its text) and the
    function's return annotation or docstring says it returns failures. A
    bare default (`None`, empty) is still a hit.
  - **Never translated:** only raising a domain error translates, whatever
    the function promises.

### A4-1. An error that reaches a caller through a registry lookup (`REGISTRY[question](...)`)

- **What is being decided:** whether the caller's `Raises:` owes the errors of
  the functions the registry dispatches to.
- **Background:** the brief already says a `functools.singledispatch` entry
  point owes its registered implementations' domain errors, and that an
  error reachable only through a callable passed in as an argument is not
  owed.
- **What it affects:** A4 verdicts on dispatchers such as the question registry
  `REGISTRY` in `checks/auditme/phaseb/candidates.py`, which
  `register_question` fills.
- **Options:**
  - **Owed when the registry is a package literal (recommended):** owed when
    the registry is a module-level literal mapping (or one filled by a
    registering decorator) whose values are the package's own functions,
    as with `singledispatch`. A mapping built at run time or passed in is
    treated like a callable passed in, and is not owed.
  - **Never owed:** a lookup is a callable chosen at run time, like one
    passed in.

### T1-1. A test that runs a script by path as a subprocess

- **What is being decided:** whether such a test counts as a caller test for
  a `script` candidate, as `runpy` and `spec_from_file_location` do since
  brief version 3.
- **Background:** the checker's own tests run its scripts with
  `subprocess.run([sys.executable, <path>, ...])`
  (`claude/skills/auditme/tests/test_driver.py`,
  `claude/skills/auditme/tests/phaseb/test_cli.py`).
- **What it affects:** T1 verdicts on private functions of standalone
  scripts.
- **Options:**
  - **Counts (recommended):** a test that runs the script's path as a
    subprocess (with `sys.executable` or the script directly) is a caller
    test of each candidate its `__main__` entry point reaches. The path in
    the test's arguments is the positive evidence.
  - **Does not count:** only an in-process load covers a candidate, since a
    subprocess run's coverage cannot be traced.

### T1-2. A call made inside a `conftest.py` fixture

- **What is being decided:** whether that call is the test's own call.
- **Background:** the index already follows a fixture the test requests by
  parameter name, from its own file or a `conftest.py` above it. Reviewers
  met fixtures reached in other ways.
- **What it affects:** T1 verdicts where the set-up does the work.
- **Options:**
  - **Counts when the test uses the fixture (recommended):** a fixture the
    test requests by parameter, through `@pytest.mark.usefixtures`, or that
    is `autouse=True` in its own file or a `conftest.py` above it, is part
    of the test, and its calls are the test's calls. A fixture the test does
    not use in one of those ways is not.
  - **Only by parameter:** keep the index's rule; `usefixtures` and
    `autouse` fixtures do not count.

### T1-3. Passing the candidate as a callable argument to the code under test

- **What is being decided:** whether `run(check_x)`, for example, covers
  `check_x`.
- **Background:** the brief covers a call through a dispatch table or a
  parametrised name, but not a function handed to other code.
- **What it affects:** T1 verdicts on callbacks and registered checks.
- **Options:**
  - **Covers when the receiver calls it (recommended):** covered when the
    package function it is passed to calls that argument on the path the
    test takes. Read the receiver. Passing it only to store, register or
    compare it does not cover it.
  - **Never covers:** only a call written in the test covers a candidate.

### Doc4-1. Whether a spec's header `**Date:**` dates its sections

- **What is being decided:** whether the header date makes the whole spec a
  dated record.
- **Background:** the brief exempts a section or table that states its own
  date, and a dated sentence. Every spec has a header date, so reading it as
  dating the sections would exempt every implemented spec from Doc4.
- **What it affects:** every Doc4 verdict.
- **Options:**
  - **Does not date them (recommended):** the header date is when the spec
    was written. Its sections are judged against the code unless one states
    its own date.
  - **Dates them:** a spec is a record of its header date; Doc4 checks only
    specs whose status is not `implemented`.

### Doc4-2. An implemented spec's account of its own change after later changes move on

- **What is being decided:** whether "its briefs at version 1", or its list
  of the questions it puts on the listed path, drifts once a later change
  bumps a brief or lists more questions.
- **Background:** a spec describes the change it made, and later amendments
  or specs move the code on.
- **What it affects:** Doc4 verdicts on the listed-question specs and on any
  spec followed by an amendment.
- **Options:**
  - **A record when worded as the change (recommended):** a statement worded
    as what this spec's change did ("version 1 when written", "puts T1 and
    T2 on the listed path") is a record of that change and is not drift. A
    statement worded as the current state of the system ("the listed
    questions are ...", "the brief is at version 1") is judged against the
    code.
  - **Always judged:** every statement is checked against today's code, and
    the spec is amended each time a later change moves on.

### Doc4-3. A statement that work is part of a `TODO.md` item, once the item moves to `DONE.md`

- **What is being decided:** whether the reference drifts.
- **Background:** the shared `todo-review` conventions move an item to
  `DONE.md` unchanged, so its heading still exists.
- **What it affects:** Doc4 verdicts on specs written from a `TODO.md` item.
- **Options:**
  - **Not drift (recommended):** the item is found in `TODO.md` or `DONE.md`,
    unchanged, so the reference still resolves. It is drift only when the
    heading is in neither file.
  - **Drift:** a spec saying work is in `TODO.md` is wrong once it is not.

### Doc4-4. A present-tense sentence in a bullet that starts "found <date>"

- **What is being decided:** whether the bullet's date dates the sentence.
- **Background:** the brief already makes a dated sentence a record of its
  day.
- **What it affects:** Doc4 verdicts on findings carried into specs.
- **Options:**
  - **Dated (recommended):** a bullet or paragraph that opens with a date
    ("found on <date>", "measured on <date>") is a record of that day for
    every sentence in it.
  - **Only the opening sentence:** later sentences in the bullet are judged.

### Doc4-5. A table recording one change's version bumps

- **What is being decided:** whether such a table is a dated record.
- **Background:** amendments record which brief went to which version; later
  changes bump them again.
- **What it affects:** Doc4 verdicts on amendment tables.
- **Options:**
  - **A record when tied to a named change (recommended):** a table whose
    caption or lead sentence names the change or amendment it records is a
    record of that change, like a dated table, and is not checked against
    today's versions.
  - **Judged:** the versions in it are checked against today's briefs.

### Doc5-1. A parenthetical list, or a list of exit conditions

- **What is being decided:** whether either presents itself as complete.
- **Background:** the brief already says a list of a field's values written
  without "for example", "such as" or "including" presents itself as
  complete.
- **What it affects:** Doc5 verdicts on the user guides and `README.md`.
- **Options:**
  - **Complete unless marked (recommended):** both present themselves as
    complete unless written with "for example", "such as", "including" or
    "e.g.". A reader relies on a list of exit conditions to know when a
    command fails.
  - **Never complete:** only a list of a field's values can claim to be
    complete.

### Doc5-2. A broad "any existing file" claim when the code asks about named files only

- **What is being decided:** whether the claim drifts.
- **Background:** a guide said a command acts on any existing file, while
  the code checks a fixed set of named files.
- **What it affects:** Doc5 verdicts on broad claims.
- **Options:**
  - **Drift (recommended):** a claim broader than the code is one the code
    contradicts: a file outside the named set does not behave as the guide
    says.
  - **Not drift:** a broad claim is an omission of detail.

## Answers

Answered on the review page on 2026-11-22. Every decision took the
recommended option, with no comments.

| Decision | Answer | |
|---|---|---|
| A1-1 | Covered | recommended |
| A1-2 | Translated when documented | recommended |
| A4-1 | Owed when the registry is a package literal | recommended |
| T1-1 | Counts | recommended |
| T1-2 | Counts when the test uses the fixture | recommended |
| T1-3 | Covers when the receiver calls it | recommended |
| Doc4-1 | Does not date them | recommended |
| Doc4-2 | A record when worded as the change | recommended |
| Doc4-3 | Not drift | recommended |
| Doc4-4 | Dated | recommended |
| Doc4-5 | A record when tied to a named change | recommended |
| Doc5-1 | Complete unless marked | recommended |
| Doc5-2 | Drift | recommended |
