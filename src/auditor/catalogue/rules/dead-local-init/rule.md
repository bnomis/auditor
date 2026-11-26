# dead-local-init

Flag function bodies where a local variable is assigned an
initial value at the top of the body, then unconditionally reassigned
before any use in all code paths.

Simple signal (low-FP only):
  - First statement in function body is `x = <literal or empty constructor>`.
  - All subsequent statements in the function body before the first
    read of `x` are reassignments to `x` inside a closed branch
    structure (an `if/elif/else` chain where every branch ends with
    `return <expr involving x>` or with `x = ...`).

Restricting to "initial empty-constructor assignment + exhaustive
if/elif/else that returns" keeps the check low-FP.
