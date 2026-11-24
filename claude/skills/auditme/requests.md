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

### Close the sweep gaps one project's audits carried as script candidates (filed 2026-11-24)

One project's audits carried these as "script coverage" candidates across two
cycles, and the second dropped them without filing a request. Each was checked on
2026-11-24 against the checker at `3e23236`; a candidate the sweep already
catches is not listed.

- **`bare-parametric-annotation` misses bare inner generics.** The visitor
  returns at the first `Subscript`, so `list[dict]`, `dict[str, dict]` and
  `list[list]` never fire; only a top-level or union-member bare name does.
- **Discarded multi-return has no check.** A23 is Phase B prose only, with no
  rule and no lister: a call to a function annotated `-> tuple[...]` used as a
  bare expression statement is not listed anywhere.
- **`layer-has-domain-error-raises-stdlib` misses `FileNotFoundError`.** Its
  set is `ValueError`, `RuntimeError` and `KeyError`; the docstring also names
  `TypeError`, which the set lacks.
- **`assert-never-missing` needs three `==` arms.** A two-arm chain on a name
  annotated with a `Literal`, whose `else` assigns or returns for the remaining
  values, is not a sweep hit, though A11 lists it for a reviewer. The `Literal`
  annotation is the positive evidence the bi-valued exemption lacks; dotted
  subjects (`self.x`), `in` and `match` are not read either.
- **The pure-name rules miss `make_` and non-write IO.**
  `build-name-has-side-effect` reads only `build_` and `compute_`;
  `pure-name-has-side-effect` matches only filesystem writes, so a `get_` that
  reads a file or runs a subprocess is not a hit.
- **`asymmetric-exception-translation` fires on callees with nothing to
  translate.** A callee is skipped only when its own body has a top-level
  `try`. One that does no third-party IO (pure string work), or that
  translates through a helper it calls, is still a hit, and needs an accept
  marker.
- **A17 lists only an `__init__.py`'s `__all__`.** A submodule's `__all__`
  entry that no other file imports is never listed. (The candidate also asked
  for a carve-out for names only a public-API test reads; the A17 brief rules
  the opposite, "a name only tests read is a finding", so that part is not
  requested.)

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
