import ast
import collections
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import collections.abc
    import pathlib


def empty_container_default(node: ast.Call) -> str | None:
    """Label the empty-container default of a two-argument `.get` call.

    Only literals count. `parsed.get('usage', dict())` has the same defect but
    is not matched: the literal form is what appears in practice, and keeping
    the predicate to one node type keeps it unarguable.
    """
    if not isinstance(node.func, ast.Attribute) or node.func.attr != 'get':
        return None
    if len(node.args) != 2 or node.keywords:
        return None
    default = node.args[1]
    if isinstance(default, ast.Dict) and not default.keys:
        return '{}'
    if isinstance(default, ast.List) and not default.elts:
        return '[]'
    if isinstance(default, ast.Tuple) and not default.elts:
        return '()'
    return None


def is_tomllib_call(node: ast.AST) -> bool:
    """True for a `tomllib.load(...)` or `tomllib.loads(...)` call."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in auditor.api.LOADER_CALLS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == 'tomllib'
    )


def toml_returning_functions(tree: ast.Module) -> set[str]:
    """Names of module-level functions that return a `tomllib` call and nothing else but a dict literal."""
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        values = [sub.value for sub in auditor.api.walk_within_scope(node) if isinstance(sub, ast.Return)]
        if any(value is not None and is_tomllib_call(value) for value in values) and all(
            value is not None and (is_tomllib_call(value) or isinstance(value, ast.Dict)) for value in values
        ):
            names.add(node.name)
    return names


def is_toml_source(node: ast.AST, toml_functions: set[str]) -> bool:
    """A `tomllib` call, or a call to a same-module function that returns one."""
    if is_tomllib_call(node):
        return True
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in toml_functions


def receiver_is_toml_mapping(receiver: ast.expr, scope_node: ast.AST, tree: ast.Module, toml_functions: set[str]) -> bool:
    """Whether the mapping `.get` is called on comes from `tomllib`.

    TOML has no null, so an explicit null cannot arrive in such a mapping. The
    receiver counts when it is a `tomllib` call (or a same-module function
    returning one), a name the scope assigns from one, or a parameter of a
    module-level function that every same-module call passes one.
    """
    if is_toml_source(receiver, toml_functions):
        return True
    if not isinstance(receiver, ast.Name):
        return False
    for stmt in auditor.api.walk_within_scope(scope_node):
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target = stmt.targets[0]
            if isinstance(target, ast.Name) and target.id == receiver.id and is_toml_source(stmt.value, toml_functions):
                return True
    if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef)) and scope_node in tree.body:
        params = [arg.arg for arg in scope_node.args.args]
        if receiver.id not in params:
            return False
        index = params.index(receiver.id)
        passed: list[ast.expr] = []
        for call in ast.walk(tree):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == scope_node.name:
                if index < len(call.args):
                    passed.append(call.args[index])
                else:
                    passed.extend(kw.value for kw in call.keywords if kw.arg == receiver.id)
        return bool(passed) and all(is_toml_source(arg, toml_functions) for arg in passed)
    return False


def name_scopes(tree: ast.AST) -> collections.abc.Iterable[ast.AST]:
    """The module and every function and class body, searched separately.

    `walk_within_scope` prunes at each of these, so a name assigned in one
    scope is never matched against a use in another, and no node is visited
    twice.
    """
    yield tree
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node


def name_is_reguarded(scope_node: ast.AST, name: str) -> bool:
    """True when the scope tests `name` for truth, for None, or for its type.

    `x = parsed.get('usage', {})` followed by `if x is None`, `x = x or {}`,
    `if x and x.get(...)`, or `if not isinstance(x, dict): raise DomainError`
    has already answered the question this check asks, whatever order the
    statements appear in. The `isinstance` form is the cure one project actually
    applied at every site an audit raised, so a predicate that did not
    recognise it would re-report every fix as a defect. Testing the whole scope
    rather than only the statements between assignment and use keeps the
    predicate free of flow analysis, at the cost of missing a guard that runs
    too late - a shape Phase B owns.
    """
    for node in [scope_node, *auditor.api.walk_within_scope(scope_node)]:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'isinstance':
            if node.args and isinstance(node.args[0], ast.Name) and node.args[0].id == name:
                return True
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == name:
            if any(isinstance(op, (ast.Is, ast.IsNot)) for op in node.ops) and any(isinstance(c, ast.Constant) and c.value is None for c in node.comparators):
                return True
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            if isinstance(node.operand, ast.Name) and node.operand.id == name:
                return True
        if isinstance(node, (ast.If, ast.IfExp, ast.While)):
            if isinstance(node.test, ast.Name) and node.test.id == name:
                return True
        if isinstance(node, ast.BoolOp):
            if any(isinstance(v, ast.Name) and v.id == name for v in node.values):
                return True
    return False


def none_hostile_use(scope_node: ast.AST, name: str, assign: ast.Assign) -> str | None:
    """Label the first use of `name` in this scope that a None would break.

    A method call (`name.get(...)`, `name.items()`) raises `AttributeError`;
    iterating raises `TypeError`. Both escape an `except <Domain>Error`
    handler. Subscripting (`name['k']`) breaks identically but is left to
    Phase B: it is also how a caller reads a value it knows is present, so the
    shape does not carry the same "the author wrote a default and thought the
    question was settled" signal.
    """
    within_assign = {id(n) for n in ast.walk(assign)}
    for node in auditor.api.walk_within_scope(scope_node):
        # `ast.comprehension` carries no lineno; treat it as on the assignment's
        # line so a comprehension over the name is not filtered out as "before".
        if id(node) in within_assign or getattr(node, 'lineno', assign.lineno) < assign.lineno:
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            if isinstance(receiver, ast.Name) and receiver.id == name:
                return f'{name}.{node.func.attr}()'
        if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            if isinstance(node.iter, ast.Name) and node.iter.id == name:
                return f'iteration over {name}'
    return None


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `x = d.get(k, {})` whose result is later a method-call receiver.

    `dict.get`'s default fires only for an *absent* key. An explicit `null` in
    the payload returns `None`, so the next `x.get(...)` / `x.items()` raises
    `AttributeError` - not the package's domain error, so a caller's
    `except <Domain>Error` handler misses it and the failure surfaces as a
    traceback from somewhere else entirely. The cure is equally mechanical:
    `d.get(k) or {}`.

    The predicate is syntactic: an `Assign` to a single name whose value is a
    two-argument `.get` call with an empty container literal as the default,
    where that name is later the receiver of an attribute call, or is iterated,
    in the same scope - and where the scope never tests the name for truth, for
    None, or for its type (see `name_is_reguarded`).

    Scope: non-test source only. In a test the payload is a fixture the author
    wrote, so an explicit null cannot arrive unannounced.

    Refinement (2026-11-21): a mapping produced by `tomllib.load` or
    `tomllib.loads` is skipped, because TOML has no null. The receiver counts
    when it is such a call, a call to a same-module function that returns one
    (and otherwise only a dict literal, such as `{}` for an absent file), a name the scope assigns from either, or a parameter of a
    module-level function that every same-module call passes one. See
    `receiver_is_toml_mapping`.

    Deliberately NOT detected - non-goals, not oversights:
      - A scalar default (`0`, `''`). Nothing is called on the result.
      - A non-empty container default. `d.get(k, {'a': 1})` fails the same way,
        but is rare enough that including it would only widen the predicate.
      - Subscripting the result (`x['k']`); see `none_hostile_use`.
    """
    for path in auditor.api.all_py_files(src_root):
        if 'tests' in set(path.parts) or path.name.startswith('conftest'):
            continue
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        toml_functions = toml_returning_functions(tree)
        for scope_node in name_scopes(tree):
            for stmt in auditor.api.walk_within_scope(scope_node):
                if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
                    continue
                target = stmt.targets[0]
                if not isinstance(target, ast.Name) or not isinstance(stmt.value, ast.Call):
                    continue
                default = empty_container_default(stmt.value)
                if default is None:
                    continue
                if isinstance(stmt.value.func, ast.Attribute) and receiver_is_toml_mapping(stmt.value.func.value, scope_node, tree, toml_functions):
                    continue
                if name_is_reguarded(scope_node, target.id):
                    continue
                use = none_hostile_use(scope_node, target.id, stmt)
                if use is None:
                    continue
                accept = auditor.api.accept_reason(lines, stmt.lineno, rule='get-container-default-then-method-call')
                auditor.api.emit(
                    rule='get-container-default-then-method-call',
                    variant=f'default {default} does not fire for an explicit null, then {use}',
                    path=rel,
                    line=stmt.lineno,
                    evidence=lines[stmt.lineno - 1].strip()[:200] if stmt.lineno <= len(lines) else ast.unparse(stmt),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
