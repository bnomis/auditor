import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


SUBPROCESS_CALL_RE = re.compile(r'\b(subprocess|sp)\.(run|check_output|check_call|Popen|call)\b')


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions that invoke `subprocess.run` / `subprocess.check_output`
    / `subprocess.check_call` without a memoisation decorator, when the
    function name suggests a request-invariant query.

    Signal:
      - Function body calls one of `subprocess.run|check_output|check_call|
        Popen|call`.
      - Function has NO `@functools.cache`, `@functools.lru_cache`, `@cache`,
        or `@lru_cache` decorator.
      - Function name starts with a pure-query prefix (`get_`, `resolve_`,
        `compute_`, `find_`, `check_`, `parse_`, `is_`, `has_`, `validate_`,
        `count_`). Other names are assumed per-call intentional.
    """
    PURE_PREFIXES = ('get_', 'resolve_', 'compute_', 'find_', 'check_', 'parse_', 'is_', 'has_', 'validate_', 'count_')
    CACHE_DECORATORS = {'cache', 'lru_cache', 'cached', 'functools.cache', 'functools.lru_cache'}
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(node.name.startswith(p) for p in PURE_PREFIXES):
                continue
            # Collect decorator names
            decorators: set[str] = set()
            for dec in node.decorator_list:
                target = dec.func if isinstance(dec, ast.Call) else dec
                decorators.add(ast.unparse(target))
            if decorators & CACHE_DECORATORS:
                continue
            # Scan body for subprocess calls
            hit_line = None
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                call_src = ast.unparse(inner.func)
                if SUBPROCESS_CALL_RE.search(call_src):
                    hit_line = inner.lineno
                    break
            if hit_line is None:
                continue
            accept = auditor.api.accept_reason(lines, hit_line, rule='subprocess-without-memoisation')
            auditor.api.emit(
                rule='subprocess-without-memoisation',
                variant=f'{node.name} shells out via subprocess without @functools.cache',
                path=rel,
                line=hit_line,
                evidence=(lines[hit_line - 1].strip()[:200] if hit_line <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
