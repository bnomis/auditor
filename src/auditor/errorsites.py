"""Error-handling site helpers shared by the catalogue rules and the listers.

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


def module_tuple_constants(tree: ast.Module) -> dict[str, list[ast.expr]]:
    """Map each name assigned exactly once at module level, to a tuple
    literal, to that tuple's members. A name assigned more than once is left
    out: which value a handler sees depends on order, so it is not resolved."""
    counts: collections.Counter[str] = collections.Counter()
    tuples: dict[str, list[ast.expr]] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            targets, value = stmt.targets, stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            targets, value = [stmt.target], stmt.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                counts[target.id] += 1
                if isinstance(value, ast.Tuple):
                    tuples[target.id] = list(value.elts)
    return {name: members for name, members in tuples.items() if counts[name] == 1}


# Builtin exception classes: not a project's domain errors.
STDLIB_ERRORS = frozenset(
    {
        'ArithmeticError',
        'AssertionError',
        'AttributeError',
        'BaseException',
        'BlockingIOError',
        'BrokenPipeError',
        'BufferError',
        'ChildProcessError',
        'ConnectionAbortedError',
        'ConnectionError',
        'ConnectionRefusedError',
        'ConnectionResetError',
        'EOFError',
        'Exception',
        'FileExistsError',
        'FileNotFoundError',
        'FloatingPointError',
        'GeneratorExit',
        'ImportError',
        'IndentationError',
        'IndexError',
        'InterruptedError',
        'IsADirectoryError',
        'KeyError',
        'KeyboardInterrupt',
        'LookupError',
        'MemoryError',
        'ModuleNotFoundError',
        'NameError',
        'NotADirectoryError',
        'NotImplementedError',
        'OSError',
        'OverflowError',
        'PermissionError',
        'ProcessLookupError',
        'RecursionError',
        'ReferenceError',
        'RuntimeError',
        'StopAsyncIteration',
        'StopIteration',
        'SyntaxError',
        'SystemError',
        'SystemExit',
        'TabError',
        'TimeoutError',
        'TypeError',
        'UnboundLocalError',
        'UnicodeDecodeError',
        'UnicodeEncodeError',
        'ValueError',
        'ZeroDivisionError',
    }
)


def handler_passes_on(handler: ast.ExceptHandler) -> bool:
    """Whether an `except` clause re-raises (a bare `raise`, or `raise <bound name>`).

    Only the clause's own scope counts: a raise inside a def, lambda or class
    defined in the handler belongs to that scope.
    """
    bound = handler.name
    return any(
        isinstance(node, ast.Raise) and (node.exc is None or (isinstance(node.exc, ast.Name) and node.exc.id == bound))
        for node in auditor.core.walk_within_scope(handler)
    )


def handler_types(handler: ast.ExceptHandler) -> frozenset[str] | None:
    """The class-name tails an `except` clause matches, or None for a broad one. Pure."""
    if handler.type is None:
        return None
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    names = set()
    for node in types:
        if isinstance(node, (ast.Name, ast.Attribute)):
            names.add(ast.unparse(node).rsplit('.', 1)[-1])
    if names & BROAD_HANDLER_NAMES:
        return None
    return frozenset(names)


def raised_name(node: ast.Raise) -> str | None:
    """The class-name tail a `raise` statement raises, or None.

    `raise X(...)` and `raise mod.X(...)` name a class; a bare `raise` and
    `raise <name>` re-raise something already caught.
    """
    if node.exc is None or not isinstance(node.exc, ast.Call):
        return None
    func = node.exc.func
    if isinstance(func, (ast.Name, ast.Attribute)):
        return ast.unparse(func).rsplit('.', 1)[-1]
    return None


# One `try`'s handlers in source order: what each matches (None for a broad
# clause) and whether it passes the error on.
HandlerLevel = tuple[tuple[frozenset[str] | None, bool], ...]


def handler_level(node: ast.Try | ast.TryStar) -> HandlerLevel:
    """A `try`'s handlers in source order. Pure."""
    return tuple((handler_types(handler), handler_passes_on(handler)) for handler in node.handlers)


def tuple_constants(trees: collections.abc.Iterable[ast.Module]) -> dict[str, frozenset[str]]:
    """Each module-level tuple of class names in the package, by name, to its members' tails. Pure.

    Built on `module_tuple_constants`, so a name assigned twice in a module is
    left out, and a member is read one level deep. Only a tuple whose members
    are all names or attributes counts, and a name two modules bind to
    different members is left out: either way a handler naming it keeps the
    name test. `expand_level` reads the result.
    """
    found: dict[str, frozenset[str]] = {}
    ambiguous: set[str] = set()
    for tree in trees:
        for name, members in module_tuple_constants(tree).items():
            if not members or not all(isinstance(member, (ast.Name, ast.Attribute)) for member in members):
                continue
            tails = frozenset(ast.unparse(member).rsplit('.', 1)[-1] for member in members)
            if found.setdefault(name, tails) != tails:
                ambiguous.add(name)
    return {name: tails for name, tails in found.items() if name not in ambiguous}


def expand_level(level: HandlerLevel, constants: collections.abc.Mapping[str, frozenset[str]]) -> HandlerLevel:
    """`level` with each tuple constant a handler names replaced by its members. Pure."""
    return tuple((None if types is None else frozenset().union(*(constants.get(name, {name}) for name in types)), passes_on) for types, passes_on in level)


def level_catches(level: HandlerLevel, lineage: set[str]) -> bool:
    """Whether a `try` stops an error of this lineage. Pure.

    Python runs only the first clause that matches, so a re-raising clause
    lets the error through even when a later, broader clause would catch it.
    """
    for types, passes_on in level:
        if types is None or types & lineage:
            return not passes_on
    return False


def reach_sites(
    body: list[ast.stmt],
    catches: tuple[HandlerLevel, ...] = (),
) -> list[tuple[ast.AST, tuple[HandlerLevel, ...]]]:
    """Every `raise` and call in a function body, with the `try` levels around it.

    Nested functions, lambdas and classes are skipped: their raises reach their
    own callers. A `try` body sees its own handlers; its handlers, `else` and
    `finally` see only the handlers outside it.
    """
    sites: list[tuple[ast.AST, tuple[HandlerLevel, ...]]] = []

    def visit(node: ast.AST, around: tuple[HandlerLevel, ...]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return
        if isinstance(node, (ast.Try, ast.TryStar)):
            inner = (*around, handler_level(node))
            for child in node.body:
                visit(child, inner)
            for child in [*node.handlers, *node.orelse, *node.finalbody]:
                visit(child, around)
            return
        if isinstance(node, (ast.Raise, ast.Call)):
            sites.append((node, around))
        for child in ast.iter_child_nodes(node):
            visit(child, around)

    for statement in body:
        visit(statement, catches)
    return sites


def nested_call_sites(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[ast.AST, tuple[HandlerLevel, ...]]]:
    """`reach_sites(func.body)` plus, for each call by bare name to a def
    nested directly in `func`'s body, that def's own reach sites with the
    call's handler levels prepended. One level deep; a nested def that is
    never called contributes nothing.
    """
    nested = {stmt.name: stmt for stmt in func.body if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))}
    sites = reach_sites(func.body)
    for site, around in list(sites):
        if isinstance(site, ast.Call) and isinstance(site.func, ast.Name) and site.func.id in nested:
            sites.extend((inner, (*around, *levels)) for inner, levels in reach_sites(nested[site.func.id].body))
    return sites


def function_levels(body: list[ast.stmt]) -> list[HandlerLevel]:
    """Every `try` level in a function body, nested defs skipped."""
    levels: list[HandlerLevel] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return
        if isinstance(node, (ast.Try, ast.TryStar)):
            levels.append(handler_level(node))
        for child in ast.iter_child_nodes(node):
            visit(child)

    for statement in body:
        visit(statement)
    return levels


# The `load` and `loads` entry points of `json` and `tomllib`.
LOADER_CALLS = frozenset({'load', 'loads'})


OS_ERROR_NAMES = frozenset({'BaseException', 'Exception', 'IOError', 'OSError'})


def enveloped_functions(tree: ast.Module) -> set[str]:
    """Names of module-level functions with a `try` whose handler covers `OSError`."""
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in auditor.core.walk_within_scope(node):
            if not isinstance(sub, ast.Try):
                continue
            for handler in sub.handlers:
                if handler.type is None:
                    names.add(node.name)
                    continue
                elements = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
                if any(isinstance(element, (ast.Name, ast.Attribute)) and ast.unparse(element).rsplit('.', 1)[-1] in OS_ERROR_NAMES for element in elements):
                    names.add(node.name)
    return names


# Anything that also satisfies a narrower requirement, whatever the body does.
UNIVERSAL_CATCHES = frozenset({'*bare*', 'BaseException', 'Exception'})


# `OSError`'s subclasses are accepted as satisfying the disk branch, matching
# `check_filesystem_envelope_gap`. Neither check tries to prove that the
# subclass named is the one the body can raise; that is Phase B's job.
OSERROR_SATISFIERS = frozenset(
    {
        'FileNotFoundError',
        'IOError',
        'IsADirectoryError',
        'OSError',
        'PermissionError',
    }
)


# Calls that read a file as text, and so can raise `UnicodeDecodeError` on
# bytes the declared encoding cannot decode. `.decode()` is deliberately not a
# trigger: the attribute name is used by tokenisers, codecs and protocol
# helpers far more often than by `bytes.decode`, so it would fire mostly on
# calls that cannot raise `UnicodeDecodeError` at all.
TEXT_DECODING_CALLS = frozenset({'read_text'})


def guarded_body_nodes(node: ast.FunctionDef | ast.AsyncFunctionDef) -> collections.abc.Iterable[ast.AST]:
    """Every node in the function's own body - not its signature or decorators.

    A decorator is itself a `Call`, and walking it would let
    `@pandas_backed_cache(...)`-shaped decoration read as a body that parses.
    Pruned at a nested `def`/`class` too: the outer walk reaches those on their
    own, where their own decoration is the envelope being judged.
    """
    for stmt in node.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield stmt
        yield from auditor.core.walk_within_scope(stmt)


def a2_branches_for_call(node: ast.Call) -> list[tuple[str, frozenset[str]]]:
    """The locked-set branches this call triggers, as (required, satisfied-by).

    Each branch is one row of A2's locked set, keyed on a form that needs no
    judgement to recognise: the module the parser is called on, or the exact
    name of the filesystem primitive.
    """
    branches: list[tuple[str, frozenset[str]]] = []
    short: str | None = None
    if isinstance(node.func, ast.Name):
        short = node.func.id
    elif isinstance(node.func, ast.Attribute):
        short = node.func.attr
        receiver = ast.unparse(node.func.value).rsplit('.', 1)[-1]
        if receiver == 'json' and short in LOADER_CALLS:
            branches.append(('json.JSONDecodeError', frozenset({'JSONDecodeError', 'ValueError'})))
        if receiver in {'pandas', 'pd'} and short.startswith('read_'):
            branches.append(('pandas.errors.ParserError', frozenset({'ParserError'})))
        if receiver == 'gzip' and short in {'GzipFile', 'open'}:
            branches.append(('gzip.BadGzipFile', frozenset({'BadGzipFile'})))
    if short in TEXT_DECODING_CALLS:
        branches.append(('UnicodeDecodeError', frozenset({'UnicodeDecodeError'})))
    if short in FILESYSTEM_TOUCHING_CALLS:
        branches.append(('OSError', OSERROR_SATISFIERS))
    return branches


# Calls whose result `filesystem-op-without-envelope` follows: filesystem writes, and read paths that can raise
# `OSError` too. `replace`, `rename`, `copy` and `remove` are left out: `str.replace`, `dataclasses.replace`,
# `list.copy` and `list.remove` make them too noisy.
FILESYSTEM_OP_CALLS = frozenset(
    {
        'copytree',
        'from_pretrained',
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


def filesystem_envelope_gap_sites(tree: ast.Module) -> list[tuple[int, list[str]]]:
    """Each `try` that calls a filesystem-touching helper and raises from a handler, with no handler for `OSError`.

    The site is its first handler's line and the caught classes, as source text.
    """
    sites: list[tuple[int, list[str]]] = []
    constants = module_tuple_constants(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        touched_fs = False
        for stmt in node.body:
            for sub in ast.walk(stmt):
                if not isinstance(sub, ast.Call):
                    continue
                short = None
                if isinstance(sub.func, ast.Name):
                    short = sub.func.id
                elif isinstance(sub.func, ast.Attribute):
                    short = sub.func.attr
                if short in FILESYSTEM_TOUCHING_CALLS:
                    touched_fs = True
                    break
            if touched_fs:
                break
        if not touched_fs:
            continue
        covers_os = False
        for handler in node.handlers:
            if handler.type is None:
                covers_os = True
                break
            elements = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
            resolved: list[ast.expr] = []
            for element in elements:
                if isinstance(element, ast.Name) and element.id in constants:
                    resolved.extend(constants[element.id])
                else:
                    resolved.append(element)
            type_src = ', '.join(ast.unparse(element) for element in resolved)
            names = set(re.findall(r'[A-Za-z_][A-Za-z_0-9]*', type_src))
            if {'OSError', 'Exception', 'BaseException', 'IOError', 'PermissionError', 'FileNotFoundError'} & names:
                covers_os = True
                break
        if covers_os:
            continue
        if not any(isinstance(sub, ast.Raise) and sub.exc is not None for handler in node.handlers for sub in ast.walk(handler)):
            continue
        first_handler = node.handlers[0] if node.handlers else None
        lineno = first_handler.lineno if first_handler is not None else node.lineno
        caught = ['<bare>' if h.type is None else ast.unparse(h.type) for h in node.handlers]
        sites.append((lineno, caught))
    return sites


def filesystem_op_sites(src_root: pathlib.Path) -> list[tuple[pathlib.Path, str, str, int]]:
    """Each public entry point's first filesystem call outside any `try`, in a package with a domain error.

    The site is the file, the function's name, the call's short name and its line.
    """
    package_has_domain_error: set[tuple[str, ...]] = set()
    for path in auditor.core.all_py_files(src_root):
        if path.name != 'errors.py':
            continue
        tree = auditor.core.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.endswith('Error'):
                package_has_domain_error.add(path.relative_to(src_root).parts[:-1])
                break
    if not package_has_domain_error:
        return []

    package_exports: dict[tuple[str, ...], set[str]] = collections.defaultdict(set)
    for path in auditor.core.all_py_files(src_root):
        if path.name != '__init__.py':
            continue
        pkg = path.relative_to(src_root).parts[:-1]
        if pkg not in package_has_domain_error:
            continue
        tree = auditor.core.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id == '__all__':
                        if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    package_exports[pkg].add(elt.value)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    package_exports[pkg].add(alias.asname or alias.name)

    sites: list[tuple[pathlib.Path, str, str, int]] = []
    for path in auditor.core.all_py_files(src_root):
        if path.name in ERRORS_MODULE_NAMES:
            continue
        pkg = path.relative_to(src_root).parts[:-1]
        if pkg not in package_has_domain_error:
            continue
        tree = auditor.core.read_and_parse(path)
        if tree is None:
            continue
        exports = package_exports.get(pkg, set())
        enveloped = enveloped_functions(tree)
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            is_exported = func.name in exports
            docstring = ast.get_docstring(func) or ''
            mentions_raises = bool(re.search(r'\bRaises?\b', docstring))
            if not (is_exported or mentions_raises):
                continue
            try_linenos: set[int] = set()
            for sub in ast.walk(func):
                if isinstance(sub, ast.Try):
                    for stmt in sub.body:
                        for innersub in ast.walk(stmt):
                            if hasattr(innersub, 'lineno'):
                                try_linenos.add(innersub.lineno)
            for inner in ast.walk(func):
                if not isinstance(inner, ast.Call):
                    continue
                short = None
                if isinstance(inner.func, ast.Name):
                    short = inner.func.id
                elif isinstance(inner.func, ast.Attribute):
                    short = inner.func.attr
                if short not in FILESYSTEM_OP_CALLS:
                    continue
                if isinstance(inner.func, ast.Name) and short in enveloped:
                    continue
                if inner.lineno in try_linenos:
                    continue
                sites.append((path, func.name, short, inner.lineno))
                break
    return sites


def enclosing_return_annotation(tree: ast.AST, lineno: int) -> str | None:
    """The source of the return annotation of the innermost function holding the line."""
    best: tuple[int, str | None] | None = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = node.lineno
        end = getattr(node, 'end_lineno', None) or start
        if not (start <= lineno <= end):
            continue
        ann = None
        if node.returns is not None:
            ann = ast.unparse(node.returns)
        if best is None or start > best[0]:
            best = (start, ann)
    return best[1] if best else None


def graceful_degradation_sites(tree: ast.AST) -> list[int]:
    """The line of each constant default a handler returns after `logger.exception`, with no `raise`.

    A function annotated `-> int` is an exit-code entry point and is left out.
    """
    linenos: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        has_logger_exception = False
        has_raise = False
        handler_last_return: ast.Return | None = None
        for stmt in node.body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Call):
                    src = ast.unparse(sub.func)
                    if (src.endswith('logger.exception') or src.endswith('.exception')) and ('logger' in src or 'loguru' in src):
                        has_logger_exception = True
                if isinstance(sub, ast.Raise):
                    has_raise = True
            if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant):
                handler_last_return = stmt
        if not has_logger_exception or has_raise:
            continue
        fallthrough_return: ast.Return | None = None
        if handler_last_return is None:
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                start = fn.lineno
                end = getattr(fn, 'end_lineno', None) or start
                if not (start <= node.lineno <= end):
                    continue
                last_stmt = fn.body[-1] if fn.body else None
                if isinstance(last_stmt, ast.Return) and isinstance(last_stmt.value, ast.Constant):
                    fallthrough_return = last_stmt
                break
        default_return = handler_last_return or fallthrough_return
        if default_return is None:
            continue
        ret_ann = enclosing_return_annotation(tree, default_return.lineno)
        if ret_ann is not None and ret_ann.strip() == 'int':
            continue
        linenos.append(default_return.lineno)
    return linenos


def translator_gap_sites(tree: ast.AST, envelopes: collections.abc.Mapping[str, frozenset[str]]) -> list[tuple[str, int, str, list[str], list[str], set[str]]]:
    """Each function whose translating decorator or `with` envelope omits an error its earliest call can raise.

    The site is the function's name, the earliest triggering call's line and source, the missing errors, the
    envelopes that guard the call and what they catch.
    """
    sites: list[tuple[str, int, str, list[str], list[str], set[str]]] = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        caught: set[str] = set()
        sources: list[str] = []
        for decorator in func.decorator_list:
            short = callable_short_name(decorator)
            if short in envelopes:
                caught |= envelopes[short]
                sources.append(f'@{short}')
        with_ranges: list[tuple[int, int, frozenset[str], str]] = []
        lexical_try_linenos: set[int] = set()
        for sub in guarded_body_nodes(func):
            if isinstance(sub, ast.Try):
                for stmt in sub.body:
                    for inner in ast.walk(stmt):
                        if hasattr(inner, 'lineno'):
                            lexical_try_linenos.add(inner.lineno)
            if not isinstance(sub, (ast.With, ast.AsyncWith)) or not sub.body:
                continue
            block_caught: set[str] = set()
            block_names: list[str] = []
            for item in sub.items:
                short = callable_short_name(item.context_expr)
                if short in envelopes:
                    block_caught |= envelopes[short]
                    block_names.append(short)
            if not block_caught:
                continue
            start = sub.body[0].lineno
            end = getattr(sub.body[-1], 'end_lineno', None) or sub.body[-1].lineno
            with_ranges.append((start, end, frozenset(block_caught), ', '.join(block_names)))
        gaps: list[tuple[int, str, list[str], list[str], set[str]]] = []
        for node in guarded_body_nodes(func):
            if not isinstance(node, ast.Call):
                continue
            branches = a2_branches_for_call(node)
            if not branches or node.lineno in lexical_try_linenos:
                continue
            site_caught = set(caught)
            site_sources = list(sources)
            for start, end, range_caught, range_names in with_ranges:
                if start <= node.lineno <= end:
                    site_caught |= range_caught
                    site_sources.append(f'with {range_names}')
            if not site_sources or site_caught & UNIVERSAL_CATCHES:
                continue
            missing = [required for required, satisfied_by in branches if not satisfied_by & site_caught]
            if missing:
                gaps.append((node.lineno, ast.unparse(node.func), missing, site_sources, site_caught))
        if not gaps:
            continue
        lineno, callee, missing, site_sources, site_caught = min(gaps, key=lambda gap: gap[0])
        sites.append((func.name, lineno, callee, missing, site_sources, site_caught))
    return sites
