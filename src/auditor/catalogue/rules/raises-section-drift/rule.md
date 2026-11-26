# raises-section-drift

Flag a `Raises:` section that disagrees with the domain errors reaching
the caller (A4).

Signal:
  - A function or method whose docstring has a Google-style `Raises:`
    section (`auditor.api.raises_section_names`).
  - What reaches its caller: every domain error its body raises, plus every
    domain error a same-package callee's own `Raises:` section declares,
    minus each that an enclosing `except` catches without re-raising.
  - One hit per name the section omits, and one per domain error it
    declares that never reaches the caller although a handler in the
    function catches it - the positive evidence that it is caught there.

A domain error is an exception class the swept package defines - positive
evidence, so `sqlite3.Error` (tail `Error`) and a third-party `*Error` are
not one - and never a builtin (`auditor.api.STDLIB_ERRORS`). Subclasses follow the package's own class tree: catching
or declaring a base covers its subclasses. A callee with a `Raises:`
section is followed through that declared section, not its body; a callee
with no section is followed into its own raises and callees, up to
`SECTIONLESS_DEPTH` calls deep. Only calls within the package being swept
resolve: a module function called by its dotted path (or a name imported
from a package module), a same-module function, a method called on
`self`, or `<ClassName>.<method>(...)` for a class the package defines,
following re-exports such as a package `__init__.py`'s
`from pkg.mod import name`. A call the check cannot resolve contributes
nothing, which is why an extra needs a catching handler: without one, the
declared error may arrive through such a call.

Raised by an audit whose Phase B A4 kept finding these by hand, cycle
after cycle (shipped 2026-10-31).

Refinement (2026-11-01): a callee's declared error does not reach the
caller through a call that leaves unset every optional argument guarding
it (`unset_optional_guard`): every raise of it in the callee's own body
sits under an `if` or `match` testing a parameter with a default that the
call does not supply, as `if strict: raise ParseError(...)` called as
`load('x')`. Omissions only; a guard on a parameter without a default, a
module-level name, a raise outside the guard, or a call passing the
argument (or `*args`/`**kwargs`) keeps the hit. Other value-dependent
cases (fixed names, pre-checked values, dispatch types) are left to the
Phase B review (A4).

Refinement (2026-11-01), nested functions: a def nested directly in the
subject and called by bare name contributes its raises and calls under
the call's handlers (`auditor.api.nested_call_sites`, one level deep), so an error it
catches and re-raises on one branch still reaches the subject's callers;
a def never called contributes nothing. A raise inside a def, lambda or
class defined in a handler does not make that handler re-raise.

Extension (2026-11-20): both resolution gaps in the request "`raises-section-drift`
should follow pass-through callees and `Class.method()` calls" (a past change
request) are closed. A `<ClassName>.<method>(...)`
call resolves like a call on `self`, and a callee with no `Raises:` section
is followed into its own raises and callees up to `SECTIONLESS_DEPTH`
calls deep, with the chain named in the hit's variant. Omission hits grow;
an extra declaration is reported only if it still never reaches the caller.

Refinement (2026-11-24): a combined entry (`ParseError, FetchError:`)
declares each name, and an `except` naming a module-level tuple of classes
the package defines (`auditor.api.tuple_constants`) catches each member.

Extension (2026-11-24): the modules under each directory `[tool.auditme]
first-party` lists (`first_party_dirs`) join the tables, so a call into such
a library resolves as a same-package call, its `Raises:` sections are
followed and its error classes count as domain errors. Only the swept
package's functions are subjects: no hit lands on a library file, which
`related` names by its path relative to the project.

Raises:
    RootsError: a `first-party` entry is invalid (`first_party_dirs`).
