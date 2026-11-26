# underscore-unpack-target-read

Flag tuple-unpack assignments with a leading-underscore target
whose name is subsequently READ in the enclosing scope. A leading
underscore conventionally marks an unused binding; reading it is
misleading.

Signal:
  - `ast.Assign` or `ast.AnnAssign` where the target is a Tuple/List
    containing `Name(id='_foo', ctx=Store)` with a leading underscore
    (not bare `_`, not dunder).
  - `_foo` appears as `ast.Name(ctx=Load)` somewhere later in the
    same function (or module scope if at module level).
