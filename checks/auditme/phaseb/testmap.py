"""The test tree index: which tests reach which package function.

`build_test_map` parses each test file once and maps each package function
id to the `TestRef` entries of the tests that call it. Resolution starts from
each test file's imports through the shared call resolver, so a bare name
match without an import is never evidence.
"""

import ast
import collections.abc
import dataclasses
import pathlib
import typing

import auditme.core
import auditme.phaseb.candidates
from auditme.phaseb.errors import PhaseBError

TEST_TREES = ('src/tests', 'tests')


@dataclasses.dataclass(frozen=True)
class TestRef:
    """One test function that reaches a package function."""

    id: str  # 'src/tests/test_mod.py::test_load'
    path: str
    start: int
    end: int
    route: typing.Literal['direct', 'caller']
    via: str | None  # 'caller' only: id of the package function the test calls
    property: bool  # decorated with hypothesis `given`


@dataclasses.dataclass(frozen=True)
class ParsedFile:
    """A file parsed once, with its repo-relative path and import bindings."""

    path: pathlib.Path
    rel: str
    module: str
    tree: ast.Module
    lines: list[str]
    bindings: dict[str, str]


def parse_file(path: pathlib.Path, base: pathlib.Path, root: pathlib.Path) -> ParsedFile:
    """Parse one file, naming it in the error when it cannot be read or parsed.

    Raises:
        PhaseBError: the file is not valid UTF-8 Python.
    """
    try:
        text = path.read_text(encoding='utf-8')
        tree = ast.parse(text)
    except (OSError, UnicodeDecodeError, SyntaxError) as error:
        raise PhaseBError(f'cannot parse {path}: {error}') from error
    module = auditme.core.module_dotted(path, base)
    return ParsedFile(
        path=path,
        rel=auditme.core._relpath(path, root),
        module=module,
        tree=tree,
        lines=text.splitlines(),
        bindings=auditme.core.call_bindings(tree, module, path.name == '__init__.py'),
    )


def is_test_path(path: pathlib.Path, root: pathlib.Path) -> bool:
    """True for a file in a `tests` directory, a `test_*.py`, `*_test.py` or `conftest.py`."""
    relative = path.relative_to(root)
    name = path.name
    return 'tests' in relative.parts[:-1] or name.startswith('test_') or name.endswith('_test.py') or name == 'conftest.py'


def test_tree_roots(root: pathlib.Path) -> list[pathlib.Path]:
    """The test directories that exist, `src/tests` then `tests`."""
    return [root / tree for tree in TEST_TREES if (root / tree).is_dir()]


def source_sites(root: pathlib.Path) -> tuple[list[auditme.phaseb.candidates.Site], dict[str, ParsedFile]]:
    """Every top-level function and class method under the audited roots, minus test files, and each module's parse.

    Raises:
        PhaseBError: an audited source file does not parse.
    """
    sites: list[auditme.phaseb.candidates.Site] = []
    parsed: dict[str, ParsedFile] = {}
    for src_root in auditme.core._audit_roots(root):
        for path in auditme.core._all_py_files(src_root):
            if is_test_path(path, root):
                continue
            file = parse_file(path, src_root, root)
            parsed[file.module] = file
            for node in file.tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sites.append(auditme.phaseb.candidates.Site(file.module, f'{file.module}.{node.name}', None, node, file.rel, file.lines))
                elif isinstance(node, ast.ClassDef):
                    sites.extend(
                        auditme.phaseb.candidates.Site(file.module, f'{file.module}.{node.name}.{member.name}', node.name, member, file.rel, file.lines)
                        for member in node.body
                        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                    )
    return sites, parsed


def parse_test_tree(root: pathlib.Path) -> tuple[list[ParsedFile], dict[pathlib.Path, ParsedFile]]:
    """The test files (`test_*.py`, `*_test.py`) and every `conftest.py`, each parsed once.

    Raises:
        PhaseBError: a test file does not parse.
    """
    tests: dict[pathlib.Path, ParsedFile] = {}
    conftests: dict[pathlib.Path, ParsedFile] = {}
    for tree_root in test_tree_roots(root):
        for path in sorted(tree_root.rglob('*.py')):
            if path in tests or path in conftests:
                continue
            if path.name == 'conftest.py':
                conftests[path.parent] = parse_file(path, tree_root, root)
            elif path.name.startswith('test_') or path.name.endswith('_test.py'):
                tests[path] = parse_file(path, tree_root, root)
    return sorted(tests.values(), key=lambda file: file.rel), conftests


def is_fixture(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True for a function decorated with `fixture` or `pytest.fixture`, called or not."""
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if ast.unparse(target).rpartition('.')[2] == 'fixture':
            return True
    return False


def is_property_test(node: ast.FunctionDef | ast.AsyncFunctionDef, bindings: collections.abc.Mapping[str, str]) -> bool:
    """True when a decorator is hypothesis `given`, imported from `hypothesis` or reached as `hypothesis.given`."""
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        head, _, rest = ast.unparse(target).partition('.')
        dotted = bindings[head] + (f'.{rest}' if rest else '') if head in bindings else ast.unparse(target)
        if dotted == 'hypothesis.given':
            return True
    return False


def fixtures_of(file: ParsedFile) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """The module-level fixtures a file defines, by name."""
    return {node.name: node for node in file.tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and is_fixture(node)}


def conftest_chain(file: ParsedFile, tree_root_names: set[pathlib.Path], conftests: dict[pathlib.Path, ParsedFile]) -> list[ParsedFile]:
    """The `conftest.py` files above a test file, nearest first, up to the test tree's root."""
    chain: list[ParsedFile] = []
    for directory in file.path.parents:
        if directory in conftests:
            chain.append(conftests[directory])
        if directory in tree_root_names:
            break
    return chain


def test_functions(file: ParsedFile) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Each test in a file: `test_*` at module level or in a `Test*` class, with its qualified name."""
    found: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for node in file.tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
            found.append((node.name, node))
        elif isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
            found.extend(
                (f'{node.name}.{member.name}', member)
                for member in node.body
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and member.name.startswith('test_')
            )
    return found


def build_test_map(root: pathlib.Path, depth: int) -> dict[str, tuple[TestRef, ...]]:
    """Map each package function id to the tests that reach it, sorted by id.

    A test reaches a function directly when a call in its body, or in a
    fixture it requests from its own file or a `conftest.py` above it,
    resolves to it. `depth` bounds the caller route.

    Raises:
        PhaseBError: a test file or audited source file does not parse.
    """
    sites, parsed_sources = source_sites(root)
    tests, conftests = parse_test_tree(root)
    by_name = {site.qualname: site for site in sites}
    known = {site.qualname: site.cls for site in sites}
    aliases = auditme.core.reexport_aliases(
        {module: auditme.core.from_import_bindings(file.tree, module, file.path.name == '__init__.py') for module, file in parsed_sources.items()},
        known,
    )
    tree_root_names = set(test_tree_roots(root))

    def called(file: ParsedFile, node: ast.AST) -> set[str]:
        return {
            target
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            for target in [auditme.core.resolve_call(call, file.module, None, file.bindings, known, aliases, class_methods=True)]
            if target
        }

    def direct_targets(file: ParsedFile, node: ast.FunctionDef | ast.AsyncFunctionDef, chain: list[tuple[ParsedFile, dict]]) -> set[str]:
        reached = called(file, node)
        seen: set[str] = set()
        pending = [argument.arg for argument in node.args.args + node.args.kwonlyargs]
        while pending:
            name = pending.pop()
            if name in seen:
                continue
            seen.add(name)
            for owner, defined in chain:
                if name in defined:
                    fixture = defined[name]
                    reached |= called(owner, fixture)
                    pending.extend(argument.arg for argument in fixture.args.args + fixture.args.kwonlyargs)
                    break
        return reached

    refs: dict[str, dict[str, TestRef]] = {}
    for file in tests:
        chain = [(owner, fixtures_of(owner)) for owner in [file, *conftest_chain(file, tree_root_names, conftests)]]
        for qualname, node in test_functions(file):
            test_id = f'{file.rel}::{qualname}'
            ref = TestRef(
                id=test_id,
                path=file.rel,
                start=min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)]),
                end=node.end_lineno or node.lineno,
                route='direct',
                via=None,
                property=is_property_test(node, file.bindings),
            )
            for target in direct_targets(file, node, chain):
                refs.setdefault(by_name[target].id, {})[test_id] = ref
    return {function_id: tuple(sorted(found.values(), key=lambda ref: ref.id)) for function_id, found in refs.items()}
