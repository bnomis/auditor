# typing-deprecated-alias

Flag `typing.Sequence`, `typing.Iterator` and every other `typing` alias
PEP 585 deprecated in favour of the standard-library class itself.

The coding standard prefers the standard generics to their `typing`
equivalents. `legacy-typing` reads that for the aliases of builtins -
`List[`, `Dict[` and the rest - and saw nothing else, so an audit
found `typing.Sequence` and `typing.Iterator` by hand under S4.

Signal, on the AST so a string or a comment never fires:
  - `typing.<alias>` anywhere, subscripted or not: `isinstance(x,
    typing.Mapping)` names the same deprecated alias an annotation does.
  - `from typing import <alias>`, once per alias at the import line. The
    bare uses that follow are the same decision, made once.

The variant names the replacement, so the fix is in the hit.

Not this rule's: the builtin aliases (`legacy-typing`), and a `typing`
name with no standard-library class to move to - `typing.Any`,
`typing.Protocol`, `typing.TypeVar`.
