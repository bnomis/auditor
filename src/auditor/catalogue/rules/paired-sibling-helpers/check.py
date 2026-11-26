import ast
import collections
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag module-level functions in two or more files whose bodies are identical."""
    bodies: dict[str, list[tuple[str, int, str]]] = collections.defaultdict(list)
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body_src = '\n'.join(ast.unparse(b) for b in node.body if not isinstance(b, ast.Expr) or not isinstance(b.value, ast.Constant))
            if not body_src.strip() or len(body_src) < 40:
                continue
            bodies[body_src].append((rel, node.lineno, node.name))
    for hits in bodies.values():
        if len(hits) < 2:
            continue
        files = {h[0] for h in hits}
        if len(files) < 2:
            continue
        for rel, lineno, fname in hits:
            full = scope / rel
            full_lines = auditor.api.source_lines(full)
            accept = auditor.api.accept_reason(full_lines, lineno, rule='paired-sibling-helpers')
            peers = sorted(set(h[2] for h in hits) - {fname})
            auditor.api.emit(
                related=sorted(files),
                rule='paired-sibling-helpers',
                variant=f'{len(hits)} functions share a body across files',
                path=rel,
                line=lineno,
                evidence=f'def {fname}(...) - matches: {", ".join(peers) or "(peer)"}',
                accepted=bool(accept),
                accepted_reason=accept,
            )
