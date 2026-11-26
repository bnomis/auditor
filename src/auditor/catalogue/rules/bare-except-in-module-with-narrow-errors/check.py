import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag modules that inconsistently mix `except Exception` / `except
    BaseException` with narrow `except <X>_ERRORS:` tuples in separate
    sites. The mixed pattern signals an incomplete sweep toward narrow
    except tuples.

    Signal:
      - Module has at least one `except Exception` / `except BaseException`
        (bare or with bound name).
      - Module ALSO has at least one `except <NAME>_ERRORS:` or
        `except (*<NAME>_ERRORS, ...):` tuple-handler where NAME_ERRORS
        is referenced as an `ast.Name`.
      - Flag the bare-except sites, not the narrow ones.
    """
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        bare_handlers: list[ast.ExceptHandler] = []
        narrow_errors_tuple_seen = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            t = node.type
            if t is None:
                bare_handlers.append(node)
                continue
            names = []
            if isinstance(t, ast.Tuple):
                for elt in t.elts:
                    if isinstance(elt, ast.Name):
                        names.append(elt.id)
                    elif isinstance(elt, ast.Starred) and isinstance(elt.value, ast.Name):
                        names.append(elt.value.id)
            elif isinstance(t, ast.Name):
                names.append(t.id)
            if any(n.endswith('_ERRORS') or n.endswith('_EXCEPTIONS') for n in names):
                narrow_errors_tuple_seen = True
                continue
            if any(n in auditor.api.BROAD_HANDLER_NAMES for n in names):
                bare_handlers.append(node)
        if not (narrow_errors_tuple_seen and bare_handlers):
            continue
        for handler in bare_handlers:
            accept = auditor.api.accept_reason(lines, handler.lineno, rule='bare-except-in-module-with-narrow-errors')
            auditor.api.emit(
                rule='bare-except-in-module-with-narrow-errors',
                variant='bare except Exception in module that elsewhere uses *_ERRORS tuple',
                path=rel,
                line=handler.lineno,
                evidence=(lines[handler.lineno - 1].strip()[:200] if handler.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
