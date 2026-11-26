# bare-parametric-annotation

Flag annotations that use `dict`, `list`, `tuple`, `set`, or
`frozenset` without a parametric type (`dict[str, int]`, `list[X]`,
etc.). Bare `dict` / `list` loses type information that pyright /
mypy / readers need.

The element types inside a subscript are read too (`list[dict]`,
`dict[str, dict]`), except `Literal[...]` arguments, `Annotated`
metadata and string forward references.

Applies to:
  - function parameter annotations
  - function return annotations
  - class / module-level AnnAssign targets
  - local AnnAssign targets inside function bodies
