import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def stmt_end_by_lineno(tree: ast.AST) -> dict[int, int]:
    """Map each source line to the max end_lineno of any statement enclosing it."""
    mapping: dict[int, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            for ln in range(node.lineno, node.end_lineno + 1):
                if mapping.get(ln, 0) < node.end_lineno:
                    mapping[ln] = node.end_lineno
    return mapping


SAFE_ATTRS = ('__name__', '__qualname__')


def is_categorical_class_name_expr(expr_src: str, bound: str) -> bool:
    """Return True when expr_src is a categorical class-name access on the
    bound exception name (e.g. ``type(exc).__name__`` or
    ``exc.__class__.__qualname__``). These patterns expose only the
    exception class string, not the lossy ``str(exc)`` message body, and
    do not duplicate the chained traceback that ``raise ... from exc``
    or ``logger.exception`` already preserve.
    """
    bound_re = re.escape(bound)
    patterns = [rf'^type\(\s*{bound_re}\s*\)\.{attr}$' for attr in SAFE_ATTRS]
    patterns += [rf'^{bound_re}\.__class__\.{attr}$' for attr in SAFE_ATTRS]
    return any(re.match(p, expr_src.strip()) for p in patterns)


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag f-string or logger-positional interpolation of a caught
    exception variable inside an ``except ... as <bound>:`` block.
    Rationale: ``raise X from exc`` and ``logger.exception(...)`` already
    preserve the chained traceback at full fidelity; embedding
    ``str(exc)`` (or its f-string equivalent) into a new message
    produces a truncated copy that drifts from the original.

    Exception: ``type(<bound>).__name__`` / ``__qualname__``
    and ``<bound>.__class__.__name__`` / ``__qualname__`` access only
    the exception class name string. The class name is a categorical
    hint, not a lossy duplication of the message body, so these
    patterns are skipped without emitting a hit. See
    ``is_categorical_class_name_expr``.
    """
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        stmt_end = stmt_end_by_lineno(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler) or not node.name:
                continue
            bound = node.name
            seen_linenos: set[tuple[int, str]] = set()
            for inner in ast.walk(node):
                if isinstance(inner, ast.JoinedStr):
                    flagged = False
                    for v in inner.values:
                        if flagged:
                            break
                        if isinstance(v, ast.FormattedValue):
                            expr_src = ast.unparse(v.value) if hasattr(ast, 'unparse') else ''
                            if not re.search(rf'\b{re.escape(bound)}\b', expr_src):
                                continue
                            if is_categorical_class_name_expr(expr_src, bound):
                                continue
                            key = (inner.lineno, 'fstring')
                            if key in seen_linenos:
                                flagged = True
                                break
                            seen_linenos.add(key)
                            end_ln = stmt_end.get(inner.lineno)
                            accept = auditor.api.accept_reason(lines, inner.lineno, end_ln, rule='except-interpolation')
                            auditor.api.emit(
                                rule='except-interpolation',
                                variant='f-string interpolates caught exception',
                                path=rel,
                                line=inner.lineno,
                                evidence=(lines[inner.lineno - 1].strip()[:200] if inner.lineno <= len(lines) else ''),
                                accepted=bool(accept),
                                accepted_reason=accept,
                            )
                            flagged = True
                            break
                if isinstance(inner, ast.Call):
                    func_src = ast.unparse(inner.func) if hasattr(ast, 'unparse') else ''
                    if re.search(r'logger\.(warning|error|exception)$', func_src):
                        for arg in inner.args:
                            arg_src = ast.unparse(arg) if hasattr(ast, 'unparse') else ''
                            if re.fullmatch(rf'\s*{re.escape(bound)}\s*', arg_src):
                                key = (inner.lineno, 'logger-arg')
                                if key in seen_linenos:
                                    continue
                                seen_linenos.add(key)
                                end_ln = stmt_end.get(inner.lineno)
                                accept = auditor.api.accept_reason(lines, inner.lineno, end_ln, rule='except-interpolation')
                                auditor.api.emit(
                                    rule='except-interpolation',
                                    variant='logger positional arg is caught exception',
                                    path=rel,
                                    line=inner.lineno,
                                    evidence=(lines[inner.lineno - 1].strip()[:200] if inner.lineno <= len(lines) else ''),
                                    accepted=bool(accept),
                                    accepted_reason=accept,
                                )
