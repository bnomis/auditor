# except-interpolation

Flag f-string or logger-positional interpolation of a caught
exception variable inside an ``except ... as <bound>:`` block.
Rationale: ``raise X from exc`` and ``logger.exception(...)`` already
preserve the chained traceback at full fidelity; embedding
``str(exc)`` (or its f-string equivalent) into a new message
produces a truncated copy that drifts from the original.

Exception: ``type(<bound>).__name__`` / ``__qualname__``
and ``<bound>.__class__.__name__`` / ``__qualname__`` access only
the exception class name string. The class name is a categorical
hint, not a lossy duplication of the message body, so these
patterns are skipped without emitting a hit. See
``is_categorical_class_name_expr``.
