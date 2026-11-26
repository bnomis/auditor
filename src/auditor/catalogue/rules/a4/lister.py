"""The A4 lister: every site the A4 question applies to."""

import ast
import builtins
import collections
import hashlib
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import collections.abc
    import pathlib


def is_stub(node: auditor.api.FunctionNode) -> bool:
    """True for an abstract or protocol body (D2): `...`, `pass`, a docstring alone or `raise NotImplementedError`."""
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    if not body:
        return True
    if len(body) != 1:
        return False
    only = body[0]
    if isinstance(only, ast.Pass):
        return True
    if isinstance(only, ast.Expr) and isinstance(only.value, ast.Constant) and only.value.value is Ellipsis:
        return True
    if isinstance(only, ast.Raise) and only.exc is not None:
        raised = only.exc.func if isinstance(only.exc, ast.Call) else only.exc
        return isinstance(raised, ast.Name) and raised.id == 'NotImplementedError'
    return False


def is_builtin_call(
    call: ast.Call, site: auditor.api.Site, imported: collections.abc.Mapping[str, str], known: collections.abc.Mapping[str, str | None]
) -> bool:
    """True for a bare-name call to a builtin that the module neither imports nor defines."""
    func = call.func
    return isinstance(func, ast.Name) and hasattr(builtins, func.id) and func.id not in imported and f'{site.module}.{func.id}' not in known


def root_sites(scope: pathlib.Path, src_root: pathlib.Path) -> tuple[list[auditor.api.Site], dict[str, ast.Module], dict[str, bool]]:
    """Every top-level function and class method under one audited root, with each module's tree and package flag."""
    sites: list[auditor.api.Site] = []
    trees: dict[str, ast.Module] = {}
    is_package: dict[str, bool] = {}
    for path in auditor.api.all_py_files(src_root):
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        module = auditor.api.module_dotted(path, src_root)
        trees[module] = tree
        is_package[module] = path.name == '__init__.py'
        sites.extend(auditor.api.module_sites(module, tree, auditor.api.relpath(path, scope), lines))
    return sites, trees, is_package


def root_candidates(scope: pathlib.Path, src_root: pathlib.Path, depth: int) -> list[auditor.api.Candidate]:
    """The A4 candidates of one audited root."""
    sites, trees, is_package = root_sites(scope, src_root)
    by_name = {site.qualname: site for site in sites}
    known = {site.qualname: site.cls for site in sites}
    bindings = {module: auditor.api.call_bindings(tree, module, is_package[module]) for module, tree in trees.items()}
    aliases = auditor.api.reexport_aliases(
        {module: auditor.api.from_import_bindings(tree, module, is_package[module]) for module, tree in trees.items()},
        known,
    )

    resolved_calls = {
        site.qualname: [
            (call, auditor.api.resolve_call(call, site.module, site.cls, bindings[site.module], known, aliases, class_methods=True))
            for call in ast.walk(site.node)
            if isinstance(call, ast.Call)
        ]
        for site in sites
    }

    def calls_of(site: auditor.api.Site) -> list[tuple[ast.Call, str | None]]:
        return resolved_calls[site.qualname]

    direct = {name: sorted({callee for _, callee in calls if callee and callee != name}) for name, calls in resolved_calls.items()}

    def reach(site: auditor.api.Site) -> list[auditor.api.Site]:
        seen = {site.qualname}
        frontier = [site.qualname]
        for _ in range(depth):
            frontier = [callee for name in frontier for callee in direct[name] if callee not in seen]
            seen.update(frontier)
        return sorted((by_name[name] for name in seen - {site.qualname}), key=lambda callee: callee.id)

    found: list[auditor.api.Candidate] = []
    for site in sites:
        doc = ast.get_docstring(site.node) or ''
        if 'Raises:' not in doc or is_stub(site.node) or not auditor.api.raises_section_names(doc):
            continue
        callees = reach(site)
        unresolved = [
            {'at': f'{site.path}:{call.lineno}', 'text': ast.unparse(call)}
            for call, callee in calls_of(site)
            if callee is None and not is_builtin_call(call, site, bindings[site.module], known)
        ]
        digest = hashlib.sha256('\0'.join([site.source, *(callee.source for callee in callees)]).encode('utf-8')).hexdigest()
        found.append(
            auditor.api.site_candidate(
                'A4',
                site,
                {
                    'raises': doc[doc.index('Raises:') :],
                    'callees': [{'id': callee.id, 'path': callee.path, 'start': callee.start, 'end': callee.end} for callee in callees],
                    'unresolved': unresolved,
                },
                digest,
            )
        )
    return found


def list_candidates(scope: pathlib.Path, depth: int = auditor.api.DEFAULT_DEPTH) -> list[auditor.api.Candidate]:
    """List every function or method with a `Raises:` section under the audited roots, minus D2's stubs.

    Each carries its section, its resolved callees to `depth` (resolving
    `<ClassName>.<method>(...)` too), its unresolved calls, and a sha256 over
    its source then its callees' source in id order, NUL-separated.

    Raises:
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    roots, _ = auditor.api.cached_roots(scope)
    return [candidate for src_root in roots for candidate in root_candidates(scope, src_root, depth)]
