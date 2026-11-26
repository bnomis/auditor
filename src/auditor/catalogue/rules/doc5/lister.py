"""The Doc5 lister: every site the Doc5 question applies to."""

import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


# auditme: accept[literal-duplication] each question declares its own kinds; equal values are coincidence
def list_candidates(scope: pathlib.Path) -> list[auditor.api.Candidate]:
    """List the (section, target) pairs of every `docs/**/*.md` and the root `README.md`.

    Raises:
        PhaseBError: a document cannot be read.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    documents = [
        path for path in auditor.api.spec_markdown_files(scope) if (rel := path.relative_to(scope).as_posix()).startswith('docs/') or rel == 'README.md'
    ]
    return auditor.api.doc_candidates('Doc5', scope, documents)
