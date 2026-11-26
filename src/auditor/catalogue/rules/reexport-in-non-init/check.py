import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a module-level `X = dotted.path.X` in a file other than `__init__.py`."""
    for path in auditor.api.all_py_files(src_root):
        if path.name == '__init__.py':
            continue
        rel = auditor.api.relpath(path, scope)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        lines = auditor.api.source_lines(path)
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            # pattern: LHS is a single Name; RHS is Attribute whose
            # trailing .attr matches the LHS name
            if len(node.targets) != 1:
                continue
            tgt = node.targets[0]
            if not isinstance(tgt, ast.Name):
                continue
            if not isinstance(node.value, ast.Attribute):
                continue
            if node.value.attr != tgt.id:
                continue
            # The RHS must be a module path (Attribute of Attribute or Name)
            rhs_src = ast.unparse(node.value)
            accept = auditor.api.accept_reason(lines, node.lineno, rule='reexport-in-non-init')
            auditor.api.emit(
                rule='reexport-in-non-init',
                variant=f'`{tgt.id} = {rhs_src}` at module scope in non-__init__.py file',
                path=rel,
                line=node.lineno,
                evidence=(lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
