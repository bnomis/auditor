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

### Settle the thresholds review-2's reviewers left open

- **Raised:** 2026-11-22, by this repository's second audit (review-2, decision D1).
- **What happens:** each brief tells its reviewer to report, not decide, a
  threshold it does not settle, and the reviewers of that audit reported
  these, so each is judged case by case:
  - A1: whether a handler for the only `subprocess.SubprocessError`
    subclass the call can raise (`TimeoutExpired` with a `timeout`,
    `CalledProcessError` with `check=True`) covers it; whether a failure a
    registered check reports as an emitted hit, or records in a registry
    the driver reports, is translated; whether a call to the package's own
    translating wrapper is covered by that wrapper.
  - A4: whether a decorator's raise at import time reaches the decorated
    function's caller.
  - A17: where a reach past a non-empty subpackage's `__all__` is reported
    (today on the parent package's candidate).
  - Doc4: whether a bullet that opens with a bold title, then "(amendment
    1.x, found <date>)", is dated; whether a spec's step instruction or
    draft docstring for its own change is a record of it; whether a
    reproduced file block, or an "X has a, b and c" sentence, presents
    itself as complete; whether a changed step order is drift; whether a
    Motivation paragraph describing the state before the change, or an
    acceptance criterion tagged with an amendment, is a record; whether a
    missing `Raises:` in a spec's API block is drift; which candidate holds
    a drift when every candidate of a section has the same span.
  - Doc5: whether a troubleshooting list is a list of exit conditions;
    whether a JSON value shown in prose is an output example; whether a
    list that begins "any failure:" presents itself as complete; whether a
    claim narrower than the code is drift; whether an admonition list
    presents itself as complete; whether a concepts row is judged against
    the published hook manifest or the setup template.
- **Asked for:** settle each in its brief, bumping the brief's version, so
  every reviewer applies the same threshold. The A1 emitted-hit case goes
  with review-2's decision D2, which makes `check_lockfile` and
  `check_ruff_version` report a missing tool as a hit.

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
