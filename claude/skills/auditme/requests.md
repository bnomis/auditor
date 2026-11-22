# auditme: open change requests

Changes to the checker or to `SKILL.md`, raised by an audit and not yet made.

**This file should normally be empty.** A non-empty file is the alarm: it means
an audit found something the tool should catch, or a rule the tool states
badly, and nothing has been done about it. The next audit is not allowed to
start until every entry here is shipped or rejected - see
[Mechanical sweep](SKILL.md#3-mechanical-sweep-scripted).

It lives here rather than in a project's `agents/audit-reviews/summary.md`
because the work is here. A new check benefits every project audited, not the
one that happened to notice; recording it in one project's summary hides it
from the repository where it would be done, and lets two projects raise the
same request without either seeing the other.

## How an entry gets here

An audit may not change the checker mid-cycle - that is failure mode 1 in
[Convergence](SKILL.md#convergence-is-the-success-criterion). When a Phase B
reviewer finds a mechanically-detectable pattern the sweep misses, the reviewer
drops it (the review records only what the predicates asked for), and the
orchestrator adds an entry here after the review is written.

## How an entry leaves

Ship it or reject it, in the same session it is picked up. There is no
permitted state where an entry sits here across two audit cycles: that was the
old "queue, defer, audit, defer again" rhythm, which guaranteed every cycle
found something new and no cycle converged.

- **Shipped:** implement it, run the sweep on a real project, land fixes or
  accept markers for the catch-up surface it exposes, then delete the entry and
  note the change in the affected projects' `summary.md` so their next
  convergence note can account for it.
- **Rejected:** delete the entry and record the reason in this file's
  [Rejected](#rejected) section, so it is not raised a third time.

## Open

### Settle the thresholds review-3's reviewers left open

- **Raised:** 2026-11-22, by this repository's third audit (review-3, decision D1).
- **What happens:** each brief tells its reviewer to report, not decide, a
  threshold it does not settle, and the reviewers of that audit reported
  these, so each is judged case by case:
  - A1: a standalone script's own error class (`ChangedError` in
    `checks/changed.py`), which is not among the payload's `domain_errors`.
  - T2: whether a call through a local alias in a hypothesis `given` test
    (`check = module.fn`) is a direct call.
  - Doc4: a present-tense Module location row marked "(new)"; a `Raises:`
    listing an error for one condition when the code raises it for another
    too; a usage block that leaves an option off; a predicate's definition
    read as "X has a, b and c"; an undated statement that a dated amendment
    later in the same section replaces; a list ending "all else is X's
    handling"; a numbered list of a guide's sections, read as complete or as
    order only; a Testing section, read as an instruction or a description; a
    shared drift whose section's candidates are split across batches; a
    command spelled with fewer flags than the code uses; a wording both
    readings fit.
  - Doc5: a "Stops for" list, as a list of when a command stops; the docs'
    account of an external tool pinned in another repository.
- **Asked for:** settle each in its brief, bumping the brief's version, so
  every reviewer applies the same threshold. Each audit since review-1 has
  reported a fresh set after the last was settled (review-3's summary,
  Recurring patterns); consider with them whether a general rule would
  settle a class of cases rather than one case each.

### The `ruff format` half of the `ruff` rule never reports a file

- **Raised:** 2026-11-22, by this repository's third audit (review-3), reproduced the same day.
- **What happens:** `check_ruff` in `checks/auditme/rules/project_hygiene.py`
  emits a `ruff-format` hit only for an output line that contains `Would
  reformat` or ends in `.py`. Ruff 0.17.4 (the version this repository's
  `.pre-commit-config.yaml` pins) and 0.17.6 print `unformatted: File would be
  reformatted` and ` --> <path>:<line>:<col>` instead, so a sweep over a
  project with an unformatted file reports no `ruff-format` hit. The parser
  also takes the hit's `path` from the text before the first colon, which on
  the older output would be `Would reformat ...`. No test feeds the parser real
  `ruff format --check` output.
- **Asked for:** read the files to reformat from a stable format (for
  example `ruff format --check --output-format=json`, or one path per
  ` --> ` line), set `path` to the file relative to the project and `line` to
  the line ruff names, and test it against output captured from the pinned
  ruff. The first sweep after it ships reports every unformatted file as
  catch-up.

## Rejected

Kept so a rejected idea is not re-raised by a later audit that rediscovers it.

### `mutable-module-level-exported` should handle `Call` values

- **Raised:** by an audit, and carried through the two after it
- **Reason:** the check would miss `DEFAULTS = get_defaults()` if that were
  mutable, because the value is a `Call` rather than a dict literal. Nothing is
  currently hidden by this - `DEFAULTS` is a `MappingProxyType` - so the check
  would gain complexity to catch a case that does not exist. Revisit only if a
  real mutable `Call`-valued export appears.
- **Still rejected after the 2026-08-17 widening.** That change added the
  comprehension forms (`{k: f(k) for ...}`), which are not the same case: a
  comprehension's type is written in the assignment, a call's is not.
- **Still rejected after the 2026-09-01 shallow-wrapper check.**
  `mutable-members-in-immutable-wrapper` reads the *members* of a wrapped
  literal, and stops at the same line for the same reason: a member written
  `build()` states no type either. That check narrows the gap rather than
  reopening this one.
