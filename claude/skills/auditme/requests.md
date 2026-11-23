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

### Settle the brief cases reviewers left open (filed 2026-11-23)

An audit on one project after the 2026-11-22 brief settlements found batch
reviewers naming cases the briefs do not settle, with different batches
judging the same shape differently (failure mode 2). Settle each in its brief:

- **Doc4, Doc5:** whether these count as presenting a complete list: a
  Module location table row saying what a module holds or becomes; a sentence
  "its only input is X and Y" or "its input is X"; a table of kinds; an API
  block drawn from several files. Whether a cited line number off by one is
  drift. Whether an example row of a file the code writes must be whole, as
  printed output must.
- **T1:** whether a test reaches a function that a framework runs (a
  pydantic validator), that runs at import to build a constant, that is a
  property getter, that a third-party library calls back, or that a test
  reaches through a server it talks to over a socket.
- **A17:** whether a documented project exception (an import-cycle carve-out,
  scripts treated as whitebox tooling) settles a read of a submodule that
  `__all__` leaves out.
- **A19:** the brief flags a broad graceful-degradation handler that carries
  the scoped `accept[logger-exception-graceful-degradation]` marker the
  2026-10-14 ruling prescribes for a handler the user decided to keep. The
  brief should read that marker as the user's decision, or the lister should
  leave such a site out, as it does for a sweep hit.

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
