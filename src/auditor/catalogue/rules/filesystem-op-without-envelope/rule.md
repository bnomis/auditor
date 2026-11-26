# filesystem-op-without-envelope

Flag public entry-point functions that perform filesystem writes
(`write_text` / `write_bytes` / `mkdir` / `unlink` / `rmtree` / etc.)
WITHOUT a surrounding try/except anywhere in the function body.

Signal:
  - Function F lives in a package P whose `errors.py` defines at
    least one `*Error` class (so the layer has a domain error to
    translate to).
  - F is a PUBLIC entry point of the package: either exported from
    the package's `__init__.py` (via `__all__` or a `from .X import F`
    re-export), OR its docstring mentions `Raises` (signalling it is
    part of the package's error contract).
  - F calls a filesystem-write primitive
    (`write_text`, `write_bytes`, `mkdir`, `unlink`, `rmdir`,
    `touch`, `rmtree`, `makedirs`, `symlink_to`, `copytree`).
  - The call is not inside any `ast.Try` block within F.

Internal utilities (functions called only by other functions in the
same package) are NOT flagged - they legitimately let `OSError`
propagate to a caller that holds the envelope.

`filesystem-envelope-gap` catches the case where a try exists but
the except tuple is too narrow. This check catches the case where
no try exists at all AND the function is part of the package's
public error contract.

Refinement (2026-11-21): a call to a function defined in the same module
whose own body wraps a call in a `try` with a handler for `OSError` (or
`IOError`, `Exception`, `BaseException`, or a bare `except`) is not a
filesystem primitive: the helper holds the envelope. A method call
(`x.read_text()`) is never resolved this way, only a bare name.
