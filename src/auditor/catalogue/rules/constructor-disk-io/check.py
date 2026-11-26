import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


DISK_IO_NAMES = {
    'copy',
    'copytree',
    'exists',
    'glob',
    'is_dir',
    'is_file',
    'iterdir',
    'makedirs',
    'mkdir',
    'mkdtemp',
    'mkstemp',
    'move',
    'open',
    'read_bytes',
    'read_text',
    'remove',
    'rename',
    'replace',
    'rglob',
    'rmdir',
    'rmtree',
    'stat',
    'symlink_to',
    'touch',
    'unlink',
    'write_bytes',
    'write_text',
}


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag disk I/O operations inside `__init__` methods. Constructors
    should accept already-loaded data, not perform I/O on demand."""
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            for member in cls.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if member.name != '__init__':
                    continue
                for inner in ast.walk(member):
                    if not isinstance(inner, ast.Call):
                        continue
                    fname = None
                    if isinstance(inner.func, ast.Name):
                        fname = inner.func.id
                    elif isinstance(inner.func, ast.Attribute):
                        fname = inner.func.attr
                    if fname not in DISK_IO_NAMES:
                        continue
                    accept = auditor.api.accept_reason(lines, inner.lineno, rule='constructor-disk-io')
                    auditor.api.emit(
                        rule='constructor-disk-io',
                        variant=f'{cls.name}.__init__ calls disk-IO `{fname}`',
                        path=rel,
                        line=inner.lineno,
                        evidence=lines[inner.lineno - 1].strip()[:200] if inner.lineno <= len(lines) else '',
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )
