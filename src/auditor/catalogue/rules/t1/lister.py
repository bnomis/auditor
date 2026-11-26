"""The T1 lister: every site the T1 question applies to."""

import ast
import dataclasses
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def self_attribute(node: ast.AST) -> str | None:
    """The attribute name when node is `self.<attr>`, else None."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'self':
        return node.attr
    return None


def tested_attributes(method: auditor.api.FunctionNode) -> set[str]:
    """The `self.<attr>` names method tests in an `if`, a `match` subject or a comparison."""
    tested: set[str] = set()
    for node in auditor.api.walk_within_scope(method):
        if isinstance(node, ast.If):
            expressions: list[ast.AST] = [node.test]
        elif isinstance(node, ast.Match):
            expressions = [node.subject]
        elif isinstance(node, ast.Compare):
            expressions = [node]
        else:
            continue
        for expression in expressions:
            for inner in ast.walk(expression):
                name = self_attribute(inner)
                if name is not None:
                    tested.add(name)
    return tested


def assigned_attributes(node: auditor.api.FunctionNode) -> set[str]:
    """The `self.<attr>` names node assigns in its own body."""
    assigned: set[str] = set()
    for inner in auditor.api.walk_within_scope(node):
        targets: list[ast.expr] = []
        if isinstance(inner, ast.Assign):
            targets = inner.targets
        elif isinstance(inner, (ast.AugAssign, ast.AnnAssign)):
            targets = [inner.target]
        for target in targets:
            for part in ast.walk(target):
                name = self_attribute(part)
                if name is not None:
                    assigned.add(name)
    return assigned


def t1_reasons(node: ast.FunctionDef | ast.AsyncFunctionDef, cls: ast.ClassDef | None) -> list[str]:
    """Why node is a T1 candidate: any of 'if', 'try', 'match', 'state'; empty if not."""
    own = list(auditor.api.walk_within_scope(node))
    reasons: list[str] = []
    if any(isinstance(inner, ast.If) for inner in own):
        reasons.append('if')
    if any(isinstance(inner, (ast.Try, ast.TryStar)) and inner.handlers for inner in own):
        reasons.append('try')
    if any(isinstance(inner, ast.Match) for inner in own):
        reasons.append('match')
    if cls is not None:
        assigned = assigned_attributes(node)
        if assigned:
            others = (method for method in cls.body if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method is not node)
            if any(assigned & tested_attributes(method) for method in others):
                reasons.append('state')
    return reasons


# auditme: accept[literal-duplication] each question declares its own kinds; equal values are coincidence
def list_candidates(scope: pathlib.Path, depth: int = auditor.api.DEFAULT_DEPTH) -> list[auditor.api.Candidate]:
    """List every function or method whose own body branches, with the tests that reach it.

    Each carries its reasons, its direct and caller tests, its callers to
    `depth`, its `test_files`, whether it is private and the `privacy` rule
    that decided it (`auditor.core.privacy`). The hash is a sha256
    over its source then each `test_files` file's text in path order,
    NUL-separated. `@typing.overload` stubs and defs under `if TYPE_CHECKING:`
    are left out.

    Raises:
        PhaseBError: a test file or audited source file does not parse.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    index = auditor.api.load_test_index(scope)
    refs = index.refs(depth)
    hidden = {module: auditor.api.type_checking_linenos(file.tree) for module, file in index.sources.items()}
    classes = {(module, node.name): node for module, file in index.sources.items() for node in file.tree.body if isinstance(node, ast.ClassDef)}
    found: list[auditor.api.Candidate] = []
    for site in index.sites.values():
        if auditor.api.is_overload(site.node) or site.node.lineno in hidden[site.module]:
            continue
        reasons = t1_reasons(site.node, classes.get((site.module, site.cls)) if site.cls else None)
        if not reasons:
            continue
        test_files = index.test_files(site.id, depth)
        parts = [site.source.encode('utf-8'), *auditor.api.read_test_files(scope, test_files)]
        private, rule = auditor.api.privacy(site.qualname.removeprefix(f'{site.module}.'), site.module, scope)
        found.append(
            auditor.api.site_candidate(
                'T1',
                site,
                {
                    'reasons': reasons,
                    'tests': [dataclasses.asdict(ref) for ref in refs.get(site.id, ())],
                    'callers': index.callers(site.id, depth),
                    'test_files': test_files,
                    'private': private,
                    'privacy': rule,
                },
                auditor.api.digest(parts),
            )
        )
    return found
