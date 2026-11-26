# pure-name-has-side-effect

Flag functions whose name suggests a pure query/resolution but
whose body calls a disk-write or I/O function.

Signal:
  - Function name starts with `resolve_`, `find_`, `get_`, `check_`,
    `parse_`, `is_`, `has_`, `validate_`, `count_` or `allocate_`.
  - Function body contains a call whose callee short-name is in
    `auditor.core.SIDE_EFFECT_CALL_NAMES` (filesystem writes), or a call
    in `PURE_NAME_IO_CALLS` (opening or reading a file, testing for
    existence, subprocess, the clock).
  - The call is not inside a nested `def` (otherwise we'd flag factory
    functions that return a closure).
  - A `check_` function the corpus registers (a member of a module-level
    tuple, list, set or dict-value literal, or decorated by a package
    function) is not read as pure-named.
