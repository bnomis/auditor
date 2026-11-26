import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a body whose only error envelope is a translating decorator or contextmanager that omits an error its call raises.

    The rationale, the signal and the carve-outs are in `rule.md`.
    """
    envelopes = auditor.api.translator_envelopes(src_root)
    if not envelopes:
        return
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for function, lineno, callee, missing, sources, caught in auditor.api.translator_gap_sites(tree, envelopes):
            accept = auditor.api.accept_reason(lines, lineno, rule='translator-envelope-gap')
            auditor.api.emit(
                rule='translator-envelope-gap',
                variant=(
                    f'{function} calls `{callee}` under {", ".join(sources)}, whose except tuple {sorted(caught - {auditor.api.BARE_HANDLER_MARK})!r} omits {missing!r}'
                ),
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if lineno <= len(lines) else callee),
                accepted=bool(accept),
                accepted_reason=accept,
            )
