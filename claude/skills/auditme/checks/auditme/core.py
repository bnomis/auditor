"""Shared helpers every check uses."""

import ast
import collections
import collections.abc
import json
import pathlib
import re
import tomllib
import types

# An accept marker may name the single rule it answers for:
#     # auditme: accept[failure-as-absence] the caller reads batch.error
# An unscoped marker accepts every rule that fires on the line, which is how
# every marker written before 2026-08-12 behaves. That form is retained so no
# existing marker needs migrating, but it is the reason a newly added check can
# arrive silently pre-accepted: a marker weighed for one rule cannot have
# considered a rule that did not exist when it was written. New markers should
# name their rule.
# One marker; its reason ends where the next marker on the line begins.
ACCEPT_COMMENT_RE = re.compile(r'#\s*auditme:\s*accept\b(?:\[([a-z0-9-]+)\])?\s*((?:(?!#\s*auditme:).)*)')

# Hits already printed this run, as their serialised form. The driver runs every
# check once per package under src/, so the project-level checks - the lockfile
# one, and every check that reads AGENTS.md - see the same project N times and
# would report each of their hits N times. A hit is identified by its whole
# record, so two genuinely different hits can never collide here.
EMITTED: set[str] = set()  # auditme: accept[mutable-module-level-exported] process-lifetime state the driver fills and the tests clear

# Builtin generics that take type parameters: a bare annotation or an empty
# constructor call of one names the type without its members.
BARE_GENERIC_NAMES = frozenset({'dict', 'frozenset', 'list', 'set', 'tuple'})


def is_test_relpath(rel: str) -> bool:
    """True for a root-relative path that is a `test_*.py`, `*_test.py`, `conftest.py` or inside a `tests` directory."""
    path = pathlib.PurePosixPath(rel)
    return 'tests' in path.parts[:-1] or path.name.startswith('test_') or path.name.endswith('_test.py') or path.name == 'conftest.py'


def emit(related: list[str] | None = None, **kwargs) -> None:
    """Print one hit. `related` names the other files a cross-file hit compares
    against (repository-relative, sorted, de-duplicated); it is omitted when
    empty so every other hit serialises as before."""
    if related:
        kwargs['related'] = sorted(set(related) - {kwargs.get('path')})
        if not kwargs['related']:
            del kwargs['related']
    line = json.dumps(kwargs, sort_keys=True)
    if line in EMITTED:
        return
    EMITTED.add(line)
    print(line)


def describe_error(error: BaseException) -> str:
    """The message of `error`, followed by its `__cause__` in brackets when set.

    The command-line entry points print this once, so a raise site chains the
    cause with `from` instead of interpolating it into its own message."""
    cause = error.__cause__
    if cause is None:
        return str(error)
    return f'{error} ({cause})'


def source_lines(path: pathlib.Path) -> list[str]:
    try:
        return path.read_text(encoding='utf-8').splitlines()
    except UnicodeDecodeError:
        return []


def accept_reason(
    lines: list[str],
    lineno: int,
    end_lineno: int | None = None,
    rule: str | None = None,
) -> str | None:
    """Return the accept reason covering this line for this rule, if any.

    A marker scoped to a rule (`accept[some-rule]`) answers only for that rule;
    one that names a different rule is ignored, so a decision taken about
    tracebacks cannot silently excuse a later check about return values. An
    unscoped marker answers for everything, which keeps every pre-existing
    marker working unchanged.

    A line may carry several markers, one per rule; each one's reason ends
    where the next marker begins.

    `rule=None` means the caller has not said which rule is asking, and every
    marker matches. Passing the rule is what makes scoping effective, so a new
    check should always pass it.
    """
    candidates = list(range(lineno - 1, lineno + 1))
    if end_lineno is not None and end_lineno > lineno:
        candidates.extend(range(lineno + 1, end_lineno + 1))
    for candidate_lineno in candidates:
        if 1 <= candidate_lineno <= len(lines):
            for m in ACCEPT_COMMENT_RE.finditer(lines[candidate_lineno - 1]):
                scoped_to, reason = m.group(1), m.group(2)
                if scoped_to and rule and scoped_to != rule:
                    continue
                return reason.strip() or 'no reason given'
    return None


def type_checking_linenos(tree: ast.AST) -> set[int]:
    """Return line numbers inside any `if TYPE_CHECKING:` block."""
    result: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test_src = ast.unparse(node.test) if hasattr(ast, 'unparse') else ''
            if 'TYPE_CHECKING' in test_src:
                for child in ast.walk(node):
                    if hasattr(child, 'lineno'):
                        result.add(child.lineno)
    return result


def py_files(root: pathlib.Path, mode: str) -> list[pathlib.Path]:
    if mode == TOP_LEVEL:
        return sorted(p for p in root.glob('*.py') if p.is_file())
    return sorted(p for p in root.rglob('*.py'))


def all_py_files(src_root: pathlib.Path) -> list[pathlib.Path]:
    return py_files(src_root, ROOT_MODULES.get(src_root, PACKAGE))


def module_dotted(path: pathlib.Path, src_root: pathlib.Path) -> str:
    """The dotted name a module is imported by, rooted at its own root."""
    parts = path.relative_to(src_root).with_suffix('').parts
    if parts and parts[-1] == '__init__':
        parts = parts[:-1]
    if ROOT_MODULES.get(src_root) == TOP_LEVEL:
        return '.'.join(parts)
    return '.'.join((src_root.name,) + parts)


def relpath(p: pathlib.Path, root: pathlib.Path) -> str:
    return str(p.relative_to(root))


def accepted_lazy_imports(scope: pathlib.Path) -> set[tuple[str, str]]:
    agents = scope / 'AGENTS.md'
    if not agents.exists():
        return set()
    text = agents.read_text(encoding='utf-8')
    pairs: set[tuple[str, str]] = set()
    for line in text.splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < 2:
            continue
        m0 = re.findall(r'`([a-zA-Z_.][a-zA-Z0-9_.]*)`', cells[0])
        m1 = re.findall(r'`([a-zA-Z_.][a-zA-Z0-9_.]*)`', cells[1])
        for a in m0:
            for b in m1:
                pairs.add((a, b))
    return pairs


LITERAL_DISPATCH_TYPE_NAMES = frozenset({'str'})  # extensible via helper below


# Directories outside `src/` that hold auditable Python. A project's scripts
# conventionally live in `bin/`, and until 2026-09-01 the sweep could not see
# them at all: `packages_under` enumerates packages *under `src/`*, so a
# project whose scripts live in `bin/` got zero rows for them - accepted or
# otherwise - and a summary could record "`bin/` remains at zero unaccepted
# hits" as a measurement of nothing.
#
# The driver rebinds this when `--extra-root` is passed, so a check asking a
# corpus-wide question through `audit_roots` measures the scope that was
# actually swept rather than the default one. It is a tuple, and rebound rather
# than mutated, so a check cannot change what a later check sees.
EXTRA_ROOT_NAMES: tuple[str, ...] = ('bin',)


PACKAGE = 'package'
TOP_LEVEL = 'top-level'

# The mode of each declared root, rebound (never mutated) whenever
# `audit_roots` reads `[tool.auditme]`. A root absent from it is a package root.
ROOT_MODULES: types.MappingProxyType[pathlib.Path, str] = types.MappingProxyType({})


# Set by the driver's `--extra-root`: the command line replaces the declaration
# for one run, so `declared_roots` reports none, valid or not.
DECLARATION_IGNORED = False


class RootsError(Exception):
    """`[tool.auditme]` in `pyproject.toml` is invalid; the message is the error text."""


def path_inside(inner: pathlib.Path, outer: pathlib.Path) -> bool:
    return inner == outer or outer in inner.parents


def declared_roots(scope: pathlib.Path) -> list[tuple[pathlib.Path, str]] | None:
    """The roots `[tool.auditme]` declares, in order, or None when none are declared.

    None when `pyproject.toml` or the table is absent. Invalid TOML is an error
    only when the text mentions `[tool.auditme`; otherwise the defaults apply.

    Raises:
        RootsError: the declaration is invalid (bad TOML, an unknown key, a
            wrong type, a missing, empty or overlapping root).
    """
    pyproject = scope / 'pyproject.toml'
    if DECLARATION_IGNORED or not pyproject.is_file():
        return None
    text = pyproject.read_text(encoding='utf-8')
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        if '[tool.auditme' in text:
            raise RootsError('pyproject.toml: not valid TOML') from exc
        return None
    tool = data.get('tool', {})
    table = tool.get('auditme') if isinstance(tool, dict) else None
    if table is None:
        return None
    where = 'pyproject.toml [tool.auditme]'
    if not isinstance(table, dict):
        raise RootsError(f'{where}: must be a table')
    unknown_table_keys = sorted(set(table) - {'roots'})
    if unknown_table_keys:
        raise RootsError(f'{where}: unknown key {unknown_table_keys[0]!r}')
    entries = table.get('roots', [])
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise RootsError(f'{where}: roots must be a list of tables')
    roots: list[tuple[pathlib.Path, str]] = []
    for entry in entries:
        unknown = sorted(set(entry) - {'path', 'modules'})
        if unknown:
            raise RootsError(f'{where}: unknown key {unknown[0]!r} in a roots entry')
        path = entry.get('path')
        if not isinstance(path, str) or not path:
            raise RootsError(f'{where}: a roots entry has no path')
        mode = entry.get('modules', PACKAGE)
        if mode not in (PACKAGE, TOP_LEVEL):
            raise RootsError(f"{where}: modules must be 'package' or 'top-level', not {mode!r}")
        root = scope / path
        if not root.is_dir():
            raise RootsError(f'declared root {path} not found')
        if not py_files(root, mode):
            raise RootsError(f'declared root {path} holds no .py file')
        roots.append((root, mode))
    for i, (a, a_mode) in enumerate(roots):
        for b, b_mode in roots[i + 1 :]:
            nested = (a_mode == PACKAGE and (path_inside(b, a) and b_mode in (PACKAGE, TOP_LEVEL))) or (b_mode == PACKAGE and path_inside(a, b))
            if nested:
                raise RootsError(f'declared roots {a.relative_to(scope)} and {b.relative_to(scope)} overlap')
    return roots


def packages_under(src: pathlib.Path) -> list[pathlib.Path]:
    """Every package directory directly under `src/`, sorted.

    Sorted because emission order is part of the output: `CHECKS`' order fixes
    the order within a package, and this fixes the order of the packages.

    Excludes caches and build artefacts, and any directory holding no `.py`
    file anywhere - not a package, and auditing it only slows the run.
    """
    if not src.is_dir():
        return []
    return sorted(
        p
        for p in src.iterdir()
        if p.is_dir() and not p.name.startswith('.') and p.name != '__pycache__' and not p.name.endswith(('.egg-info', '.dist-info')) and any(p.rglob('*.py'))
    )


def loose_src_modules(scope: pathlib.Path) -> list[pathlib.Path]:
    """Every `.py` file directly in `<scope>/src/`, outside any package, sorted.

    Empty when `src/` is absent. Pure apart from reading the directory.
    """
    src = scope / 'src'
    if not src.is_dir():
        return []
    return sorted(p for p in src.glob('*.py') if p.is_file())


def extra_roots(scope: pathlib.Path, names: collections.abc.Sequence[str] | None = None) -> list[pathlib.Path]:
    """Every auditable root outside `src/`, in the order `names` gives them.

    `names` defaults to the current `EXTRA_ROOT_NAMES`, read at call time so the
    driver's `--extra-root` rebinding reaches the checks.

    A name that does not exist under `scope`, or that holds no `.py` file, is
    dropped: `bin/` is a default, not a requirement, and a project without one
    must not fail the sweep. The driver checks the roots it was given by name
    itself, so a typo on the command line is an error there rather than a
    silently empty pass here.
    """
    roots: list[pathlib.Path] = []
    for name in EXTRA_ROOT_NAMES if names is None else names:
        root = scope / name
        if root.is_dir() and any(root.rglob('*.py')):
            roots.append(root)
    return roots


def audit_roots(scope: pathlib.Path) -> list[pathlib.Path]:
    """Every root the sweep passes over: the packages under `src/`, then the extras.

    This is the driver's pass list, and each entry becomes one check's
    `src_root`. A check that instead asks a corpus-wide question - "does
    anything read this name?" - wants every file rather than every root, and
    reads it from `corpus_py_files`, which spans all of `src/` and the same
    extras. Asking that question of a single root answers about a fragment
    while reading like an answer about the whole.
    """
    global ROOT_MODULES
    declared = declared_roots(scope)
    if declared is not None:
        ROOT_MODULES = types.MappingProxyType({root: mode for root, mode in declared})
        return [root for root, _ in declared]
    ROOT_MODULES = types.MappingProxyType({})
    return packages_under(scope / 'src') + extra_roots(scope)


# call resolver


def from_import_bindings(tree: ast.Module, module: str, is_package: bool) -> dict[str, str]:
    """Each name a module's top-level `from ... import` binds, to its dotted target.

    A relative import resolves against the module's own package. Pure.
    """
    package = module if is_package else module.rpartition('.')[0]
    bindings: dict[str, str] = {}
    for statement in tree.body:
        if not isinstance(statement, ast.ImportFrom):
            continue
        if statement.level:
            base = package.rsplit('.', statement.level - 1)[0] if statement.level > 1 else package
            source = f'{base}.{statement.module}' if statement.module else base
        elif statement.module:
            source = statement.module
        else:
            continue
        for alias in statement.names:
            bindings[alias.asname or alias.name] = f'{source}.{alias.name}'
    return bindings


def call_bindings(tree: ast.Module, module: str, is_package: bool) -> dict[str, str]:
    """Every name a module's top-level imports bind, to its dotted target.

    The `from ... import` bindings plus each `import a.b as c`. Pure.
    """
    bindings = from_import_bindings(tree, module, is_package)
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                if alias.asname:
                    bindings[alias.asname] = alias.name
    return bindings


def reexport_aliases(
    from_bindings: collections.abc.Mapping[str, collections.abc.Mapping[str, str]],
    known: collections.abc.Collection[str],
) -> dict[str, str]:
    """Each `module.name` that re-exports a known function, mapped to its target.

    `from_bindings` maps a module to its `from_import_bindings`. A package's
    `__init__.py` (or any module) re-exporting a function makes `pkg.name`
    another path to it. Followed until no alias is added, so a re-export of a
    re-export resolves too. Pure.
    """
    aliases: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        for module, bindings in from_bindings.items():
            for name, target in bindings.items():
                target = aliases.get(target, target)
                alias = f'{module}.{name}'
                if target in known and aliases.get(alias) != target and alias not in known:
                    aliases[alias] = target
                    changed = True
    return aliases


def resolve_call(
    call: ast.Call,
    module: str,
    cls: str | None,
    imported: collections.abc.Mapping[str, str],
    known: collections.abc.Mapping[str, str | None],
    aliases: collections.abc.Mapping[str, str],
    class_methods: bool = False,
) -> str | None:
    """The package function a call reaches, or None when it cannot be told.

    `known` maps the dotted name of every function the package defines to the
    class that owns it (None for a module function). A call resolves when it is
    a method call on `self`, a same-module name, or a dotted or imported name
    reaching a known function, following `aliases` (see `reexport_aliases`).

    `class_methods` also resolves `<ClassName>.<method>(...)` for a class the
    package defines, in the same module or imported by name. It is off by
    default, and then a call that reaches a method other than through `self`
    resolves to None: the `Raises:` drift rule follows only calls whose callee
    is certain, and a classmethod and an instance method called on the class
    look alike. The A4 lister turns it on, because a question listing a
    reachable classmethod is cheap to dismiss and a missed one is not. Pure.
    """
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == 'self' and cls:
        method = f'{module}.{cls}.{func.attr}'
        return method if method in known else None
    if not isinstance(func, (ast.Name, ast.Attribute)):
        return None
    dotted = ast.unparse(func)
    head, _, rest = dotted.partition('.')
    if head in imported:
        dotted = imported[head] + (f'.{rest}' if rest else '')
    elif isinstance(func, ast.Name) or (class_methods and isinstance(func.value, ast.Name)):
        dotted = f'{module}.{dotted}'
    dotted = aliases.get(dotted, dotted)
    if dotted not in known:
        return None
    if known[dotted] is not None and not class_methods:
        return None
    return dotted


# corpus definitions


def corpus_py_files(scope: pathlib.Path, src_root: pathlib.Path) -> list[pathlib.Path]:
    """Every `.py` file the sweep reads, not just the root being swept.

    The driver audits one root per pass, so `src_root` is a single package (or
    a single extra root such as `bin/`). That is the right scope for finding a
    package's own exports, and the wrong scope for finding who reads them: a
    project whose `src/` holds both the library and the test tree has readers
    in a sibling package, invisible to a scan rooted at the library. On one
    project that hid mutable exported dicts whose only cross-module readers were
    in `src/tests/`. A script in `bin/` is a reader on the same argument.

    Falls back to the root being swept when the project has neither a `src/`
    nor an extra root, which only happens when a check is called directly
    rather than by the driver.
    """
    declared = declared_roots(scope)
    if declared is not None:
        return sorted(path for root, mode in declared for path in py_files(root, mode))
    roots = extra_roots(scope)
    src = scope / 'src'
    if src.is_dir():
        roots.insert(0, src)
    if not roots:
        return all_py_files(src_root)
    return sorted(path for root in roots for path in all_py_files(root))


def dotted_read(node: ast.Attribute) -> tuple[str, str] | None:
    """Resolve an attribute chain to the `(module, name)` it reads, or None.

    Two rooted forms count. The ordinary one is a chain of attributes on a
    name - `pkg.evaluation.primary.METRICS_BY_HEAD` reads `METRICS_BY_HEAD`
    from `pkg.evaluation.primary`. The second is the `sys.modules`
    indirection - `sys.modules['pkg.evaluation.primary'].METRICS_BY_HEAD` -
    which is the documented idiom for reaching a module without importing it,
    used to break a package-initialisation ordering cycle. It reads exactly
    what the dotted form reads, so a scan that resolved only the dotted form
    reported a container with many such readers as private. Literal subscripts
    only: a computed key names no module a scan can know.
    """
    parts: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    elif isinstance(cur, ast.Subscript):
        key = sys_modules_key(cur)
        if key is None:
            return None
        parts.append(key)
    else:
        return None
    parts.reverse()
    if len(parts) < 2:
        return None
    return '.'.join(parts[:-1]), parts[-1]


def sys_modules_key(node: ast.Subscript) -> str | None:
    """`sys.modules['pkg.mod']` -> `'pkg.mod'`; any other subscript -> None."""
    target = node.value
    if not (isinstance(target, ast.Attribute) and target.attr == 'modules'):
        return None
    if not (isinstance(target.value, ast.Name) and target.value.id == 'sys'):
        return None
    key = node.slice
    if isinstance(key, ast.Constant) and isinstance(key.value, str):
        return key.value
    return None


def reads_by_module_and_name(
    scope: pathlib.Path,
    src_root: pathlib.Path,
) -> dict[tuple[str, str], list[tuple[pathlib.Path, int]]]:
    """Every `(module, name)` the corpus reads, mapped to where it reads it.

    Both spellings count. `from <module> import NAME` is the one a project
    that permits it writes; a project that mandates full import paths writes
    every read dotted, as `<module>.NAME`, and a scan that saw only the first
    would read a heavily-used export as private.

    The corpus is every root the sweep reads, not the one being swept: a
    reader in a sibling package, or in a script under `bin/`, is a reader.
    """
    reads: dict[tuple[str, str], list[tuple[pathlib.Path, int]]] = collections.defaultdict(list)
    for path in corpus_py_files(scope, src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except SyntaxError, UnicodeDecodeError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                for alias in node.names:
                    reads[(node.module, alias.name)].append((path, node.lineno))
            elif isinstance(node, ast.Attribute):
                read = dotted_read(node)
                if read is not None:
                    reads[read].append((path, node.lineno))
    return reads


def corpus_definitions(
    scope: pathlib.Path,
    src_root: pathlib.Path,
    *,
    classes: bool = False,
) -> dict[str, list[tuple[ast.AST, pathlib.Path]]]:
    """Every MODULE-LEVEL `def` across the whole corpus, keyed by bare name.

    Two deliberate choices, both learned from the first run against a real
    project:

    - **Corpus-wide, not per-root.** The driver audits one root per pass, so
      resolving against `src_root` answers a different question on each pass:
      one project's `write_worklist` resolved to the library function on the
      library's pass and to a test double's method on the `src/tests` one,
      and the spec was reported as drifting from both. A name is ambiguous or
      it is not, and that is a property of the corpus.
    - **Module-level only.** A method that happens to share a module-level
      function's name is not a candidate for the `def` a spec's API block
      documents - it is usually a test double. Including methods made every
      such name ambiguous and silently dropped a real finding.

    With `classes=True` the index also holds each module-level class under
    its name and each method of such a class under its bare name. Only the
    Phase B listers set it: they resolve names a document mentions, which may
    be a class or a method. A file with a syntax error is skipped.
    """
    out: dict[str, list[tuple[ast.AST, pathlib.Path]]] = {}
    for path in corpus_py_files(scope, src_root):
        try:
            tree = ast.parse('\n'.join(source_lines(path)))
        except SyntaxError:
            continue
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.setdefault(node.name, []).append((node, path))
            elif classes and isinstance(node, ast.ClassDef):
                out.setdefault(node.name, []).append((node, path))
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        out.setdefault(member.name, []).append((member, path))
    return out


SIDE_EFFECT_CALL_NAMES = frozenset(
    {
        'copytree',
        'makedirs',
        'mkdir',
        'mkdtemp',
        'mkstemp',
        'remove',
        'rmdir',
        'rmtree',
        'symlink_to',
        'touch',
        'unlink',
        'write_bytes',
        'write_text',
    }
)


def walk_within_scope(node: ast.AST) -> collections.abc.Iterable[ast.AST]:
    """Yield descendants of node without entering a nested function or class.

    ast.walk cannot prune, and a `return None` inside a nested helper belongs
    to that helper, not to the handler being examined.
    """
    stack: list[ast.AST] = list(ast.iter_child_nodes(node))
    while stack:
        current = stack.pop()
        yield current
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(current))


def is_dunder_all_assignment(node: ast.Assign | ast.AnnAssign) -> bool:
    """Return True when `node` assigns to the single target `__all__`."""
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return len(targets) == 1 and isinstance(targets[0], ast.Name) and targets[0].id == '__all__'


def all_names(path: pathlib.Path) -> set[str] | None:
    """The string members of the `__all__` in `path`, or None when it has none."""
    if not path.is_file():
        return None
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except SyntaxError, UnicodeDecodeError:
        return None
    names: set[str] | None = None
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and is_dunder_all_assignment(node):
            names = set() if names is None else names
            if isinstance(node.value, (ast.List, ast.Tuple)):
                names.update(e.value for e in node.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str))
    return names


PRIVACY_ALL = 'all'
PRIVACY_SCRIPT = 'script'
PRIVACY_UNDERSCORE = 'underscore'


def surface_files(module: str, root: pathlib.Path) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    """The files whose `__all__` count for module, and module's own candidate files.

    The first list holds module's own file and every package `__init__.py`
    above it; the second only module's own file (`<part>.py` or a package's
    `__init__.py`). A root declared `top-level` holds its modules directly, so
    a module there is `<root>/<module>.py`. Files that do not exist are kept;
    readers skip them.
    """
    first, *rest = module.split('.')
    files: list[pathlib.Path] = []
    own: list[pathlib.Path] = []
    for src_root in audit_roots(root):
        if ROOT_MODULES.get(src_root) == TOP_LEVEL:
            if not rest:
                files.append(src_root / f'{first}.py')
                own.append(src_root / f'{first}.py')
            continue
        if src_root.name != first:
            continue
        files.append(src_root / '__init__.py')
        current = src_root
        for index, part in enumerate(rest):
            if index == len(rest) - 1:
                files.append(current / f'{part}.py')
                own.append(current / f'{part}.py')
            current = current / part
            files.append(current / '__init__.py')
        own.append(current / '__init__.py')
    return files, own


def is_main_guard(node: ast.stmt) -> bool:
    """True for a top-level `if __name__ == '__main__':`, either way round."""
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare) or len(node.test.ops) != 1:
        return False
    if not isinstance(node.test.ops[0], ast.Eq):
        return False
    sides = [node.test.left, node.test.comparators[0]]
    has_name = any(isinstance(s, ast.Name) and s.id == '__name__' for s in sides)
    has_main = any(isinstance(s, ast.Constant) and s.value == '__main__' for s in sides)
    return has_name and has_main


def script_entry_points(path: pathlib.Path) -> set[str] | None:
    """The names a standalone script's `__main__` guard calls, or None when path is no script.

    A script is a file outside any package (no `__init__.py` beside it) with a
    top-level `if __name__ == '__main__':`; the guard is the positive evidence,
    so a loose module that is only ever imported stays under the underscore
    rule. The entry points are the bare names the guard calls (`main`, also
    inside `sys.exit(main())`).
    """
    if not path.is_file() or path.name == '__init__.py' or (path.parent / '__init__.py').exists():
        return None
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except SyntaxError, UnicodeDecodeError:
        return None
    guards = [node for node in tree.body if is_main_guard(node)]
    if not guards:
        return None
    return {n.func.id for guard in guards for n in ast.walk(guard) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def privacy(qualname: str, module: str, root: pathlib.Path) -> tuple[bool, str]:
    """Whether the function or class qualname in module is private, and the rule that decided.

    The rules, first that applies (decision 1, clarified 2026-11-21):

    - `all`: module's own `__all__` and the `__all__` of every package
      `__init__.py` above it. Public when any of them names qualname's first
      segment; private when at least one has an `__all__` and none names it.
    - `script`: a standalone script (see `script_entry_points`) with no
      `__all__`. Public only when qualname's first segment is a name its
      `__main__` guard calls; every other function is private.
    - `underscore`: where nothing is declared, private when a segment of
      qualname or module starts with an underscore (clarified in 1.2).
    """
    files, own = surface_files(module, root)
    first = qualname.split('.')[0]
    found = [names for names in (all_names(f) for f in files) if names is not None]
    if found:
        return first not in set().union(*found), PRIVACY_ALL
    for path in own:
        entry_points = script_entry_points(path)
        if entry_points is not None:
            return first not in entry_points, PRIVACY_SCRIPT
    segments = qualname.split('.') + module.split('.')
    return any(s.startswith('_') and not (s.startswith('__') and s.endswith('__')) for s in segments), PRIVACY_UNDERSCORE


def is_private(qualname: str, module: str, root: pathlib.Path) -> bool:
    """Whether the function or class qualname in module is private; see `privacy`."""
    return privacy(qualname, module, root)[0]
