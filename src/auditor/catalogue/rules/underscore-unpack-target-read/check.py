import ast
import collections
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def collect_name_loads(scope: ast.AST) -> dict[str, list[int]]:
    """Return a map of Name.id -> [lineno, ...] for every Load within
    `scope` (not descending into nested function or class definitions)."""
    result: dict[str, list[int]] = collections.defaultdict(list)

    def walk(n: ast.AST) -> None:
        for sub in ast.iter_child_nodes(n):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                result[sub.id].append(sub.lineno)
            walk(sub)

    walk(scope)
    return result


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a tuple-unpack target with a leading underscore whose name is read later in its scope."""
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        # Enclosing scopes: module-level plus each function
        scopes: list[ast.AST] = [tree]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.append(node)
        for scope_node in scopes:
            loads = collect_name_loads(scope_node)
            for node in ast.iter_child_nodes(scope_node) if scope_node is tree else ast.walk(scope_node):
                if scope_node is not tree and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)) and node is not scope_node:
                    continue
                targets: list[ast.AST] = []
                if isinstance(node, ast.Assign):
                    targets = list(node.targets)
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                else:
                    continue
                for target in targets:
                    if not isinstance(target, (ast.Tuple, ast.List)):
                        continue
                    for name, lineno in auditor.api.leading_underscore_names(target):
                        reads_after = [ln for ln in loads.get(name, []) if ln > lineno]
                        if not reads_after:
                            continue
                        accept = auditor.api.accept_reason(lines, lineno, rule='underscore-unpack-target-read')
                        auditor.api.emit(
                            rule='underscore-unpack-target-read',
                            variant=f'`{name}` unpacked but read at line {reads_after[0]}',
                            path=rel,
                            line=lineno,
                            evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
                            accepted=bool(accept),
                            accepted_reason=accept,
                        )
