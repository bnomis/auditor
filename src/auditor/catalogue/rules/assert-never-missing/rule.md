# assert-never-missing

Flag `if/elif` chains and `match` statements that dispatch on string
values of one subject and end without `assert_never`.

The subject is a name or a dotted name (`self.kind`). An arm is
`subject == 'x'` (either order) or `subject in ('x', 'y')` (a tuple, list
or set of string constants). A chain needs three arms, or two when the
subject is a parameter or an annotated local typed `Literal[...]` with
three or more string members: the annotation is the evidence that a third
value exists, so an unannotated two-arm chain stays exempt as bi-valued.
A `match` needs three string-constant `case` patterns and is exhausted
only by a final `case _:` calling `assert_never`.

Cure: replace the trailing `else:` (or absent `else`) with
    else:
        typing.assert_never(var)
which lets the type-checker verify exhaustion.
