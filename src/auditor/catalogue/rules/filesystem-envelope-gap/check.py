import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a `try` that calls a filesystem-touching helper, raises from a handler and catches no `OSError`.

    The rationale, the signal and the dated refinements are in `rule.md`.
    """
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for lineno, caught in auditor.api.filesystem_envelope_gap_sites(tree):
            accept = auditor.api.accept_reason(lines, lineno, rule='filesystem-envelope-gap')
            auditor.api.emit(
                rule='filesystem-envelope-gap',
                variant=f'try block touches filesystem (download/from_pretrained/etc.) but except tuple {caught!r} omits OSError',
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
