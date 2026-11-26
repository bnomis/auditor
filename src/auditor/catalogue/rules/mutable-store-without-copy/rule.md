# mutable-store-without-copy

Flag `__init__` methods that store a parameter typed as dict/list
onto `self.<name>` without taking a defensive copy. Callers share
the reference with the instance; if anyone mutates later, all
observers see the change.

Signal:
  - `__init__` has a parameter P whose annotation mentions `dict`
    or `list` (at the top level; allows `dict | None`, `list[str]`,
    `dict[str, Any]` forms).
  - The body assigns `self.<P> = <P>` with no `.copy()` /
    `.deepcopy()` / `dict(...)` / `list(...)` / `frozenset(...)`
    wrapping.
  - The parameter is not annotated as `frozenset`, `tuple`, or a
    project dataclass (which is immutable by convention).
