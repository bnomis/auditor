# bare-except-in-module-with-narrow-errors

Flag modules that inconsistently mix `except Exception` / `except
BaseException` with narrow `except <X>_ERRORS:` tuples in separate
sites. The mixed pattern signals an incomplete sweep toward narrow
except tuples.

Signal:
  - Module has at least one `except Exception` / `except BaseException`
    (bare or with bound name).
  - Module ALSO has at least one `except <NAME>_ERRORS:` or
    `except (*<NAME>_ERRORS, ...):` tuple-handler where NAME_ERRORS
    is referenced as an `ast.Name`.
  - Flag the bare-except sites, not the narrow ones.
