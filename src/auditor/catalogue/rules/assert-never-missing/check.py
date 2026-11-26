import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `if/elif` chains and `match` statements that dispatch on string
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
    """
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node, subject, arms, terminal_else in auditor.api.assert_never_findings(tree):
            kind = 'match' if isinstance(node, ast.Match) else 'if/elif chain'
            ending = 'has fall-through else' if terminal_else else 'has no else'
            accept = auditor.api.accept_reason(lines, node.lineno, rule='assert-never-missing')
            auditor.api.emit(
                rule='assert-never-missing',
                variant=(f'{kind} on `{subject}` with {arms} string arms {ending}; should end with `else: typing.assert_never({subject})`'),
                path=rel,
                line=node.lineno,
                evidence=(lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
