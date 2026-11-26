# leading-underscore-binding

Flag a leading-underscore parameter or bound name, wherever it occurs.

The text patterns see a leading underscore only where a regex can anchor
on it: a module-level `def`/`class`/assignment, and once saw the first or
second name of an unpack or loop target. That left a starred `*_rest`, a
third-or-later tuple position, every parameter (including `*_args`,
`**_kwargs` and lambda arguments) and every function-local assignment
invisible. This check walks the AST for all of them and replaces the
five `destructure`/`forloop` regexes, which it subsumes.

Signal: see `leading_underscore_bindings`.

Refinements (each has a test asserting it does not fire):
  - Bare `_` does not fire; it is the sanctioned throwaway.
  - A dunder or a name-mangled `__foo` does not fire.
  - A module-level `_NAME = ...` does not fire here: the const regexes
    report it.

Whether a bound underscore name is also *read* is a separate defect,
reported by `underscore-unpack-target-read` and
`underscore-forloop-target-read`.

Raised as a request by an audit (shipped 2026-10-05) whose S2 found
many such sites across its test modules.
