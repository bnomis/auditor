# docstring-raises-mismatch

Flag functions whose docstring declares `Raises: <X>` (or a
sphinx-style `:raises X:` or a plain 'Raises X' sentence) where the
body actually raises a different exception class.

Signal:
  - Function has a docstring.
  - Docstring mentions at least one exception class name (via
    `Raises:` section, `:raises X:` role, or 'Raises FooError' prose).
  - Function body contains `raise <Y>(...)` statements, all of which
    raise a class NOT listed in the docstring, and no `raise` re-raises
    a caught variable.
