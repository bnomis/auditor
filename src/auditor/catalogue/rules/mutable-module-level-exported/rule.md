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
