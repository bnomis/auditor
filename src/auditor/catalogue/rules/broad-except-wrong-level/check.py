import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `except (Exception|BaseException):` blocks whose body calls
    logger.warning / logger.error / logger.debug / logger.info instead of
    logger.exception. Distinct from `silent-broad-except`, which only
    catches blocks with NO logger call at all.

    A broad handler that logs and returns a default is caught here at
    `warning` and by `logger-exception-graceful-degradation` at `exception`.
    SKILL.md's "Conflicts with no winner" rules on it: remove or narrow the
    handler rather than change its level."""
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in auditor.api.wrong_level_broad_except_sites(tree):
            accept = auditor.api.accept_reason(lines, node.lineno, rule='broad-except-wrong-level')
            auditor.api.emit(
                rule='broad-except-wrong-level',
                variant='broad except logs at warning/error/info/debug instead of exception',
                path=rel,
                line=node.lineno,
                evidence=lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else '',
                accepted=bool(accept),
                accepted_reason=accept,
            )
