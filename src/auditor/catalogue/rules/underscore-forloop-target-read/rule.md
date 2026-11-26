# underscore-forloop-target-read

Flag `for _x in ...:` (or tuple form `for _x, y in ...:`) where
`_x` is subsequently READ inside the loop body.

Signal:
  - `ast.For` / `ast.AsyncFor` with a target that contains a leading-
    underscore `Name(ctx=Store)` (not bare `_`, not dunder).
  - The same name appears as `ast.Name(ctx=Load)` within the loop's
    body statements (not nested function defs).
