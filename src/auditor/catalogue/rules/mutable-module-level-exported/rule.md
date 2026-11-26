# mutable-module-level-exported

Flag module-level mutable containers that are read by name from
another module in the same corpus. Externally-read globals should
be immutable so callers cannot mutate shared state.

Signal:
  - Module-level `NAME = {...}` / `NAME = [...]` / `NAME = {...}` set
    literal, the comprehension form of any of the three, or a call to
    the bare builtin `dict(...)` / `list(...)` / `set(...)`, where the
    value is NOT wrapped in `types.MappingProxyType`, `frozenset`, or
    `tuple`.
  - `NAME` is read from another file, as `from <this-module> import NAME`,
    as `<this-module>.NAME`, or as
    `sys.modules['<this-module>'].NAME`; see `dotted_read`.

Locked enumeration (per SKILL.md A20):
  dict -> must be `types.MappingProxyType(...)`.
  set  -> must be `frozenset(...)`.
  list -> must be `tuple(...)`.

A comprehension is the same container as its literal - `{k: f(k) for ...}`
is a `dict`, mutable and shared exactly as `{...}` is - so it is the same
finding, and so is a builtin constructor call (`list(...)`), which states
its type just as plainly (ruled 2026-10-31). Any other `Call` value
(`DEFAULTS = get_defaults()`) is deliberately NOT covered: its type is not
knowable from the assignment.

The reader scan covers every root the sweep reads - every package under
`src/` and every extra root such as `bin/` - not just the root being
swept; see `corpus_py_files`.

A wrapped value is this check's non-goal and
`check_mutable_members_in_immutable_wrapper`'s subject: the wrapper is
shallow, so `types.MappingProxyType({'a': []})` satisfies this predicate
while still handing every caller a live `list`.

Private (non-read) mutable globals are NOT flagged - that is a
different rule.

## Rejected widenings

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
