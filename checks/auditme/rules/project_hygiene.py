"""Checks on project-level artefacts rather than source."""

from __future__ import annotations
import ast
import json
import pathlib
import re
import subprocess

from auditme.core import _accept_reason, _all_py_files, _emit, _relpath, _source_lines


def check_ruff(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    for cmd, variant in (
        (['ruff', 'check', '--output-format=json', str(src_root)], 'ruff-check'),
        (['ruff', 'format', '--check', str(src_root)], 'ruff-format'),
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=scope)
        except FileNotFoundError:
            _emit(
                rule='ruff',
                variant=variant,
                path=None,
                line=None,
                evidence='ruff not installed',
                accepted=False,
                accepted_reason=None,
            )
            continue
        if variant == 'ruff-check' and result.stdout.strip():
            try:
                for hit in json.loads(result.stdout):
                    _emit(
                        rule='ruff',
                        variant=hit.get('code', 'ruff-check'),
                        path=_relpath(pathlib.Path(hit['filename']), scope),
                        line=hit['location']['row'],
                        evidence=hit.get('message', ''),
                        accepted=False,
                        accepted_reason=None,
                    )
            except json.JSONDecodeError:
                _emit(rule='ruff', variant='ruff-check-parse-error', path=None, line=None, evidence=result.stdout[:200], accepted=False, accepted_reason=None)
        elif variant == 'ruff-format' and result.returncode != 0:
            for ln in result.stdout.splitlines() + result.stderr.splitlines():
                if 'Would reformat' in ln or ln.endswith('.py'):
                    _emit(
                        rule='ruff', variant='ruff-format', path=ln.split(':')[0].strip(), line=None, evidence=ln.strip(), accepted=False, accepted_reason=None
                    )

# `uv lock --check` exits non-zero both when the lockfile is genuinely stale
# and when it could not resolve at all. Only the first message is the drift.
_LOCKFILE_DRIFT_MARKER = 'needs to be updated'
_LOCKFILE_TIMESTAMP_RE = re.compile(r'\d{4}-\d{2}-\d{2}T[\d:.]+Z?')


def check_lockfile(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    pyproject = scope / 'pyproject.toml'
    uvlock = scope / 'uv.lock'
    if not pyproject.exists() or not uvlock.exists():
        return
    try:
        result = subprocess.run(['uv', 'lock', '--check'], capture_output=True, text=True, cwd=scope)
    except FileNotFoundError:
        return
    if result.returncode == 0:
        return

    output = (result.stderr or result.stdout).strip()
    # uv's progress chatter carries a resolution timestamp, and a network
    # failure carries whatever the transport said. Both change between runs, so
    # emitting the raw output made this check report a different evidence
    # string every time on an unchanged tree - see the convergence rules in
    # SKILL.md. Keep only the error lines, with any timestamp masked.
    error_lines = [line.strip() for line in output.splitlines() if line.strip().startswith('error:')]
    evidence = _LOCKFILE_TIMESTAMP_RE.sub('<timestamp>', ' '.join(error_lines))[:200]

    # A lockfile that needs regenerating and a lockfile that could not be
    # checked are different facts: the first is drift, the second means the
    # question went unanswered. Reporting both as drift is the
    # failure-versus-absence defect, in the checker rather than in the code
    # under audit.
    if _LOCKFILE_DRIFT_MARKER in output:
        variant = 'uv lock --check reports the lockfile is out of date'
        evidence = evidence or 'lockfile needs updating'
    else:
        variant = 'uv lock --check could not verify the lockfile'
        evidence = evidence or 'no error detail on stderr or stdout'

    _emit(
        rule='lockfile-drift',
        variant=variant,
        path='uv.lock',
        line=None,
        evidence=evidence,
        accepted=False,
        accepted_reason=None,
    )

_PHASE_REF_RE = re.compile(r'\bPhase\s+[1-9][a-z]?\b')

_SECTION_REF_RE = re.compile(r'\bSection\s+[0-9]+\.[0-9]+\b')

def check_phase_section_doc_reference(scope: pathlib.Path, src_root: pathlib.Path) -> None:
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
    file_level_accept_re = re.compile(
        r'^\s*#\s*auditme:\s*accept\s+.*phase-section'
    )
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        # File-level accept check: if any line is a comment-only
        # `# auditme: accept phase-section ...`, skip the file.
        if any(file_level_accept_re.search(raw) for raw in lines):
            continue
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
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
        def in_docstring(ln: int) -> bool:
            return any(a <= ln <= b for a, b in docstring_ranges)

        for idx, raw in enumerate(lines, 1):
            matches = list(_PHASE_REF_RE.finditer(raw)) + list(_SECTION_REF_RE.finditer(raw))
            if not matches:
                continue
            stripped = raw.strip()
            is_comment = stripped.startswith('#')
            if not (is_comment or in_docstring(idx)):
                continue
            accept = _accept_reason(lines, idx, rule='phase-section-doc-reference')
            _emit(
                rule='phase-section-doc-reference',
                variant=f'numeric spec cross-reference {matches[0].group(0)!r}',
                path=rel,
                line=idx,
                evidence=stripped[:200],
                accepted=bool(accept),
                accepted_reason=accept,
            )
