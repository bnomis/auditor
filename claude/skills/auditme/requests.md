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

### A user guide's parameter list is checked by nothing

- **Raised:** 2026-11-21, by an audit
- **Gap:** the Doc5 brief (`phaseb/briefs/Doc5.md`, Thresholds) leaves "a
  difference in the parameter list" to the sweep's `spec-api-signature-drift`
  rule. That rule reads only `def` lines in a spec's `## API` fenced block. A
  README or `docs/` page that shows a public function as an annotated call
  (`pkg.setup(a=..., b=...)`, one keyword per line) is read by neither: a
  parameter added to the function and missing from the guide's example passes
  both, although `user-guides.md` requires every option to be documented.
- **Seen as:** a guide's call example listing every keyword of a public
  function except the two most recently added.
- **Options:** extend the rule to a call of a uniquely named public function
  in a fenced block of `README.md` or `docs/`, reporting keywords the source
  has and the example lacks (or the reverse) when the example presents itself
  as the full signature; or narrow the Doc5 threshold so a guide's
  parameter-list omission is drift when the example lists more than one
  keyword.

### Listed briefs leave thresholds open that reviewers settle differently

- **Raised:** 2026-11-21, by an audit
- **Gap:** in one audit, reviewers of different batches of the same listed
  question settled these unsettled thresholds in opposite ways, so verdicts
  differed by batch until the orchestrator re-judged them:
  - T1: whether a test counts as calling the candidate when it calls a package
    re-export of the same object, or calls through a `functools.singledispatch`
    generic, a dispatch table or a parametrised name. Also whether a dunder
    (`__post_init__`, `__str__`, `__getattr__`) run by constructing, printing or
    attribute access counts, whether a one-line `__str__` forwarding to
    `summary()` counts as calling `summary`, and whether calls from a helper in
    the test file count. Related: the lister's `test_files` misses tests that
    import only the top-level package.
  - A4: whether a `singledispatch` entry point's `Raises:` owes the errors of
    its registered implementations; and whether a raise the candidate's own
    checks make unreachable (an invariant guard) counts as raised.
  - Doc4 and Doc5: whether one dated sentence inside an undated section is a
    dated record; whether "today" in an implemented spec is one; and where a
    drift that falls under several candidates of one section is reported.
- **Seen as:** one batch flagging a public function as untested while another
  counted the same kind of call as a direct test.
- **Options:** write each ruling into the brief's Thresholds (bumping its
  version so carried verdicts are re-judged), and have the T1 lister count a
  test file that imports the top-level package which re-exports the candidate.

### D2 has no carve-out for type-stub packages and notebook kernels

- **Raised:** 2026-11-21, by an audit
- **Gap:** D2 flags a declared dependency that is neither imported, run nor
  loaded through an entry point. A type-stub package (`*-stubs`) that the type
  checker reads, and an `ipykernel` that a notebook runner starts as its
  kernel, are both used but match none of the carve-outs.
- **Seen as:** two stub packages and a kernel package flagged as unused in a
  project that runs mypy and executes notebooks in its tests.
- **Options:** add a carve-out: a `*-stubs` / `types-*` package when the
  project runs a type checker, and a Jupyter kernel package when a declared
  dependency executes notebooks (`nbclient`, `nbconvert`, `papermill`).

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
