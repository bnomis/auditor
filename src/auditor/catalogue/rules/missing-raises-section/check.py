import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions whose body raises a project exception but whose
    docstring lacks any `Raises:` / `:raises:` section.

    Signal:
      - Function has a non-empty docstring.
      - Function body contains at least one `ast.Raise` whose exception
        class name ends in `Error` and that is NOT a bare `raise` inside
        an except block (pure re-raise) and NOT a re-raise of a caught
        variable (`raise exc_var`).
      - Docstring contains NO `Raises:` block, `:raises X:` role, or
        sentence beginning with `Raises `.

    Refinement (2026-11-01): a raise that a handler around it catches, by its
    own class or a base class in the package's class tree (a bare `except:`,
    `Exception` and `BaseException` catch all), without re-raising, does not
    reach the caller and does not count (`auditor.api.level_catches`). A def nested in
    the subject counts only where it is called by bare name, under that
    call's handlers (`auditor.api.nested_call_sites`); a nested def never called counts
    nothing, and stays a subject of its own. A handler that re-raises, one
    for an unrelated class, or no handler keeps the hit.
    """
    # Accept any of:
    #   - a `Raises:` / `Raise:` header line (napoleon / google style)
    #   - sphinx `:raises X:` role
    #   - a prose sentence `Raise <X>Error` or `Raises <X>Error` that may
    #     use a dotted-module-qualified form (`pkg.ensemble.errors.LoadError`)
    raises_marker_re = re.compile(
        r'(?:^\s*Raises?\s*:|:raises\s+[A-Za-z_]|\bRaises?\s+[A-Za-z_][\w.]*Error\b)',
        re.MULTILINE,
    )
    parsed: list[tuple[pathlib.Path, list[str], ast.Module]] = []
    for path in auditor.api.all_py_files(src_root):
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        parsed.append((path, lines, tree))
    parents = auditor.api.package_class_parents(tree for _, _, tree in parsed)
    for path, lines, tree in parsed:
        if path.name == '__init__.py' or path.name == 'errors.py':
            continue
        rel = auditor.api.relpath(path, scope)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = ast.get_docstring(node)
            if not doc:
                continue
            if raises_marker_re.search(doc):
                continue
            # Does body raise a project *Error class, not a re-raise or stdlib?
            found_project_raise = False
            for inner, levels in auditor.api.nested_call_sites(node):
                if not isinstance(inner, ast.Raise):
                    continue
                if inner.exc is None:
                    continue  # bare `raise` re-raise
                target = inner.exc.func if isinstance(inner.exc, ast.Call) else inner.exc
                if isinstance(target, ast.Name):
                    # a re-raise of a caught variable is `raise exc_var` - Name without Call
                    if not isinstance(inner.exc, ast.Call):
                        continue
                    name = target.id
                elif isinstance(target, ast.Attribute):
                    name = target.attr
                else:
                    continue
                if not name.endswith('Error'):
                    continue
                if name in auditor.api.STDLIB_ERRORS:
                    continue  # stdlib raises are covered by the layer-stdlib check
                lineage = auditor.api.class_lineage(name, parents)
                if any(auditor.api.level_catches(level, lineage) for level in levels):
                    continue
                found_project_raise = True
                break
            if not found_project_raise:
                continue
            accept = auditor.api.accept_reason(lines, node.lineno, rule='missing-raises-section')
            auditor.api.emit(
                rule='missing-raises-section',
                variant=f'{node.name} raises a project *Error but docstring lacks a Raises: section',
                path=rel,
                line=node.lineno,
                evidence=(lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
