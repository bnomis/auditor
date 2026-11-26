import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a top-level `def` or `class` line in an `__init__.py`."""
    for path in auditor.api.all_py_files(src_root):
        if path.name != '__init__.py':
            continue
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        for idx, raw in enumerate(lines, 1):
            if re.match(r'^(def |class )', raw):
                accept = auditor.api.accept_reason(lines, idx, rule='def-class-in-init')
                auditor.api.emit(
                    rule='def-class-in-init',
                    variant='top-level def or class in __init__.py',
                    path=rel,
                    line=idx,
                    evidence=raw.strip()[:200],
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
