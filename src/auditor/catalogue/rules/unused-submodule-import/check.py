import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a top-level `import a.b.c` whose name the file never uses."""
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        full_src = '\n'.join(lines)
        for node in tree.body:
            if not isinstance(node, ast.Import):
                continue
            for alias in node.names:
                if alias.asname:
                    continue
                if '.' not in alias.name:
                    continue
                import_line_src = lines[node.lineno - 1] if node.lineno <= len(lines) else ''
                remainder = full_src.replace(import_line_src, '', 1)
                if re.search(rf'\b{re.escape(alias.name)}\b', remainder):
                    continue
                root_name = alias.name.split('.')[0]
                if re.search(rf'\b{re.escape(root_name)}\.', remainder):
                    continue
                accept = auditor.api.accept_reason(lines, node.lineno, rule='unused-submodule-import')
                auditor.api.emit(
                    rule='unused-submodule-import',
                    variant='import X.Y.Z never referenced',
                    path=rel,
                    line=node.lineno,
                    evidence=f'import {alias.name}',
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
