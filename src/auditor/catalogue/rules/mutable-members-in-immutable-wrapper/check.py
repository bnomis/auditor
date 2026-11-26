import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


# The wrappers A20 accepts as making an exported container immutable. Every one
# of them is shallow: it freezes the container it is given and nothing inside
# it, which is what `check_mutable_members_in_immutable_wrapper` is for.
IMMUTABLE_WRAPPERS = frozenset({'MappingProxyType', 'frozenset', 'tuple'})


MEMBER_CONTAINERS = (ast.Dict, ast.DictComp, ast.GeneratorExp, ast.List, ast.ListComp, ast.Set, ast.SetComp, ast.Tuple)


def wrapped_literal(value: ast.expr) -> tuple[str, ast.expr] | None:
    """`types.MappingProxyType({...})` -> `('MappingProxyType', <the dict>)`.

    Only a single literal or comprehension argument counts, for the same
    reason A20 stops at literals: `tuple(build())` states no members to read.
    """
    if not isinstance(value, ast.Call) or len(value.args) != 1 or value.keywords:
        return None
    func = value.func
    if isinstance(func, ast.Attribute):
        wrapper = func.attr
    elif isinstance(func, ast.Name):
        wrapper = func.id
    else:
        return None
    if wrapper not in IMMUTABLE_WRAPPERS:
        return None
    argument = value.args[0]
    if not isinstance(argument, MEMBER_CONTAINERS):
        return None
    return wrapper, argument


def mutable_members(literal: ast.expr, frozen_by_name: dict[str, bool]) -> list[tuple[int, str]]:
    """Every mutable member of a literal, as `(line, what it is)`, deduped.

    Descends through a nested tuple literal, which is immutable itself and
    holds whatever it is given: a tuple of lists inside a proxy is the same
    hazard one level down. A nested `set` or `list` literal is not descended
    into - it is already the hazard, and is reported as itself.
    """
    hazards: dict[str, int] = {}
    for member in member_nodes(literal):
        if isinstance(member, ast.Tuple):
            for line, what in mutable_members(member, frozen_by_name):
                hazards.setdefault(what, line)
            continue
        what = member_hazard(member, frozen_by_name)
        if what is not None:
            hazards.setdefault(what, getattr(member, 'lineno', 0))
    return sorted((line, what) for what, line in hazards.items())


def member_nodes(literal: ast.expr) -> list[ast.expr]:
    """The member expressions of a literal or comprehension.

    A comprehension has exactly one member expression, evaluated per item, so
    a mutable one is a hazard repeated rather than a different shape.
    """
    if isinstance(literal, ast.Dict):
        return [value for value in literal.values if value is not None]
    if isinstance(literal, ast.DictComp):
        return [literal.value]
    if isinstance(literal, (ast.List, ast.Set, ast.Tuple)):
        return list(literal.elts)
    if isinstance(literal, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
        return [literal.elt]
    return []


def member_hazard(member: ast.expr, frozen_by_name: dict[str, bool]) -> str | None:
    """What makes this member mutable, phrased for the variant line, or None."""
    shape = auditor.api.MUTABLE_VALUE_SHAPES.get(type(member))
    if shape is not None:
        return f'a {shape[0]}'
    if isinstance(member, ast.Call):
        called = member.func
        name = called.attr if isinstance(called, ast.Attribute) else called.id if isinstance(called, ast.Name) else None
        if name is not None and frozen_by_name.get(name) is False:
            return f'a non-frozen dataclass `{name}`'
    return None


def hazard_summary(hazards: list[tuple[int, str]]) -> str:
    return ', '.join(f'{what} at line {line}' for line, what in hazards)


def dataclass_frozen_by_name(scope: pathlib.Path, src_root: pathlib.Path) -> dict[str, bool]:
    """Every dataclass the corpus defines, mapped to whether it is frozen.

    A name defined more than once is frozen if any definition is: the scan
    resolves no imports, so the alternative is to call a frozen class mutable
    on the strength of a same-named class somewhere else in the tree.
    """
    return auditor.api.corpus_index('frozen', scope, src_root, lambda: index_frozen_classes(scope, src_root))


def index_frozen_classes(scope: pathlib.Path, src_root: pathlib.Path) -> dict[str, bool]:
    """The index `dataclass_frozen_by_name` shares: one scan of the corpus."""
    frozen_by_name: dict[str, bool] = {}
    for path in auditor.api.corpus_py_files(scope, src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            frozen = [f for f in (dataclass_decorator(d) for d in node.decorator_list) if f is not None]
            if not frozen:
                continue
            frozen_by_name[node.name] = frozen_by_name.get(node.name, False) or any(frozen)
    return frozen_by_name


def dataclass_decorator(decorator: ast.expr) -> bool | None:
    """True/False if this decorator is `@dataclass`, saying whether it freezes."""
    call = decorator if isinstance(decorator, ast.Call) else None
    target = call.func if call is not None else decorator
    if isinstance(target, ast.Attribute):
        name = target.attr
    elif isinstance(target, ast.Name):
        name = target.id
    else:
        return None
    if name != 'dataclass':
        return None
    if call is None:
        return False
    for keyword in call.keywords:
        if keyword.arg == 'frozen':
            return isinstance(keyword.value, ast.Constant) and keyword.value.value is True
    return False


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag an externally-read module-level container that is wrapped in an
    immutable wrapper but holds mutable members.

    Signal:
      - Module-level `NAME = <wrapper>(<literal or comprehension>)`, where
        `<wrapper>` is `types.MappingProxyType`, `frozenset` or `tuple` - the
        three A20 accepts.
      - `NAME` is read from another file (the same predicate, and the same
        scan, as `mutable-module-level-exported`).
      - A member of the wrapped literal is itself mutable: a `dict`/`list`/
        `set` literal or comprehension, or an instance of a dataclass this
        corpus defines without `frozen=True`.

    Every one of those wrappers is shallow. `types.MappingProxyType({'a': []})`
    passes `mutable-module-level-exported` and still hands every caller the
    same live `list`; on one project a proxy's values were the very objects a
    `get_defaults()` helper returned, so `defaults[k].append(...)` mutated the
    process-wide default seen through both names. A project that has adopted
    A20 reads the passing check as a guarantee, which is what makes this shape
    worth its own rule rather than a footnote to that one: it is a guard that
    fails open.

    Deliberately syntactic. A member whose mutability is decided elsewhere -
    `MappingProxyType({'a': build()})` - is not covered, for the reason the
    `Call` case is rejected for A20: the assignment does not state the type.
    The dataclass carve-in is not an exception to that; a dataclass's
    mutability is stated by its own decorator, in this corpus, and read there.
    """
    frozen_by_name = dataclass_frozen_by_name(scope, src_root)
    candidates: list[tuple[pathlib.Path, ast.stmt, str, str, list[tuple[int, str]]]] = []
    module_name_of: dict[pathlib.Path, str] = {}
    for path in auditor.api.all_py_files(src_root):
        module_name_of[path] = auditor.api.module_dotted(path, src_root)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            name, value = auditor.api.module_level_binding(node)
            if name is None or value is None or name.startswith('_'):
                continue
            wrapped = wrapped_literal(value)
            if wrapped is None:
                continue
            wrapper, literal = wrapped
            hazards = mutable_members(literal, frozen_by_name)
            if hazards:
                candidates.append((path, node, name, wrapper, hazards))

    if not candidates:
        return

    imports_of = auditor.api.reads_by_module_and_name(scope, src_root)
    for path, assign_node, name, wrapper, hazards in candidates:
        # auditme: accept[get-container-default-then-method-call] an internal mapping that never holds `None`
        readers = imports_of.get((module_name_of[path], name), [])
        if not [(p, ln) for p, ln in readers if p != path]:
            continue
        lines = auditor.api.source_lines(path)
        accept = auditor.api.accept_reason(lines, assign_node.lineno, rule='mutable-members-in-immutable-wrapper')
        auditor.api.emit(
            rule='mutable-members-in-immutable-wrapper',
            variant=(f'{name} is wrapped in {wrapper}, which is shallow; still mutable through it: {hazard_summary(hazards)}'),
            path=auditor.api.relpath(path, scope),
            line=assign_node.lineno,
            evidence=(lines[assign_node.lineno - 1].strip()[:200] if assign_node.lineno <= len(lines) else ''),
            accepted=bool(accept),
            accepted_reason=accept,
        )
