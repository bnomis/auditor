import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import collections.abc
    import pathlib


# Calls A9 counts as I/O, besides the filesystem writes in
# `SIDE_EFFECT_CALL_NAMES` (which the build rule and the T2 lister share).
# An entry is a dotted suffix of the callee's source text, so `run` only
# counts as `subprocess.run`. Path normalisation (`resolve`, `absolute`,
# `expanduser`, `os.path.realpath`) is deliberately absent.
PURE_NAME_IO_CALLS = frozenset(
    {
        'datetime.now',
        'datetime.utcnow',
        'exists',
        'is_dir',
        'is_file',
        'open',
        'os.system',
        'read_bytes',
        'read_text',
        'subprocess.Popen',
        'subprocess.call',
        'subprocess.check_call',
        'subprocess.check_output',
        'subprocess.run',
        'time.time',
    }
)


def io_call_name(call: ast.Call) -> str | None:
    """The `PURE_NAME_IO_CALLS` entry the call matches, or None."""
    text = ast.unparse(call.func)
    for entry in sorted(PURE_NAME_IO_CALLS):
        if text == entry or text.endswith('.' + entry):
            return entry
    return None


def registered_check_names(src_root: pathlib.Path) -> frozenset[str]:
    """Names of functions the corpus registers: a member of a module-level
    tuple, list, set or dict-value literal, or decorated by a function the
    corpus defines. The registration is the positive evidence A9 asks for.
    """
    trees = [tree for tree in (auditor.api.read_and_parse(path) for path in auditor.api.all_py_files(src_root)) if tree]
    defined = {node.name for tree in trees for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}

    def short(expr: ast.expr) -> str | None:
        if isinstance(expr, ast.Call):
            expr = expr.func
        if isinstance(expr, ast.Name):
            return expr.id
        if isinstance(expr, ast.Attribute):
            return expr.attr
        return None

    names: set[str] = set()
    for tree in trees:
        for stmt in tree.body:
            value = stmt.value if isinstance(stmt, (ast.Assign, ast.AnnAssign)) else None
            if isinstance(value, ast.Dict):
                members: list[ast.expr] = [v for v in value.values if v is not None]
            elif isinstance(value, (ast.Tuple, ast.List, ast.Set)):
                members = list(value.elts)
            else:
                continue
            names.update(name for name in (short(m) for m in members) if name)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(short(dec) in defined for dec in node.decorator_list):
                names.add(node.name)
    return frozenset(names)


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions whose name suggests a pure query/resolution but
    whose body calls a disk-write or I/O function.

    Signal:
      - Function name starts with `resolve_`, `find_`, `get_`, `check_`,
        `parse_`, `is_`, `has_`, `validate_`, `count_` or `allocate_`.
      - Function body contains a call whose callee short-name is in
        `auditor.api.SIDE_EFFECT_CALL_NAMES` (filesystem writes), or a call
        in `PURE_NAME_IO_CALLS` (opening or reading a file, testing for
        existence, subprocess, the clock).
      - The call is not inside a nested `def` (otherwise we'd flag factory
        functions that return a closure).
      - A `check_` function the corpus registers (a member of a module-level
        tuple, list, set or dict-value literal, or decorated by a package
        function) is not read as pure-named.
    """
    # `compute_` / `build_` are covered by check_build_name_has_side_effect
    # which documents allowed exceptions per-call-site rather than banning
    # the prefix outright. `load_` is deliberately omitted: load_* functions
    # legitimately perform IO.
    PURE_PREFIXES = ('resolve_', 'find_', 'get_', 'check_', 'parse_', 'is_', 'has_', 'validate_', 'count_', 'allocate_')
    registered = registered_check_names(src_root)
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
            if node.name.startswith('check_') and node.name in registered:
                continue

            # Walk only the direct body (and its nested statements) but not
            # nested function definitions
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
                if callee_short not in auditor.api.SIDE_EFFECT_CALL_NAMES:
                    callee_short = io_call_name(sub)
                if callee_short is None:
                    continue
                accept = auditor.api.accept_reason(lines, sub.lineno, rule='pure-name-has-side-effect')
                auditor.api.emit(
                    rule='pure-name-has-side-effect',
                    variant=f'{node.name} calls side-effect `{callee_short.rpartition(".")[2]}` despite name implying a pure query',
                    path=rel,
                    line=sub.lineno,
                    evidence=(lines[sub.lineno - 1].strip()[:200] if sub.lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
                break  # one finding per function is enough
