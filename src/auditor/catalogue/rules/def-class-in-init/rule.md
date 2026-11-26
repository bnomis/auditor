# def-class-in-init

Flag a top-level `def` or `class` line in an `__init__.py`.

Signal: a line of an `__init__.py` that starts with `def ` or `class `
in column 0. Carve-outs: only `__init__.py` files are read; an indented
definition (inside an `if` block, say) is not matched.
