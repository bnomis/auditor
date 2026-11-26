import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def read_package_layering(scope: pathlib.Path) -> tuple[list[str], set[tuple[str, str]]]:
    """`scan_package_layering`, worked out once per run; callers do not modify the result."""
    return typing.cast('tuple[list[str], set[tuple[str, str]]]', auditor.api.cached_per_run('read_package_layering', scope, scan_package_layering))


def scan_package_layering(scope: pathlib.Path) -> tuple[list[str], set[tuple[str, str]]]:
    """Parse AGENTS.md's Package Layering section.

    Returns (layer_order, accepted_exceptions). layer_order is a list of
    package names from low to high; accepted_exceptions is a set of
    (importer_pkg, imported_pkg) pairs that are explicitly allowed to
    invert the layering.
    """
    agents = scope / 'AGENTS.md'
    if not agents.is_file():
        return [], set()
    text = auditor.api.read_source(agents)
    if text is None:
        return [], set()
    layer_order: list[str] = []
    accepted: set[tuple[str, str]] = set()
    in_layering_section = False
    in_exceptions_table = False
    for line in text.splitlines():
        if re.match(r'^##+\s+Package\s+Layering', line, re.IGNORECASE):
            in_layering_section = True
            continue
        if in_layering_section and re.match(r'^##+ ', line):
            # next heading; check if it is the exceptions sub-section
            if re.search(r'Accepted\s+(cross-layer\s+)?exceptions?', line, re.IGNORECASE):
                in_exceptions_table = True
                continue
            else:
                in_layering_section = False
                in_exceptions_table = False
                continue
        if in_layering_section and not in_exceptions_table and not layer_order:
            # match `data < config < ...` or similar single-line layer order
            if '<' in line and '`' not in line:
                clean = line.strip().strip('`')
                parts = [p.strip().strip('`') for p in clean.split('<')]
                if len(parts) >= 2 and all(re.match(r'^[a-z_][a-z0-9_]*$', p) for p in parts):
                    layer_order = parts
            elif line.strip().startswith('```'):
                continue
        if in_exceptions_table and line.startswith('|'):
            cells = [c.strip() for c in line.strip('|').split('|')]
            if len(cells) < 2:
                continue
            m0 = re.findall(r'`([a-zA-Z_.][a-zA-Z0-9_.]*)`', cells[0])
            m1 = re.findall(r'`([a-zA-Z_.][a-zA-Z0-9_.]*)`', cells[1])
            for a in m0:
                for b in m1:
                    accepted.add((a.split('.')[0], b.split('.')[0]))
    return layer_order, accepted


def maybe_emit_layering(
    rel: str,
    lines: list[str],
    lineno: int,
    importer_pkg: str,
    module_name: str,
    rank: dict[str, int],
    accepted: set[tuple[str, str]],
    package_root_name: str,
) -> None:
    if not module_name.startswith(package_root_name + '.'):
        return
    parts = module_name.split('.')
    if len(parts) < 2:
        return
    imported_pkg = parts[1]
    if imported_pkg == importer_pkg:
        return
    if imported_pkg not in rank:
        return
    if rank[imported_pkg] <= rank[importer_pkg]:
        return  # downward or equal; fine
    if (importer_pkg, imported_pkg) in accepted:
        return
    accept = auditor.api.accept_reason(lines, lineno, rule='layering-violation')
    auditor.api.emit(
        rule='layering-violation',
        variant=f'{importer_pkg} imports {imported_pkg} (upward)',
        path=rel,
        line=lineno,
        evidence=f'import {module_name}',
        accepted=bool(accept),
        accepted_reason=accept,
    )


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a first-party import that goes upward in AGENTS.md's package layering."""
    layer_order, accepted = read_package_layering(scope)
    if not layer_order:
        return
    rank = {pkg: i for i, pkg in enumerate(layer_order)}
    package_root_name = src_root.name  # e.g. 'pkg'

    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        # importer's package is the first component under src_root
        rel_parts = path.relative_to(src_root).parts
        if len(rel_parts) < 2:
            continue
        importer_pkg = rel_parts[0]
        if importer_pkg not in rank:
            continue
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        tc_linenos = auditor.api.type_checking_linenos(tree)
        for node in ast.walk(tree):
            module_name = None
            if isinstance(node, ast.Import):
                if node.lineno in tc_linenos:
                    continue
                for alias in node.names:
                    module_name = alias.name
                    maybe_emit_layering(rel, lines, node.lineno, importer_pkg, module_name, rank, accepted, package_root_name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.lineno in tc_linenos:
                    continue
                module_name = node.module
                maybe_emit_layering(rel, lines, node.lineno, importer_pkg, module_name, rank, accepted, package_root_name)
