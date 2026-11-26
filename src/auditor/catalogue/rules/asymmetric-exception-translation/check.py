import ast
import collections
import collections.abc
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def raising_call_roots(tree: ast.Module, package_root_name: str) -> frozenset[str]:
    """Names bound by an import of a module from outside the swept package."""
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.partition('.')[0] != package_root_name:
                    roots.add(alias.asname or alias.name.partition('.')[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and node.module.partition('.')[0] != package_root_name:
            roots.update(alias.asname or alias.name for alias in node.names)
    return frozenset(roots)


def has_something_to_translate(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    external_roots: frozenset[str],
    module_functions: frozenset[str],
    envelopes: collections.abc.Mapping[str, frozenset[str]],
) -> bool:
    """True when the function's own body can raise what callers translate.

    That is a call to a filesystem-touching name, a subprocess call, or a call
    rooted at a module imported from outside the package. A body that calls a
    same-module translating function translates through it and gives False.
    """
    raises = False
    for stmt in node.body:
        for sub in (stmt, *auditor.api.walk_within_scope(stmt)):
            if not isinstance(sub, ast.Call):
                continue
            func = sub.func
            short = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if isinstance(func, ast.Name) and short in module_functions and short in envelopes:
                return False
            root = func
            while isinstance(root, (ast.Attribute, ast.Call, ast.Subscript)):
                root = root.func if isinstance(root, ast.Call) else root.value
            if short in auditor.api.FILESYSTEM_TOUCHING_CALLS or (isinstance(root, ast.Name) and root.id in external_roots):
                raises = True
    return raises


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Detect functions F such that:
      - F is a module-level (or public-looking) function that itself does
        NOT have a try/except around its body translating third-party
        exceptions to a project error class.
      - Every known call site of F is inside a `try: ... except <ProjectError>: ...`
        block that catches a third-party exception class and translates.
      - There are 2+ call sites with this shape.

    The asymmetric contract is a smell: a new caller that doesn't wrap F
    will leak the third-party exception. Mechanical signal the finding.

    F must also have something to translate: its own body (nested defs
    skipped) calls a filesystem-touching name or a module imported from outside
    the package, and does not call a same-module translating function.
    """
    # First pass: enumerate every module-level function and whether its body
    # contains a top-level try/except handler.
    function_index: dict[str, tuple[str, int, bool]] = {}
    translatable: set[str] = set()
    envelopes = auditor.api.translator_envelopes(src_root)
    # function_index key is full dotted path (e.g. 'pkg.registry.runs.setup_experiment')
    package_root_name = src_root.name

    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        rel = auditor.api.relpath(path, scope)
        rel_parts = path.relative_to(src_root).parts
        if rel_parts[-1] == '__init__.py':
            mod = package_root_name + '.' + '.'.join(rel_parts[:-1]) if len(rel_parts) > 1 else package_root_name
        else:
            mod = package_root_name + '.' + '.'.join(rel_parts)[:-3]
        external_roots = raising_call_roots(tree, package_root_name)
        module_functions = frozenset(n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if has_something_to_translate(node, external_roots, module_functions, envelopes):
                translatable.add(f'{mod}.{node.name}')
            # Check if function's OWN body has a try/except that catches anything
            has_own_try = any(isinstance(child, ast.Try) for child in node.body)
            function_index[f'{mod}.{node.name}'] = (rel, node.lineno, has_own_try)

    # Second pass: for every call to a known function, check the surrounding
    # context. If every call site in the project is inside a `try: ...
    # except <something>:` block AND the function itself has no try, flag.
    call_sites: dict[str, list[tuple[str, int, bool]]] = collections.defaultdict(list)
    # key: callee full dotted path; value: list of (caller_path, lineno, is_wrapped)

    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        rel = auditor.api.relpath(path, scope)
        # Track which nodes are inside a try block
        try_descendants: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                # Does this try have a handler that looks like it translates to
                # a ProjectError (a class name ending in 'Error' defined in this
                # package)? We only care about try blocks whose handlers raise
                # something that ends in 'Error'.
                translates = False
                for handler in node.handlers:
                    # Inspect handler body for `raise <Something>Error(...)`
                    for sub in ast.walk(handler):
                        if isinstance(sub, ast.Raise) and isinstance(sub.exc, ast.Call):
                            raised = ast.unparse(sub.exc.func)
                            # name ends in 'Error' or similar
                            tail = raised.rsplit('.', 1)[-1]
                            if tail.endswith('Error'):
                                translates = True
                                break
                    if translates:
                        break
                if translates:
                    for child in node.body:
                        for sub in ast.walk(child):
                            if hasattr(sub, 'lineno'):
                                try_descendants.add(id(sub))
        # Now walk every Call node and check its callee
        # We need to resolve callee to a full dotted path. Use ast.unparse.
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee_src = ast.unparse(node.func)
            # Look up in function_index: match any entry whose suffix == callee_src
            # or whose full dotted path == callee_src
            callee_candidates = []
            if callee_src in function_index:
                callee_candidates.append(callee_src)
            else:
                # match `short_name` against entries where dotted path ends in `.short_name`
                for full in function_index:
                    if full.endswith('.' + callee_src):
                        callee_candidates.append(full)
            for callee in callee_candidates:
                is_wrapped = id(node) in try_descendants
                call_sites[callee].append((rel, node.lineno, is_wrapped))

    # Third pass: emit findings
    for callee, sites in call_sites.items():
        if len(sites) < 2:
            continue
        callee_path, callee_line, callee_has_try = function_index[callee]
        if callee_has_try or callee not in translatable:
            continue
        if not all(is_wrapped for (_, _, is_wrapped) in sites):
            continue
        # Every call site is wrapped; the function itself has no try.
        accept = auditor.api.accept_reason(auditor.api.source_lines(scope / callee_path), callee_line, rule='asymmetric-exception-translation')
        sites_summary = '; '.join(f'{p}:{n}' for (p, n, _) in sites[:5])
        auditor.api.emit(
            related=[p for (p, _, _) in sites],
            rule='asymmetric-exception-translation',
            variant=f'{callee} has no own try/except; all {len(sites)} callers wrap it',
            path=callee_path,
            line=callee_line,
            evidence=f'called (wrapped) from: {sites_summary}',
            accepted=bool(accept),
            accepted_reason=accept,
        )
