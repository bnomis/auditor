"""Checks on import graphs and package public surfaces."""

import ast
import collections
import collections.abc
import re
import typing

import auditme.core

if typing.TYPE_CHECKING:
    import pathlib

IMPORT_ERROR_NAMES = frozenset({'ImportError', 'ModuleNotFoundError'})


def check_def_class_in_init(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a top-level `def` or `class` line in an `__init__.py`.

    Signal: a line of an `__init__.py` that starts with `def ` or `class `
    in column 0. Carve-outs: only `__init__.py` files are read; an indented
    definition (inside an `if` block, say) is not matched.
    """
    for path in auditme.core.all_py_files(src_root):
        if path.name != '__init__.py':
            continue
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        for idx, raw in enumerate(lines, 1):
            if re.match(r'^(def |class )', raw):
                accept = auditme.core.accept_reason(lines, idx, rule='def-class-in-init')
                auditme.core.emit(
                    rule='def-class-in-init',
                    variant='top-level def or class in __init__.py',
                    path=rel,
                    line=idx,
                    evidence=raw.strip()[:200],
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


def walk_function_scopes(tree: ast.AST) -> collections.abc.Iterable[ast.AST]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


STDLIB = {
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


def declared_root_modules() -> frozenset[str]:
    """The top-level module names the declared roots (`[tool.auditme]`) provide.

    A `package` root provides its own directory name; a `top-level` root
    provides each module and package directly inside it. Empty when no root is
    declared.
    """
    key = ('declared-root-modules', tuple(auditme.core.ROOT_MODULES.items()))
    if key in auditme.core.INDEX_CACHE:
        return typing.cast('frozenset[str]', auditme.core.INDEX_CACHE[key])
    names: set[str] = set()
    for root, mode in auditme.core.ROOT_MODULES.items():
        if mode == auditme.core.TOP_LEVEL:
            names.update(p.stem for p in root.glob('*.py'))
            names.update(p.name for p in root.iterdir() if p.is_dir() and (p / '__init__.py').is_file())
        else:
            names.add(root.name)
    declared = frozenset(names)
    auditme.core.INDEX_CACHE[key] = declared
    return declared


def check_in_function_imports(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag every import inside a function.

    The variant labels the imported module `stdlib`, `first-party` or
    `third-party`. Refinement (2026-11-21): a module under a declared root
    (`[tool.auditme]`, either mode) is first-party, not only the importer's own
    package, so an import between two declared roots is labelled as one.
    """
    accepted_pairs = auditme.core.accepted_lazy_imports(scope)
    for path in auditme.core.all_py_files(src_root):
        if path.name == '__init__.py':
            continue
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        type_checking_linenos = auditme.core.type_checking_linenos(tree)
        importerror_linenos: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                handles = False
                for h in node.handlers:
                    if (
                        isinstance(h.type, ast.Name)
                        and h.type.id in IMPORT_ERROR_NAMES
                        or (isinstance(h.type, ast.Tuple) and any(isinstance(e, ast.Name) and e.id in IMPORT_ERROR_NAMES for e in h.type.elts))
                    ):
                        handles = True
                if handles:
                    for child in node.body:
                        for sub in ast.walk(child):
                            if hasattr(sub, 'lineno'):
                                importerror_linenos.add(sub.lineno)
        importer_module = rel.replace('/', '.').removesuffix('.py').removeprefix('src.')
        first_party = declared_root_modules() | {importer_module.split('.')[0]}
        for func in walk_function_scopes(tree):
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
                accept = auditme.core.accept_reason(lines, inner.lineno, rule='in-function-import')
                for imported in imported_names:
                    pair_accepted = any(importer_module.startswith(a) and imported.startswith(b) for (a, b) in accepted_pairs)
                    if pair_accepted:
                        accept = accept or f'AGENTS.md accepted ({importer_module} -> {imported})'
                    top = imported.split('.')[0]
                    variant = 'stdlib' if top in STDLIB else ('first-party' if top in first_party else 'third-party')
                    auditme.core.emit(
                        rule='in-function-import',
                        variant=variant,
                        path=rel,
                        line=inner.lineno,
                        evidence=f'{"import" if isinstance(inner, ast.Import) else "from"} {imported}',
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )


def check_unused_submodule_imports(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a top-level `import a.b.c` whose name the file never uses.

    Signal: a module-level `import X.Y` with no `as` alias, where neither the
    dotted name nor its root followed by a dot appears in the rest of the
    file. Carve-outs: an `as` alias, an undotted import, an import not at
    module level, and a file that does not parse.
    """
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
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
                accept = auditme.core.accept_reason(lines, node.lineno, rule='unused-submodule-import')
                auditme.core.emit(
                    rule='unused-submodule-import',
                    variant='import X.Y.Z never referenced',
                    path=rel,
                    line=node.lineno,
                    evidence=f'import {alias.name}',
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


# A prohibition word, a short gap, then the keyword quoted or backticked:
# "no `as` imports either", 'Do NOT use "as" imports', "never use `as` imports".
# Requiring the quoting is what keeps ordinary prose - "no imports as such" -
# from reading as a declared rule.
AS_IMPORT_BAN_RE = re.compile(
    r"""(?:\bno\b|\bnever\b|\bavoid\b|\bdo\s+not\b|\bdon'?t\b)
        [^.\n]{0,24}?
        [`"']as[`"']
        \s+imports?\b""",
    re.IGNORECASE | re.VERBOSE,
)


def project_bans_as_imports(scope: pathlib.Path) -> bool:
    """True when the project's own AGENTS.md declares `import X as Y` banned.

    The check is gated because the rule is a project standard, not a universal
    one: `import numpy as np` is idiomatic nearly everywhere, and a checker
    that flagged it unasked would bury every other hit. Only AGENTS.md is read,
    the way the layering and lazy-import tables are - a rule the project states
    somewhere else is a rule the project has not stated here.
    """
    agents = scope / 'AGENTS.md'
    if not agents.exists():
        return False
    text = auditme.core.read_source(agents)
    return text is not None and bool(AS_IMPORT_BAN_RE.search(text))


def check_as_import(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `import X as Y` / `from M import X as Y` where the project bans it.

    An alias is a second name for a module, so every reader has to hold the
    mapping in their head, and the full-import-path codemods do not see it:
    one project's AGENTS.md states the ban and names two enforcement mechanisms -
    ruff's `ICN003`, which only sees the modules listed in `banned-from`, and
    `bin/full-path-imports.sh --check`, which rewrites `from X import Y` and
    leaves a bare `import gitutils as module` alone. Both reported clean over a
    tree that carried one.

    The signal is `ast.alias.asname` on any `ast.Import` or `ast.ImportFrom`.

    Carve-out: a module-level `from ... import ... as ...` in an `__init__.py`.
    That is a package's re-export list, the one place a from-import is
    sanctioned, and renaming on the way out is how a surface is composed. A
    plain `import x as y` in an `__init__.py` is not a re-export and still
    fires.

    Fires only where `project_bans_as_imports` finds the rule declared.
    """
    if not project_bans_as_imports(scope):
        return
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        reexport_linenos: set[int] = set()
        if path.name == '__init__.py':
            reexport_linenos = {n.lineno for n in tree.body if isinstance(n, ast.ImportFrom)}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if node.lineno in reexport_linenos:
                continue
            for alias in node.names:
                if not alias.asname:
                    continue
                if isinstance(node, ast.Import):
                    variant = 'import X as Y'
                    statement = f'import {alias.name} as {alias.asname}'
                else:
                    variant = 'from M import X as Y'
                    statement = f'from {"." * node.level}{node.module or ""} import {alias.name} as {alias.asname}'
                accept = auditme.core.accept_reason(lines, node.lineno, rule='as-import')
                auditme.core.emit(
                    rule='as-import',
                    variant=variant,
                    path=rel,
                    line=node.lineno,
                    evidence=statement,
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


def check_from_import(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `from X import Y` in any file other than an `__init__.py`.

    The shared import rule asks for full import paths - `import pathlib` then
    `pathlib.Path` - and names one exception: an `__init__.py`'s re-export
    list. Until 2026-10-14 nothing mechanical read that rule, so audits found
    its sites by hand under S4, a judgement question answering
    what a parser can.

    The signal is any `ast.ImportFrom` in a non-`__init__.py` file, at any
    depth: a function-local or `TYPE_CHECKING` from-import is still one. Each
    statement is one hit, however many names it imports.

    Not this rule's: `from __future__ import ...` (`future-annotations`) and
    `from X import *` (`wildcard-imports`), which already report the same line
    for a sharper reason. A relative import outside an `__init__.py` is also
    `relative-import-nonpackage`'s, and is reported by both, the way
    `import X as Y` is by both `aliased-imports` and `as-import`.

    Ungated, unlike `as-import`: the rule is a shared standard, as
    `stdlib-logging` and `legacy-typing` are, and no project restates it in
    its AGENTS.md - a gate there would silence the check on every project the
    rule governs.
    """
    for path in auditme.core.all_py_files(src_root):
        if path.name == '__init__.py':
            continue
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module == '__future__' or any(alias.name == '*' for alias in node.names):
                continue
            module = f'{"." * node.level}{node.module or ""}'
            names = ', '.join(alias.name for alias in node.names)
            accept = auditme.core.accept_reason(lines, node.lineno, getattr(node, 'end_lineno', None), rule='from-import')
            auditme.core.emit(
                rule='from-import',
                variant='from X import Y outside an __init__.py',
                path=rel,
                line=node.lineno,
                evidence=f'from {module} import {names}'[:200],
                accepted=bool(accept),
                accepted_reason=accept,
            )


def read_package_layering(scope: pathlib.Path) -> tuple[list[str], set[tuple[str, str]]]:
    """Parse AGENTS.md's Package Layering section.

    Returns (layer_order, accepted_exceptions). layer_order is a list of
    package names from low to high; accepted_exceptions is a set of
    (importer_pkg, imported_pkg) pairs that are explicitly allowed to
    invert the layering.
    """
    agents = scope / 'AGENTS.md'
    if not agents.exists():
        return [], set()
    text = auditme.core.read_source(agents)
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


def check_layering_violations(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Walk every import; if it is a first-party import and goes upward
    in the layering chain, flag unless the (importer, imported) pair is
    in AGENTS.md's accepted-exceptions table or the line carries an
    `# auditme: accept` marker."""
    layer_order, accepted = read_package_layering(scope)
    if not layer_order:
        return
    rank = {pkg: i for i, pkg in enumerate(layer_order)}
    package_root_name = src_root.name  # e.g. 'pkg'

    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        # importer's package is the first component under src_root
        rel_parts = path.relative_to(src_root).parts
        if len(rel_parts) < 2:
            continue
        importer_pkg = rel_parts[0]
        if importer_pkg not in rank:
            continue
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        tc_linenos = auditme.core.type_checking_linenos(tree)
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
    accept = auditme.core.accept_reason(lines, lineno, rule='layering-violation')
    auditme.core.emit(
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
    pass-through shims that add no behaviour and obscure the real callee.

    Refinement (2026-11-01): only real forwarding is flagged. Every keyword
    value must be a Name of one of the wrapper's parameters (a `**` keyword
    or a computed value is not), no parameter may be passed twice across the
    positional and keyword arguments (`table.get(name, name)` computes), and
    a function with any decorator is skipped, since a decorator registers it
    for something else (a fixture, a command, a route)."""
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.decorator_list:
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
            if not all(kw.arg is not None and isinstance(kw.value, ast.Name) and kw.value.id in param_names for kw in call.keywords):
                continue
            passed = [a.id for a in call.args if isinstance(a, ast.Name)] + [kw.value.id for kw in call.keywords if isinstance(kw.value, ast.Name)]
            if len(passed) != len(set(passed)):
                continue
            call_src = ast.unparse(call.func)
            # skip self.<method>(args) - that's typical delegation, not a shim
            if call_src.startswith('self.'):
                continue
            accept = auditme.core.accept_reason(lines, node.lineno, rule='passthrough-shim')
            auditme.core.emit(
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

    Acceptance: this is a file-level finding, so the
    accept-marker scan looks at every line in the file rather than just
    the docstring line. A docstring-only ``__init__.py`` cannot host an
    inline comment on the docstring opener; the marker has to land on a
    separate comment-only line. Any line containing
    ``# auditme: accept <reason>`` accepts the file."""
    init_files: dict[pathlib.Path, int] = {}
    for path in auditme.core.all_py_files(src_root):
        if path.name != '__init__.py':
            continue
        # Skip the top-level package init (parent is src_root itself)
        if path.parent == src_root:
            continue
        tree = auditme.core.read_and_parse(path)
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
        return
    sibling_max = max(init_files.values())
    if sibling_max < 5:
        return  # no sibling exports a non-trivial surface; rule does not apply
    for path, count in init_files.items():
        if count != 0:
            continue
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        # File-level finding: scan every line for an `# auditme: accept`
        # marker. The standard line-bracketed `accept_reason` only checks
        # the hit line and its predecessor, but a docstring-only
        # `__init__.py` cannot host an inline comment on the docstring
        # line itself - the marker has to land on a comment-only line
        # somewhere in the file.
        accept: str | None = None
        for ln in range(1, len(lines) + 1):
            accept = auditme.core.accept_reason(lines, ln, rule='empty-init-while-siblings-export')
            if accept:
                break
        auditme.core.emit(
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
    canonical_home: dict[str, set[str]] = collections.defaultdict(set)
    # shims: dict[shim_module_dotted_path -> set[(symbol, canonical_module)]]
    shims: dict[str, set[tuple[str, str]]] = collections.defaultdict(set)

    for path in auditme.core.all_py_files(src_root):
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        rel = auditme.core.relpath(path, scope)
        # mod path like 'pkg.models.settings'
        rel_parts = path.relative_to(src_root).parts
        if rel_parts[-1] == '__init__.py':
            shim_mod = package_root_name + '.' + '.'.join(rel_parts[:-1]) if len(rel_parts) > 1 else package_root_name
        else:
            shim_mod = package_root_name + '.' + '.'.join(rel_parts)[:-3]  # strip '.py'
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            # X = pkg.something.X
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if value is None:
                continue
            if not (isinstance(value, ast.Attribute) and isinstance(value.value, ast.Attribute | ast.Name)):
                continue
            # unparse RHS to get full dotted path
            rhs = ast.unparse(value)
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
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        # the consumer is itself a module; do not flag the canonical or shim
        rel_parts = path.relative_to(src_root).parts
        if rel_parts[-1] == '__init__.py':
            consumer_mod = package_root_name + '.' + '.'.join(rel_parts[:-1]) if len(rel_parts) > 1 else package_root_name
        else:
            consumer_mod = package_root_name + '.' + '.'.join(rel_parts)[:-3]
        if consumer_mod in shims:
            continue
        lines = auditme.core.source_lines(path)
        for node in ast.walk(tree):
            # Pattern 1: `from <shim_mod> import X` where X has a canonical home elsewhere
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module in shims:
                    for alias in node.names:
                        for sym, canonical_mod in shims[node.module]:
                            if alias.name == sym and canonical_mod != node.module:
                                accept = auditme.core.accept_reason(lines, node.lineno, rule='migration-shim-consumer')
                                auditme.core.emit(
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
                full = ast.unparse(node)
                if not full.startswith(package_root_name + '.'):
                    continue
                # Split into module-prefix and attr
                parent_mod, _, attr = full.rpartition('.')
                if parent_mod in shims:
                    for sym, canonical_mod in shims[parent_mod]:
                        if attr == sym and canonical_mod != parent_mod:
                            line_no = getattr(node, 'lineno', 1)
                            accept = auditme.core.accept_reason(lines, line_no, rule='migration-shim-consumer')
                            auditme.core.emit(
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
    for path in auditme.core.all_py_files(src_root):
        if path.name == '__init__.py':
            continue
        rel = auditme.core.relpath(path, scope)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        lines = auditme.core.source_lines(path)
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
            rhs_src = ast.unparse(node.value)
            accept = auditme.core.accept_reason(lines, node.lineno, rule='reexport-in-non-init')
            auditme.core.emit(
                rule='reexport-in-non-init',
                variant=f'`{tgt.id} = {rhs_src}` at module scope in non-__init__.py file',
                path=rel,
                line=node.lineno,
                evidence=(lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


ALL_GUARD_RE = re.compile(r"""['"]__all__['"]|\.__all__\b""")


def project_has_all_guard(scope: pathlib.Path) -> bool:
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
        text = auditme.core.read_source(path)
        if text is None:
            continue
        if ALL_GUARD_RE.search(text):
            return True
    return False


def check_annotated_all_assignment(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `__all__: list[str] = [...]` in a project that guards `__all__`.

    An annotated assignment is an `ast.AnnAssign`, not an `ast.Assign`. A
    public-surface guard written to match `ast.Assign` therefore does not see
    the module at all - and reports green while checking nothing, which is the
    worst failure a guard has. On one project this switched the guard off for a
    whole package: its `__all__` entries were never checked for a consumer, and
    the private-submodule exception entries written for it were inert, while
    the suite passed throughout.

    The predicate is not "an annotated `__all__` is wrong". It is that a
    project whose surface guard may discriminate on assignment form has a hole
    wherever the annotated form appears. A guard that handles both forms is a
    real answer - record it with an accept marker on the declaration, or
    normalise the declaration to the plain form.

    Fires only where the project has an `__all__`-based guard at all; see
    `project_has_all_guard`.
    """
    if not project_has_all_guard(scope):
        return
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.AnnAssign):
                continue
            if not isinstance(node.target, ast.Name) or node.target.id != '__all__':
                continue
            accept = auditme.core.accept_reason(lines, node.lineno, rule='annotated-all-assignment')
            auditme.core.emit(
                rule='annotated-all-assignment',
                variant='__all__ is an AnnAssign; a guard matching ast.Assign skips this module',
                path=rel,
                line=node.lineno,
                evidence=lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else ast.unparse(node),
                accepted=bool(accept),
                accepted_reason=accept,
            )


__all__ = [
    'check_annotated_all_assignment',
    'check_as_import',
    'check_def_class_in_init',
    'check_empty_init_with_exporting_siblings',
    'check_from_import',
    'check_in_function_imports',
    'check_layering_violations',
    'check_migration_shim_consumers',
    'check_passthrough_shim',
    'check_reexport_in_non_init',
    'check_unused_submodule_imports',
]
