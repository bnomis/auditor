import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a consumer that imports a symbol via a re-export shim instead of its canonical home."""
    for path, lineno, variant, evidence in auditor.api.migration_shim_sites(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        accept = auditor.api.accept_reason(lines, lineno, rule='migration-shim-consumer')
        auditor.api.emit(
            rule='migration-shim-consumer',
            variant=variant,
            path=rel,
            line=lineno,
            evidence=evidence,
            accepted=bool(accept),
            accepted_reason=accept,
        )
