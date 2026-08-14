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

### `dict.get` with a container default, then a method call on the result

- **Raised:** review-6 (litrev), 2026-08-14
- **Shape:** `x = parsed.get('usage', {})` followed by `x.get('input_tokens', 0)`
  (or `.items()`, `.keys()`, iteration). `dict.get`'s default fires only for an
  *absent* key, so an explicit `null` in the payload returns `None` and the next
  call raises `AttributeError`/`TypeError` - not the package's domain error, so
  the caller's `except <Domain>Error` handler misses it.
- **Why it earns a check:** this was the most common residual Sec2 shape in
  litrev, at ~21 sites across six packages, and it is what review-5's F5 turned
  into after the reported site was fixed - the same defect one level down, in
  the same function. It is purely syntactic: an `Assign` whose value is a
  `Call` to `.get` with a `Dict`/`List` literal second argument, where the
  target is later the receiver of an attribute call in the same scope. The
  cure, `parsed.get('usage') or {}`, is equally mechanical.
- **Scope note:** fire only when the default is an empty container literal. A
  scalar default (`0`, `''`) has no method call after it and is not this defect.

### `__all__` declared as an annotated assignment

- **Raised:** review-6 (litrev), 2026-08-14
- **Shape:** `__all__: list[str] = ['X']` (an `ast.AnnAssign`) rather than
  `__all__ = ['X']` (an `ast.Assign`).
- **Why it earns a check:** on litrev this silently switched off the entire
  public-surface guard for one package. `test_package_surfaces.py`'s
  `declares_all()` matched `ast.Assign` only, so `litlib.commands` never entered
  `PACKAGES`: its `__all__` entry was never checked for a consumer, and thirteen
  private-submodule exception entries written for it were inert. The test suite
  passed throughout. This is the worst failure mode a guard has - reporting
  green while checking nothing - and it is one AST node type to detect.
- **Scope note:** the check is not "annotated `__all__` is wrong"; it is that a
  project whose surface guard discriminates on assignment form has a hole. Fire
  on the annotated form wherever a project has an `__all__`-based guard, and let
  the accept marker carry the case where the guard handles both.

## Rejected

Kept so a rejected idea is not re-raised by a later audit that rediscovers it.

### `mutable-module-level-exported` should handle `Call` values

- **Raised:** review-3 (litrev), carried to review-4 and review-5
- **Reason:** the check would miss `DEFAULTS = get_defaults()` if that were
  mutable, because the value is a `Call` rather than a dict literal. Nothing is
  currently hidden by this - `DEFAULTS` is a `MappingProxyType` - so the check
  would gain complexity to catch a case that does not exist. Revisit only if a
  real mutable `Call`-valued export appears.
