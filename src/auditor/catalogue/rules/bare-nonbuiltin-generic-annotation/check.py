import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


PARAMETRIC_NONBUILTIN_GENERICS = {
    'asyncio.Queue',
    'collections.Counter',
    'collections.OrderedDict',
    'collections.defaultdict',
    'collections.deque',
    'concurrent.futures.Executor',
    'concurrent.futures.Future',
    'multiprocessing.Queue',
    'multiprocessing.queues.Queue',
    'queue.Queue',
    'weakref.WeakKeyDictionary',
    'weakref.WeakValueDictionary',
}


def bare_nonbuiltin_generic_annotation_in_file(rel: str, lines: list[str], tree: ast.Module | None) -> None:
    if tree is None:
        return
    # Build import alias map so `Queue` resolves to `multiprocessing.Queue`
    # when imported as `from multiprocessing import Queue`.
    alias_to_full: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                alias_to_full[alias.asname or alias.name] = f'{node.module}.{alias.name}'
        elif isinstance(node, ast.Import):
            for alias in node.names:
                alias_to_full[alias.asname or alias.name.split('.')[0]] = alias.name

    reported: set[int] = set()

    def flag_bare_annotation(ann: ast.AST) -> None:
        if isinstance(ann, ast.Subscript):
            return  # parametric
        full = None
        if isinstance(ann, ast.Attribute):
            full = ast.unparse(ann)
        elif isinstance(ann, ast.Name):
            full = alias_to_full.get(ann.id, ann.id)
        if full is None:
            return
        if full not in PARAMETRIC_NONBUILTIN_GENERICS:
            return
        lineno = getattr(ann, 'lineno', None)
        if lineno is None or lineno in reported:
            return
        reported.add(lineno)
        accept = auditor.api.accept_reason(lines, lineno, rule='bare-nonbuiltin-generic-annotation')
        auditor.api.emit(
            rule='bare-nonbuiltin-generic-annotation',
            variant=f'bare `{full}` annotation without type parameter',
            path=rel,
            line=lineno,
            evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
            accepted=bool(accept),
            accepted_reason=accept,
        )

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in (*node.args.args, *node.args.kwonlyargs, *node.args.posonlyargs):
                if arg.annotation is not None:
                    flag_bare_annotation(arg.annotation)
            if node.returns is not None:
                flag_bare_annotation(node.returns)
        elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
            flag_bare_annotation(node.annotation)


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag an annotation that names a parameterisable non-builtin class without its type parameter."""
    for path in auditor.api.all_py_files(src_root):
        bare_nonbuiltin_generic_annotation_in_file(auditor.api.relpath(path, scope), auditor.api.source_lines(path), auditor.api.read_and_parse(path))
