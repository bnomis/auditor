"""The test tree index: which tests reach which package function.

`load_test_map` parses each test file once and maps each package function
id to the `TestRef` entries of the tests that call it. Resolution starts from
each test file's imports through the shared call resolver, so a bare name
match without an import is never evidence.
"""

import ast
import dataclasses
import functools
import pathlib
import typing

import auditme.core
import auditme.phaseb.candidates
import auditme.phaseb.errors

if typing.TYPE_CHECKING:
    import collections.abc

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


def read_test_file(path: pathlib.Path, base: pathlib.Path, root: pathlib.Path) -> ParsedFile:
    """Parse one file, naming it in the error when it cannot be read or parsed.

    Raises:
        PhaseBError: the file is not valid UTF-8 Python.
    """
    try:
        text = path.read_text(encoding='utf-8')
        tree = ast.parse(text)
    except (OSError, UnicodeDecodeError, SyntaxError) as error:
        raise auditme.phaseb.errors.PhaseBError(f'cannot parse {path}') from error
    module = auditme.core.module_dotted(path, base)
    return ParsedFile(
        path=path,
        rel=auditme.core.relpath(path, root),
        module=module,
        tree=tree,
        lines=text.splitlines(),
        bindings=auditme.core.call_bindings(tree, module, path.name == '__init__.py'),
    )


def is_test_path(path: pathlib.Path, root: pathlib.Path) -> bool:
    """True for a file in a `tests` directory, a `test_*.py`, `*_test.py` or `conftest.py`."""
    return auditme.core.is_test_relpath(path.relative_to(root).as_posix())


def test_tree_roots(root: pathlib.Path, audit_roots: list[pathlib.Path]) -> list[pathlib.Path]:
    """The directories tests are read from: every audit root, then `src/tests` and `tests` where they exist and are not already listed."""
    roots = list(audit_roots)
    roots.extend(root / tree for tree in TEST_TREES if (root / tree).is_dir() and root / tree not in roots)
    return roots


def source_sites(root: pathlib.Path, audit_roots: list[pathlib.Path]) -> tuple[list[auditme.phaseb.candidates.Site], dict[str, ParsedFile]]:
    """Every top-level function and class method under the audited roots, minus test files, and each module's parse.

    Raises:
        PhaseBError: an audited source file does not parse.
    """
    sites: list[auditme.phaseb.candidates.Site] = []
    parsed: dict[str, ParsedFile] = {}
    for src_root in audit_roots:
        for path in auditme.core.all_py_files(src_root):
            if is_test_path(path, root):
                continue
            file = read_test_file(path, src_root, root)
            parsed[file.module] = file
            sites.extend(auditme.phaseb.candidates.module_sites(file.module, file.tree, file.rel, file.lines))
    return sites, parsed


def read_test_tree(root: pathlib.Path, audit_roots: list[pathlib.Path]) -> tuple[list[ParsedFile], dict[pathlib.Path, ParsedFile]]:
    """The test files (`test_*.py`, `*_test.py`) and every `conftest.py`, each parsed once.

    Raises:
        PhaseBError: a test file does not parse.
    """
    tests: dict[pathlib.Path, ParsedFile] = {}
    conftests: dict[pathlib.Path, ParsedFile] = {}
    for tree_root in test_tree_roots(root, audit_roots):
        for path in sorted(tree_root.rglob('*.py')):
            if path in tests or path in conftests:
                continue
            if path.name == 'conftest.py':
                conftests[path.parent] = read_test_file(path, tree_root, root)
            elif path.name.startswith('test_') or path.name.endswith('_test.py'):
                tests[path] = read_test_file(path, tree_root, root)
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


def imported_names(file: ParsedFile) -> set[str]:
    """Every dotted name a file's top-level imports bind or name."""
    names = set(file.bindings.values())
    for statement in file.tree.body:
        if isinstance(statement, ast.Import):
            names.update(alias.name for alias in statement.names)
    return names


def reach(direct: collections.abc.Mapping[str, list[str]], start: collections.abc.Iterable[str], depth: int) -> dict[str, int]:
    """Each name reached from `start` within `depth` calls, with its distance; `start` itself is at 0."""
    distance = dict.fromkeys(start, 0)
    frontier = list(distance)
    for step in range(1, depth + 1):
        frontier = sorted({callee for name in frontier for callee in direct.get(name, []) if callee not in distance})
        distance.update(dict.fromkeys(frontier, step))
    return distance


@dataclasses.dataclass
class TestIndex:
    """The parsed package and test tree, built once, with the tests' routes to each function."""

    __test__ = False

    root: pathlib.Path
    sites: dict[str, auditme.phaseb.candidates.Site]  # by dotted qualname
    direct: dict[str, list[str]]  # qualname -> sorted resolved callees
    tests: list[ParsedFile]
    conftests: dict[pathlib.Path, ParsedFile]
    reached: dict[str, dict[str, tuple[ast.FunctionDef | ast.AsyncFunctionDef, set[str]]]]  # test file rel -> test name -> (node, directly reached)
    by_id: dict[str, auditme.phaseb.candidates.Site]
    sources: dict[str, ParsedFile]  # package modules by dotted name
    aliases: dict[str, str] = dataclasses.field(default_factory=dict)  # re-export `module.name` -> target qualname
    tree_roots: list[pathlib.Path] = dataclasses.field(default_factory=list)  # the directories tests are read from

    def refs(self, depth: int) -> dict[str, tuple[TestRef, ...]]:
        """Map each package function id to the tests that reach it, sorted by id."""
        found: dict[str, dict[str, TestRef]] = {}
        reached_from: dict[str, dict[str, int]] = {}
        for file in self.tests:
            for qualname, (node, targets) in self.reached[file.rel].items():
                test_id = f'{file.rel}::{qualname}'
                base = TestRef(
                    id=test_id,
                    path=file.rel,
                    start=min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)]),
                    end=node.end_lineno or node.lineno,
                    route='direct',
                    via=None,
                    property=is_property_test(node, file.bindings),
                )
                for target in sorted(targets):
                    found.setdefault(self.sites[target].id, {})[test_id] = base
                for via in sorted(targets):
                    if via not in reached_from:
                        reached_from[via] = reach(self.direct, [via], depth)
                    for target in reached_from[via]:
                        if target != via and target not in targets:
                            found.setdefault(self.sites[target].id, {}).setdefault(test_id, dataclasses.replace(base, route='caller', via=self.sites[via].id))
        return {function_id: tuple(sorted(refs.values(), key=lambda ref: ref.id)) for function_id, refs in found.items()}

    @functools.cached_property
    def importers(self) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
        """Test file paths by module imported (a name or any parent of it), and by exact imported name; each file's names are computed once."""
        by_module: dict[str, set[str]] = {}
        by_name: dict[str, set[str]] = {}
        for file in self.tests:
            for name in imported_names(file):
                by_name.setdefault(name, set()).add(file.rel)
                parts = name.split('.')
                for end in range(1, len(parts) + 1):
                    by_module.setdefault('.'.join(parts[:end]), set()).add(file.rel)
        return by_module, by_name

    @functools.cached_property
    def reverse(self) -> dict[str, list[str]]:
        """Each qualname's direct callers, built on first use and shared by every query."""
        reverse: dict[str, list[str]] = {}
        for name, callees in self.direct.items():
            for callee in callees:
                reverse.setdefault(callee, []).append(name)
        return reverse

    def caller_sites(self, function_id: str, depth: int) -> list[auditme.phaseb.candidates.Site]:
        """The package functions that reach a function within `depth` calls, sorted by id."""
        target = self.by_id[function_id].qualname
        found = reach(self.reverse, [target], depth)
        return sorted((self.sites[name] for name in found if name != target), key=lambda site: site.id)

    def callers(self, function_id: str, depth: int) -> list[dict[str, str | int]]:
        """The callers of a function as `{id, path, start, end}`, sorted by id."""
        return [{'id': site.id, 'path': site.path, 'start': site.start, 'end': site.end} for site in self.caller_sites(function_id, depth)]

    def test_files(self, function_id: str, depth: int) -> list[str]:
        """The test files that bear on a function, sorted.

        The mirrored test file where it exists (`src/<project>/<pkg>/<f>.py` ->
        `src/tests/<pkg>/test_<f>.py`, also with the project directory kept),
        every test file importing the function's module, every one importing
        a caller's module, and every one importing a re-export of the
        function by its own name (`from pkg import load`) or the module that
        re-exports it (`import pkg`).
        """
        site = self.by_id[function_id]
        modules = {site.module, *(caller.module for caller in self.caller_sites(function_id, depth))}
        reexports = {alias for alias, target in self.aliases.items() if target == site.qualname}
        reexport_names = reexports | {alias.rsplit('.', 1)[0] for alias in reexports}
        by_module, by_name = self.importers
        found = {rel for module in modules for rel in by_module.get(module, ())}
        found.update(rel for name in reexport_names for rel in by_name.get(name, ()))
        found.update(self.mirrored(site))
        return sorted(found)

    def mirrored(self, site: auditme.phaseb.candidates.Site) -> list[str]:
        """The mirrored test files of a function's module that exist."""
        source = pathlib.PurePosixPath(site.path)
        parts = source.parts[1:] if source.parts[0] == 'src' else source.parts
        stem = f'test_{source.stem}.py'
        candidates = {(*parts[:-1], stem), (*parts[1:-1], stem)}
        return sorted(
            auditme.core.relpath(path, self.root)
            for tree_root in self.tree_roots
            for names in candidates
            for path in [tree_root.joinpath(*names)]
            if path.is_file()
        )


def load_test_index(root: pathlib.Path) -> TestIndex:
    """Parse the package and its test tree once and resolve every test's direct calls.

    A test reaches a function directly when a call in its body, or in a
    fixture it requests from its own file or a `conftest.py` above it,
    resolves to it.

    Raises:
        PhaseBError: a test file or audited source file does not parse.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    roots, _ = auditme.core.cached_roots(root)
    site_list, parsed_sources = source_sites(root, roots)
    tests, conftests = read_test_tree(root, roots)
    sites = {site.qualname: site for site in site_list}
    known = {site.qualname: site.cls for site in site_list}
    aliases = auditme.core.reexport_aliases(
        {module: auditme.core.from_import_bindings(file.tree, module, file.path.name == '__init__.py') for module, file in parsed_sources.items()},
        known,
    )
    tree_roots = test_tree_roots(root, roots)
    tree_root_names = set(tree_roots)

    def called(file: ParsedFile, node: ast.AST, cls: str | None = None) -> set[str]:
        return {
            target
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            for target in [auditme.core.resolve_call(call, file.module, cls, file.bindings, known, aliases, class_methods=True)]
            if target
        }

    direct = {site.qualname: sorted(called(parsed_sources[site.module], site.node, site.cls) - {site.qualname}) for site in site_list}

    def direct_targets(file: ParsedFile, node: ast.FunctionDef | ast.AsyncFunctionDef, chain: list[tuple[ParsedFile, dict[str, typing.Any]]]) -> set[str]:
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

    reached: dict[str, dict[str, tuple[ast.FunctionDef | ast.AsyncFunctionDef, set[str]]]] = {}
    for file in tests:
        chain = [(owner, fixtures_of(owner)) for owner in [file, *conftest_chain(file, tree_root_names, conftests)]]
        reached[file.rel] = {qualname: (node, direct_targets(file, node, chain)) for qualname, node in test_functions(file)}
    return TestIndex(root, sites, direct, tests, conftests, reached, {site.id: site for site in site_list}, parsed_sources, aliases, tree_roots)


# auditme: accept[passthrough-shim] public, documented and in `phaseb.__all__`
def load_test_map(root: pathlib.Path, depth: int) -> dict[str, tuple[TestRef, ...]]:
    """Map each package function id to the tests that reach it, sorted by id.

    A test reaches a function directly when a call in its body, or in a
    fixture it requests, resolves to it; through a caller when a function it
    reaches directly has callees reaching the target within `depth` calls,
    `via` naming that function.

    Raises:
        PhaseBError: a test file or audited source file does not parse.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    return load_test_index(root).refs(depth)
