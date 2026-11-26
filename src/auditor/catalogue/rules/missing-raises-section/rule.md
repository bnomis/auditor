# missing-raises-section

Flag functions whose body raises a project exception but whose
docstring lacks any `Raises:` / `:raises:` section.

Signal:
  - Function has a non-empty docstring.
  - Function body contains at least one `ast.Raise` whose exception
    class name ends in `Error` and that is NOT a bare `raise` inside
    an except block (pure re-raise) and NOT a re-raise of a caught
    variable (`raise exc_var`).
  - Docstring contains NO `Raises:` block, `:raises X:` role, or
    sentence beginning with `Raises `.

Refinement (2026-11-01): a raise that a handler around it catches, by its
own class or a base class in the package's class tree (a bare `except:`,
`Exception` and `BaseException` catch all), without re-raising, does not
reach the caller and does not count (`auditor.api.level_catches`). A def nested in
the subject counts only where it is called by bare name, under that
call's handlers (`auditor.api.nested_call_sites`); a nested def never called counts
nothing, and stays a subject of its own. A handler that re-raises, one
for an unrelated class, or no handler keeps the hit.
