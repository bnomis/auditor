"""Checks on naming, ordering and annotation style that have not yet moved to the catalogue."""

import ast
import typing

import auditor.core

if typing.TYPE_CHECKING:
    import pathlib


def function_nested_definitions(tree: ast.Module) -> list[tuple[ast.AST, str]]:
    """Return every def/class lexically inside a function body, with its kind.

    Descends through nested functions to any depth, so a helper defined
    inside a helper is found. A method (a def whose nearest enclosing
    definition is a class) is NOT returned: that is a different naming
    question, answered by `leading-underscore-self` and by whether the
    project treats a private method as public surface.
    """
    found: list[tuple[ast.AST, str]] = []

    def walk(node: ast.AST, inside_function: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if inside_function:
                    found.append((child, 'def'))
                walk(child, True)
            elif isinstance(child, ast.ClassDef):
                if inside_function:
                    found.append((child, 'class'))
                # A def inside this class is a method, not a nested helper,
                # so the class body is walked with inside_function reset.
                walk(child, False)
            else:
                walk(child, inside_function)

    walk(tree, False)
    return found


def check_leading_underscore_nested_def_class(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a leading-underscore `def`/`class` defined inside a function body.

    Emits under the same rule name as the module-level regex form
    (`leading-underscore-def-class` in check_text_patterns), because it is
    the same defect and a project's existing scoped accept markers should
    answer for both. The regex anchors on `^(def|class) _`, so it sees
    module-level definitions only; this check supplies the nested ones.

    Signal:
      - `ast.FunctionDef` / `ast.AsyncFunctionDef` / `ast.ClassDef` whose
        name starts with a single underscore, lexically inside a function
        body at any depth.

    Refinements (each has a test asserting it does not fire):
      - A **method** does not fire. `walk()` resets `inside_function` when
        it descends into a class body, so `def _m(self)` inside a class
        inside a function is a method, not a nested helper.
      - A **dunder** (`__init__`, `__enter__`) does not fire.
      - A name that **shadows an outer binding** does not fire: a nested
        `_foo` where `_foo` is also defined at module scope is a
        deliberate local override, and renaming it would break the
        shadowing the author wanted.
      - Bare `_` does not fire.

    Raised as a request by an audit (shipped 2026-09-01) that found
    instances which had been invisible across many audit cycles while the
    rule reported almost none.
    """
    for path in auditor.core.all_py_files(src_root):
        rel = auditor.core.relpath(path, scope)
        lines = auditor.core.source_lines(path)
        tree = auditor.core.read_and_parse(path)
        if tree is None:
            continue
        if not isinstance(tree, ast.Module):
            continue

        module_level_names = {node.name for node in ast.iter_child_nodes(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        module_level_names.add(target.id)

        for node, kind in function_nested_definitions(tree):
            name = getattr(node, 'name', '')
            if not name.startswith('_'):
                continue
            if name == '_' or name.startswith('__'):
                continue
            if name in module_level_names:
                continue
            lineno = node.lineno
            accept = auditor.core.accept_reason(lines, lineno, rule='leading-underscore-def-class')
            auditor.core.emit(
                rule='leading-underscore-def-class',
                variant=f'{kind} {name} nested inside a function body',
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


__all__ = [
    'check_leading_underscore_nested_def_class',
]
