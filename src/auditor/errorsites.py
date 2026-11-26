"""Error-handling site helpers shared by the catalogue rules, the listers and the checks not yet moved.

The rules helper API publishes them in its errors submodule.
"""

import ast
import collections
import collections.abc
import re
import typing

import auditor.core

if typing.TYPE_CHECKING:
    import pathlib

BARE_HANDLER_MARK = '*bare*'


ERRORS_MODULE_NAMES = frozenset({'__init__.py', 'errors.py'})


# Handlers that catch every domain error, whatever its name.
BROAD_HANDLER_NAMES = frozenset({'BaseException', 'Exception'})


def is_broad_handler(handler: ast.ExceptHandler) -> bool:
    """True for a bare `except:` and for `Exception` or `BaseException`,
    alone or inside a tuple."""
    exc = handler.type
    if exc is None:
        return True
    if isinstance(exc, ast.Name):
        names = [exc.id]
    elif isinstance(exc, ast.Tuple):
        names = [e.id for e in exc.elts if isinstance(e, ast.Name)]
    else:
        return False
    return any(n in BROAD_HANDLER_NAMES for n in names)


# Callees that indicate the wrapped try-block touches local filesystem
# cache / does writing I/O. Catching only library-specific exceptions
# (MlflowException, BotoException, etc.) without also catching OSError
# leaks disk failures to callers.
THIRD_PARTY_FILESYSTEM_CALLS = frozenset(
    {
        # Third-party helpers that cache to disk / upload / download
        'download',
        'download_artifacts',
        'download_file',
        'from_pretrained',
        'log_artifact',
        'log_artifacts',
        'log_model',
        'push_to_hub',
        'save_model',
        'save_pretrained',
        'snapshot_download',
        'upload_artifacts',
        'upload_file',
    }
)


# `replace`, `rename`, `copy`, `remove` are intentionally omitted -
# `str.replace`, `dataclasses.replace`, `list.copy`, `dict.copy`,
# `list.remove` are overwhelmingly common; the false-positive rate
# on their bare names dominates.
STDLIB_FILESYSTEM_CALLS = frozenset(
    {
        # Pathlib / open / stdlib filesystem primitives used directly.
        'copytree',
        'makedirs',
        'mkdir',
        'read_bytes',
        'read_text',
        'rmdir',
        'rmtree',
        'symlink_to',
        'touch',
        'unlink',
        'write_bytes',
        'write_text',
    }
)


LIBRARY_READ_CALLS = frozenset(
    {
        # Common library read entry points that open the file under the hood
        'from_csv',
        'from_json',
        'read_csv',
        'read_excel',
        'read_feather',
        'read_hdf',
        'read_json',
        'read_parquet',
        'read_pickle',
        'read_sql',
        'read_sql_query',
        'read_sql_table',
        'read_table',
    }
)


FILESYSTEM_TOUCHING_CALLS = THIRD_PARTY_FILESYSTEM_CALLS | STDLIB_FILESYSTEM_CALLS | LIBRARY_READ_CALLS


def handler_catches(handler: ast.ExceptHandler) -> set[str]:
    """Every identifier named in this handler's except tuple.

    Dotted forms contribute both halves (`json.JSONDecodeError` gives `json`
    and `JSONDecodeError`), which is harmless: only the exception names are
    ever looked up. A bare `except:` gives the `*bare*` sentinel.
    """
    if handler.type is None:
        return {BARE_HANDLER_MARK}
    return set(re.findall(r'[A-Za-z_][A-Za-z_0-9]*', ast.unparse(handler.type)))


def handler_translates(handler: ast.ExceptHandler) -> bool:
    """True when this handler raises something whose name ends in `Error`.

    The same signal `check_asymmetric_exception_translation` uses. It is what
    separates an error-translating wrapper from a decorator that happens to
    contain a `try` for an unrelated reason, such as an optional-import probe.
    """
    for sub in ast.walk(handler):
        if not isinstance(sub, ast.Raise) or sub.exc is None:
            continue
        target = sub.exc.func if isinstance(sub.exc, ast.Call) else sub.exc
        if not isinstance(target, (ast.Name, ast.Attribute)):
            continue
        if ast.unparse(target).rsplit('.', 1)[-1].endswith('Error'):
            return True
    return False


def translator_envelopes(src_root: pathlib.Path) -> dict[str, frozenset[str]]:
    """Map every error-translating function's name to what its handlers catch.

    Indexed by short name rather than by dotted path, because the decorator is
    written as the name it was bound to at the use site and that binding is not
    always an import the checker can follow - one project's store reads the
    contextmanager back out of `sys.modules` to dodge a circular import, and a
    dotted-path index would resolve nothing there.

    Two definitions sharing a short name contribute a union, so a wide envelope
    elsewhere in the package can only ever silence a hit, never invent one.
    """
    envelopes: dict[str, set[str]] = collections.defaultdict(set)
    for path in auditor.core.all_py_files(src_root):
        tree = auditor.core.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            caught: set[str] = set()
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Try):
                    continue
                for handler in sub.handlers:
                    if handler_translates(handler):
                        caught |= handler_catches(handler)
            if caught:
                envelopes[node.name] |= caught
    return {name: frozenset(caught) for name, caught in envelopes.items()}


def callable_short_name(expr: ast.expr) -> str | None:
    """The bare name a decorator or `with` item invokes.

    `@translate('...')`, `@errors.translate` and `@translate` all give
    `translate`.
    """
    node = expr.func if isinstance(expr, ast.Call) else expr
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def package_class_parents(trees: collections.abc.Iterable[ast.Module]) -> dict[str, set[str]]:
    """Map each top-level class in the given modules to the names of its bases.

    A base written `mod.Base` is recorded as `Base`, so the table follows the
    package's own class tree by bare name. Modules are pooled: a class and its
    base may live in different ones. A class with no base maps to an empty set,
    so the keys are exactly the package's top-level class names."""
    parents: dict[str, set[str]] = collections.defaultdict(set)
    for tree in trees:
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                parents[node.name].update(ast.unparse(base).rsplit('.', 1)[-1] for base in node.bases if isinstance(base, (ast.Name, ast.Attribute)))
    return dict(parents)


def class_lineage(name: str, parents: collections.abc.Mapping[str, set[str]]) -> set[str]:
    """The name and every ancestor of it, transitively, in `parents`.

    A cycle terminates, and a name `parents` does not know is its own lineage."""
    seen = {name}
    stack = [name]
    while stack:
        for parent in parents.get(stack.pop(), ()):
            if parent not in seen:
                seen.add(parent)
                stack.append(parent)
    return seen


def raises_section_names(doc: str) -> set[str]:
    """Return the class name of every entry in a Google-style `Raises:` section.

    An entry is a line at the section's first indent, optionally bulleted,
    naming a `*Error`, or several comma-separated (`ParseError, FetchError:`);
    deeper lines continue the entry before them, and the first line back at
    the header's indent ends the section.
    """
    entry_re = re.compile(r'\s*(?:[-*]\s+)?([A-Za-z_][\w.]*Error(?:\s*,\s*[A-Za-z_][\w.]*Error)*)\b')
    lines = doc.splitlines()
    names: set[str] = set()
    for start, header in enumerate(lines):
        if header.strip() != 'Raises:':
            continue
        header_indent = len(header) - len(header.lstrip())
        entry_indent = None
        for line in lines[start + 1 :]:
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= header_indent:
                break
            if entry_indent is None:
                entry_indent = indent
            if indent != entry_indent:
                continue
            match = entry_re.match(line)
            if match:
                names.update(name.strip().rsplit('.', 1)[-1] for name in match.group(1).split(','))
    return names


def silent_broad_except_sites(tree: ast.AST) -> collections.abc.Iterator[ast.ExceptHandler]:
    """Each broad handler whose body neither logs nor raises."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or not is_broad_handler(node):
            continue
        body_src = '\n'.join(ast.unparse(c) for c in node.body)
        has_log = bool(re.search(r'\blogger\.|loguru\.logger\.|logging\.', body_src))
        has_raise = any(isinstance(c, ast.Raise) for c in ast.walk(node))
        if not (has_log or has_raise):
            yield node


def wrong_level_broad_except_sites(tree: ast.AST) -> collections.abc.Iterator[ast.ExceptHandler]:
    """Each broad handler whose body logs at warning, error, info or debug."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or not is_broad_handler(node):
            continue
        body_src = '\n'.join(ast.unparse(c) for c in node.body)
        if re.search(r'\b(logger|loguru\.logger|logging)\.(warning|error|info|debug)\(', body_src):
            yield node
