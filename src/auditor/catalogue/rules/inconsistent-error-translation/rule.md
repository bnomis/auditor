# inconsistent-error-translation

Flag helper functions F that raise a domain error E, where two or
more distinct callers of F translate E to different project-error
classes. Divergent translation is a semantic bug: the same
underlying failure surfaces as different error types to different
consumers.

Signal:
  - Function F at path P has at least one `raise <E>(...)` where E
    ends in `Error` (a project domain error).
  - Two or more functions elsewhere call F, each wrapping the call
    in a `try: ... except <E>: raise <T_i>(...)` where the raised
    translation target classes T_i differ across callers.
