# bare-nonbuiltin-generic-annotation

Flag annotations that reference a parameterisable non-builtin
class without its type parameter.

Signal:
  - `ast.AnnAssign.annotation` or a parameter annotation is an
    `ast.Attribute` (e.g. `multiprocessing.Queue`) OR an `ast.Name`
    whose resolved full name is in the parametric-non-builtin set.
  - The annotation is NOT wrapped in `ast.Subscript` (which would
    indicate parametric use like `multiprocessing.Queue[int]`).

Builtin generics (`dict`/`list`/`tuple`/`set`/`frozenset`) are
handled by `check_bare_parametric_annotation` and skipped here.
