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

### `domain-error-envelope-covers-json-parse`

- **Raised:** review-7 (litrev), 2026-08-16
- **Shape:** a function whose only error envelope is a **decorator** or
  **contextmanager** (rather than a lexical `try/except`) whose except tuple omits
  an exception the body's parser can raise. Concretely: a body calling
  `json.loads`/`json.load` inside a function wrapped by a translator whose tuple is
  narrower than the locked A2 set.
- **Why the existing checks miss it:** `filesystem-envelope-gap` and the A2
  mechanical checks look for a lexical `try/except` in the function. A
  `@translate_sqlite_errors`-style decorator is invisible to that scan, so the
  function reads as "no envelope at all" (and is skipped, being neither exported
  with a `Raises:` nor lexically guarded) rather than as "envelope with the wrong
  tuple".
- **Evidence it is worth catching:** on litrev, `store/query.py:57,149,158` sat
  undetected across six audit cycles. All three call `json.loads` on a sqlite
  column value inside functions documenting `Raises: StoreError` whose only
  envelope catches `sqlite3.Error`. A malformed `runs.config` therefore raises a
  raw `json.JSONDecodeError` out through `citations/render.py` to the CLI, which
  does not list it in `DOMAIN_ERRORS` - so the user gets a bare traceback. Found by
  hand under Phase B A2; no mechanical rule reports it.
- **Suggested implementation:** resolve decorator names to their definitions
  within the package, read the `except` tuple of the contextmanager/decorator body,
  and treat it as the enclosing envelope for A2's locked-set comparison. Carve-out:
  a decorator whose body has a bare `except Exception` satisfies the set, as a
  lexical one does.
- **Catch-up surface to expect on litrev:** at least the three `store/query.py`
  sites; re-run the whole sweep to find the rest.

## Rejected

Kept so a rejected idea is not re-raised by a later audit that rediscovers it.

### `mutable-module-level-exported` should handle `Call` values

- **Raised:** review-3 (litrev), carried to review-4 and review-5
- **Reason:** the check would miss `DEFAULTS = get_defaults()` if that were
  mutable, because the value is a `Call` rather than a dict literal. Nothing is
  currently hidden by this - `DEFAULTS` is a `MappingProxyType` - so the check
  would gain complexity to catch a case that does not exist. Revisit only if a
  real mutable `Call`-valued export appears.
