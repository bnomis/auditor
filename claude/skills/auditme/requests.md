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

### Settle the thresholds review-1's reviewers left open

- **Raised:** 2026-11-21, by this repository's own first full audit (review-1, decision D1).
- **What happens:** each brief tells its reviewer to report, not decide, a
  threshold it does not settle, and the reviewers of that audit reported
  these, so each is judged case by case and can be judged differently in
  another batch:
  - A1: whether a handler that catches only `OSError` covers a
    `subprocess.run(..., check=False)` call with no timeout, which can raise
    nothing else; and whether a function that turns a read failure into a
    problem it returns to its caller, by design, translates it.
  - A4: whether an error reaches a caller through a call dispatched by a
    registry lookup (`REGISTRY[question](...)`), as it does through a
    `functools.singledispatch` generic.
  - T1: whether a test that runs a script by path as a subprocess counts as
    a caller test for a `script` candidate (the brief names only `runpy` and
    `spec_from_file_location`); whether a call made inside a `conftest.py`
    fixture is the test's own call; and whether passing a function as a
    callable argument to the code under test covers it.
  - Doc4: whether a spec's header `**Date:**` dates its sections; whether an
    implemented spec's account of its own change (its briefs at "version 1",
    its list of listed questions) drifts once later changes move on; whether
    a statement that work is part of a `TODO.md` item drifts once the item
    moves to `DONE.md`; whether a present-tense sentence in a bullet that
    starts "found <date>" is dated; and whether a table recording one
    change's version bumps is a dated record.
  - Doc5: whether a parenthetical list or a list of exit conditions claims
    to be complete, and whether a broad "any existing file" claim drifts
    when the code asks about named files only.
- **Asked for:** settle each in its brief, bumping the brief's version, so
  every reviewer applies the same threshold.

### A9 should not read a registered check's `check_` name as a purity promise

- **Raised:** 2026-11-21, by this repository's own first full audit (review-1, decision D3).
- **What happens:** A9 lists `check_` among the pure prefixes. In the
  checker's registry (`checks/auditme/registry.py`) `check_` is the naming
  convention for a check, and every check reads the tree and prints hits, so
  that audit's A9 reported every registered check (68 sites), all dismissed
  for that one reason. Any project whose `check_*` functions validate by
  reading meets the same conflict.
- **Asked for:** a refinement (a narrowing): a function registered as a
  check, by the project's registry or a decorator that registers it, is not
  read as pure-named. The refinement names the positive evidence (the
  registration), not the prefix alone.

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
