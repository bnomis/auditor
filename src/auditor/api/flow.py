"""Helpers that read the shape of an AST node, for rules to share."""

import ast
import types
import typing

import auditor.core
import auditor.dispatch

if typing.TYPE_CHECKING:
    import collections.abc

BARE_GENERIC_NAMES = auditor.core.BARE_GENERIC_NAMES  # auditme: accept[reexport-in-non-init] the API publishes the core helper under this name
is_dunder_all_assignment = auditor.core.is_dunder_all_assignment  # auditme: accept[reexport-in-non-init] the API publishes the core helper under this name


def leading_underscore_names(target: ast.AST) -> list[tuple[str, int]]:
    """Return `(name, lineno)` for every `_foo` Store-name inside a
    tuple-unpack target (or a bare `_foo`). Skips bare `_`."""
    out: list[tuple[str, int]] = []

    def walk(n: ast.AST) -> None:
        if isinstance(n, ast.Name):
            if n.id.startswith('_') and n.id != '_' and not n.id.startswith('__'):
                out.append((n.id, n.lineno))
        elif isinstance(n, (ast.Tuple, ast.List)):
            for elt in n.elts:
                walk(elt)
        elif isinstance(n, ast.Starred):
            walk(n.value)

    walk(target)
    return out


SIDE_EFFECT_CALL_NAMES = auditor.core.SIDE_EFFECT_CALL_NAMES  # auditme: accept[reexport-in-non-init] the API publishes the core helper under this name
reads_by_module_and_name = auditor.core.reads_by_module_and_name  # auditme: accept[reexport-in-non-init] the API publishes the core helper under this name
IfChain = auditor.dispatch.IfChain  # auditme: accept[reexport-in-non-init] the API publishes the runner's chain walker under this name
assert_never_findings = (
    auditor.dispatch.assert_never_findings
)  # auditme: accept[reexport-in-non-init] the API publishes the runner's site finder under this name
extract_string_eq_var = auditor.dispatch.extract_string_eq_var  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
if_chain = auditor.dispatch.if_chain  # auditme: accept[reexport-in-non-init] the API publishes the runner's chain walker under this name


MUTABLE_VALUE_SHAPES: collections.abc.Mapping[type[ast.expr], tuple[str, str]] = types.MappingProxyType(
    {
        ast.Dict: ('dict literal', 'types.MappingProxyType(...)'),
        ast.DictComp: ('dict comprehension', 'types.MappingProxyType(...)'),
        ast.List: ('list literal', 'tuple(...)'),
        ast.ListComp: ('list comprehension', 'tuple(...)'),
        ast.Set: ('set literal', 'frozenset(...)'),
        ast.SetComp: ('set comprehension', 'frozenset(...)'),
    }
)


# The builtin constructors that build the same three mutable containers. A call
# to one states its type in the assignment as a literal does, so it is the same
# finding; any other call (`get_defaults()`) states none and stays out. Ruled on
# 2026-10-31 on an audit's request; see `requests.md`.
MUTABLE_CONSTRUCTORS: collections.abc.Mapping[str, tuple[str, str]] = types.MappingProxyType(
    {
        'dict': ('dict constructor call', 'types.MappingProxyType(...)'),
        'list': ('list constructor call', 'tuple(...)'),
        'set': ('set constructor call', 'frozenset(...)'),
    }
)


def mutable_value_shape(value: ast.expr) -> tuple[str, str] | None:
    """The `(shape, required wrap)` of a mutable container value, or None.

    A literal or comprehension of a dict, list or set, or a call to the bare
    builtin `dict`, `list` or `set`. Pure.
    """
    shape = MUTABLE_VALUE_SHAPES.get(type(value))
    if shape is not None:
        return shape
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        return MUTABLE_CONSTRUCTORS.get(value.func.id)
    return None


def module_level_binding(node: ast.stmt) -> tuple[str | None, ast.expr | None]:
    """The `(name, value)` a top-level statement binds, if it binds one name."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id, node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
        return node.target.id, node.value
    return None, None


__all__ = [
    'BARE_GENERIC_NAMES',
    'MUTABLE_CONSTRUCTORS',
    'MUTABLE_VALUE_SHAPES',
    'SIDE_EFFECT_CALL_NAMES',
    'IfChain',
    'assert_never_findings',
    'extract_string_eq_var',
    'if_chain',
    'is_dunder_all_assignment',
    'leading_underscore_names',
    'module_level_binding',
    'mutable_value_shape',
    'reads_by_module_and_name',
]
