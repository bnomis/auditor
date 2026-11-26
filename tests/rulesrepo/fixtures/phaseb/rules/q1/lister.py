import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def list_candidates(scope: pathlib.Path, depth: int) -> list[auditor.api.Candidate]:
    return [auditor.api.Candidate('Q1', f'a.py::f{depth}', 'a.py', 1, 2, {'depth': depth}, 'h1')]
