import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a module-level dict whose keys are all string literals and not in alphabetical order."""
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if not isinstance(value, ast.Dict):
                continue
            keys = value.keys
            if not keys or len(keys) < 2:
                continue
            if not all(isinstance(k, ast.Constant) and isinstance(k.value, str) for k in keys):
                continue
            actual = [k.value for k in keys]
            if actual == sorted(actual):
                continue
            accept = auditor.api.accept_reason(lines, node.lineno, rule='non-alphabetical-dict-keys')
            auditor.api.emit(
                rule='non-alphabetical-dict-keys',
                variant='dict with string keys not alphabetically sorted',
                path=rel,
                line=node.lineno,
                evidence=f'keys: {actual!r}',
                accepted=bool(accept),
                accepted_reason=accept,
            )
