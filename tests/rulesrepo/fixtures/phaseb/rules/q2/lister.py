import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def list_candidates(scope: pathlib.Path) -> list[auditor.api.Candidate]:
    return [auditor.api.Candidate('Q2', 'b.py::g', 'b.py', 3, 4, {}, 'h2')]
