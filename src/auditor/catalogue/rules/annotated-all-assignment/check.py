import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


ALL_GUARD_RE = re.compile(r"""['"]__all__['"]|\.__all__\b""")


def project_has_all_guard(scope: pathlib.Path) -> bool:
    """`scan_has_all_guard`, worked out once per run."""
    return typing.cast('bool', auditor.api.cached_per_run('project_has_all_guard', scope, scan_has_all_guard))


def scan_has_all_guard(scope: pathlib.Path) -> bool:
    """True when some file in the project inspects other modules' `__all__`.

    The signal is `__all__` read as data - `getattr(mod, '__all__')`,
    `mod.__all__`, or an AST walk comparing a target's id to `'__all__'` -
    rather than declared. A project with no such guard has nothing to switch
    off, so the annotated form costs it nothing.
    """
    src = scope / 'src'
    if not src.is_dir():
        return False
    for path in sorted(src.rglob('*.py')):
        text = auditor.api.read_source(path)
        if text is None:
            continue
        if ALL_GUARD_RE.search(text):
            return True
    return False


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `__all__: list[str] = [...]` in a project that guards `__all__`."""
    if not project_has_all_guard(scope):
        return
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.AnnAssign):
                continue
            if not isinstance(node.target, ast.Name) or node.target.id != '__all__':
                continue
            accept = auditor.api.accept_reason(lines, node.lineno, rule='annotated-all-assignment')
            auditor.api.emit(
                rule='annotated-all-assignment',
                variant='__all__ is an AnnAssign; a guard matching ast.Assign skips this module',
                path=rel,
                line=node.lineno,
                evidence=lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else ast.unparse(node),
                accepted=bool(accept),
                accepted_reason=accept,
            )
