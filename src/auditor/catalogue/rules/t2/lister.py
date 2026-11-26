"""The T2 lister: every site the T2 question applies to."""

import ast
import collections
import dataclasses
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import collections.abc
    import pathlib

# The type set and the extra call names below change only with a bump of the
# T2 brief version: a change re-plans every candidate through its hash.
T2_SCALAR_TYPES = frozenset({'Decimal', 'Fraction', 'bool', 'bytes', 'date', 'datetime', 'float', 'int', 'str', 'timedelta'})


T2_CONTAINER_TYPES = frozenset({'Iterable', 'Mapping', 'Optional', 'Sequence', 'Union', 'dict', 'frozenset', 'list', 'set', 'tuple'})


T2_EXTRA_CALL_NAMES = frozenset(
    {'Popen', 'check_call', 'check_output', 'choice', 'input', 'now', 'open', 'print', 'randint', 'randrange', 'shuffle', 'time', 'uniform'}
)


T2_EFFECT_MODULES = frozenset({'random', 'subprocess'})


T2_BRANCHES = (ast.If, ast.IfExp, ast.Match, ast.For, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def short_name(node: ast.AST) -> str | None:
    """The last dotted component of a name or attribute, else None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def root_name(node: ast.AST) -> str | None:
    """The leftmost name of an attribute, subscript or call chain, else None."""
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def is_frozen_dataclass(cls: ast.ClassDef) -> bool:
    """True for a class decorated `dataclass(frozen=True)`."""
    for decorator in cls.decorator_list:
        if isinstance(decorator, ast.Call) and short_name(decorator.func) == 'dataclass':
            if any(keyword.arg == 'frozen' and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in decorator.keywords):
                return True
    return False


def is_well_defined_class(cls: ast.ClassDef, package_types: collections.abc.Mapping[str, ast.ClassDef], checking: set[str]) -> bool:
    """True when cls is an Enum, or a frozen dataclass, NamedTuple or TypedDict of well-defined fields."""
    bases = {short_name(base) for base in cls.bases}
    if bases & auditor.api.T2_ENUM_BASES:
        return True
    if not (bases & {'NamedTuple', 'TypedDict'} or is_frozen_dataclass(cls)):
        return False
    checking = checking | {cls.name}
    for field in cls.body:
        if isinstance(field, ast.AnnAssign) and short_name(field.annotation) != 'ClassVar':
            if not is_well_defined_type(field.annotation, package_types, checking):
                return False
    return True


def is_well_defined_type(annotation: ast.expr, package_types: collections.abc.Mapping[str, ast.ClassDef], checking: set[str]) -> bool:
    """True when annotation is built only from the T2 type set."""
    if isinstance(annotation, ast.Constant):
        if annotation.value is None or annotation.value is Ellipsis:
            return True
        if isinstance(annotation.value, str):
            try:
                inner = ast.parse(annotation.value, mode='eval').body
            except SyntaxError:
                return False
            return is_well_defined_type(inner, package_types, checking)
        return False
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return is_well_defined_type(annotation.left, package_types, checking) and is_well_defined_type(annotation.right, package_types, checking)
    if isinstance(annotation, ast.Subscript):
        head = short_name(annotation.value)
        if head == 'Literal':
            return True
        if head not in T2_CONTAINER_TYPES:
            return False
        arguments = annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
        return all(is_well_defined_type(argument, package_types, checking) for argument in arguments)
    name = short_name(annotation)
    if name is None:
        return False
    if name in T2_SCALAR_TYPES:
        return True
    cls = package_types.get(name)
    if cls is None:
        return False
    if name in checking:
        return True
    return is_well_defined_class(cls, package_types, checking)


def is_t2_candidate(node: ast.FunctionDef, package_types: collections.abc.Mapping[str, ast.ClassDef]) -> bool:
    """True when node is pure over well-defined types and has logic a property can test."""
    if not isinstance(node, ast.FunctionDef):
        return False
    arguments = node.args
    decorators = {short_name(decorator) for decorator in node.decorator_list}
    parameters = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    if arguments.vararg is not None:
        parameters.append(arguments.vararg)
    if arguments.kwarg is not None:
        parameters.append(arguments.kwarg)
    if not parameters or 'classmethod' in decorators:
        return False
    if parameters[0].arg in {'self', 'cls'} and 'staticmethod' not in decorators:
        return False
    returns = node.returns
    if returns is None or (isinstance(returns, ast.Constant) and returns.value is None):
        return False
    annotations = [parameter.annotation for parameter in parameters]
    if any(annotation is None for annotation in annotations):
        return False
    if not all(is_well_defined_type(annotation, package_types, set()) for annotation in [*annotations, returns] if annotation is not None):
        return False
    names = {parameter.arg for parameter in parameters}
    effects = auditor.api.SIDE_EFFECT_CALL_NAMES | T2_EXTRA_CALL_NAMES
    own = list(auditor.api.walk_within_scope(node))
    for inner in own:
        if isinstance(inner, (ast.Yield, ast.YieldFrom, ast.Global, ast.Nonlocal, ast.Await)):
            return False
        if isinstance(inner, ast.Call) and (short_name(inner.func) in effects or root_name(inner.func) in T2_EFFECT_MODULES):
            return False
        targets: list[ast.expr] = []
        if isinstance(inner, ast.Assign):
            targets = inner.targets
        elif isinstance(inner, (ast.AugAssign, ast.AnnAssign)):
            targets = [inner.target]
        elif isinstance(inner, ast.Delete):
            targets = inner.targets
        for target in targets:
            for part in ast.walk(target):
                if isinstance(part, (ast.Attribute, ast.Subscript)) and root_name(part) in names:
                    return False
    return any(isinstance(inner, T2_BRANCHES) for inner in own)


# auditme: accept[literal-duplication] the test states the expected pairs independently of the lister
T2_INVERSES = (('parse', 'format'), ('encode', 'decode'), ('to', 'from'), ('dumps', 'loads'))


def inverse_names(name: str) -> set[str]:
    """The names that invert `name`: `parse_x`/`format_x`, `encode`/`decode`, `to_x`/`from_x`, `dumps`/`loads`."""
    head, separator, rest = name.partition('_')
    found: set[str] = set()
    for first, second in T2_INVERSES:
        if head == first:
            found.add(f'{second}{separator}{rest}')
        elif head == second:
            found.add(f'{first}{separator}{rest}')
    return found


def referenced_types(annotations: list[ast.expr], package_types: collections.abc.Mapping[str, ast.ClassDef]) -> set[str]:
    """The package class names the annotations name, directly or through a class's fields."""
    found: set[str] = set()
    pending = [name for annotation in annotations for name in auditor.api.annotation_names(annotation)]
    while pending:
        name = pending.pop()
        if name in found or name not in package_types:
            continue
        found.add(name)
        for field in package_types[name].body:
            if isinstance(field, ast.AnnAssign):
                pending.extend(auditor.api.annotation_names(field.annotation))
    return found


# auditme: accept[literal-duplication] each question declares its own kinds; equal values are coincidence
def list_candidates(scope: pathlib.Path, depth: int = auditor.api.DEFAULT_DEPTH) -> list[auditor.api.Candidate]:
    """List every function `is_t2_candidate` accepts, with its types, inverse pairs and tests.

    The hash is a sha256 over its source, each `types` class's source in id
    order, then each `test_files` file's text in path order, NUL-separated.

    Raises:
        PhaseBError: a test file or audited source file does not parse.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    index = auditor.api.load_test_index(scope)
    refs = index.refs(depth)
    hidden = {module: auditor.api.type_checking_linenos(file.tree) for module, file in index.sources.items()}
    class_sites: dict[str, tuple[auditor.api.ParsedFile, ast.ClassDef]] = {}
    for module in sorted(index.sources):
        file = index.sources[module]
        for node in file.tree.body:
            if isinstance(node, ast.ClassDef):
                class_sites[node.name] = (file, node)
    package_types = {name: cls for name, (_, cls) in class_sites.items()}
    accepted = [
        site
        for site in index.sites.values()
        if isinstance(site.node, ast.FunctionDef)
        and (site.cls is None or any(short_name(decorator) == 'staticmethod' for decorator in site.node.decorator_list))
        and not auditor.api.is_overload(site.node)
        and site.node.lineno not in hidden[site.module]
        and is_t2_candidate(site.node, package_types)
    ]
    by_name: dict[str, list[str]] = {}
    for site in accepted:
        by_name.setdefault(site.node.name, []).append(site.id)
    module_text: dict[str, str] = {}
    found: list[auditor.api.Candidate] = []
    for site in accepted:
        node = site.node
        arguments = node.args
        parameters = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
        if arguments.vararg is not None:
            parameters.append(arguments.vararg)
        if arguments.kwarg is not None:
            parameters.append(arguments.kwarg)
        annotated = [(parameter.arg, parameter.annotation) for parameter in parameters if parameter.annotation is not None]
        returns = node.returns
        if returns is None:
            continue
        text = module_text.setdefault(site.path, '\n'.join(site.lines))
        types: list[dict[str, str | int]] = []
        class_sources: list[tuple[str, bytes]] = []
        for name in referenced_types([*(annotation for _, annotation in annotated), returns], package_types):
            file, cls = class_sites[name]
            start = min([cls.lineno, *(decorator.lineno for decorator in cls.decorator_list)])
            end = cls.end_lineno or cls.lineno
            type_id = f'{file.rel}::{cls.name}'
            types.append({'id': type_id, 'path': file.rel, 'start': start, 'end': end})
            class_sources.append((type_id, '\n'.join(file.lines[start - 1 : end]).encode('utf-8')))
        types.sort(key=lambda entry: str(entry['id']))
        class_sources.sort()
        test_files = index.test_files(site.id, depth)
        parts = [site.source.encode('utf-8'), *(source for _, source in class_sources), *auditor.api.read_test_files(scope, test_files)]
        pairs = sorted(other for inverse in inverse_names(node.name) for other in by_name.get(inverse, ()))
        found.append(
            auditor.api.site_candidate(
                'T2',
                site,
                {
                    'params': [
                        {'name': name, 'annotation': ast.get_source_segment(text, annotation) or ast.unparse(annotation)} for name, annotation in annotated
                    ],
                    'returns': ast.get_source_segment(text, returns) or ast.unparse(returns),
                    'types': types,
                    'pairs': pairs,
                    'tests': [dataclasses.asdict(ref) for ref in refs.get(site.id, ())],
                    'test_files': test_files,
                },
                auditor.api.digest(parts),
            )
        )
    return found
