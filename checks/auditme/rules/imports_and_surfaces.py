"""Checks on import graphs and package public surfaces."""

from __future__ import annotations
import ast
import pathlib
import re
from collections import defaultdict
from typing import Iterable

from auditme.core import _accept_reason, _accepted_lazy_imports, _all_py_files, _emit, _relpath, _source_lines, _type_checking_linenos


def check_def_class_in_init(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    for path in _all_py_files(src_root):
        if path.name != '__init__.py':
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        for idx, raw in enumerate(lines, 1):
            if re.match(r'^(def |class )', raw):
                accept = _accept_reason(lines, idx, rule='def-class-in-init')
                _emit(
                    rule='def-class-in-init',
                    variant='top-level def or class in __init__.py',
                    path=rel,
                    line=idx,
                    evidence=raw.strip()[:200],
                    accepted=bool(accept),
                    accepted_reason=accept,
                )

def _walk_function_scopes(tree: ast.AST) -> Iterable[ast.AST]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node

_STDLIB = {
    'abc',
    'argparse',
    'ast',
    'asyncio',
    'base64',
    'collections',
    'contextlib',
    'copy',
    'csv',
    'dataclasses',
    'datetime',
    'decimal',
    'enum',
    'errno',
    'functools',
    'gc',
    'glob',
    'gzip',
    'hashlib',
    'heapq',
    'importlib',
    'inspect',
    'io',
    'ipaddress',
    'itertools',
    'json',
    'locale',
    'logging',
    'math',
    'mimetypes',
    'operator',
    'os',
    'pathlib',
    'platform',
    'pprint',
    'queue',
    'random',
    're',
    'secrets',
    'shlex',
    'shutil',
    'signal',
    'socket',
    'sqlite3',
    'ssl',
    'stat',
    'string',
    'struct',
    'subprocess',
    'sys',
    'tempfile',
    'textwrap',
    'threading',
    'time',
    'timeit',
    'token',
    'tokenize',
    'traceback',
    'types',
    'typing',
    'unicodedata',
    'urllib',
    'uuid',
    'warnings',
    'weakref',
    'xml',
    'zipfile',
    'zoneinfo',
}

def check_in_function_imports(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    accepted_pairs = _accepted_lazy_imports(scope)
    for path in _all_py_files(src_root):
        if path.name == '__init__.py':
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        type_checking_linenos = _type_checking_linenos(tree)
        importerror_linenos: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                handles = False
                for h in node.handlers:
                    if (
                        isinstance(h.type, ast.Name)
                        and h.type.id in {'ImportError', 'ModuleNotFoundError'}
                        or (
                            isinstance(h.type, ast.Tuple)
                            and any(isinstance(e, ast.Name) and e.id in {'ImportError', 'ModuleNotFoundError'} for e in h.type.elts)
                        )
                    ):
                        handles = True
                if handles:
                    for child in node.body:
                        for sub in ast.walk(child):
                            if hasattr(sub, 'lineno'):
                                importerror_linenos.add(sub.lineno)
        importer_module = rel.replace('/', '.').removesuffix('.py').removeprefix('src.')
        for func in _walk_function_scopes(tree):
            for inner in ast.walk(func):
                if not isinstance(inner, (ast.Import, ast.ImportFrom)):
                    continue
                if inner.lineno in type_checking_linenos:
                    continue
                if inner.lineno in importerror_linenos:
                    continue
                if isinstance(inner, ast.Import):
                    imported_names = [n.name for n in inner.names]
                else:
                    imported_names = [inner.module or '']
                accept = _accept_reason(lines, inner.lineno, rule='in-function-import')
                for imported in imported_names:
                    pair_accepted = any(importer_module.startswith(a) and imported.startswith(b) for (a, b) in accepted_pairs)
                    if pair_accepted:
                        accept = accept or f'AGENTS.md accepted ({importer_module} -> {imported})'
                    top = imported.split('.')[0]
                    variant = 'stdlib' if top in _STDLIB else ('first-party' if importer_module.split('.')[0] == top else 'third-party')
                    _emit(
                        rule='in-function-import',
                        variant=variant,
                        path=rel,
                        line=inner.lineno,
                        evidence=f'{"import" if isinstance(inner, ast.Import) else "from"} {imported}',
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )

def check_unused_submodule_imports(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        full_src = '\n'.join(lines)
        for node in tree.body:
            if not isinstance(node, ast.Import):
                continue
            for alias in node.names:
                if alias.asname:
                    continue
                if '.' not in alias.name:
                    continue
                import_line_src = lines[node.lineno - 1] if node.lineno <= len(lines) else ''
                remainder = full_src.replace(import_line_src, '', 1)
                if re.search(rf'\b{re.escape(alias.name)}\b', remainder):
                    continue
                root_name = alias.name.split('.')[0]
                if re.search(rf'\b{re.escape(root_name)}\.', remainder):
                    continue
                accept = _accept_reason(lines, node.lineno, rule='unused-submodule-import')
                _emit(
                    rule='unused-submodule-import',
                    variant='import X.Y.Z never referenced',
                    path=rel,
                    line=node.lineno,
                    evidence=f'import {alias.name}',
                    accepted=bool(accept),
                    accepted_reason=accept,
                )

def _parse_package_layering(scope: pathlib.Path) -> tuple[list[str], set[tuple[str, str]]]:
    """Parse AGENTS.md's Package Layering section.

    Returns (layer_order, accepted_exceptions). layer_order is a list of
    package names from low to high; accepted_exceptions is a set of
    (importer_pkg, imported_pkg) pairs that are explicitly allowed to
    invert the layering.
    """
    agents = scope / 'AGENTS.md'
    if not agents.exists():
        return [], set()
    text = agents.read_text(encoding='utf-8')
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

def check_layering_violations(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Walk every import; if it is a first-party import and goes upward
    in the layering chain, flag unless the (importer, imported) pair is
    in AGENTS.md's accepted-exceptions table or the line carries an
    `# auditme: accept` marker."""
    layer_order, accepted = _parse_package_layering(scope)
    if not layer_order:
        return
    rank = {pkg: i for i, pkg in enumerate(layer_order)}
    package_root_name = src_root.name  # e.g. 'feathf'

    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        # importer's package is the first component under src_root
        rel_parts = path.relative_to(src_root).parts
        if len(rel_parts) < 2:
            continue
        importer_pkg = rel_parts[0]
        if importer_pkg not in rank:
            continue
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        tc_linenos = _type_checking_linenos(tree)
        for node in ast.walk(tree):
            module_name = None
            if isinstance(node, ast.Import):
                if node.lineno in tc_linenos:
                    continue
                for alias in node.names:
                    module_name = alias.name
                    _maybe_emit_layering(rel, lines, node.lineno, importer_pkg, module_name,
                                         rank, accepted, package_root_name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.lineno in tc_linenos:
                    continue
                module_name = node.module
                _maybe_emit_layering(rel, lines, node.lineno, importer_pkg, module_name,
                                     rank, accepted, package_root_name)

def _maybe_emit_layering(rel, lines, lineno, importer_pkg, module_name,
                         rank, accepted, package_root_name):
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
    accept = _accept_reason(lines, lineno, rule='layering-violation')
    _emit(
        rule='layering-violation',
        variant=f'{importer_pkg} imports {imported_pkg} (upward)',
        path=rel,
        line=lineno,
        evidence=f'import {module_name}',
        accepted=bool(accept),
        accepted_reason=accept,
    )

def check_passthrough_shim(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag module-level functions whose body is exactly `return f(...)`
    where the call's args are the function's own parameters. These are
    pass-through shims that add no behaviour and obscure the real callee."""
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # strip a leading docstring
            body = [b for b in node.body if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
            if len(body) != 1:
                continue
            stmt = body[0]
            if not isinstance(stmt, ast.Return) or not isinstance(stmt.value, ast.Call):
                continue
            call = stmt.value
            # Compare args: every positional must be a Name matching a parameter
            param_names = [a.arg for a in node.args.args]
            if not call.args:
                continue
            if not all(isinstance(a, ast.Name) and a.id in param_names for a in call.args):
                continue
            try:
                call_src = ast.unparse(call.func)
            except Exception:
                continue
            # skip self.<method>(args) - that's typical delegation, not a shim
            if call_src.startswith('self.'):
                continue
            accept = _accept_reason(lines, node.lineno, rule='passthrough-shim')
            _emit(
                rule='passthrough-shim',
                variant=f'{node.name} is a pass-through wrapper for {call_src}',
                path=rel,
                line=node.lineno,
                evidence=f'def {node.name}(...): return {call_src}(...)',
                accepted=bool(accept),
                accepted_reason=accept,
            )

def check_empty_init_with_exporting_siblings(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag any subpackage `__init__.py` that exports nothing while at
    least one sibling subpackage exports a non-trivial public surface.
    Sparse public surfaces force consumers to reach into private submodules.

    Acceptance (review-36): this is a file-level finding, so the
    accept-marker scan looks at every line in the file rather than just
    the docstring line. A docstring-only ``__init__.py`` cannot host an
    inline comment on the docstring opener; the marker has to land on a
    separate comment-only line. Any line containing
    ``# auditme: accept <reason>`` accepts the file."""
    init_files: dict[pathlib.Path, int] = {}
    for path in _all_py_files(src_root):
        if path.name != '__init__.py':
            continue
        # Skip the top-level package init (parent is src_root itself)
        if path.parent == src_root:
            continue
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
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
        return
    sibling_max = max(init_files.values())
    if sibling_max < 5:
        return  # no sibling exports a non-trivial surface; rule does not apply
    for path, count in init_files.items():
        if count != 0:
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        # File-level finding: scan every line for an `# auditme: accept`
        # marker. The standard line-bracketed `_accept_reason` only checks
        # the hit line and its predecessor, but a docstring-only
        # `__init__.py` cannot host an inline comment on the docstring
        # line itself - the marker has to land on a comment-only line
        # somewhere in the file.
        accept: str | None = None
        for ln in range(1, len(lines) + 1):
            accept = _accept_reason(lines, ln, rule='empty-init-while-siblings-export')
            if accept:
                break
        _emit(
            rule='empty-init-while-siblings-export',
            variant=f'{path.parent.name}/__init__.py exports 0 symbols; siblings export up to {sibling_max}',
            path=rel,
            line=1,
            evidence='no __all__ and no re-exports',
            accepted=bool(accept),
            accepted_reason=accept,
        )

def check_migration_shim_consumers(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Detect re-export shims (`X = canonical.X` style aliases) and flag
    any consumer that imports via the shim instead of the canonical home.

    Mechanical signal: a module-level assignment `X = pkg.mod.X` where the
    LHS name equals the RHS attribute is a re-export shim for symbol X
    whose canonical home is `pkg.mod`. Any importer that reads `X` via
    the shim's path is using a deprecated migration shim.
    """
    package_root_name = src_root.name
    # canonical_home: dict[symbol_name -> set[canonical_module_dotted_path]]
    canonical_home: dict[str, set[str]] = defaultdict(set)
    # shims: dict[shim_module_dotted_path -> set[(symbol, canonical_module)]]
    shims: dict[str, set[tuple[str, str]]] = defaultdict(set)

    for path in _all_py_files(src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = _relpath(path, scope)
        # mod path like 'feathf.models.settings'
        rel_parts = path.relative_to(src_root).parts
        if rel_parts[-1] == '__init__.py':
            shim_mod = package_root_name + '.' + '.'.join(rel_parts[:-1]) if len(rel_parts) > 1 else package_root_name
        else:
            shim_mod = package_root_name + '.' + '.'.join(rel_parts)[:-3]  # strip '.py'
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            # X = feathf.something.X
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if value is None:
                continue
            if not (isinstance(value, ast.Attribute) and isinstance(value.value, ast.Attribute | ast.Name)):
                continue
            # unparse RHS to get full dotted path
            try:
                rhs = ast.unparse(value)
            except Exception:
                continue
            if not rhs.startswith(package_root_name + '.'):
                continue
            sym = value.attr
            for tgt in targets:
                if isinstance(tgt, ast.Name) and tgt.id == sym:
                    canonical_mod = rhs.rsplit('.', 1)[0]  # everything before the symbol
                    canonical_home[sym].add(canonical_mod)
                    shims[shim_mod].add((sym, canonical_mod))
    # Now walk all imports project-wide; for each symbol with an established
    # canonical home AND a known shim, find any consumer that reads the
    # symbol via the shim's module path.
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        # the consumer is itself a module; do not flag the canonical or shim
        rel_parts = path.relative_to(src_root).parts
        if rel_parts[-1] == '__init__.py':
            consumer_mod = package_root_name + '.' + '.'.join(rel_parts[:-1]) if len(rel_parts) > 1 else package_root_name
        else:
            consumer_mod = package_root_name + '.' + '.'.join(rel_parts)[:-3]
        if consumer_mod in shims:
            continue
        lines = _source_lines(path)
        for node in ast.walk(tree):
            # Pattern 1: `from <shim_mod> import X` where X has a canonical home elsewhere
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module in shims:
                    for alias in node.names:
                        for sym, canonical_mod in shims[node.module]:
                            if alias.name == sym and canonical_mod != node.module:
                                accept = _accept_reason(lines, node.lineno, rule='migration-shim-consumer')
                                _emit(
                                    rule='migration-shim-consumer',
                                    variant=f'imports `{sym}` via shim `{node.module}`; canonical home is `{canonical_mod}`',
                                    path=rel,
                                    line=node.lineno,
                                    evidence=f'from {node.module} import {sym}',
                                    accepted=bool(accept),
                                    accepted_reason=accept,
                                )
            # Pattern 2: `<shim_mod>.X` attribute access where X has a canonical home
            if isinstance(node, ast.Attribute) and isinstance(node.value, (ast.Name, ast.Attribute)):
                try:
                    full = ast.unparse(node)
                except Exception:
                    continue
                if not full.startswith(package_root_name + '.'):
                    continue
                # Split into module-prefix and attr
                parent_mod, _, attr = full.rpartition('.')
                if parent_mod in shims:
                    for sym, canonical_mod in shims[parent_mod]:
                        if attr == sym and canonical_mod != parent_mod:
                            line_no = getattr(node, 'lineno', 1)
                            accept = _accept_reason(lines, line_no, rule='migration-shim-consumer')
                            _emit(
                                rule='migration-shim-consumer',
                                variant=f'reads `{sym}` from shim `{parent_mod}`; canonical home is `{canonical_mod}`',
                                path=rel,
                                line=line_no,
                                evidence=full[:200],
                                accepted=bool(accept),
                                accepted_reason=accept,
                            )

def check_reexport_in_non_init(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag module-level assignments `X = <dotted.path>.X` in files OTHER
    than `__init__.py`. Re-exports belong in the package's `__init__.py`;
    mid-tree re-export shims fragment the public surface and create
    migration-shim-style consumer drift.
    """
    for path in _all_py_files(src_root):
        if path.name == '__init__.py':
            continue
        rel = _relpath(path, scope)
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        lines = _source_lines(path)
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            # pattern: LHS is a single Name; RHS is Attribute whose
            # trailing .attr matches the LHS name
            if len(node.targets) != 1:
                continue
            tgt = node.targets[0]
            if not isinstance(tgt, ast.Name):
                continue
            if not isinstance(node.value, ast.Attribute):
                continue
            if node.value.attr != tgt.id:
                continue
            # The RHS must be a module path (Attribute of Attribute or Name)
            try:
                rhs_src = ast.unparse(node.value)
            except Exception:
                continue
            accept = _accept_reason(lines, node.lineno, rule='reexport-in-non-init')
            _emit(
                rule='reexport-in-non-init',
                variant=f'`{tgt.id} = {rhs_src}` at module scope in non-__init__.py file',
                path=rel,
                line=node.lineno,
                evidence=(lines[node.lineno - 1].strip()[:200]
                          if node.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )

_ALL_GUARD_RE = re.compile(r"""['"]__all__['"]|\.__all__\b""")

def _project_has_all_guard(scope: pathlib.Path) -> bool:
    """True when some file in the project inspects other modules' `__all__`.

    The signal is `__all__` read as data - `getattr(mod, '__all__')`,
    `mod.__all__`, or an AST walk comparing a target's id to `'__all__'` -
    rather than declared. A project with no such guard has nothing to switch
    off, so the annotated form costs it nothing.
    """
    src = scope / 'src'
    if not src.is_dir():
        return False
    for path in sorted(src.rglob('*.py')):
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        if _ALL_GUARD_RE.search(text):
            return True
    return False

def check_annotated_all_assignment(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `__all__: list[str] = [...]` in a project that guards `__all__`.

    An annotated assignment is an `ast.AnnAssign`, not an `ast.Assign`. A
    public-surface guard written to match `ast.Assign` therefore does not see
    the module at all - and reports green while checking nothing, which is the
    worst failure a guard has. On litrev this switched the guard off for a
    whole package: its `__all__` entries were never checked for a consumer, and
    the private-submodule exception entries written for it were inert, while
    the suite passed throughout.

    The predicate is not "an annotated `__all__` is wrong". It is that a
    project whose surface guard may discriminate on assignment form has a hole
    wherever the annotated form appears. A guard that handles both forms is a
    real answer - record it with an accept marker on the declaration, or
    normalise the declaration to the plain form.

    Fires only where the project has an `__all__`-based guard at all; see
    `_project_has_all_guard`.
    """
    if not _project_has_all_guard(scope):
        return
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.AnnAssign):
                continue
            if not isinstance(node.target, ast.Name) or node.target.id != '__all__':
                continue
            accept = _accept_reason(lines, node.lineno, rule='annotated-all-assignment')
            _emit(
                rule='annotated-all-assignment',
                variant='__all__ is an AnnAssign; a guard matching ast.Assign skips this module',
                path=rel,
                line=node.lineno,
                evidence=lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else ast.unparse(node),
                accepted=bool(accept),
                accepted_reason=accept,
            )
