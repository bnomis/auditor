"""Checks on exception handling, error translation and failure reporting."""

import ast
import collections
import collections.abc
import contextlib
import re
import typing

import auditme.core

if typing.TYPE_CHECKING:
    import pathlib

BARE_HANDLER_MARK = '*bare*'
ERRORS_MODULE_NAMES = frozenset({'__init__.py', 'errors.py'})
# A chain of one empty step: the error is raised in the function itself.
RAISED_HERE: tuple[str, ...] = ('',)


def is_broad_handler(handler: ast.ExceptHandler) -> bool:
    """True for a bare `except:` and for `Exception` or `BaseException`,
    alone or inside a tuple."""
    exc = handler.type
    if exc is None:
        return True
    if isinstance(exc, ast.Name):
        names = [exc.id]
    elif isinstance(exc, ast.Tuple):
        names = [e.id for e in exc.elts if isinstance(e, ast.Name)]
    else:
        return False
    return any(n in BROAD_HANDLER_NAMES for n in names)


def check_silent_broad_except(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a broad `except` handler that neither logs nor raises.

    Signal: a handler for a bare `except:`, `Exception` or `BaseException`
    (alone or in a tuple) whose body holds no `logger.`, `loguru.logger.` or
    `logging.` text and no `raise` statement anywhere inside it. Carve-outs:
    a handler naming only narrower exceptions; a file that does not parse.
    """
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if not is_broad_handler(node):
                continue
            body_src = '\n'.join(ast.unparse(c) for c in node.body) if hasattr(ast, 'unparse') else ''
            has_log = bool(re.search(r'\blogger\.|loguru\.logger\.|logging\.', body_src))
            has_raise = any(isinstance(c, ast.Raise) for c in ast.walk(node))
            if has_log or has_raise:
                continue
            accept = auditme.core.accept_reason(lines, node.lineno, rule='silent-broad-except')
            auditme.core.emit(
                rule='silent-broad-except',
                variant='no logger and no raise in body',
                path=rel,
                line=node.lineno,
                evidence=lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else '',
                accepted=bool(accept),
                accepted_reason=accept,
            )


def stmt_end_by_lineno(tree: ast.AST) -> dict[int, int]:
    """Map each source line to the max end_lineno of any statement enclosing it."""
    mapping: dict[int, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            for ln in range(node.lineno, node.end_lineno + 1):
                if mapping.get(ln, 0) < node.end_lineno:
                    mapping[ln] = node.end_lineno
    return mapping


def is_categorical_class_name_expr(expr_src: str, bound: str) -> bool:
    """Return True when expr_src is a categorical class-name access on the
    bound exception name (e.g. ``type(exc).__name__`` or
    ``exc.__class__.__qualname__``). These patterns expose only the
    exception class string, not the lossy ``str(exc)`` message body, and
    do not duplicate the chained traceback that ``raise ... from exc``
    or ``logger.exception`` already preserve.
    """
    SAFE_ATTRS = ('__name__', '__qualname__')
    bound_re = re.escape(bound)
    patterns = [rf'^type\(\s*{bound_re}\s*\)\.{attr}$' for attr in SAFE_ATTRS]
    patterns += [rf'^{bound_re}\.__class__\.{attr}$' for attr in SAFE_ATTRS]
    return any(re.match(p, expr_src.strip()) for p in patterns)


def check_except_interpolation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag f-string or logger-positional interpolation of a caught
    exception variable inside an ``except ... as <bound>:`` block.
    Rationale: ``raise X from exc`` and ``logger.exception(...)`` already
    preserve the chained traceback at full fidelity; embedding
    ``str(exc)`` (or its f-string equivalent) into a new message
    produces a truncated copy that drifts from the original.

    Exception: ``type(<bound>).__name__`` / ``__qualname__``
    and ``<bound>.__class__.__name__`` / ``__qualname__`` access only
    the exception class name string. The class name is a categorical
    hint, not a lossy duplication of the message body, so these
    patterns are skipped without emitting a hit. See
    ``is_categorical_class_name_expr``.
    """
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        stmt_end = stmt_end_by_lineno(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler) or not node.name:
                continue
            bound = node.name
            seen_linenos: set[tuple[int, str]] = set()
            for inner in ast.walk(node):
                if isinstance(inner, ast.JoinedStr):
                    flagged = False
                    for v in inner.values:
                        if flagged:
                            break
                        if isinstance(v, ast.FormattedValue):
                            expr_src = ast.unparse(v.value) if hasattr(ast, 'unparse') else ''
                            if not re.search(rf'\b{re.escape(bound)}\b', expr_src):
                                continue
                            if is_categorical_class_name_expr(expr_src, bound):
                                continue
                            key = (inner.lineno, 'fstring')
                            if key in seen_linenos:
                                flagged = True
                                break
                            seen_linenos.add(key)
                            end_ln = stmt_end.get(inner.lineno)
                            accept = auditme.core.accept_reason(lines, inner.lineno, end_ln, rule='except-interpolation')
                            auditme.core.emit(
                                rule='except-interpolation',
                                variant='f-string interpolates caught exception',
                                path=rel,
                                line=inner.lineno,
                                evidence=(lines[inner.lineno - 1].strip()[:200] if inner.lineno <= len(lines) else ''),
                                accepted=bool(accept),
                                accepted_reason=accept,
                            )
                            flagged = True
                            break
                if isinstance(inner, ast.Call):
                    func_src = ast.unparse(inner.func) if hasattr(ast, 'unparse') else ''
                    if re.search(r'logger\.(warning|error|exception)$', func_src):
                        for arg in inner.args:
                            arg_src = ast.unparse(arg) if hasattr(ast, 'unparse') else ''
                            if re.fullmatch(rf'\s*{re.escape(bound)}\s*', arg_src):
                                key = (inner.lineno, 'logger-arg')
                                if key in seen_linenos:
                                    continue
                                seen_linenos.add(key)
                                end_ln = stmt_end.get(inner.lineno)
                                accept = auditme.core.accept_reason(lines, inner.lineno, end_ln, rule='except-interpolation')
                                auditme.core.emit(
                                    rule='except-interpolation',
                                    variant='logger positional arg is caught exception',
                                    path=rel,
                                    line=inner.lineno,
                                    evidence=(lines[inner.lineno - 1].strip()[:200] if inner.lineno <= len(lines) else ''),
                                    accepted=bool(accept),
                                    accepted_reason=accept,
                                )


def check_broad_except_wrong_level(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `except (Exception|BaseException):` blocks whose body calls
    logger.warning / logger.error / logger.debug / logger.info instead of
    logger.exception. Distinct from check_silent_broad_except, which only
    catches blocks with NO logger call at all.

    A broad handler that logs and returns a default is caught here at
    `warning` and by `logger-exception-graceful-degradation` at `exception`.
    SKILL.md's "Conflicts with no winner" rules on it: remove or narrow the
    handler rather than change its level."""
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if not is_broad_handler(node):
                continue
            body_src = '\n'.join(ast.unparse(c) for c in node.body) if hasattr(ast, 'unparse') else ''
            wrong_level = re.search(r'\b(logger|loguru\.logger|logging)\.(warning|error|info|debug)\(', body_src)
            if not wrong_level:
                continue
            accept = auditme.core.accept_reason(lines, node.lineno, rule='broad-except-wrong-level')
            auditme.core.emit(
                rule='broad-except-wrong-level',
                variant='broad except logs at warning/error/info/debug instead of exception',
                path=rel,
                line=node.lineno,
                evidence=lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else '',
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_mixed_raise_types(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag methods/functions that raise two or more different exception
    types where the types do not share a clear inheritance relationship.
    A common architecture smell: half the invariants raise PipelineError,
    half raise stdlib RuntimeError - callers cannot establish a clean
    catch envelope."""
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            raised_types: dict[str, list[int]] = collections.defaultdict(list)
            for inner in ast.walk(node):
                if isinstance(inner, ast.Raise) and isinstance(inner.exc, ast.Call):
                    fn = inner.exc.func
                    if isinstance(fn, ast.Name):
                        raised_types[fn.id].append(inner.lineno)
                    elif isinstance(fn, ast.Attribute):
                        with contextlib.suppress(Exception):
                            raised_types[ast.unparse(fn).split('.')[-1]].append(inner.lineno)
            if len(raised_types) < 2:
                continue
            # exclude common cases where the mix is intentional: re-raise of
            # input-validation distinct from internal invariants is signalled
            # by error suffix matching: ConfigError + InputEnvelopeError is one
            # cluster; RuntimeError + PipelineError is a real mix
            STDLIB_EXCS = {'RuntimeError', 'ValueError', 'TypeError', 'KeyError', 'IndexError', 'AttributeError'}
            project_excs = {n for n in raised_types if n.endswith('Error') and n not in STDLIB_EXCS}
            if not project_excs:
                continue
            mixed_with_stdlib = STDLIB_EXCS & raised_types.keys()
            if not mixed_with_stdlib:
                continue
            # Emit ONE finding per function, listing every raise site
            sample_line = sorted(min(v) for v in raised_types.values())[0]
            accept = auditme.core.accept_reason(lines, sample_line, rule='mixed-raise-types')
            evidence = f'{node.name}: raises {sorted(raised_types.keys())}'
            auditme.core.emit(
                rule='mixed-raise-types',
                variant=f'{node.name} mixes stdlib ({sorted(mixed_with_stdlib)}) with project errors ({sorted(project_excs)})',
                path=rel,
                line=node.lineno,
                evidence=evidence,
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_asymmetric_exception_translation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Detect functions F such that:
      - F is a module-level (or public-looking) function that itself does
        NOT have a try/except around its body translating third-party
        exceptions to a project error class.
      - Every known call site of F is inside a `try: ... except <ProjectError>: ...`
        block that catches a third-party exception class and translates.
      - There are 2+ call sites with this shape.

    The asymmetric contract is a smell: a new caller that doesn't wrap F
    will leak the third-party exception. Mechanical signal the finding.
    """
    # First pass: enumerate every module-level function and whether its body
    # contains a top-level try/except handler.
    function_index: dict[str, tuple[str, int, bool]] = {}
    # function_index key is full dotted path (e.g. 'pkg.registry.runs.setup_experiment')
    package_root_name = src_root.name

    for path in auditme.core.all_py_files(src_root):
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        rel = auditme.core.relpath(path, scope)
        rel_parts = path.relative_to(src_root).parts
        if rel_parts[-1] == '__init__.py':
            mod = package_root_name + '.' + '.'.join(rel_parts[:-1]) if len(rel_parts) > 1 else package_root_name
        else:
            mod = package_root_name + '.' + '.'.join(rel_parts)[:-3]
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Check if function's OWN body has a try/except that catches anything
            has_own_try = any(isinstance(child, ast.Try) for child in node.body)
            function_index[f'{mod}.{node.name}'] = (rel, node.lineno, has_own_try)

    # Second pass: for every call to a known function, check the surrounding
    # context. If every call site in the project is inside a `try: ...
    # except <something>:` block AND the function itself has no try, flag.
    call_sites: dict[str, list[tuple[str, int, bool]]] = collections.defaultdict(list)
    # key: callee full dotted path; value: list of (caller_path, lineno, is_wrapped)

    for path in auditme.core.all_py_files(src_root):
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        rel = auditme.core.relpath(path, scope)
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
        if callee_has_try:
            continue
        if not all(is_wrapped for (_, _, is_wrapped) in sites):
            continue
        # Every call site is wrapped; the function itself has no try.
        accept = auditme.core.accept_reason(auditme.core.source_lines(scope / callee_path), callee_line, rule='asymmetric-exception-translation')
        sites_summary = '; '.join(f'{p}:{n}' for (p, n, _) in sites[:5])
        auditme.core.emit(
            related=[p for (p, _, _) in sites],
            rule='asymmetric-exception-translation',
            variant=f'{callee} has no own try/except; all {len(sites)} callers wrap it',
            path=callee_path,
            line=callee_line,
            evidence=f'called (wrapped) from: {sites_summary}',
            accepted=bool(accept),
            accepted_reason=accept,
        )


def check_sibling_error_no_common_base(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Detect project error classes that sit side-by-side in a `*/errors.py`
    module but have different base classes (one subclasses ProjectError,
    another subclasses stdlib Exception). The mismatch is a smell:
    existing `except ProjectError` catch sites will miss the sibling.

    Signal:
      - A file named `errors.py` defines >= 2 classes whose names end in
        `Error`.
      - At least one of the classes subclasses a project-local error base
        (any name ending in 'Error' that is not stdlib Exception).
      - At least one of the classes subclasses stdlib `Exception`
        (or has no explicit base).
      - The two groups are not related by inheritance within the file.

    A common mistake is defining `SignatureError(Exception)` next to
    `RegistryError(Exception)` without making them share a hierarchy.
    Call sites that catch `RegistryError` never catch `SignatureError`.
    """
    for path in auditme.core.all_py_files(src_root):
        if path.name != 'errors.py':
            continue
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        error_classes: list[tuple[str, int, list[str]]] = []
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith('Error'):
                continue
            base_names: list[str] = []
            for base in node.bases:
                with contextlib.suppress(Exception):
                    base_names.append(ast.unparse(base))
            error_classes.append((node.name, node.lineno, base_names))
        if len(error_classes) < 2:
            continue
        # Partition into "rooted at stdlib Exception" vs "rooted at a
        # project Error parent"
        rooted_at_stdlib: list[tuple[str, int, list[str]]] = []
        rooted_at_project: list[tuple[str, int, list[str]]] = []
        for name, lineno, bases in error_classes:
            if not bases or any(b.split('.')[-1] == 'Exception' for b in bases):
                rooted_at_stdlib.append((name, lineno, bases))
            elif any(b.split('.')[-1].endswith('Error') for b in bases):
                # If the base is one of the other classes defined in this file,
                # that's a real hierarchy; otherwise it's a new root
                sibling_names = {n for n, _, _ in error_classes}
                if any(b.split('.')[-1] in sibling_names for b in bases):
                    rooted_at_project.append((name, lineno, bases))
                else:
                    rooted_at_stdlib.append((name, lineno, bases))
            else:
                rooted_at_stdlib.append((name, lineno, bases))
        if len(rooted_at_stdlib) < 2:
            continue
        # At least two sibling roots. Emit one finding per class whose
        # sibling is not caught together by any call site.
        # Build set of classes actually used in except clauses anywhere in the tree.
        caught_elsewhere: dict[str, set[str]] = collections.defaultdict(set)
        for src in auditme.core.all_py_files(src_root):
            other_tree = auditme.core.read_and_parse(src)
            if other_tree is None:
                continue
            for sub in ast.walk(other_tree):
                if not isinstance(sub, ast.ExceptHandler):
                    continue
                if sub.type is None:
                    continue
                type_src = ast.unparse(sub.type)
                for caught in re.findall(r'[a-zA-Z_.][a-zA-Z0-9_.]*', type_src):
                    tail = caught.split('.')[-1]
                    caught_elsewhere[tail].add(auditme.core.relpath(src, scope))
        # Find the two classes most likely to belong together: if a class C
        # is caught at site S and a sibling D in the same file is never
        # caught together at S, D leaks.
        sibling_names = {name for name, _, _ in rooted_at_stdlib}
        if len(sibling_names) < 2:
            continue
        # Emit one finding per file naming all co-defined siblings.
        first_name, first_line, _ = rooted_at_stdlib[0]
        accept = auditme.core.accept_reason(lines, first_line, rule='sibling-errors-no-common-base')
        auditme.core.emit(
            rule='sibling-errors-no-common-base',
            variant=f'{len(sibling_names)} Error classes co-defined with no shared parent: {sorted(sibling_names)}',
            path=rel,
            line=first_line,
            evidence=f'classes: {", ".join(sorted(sibling_names))}',
            accepted=bool(accept),
            accepted_reason=accept,
        )


def check_cli_entry_missing_error_envelope(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag CLI entry-point functions (top-level functions in `cli/*.py`
    whose name starts with `run_`) that have no top-level try/except.

    The rule: if at least one sibling CLI entry in the project does have
    a top-level try/except catching a project error class, flag every
    CLI entry that does not. CLI entries are the error envelope for
    user-facing errors; an unenveloped entry will surface untranslated
    third-party exceptions.
    """
    cli_dir = src_root / 'cli'
    if not cli_dir.is_dir():
        return
    # First pass: enumerate all CLI run_* entries and whether they wrap
    # something in a top-level try/except.
    entries: list[tuple[str, int, str, bool]] = []  # (path, lineno, fname, has_outer_try)
    for path in sorted(cli_dir.rglob('*.py')):
        if path.name == '__init__.py':
            continue
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith('run_'):
                continue
            # Only consider true CLI dispatch entries. Heuristics to
            # exclude helper functions in cli/*.py:
            #   - return annotation is `int` (CLI commands return an
            #     exit code)
            #   - OR has a parameter annotated with a name ending in
            #     `.App` / `.Cmd` / any cappa dispatcher root (the
            #     dispatcher-aware second argument)
            returns_int = False
            if node.returns is not None:
                if ast.unparse(node.returns).strip() == 'int':
                    returns_int = True
            # params whose annotation string contains a capitalised cappa
            # command class (the `parent: 'pkg.cli.app.App'` style)
            has_cappa_param = False
            for arg in node.args.args:
                if arg.annotation is None:
                    continue
                ann_src = ast.unparse(arg.annotation)
                if re.search(r"\.[A-Z]\w+['\"]?$", ann_src.strip('\'"')):
                    has_cappa_param = True
                    break
            if not (returns_int or has_cappa_param):
                continue
            # Is there any Try in the function body? (Any depth.) The
            # rule is: CLI entry must have at least one try/except
            # somewhere to be considered "enveloped".
            has_try = any(isinstance(sub, ast.Try) for sub in ast.walk(node))
            entries.append((rel, node.lineno, node.name, has_try))
    if not entries:
        return
    # If at least one entry has a try/except, any entry without one is flagged.
    any_has_try = any(has_try for (_, _, _, has_try) in entries)
    if not any_has_try:
        return
    for rel, lineno, fname, has_try in entries:
        if has_try:
            continue
        full = scope / rel
        lines = auditme.core.source_lines(full)
        accept = auditme.core.accept_reason(lines, lineno, rule='cli-entry-missing-error-envelope')
        auditme.core.emit(
            rule='cli-entry-missing-error-envelope',
            variant=f'{fname} has no top-level try/except',
            path=rel,
            line=lineno,
            evidence=f'def {fname}(...): (no try/except; siblings do wrap)',
            accepted=bool(accept),
            accepted_reason=accept,
        )


def check_try_wrapping_with_too_broad(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `try: with X(): body...` patterns where the except handler
    re-invokes work that was inside the `with` body, assuming the
    exception came from `__enter__`.

    Signal:
      - An `ast.Try` node whose body starts with an `ast.With` block.
      - The `with` body contains one or more call statements.
      - The `except` handler body itself contains at least one call
        whose callee name matches a callee inside the `with` body.
      - The handler's intent (per comments/log messages) is startup
        failure - but the catch will also fire for any exception raised
        inside the `with` body.

    The `run_batch` double-run: `try: with open_batch_run(): run_pipeline_and_finalise(...)`
    catches `RegistryError`, and the handler calls `run_pipeline_and_finalise(...)`
    again. If `RegistryError` escapes from the `with` body (not startup),
    the pipeline runs twice.
    """
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            if not node.body:
                continue
            # First statement is a `with`
            first = node.body[0]
            if not isinstance(first, ast.With):
                continue
            # Collect call names in the with-body
            with_body_callees: set[str] = set()
            for stmt in first.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Call):
                        callee = ast.unparse(sub.func)
                        short = callee.rsplit('.', 1)[-1]
                        with_body_callees.add(short)
            if not with_body_callees:
                continue
            # Collect call names in each handler's body
            for handler in node.handlers:
                handler_callees: set[str] = set()
                for stmt in handler.body:
                    for sub in ast.walk(stmt):
                        if isinstance(sub, ast.Call):
                            callee = ast.unparse(sub.func)
                            short = callee.rsplit('.', 1)[-1]
                            handler_callees.add(short)
                # Overlap of non-trivial callees
                overlap = {
                    c
                    for c in with_body_callees & handler_callees
                    # Skip logger/print/etc. noise
                    if c not in {'warning', 'info', 'error', 'exception', 'debug', 'print', 'format', 'str', 'repr', 'len'}
                    # Skip class / exception constructors (CamelCase) -
                    # they are error construction, not "work".
                    and not (c[:1].isupper() if c else True)
                }
                if not overlap:
                    continue
                accept = auditme.core.accept_reason(lines, handler.lineno, rule='try-wrapping-with-block-too-broad')
                auditme.core.emit(
                    rule='try-wrapping-with-block-too-broad',
                    variant=f'except handler re-invokes {sorted(overlap)!r} from the wrapped `with` body',
                    path=rel,
                    line=handler.lineno,
                    evidence=(lines[handler.lineno - 1].strip()[:200] if handler.lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


def check_layer_has_domain_error_but_raises_stdlib(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag modules that raise stdlib exceptions (ValueError, RuntimeError,
    TypeError, KeyError) for domain errors when a sibling `errors.py` in
    the same package defines a domain-error class.

    Signal:
      - Package P contains an `errors.py` defining at least one `*Error`
        class.
      - Another module M in the same package P raises a stdlib exception
        (ValueError, RuntimeError, TypeError, KeyError) at module-level
        or function scope.
      - The stdlib raise is NOT inside an `except` block (which is the
        re-raise-with-narrower-type pattern and is fine).

    Scope rationale: the "widen to any module that imports a
    domain `*Error` lazily" variant was tried and discarded because it
    over-fired on `config/structures.py.__post_init__` validation raises,
    which AGENTS.md's "Error type policy by layer" permits (`config` has
    no own `*Error` class and only lazily imports `PipelineError` for a
    narrow cross-stage violation). The narrower same-package predicate is
    the stable form.
    """
    STDLIB_EXCS = {'ValueError', 'RuntimeError', 'KeyError'}
    # First pass: find every package with a domain error class
    package_has_domain_error: set[tuple[str, ...]] = set()
    for path in auditme.core.all_py_files(src_root):
        if path.name != 'errors.py':
            continue
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.endswith('Error'):
                pkg = path.relative_to(src_root).parts[:-1]
                package_has_domain_error.add(pkg)
                break

    if not package_has_domain_error:
        return

    # Second pass: walk every module raising stdlib errors
    for path in auditme.core.all_py_files(src_root):
        if path.name in ERRORS_MODULE_NAMES:
            continue
        pkg = path.relative_to(src_root).parts[:-1]
        if pkg not in package_has_domain_error:
            continue
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        # Track which Raise nodes are inside an except block
        except_bodies: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                for child in ast.walk(node):
                    if hasattr(child, 'lineno'):
                        except_bodies.add(child.lineno)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise):
                continue
            if node.lineno in except_bodies:
                continue
            exc_call = node.exc
            exc_name = None
            if isinstance(exc_call, ast.Call):
                if isinstance(exc_call.func, ast.Name):
                    exc_name = exc_call.func.id
            elif isinstance(exc_call, ast.Name):
                exc_name = exc_call.id
            if exc_name not in STDLIB_EXCS:
                continue
            accept = auditme.core.accept_reason(lines, node.lineno, rule='layer-has-domain-error-raises-stdlib')
            auditme.core.emit(
                rule='layer-has-domain-error-raises-stdlib',
                variant=f'{pkg[-1] if pkg else "(root)"} package defines *Error classes but this module raises {exc_name}',
                path=rel,
                line=node.lineno,
                evidence=(lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_inconsistent_error_translation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag helper functions F that raise a domain error E, where two or
    more distinct callers of F translate E to different project-error
    classes. Divergent translation is a semantic bug: the same
    underlying failure surfaces as different error types to different
    consumers.

    Signal:
      - Function F at path P has at least one `raise <E>(...)` where E
        ends in `Error` (a project domain error).
      - Two or more functions elsewhere call F, each wrapping the call
        in a `try: ... except <E>: raise <T_i>(...)` where the raised
        translation target classes T_i differ across callers.
    """
    package_root_name = src_root.name

    # Pass 1: for each module-level function, enumerate the *Error classes
    # it raises directly (i.e. not via re-raise of a caught exception).
    function_raises: dict[str, set[str]] = collections.defaultdict(set)
    function_path_line: dict[str, tuple[str, int]] = {}
    for path in auditme.core.all_py_files(src_root):
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        rel = auditme.core.relpath(path, scope)
        rel_parts = path.relative_to(src_root).parts
        if rel_parts[-1] == '__init__.py':
            continue
        mod = package_root_name + '.' + '.'.join(rel_parts)[:-3]
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            key = f'{mod}.{node.name}'
            function_path_line[key] = (rel, node.lineno)
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Raise) or inner.exc is None:
                    continue
                target = inner.exc.func if isinstance(inner.exc, ast.Call) else inner.exc
                if isinstance(target, (ast.Name, ast.Attribute)):
                    src = ast.unparse(target)
                    tail = src.rsplit('.', 1)[-1]
                    if tail.endswith('Error'):
                        function_raises[key].add(tail)

    if not function_raises:
        return

    # Short-name lookup
    short_to_full: dict[str, set[str]] = collections.defaultdict(set)
    for key in function_raises:
        short = key.rsplit('.', 1)[-1]
        short_to_full[short].add(key)

    # Pass 2: for every call site of a function in function_raises, find
    # the enclosing try/except and the translation target if any.
    translations: dict[str, dict[str, set[str]]] = collections.defaultdict(lambda: collections.defaultdict(set))
    # translations[callee_full][caught_error] = set of translated target classes
    for path in auditme.core.all_py_files(src_root):
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            # find calls inside the try body to known functions
            for body_stmt in node.body:
                for sub in ast.walk(body_stmt):
                    if not isinstance(sub, ast.Call):
                        continue
                    callee = ast.unparse(sub.func)
                    short = callee.rsplit('.', 1)[-1]
                    for full in short_to_full.get(short, set()):
                        caught_classes: set[str] = set()
                        for h in node.handlers:
                            if h.type is None:
                                continue
                            type_src = ast.unparse(h.type)
                            for caught in re.findall(r'[A-Za-z_][A-Za-z_0-9]*', type_src):
                                if caught.endswith('Error'):
                                    caught_classes.add(caught)
                        # For each caught class that the callee actually raises,
                        # record the translation target(s)
                        for caught in caught_classes:
                            if caught not in function_raises.get(full, set()):
                                continue
                            for h in node.handlers:
                                if h.type is None:
                                    continue
                                h_src = ast.unparse(h.type)
                                if caught not in h_src:
                                    continue
                                for handler_stmt in h.body:
                                    for raisesub in ast.walk(handler_stmt):
                                        if not isinstance(raisesub, ast.Raise):
                                            continue
                                        if raisesub.exc is None:
                                            continue
                                        tgt = raisesub.exc.func if isinstance(raisesub.exc, ast.Call) else raisesub.exc
                                        if not isinstance(tgt, (ast.Name, ast.Attribute)):
                                            continue
                                        tgt_src = ast.unparse(tgt)
                                        tgt_tail = tgt_src.rsplit('.', 1)[-1]
                                        if tgt_tail.endswith('Error'):
                                            translations[full][caught].add(tgt_tail)

    # Pass 3: emit findings for callees whose domain error is translated
    # to 2+ distinct targets across the codebase.
    for callee_full, err_map in translations.items():
        for caught, targets in err_map.items():
            if len(targets) < 2:
                continue
            if callee_full not in function_path_line:
                continue
            rel, lineno = function_path_line[callee_full]
            full_path = scope / rel
            lines = auditme.core.source_lines(full_path)
            accept = auditme.core.accept_reason(lines, lineno, rule='inconsistent-error-translation')
            auditme.core.emit(
                rule='inconsistent-error-translation',
                variant=f'{callee_full} raises {caught}; callers translate to {sorted(targets)}',
                path=rel,
                line=lineno,
                evidence=f'{caught} -> {sorted(targets)}',
                accepted=bool(accept),
                accepted_reason=accept,
            )


# Callees that indicate the wrapped try-block touches local filesystem
# cache / does writing I/O. Catching only library-specific exceptions
# (MlflowException, BotoException, etc.) without also catching OSError
# leaks disk failures to callers.
THIRD_PARTY_FILESYSTEM_CALLS = frozenset(
    {
        # Third-party helpers that cache to disk / upload / download
        'download',
        'download_artifacts',
        'download_file',
        'from_pretrained',
        'log_artifact',
        'log_artifacts',
        'log_model',
        'push_to_hub',
        'save_model',
        'save_pretrained',
        'snapshot_download',
        'upload_artifacts',
        'upload_file',
    }
)
# `replace`, `rename`, `copy`, `remove` are intentionally omitted -
# `str.replace`, `dataclasses.replace`, `list.copy`, `dict.copy`,
# `list.remove` are overwhelmingly common; the false-positive rate
# on their bare names dominates.
STDLIB_FILESYSTEM_CALLS = frozenset(
    {
        # Pathlib / open / stdlib filesystem primitives used directly.
        'copytree',
        'makedirs',
        'mkdir',
        'read_bytes',
        'read_text',
        'rmdir',
        'rmtree',
        'symlink_to',
        'touch',
        'unlink',
        'write_bytes',
        'write_text',
    }
)
LIBRARY_READ_CALLS = frozenset(
    {
        # Common library read entry points that open the file under the hood
        'from_csv',
        'from_json',
        'read_csv',
        'read_excel',
        'read_feather',
        'read_hdf',
        'read_json',
        'read_parquet',
        'read_pickle',
        'read_sql',
        'read_sql_query',
        'read_sql_table',
        'read_table',
    }
)
FILESYSTEM_TOUCHING_CALLS = THIRD_PARTY_FILESYSTEM_CALLS | STDLIB_FILESYSTEM_CALLS | LIBRARY_READ_CALLS


def module_tuple_constants(tree: ast.Module) -> dict[str, list[ast.expr]]:
    """Map each name assigned exactly once at module level, to a tuple
    literal, to that tuple's members. A name assigned more than once is left
    out: which value a handler sees depends on order, so it is not resolved."""
    counts: collections.Counter[str] = collections.Counter()
    tuples: dict[str, list[ast.expr]] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            targets, value = stmt.targets, stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            targets, value = [stmt.target], stmt.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                counts[target.id] += 1
                if isinstance(value, ast.Tuple):
                    tuples[target.id] = list(value.elts)
    return {name: members for name, members in tuples.items() if counts[name] == 1}


def package_class_parents(trees: collections.abc.Iterable[ast.Module]) -> dict[str, set[str]]:
    """Map each top-level class in the given modules to the names of its bases.

    A base written `mod.Base` is recorded as `Base`, so the table follows the
    package's own class tree by bare name. Modules are pooled: a class and its
    base may live in different ones. A class with no base maps to an empty set,
    so the keys are exactly the package's top-level class names."""
    parents: dict[str, set[str]] = collections.defaultdict(set)
    for tree in trees:
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                parents[node.name].update(ast.unparse(base).rsplit('.', 1)[-1] for base in node.bases if isinstance(base, (ast.Name, ast.Attribute)))
    return dict(parents)


def class_lineage(name: str, parents: collections.abc.Mapping[str, set[str]]) -> set[str]:
    """The name and every ancestor of it, transitively, in `parents`.

    A cycle terminates, and a name `parents` does not know is its own lineage."""
    seen = {name}
    stack = [name]
    while stack:
        for parent in parents.get(stack.pop(), ()):
            if parent not in seen:
                seen.add(parent)
                stack.append(parent)
    return seen


def check_filesystem_envelope_gap(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `try` blocks that call a filesystem-touching third-party
    helper (`download_artifacts`, `from_pretrained`, `snapshot_download`,
    etc.) where the `except` tuple does not include `OSError` (or a
    parent like `Exception`/`BaseException`).

    These helpers write to a local cache directory; disk-full,
    read-only, or permission-denied failures surface as `OSError` /
    `PermissionError`, not as the library's own exception. The narrow
    except clause lets those propagate past the wrapper's promise to
    translate to a project error class.

    Refinement (2026-11-01): a bare name in a handler's type, alone or inside
    a tuple, that names a module-level tuple literal assigned once in the same
    file is read as that tuple's members, one level deep, so
    `except READ_ERRORS:` with `READ_ERRORS = (OSError, ValueError)` is
    covered. Any other name - another module's, a call's result, a nested
    constant - keeps the name test. See `module_tuple_constants`.

    Refinement (2026-11-21): a `try` is flagged only when one of its handlers
    raises (`raise X`, with an exception), because the rationale is a wrapper
    that promises to translate. A handler that returns, continues or logs
    makes no such promise, so skipping a file on a decode error is not a gap.
    A bare `raise` re-raises the original and does not translate.
    """
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        constants = module_tuple_constants(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            # Does the body call any filesystem-touching helper?
            touched_fs = False
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if not isinstance(sub, ast.Call):
                        continue
                    short = None
                    if isinstance(sub.func, ast.Name):
                        short = sub.func.id
                    elif isinstance(sub.func, ast.Attribute):
                        short = sub.func.attr
                    if short in FILESYSTEM_TOUCHING_CALLS:
                        touched_fs = True
                        break
                if touched_fs:
                    break
            if not touched_fs:
                continue
            # Does ANY except handler catch OSError/Exception/BaseException?
            covers_os = False
            for handler in node.handlers:
                if handler.type is None:
                    covers_os = True
                    break
                elements = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
                resolved: list[ast.expr] = []
                for element in elements:
                    if isinstance(element, ast.Name) and element.id in constants:
                        resolved.extend(constants[element.id])
                    else:
                        resolved.append(element)
                type_src = ', '.join(ast.unparse(element) for element in resolved)
                names = set(re.findall(r'[A-Za-z_][A-Za-z_0-9]*', type_src))
                if {'OSError', 'Exception', 'BaseException', 'IOError', 'PermissionError', 'FileNotFoundError'} & names:
                    covers_os = True
                    break
            if covers_os:
                continue
            if not any(isinstance(sub, ast.Raise) and sub.exc is not None for handler in node.handlers for sub in ast.walk(handler)):
                continue
            # Emit a finding at the first handler's line so the reviewer
            # sees the narrow catch.
            first_handler = node.handlers[0] if node.handlers else None
            lineno = first_handler.lineno if first_handler is not None else node.lineno
            # List the caught classes for context
            caught = []
            for h in node.handlers:
                if h.type is None:
                    caught.append('<bare>')
                else:
                    with contextlib.suppress(Exception):
                        caught.append(ast.unparse(h.type))
            accept = auditme.core.accept_reason(lines, lineno, rule='filesystem-envelope-gap')
            auditme.core.emit(
                rule='filesystem-envelope-gap',
                variant=f'try block touches filesystem (download/from_pretrained/etc.) but except tuple {caught!r} omits OSError',
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


OS_ERROR_NAMES = frozenset({'BaseException', 'Exception', 'IOError', 'OSError'})


def enveloped_functions(tree: ast.Module) -> set[str]:
    """Names of module-level functions with a `try` whose handler covers `OSError`."""
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in auditme.core.walk_within_scope(node):
            if not isinstance(sub, ast.Try):
                continue
            for handler in sub.handlers:
                if handler.type is None:
                    names.add(node.name)
                    continue
                elements = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
                if any(isinstance(element, (ast.Name, ast.Attribute)) and ast.unparse(element).rsplit('.', 1)[-1] in OS_ERROR_NAMES for element in elements):
                    names.add(node.name)
    return names


def check_filesystem_op_without_envelope(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag public entry-point functions that perform filesystem writes
    (`write_text` / `write_bytes` / `mkdir` / `unlink` / `rmtree` / etc.)
    WITHOUT a surrounding try/except anywhere in the function body.

    Signal:
      - Function F lives in a package P whose `errors.py` defines at
        least one `*Error` class (so the layer has a domain error to
        translate to).
      - F is a PUBLIC entry point of the package: either exported from
        the package's `__init__.py` (via `__all__` or a `from .X import F`
        re-export), OR its docstring mentions `Raises` (signalling it is
        part of the package's error contract).
      - F calls a filesystem-write primitive
        (`write_text`, `write_bytes`, `mkdir`, `unlink`, `rmdir`,
        `touch`, `rmtree`, `makedirs`, `symlink_to`, `copytree`).
      - The call is not inside any `ast.Try` block within F.

    Internal utilities (functions called only by other functions in the
    same package) are NOT flagged - they legitimately let `OSError`
    propagate to a caller that holds the envelope.

    `filesystem-envelope-gap` catches the case where a try exists but
    the except tuple is too narrow. This check catches the case where
    no try exists at all AND the function is part of the package's
    public error contract.

    Refinement (2026-11-21): a call to a function defined in the same module
    whose own body wraps a call in a `try` with a handler for `OSError` (or
    `IOError`, `Exception`, `BaseException`, or a bare `except`) is not a
    filesystem primitive: the helper holds the envelope. A method call
    (`x.read_text()`) is never resolved this way, only a bare name.
    """
    # Drop `replace`, `rename`, `copy`, `remove` - too noisy due to
    # str.replace, dataclasses.replace, list.copy, list.remove etc.
    # `read_text` / `read_bytes` / `from_pretrained` added by a
    # predicate-extension decision: packages with a domain *Error must
    # envelope read-path IO too, not only writes.
    STDLIB_WRITE_CALLS = {
        'write_text',
        'write_bytes',
        'mkdir',
        'unlink',
        'rmdir',
        'touch',
        'rmtree',
        'makedirs',
        'symlink_to',
        'copytree',
        'read_text',
        'read_bytes',
        'from_pretrained',
    }
    # First pass: find every package with a domain error class
    package_has_domain_error: set[tuple[str, ...]] = set()
    for path in auditme.core.all_py_files(src_root):
        if path.name != 'errors.py':
            continue
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.endswith('Error'):
                pkg = path.relative_to(src_root).parts[:-1]
                package_has_domain_error.add(pkg)
                break
    if not package_has_domain_error:
        return

    # For each package with a domain error, collect the names exported
    # from its `__init__.py` (via __all__ or re-exports).
    package_exports: dict[tuple[str, ...], set[str]] = collections.defaultdict(set)
    for path in auditme.core.all_py_files(src_root):
        if path.name != '__init__.py':
            continue
        pkg = path.relative_to(src_root).parts[:-1]
        if pkg not in package_has_domain_error:
            continue
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id == '__all__':
                        if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    package_exports[pkg].add(elt.value)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    package_exports[pkg].add(alias.asname or alias.name)

    for path in auditme.core.all_py_files(src_root):
        if path.name in ERRORS_MODULE_NAMES:
            continue
        pkg = path.relative_to(src_root).parts[:-1]
        if pkg not in package_has_domain_error:
            continue
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        exports = package_exports.get(pkg, set())
        enveloped = enveloped_functions(tree)
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Public entry-point test: either exported from package
            # __init__ OR docstring mentions "Raises"
            is_exported = func.name in exports
            docstring = ast.get_docstring(func) or ''
            mentions_raises = bool(re.search(r'\bRaises?\b', docstring))
            if not (is_exported or mentions_raises):
                continue
            # Collect linenos inside any try block within this function
            try_linenos: set[int] = set()
            for sub in ast.walk(func):
                if isinstance(sub, ast.Try):
                    for stmt in sub.body:
                        for innersub in ast.walk(stmt):
                            if hasattr(innersub, 'lineno'):
                                try_linenos.add(innersub.lineno)
            # Walk for filesystem write calls
            for inner in ast.walk(func):
                if not isinstance(inner, ast.Call):
                    continue
                short = None
                if isinstance(inner.func, ast.Name):
                    short = inner.func.id
                elif isinstance(inner.func, ast.Attribute):
                    short = inner.func.attr
                if short not in STDLIB_WRITE_CALLS:
                    continue
                if isinstance(inner.func, ast.Name) and short in enveloped:
                    continue
                if inner.lineno in try_linenos:
                    continue
                accept = auditme.core.accept_reason(lines, inner.lineno, rule='filesystem-op-without-envelope')
                auditme.core.emit(
                    rule='filesystem-op-without-envelope',
                    variant=f'{func.name} calls `{short}` with no surrounding try/except in the function body',
                    path=rel,
                    line=inner.lineno,
                    evidence=(lines[inner.lineno - 1].strip()[:200] if inner.lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
                break  # one finding per function


def check_logger_exception_graceful_degradation(
    scope: pathlib.Path,
    src_root: pathlib.Path,
) -> None:
    """Flag `except` handlers that call `logger.exception(...)` and then
    `return <constant>` without raising. `logger.exception` is reserved
    for unexpected failures; a handler that logs-then-returns-default is
    a graceful-degradation path and should use `logger.warning` /
    `logger.debug` instead, so log severity matches the handling
    intent.

    Signal:
      - An `ast.ExceptHandler` whose body contains a `logger.exception(...)`
        call AND contains no `ast.Raise`.
      - EITHER the handler body ends with `return <Constant>` OR the
        enclosing function body ends with `return <Constant>` (so the
        handler falls through to the graceful-degradation default).
      - The enclosing function's return annotation is NOT `int`. CLI entry
        points return `int` exit codes and `logger.exception + return 2`
        is the canonical CLI error-contract, not graceful degradation.

    For a broad `except Exception` handler, the `logger.warning` this
    suggests fires `broad-except-wrong-level` instead. SKILL.md's "Conflicts
    with no winner" rules on it: remove the handler, or narrow it to the
    expected exception and then use `logger.warning`.
    """

    # Build a map of lineno -> enclosing FunctionDef return annotation.
    def enclosing_return_annotation(tree: ast.AST, lineno: int) -> str | None:
        best: tuple[int, str | None] | None = None
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            start = node.lineno
            end = getattr(node, 'end_lineno', None) or start
            if not (start <= lineno <= end):
                continue
            ann = None
            if node.returns is not None:
                ann = ast.unparse(node.returns)
            if best is None or start > best[0]:
                best = (start, ann)
        return best[1] if best else None

    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            has_logger_exception = False
            has_raise = False
            handler_last_return: ast.Return | None = None
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Call):
                        src = ''
                        with contextlib.suppress(Exception):
                            src = ast.unparse(sub.func)
                        if src.endswith('logger.exception') or src.endswith('.exception'):
                            if 'logger' in src or 'loguru' in src:
                                has_logger_exception = True
                    if isinstance(sub, ast.Raise):
                        has_raise = True
                if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant):
                    handler_last_return = stmt
            if not has_logger_exception:
                continue
            if has_raise:
                continue
            # The graceful-degradation default lives either at the end of
            # the handler body (`return <Constant>`) or at the end of the
            # enclosing function body (handler falls through).
            fallthrough_return: ast.Return | None = None
            if handler_last_return is None:
                for fn in ast.walk(tree):
                    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    start = fn.lineno
                    end = getattr(fn, 'end_lineno', None) or start
                    if not (start <= node.lineno <= end):
                        continue
                    last_stmt = fn.body[-1] if fn.body else None
                    if isinstance(last_stmt, ast.Return) and isinstance(last_stmt.value, ast.Constant):
                        fallthrough_return = last_stmt
                    break
            default_return = handler_last_return or fallthrough_return
            if default_return is None:
                continue
            lineno = default_return.lineno
            # Exclude CLI entry points (return `int` exit code)
            ret_ann = enclosing_return_annotation(tree, lineno)
            if ret_ann is not None and ret_ann.strip() == 'int':
                continue
            accept = auditme.core.accept_reason(lines, lineno, rule='logger-exception-graceful-degradation')
            auditme.core.emit(
                rule='logger-exception-graceful-degradation',
                variant=('except handler calls logger.exception then returns a constant default; use logger.warning or logger.debug instead'),
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


def raises_section_names(doc: str) -> set[str]:
    """Return the class name of every entry in a Google-style `Raises:` section.

    An entry is a line at the section's first indent, optionally bulleted,
    naming a `*Error`; deeper lines continue the entry before them, and the
    first line back at the header's indent ends the section.
    """
    entry_re = re.compile(r'\s*(?:[-*]\s+)?([A-Za-z_][\w.]*Error)\b')
    lines = doc.splitlines()
    names: set[str] = set()
    for start, header in enumerate(lines):
        if header.strip() != 'Raises:':
            continue
        header_indent = len(header) - len(header.lstrip())
        entry_indent = None
        for line in lines[start + 1 :]:
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= header_indent:
                break
            if entry_indent is None:
                entry_indent = indent
            if indent != entry_indent:
                continue
            match = entry_re.match(line)
            if match:
                names.add(match.group(1).rsplit('.', 1)[-1])
    return names


def check_docstring_raises_mismatch(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions whose docstring declares `Raises: <X>` (or a
    sphinx-style `:raises X:` or a plain 'Raises X' sentence) where the
    body actually raises a different exception class.

    Signal:
      - Function has a docstring.
      - Docstring mentions at least one exception class name (via
        `Raises:` section, `:raises X:` role, or 'Raises FooError' prose).
      - Function body contains `raise <Y>(...)` statements, all of which
        raise a class NOT listed in the docstring, and no `raise` re-raises
        a caught variable.
    """
    # Match exception class names from docstrings in a few common shapes
    docstring_class_re = re.compile(
        r'(?:Raises[\s:]+|:raises\s+|^\s*Raises?\s+)'
        r'([A-Za-z_][\w.]*Error)',
        re.MULTILINE,
    )
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = ast.get_docstring(node)
            if not doc:
                continue
            declared = {m.rsplit('.', 1)[-1] for m in docstring_class_re.findall(doc)} | raises_section_names(doc)
            if not declared:
                continue
            # Collect actual raised classes (excluding re-raises of bound vars)
            actual: set[str] = set()
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Raise) or inner.exc is None:
                    continue
                target = inner.exc.func if isinstance(inner.exc, ast.Call) else inner.exc
                if isinstance(target, (ast.Name, ast.Attribute)):
                    src = ast.unparse(target)
                    tail = src.rsplit('.', 1)[-1]
                    if tail.endswith('Error'):
                        actual.add(tail)
            if not actual:
                continue
            if actual & declared:
                continue  # intersection non-empty => at least one documented match
            # Every actual raise is not in declared list => mismatch
            accept = auditme.core.accept_reason(lines, node.lineno, rule='docstring-raises-mismatch')
            auditme.core.emit(
                rule='docstring-raises-mismatch',
                variant=f'{node.name} docstring declares `Raises: {sorted(declared)}` but body raises {sorted(actual)}',
                path=rel,
                line=node.lineno,
                evidence=f'docstring: {sorted(declared)} | body: {sorted(actual)}',
                accepted=bool(accept),
                accepted_reason=accept,
            )


# Builtin exception classes: not a project's domain errors.
STDLIB_ERRORS = frozenset(
    {
        'ArithmeticError',
        'AssertionError',
        'AttributeError',
        'BaseException',
        'BlockingIOError',
        'BrokenPipeError',
        'BufferError',
        'ChildProcessError',
        'ConnectionAbortedError',
        'ConnectionError',
        'ConnectionRefusedError',
        'ConnectionResetError',
        'EOFError',
        'Exception',
        'FileExistsError',
        'FileNotFoundError',
        'FloatingPointError',
        'GeneratorExit',
        'ImportError',
        'IndentationError',
        'IndexError',
        'InterruptedError',
        'IsADirectoryError',
        'KeyError',
        'KeyboardInterrupt',
        'LookupError',
        'MemoryError',
        'ModuleNotFoundError',
        'NameError',
        'NotADirectoryError',
        'NotImplementedError',
        'OSError',
        'OverflowError',
        'PermissionError',
        'ProcessLookupError',
        'RecursionError',
        'ReferenceError',
        'RuntimeError',
        'StopAsyncIteration',
        'StopIteration',
        'SyntaxError',
        'SystemError',
        'SystemExit',
        'TabError',
        'TimeoutError',
        'TypeError',
        'UnboundLocalError',
        'UnicodeDecodeError',
        'UnicodeEncodeError',
        'ValueError',
        'ZeroDivisionError',
    }
)


def check_missing_raises_section(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions whose body raises a project exception but whose
    docstring lacks any `Raises:` / `:raises:` section.

    Signal:
      - Function has a non-empty docstring.
      - Function body contains at least one `ast.Raise` whose exception
        class name ends in `Error` and that is NOT a bare `raise` inside
        an except block (pure re-raise) and NOT a re-raise of a caught
        variable (`raise exc_var`).
      - Docstring contains NO `Raises:` block, `:raises X:` role, or
        sentence beginning with `Raises `.

    Refinement (2026-11-01): a raise that a handler around it catches, by its
    own class or a base class in the package's class tree (a bare `except:`,
    `Exception` and `BaseException` catch all), without re-raising, does not
    reach the caller and does not count (`level_catches`). A def nested in
    the subject counts only where it is called by bare name, under that
    call's handlers (`nested_call_sites`); a nested def never called counts
    nothing, and stays a subject of its own. A handler that re-raises, one
    for an unrelated class, or no handler keeps the hit.
    """
    # Accept any of:
    #   - a `Raises:` / `Raise:` header line (napoleon / google style)
    #   - sphinx `:raises X:` role
    #   - a prose sentence `Raise <X>Error` or `Raises <X>Error` that may
    #     use a dotted-module-qualified form (`pkg.ensemble.errors.LoadError`)
    raises_marker_re = re.compile(
        r'(?:^\s*Raises?\s*:|:raises\s+[A-Za-z_]|\bRaises?\s+[A-Za-z_][\w.]*Error\b)',
        re.MULTILINE,
    )
    parsed: list[tuple[pathlib.Path, list[str], ast.Module]] = []
    for path in auditme.core.all_py_files(src_root):
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        parsed.append((path, lines, tree))
    parents = package_class_parents(tree for _, _, tree in parsed)
    for path, lines, tree in parsed:
        if path.name == '__init__.py' or path.name == 'errors.py':
            continue
        rel = auditme.core.relpath(path, scope)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = ast.get_docstring(node)
            if not doc:
                continue
            if raises_marker_re.search(doc):
                continue
            # Does body raise a project *Error class, not a re-raise or stdlib?
            found_project_raise = False
            for inner, levels in nested_call_sites(node):
                if not isinstance(inner, ast.Raise):
                    continue
                if inner.exc is None:
                    continue  # bare `raise` re-raise
                target = inner.exc.func if isinstance(inner.exc, ast.Call) else inner.exc
                if isinstance(target, ast.Name):
                    # a re-raise of a caught variable is `raise exc_var` - Name without Call
                    if not isinstance(inner.exc, ast.Call):
                        continue
                    name = target.id
                elif isinstance(target, ast.Attribute):
                    name = target.attr
                else:
                    continue
                if not name.endswith('Error'):
                    continue
                if name in STDLIB_ERRORS:
                    continue  # stdlib raises are covered by the layer-stdlib check
                lineage = class_lineage(name, parents)
                if any(level_catches(level, lineage) for level in levels):
                    continue
                found_project_raise = True
                break
            if not found_project_raise:
                continue
            accept = auditme.core.accept_reason(lines, node.lineno, rule='missing-raises-section')
            auditme.core.emit(
                rule='missing-raises-section',
                variant=f'{node.name} raises a project *Error but docstring lacks a Raises: section',
                path=rel,
                line=node.lineno,
                evidence=(lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_bare_except_in_module_with_narrow_errors(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag modules that inconsistently mix `except Exception` / `except
    BaseException` with narrow `except <X>_ERRORS:` tuples in separate
    sites. The mixed pattern signals an incomplete sweep toward narrow
    except tuples.

    Signal:
      - Module has at least one `except Exception` / `except BaseException`
        (bare or with bound name).
      - Module ALSO has at least one `except <NAME>_ERRORS:` or
        `except (*<NAME>_ERRORS, ...):` tuple-handler where NAME_ERRORS
        is referenced as an `ast.Name`.
      - Flag the bare-except sites, not the narrow ones.
    """
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        bare_handlers: list[ast.ExceptHandler] = []
        narrow_errors_tuple_seen = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            t = node.type
            if t is None:
                bare_handlers.append(node)
                continue
            names = []
            if isinstance(t, ast.Tuple):
                for elt in t.elts:
                    if isinstance(elt, ast.Name):
                        names.append(elt.id)
                    elif isinstance(elt, ast.Starred) and isinstance(elt.value, ast.Name):
                        names.append(elt.value.id)
            elif isinstance(t, ast.Name):
                names.append(t.id)
            if any(n.endswith('_ERRORS') or n.endswith('_EXCEPTIONS') for n in names):
                narrow_errors_tuple_seen = True
                continue
            if any(n in BROAD_HANDLER_NAMES for n in names):
                bare_handlers.append(node)
        if not (narrow_errors_tuple_seen and bare_handlers):
            continue
        for handler in bare_handlers:
            accept = auditme.core.accept_reason(lines, handler.lineno, rule='bare-except-in-module-with-narrow-errors')
            auditme.core.emit(
                rule='bare-except-in-module-with-narrow-errors',
                variant='bare except Exception in module that elsewhere uses *_ERRORS tuple',
                path=rel,
                line=handler.lineno,
                evidence=(lines[handler.lineno - 1].strip()[:200] if handler.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


# Directories whose modules adapt an external service. AGENTS.md's
# failure-versus-absence rule is written for "a source or resolver"; LLM
# providers are the same shape - an adapter over a remote API - so they are
# included. Scope is deliberately narrow: outside an adapter, a bare
# `return None` from an except handler is often a legitimate cache miss or
# optional lookup, and firing on those would make the check untrustworthy.
EXTERNAL_ADAPTER_DIRS = frozenset({'providers', 'resolvers', 'sources'})

# What counts as "recording a failure the caller can see". Logging does not:
# a log line is not a value the caller can branch on, which is the whole point
# of the rule.
FAILURE_WORD_RE = re.compile(r'error|failure|failed|cannot_answer', re.IGNORECASE)

LOGGING_CALL_RE = re.compile(r'^(logger|logging|log)\b|\.(debug|info|warning|error|exception|critical)$')

STATUS_TEST_RE = re.compile(r'\b(status|status_code|statuscode)\b')


def clean_absence_return(node: ast.Return) -> str | None:
    """Label this return if it signals 'nothing here', else None.

    Covers the tuple form because `resolve_chain` returns `(None, None)`.
    """
    value = node.value
    if value is None:
        return 'bare return'
    if isinstance(value, ast.Constant) and value.value is None:
        return 'return None'
    if isinstance(value, ast.List) and not value.elts:
        return 'return []'
    if isinstance(value, ast.Dict) and not value.keys:
        return 'return {}'
    if isinstance(value, ast.Tuple) and value.elts and all(isinstance(e, ast.Constant) and e.value is None for e in value.elts):
        return f'return ({", ".join(["None"] * len(value.elts))})'
    return None


def records_visible_failure(stmts: list[ast.stmt]) -> bool:
    """True when these statements raise, or set something the caller reads.

    A keyword argument counts (`SearchBatch(..., error=str(e))`) because that
    is the project's documented alternative to raising. A logger call does not,
    however error-shaped its name.
    """
    for stmt in stmts:
        for child in [stmt, *auditme.core.walk_within_scope(stmt)]:
            if isinstance(child, ast.Raise):
                return True
            if isinstance(child, ast.keyword) and child.arg and FAILURE_WORD_RE.search(child.arg):
                return True
            if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                if any(FAILURE_WORD_RE.search(ast.unparse(t)) for t in targets if t is not None):
                    return True
            if isinstance(child, ast.Call):
                func_src = ast.unparse(child.func)
                if LOGGING_CALL_RE.search(func_src):
                    continue
                if FAILURE_WORD_RE.search(func_src):
                    return True
    return False


def status_failure_branch(node: ast.If) -> list[ast.stmt] | None:
    """Return whichever branch of an HTTP-status test runs on a non-200."""
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return None
    if not STATUS_TEST_RE.search(ast.unparse(test)):
        return None
    op = test.ops[0]
    if isinstance(op, (ast.NotEq, ast.GtE, ast.Gt, ast.NotIn)):
        return node.body
    if isinstance(op, (ast.Eq, ast.In)):
        return node.orelse or None
    return None


def check_failure_as_absence(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a clean-absence return reached from a caught exception or a non-200.

    AGENTS.md ("Failure versus absence") requires that a source or resolver
    never return None/[] for a non-200 response or a caught exception without
    also recording a failure the caller can see - by raising, or by setting an
    error field the caller reads. Returning empty is reserved for a genuine
    "the request completed and there was nothing to find". Conflating the two
    makes a network outage read as "this paper has no match", which is silently
    wrong rather than loudly wrong.

    Two shapes are detected:
      A. An `except` handler whose body reaches a clean-absence return with no
         raise and no error-recording statement.
      B. The non-200 branch of an HTTP status test doing the same.

    Deliberately NOT detected - documented non-goals, not oversights:
      - The loop-continue shape, where a per-item handler `continue`s and the
        function later returns a collection that happens to be empty. Catching
        it needs flow analysis and would fire on legitimate partial-result
        paths, where returning what did parse is correct.
      - Count guards such as `if failed == attempted: raise`, where the defect
        is the arithmetic and the return is innocent.
    Both remain Phase B's job. This check owns the direct shapes, where a
    verdict needs no judgement.
    """
    for path in auditme.core.all_py_files(src_root):
        parts = set(path.parts)
        if 'tests' in parts or not (parts & EXTERNAL_ADAPTER_DIRS):
            continue
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                variant, body = 'caught exception returns empty', node.body
            elif isinstance(node, ast.If):
                body = status_failure_branch(node)
                if body is None:
                    continue
                variant = 'non-200 branch returns empty'
            else:
                continue
            if records_visible_failure(body):
                continue
            for child in [*body, *(c for stmt in body for c in auditme.core.walk_within_scope(stmt))]:
                if not isinstance(child, ast.Return):
                    continue
                label = clean_absence_return(child)
                if label is None:
                    continue
                accept = auditme.core.accept_reason(lines, child.lineno, rule='failure-as-absence') or auditme.core.accept_reason(
                    lines, node.lineno, rule='failure-as-absence'
                )
                auditme.core.emit(
                    rule='failure-as-absence',
                    variant=f'{variant} ({label})',
                    path=rel,
                    line=child.lineno,
                    evidence=lines[child.lineno - 1].strip()[:200] if child.lineno <= len(lines) else label,
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


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


# The `load` and `loads` entry points of `json` and `tomllib`.
LOADER_CALLS = frozenset({'load', 'loads'})


def is_tomllib_call(node: ast.AST) -> bool:
    """True for a `tomllib.load(...)` or `tomllib.loads(...)` call."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in LOADER_CALLS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == 'tomllib'
    )


def toml_returning_functions(tree: ast.Module) -> set[str]:
    """Names of module-level functions that return a `tomllib` call and nothing else but a dict literal."""
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        values = [sub.value for sub in auditme.core.walk_within_scope(node) if isinstance(sub, ast.Return)]
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
    for stmt in auditme.core.walk_within_scope(scope_node):
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
    for node in [scope_node, *auditme.core.walk_within_scope(scope_node)]:
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
    for node in auditme.core.walk_within_scope(scope_node):
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


def check_get_container_default_then_method_call(scope: pathlib.Path, src_root: pathlib.Path) -> None:
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
    for path in auditme.core.all_py_files(src_root):
        if 'tests' in set(path.parts) or path.name.startswith('conftest'):
            continue
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        toml_functions = toml_returning_functions(tree)
        for scope_node in name_scopes(tree):
            for stmt in auditme.core.walk_within_scope(scope_node):
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
                accept = auditme.core.accept_reason(lines, stmt.lineno, rule='get-container-default-then-method-call')
                auditme.core.emit(
                    rule='get-container-default-then-method-call',
                    variant=f'default {default} does not fire for an explicit null, then {use}',
                    path=rel,
                    line=stmt.lineno,
                    evidence=lines[stmt.lineno - 1].strip()[:200] if stmt.lineno <= len(lines) else ast.unparse(stmt),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


# Anything that also satisfies a narrower requirement, whatever the body does.
UNIVERSAL_CATCHES = frozenset({'*bare*', 'BaseException', 'Exception'})

# `OSError`'s subclasses are accepted as satisfying the disk branch, matching
# `check_filesystem_envelope_gap`. Neither check tries to prove that the
# subclass named is the one the body can raise; that is Phase B's job.
OSERROR_SATISFIERS = frozenset(
    {
        'FileNotFoundError',
        'IOError',
        'IsADirectoryError',
        'OSError',
        'PermissionError',
    }
)

# Calls that read a file as text, and so can raise `UnicodeDecodeError` on
# bytes the declared encoding cannot decode. `.decode()` is deliberately not a
# trigger: the attribute name is used by tokenisers, codecs and protocol
# helpers far more often than by `bytes.decode`, so it would fire mostly on
# calls that cannot raise `UnicodeDecodeError` at all.
TEXT_DECODING_CALLS = frozenset({'read_text'})


def handler_catches(handler: ast.ExceptHandler) -> set[str]:
    """Every identifier named in this handler's except tuple.

    Dotted forms contribute both halves (`json.JSONDecodeError` gives `json`
    and `JSONDecodeError`), which is harmless: only the exception names are
    ever looked up. A bare `except:` gives the `*bare*` sentinel.
    """
    if handler.type is None:
        return {BARE_HANDLER_MARK}
    return set(re.findall(r'[A-Za-z_][A-Za-z_0-9]*', ast.unparse(handler.type)))


def handler_translates(handler: ast.ExceptHandler) -> bool:
    """True when this handler raises something whose name ends in `Error`.

    The same signal `check_asymmetric_exception_translation` uses. It is what
    separates an error-translating wrapper from a decorator that happens to
    contain a `try` for an unrelated reason, such as an optional-import probe.
    """
    for sub in ast.walk(handler):
        if not isinstance(sub, ast.Raise) or sub.exc is None:
            continue
        target = sub.exc.func if isinstance(sub.exc, ast.Call) else sub.exc
        if not isinstance(target, (ast.Name, ast.Attribute)):
            continue
        if ast.unparse(target).rsplit('.', 1)[-1].endswith('Error'):
            return True
    return False


def translator_envelopes(src_root: pathlib.Path) -> dict[str, frozenset[str]]:
    """Map every error-translating function's name to what its handlers catch.

    Indexed by short name rather than by dotted path, because the decorator is
    written as the name it was bound to at the use site and that binding is not
    always an import the checker can follow - one project's store reads the
    contextmanager back out of `sys.modules` to dodge a circular import, and a
    dotted-path index would resolve nothing there.

    Two definitions sharing a short name contribute a union, so a wide envelope
    elsewhere in the package can only ever silence a hit, never invent one.
    """
    envelopes: dict[str, set[str]] = collections.defaultdict(set)
    for path in auditme.core.all_py_files(src_root):
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            caught: set[str] = set()
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Try):
                    continue
                for handler in sub.handlers:
                    if handler_translates(handler):
                        caught |= handler_catches(handler)
            if caught:
                envelopes[node.name] |= caught
    return {name: frozenset(caught) for name, caught in envelopes.items()}


def callable_short_name(expr: ast.expr) -> str | None:
    """The bare name a decorator or `with` item invokes.

    `@translate('...')`, `@errors.translate` and `@translate` all give
    `translate`.
    """
    node = expr.func if isinstance(expr, ast.Call) else expr
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def guarded_body_nodes(node: ast.FunctionDef | ast.AsyncFunctionDef) -> collections.abc.Iterable[ast.AST]:
    """Every node in the function's own body - not its signature or decorators.

    A decorator is itself a `Call`, and walking it would let
    `@pandas_backed_cache(...)`-shaped decoration read as a body that parses.
    Pruned at a nested `def`/`class` too: the outer walk reaches those on their
    own, where their own decoration is the envelope being judged.
    """
    for stmt in node.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield stmt
        yield from auditme.core.walk_within_scope(stmt)


def a2_branches_for_call(node: ast.Call) -> list[tuple[str, frozenset[str]]]:
    """The locked-set branches this call triggers, as (required, satisfied-by).

    Each branch is one row of A2's locked set, keyed on a form that needs no
    judgement to recognise: the module the parser is called on, or the exact
    name of the filesystem primitive.
    """
    branches: list[tuple[str, frozenset[str]]] = []
    short: str | None = None
    if isinstance(node.func, ast.Name):
        short = node.func.id
    elif isinstance(node.func, ast.Attribute):
        short = node.func.attr
        receiver = ast.unparse(node.func.value).rsplit('.', 1)[-1]
        if receiver == 'json' and short in LOADER_CALLS:
            branches.append(('json.JSONDecodeError', frozenset({'JSONDecodeError', 'ValueError'})))
        if receiver in {'pandas', 'pd'} and short.startswith('read_'):
            branches.append(('pandas.errors.ParserError', frozenset({'ParserError'})))
        if receiver == 'gzip' and short in {'GzipFile', 'open'}:
            branches.append(('gzip.BadGzipFile', frozenset({'BadGzipFile'})))
    if short in TEXT_DECODING_CALLS:
        branches.append(('UnicodeDecodeError', frozenset({'UnicodeDecodeError'})))
    if short in FILESYSTEM_TOUCHING_CALLS:
        branches.append(('OSError', OSERROR_SATISFIERS))
    return branches


def check_translator_envelope_gap(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a body whose only error envelope is a translating decorator or
    contextmanager whose except tuple is narrower than A2's locked set.

    `filesystem-envelope-gap` and every other mechanical A2 check look for a
    lexical `try/except` in the function. A `@translate_sqlite_errors`-style
    decorator is invisible to that scan, so a function guarded only by one
    reads as "no envelope at all" - and is then skipped, being neither
    lexically guarded nor caught by the no-envelope checks. On one project
    such sites in a query module survived several audit cycles: each
    `json.loads` a sqlite column inside functions documenting
    `Raises: StoreError` whose only envelope caught `sqlite3.Error`, so a
    malformed column reached the CLI as a bare `json.JSONDecodeError`
    traceback.

    Signal:
      - Function F is decorated with, or contains a `with` block entering, a
        function defined in this package whose own `except` handler raises a
        `*Error` (see `handler_translates`). That handler's tuple is F's
        envelope.
      - F's body calls something that triggers a branch of A2's locked set:
        `json.load*` needs `json.JSONDecodeError`; `pd.read_*` needs
        `pandas.errors.ParserError`; `gzip.open` needs `gzip.BadGzipFile`;
        `read_text` needs `UnicodeDecodeError`; any filesystem primitive
        needs `OSError`.
      - The envelope's tuple satisfies none of the branch's exceptions.

    Carve-outs, each of which must not fire:
      - A decorator catching bare `Exception` / `BaseException`, or a bare
        `except:`, satisfies every branch - exactly as a lexical one does.
      - A call already inside a lexical `try` in F. That envelope is the
        lexical checks' to judge, and reporting it here would double-count it.
      - A function with no resolvable translator at all. "No envelope" is
        `filesystem-op-without-envelope`'s question, not this one.

    One finding per function, at its earliest triggering call, so a function
    parsing several columns is one item of work rather than several.
    """
    envelopes = translator_envelopes(src_root)
    if not envelopes:
        return
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            caught: set[str] = set()
            sources: list[str] = []
            for decorator in func.decorator_list:
                short = callable_short_name(decorator)
                if short in envelopes:
                    caught |= envelopes[short]
                    sources.append(f'@{short}')
            # A contextmanager entered inside the body guards only the block it
            # wraps, so its reach is recorded as a line range rather than
            # folded into the whole function's envelope.
            with_ranges: list[tuple[int, int, frozenset[str], str]] = []
            lexical_try_linenos: set[int] = set()
            for sub in guarded_body_nodes(func):
                if isinstance(sub, ast.Try):
                    for stmt in sub.body:
                        for inner in ast.walk(stmt):
                            if hasattr(inner, 'lineno'):
                                lexical_try_linenos.add(inner.lineno)
                if not isinstance(sub, (ast.With, ast.AsyncWith)) or not sub.body:
                    continue
                block_caught: set[str] = set()
                block_names: list[str] = []
                for item in sub.items:
                    short = callable_short_name(item.context_expr)
                    if short in envelopes:
                        block_caught |= envelopes[short]
                        block_names.append(short)
                if not block_caught:
                    continue
                start = sub.body[0].lineno
                end = getattr(sub.body[-1], 'end_lineno', None) or sub.body[-1].lineno
                with_ranges.append((start, end, frozenset(block_caught), ', '.join(block_names)))
            # Collected rather than emitted in the walk, because the walk's
            # order is not the source's: the earliest triggering call is the
            # one to report, so a reader lands on the first parse in the
            # function rather than on whichever the traversal reached first.
            gaps: list[tuple[int, str, list[str], list[str], set[str]]] = []
            for node in guarded_body_nodes(func):
                if not isinstance(node, ast.Call):
                    continue
                branches = a2_branches_for_call(node)
                if not branches or node.lineno in lexical_try_linenos:
                    continue
                site_caught = set(caught)
                site_sources = list(sources)
                for start, end, range_caught, range_names in with_ranges:
                    if start <= node.lineno <= end:
                        site_caught |= range_caught
                        site_sources.append(f'with {range_names}')
                if not site_sources or site_caught & UNIVERSAL_CATCHES:
                    continue
                missing = [required for required, satisfied_by in branches if not satisfied_by & site_caught]
                if missing:
                    gaps.append((node.lineno, ast.unparse(node.func), missing, site_sources, site_caught))
            if not gaps:
                continue
            lineno, callee, missing, site_sources, site_caught = min(gaps, key=lambda gap: gap[0])
            accept = auditme.core.accept_reason(lines, lineno, rule='translator-envelope-gap')
            auditme.core.emit(
                rule='translator-envelope-gap',
                variant=(
                    f'{func.name} calls `{callee}` under {", ".join(site_sources)}, whose except tuple {sorted(site_caught - {BARE_HANDLER_MARK})!r} omits {missing!r}'
                ),
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if lineno <= len(lines) else callee),
                accepted=bool(accept),
                accepted_reason=accept,
            )


# Handlers that catch every domain error, whatever its name.
BROAD_HANDLER_NAMES = frozenset({'BaseException', 'Exception'})


def handler_passes_on(handler: ast.ExceptHandler) -> bool:
    """Whether an `except` clause re-raises (a bare `raise`, or `raise <bound name>`).

    Only the clause's own scope counts: a raise inside a def, lambda or class
    defined in the handler belongs to that scope.
    """
    bound = handler.name
    return any(
        isinstance(node, ast.Raise) and (node.exc is None or (isinstance(node.exc, ast.Name) and node.exc.id == bound))
        for node in auditme.core.walk_within_scope(handler)
    )


def handler_types(handler: ast.ExceptHandler) -> frozenset[str] | None:
    """The class-name tails an `except` clause matches, or None for a broad one. Pure."""
    if handler.type is None:
        return None
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    names = set()
    for node in types:
        if isinstance(node, (ast.Name, ast.Attribute)):
            names.add(ast.unparse(node).rsplit('.', 1)[-1])
    if names & BROAD_HANDLER_NAMES:
        return None
    return frozenset(names)


def raised_name(node: ast.Raise) -> str | None:
    """The class-name tail a `raise` statement raises, or None.

    `raise X(...)` and `raise mod.X(...)` name a class; a bare `raise` and
    `raise <name>` re-raise something already caught.
    """
    if node.exc is None or not isinstance(node.exc, ast.Call):
        return None
    func = node.exc.func
    if isinstance(func, (ast.Name, ast.Attribute)):
        return ast.unparse(func).rsplit('.', 1)[-1]
    return None


# One `try`'s handlers in source order: what each matches (None for a broad
# clause) and whether it passes the error on.
HandlerLevel = tuple[tuple[frozenset[str] | None, bool], ...]


def handler_level(node: ast.Try | ast.TryStar) -> HandlerLevel:
    """A `try`'s handlers in source order. Pure."""
    return tuple((handler_types(handler), handler_passes_on(handler)) for handler in node.handlers)


def level_catches(level: HandlerLevel, lineage: set[str]) -> bool:
    """Whether a `try` stops an error of this lineage. Pure.

    Python runs only the first clause that matches, so a re-raising clause
    lets the error through even when a later, broader clause would catch it.
    """
    for types, passes_on in level:
        if types is None or types & lineage:
            return not passes_on
    return False


def reach_sites(
    body: list[ast.stmt],
    catches: tuple[HandlerLevel, ...] = (),
) -> list[tuple[ast.AST, tuple[HandlerLevel, ...]]]:
    """Every `raise` and call in a function body, with the `try` levels around it.

    Nested functions, lambdas and classes are skipped: their raises reach their
    own callers. A `try` body sees its own handlers; its handlers, `else` and
    `finally` see only the handlers outside it.
    """
    sites: list[tuple[ast.AST, tuple[HandlerLevel, ...]]] = []

    def visit(node: ast.AST, around: tuple[HandlerLevel, ...]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return
        if isinstance(node, (ast.Try, ast.TryStar)):
            inner = (*around, handler_level(node))
            for child in node.body:
                visit(child, inner)
            for child in [*node.handlers, *node.orelse, *node.finalbody]:
                visit(child, around)
            return
        if isinstance(node, (ast.Raise, ast.Call)):
            sites.append((node, around))
        for child in ast.iter_child_nodes(node):
            visit(child, around)

    for statement in body:
        visit(statement, catches)
    return sites


def nested_call_sites(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[ast.AST, tuple[HandlerLevel, ...]]]:
    """`reach_sites(func.body)` plus, for each call by bare name to a def
    nested directly in `func`'s body, that def's own reach sites with the
    call's handler levels prepended. One level deep; a nested def that is
    never called contributes nothing.
    """
    nested = {stmt.name: stmt for stmt in func.body if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))}
    sites = reach_sites(func.body)
    for site, around in list(sites):
        if isinstance(site, ast.Call) and isinstance(site.func, ast.Name) and site.func.id in nested:
            sites.extend((inner, (*around, *levels)) for inner, levels in reach_sites(nested[site.func.id].body))
    return sites


def function_levels(body: list[ast.stmt]) -> list[HandlerLevel]:
    """Every `try` level in a function body, nested defs skipped."""
    levels: list[HandlerLevel] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return
        if isinstance(node, (ast.Try, ast.TryStar)):
            levels.append(handler_level(node))
        for child in ast.iter_child_nodes(node):
            visit(child)

    for statement in body:
        visit(statement)
    return levels


def unset_optional_guard(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    error: str,
    parents: collections.abc.Mapping[str, set[str]],
    call: ast.Call,
    bound: bool,
) -> bool:
    """Whether `call` leaves unset every optional argument guarding `error`.

    True when `func`'s own scope (nested defs, lambdas and classes excluded)
    holds at least one `raise X(...)` or `raise mod.X(...)` whose lineage
    contains `error`, and each such raise has an enclosing `If` (in its body
    or `orelse`) or `Match` inside `func` whose test or subject reads a Name
    that is a parameter with a default which `call` does not supply. A
    parameter is supplied when a keyword names it or a positional argument
    reaches its position; with `bound` (a call through `self.`), positional
    arguments start at the second parameter. A call with a `*` or `**`
    argument supplies every parameter. False otherwise, including when
    `func` raises `error` only through its own callees.
    """
    if any(isinstance(arg, ast.Starred) for arg in call.args) or any(kw.arg is None for kw in call.keywords):
        return False
    args = func.args
    positional = [*args.posonlyargs, *args.args]
    first_default = len(positional) - len(args.defaults)
    optional = {arg.arg: index for index, arg in enumerate(positional) if index >= first_default}
    optional.update({arg.arg: -1 for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True) if default is not None})
    reached = len(call.args) + (1 if bound else 0)
    named = {kw.arg for kw in call.keywords}
    unset = {name for name, index in optional.items() if name not in named and (index < 0 or index >= reached)}
    if not unset:
        return False

    def reads_unset(expr: ast.expr) -> bool:
        return any(isinstance(node, ast.Name) and node.id in unset for node in ast.walk(expr))

    found = False

    def visit(node: ast.AST, guarded: bool) -> bool:
        """Walk `node`; False when a matching raise sits outside an unset-argument guard."""
        nonlocal found
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return True
        if isinstance(node, ast.Raise):
            name = raised_name(node)
            if name and error in class_lineage(name, parents):
                found = True
                if not guarded:
                    return False
        tested = node.test if isinstance(node, ast.If) else node.subject if isinstance(node, ast.Match) else None
        inner = guarded or (tested is not None and reads_unset(tested))
        return all(visit(child, inner) for child in ast.iter_child_nodes(node))

    return all(visit(statement, False) for statement in func.body) and found


SECTIONLESS_DEPTH: typing.Final = 3
"""How many calls deep the rule follows from a subject; the A4 lister's `--depth` default."""


def check_raises_section_drift(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a `Raises:` section that disagrees with the domain errors reaching
    the caller (A4).

    Signal:
      - A function or method whose docstring has a Google-style `Raises:`
        section (`raises_section_names`).
      - What reaches its caller: every domain error its body raises, plus every
        domain error a same-package callee's own `Raises:` section declares,
        minus each that an enclosing `except` catches without re-raising.
      - One hit per name the section omits, and one per domain error it
        declares that never reaches the caller although a handler in the
        function catches it - the positive evidence that it is caught there.

    A domain error is an exception class the swept package defines - positive
    evidence, so `sqlite3.Error` (tail `Error`) and a third-party `*Error` are
    not one - and never a builtin (`STDLIB_ERRORS`). Subclasses follow the package's own class tree: catching
    or declaring a base covers its subclasses. A callee with a `Raises:`
    section is followed through that declared section, not its body; a callee
    with no section is followed into its own raises and callees, up to
    `SECTIONLESS_DEPTH` calls deep. Only calls within the package being swept
    resolve: a module function called by its dotted path (or a name imported
    from a package module), a same-module function, a method called on
    `self`, or `<ClassName>.<method>(...)` for a class the package defines,
    following re-exports such as a package `__init__.py`'s
    `from pkg.mod import name`. A call the check cannot resolve contributes
    nothing, which is why an extra needs a catching handler: without one, the
    declared error may arrive through such a call.

    Raised by an audit whose Phase B A4 kept finding these by hand, cycle
    after cycle (shipped 2026-10-31).

    Refinement (2026-11-01): a callee's declared error does not reach the
    caller through a call that leaves unset every optional argument guarding
    it (`unset_optional_guard`): every raise of it in the callee's own body
    sits under an `if` or `match` testing a parameter with a default that the
    call does not supply, as `if strict: raise ParseError(...)` called as
    `load('x')`. Omissions only; a guard on a parameter without a default, a
    module-level name, a raise outside the guard, or a call passing the
    argument (or `*args`/`**kwargs`) keeps the hit. Other value-dependent
    cases (fixed names, pre-checked values, dispatch types) are left to the
    Phase B review (A4).

    Refinement (2026-11-01), nested functions: a def nested directly in the
    subject and called by bare name contributes its raises and calls under
    the call's handlers (`nested_call_sites`, one level deep), so an error it
    catches and re-raises on one branch still reaches the subject's callers;
    a def never called contributes nothing. A raise inside a def, lambda or
    class defined in a handler does not make that handler re-raise.

    Extension (2026-11-20): both resolution gaps in the request "`raises-section-drift`
    should follow pass-through callees and `Class.method()` calls" in
    `claude/skills/auditme/requests.md` are closed. A `<ClassName>.<method>(...)`
    call resolves like a call on `self`, and a callee with no `Raises:` section
    is followed into its own raises and callees up to `SECTIONLESS_DEPTH`
    calls deep, with the chain named in the hit's variant. Omission hits grow;
    an extra declaration is reported only if it still never reaches the caller.
    """
    modules: dict[str, tuple[pathlib.Path, ast.Module, list[str]]] = {}
    for path in auditme.core.all_py_files(src_root):
        lines = auditme.core.source_lines(path)
        tree = auditme.core.read_and_parse(path)
        if tree is None:
            continue
        modules[auditme.core.module_dotted(path, src_root)] = (path, tree, lines)

    parents = package_class_parents(tree for _, tree, _ in modules.values())
    package_classes = set(parents)
    declared_by: dict[str, set[str]] = {}
    path_of: dict[str, pathlib.Path] = {}
    functions: list[tuple[str, str, str | None, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for module, (_, tree, _) in modules.items():
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append((module, f'{module}.{node.name}', None, node))
            elif isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        functions.append((module, f'{module}.{node.name}.{member.name}', node.name, member))
    node_of: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for module, qualname, _, node in functions:
        declared_by[qualname] = raises_section_names(ast.get_docstring(node) or '')
        node_of[qualname] = node
        path_of[qualname] = modules[module][0]

    known = {qualname: cls for _, qualname, cls, _ in functions}
    bindings_of = {module: auditme.core.call_bindings(tree, module, path.name == '__init__.py') for module, (path, tree, _) in modules.items()}
    aliases = auditme.core.reexport_aliases(bindings_of, known)

    def ancestors(name: str) -> set[str]:
        return class_lineage(name, parents) - {name}

    def is_domain(name: str) -> bool:
        return name in package_classes and name not in STDLIB_ERRORS

    def caught(name: str, around: tuple[HandlerLevel, ...]) -> bool:
        lineage = {name} | ancestors(name)
        return any(level_catches(level, lineage) for level in around)

    module_of = {qualname: module for module, qualname, _, _ in functions}

    def is_bound(site: ast.Call, callee: str) -> bool:
        callee_node = node_of[callee]
        on_name = isinstance(site.func, ast.Attribute) and isinstance(site.func.value, ast.Name)
        return on_name and (
            site.func.value.id == 'self' or (known[callee] is not None and any(ast.unparse(d) == 'classmethod' for d in callee_node.decorator_list))
        )

    def declared_reach(site: ast.Call, callee: str, around: tuple[HandlerLevel, ...]) -> list[str]:
        """The domain errors a callee's section declares that reach past `around` and the call's unset guards."""
        bound = is_bound(site, callee)
        return [
            name
            for name in sorted(declared_by[callee])
            if is_domain(name) and not caught(name, around) and not unset_optional_guard(node_of[callee], name, parents, site, bound)
        ]

    def escapes(qualname: str, hop: int, chain: tuple[str, ...]) -> dict[str, set[tuple[str, ...]]]:
        """The domain errors leaving the section-less function `qualname`, each with the chains it leaves through.

        A chain lists the functions it passes through, outermost first, and ends with
        the function whose section declares the error, or with `''` after the function that raises it.
        """
        found: dict[str, set[tuple[str, ...]]] = collections.defaultdict(set)
        on_path = (*chain, qualname)
        module = module_of[qualname]
        for site, around in nested_call_sites(node_of[qualname]):
            if isinstance(site, ast.Raise):
                name = raised_name(site)
                if name and is_domain(name) and not caught(name, around):
                    found[name].add((qualname, ''))
                continue
            if hop >= SECTIONLESS_DEPTH:
                continue
            callee = auditme.core.resolve_call(site, module, known[qualname], bindings_of[module], known, aliases, class_methods=True)
            if callee is None or callee in on_path:
                continue
            if 'Raises:' in (ast.get_docstring(node_of[callee]) or ''):
                for name in declared_reach(site, callee, around):
                    found[name].add((qualname, callee))
                continue
            for name, chains in escapes(callee, hop + 1, on_path).items():
                if not caught(name, around):
                    found[name].update((qualname, *inner) for inner in chains)
        return found

    def describe(chain: tuple[str, ...]) -> str:
        if chain == RAISED_HERE:
            return 'raised here'
        *wrappers, last = chain
        if last == '':
            *wrappers, raiser = wrappers
            source = f'raised by {raiser}'
        else:
            source = f'declared by {last}'
        return f'{source} via {", ".join(wrappers)}' if wrappers else source

    for module, qualname, cls, node in functions:
        doc = ast.get_docstring(node) or ''
        if 'Raises:' not in doc:
            continue
        declared = {name for name in raises_section_names(doc) if is_domain(name)}
        path, tree, lines = modules[module]
        imported = bindings_of[module]

        reached: dict[str, set[tuple[str, ...]]] = collections.defaultdict(set)
        for site, around in nested_call_sites(node):
            if isinstance(site, ast.Raise):
                name = raised_name(site)
                if name and is_domain(name) and not caught(name, around):
                    reached[name].add(RAISED_HERE)
                continue
            callee = auditme.core.resolve_call(site, module, cls, imported, known, aliases, class_methods=True)
            if callee is None or callee == qualname:
                continue
            if 'Raises:' in (ast.get_docstring(node_of[callee]) or ''):
                for name in declared_reach(site, callee, around):
                    reached[name].add((callee,))
                continue
            for name, chains in escapes(callee, 1, (qualname,)).items():
                if not caught(name, around):
                    reached[name].update(chains)

        rel = auditme.core.relpath(path, scope)
        accept = auditme.core.accept_reason(lines, node.lineno, rule='raises-section-drift')
        evidence = lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else ''
        for name in sorted(reached):
            if name in declared or ancestors(name) & declared:
                continue
            chains = reached[name]
            on_chains = {function for chain in chains for function in chain if function}
            auditme.core.emit(
                related=sorted({auditme.core.relpath(path_of[function], scope) for function in on_chains if path_of[function] != path}),
                rule='raises-section-drift',
                variant=f'{node.name}: Raises: omits {name}, {describe(min(chains, key=lambda chain: (len(chain), chain)))}',
                path=rel,
                line=node.lineno,
                evidence=evidence,
                accepted=bool(accept),
                accepted_reason=accept,
            )
        levels = function_levels(node.body)
        for name in sorted(declared):
            if any(name == found or name in ancestors(found) for found in reached):
                continue
            lineage = {name} | ancestors(name)
            if not any(level_catches(level, lineage) for level in levels):
                continue
            auditme.core.emit(
                rule='raises-section-drift',
                variant=f'{node.name}: Raises: declares {name}, which never reaches the caller',
                path=rel,
                line=node.lineno,
                evidence=evidence,
                accepted=bool(accept),
                accepted_reason=accept,
            )


__all__ = [
    'FILESYSTEM_TOUCHING_CALLS',
    'callable_short_name',
    'check_asymmetric_exception_translation',
    'check_bare_except_in_module_with_narrow_errors',
    'check_broad_except_wrong_level',
    'check_cli_entry_missing_error_envelope',
    'check_docstring_raises_mismatch',
    'check_except_interpolation',
    'check_failure_as_absence',
    'check_filesystem_envelope_gap',
    'check_filesystem_op_without_envelope',
    'check_get_container_default_then_method_call',
    'check_inconsistent_error_translation',
    'check_layer_has_domain_error_but_raises_stdlib',
    'check_logger_exception_graceful_degradation',
    'check_missing_raises_section',
    'check_mixed_raise_types',
    'check_raises_section_drift',
    'check_sibling_error_no_common_base',
    'check_silent_broad_except',
    'check_translator_envelope_gap',
    'check_try_wrapping_with_too_broad',
    'class_lineage',
    'is_broad_handler',
    'package_class_parents',
    'raises_section_names',
    'translator_envelopes',
]
