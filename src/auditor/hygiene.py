"""Project-hygiene helpers shared by the catalogue rules and the runner.

The rules helper API publishes them in its `project` and `docs` submodules.
"""

import os
import re
import typing

import auditor.core

if typing.TYPE_CHECKING:
    import pathlib


def ruff_executable(scope: pathlib.Path) -> tuple[str, str]:
    """Return (command, label) for the ruff the audit runs: `$AUDITME_RUFF` when
    set and not empty, else the project's `.venv/bin/ruff` when it is an
    executable file, else `ruff` from PATH. The label for the first is
    `AUDITME_RUFF`.

    The project's own ruff is the one its lockfile pins, so preferring it makes
    the answer the same in every shell and in CI, whatever else is on PATH.
    Resolved once per run and scope.
    """
    key = ('ruff-executable', scope)
    if key not in auditor.core.INDEX_CACHE:
        venv_ruff = scope / '.venv' / 'bin' / 'ruff'
        named = os.environ.get('AUDITME_RUFF')
        if named:
            auditor.core.INDEX_CACHE[key] = (named, 'AUDITME_RUFF')
        elif auditor.core.is_executable_file(venv_ruff):
            auditor.core.INDEX_CACHE[key] = (str(venv_ruff), '.venv/bin/ruff')
        else:
            auditor.core.INDEX_CACHE[key] = ('ruff', 'ruff on PATH')
    return typing.cast('tuple[str, str]', auditor.core.INDEX_CACHE[key])


DEF_LINE_RE = re.compile(r'^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(')
CLASS_LINE_RE = re.compile(r'^(\s*)class\s+[A-Za-z_]\w*\s*[(:]')
SPEC_SKIP_PARTS = frozenset({'.git', '.venv', '__pycache__', 'audit-reviews', 'node_modules', 'tasks'})


def spec_markdown_files(scope: pathlib.Path) -> list[pathlib.Path]:
    """Markdown under scope, minus records and hidden directories.

    A hidden directory is skipped as a whole, not just `.git`/`.venv`: a
    Claude Code worktree lives at `.claude/worktrees/<name>/`, a full second
    checkout, and reading its specs reported every drift hit twice - once
    against a path no commit in this tree can touch.
    """
    out = []
    for path in scope.rglob('*.md'):
        dirs = path.relative_to(scope).parts[:-1]
        if SPEC_SKIP_PARTS & set(dirs) or any(part.startswith('.') for part in dirs):
            continue
        out.append(path)
    return sorted(out)
