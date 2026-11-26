# dataclass-optional-always-set

Flag dataclass fields annotated as `X | None` (defaulting to
`None`) where `__post_init__` unconditionally reassigns them to
a non-None value. The `| None` is inaccurate - the field is never
None after construction.

Signal:
  - Class decorated with `@dataclass` or inheriting from a dataclass
    convention.
  - AnnAssign field `X: Y | None = <default>` (or `= field(default=None)`).
  - `__post_init__` method assigns `self.X = <expr>` unconditionally
    (not inside an `if`/`try`/`for`).
