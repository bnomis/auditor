import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib

PHASE_REF_RE = re.compile(r'\bPhase\s+[1-9][a-z]?\b')

SECTION_REF_RE = re.compile(r'\bSection\s+[0-9]+\.[0-9]+\b')


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag src/ docstrings and comments that reference numbered
    `Phase N` or `Section X.Y` spec locations. These cross-references
    rot when specs are renumbered.

    Signal:
      - Line in a .py file in src/ matches `\\bPhase [1-9][a-z]?\\b` or
        `\\bSection [0-9]+\\.[0-9]+\\b`.
      - Line is part of a docstring (triple-quoted string) OR a comment
        (starts with `#` after optional whitespace).
      - The file does NOT carry a file-level `# auditme: accept <reason>`
        marker on any comment-only line (to allow modules that render
        user-facing Phase vocabulary to be excused wholesale).
      - Hit is not explicitly accepted via inline marker.
    """
    file_level_accept_re = re.compile(r'^\s*#\s*auditme:\s*accept\s+.*phase-section')
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        # File-level accept check: if any line is a comment-only
        # `# auditme: accept phase-section ...`, skip the file.
        if any(file_level_accept_re.search(raw) for raw in lines):
            continue
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        # Collect docstring line ranges
        docstring_ranges: list[tuple[int, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                doc = ast.get_docstring(node, clean=False)
                if doc and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                    const = node.body[0]
                    end = getattr(const, 'end_lineno', const.lineno)
                    docstring_ranges.append((const.lineno, end))

        for idx, raw in enumerate(lines, 1):
            matches = list(PHASE_REF_RE.finditer(raw)) + list(SECTION_REF_RE.finditer(raw))
            if not matches:
                continue
            stripped = raw.strip()
            is_comment = stripped.startswith('#')
            if not (is_comment or any(a <= idx <= b for a, b in docstring_ranges)):
                continue
            accept = auditor.api.accept_reason(lines, idx, rule='phase-section-doc-reference')
            auditor.api.emit(
                rule='phase-section-doc-reference',
                variant=f'numeric spec cross-reference {matches[0].group(0)!r}',
                path=rel,
                line=idx,
                evidence=stripped[:200],
                accepted=bool(accept),
                accepted_reason=accept,
            )
