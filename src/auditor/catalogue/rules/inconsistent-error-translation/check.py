import ast
import collections
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
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
    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        rel = auditor.api.relpath(path, scope)
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
    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
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
            lines = auditor.api.source_lines(full_path)
            accept = auditor.api.accept_reason(lines, lineno, rule='inconsistent-error-translation')
            auditor.api.emit(
                rule='inconsistent-error-translation',
                variant=f'{callee_full} raises {caught}; callers translate to {sorted(targets)}',
                path=rel,
                line=lineno,
                evidence=f'{caught} -> {sorted(targets)}',
                accepted=bool(accept),
                accepted_reason=accept,
            )
