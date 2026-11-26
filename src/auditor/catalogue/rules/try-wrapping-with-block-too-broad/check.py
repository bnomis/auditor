import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
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
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
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
                accept = auditor.api.accept_reason(lines, handler.lineno, rule='try-wrapping-with-block-too-broad')
                auditor.api.emit(
                    rule='try-wrapping-with-block-too-broad',
                    variant=f'except handler re-invokes {sorted(overlap)!r} from the wrapped `with` body',
                    path=rel,
                    line=handler.lineno,
                    evidence=(lines[handler.lineno - 1].strip()[:200] if handler.lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
