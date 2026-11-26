# failure-as-absence

Flag a clean-absence return reached from a caught exception or a non-200.

AGENTS.md ("Failure versus absence") requires that a source or resolver
never return None/[] for a non-200 response or a caught exception without
also recording a failure the caller can see - by raising, or by setting an
error field the caller reads. Returning empty is reserved for a genuine
"the request completed and there was nothing to find". Conflating the two
makes a network outage read as "this paper has no match", which is silently
wrong rather than loudly wrong.

Two shapes are detected:
  A. An `except` handler whose body reaches a clean-absence return with no
     raise and no error-recording statement.
  B. The non-200 branch of an HTTP status test doing the same.

Deliberately NOT detected - documented non-goals, not oversights:
  - The loop-continue shape, where a per-item handler `continue`s and the
    function later returns a collection that happens to be empty. Catching
    it needs flow analysis and would fire on legitimate partial-result
    paths, where returning what did parse is correct.
  - Count guards such as `if failed == attempted: raise`, where the defect
    is the arithmetic and the return is innocent.
Both remain Phase B's job. This check owns the direct shapes, where a
verdict needs no judgement.
