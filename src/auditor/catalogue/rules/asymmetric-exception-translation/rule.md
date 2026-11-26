# asymmetric-exception-translation

Detect functions F such that:
  - F is a module-level (or public-looking) function that itself does
    NOT have a try/except around its body translating third-party
    exceptions to a project error class.
  - Every known call site of F is inside a `try: ... except <ProjectError>: ...`
    block that catches a third-party exception class and translates.
  - There are 2+ call sites with this shape.

The asymmetric contract is a smell: a new caller that doesn't wrap F
will leak the third-party exception. Mechanical signal the finding.

F must also have something to translate: its own body (nested defs
skipped) calls a filesystem-touching name or a module imported from outside
the package, and does not call a same-module translating function.
