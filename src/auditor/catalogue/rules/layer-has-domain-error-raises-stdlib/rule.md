# layer-has-domain-error-raises-stdlib

Flag modules that raise stdlib exceptions (FileNotFoundError, KeyError,
RuntimeError, TypeError, ValueError) for domain errors when a sibling `errors.py` in
the same package defines a domain-error class.

Signal:
  - Package P contains an `errors.py` defining at least one `*Error`
    class.
  - Another module M in the same package P raises a stdlib exception
    (FileNotFoundError, KeyError, RuntimeError, TypeError, ValueError) at module-level
    or function scope.
  - The stdlib raise is NOT inside an `except` block (which is the
    re-raise-with-narrower-type pattern and is fine).

Scope rationale: the "widen to any module that imports a
domain `*Error` lazily" variant was tried and discarded because it
over-fired on `config/structures.py.__post_init__` validation raises,
which AGENTS.md's "Error type policy by layer" permits (`config` has
no own `*Error` class and only lazily imports `PipelineError` for a
narrow cross-stage violation). The narrower same-package predicate is
the stable form.
