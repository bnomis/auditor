# filesystem-envelope-gap

Flag `try` blocks that call a filesystem-touching third-party
helper (`download_artifacts`, `from_pretrained`, `snapshot_download`,
etc.) where the `except` tuple does not include `OSError` (or a
parent like `Exception`/`BaseException`).

These helpers write to a local cache directory; disk-full,
read-only, or permission-denied failures surface as `OSError` /
`PermissionError`, not as the library's own exception. The narrow
except clause lets those propagate past the wrapper's promise to
translate to a project error class.

Refinement (2026-11-01): a bare name in a handler's type, alone or inside
a tuple, that names a module-level tuple literal assigned once in the same
file is read as that tuple's members, one level deep, so
`except READ_ERRORS:` with `READ_ERRORS = (OSError, ValueError)` is
covered. Any other name - another module's, a call's result, a nested
constant - keeps the name test. See `module_tuple_constants`.

Refinement (2026-11-21): a `try` is flagged only when one of its handlers
raises (`raise X`, with an exception), because the rationale is a wrapper
that promises to translate. A handler that returns, continues or logs
makes no such promise, so skipping a file on a decode error is not a gap.
A bare `raise` re-raises the original and does not translate.
