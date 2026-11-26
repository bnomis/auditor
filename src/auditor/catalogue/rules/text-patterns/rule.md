# text-patterns

Flag source lines that match a text pattern.

Refinement (2026-11-21): the rules in `CODE_ONLY_RULES` read each line with
its non-docstring string literals blanked, so fixture source or a regex
held in a plain string is not read as code. A docstring is still read.

## Nested leading-underscore def or class

The pattern for `leading-underscore-def-class` anchors on `^(def|class) _`,
so it sees module-level definitions only. The same directory also flags a
leading-underscore `def` or `class` defined inside a function body, under the
same rule id, because it is the same defect and a project's existing scoped
accept markers answer for both.

Signal: an `ast.FunctionDef`, `ast.AsyncFunctionDef` or `ast.ClassDef` whose
name starts with a single underscore, lexically inside a function body at any
depth.

Refinements (each has a test asserting it does not fire):

- A method does not fire: a `def _m(self)` inside a class inside a function is
  a method, not a nested helper.
- A dunder (`__init__`, `__enter__`) does not fire.
- A name that shadows an outer binding does not fire: a nested `_foo` where
  `_foo` is also defined at module scope is a deliberate local override.
- Bare `_` does not fire.

Shipped 2026-09-01, raised by an audit that found instances invisible across
many audit cycles while the rule reported almost none.
