import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def is_leading_underscore(name: str | None) -> bool:
    """True for `_foo`; false for bare `_`, a dunder or a mangled `__foo`."""
    return bool(name) and name.startswith('_') and name != '_' and not name.startswith('__')


def leading_underscore_bindings(tree: ast.Module) -> list[tuple[str, int, str]]:
    """Return `(name, lineno, kind)` for every leading-underscore name a file binds.

    A binding is any name the author chose for a value: a parameter, a
    `Name` in store context (an assignment, unpack or loop target at any
    position, starred or not, a `with ... as`, a comprehension target, a
    walrus), an `except ... as` name, or a `match` capture.

    A plain-name target of a module-level assignment is left out, because the
    `leading-underscore-const-*` regexes own it and reporting it twice would
    double its count. A `def`/`class` name is left out for the same reason:
    `leading-underscore-def-class` owns it.
    """
    regex_owned: set[int] = set()
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            regex_owned.update(id(target) for target in targets if isinstance(target, ast.Name))

    found: list[tuple[str, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            prefix = 'lambda ' if isinstance(node, ast.Lambda) else ''
            arguments = node.args
            for arg in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs):
                found.append((arg.arg, arg.lineno, f'{prefix}parameter'))
            if arguments.vararg:
                found.append((arguments.vararg.arg, arguments.vararg.lineno, f'{prefix}`*` parameter'))
            if arguments.kwarg:
                found.append((arguments.kwarg.arg, arguments.kwarg.lineno, f'{prefix}`**` parameter'))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and id(node) not in regex_owned:
            found.append((node.id, node.lineno, 'binding'))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            found.append((node.name, node.lineno, '`except ... as` name'))
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            found.append((node.name, node.lineno, '`match` capture'))
        elif isinstance(node, ast.MatchMapping) and node.rest:
            found.append((node.rest, node.lineno, '`match` capture'))
    return [(name, lineno, kind) for name, lineno, kind in found if is_leading_underscore(name)]


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a leading-underscore parameter or bound name, wherever it occurs."""
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for name, lineno, kind in sorted(leading_underscore_bindings(tree), key=lambda item: (item[1], item[0])):
            accept = auditor.api.accept_reason(lines, lineno, rule='leading-underscore-binding')
            auditor.api.emit(
                rule='leading-underscore-binding',
                variant=f'{kind} `{name}`',
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
