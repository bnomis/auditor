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

### `raises-section-drift` should follow pass-through callees and `Class.method()` calls

- **Raised:** 2026-11-20, by an audit whose Phase B A4 found by hand a set of
  `Raises:` omissions the check exists to catch. Each was traced to one of the
  two resolution gaps below; neither is a judgement call, so the question
  should stop costing a Phase B pass once both are closed.
- **Gap 1 - a callee with no `Raises:` section contributes nothing.** The
  check follows a callee one level, through the callee's declared section. A
  thin wrapper whose docstring defers to another function in prose ("see
  `perform()` for the Raises this shares") has no section, so every domain
  error that reaches the caller through it is invisible. Proposed: when a
  resolved same-package callee has no `Raises:` section, follow it into its
  own resolved callees (one further level, or to a fixed depth), rather than
  treating it as raising nothing.
- **Gap 2 - a classmethod or staticmethod called through its class name is
  not resolved.** `Config.load(path)` in the same module or package resolves
  to nothing, though `self.load(path)` would. Proposed: resolve
  `<ClassName>.<method>(...)` where `<ClassName>` is a class the package
  defines (same module, or imported by name or dotted path), the same way a
  method called on `self` is.
- **Test fixtures:** a caller of a section-less wrapper whose inner callee
  declares `ProbeError`, with and without the caller declaring it; and a
  caller of `Probe.load()` (a classmethod declaring `ProbeError`), with and
  without a catching handler.
- **Catch-up surface:** run on each project with the shared hooks before the
  entry is deleted, as [How an entry leaves](#how-an-entry-leaves) says.

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
