import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import collections.abc
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `build_*` / `compute_*` / `make_*` functions that call subprocess, clock,
    uuid, random, or filesystem-write primitives. `build_*` names imply
    pure assembly from inputs; the listed side-effect calls contradict
    that contract.

    Signal:
      - Function name starts with `build_`, `compute_` or `make_`.
      - Function body contains a call whose callee short-name is in the
        side-effect set below (extends `SIDE_EFFECT_CALL_NAMES` with
        `subprocess.run`, `datetime.now`, `uuid.uuid4`, `time.time`).
      - The call is not inside a nested function.

    The separate `check_pure_name_has_side_effect` covers the 9 other
    pure prefixes; `build_`/`compute_` are split out because their
    side-effect enumerations include clock/uuid (not relevant to the
    others) and because reporting's `build_*_data` family has a large
    number of accepted-via-comment sites that would dominate the output
    if bundled.
    """
    BUILD_SIDE_EFFECTS = auditor.api.SIDE_EFFECT_CALL_NAMES | {
        'run',  # subprocess.run
        'check_output',
        'check_call',
        'Popen',
        'now',
        'utcnow',  # datetime.now / datetime.utcnow
        'time',
        'monotonic',
        'perf_counter',
        'uuid1',
        'uuid3',
        'uuid4',
        'uuid5',
        'random',
        'randint',
        'choice',
        'shuffle',
    }
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith(('build_', 'compute_', 'make_')):
                continue

            def walk_non_nested(n: ast.AST) -> collections.abc.Iterator[ast.AST]:
                for sub in ast.iter_child_nodes(n):
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                        continue
                    yield sub
                    yield from walk_non_nested(sub)

            for sub in walk_non_nested(node):
                if not isinstance(sub, ast.Call):
                    continue
                callee_short = None
                if isinstance(sub.func, ast.Name):
                    callee_short = sub.func.id
                elif isinstance(sub.func, ast.Attribute):
                    callee_short = sub.func.attr
                if callee_short not in BUILD_SIDE_EFFECTS:
                    continue
                accept = auditor.api.accept_reason(lines, sub.lineno, rule='build-name-has-side-effect')
                auditor.api.emit(
                    rule='build-name-has-side-effect',
                    variant=f'{node.name} calls side-effect `{callee_short}` despite `build_`/`compute_`/`make_` name',
                    path=rel,
                    line=sub.lineno,
                    evidence=(lines[sub.lineno - 1].strip()[:200] if sub.lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
                break
