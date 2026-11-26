# build-name-has-side-effect

Flag `build_*` / `compute_*` / `make_*` functions that call subprocess, clock,
uuid, random, or filesystem-write primitives. `build_*` names imply
pure assembly from inputs; the listed side-effect calls contradict
that contract.

Signal:
  - Function name starts with `build_`, `compute_` or `make_`.
  - Function body contains a call whose callee short-name is in the
    side-effect set below (extends `SIDE_EFFECT_CALL_NAMES` with
    `subprocess.run`, `datetime.now`, `uuid.uuid4`, `time.time`).
  - The call is not inside a nested function.

The separate `check_pure_name_has_side_effect` covers the 9 other
pure prefixes; `build_`/`compute_` are split out because their
side-effect enumerations include clock/uuid (not relevant to the
others) and because reporting's `build_*_data` family has a large
number of accepted-via-comment sites that would dominate the output
if bundled.
