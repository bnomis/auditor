import ast
import collections
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import collections.abc
    import pathlib


IMPORT_ERROR_NAMES = frozenset({'ImportError', 'ModuleNotFoundError'})


def walk_function_scopes(tree: ast.AST) -> collections.abc.Iterable[ast.AST]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


STDLIB = {
    'abc',
    'argparse',
    'ast',
    'asyncio',
    'base64',
    'collections',
    'contextlib',
    'copy',
    'csv',
    'dataclasses',
    'datetime',
    'decimal',
    'enum',
    'errno',
    'functools',
    'gc',
    'glob',
    'gzip',
    'hashlib',
    'heapq',
    'importlib',
    'inspect',
    'io',
    'ipaddress',
    'itertools',
    'json',
    'locale',
    'logging',
    'math',
    'mimetypes',
    'operator',
    'os',
    'pathlib',
    'platform',
    'pprint',
    'queue',
    'random',
    're',
    'secrets',
    'shlex',
    'shutil',
    'signal',
    'socket',
    'sqlite3',
    'ssl',
    'stat',
    'string',
    'struct',
    'subprocess',
    'sys',
    'tempfile',
    'textwrap',
    'threading',
    'time',
    'timeit',
    'token',
    'tokenize',
    'traceback',
    'types',
    'typing',
    'unicodedata',
    'urllib',
    'uuid',
    'warnings',
    'weakref',
    'xml',
    'zipfile',
    'zoneinfo',
}


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag every import inside a function, labelled stdlib, first-party or third-party."""
    accepted_pairs = auditor.api.accepted_lazy_imports(scope)
    for path in auditor.api.all_py_files(src_root):
        if path.name == '__init__.py':
            continue
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        type_checking_linenos = auditor.api.type_checking_linenos(tree)
        importerror_linenos: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                handles = False
                for h in node.handlers:
                    if (
                        isinstance(h.type, ast.Name)
                        and h.type.id in IMPORT_ERROR_NAMES
                        or (isinstance(h.type, ast.Tuple) and any(isinstance(e, ast.Name) and e.id in IMPORT_ERROR_NAMES for e in h.type.elts))
                    ):
                        handles = True
                if handles:
                    for child in node.body:
                        for sub in ast.walk(child):
                            if hasattr(sub, 'lineno'):
                                importerror_linenos.add(sub.lineno)
        importer_module = rel.replace('/', '.').removesuffix('.py').removeprefix('src.')
        first_party = auditor.api.declared_root_modules() | {importer_module.split('.')[0]}
        for func in walk_function_scopes(tree):
            for inner in ast.walk(func):
                if not isinstance(inner, (ast.Import, ast.ImportFrom)):
                    continue
                if inner.lineno in type_checking_linenos:
                    continue
                if inner.lineno in importerror_linenos:
                    continue
                if isinstance(inner, ast.Import):
                    imported_names = [n.name for n in inner.names]
                else:
                    imported_names = [inner.module or '']
                accept = auditor.api.accept_reason(lines, inner.lineno, rule='in-function-import')
                for imported in imported_names:
                    pair_accepted = any(importer_module.startswith(a) and imported.startswith(b) for (a, b) in accepted_pairs)
                    if pair_accepted:
                        accept = accept or f'AGENTS.md accepted ({importer_module} -> {imported})'
                    top = imported.split('.')[0]
                    variant = 'stdlib' if top in STDLIB else ('first-party' if top in first_party else 'third-party')
                    auditor.api.emit(
                        rule='in-function-import',
                        variant=variant,
                        path=rel,
                        line=inner.lineno,
                        evidence=f'{"import" if isinstance(inner, ast.Import) else "from"} {imported}',
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )
