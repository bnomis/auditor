# cli-entry-missing-error-envelope

Flag CLI entry-point functions (top-level functions in `cli/*.py`
whose name starts with `run_`) that have no top-level try/except.

The rule: if at least one sibling CLI entry in the project does have
a top-level try/except catching a project error class, flag every
CLI entry that does not. CLI entries are the error envelope for
user-facing errors; an unenveloped entry will surface untranslated
third-party exceptions.
