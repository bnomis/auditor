import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


TUPLE_ANNOTATION_NAMES = {'Tuple', 'tuple', 'typing.Tuple'}


def is_multi_return_annotation(returns: ast.expr | None) -> bool:
    """Whether a return annotation is `tuple[A, B, ...]` with two or more element types. Pure."""
    if not isinstance(returns, ast.Subscript) or ast.unparse(returns.value) not in TUPLE_ANNOTATION_NAMES:
        return False
    if not isinstance(returns.slice, ast.Tuple) or len(returns.slice.elts) < 2:
        return False
    return not any(isinstance(element, ast.Constant) and element.value is Ellipsis for element in returns.slice.elts)


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a call whose tuple result is thrown away (A23, mechanical part).

    Signal: an expression statement (`ast.Expr`) whose value is a call, or
    an `await` of one, that `auditor.api.resolve_call` resolves to a
    function of the swept package annotated `-> tuple[A, B, ...]` with two
    or more element types (the `typing` alias `Tuple` too). `tuple[X, ...]` is a
    sequence, not a multi-return, and does not count. `_ = f()` and
    `a, _ = f()` name the discard and are not hits.

    Calls resolve as `raises-section-drift` resolves them, so an unresolved
    call is not a hit, and a function returning a tuple without annotating
    it is left to Phase B. `related` names the callee's file when it
    differs from the caller's.
    """
    modules: dict[str, tuple[pathlib.Path, ast.Module, list[str]]] = {}
    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is not None:
            modules[auditor.api.module_dotted(path, src_root)] = (path, tree, auditor.api.source_lines(path))

    known: dict[str, str | None] = {}
    multi: set[str] = set()
    path_of: dict[str, pathlib.Path] = {}
    for module, (path, tree, _) in modules.items():
        for node in tree.body:
            members = [(f'{module}.{node.name}', None, node)] if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else []
            if isinstance(node, ast.ClassDef):
                members = [
                    (f'{module}.{node.name}.{member.name}', node.name, member)
                    for member in node.body
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
            for qualname, cls, function in members:
                known[qualname] = cls
                path_of[qualname] = path
                if is_multi_return_annotation(function.returns):
                    multi.add(qualname)

    bindings_of = {module: auditor.api.call_bindings(tree, module, path.name == '__init__.py') for module, (path, tree, _) in modules.items()}
    aliases = auditor.api.reexport_aliases(bindings_of, known)

    for module, (path, tree, lines) in modules.items():
        class_of: dict[int, str] = {}
        for top in tree.body:
            if isinstance(top, ast.ClassDef):
                for inner in ast.walk(top):
                    class_of[id(inner)] = top.name
        rel = auditor.api.relpath(path, scope)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Expr):
                continue
            call = node.value.value if isinstance(node.value, ast.Await) else node.value
            if not isinstance(call, ast.Call):
                continue
            callee = auditor.api.resolve_call(call, module, class_of.get(id(node)), bindings_of[module], known, aliases, class_methods=True)
            if callee is None or callee not in multi:
                continue
            accept = auditor.api.accept_reason(lines, node.lineno, rule='discarded-tuple-return')
            related = [auditor.api.relpath(path_of[callee], scope)] if path_of[callee] != path else []
            auditor.api.emit(
                related=related,
                rule='discarded-tuple-return',
                variant=f'{callee} returns tuple[...]; the result is discarded',
                path=rel,
                line=node.lineno,
                evidence=lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else '',
                accepted=bool(accept),
                accepted_reason=accept,
            )
