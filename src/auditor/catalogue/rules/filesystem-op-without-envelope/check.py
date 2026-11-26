import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a public entry point that makes a filesystem call outside any `try`, in a package with a domain error.

    The rationale, the signal and the dated refinements are in `rule.md`.
    """
    for path, function, short, lineno in auditor.api.filesystem_op_sites(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        accept = auditor.api.accept_reason(lines, lineno, rule='filesystem-op-without-envelope')
        auditor.api.emit(
            rule='filesystem-op-without-envelope',
            variant=f'{function} calls `{short}` with no surrounding try/except in the function body',
            path=rel,
            line=lineno,
            evidence=(lines[lineno - 1].strip()[:200] if lineno <= len(lines) else ''),
            accepted=bool(accept),
            accepted_reason=accept,
        )
