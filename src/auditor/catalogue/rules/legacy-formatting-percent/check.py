import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


STRFTIME_TOKENS = {'%A', '%B', '%H', '%I', '%M', '%S', '%U', '%W', '%X', '%Y', '%Z', '%a', '%b', '%c', '%d', '%f', '%j', '%m', '%p', '%x', '%y', '%z'}


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `%s`/`%d`/`%r`-style formatting in a string literal, leaving strftime directives alone."""
    suspect_re = re.compile(r'%[sdrfg]|%\d+[sdrfg]')
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        for idx, raw in enumerate(lines, 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith('#'):
                continue
            # extract string literals
            strings = re.findall(r"""(?:[fF]?r?)?['"](?:[^'"\\]|\\.)*['"]""", raw)
            for s in strings:
                if not suspect_re.search(s):
                    continue
                if any(tok in s for tok in STRFTIME_TOKENS):
                    continue
                accept = auditor.api.accept_reason(lines, idx, rule='legacy-formatting-percent')
                auditor.api.emit(
                    rule='legacy-formatting-percent',
                    variant='%-style C-printf formatting in Python string',
                    path=rel,
                    line=idx,
                    evidence=stripped[:200],
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
                break
