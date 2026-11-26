import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def bare_parametric_annotation_in_file(rel: str, lines: list[str], tree: ast.Module | None) -> None:
    if tree is None:
        return
    reported: set[int] = set()

    def flag_annotation(ann: ast.AST, ctx: str) -> None:
        # Walk the annotation expression to find any `Name` matching
        # a bare generic. `Subscript(Name(id='dict'), ...)` is fine.
        # `Name(id='dict')` alone is a bare annotation. Handle
        # `dict | None`, `dict | Other`, etc. by descending into BinOp.
        def visit(node: ast.AST) -> None:
            if isinstance(node, ast.Subscript):
                tail = node.value.attr if isinstance(node.value, ast.Attribute) else getattr(node.value, 'id', '')
                if tail == 'Literal':
                    return
                if tail == 'Annotated':
                    if isinstance(node.slice, ast.Tuple) and node.slice.elts:
                        visit(node.slice.elts[0])
                    return
                visit(node.slice)
                return
            if isinstance(node, ast.Name) and node.id in auditor.api.BARE_GENERIC_NAMES:
                lineno = getattr(node, 'lineno', None)
                if lineno is None or lineno in reported:
                    return
                reported.add(lineno)
                accept = auditor.api.accept_reason(lines, lineno, rule='bare-parametric-annotation')
                auditor.api.emit(
                    rule='bare-parametric-annotation',
                    variant=f'{ctx} uses bare `{node.id}` without element type',
                    path=rel,
                    line=lineno,
                    evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
            elif isinstance(node, ast.BinOp):
                visit(node.left)
                visit(node.right)
            elif isinstance(node, ast.Tuple):
                for elt in node.elts:
                    visit(elt)

        visit(ann)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in (*node.args.args, *node.args.kwonlyargs, *node.args.posonlyargs):
                if arg.annotation is not None:
                    flag_annotation(arg.annotation, f'{node.name}({arg.arg}:)')
            if node.returns is not None:
                flag_annotation(node.returns, f'{node.name} -> ')
        elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
            tgt = node.target
            ctx = 'annotation'
            if isinstance(tgt, ast.Name):
                ctx = f'{tgt.id}:'
            flag_annotation(node.annotation, ctx)


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag an annotation that uses `dict`, `list`, `tuple`, `set` or `frozenset` without its type parameters."""
    for path in auditor.api.all_py_files(src_root):
        bare_parametric_annotation_in_file(auditor.api.relpath(path, scope), auditor.api.source_lines(path), auditor.api.read_and_parse(path))
