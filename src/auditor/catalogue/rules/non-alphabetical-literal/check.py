import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def is_fixed_length_tuple(annotation: ast.expr) -> bool:
    """Return True for `tuple[X, Y]` (also under `Final[...]`), not `tuple[X, ...]`.

    A fixed-length tuple's positions carry meaning - a pattern and its
    replacement, an expected order - so sorting its members would change it.
    """
    if isinstance(annotation, ast.Subscript) and ast.unparse(annotation.value) in {'Final', 'typing.Final'}:
        annotation = annotation.slice
    if not isinstance(annotation, ast.Subscript) or ast.unparse(annotation.value) != 'tuple':
        return False
    members = annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
    return not any(isinstance(m, ast.Constant) and m.value is Ellipsis for m in members)


def ruff_dunder_all_key(name: str) -> tuple[int, list[int | str]]:
    """Sort key for ruff's RUF022 order of `__all__`.

    Group 0: more than one character and `name.isupper()` (SCREAMING_SNAKE);
    group 1: first character upper case (CamelCase); group 2: the rest.
    Within a group, natural order: digit runs compare as integers.
    """
    if len(name) > 1 and name.isupper():
        group = 0
    elif name[:1].isupper():
        group = 1
    else:
        group = 2
    natural = [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', name)]
    return group, natural


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a module-level string tuple, list, set or `frozenset(...)` literal not in sorted order."""
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            if isinstance(node, ast.AnnAssign) and is_fixed_length_tuple(node.annotation):
                continue
            value = node.value
            if value is None:
                continue
            members = None
            if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
                members = value.elts
            elif (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == 'frozenset'
                and value.args
                and isinstance(value.args[0], (ast.Set, ast.List, ast.Tuple))
            ):
                members = value.args[0].elts
            if not members or len(members) < 2:
                continue
            if not all(isinstance(m, ast.Constant) and isinstance(m.value, str) for m in members):
                continue
            actual = [m.value for m in members]
            if actual == sorted(actual):
                continue
            if auditor.api.is_dunder_all_assignment(node) and actual == sorted(actual, key=ruff_dunder_all_key):
                continue
            accept = auditor.api.accept_reason(lines, node.lineno, rule='non-alphabetical-literal')
            auditor.api.emit(
                rule='non-alphabetical-literal',
                variant='string members not alphabetically sorted',
                path=rel,
                line=node.lineno,
                evidence=f'{actual!r}',
                accepted=bool(accept),
                accepted_reason=accept,
            )
