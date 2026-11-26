# parameter-mutation-in-pure-function

Flag functions that mutate a parameter's dict/list items while
the function name or docstring suggests pure validation / checking.

Signal:
  - Function F has parameter P (typed as dict/list or named like
    `merged`, `config`, `data`, `params`).
  - F's name starts with `check_`, `validate_`, `is_`, `has_`,
    `get_`, `compute_`, `resolve_`, `parse_`.
  - F's body contains `P[key] = value` or `P.update(...)` or
    `P.pop(...)` or `P.append(...)` or similar mutation on P.
