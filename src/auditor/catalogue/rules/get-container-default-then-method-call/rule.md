# get-container-default-then-method-call

Flag `x = d.get(k, {})` whose result is later a method-call receiver.

`dict.get`'s default fires only for an *absent* key. An explicit `null` in
the payload returns `None`, so the next `x.get(...)` / `x.items()` raises
`AttributeError` - not the package's domain error, so a caller's
`except <Domain>Error` handler misses it and the failure surfaces as a
traceback from somewhere else entirely. The cure is equally mechanical:
`d.get(k) or {}`.

The predicate is syntactic: an `Assign` to a single name whose value is a
two-argument `.get` call with an empty container literal as the default,
where that name is later the receiver of an attribute call, or is iterated,
in the same scope - and where the scope never tests the name for truth, for
None, or for its type (see `name_is_reguarded`).

Scope: non-test source only. In a test the payload is a fixture the author
wrote, so an explicit null cannot arrive unannounced.

Refinement (2026-11-21): a mapping produced by `tomllib.load` or
`tomllib.loads` is skipped, because TOML has no null. The receiver counts
when it is such a call, a call to a same-module function that returns one
(and otherwise only a dict literal, such as `{}` for an absent file), a name the scope assigns from either, or a parameter of a
module-level function that every same-module call passes one. See
`receiver_is_toml_mapping`.

Deliberately NOT detected - non-goals, not oversights:
  - A scalar default (`0`, `''`). Nothing is called on the result.
  - A non-empty container default. `d.get(k, {'a': 1})` fails the same way,
    but is rare enough that including it would only widen the predicate.
  - Subscripting the result (`x['k']`); see `none_hostile_use`.
