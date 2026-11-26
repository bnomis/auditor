"""The Doc1 lister: every site the Doc1 question applies to."""

import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def tracked_directories(index: auditor.api.CorpusIndex) -> list[str]:
    """The tracked directories down to the tree depth, sorted."""
    return sorted(name for name in index.directories if name.count('/') < auditor.api.TREE_DEPTH)


# auditme: accept[literal-duplication] each question declares its own kinds; equal values are coincidence
def list_candidates(scope: pathlib.Path) -> list[auditor.api.Candidate]:
    """List each `AGENTS.md` section that names a path or holds a fence, with the tracked directory tree.

    Raises:
        PhaseBError: `AGENTS.md` cannot be read, or `git ls-files` fails.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    document = auditor.api.agents_document(scope)
    if document is None:
        return []
    path, lines = document
    index = auditor.api.CorpusIndex.build(scope)
    tree = tracked_directories(index)
    tree_bytes = '\n'.join(tree).encode('utf-8', errors='surrogateescape')
    found: list[auditor.api.Candidate] = []
    for section in auditor.api.read_sections(path, scope):
        text = lines[section.start - 1 : section.end]
        named = [(number, token) for number, token in section.names if auditor.api.is_path_shaped(token)]
        if not named and not any(auditor.api.FENCE_RE.match(line) for line in text):
            continue
        paths = [
            {'path': token, 'line': number, 'resolved': [target.id for target in auditor.api.read_path_targets(token, path, index)]} for number, token in named
        ]
        found.append(
            auditor.api.section_candidate(
                'Doc1',
                f'{section.doc}::{section.heading_path}',
                section,
                {'paths': paths, 'tree': tree},
                auditor.api.digest(['\n'.join(text).encode('utf-8'), tree_bytes]),
            )
        )
    return found
