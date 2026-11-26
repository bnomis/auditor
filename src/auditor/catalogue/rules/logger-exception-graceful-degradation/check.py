import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag an `except` handler that calls `logger.exception` and then returns a constant default.

    The rationale and the signal are in `rule.md`.
    """
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for lineno in auditor.api.graceful_degradation_sites(tree):
            accept = auditor.api.accept_reason(lines, lineno, rule='logger-exception-graceful-degradation')
            auditor.api.emit(
                rule='logger-exception-graceful-degradation',
                variant='except handler calls logger.exception then returns a constant default; use logger.warning or logger.debug instead',
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
