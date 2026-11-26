import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `from X import Y` in any file other than an `__init__.py`."""
    for path in auditor.api.all_py_files(src_root):
        if path.name == '__init__.py':
            continue
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module == '__future__' or any(alias.name == '*' for alias in node.names):
                continue
            module = f'{"." * node.level}{node.module or ""}'
            names = ', '.join(alias.name for alias in node.names)
            accept = auditor.api.accept_reason(lines, node.lineno, getattr(node, 'end_lineno', None), rule='from-import')
            auditor.api.emit(
                rule='from-import',
                variant='from X import Y outside an __init__.py',
                path=rel,
                line=node.lineno,
                evidence=f'from {module} import {names}'[:200],
                accepted=bool(accept),
                accepted_reason=accept,
            )
