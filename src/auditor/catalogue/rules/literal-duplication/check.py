import ast
import collections
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


SET_CALL_NAMES = frozenset({'frozenset', 'set'})


def is_pytest_param(node: ast.AST) -> bool:
    """True for a call to `pytest.param`."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'param'
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == 'pytest'
    )


def test_expectation_nodes(tree: ast.AST) -> set[int]:
    """The ids of every node inside an `assert` statement or a `pytest.param(...)` call."""
    inside: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) or is_pytest_param(node):
            inside.update(id(child) for child in ast.walk(node))
    return inside


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag the same string-literal collection written in two or more places."""
    bucket: dict[tuple[typing.Any, ...], set[tuple[str, int, str]]] = collections.defaultdict(set)
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        # Find frozenset(...) / set(...) call nodes so we can skip their inner ast.Set/Tuple child
        skip_inner_nodes: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in SET_CALL_NAMES:
                if node.args and isinstance(node.args[0], (ast.Set, ast.Tuple, ast.List)):
                    skip_inner_nodes.add(id(node.args[0]))
        in_test = auditor.api.is_test_relpath(rel)
        expectation_nodes = test_expectation_nodes(tree) if in_test else set()
        for node in ast.walk(tree):
            if id(node) in skip_inner_nodes or id(node) in expectation_nodes:
                continue
            members = None
            kind = None
            if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
                members = node.elts
                kind = type(node).__name__
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in SET_CALL_NAMES:
                    if node.args and isinstance(node.args[0], (ast.Set, ast.Tuple, ast.List)):
                        members = node.args[0].elts
                        kind = 'frozenset'
            if not members or (in_test and len(members) == 1):
                continue
            consts: list[str] = []
            ok = True
            for m in members:
                if isinstance(m, ast.Constant) and isinstance(m.value, str):
                    consts.append(m.value)
                else:
                    ok = False
                    break
            if not ok or not consts:
                continue
            if kind in {'Set', 'frozenset'}:
                key = ('unordered', tuple(sorted(consts)))
            else:
                key = ('ordered', tuple(consts))
            bucket[key].add((rel, node.lineno, repr(tuple(consts))))
    for key, hits in bucket.items():
        if len(hits) < 2:
            continue
        # A single file can legitimately have two copies at different linenos;
        # that's still a finding. But if the same (path, line) is hit twice,
        # dedup via the set.
        for rel, lineno, evidence in sorted(hits):
            full = scope / rel
            full_lines = auditor.api.source_lines(full)
            accept = auditor.api.accept_reason(full_lines, lineno, rule='literal-duplication')
            auditor.api.emit(
                related=[h[0] for h in hits],
                rule='literal-duplication',
                variant=f'identical {key[0]} literal across {len(hits)} locations',
                path=rel,
                line=lineno,
                evidence=evidence[:200],
                accepted=bool(accept),
                accepted_reason=accept,
            )
