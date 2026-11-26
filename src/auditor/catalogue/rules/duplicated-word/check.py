import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag the same word twice in a row in a comment or string."""
    dup_re = re.compile(r'\b([a-z]{2,})\s+\1\b', re.IGNORECASE)
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        for idx, raw in enumerate(lines, 1):
            m = dup_re.search(raw)
            if not m:
                continue
            word = m.group(1).lower()
            if word in {'that', 'had', 'has', 'as', 'in', 'is'}:
                continue
            s = raw.strip()
            if not (s.startswith('#') or '"""' in raw or "'''" in raw or '"' in raw or "'" in raw):
                continue
            accept = auditor.api.accept_reason(lines, idx, rule='duplicated-word')
            auditor.api.emit(
                rule='duplicated-word',
                variant=f'duplicated word {word!r}',
                path=rel,
                line=idx,
                evidence=s[:200],
                accepted=bool(accept),
                accepted_reason=accept,
            )
