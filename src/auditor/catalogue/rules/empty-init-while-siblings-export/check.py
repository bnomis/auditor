import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a subpackage `__init__.py` that exports nothing while a sibling exports a non-trivial surface."""
    for path, sibling_max in auditor.api.empty_init_sites(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        # File-level finding: scan every line for an `# auditme: accept`
        # marker. The standard line-bracketed `accept_reason` only checks
        # the hit line and its predecessor, but a docstring-only
        # `__init__.py` cannot host an inline comment on the docstring
        # line itself - the marker has to land on a comment-only line
        # somewhere in the file.
        accept: str | None = None
        for ln in range(1, len(lines) + 1):
            accept = auditor.api.accept_reason(lines, ln, rule='empty-init-while-siblings-export')
            if accept:
                break
        auditor.api.emit(
            rule='empty-init-while-siblings-export',
            variant=f'{path.parent.name}/__init__.py exports 0 symbols; siblings export up to {sibling_max}',
            path=rel,
            line=1,
            evidence='no __all__ and no re-exports',
            accepted=bool(accept),
            accepted_reason=accept,
        )
