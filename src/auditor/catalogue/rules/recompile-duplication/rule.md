# recompile-duplication

Flag module-level constants assigned from `re.compile(...)` when
the same CONSTANT NAME is also assigned from `re.compile(...)` in
another file.

Name collision across files is the real risk - the two copies read
as if they express the same predicate, so any change to one silently
drifts from the other. Comparing regex literals byte-wise would miss
functionally-equivalent variants (e.g., `r'^foo$'` vs `r'^(foo)$'`),
so the predicate is scoped to name duplication.

Signal:
  - Module-level `Assign`/`AnnAssign` whose RHS is
    `re.compile(<literal>)`.
  - Same LHS name appears in >= 2 distinct files.
