import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag modules that raise stdlib exceptions (FileNotFoundError, KeyError,
    RuntimeError, TypeError, ValueError) for domain errors when a sibling `errors.py` in
    the same package defines a domain-error class.

    Signal:
      - Package P contains an `errors.py` defining at least one `*Error`
        class.
      - Another module M in the same package P raises a stdlib exception
        (FileNotFoundError, KeyError, RuntimeError, TypeError, ValueError) at module-level
        or function scope.
      - The stdlib raise is NOT inside an `except` block (which is the
        re-raise-with-narrower-type pattern and is fine).

    Scope rationale: the "widen to any module that imports a
    domain `*Error` lazily" variant was tried and discarded because it
    over-fired on `config/structures.py.__post_init__` validation raises,
    which AGENTS.md's "Error type policy by layer" permits (`config` has
    no own `*Error` class and only lazily imports `PipelineError` for a
    narrow cross-stage violation). The narrower same-package predicate is
    the stable form.
    """
    STDLIB_EXCS = {'FileNotFoundError', 'KeyError', 'RuntimeError', 'TypeError', 'ValueError'}
    # First pass: find every package with a domain error class
    package_has_domain_error: set[tuple[str, ...]] = set()
    for path in auditor.api.all_py_files(src_root):
        if path.name != 'errors.py':
            continue
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.endswith('Error'):
                pkg = path.relative_to(src_root).parts[:-1]
                package_has_domain_error.add(pkg)
                break

    if not package_has_domain_error:
        return

    # Second pass: walk every module raising stdlib errors
    for path in auditor.api.all_py_files(src_root):
        if path.name in auditor.api.ERRORS_MODULE_NAMES:
            continue
        pkg = path.relative_to(src_root).parts[:-1]
        if pkg not in package_has_domain_error:
            continue
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        # Track which Raise nodes are inside an except block
        except_bodies: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                for child in ast.walk(node):
                    if hasattr(child, 'lineno'):
                        except_bodies.add(child.lineno)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise):
                continue
            if node.lineno in except_bodies:
                continue
            exc_call = node.exc
            exc_name = None
            if isinstance(exc_call, ast.Call):
                if isinstance(exc_call.func, ast.Name):
                    exc_name = exc_call.func.id
            elif isinstance(exc_call, ast.Name):
                exc_name = exc_call.id
            if exc_name not in STDLIB_EXCS:
                continue
            accept = auditor.api.accept_reason(lines, node.lineno, rule='layer-has-domain-error-raises-stdlib')
            auditor.api.emit(
                rule='layer-has-domain-error-raises-stdlib',
                variant=f'{pkg[-1] if pkg else "(root)"} package defines *Error classes but this module raises {exc_name}',
                path=rel,
                line=node.lineno,
                evidence=(lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
