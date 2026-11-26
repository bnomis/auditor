# non-alphabetical-literal

Flag module-level string tuple, list, set and `frozenset(...)` literals not in sorted order.

Only top-level assignments are read, and a literal needs two or more string
members. A fixed-length tuple annotation (`tuple[str, str]`) is exempt,
since its positions carry meaning.

Refinement (2026-11-01): an `__all__` assignment (plain or annotated, single
target) also passes when its members equal `sorted(members,
key=ruff_dunder_all_key)`, the order ruff's RUF022 writes. Any other name
keeps the plain `sorted()` test.
