import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a module-level function whose body is exactly `return f(...)` of its own parameters."""
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.decorator_list:
                continue
            # strip a leading docstring
            body = [b for b in node.body if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
            if len(body) != 1:
                continue
            stmt = body[0]
            if not isinstance(stmt, ast.Return) or not isinstance(stmt.value, ast.Call):
                continue
            call = stmt.value
            # Compare args: every positional must be a Name matching a parameter
            param_names = [a.arg for a in node.args.args]
            if not call.args:
                continue
            if not all(isinstance(a, ast.Name) and a.id in param_names for a in call.args):
                continue
            if not all(kw.arg is not None and isinstance(kw.value, ast.Name) and kw.value.id in param_names for kw in call.keywords):
                continue
            passed = [a.id for a in call.args if isinstance(a, ast.Name)] + [kw.value.id for kw in call.keywords if isinstance(kw.value, ast.Name)]
            if len(passed) != len(set(passed)):
                continue
            call_src = ast.unparse(call.func)
            # skip self.<method>(args) - that's typical delegation, not a shim
            if call_src.startswith('self.'):
                continue
            accept = auditor.api.accept_reason(lines, node.lineno, rule='passthrough-shim')
            auditor.api.emit(
                rule='passthrough-shim',
                variant=f'{node.name} is a pass-through wrapper for {call_src}',
                path=rel,
                line=node.lineno,
                evidence=f'def {node.name}(...): return {call_src}(...)',
                accepted=bool(accept),
                accepted_reason=accept,
            )
