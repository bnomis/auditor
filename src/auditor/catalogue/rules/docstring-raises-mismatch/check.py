import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions whose docstring declares `Raises: <X>` (or a
    sphinx-style `:raises X:` or a plain 'Raises X' sentence) where the
    body actually raises a different exception class.

    Signal:
      - Function has a docstring.
      - Docstring mentions at least one exception class name (via
        `Raises:` section, `:raises X:` role, or 'Raises FooError' prose).
      - Function body contains `raise <Y>(...)` statements, all of which
        raise a class NOT listed in the docstring, and no `raise` re-raises
        a caught variable.
    """
    # Match exception class names from docstrings in a few common shapes
    docstring_class_re = re.compile(
        r'(?:Raises[\s:]+|:raises\s+|^\s*Raises?\s+)'
        r'([A-Za-z_][\w.]*Error)',
        re.MULTILINE,
    )
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = ast.get_docstring(node)
            if not doc:
                continue
            declared = {m.rsplit('.', 1)[-1] for m in docstring_class_re.findall(doc)} | auditor.api.raises_section_names(doc)
            if not declared:
                continue
            # Collect actual raised classes (excluding re-raises of bound vars)
            actual: set[str] = set()
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Raise) or inner.exc is None:
                    continue
                target = inner.exc.func if isinstance(inner.exc, ast.Call) else inner.exc
                if isinstance(target, (ast.Name, ast.Attribute)):
                    src = ast.unparse(target)
                    tail = src.rsplit('.', 1)[-1]
                    if tail.endswith('Error'):
                        actual.add(tail)
            if not actual:
                continue
            if actual & declared:
                continue  # intersection non-empty => at least one documented match
            # Every actual raise is not in declared list => mismatch
            accept = auditor.api.accept_reason(lines, node.lineno, rule='docstring-raises-mismatch')
            auditor.api.emit(
                rule='docstring-raises-mismatch',
                variant=f'{node.name} docstring declares `Raises: {sorted(declared)}` but body raises {sorted(actual)}',
                path=rel,
                line=node.lineno,
                evidence=f'docstring: {sorted(declared)} | body: {sorted(actual)}',
                accepted=bool(accept),
                accepted_reason=accept,
            )
