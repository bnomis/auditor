# redundant-sink-caller-plus-callee

Flag functions that call a sink S directly, and then call a helper
G which itself also calls S with IDENTICAL argument signatures.

Example: `run_evaluate` calls `flush_resolved_config(config, run_dir)`
at line L1, then calls `pipeline.tokenize(splits)` which itself
calls `flush_resolved_config(config, run_dir)`. The argument
signatures match, so the outer call is redundant.

Tight signal to avoid the O(n^2) false positives on large pipelines
(where one orchestrator calls five helpers that each log metrics -
those are NOT redundant, they log different arguments):
  - Function F calls sink S(args1) at line L1.
  - Function F calls helper G at line L2 where L2 > L1.
  - G is a module-level function in this project whose body also
    calls S(args2).
  - args1 and args2 have the same **normalised argument tails**:
    for each positional arg, the trailing name (`config`, `run_dir`)
    matches; for each keyword arg, the keyword and its value's trailing
    name match.
  - S's short name contains a sink token (`flush`, `write`, `save`,
    `persist`, `emit`, `dump`, `log`, `publish`, `upload`,
    `register`).

Refinements (2026-11-21), each removing a misread:
  - A call inside a def nested in F (or in G) belongs to the nested def,
    not to F, and is not counted for either.
  - A call from F to F itself (self-recursion) is not a helper call.
  - A helper is resolved by qualified name: `pipeline.tokenize` matches
    only a function whose module path ends `pipeline.tokenize`, and a bare
    `tokenize` matches the same module's function, else a single
    project-wide function of that name; an ambiguous bare name matches
    nothing.
  - Keyword values are compared as well as keyword names, so
    `write(path=a)` and `write(path=b)` are different calls.
