# discarded-tuple-return

Flag a call whose tuple result is thrown away (A23, mechanical part).

Signal: an expression statement (`ast.Expr`) whose value is a call, or
an `await` of one, that `auditor.core.resolve_call` resolves to a
function of the swept package annotated `-> tuple[A, B, ...]` with two
or more element types (the `typing` alias `Tuple` too). `tuple[X, ...]` is a
sequence, not a multi-return, and does not count. `_ = f()` and
`a, _ = f()` name the discard and are not hits.

Calls resolve as `raises-section-drift` resolves them, so an unresolved
call is not a hit, and a function returning a tuple without annotating
it is left to Phase B. `related` names the callee's file when it
differs from the caller's.
