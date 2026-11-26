import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a `for` target with a leading underscore whose name is read inside the loop body."""
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.For, ast.AsyncFor)):
                continue
            underscore_targets = auditor.api.leading_underscore_names(node.target)
            if not underscore_targets:
                continue
            # Collect loads inside loop body
            body_loads: set[str] = set()
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                        continue
                    if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                        body_loads.add(sub.id)
            for name, lineno in underscore_targets:
                if name not in body_loads:
                    continue
                accept = auditor.api.accept_reason(lines, lineno, rule='underscore-forloop-target-read')
                auditor.api.emit(
                    rule='underscore-forloop-target-read',
                    variant=f'for-loop target `{name}` read inside body',
                    path=rel,
                    line=lineno,
                    evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
