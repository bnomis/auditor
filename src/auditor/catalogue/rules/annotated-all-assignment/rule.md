# annotated-all-assignment

Flag `__all__: list[str] = [...]` in a project that guards `__all__`.

An annotated assignment is an `ast.AnnAssign`, not an `ast.Assign`. A
public-surface guard written to match `ast.Assign` therefore does not see
the module at all - and reports green while checking nothing, which is the
worst failure a guard has. On one project this switched the guard off for a
whole package: its `__all__` entries were never checked for a consumer, and
the private-submodule exception entries written for it were inert, while
the suite passed throughout.

The predicate is not "an annotated `__all__` is wrong". It is that a
project whose surface guard may discriminate on assignment form has a hole
wherever the annotated form appears. A guard that handles both forms is a
real answer - record it with an accept marker on the declaration, or
normalise the declaration to the plain form.

Fires only where the project has an `__all__`-based guard at all; see
`project_has_all_guard`.
