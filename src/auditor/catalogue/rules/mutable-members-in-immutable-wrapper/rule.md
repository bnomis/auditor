# mutable-members-in-immutable-wrapper

Flag an externally-read module-level container that is wrapped in an
immutable wrapper but holds mutable members.

Signal:
  - Module-level `NAME = <wrapper>(<literal or comprehension>)`, where
    `<wrapper>` is `types.MappingProxyType`, `frozenset` or `tuple` - the
    three A20 accepts.
  - `NAME` is read from another file (the same predicate, and the same
    scan, as `mutable-module-level-exported`).
  - A member of the wrapped literal is itself mutable: a `dict`/`list`/
    `set` literal or comprehension, or an instance of a dataclass this
    corpus defines without `frozen=True`.

Every one of those wrappers is shallow. `types.MappingProxyType({'a': []})`
passes `mutable-module-level-exported` and still hands every caller the
same live `list`; on one project a proxy's values were the very objects a
`get_defaults()` helper returned, so `defaults[k].append(...)` mutated the
process-wide default seen through both names. A project that has adopted
A20 reads the passing check as a guarantee, which is what makes this shape
worth its own rule rather than a footnote to that one: it is a guard that
fails open.

Deliberately syntactic. A member whose mutability is decided elsewhere -
`MappingProxyType({'a': build()})` - is not covered, for the reason the
`Call` case is rejected for A20: the assignment does not state the type.
The dataclass carve-in is not an exception to that; a dataclass's
mutability is stated by its own decorator, in this corpus, and read there.
