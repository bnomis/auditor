# subprocess-without-memoisation

Flag functions that invoke `subprocess.run` / `subprocess.check_output`
/ `subprocess.check_call` without a memoisation decorator, when the
function name suggests a request-invariant query.

Signal:
  - Function body calls one of `subprocess.run|check_output|check_call|
    Popen|call`.
  - Function has NO `@functools.cache`, `@functools.lru_cache`, `@cache`,
    or `@lru_cache` decorator.
  - Function name starts with a pure-query prefix (`get_`, `resolve_`,
    `compute_`, `find_`, `check_`, `parse_`, `is_`, `has_`, `validate_`,
    `count_`). Other names are assumed per-call intentional.
