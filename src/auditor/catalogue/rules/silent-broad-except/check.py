import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a broad `except` handler that neither logs nor raises.

    Signal: a handler for a bare `except:`, `Exception` or `BaseException`
    (alone or in a tuple) whose body holds no `logger.`, `loguru.logger.` or
    `logging.` text and no `raise` statement anywhere inside it. Carve-outs:
    a handler naming only narrower exceptions; a file that does not parse.
    """
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in auditor.api.silent_broad_except_sites(tree):
            accept = auditor.api.accept_reason(lines, node.lineno, rule='silent-broad-except')
            auditor.api.emit(
                rule='silent-broad-except',
                variant='no logger and no raise in body',
                path=rel,
                line=node.lineno,
                evidence=lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else '',
                accepted=bool(accept),
                accepted_reason=accept,
            )
