"""The Doc4 lister: every site the Doc4 question applies to."""

import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib

IMPLEMENTED_RE = re.compile(r'^\*\*Status:\*\*\s*implemented\s*$', re.MULTILINE)


# auditme: accept[literal-duplication] each question declares its own kinds; equal values are coincidence
def list_candidates(scope: pathlib.Path) -> list[auditor.api.Candidate]:
    """List the (section, target) pairs of every implemented spec under `agents/specs/`.

    A proposed spec describes code not yet written, so it is not listed.

    Raises:
        PhaseBError: a spec cannot be read.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    specs = [
        path
        for path in auditor.api.spec_markdown_files(scope)
        if path.relative_to(scope).as_posix().startswith('agents/specs/') and IMPLEMENTED_RE.search(auditor.api.read_text(path))
    ]
    return auditor.api.doc_candidates('Doc4', scope, specs)
