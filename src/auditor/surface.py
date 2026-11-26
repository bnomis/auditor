"""Site finders for the import-surface checks.

The `empty-init-while-siblings-export` and `migration-shim-consumer` rules
report what these find, and the Phase B A17 lister reads the same sites
without running a rule. Both read the finders from here, so that the lister
needs no check function. The rules reach them through the helper API.
"""

import ast
import collections
import typing

import auditor.core

if typing.TYPE_CHECKING:
    import pathlib

MIN_SIBLING_SURFACE = 5


def module_dotted_name(path: pathlib.Path, src_root: pathlib.Path) -> str:
    """The dotted name of a file, rooted at the name of `src_root`."""
    package_root_name = src_root.name
    rel_parts = path.relative_to(src_root).parts
    if rel_parts[-1] == '__init__.py':
        return package_root_name + '.' + '.'.join(rel_parts[:-1]) if len(rel_parts) > 1 else package_root_name
    return package_root_name + '.' + '.'.join(rel_parts)[:-3]


def empty_init_sites(src_root: pathlib.Path) -> list[tuple[pathlib.Path, int]]:
    """Each subpackage `__init__.py` that exports nothing while a sibling exports a non-trivial surface.

    Returns `(path, sibling_max)` pairs, `sibling_max` being the largest export
    count among the subpackage inits. Empty when no sibling exports
    `MIN_SIBLING_SURFACE` names or more.
    """
    init_files: dict[pathlib.Path, int] = {}
    for path in auditor.core.all_py_files(src_root):
        if path.name != '__init__.py':
            continue
        # Skip the top-level package init (parent is src_root itself)
        if path.parent == src_root:
            continue
        tree = auditor.core.read_and_parse(path)
        if tree is None:
            continue
        export_count = 0
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == '__all__':
                        if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                            export_count = len(node.value.elts)
            elif isinstance(node, (ast.ImportFrom,)) and node.module:
                # `from .x import Y` style re-exports
                export_count += len(node.names)
        init_files[path] = export_count
    if not init_files:
        return []
    sibling_max = max(init_files.values())
    if sibling_max < MIN_SIBLING_SURFACE:
        return []
    return [(path, sibling_max) for path, count in init_files.items() if count == 0]


def migration_shim_sites(src_root: pathlib.Path) -> list[tuple[pathlib.Path, int, str, str]]:
    """Each read of a symbol through a re-export shim instead of its canonical home.

    A shim is a module-level assignment `X = pkg.mod.X` whose left name equals
    the right attribute and whose right side starts with the root's name; the
    canonical home of `X` is `pkg.mod`. Returns `(path, line, variant, evidence)`
    for every importer or attribute read that names `X` by the shim's module.
    """
    package_root_name = src_root.name
    shims: dict[str, set[tuple[str, str]]] = collections.defaultdict(set)

    for path in auditor.core.all_py_files(src_root):
        tree = auditor.core.read_and_parse(path)
        if tree is None:
            continue
        shim_mod = module_dotted_name(path, src_root)
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if value is None:
                continue
            if not (isinstance(value, ast.Attribute) and isinstance(value.value, ast.Attribute | ast.Name)):
                continue
            rhs = ast.unparse(value)
            if not rhs.startswith(package_root_name + '.'):
                continue
            sym = value.attr
            for tgt in targets:
                if isinstance(tgt, ast.Name) and tgt.id == sym:
                    canonical_mod = rhs.rsplit('.', 1)[0]  # everything before the symbol
                    shims[shim_mod].add((sym, canonical_mod))

    sites: list[tuple[pathlib.Path, int, str, str]] = []
    for path in auditor.core.all_py_files(src_root):
        tree = auditor.core.read_and_parse(path)
        if tree is None:
            continue
        # the consumer is itself a module; do not flag the canonical or shim
        if module_dotted_name(path, src_root) in shims:
            continue
        for node in ast.walk(tree):
            # Pattern 1: `from <shim_mod> import X` where X has a canonical home elsewhere
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module in shims:
                    for alias in node.names:
                        for sym, canonical_mod in shims[node.module]:
                            if alias.name == sym and canonical_mod != node.module:
                                variant = f'imports `{sym}` via shim `{node.module}`; canonical home is `{canonical_mod}`'
                                sites.append((path, node.lineno, variant, f'from {node.module} import {sym}'))
            # Pattern 2: `<shim_mod>.X` attribute access where X has a canonical home
            if isinstance(node, ast.Attribute) and isinstance(node.value, (ast.Name, ast.Attribute)):
                full = ast.unparse(node)
                if not full.startswith(package_root_name + '.'):
                    continue
                parent_mod, _, attr = full.rpartition('.')
                if parent_mod in shims:
                    for sym, canonical_mod in shims[parent_mod]:
                        if attr == sym and canonical_mod != parent_mod:
                            variant = f'reads `{sym}` from shim `{parent_mod}`; canonical home is `{canonical_mod}`'
                            sites.append((path, getattr(node, 'lineno', 1), variant, full[:200]))
    return sites
