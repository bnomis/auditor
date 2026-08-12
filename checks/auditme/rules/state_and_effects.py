"""Checks on mutation, side effects and hidden state."""

from __future__ import annotations
import ast
import pathlib
import re
from collections import defaultdict

from auditme.core import _accept_reason, _all_py_files, _emit, _relpath, _source_lines


_DISK_IO_NAMES = {
    'open', 'mkdir', 'rmdir', 'unlink', 'rmtree', 'makedirs', 'remove',
    'read_text', 'write_text', 'read_bytes', 'write_bytes', 'touch',
    'iterdir', 'glob', 'rglob', 'exists', 'is_file', 'is_dir', 'stat',
    'copy', 'copytree', 'move', 'rename', 'replace', 'symlink_to',
    'mkstemp', 'mkdtemp',
}

def check_constructor_disk_io(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag disk I/O operations inside `__init__` methods. Constructors
    should accept already-loaded data, not perform I/O on demand."""
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            for member in cls.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if member.name != '__init__':
                    continue
                for inner in ast.walk(member):
                    if not isinstance(inner, ast.Call):
                        continue
                    fname = None
                    if isinstance(inner.func, ast.Name):
                        fname = inner.func.id
                    elif isinstance(inner.func, ast.Attribute):
                        fname = inner.func.attr
                    if fname not in _DISK_IO_NAMES:
                        continue
                    accept = _accept_reason(lines, inner.lineno, rule='constructor-disk-io')
                    _emit(
                        rule='constructor-disk-io',
                        variant=f'{cls.name}.__init__ calls disk-IO `{fname}`',
                        path=rel,
                        line=inner.lineno,
                        evidence=lines[inner.lineno - 1].strip()[:200]
                        if inner.lineno <= len(lines) else '',
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )

def check_silent_self_mutation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag methods (other than __init__ / __post_init__ / setters / setX-named
    methods / clear / reset / load) that reassign `self.<attr>` where `<attr>`
    was set from a constructor argument of the same name in __init__.

    The pattern is: a method whose name signals a non-mutating operation
    (a stage, a compute, a build, a load, a predict, a tokenize, a train,
    an evaluate) silently mutates state the caller passed in. Downstream
    stages consume the mutation through `self.<attr>` but a Python-API
    caller holding a reference to the original sees their view drift.
    """
    MUTATING_METHOD_NAMES = {
        'set', 'reset', 'clear', 'update', 'mutate', 'merge', 'replace',
        'apply', 'patch', 'override',
    }
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            # Find attrs assigned in __init__ from a same-named argument
            owned_attrs: set[str] = set()
            init = next(
                (m for m in cls.body
                 if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and m.name == '__init__'),
                None,
            )
            if init is not None:
                arg_names = {a.arg for a in init.args.args}
                for inner in ast.walk(init):
                    if not isinstance(inner, ast.Assign):
                        continue
                    for tgt in inner.targets:
                        if (isinstance(tgt, ast.Attribute)
                                and isinstance(tgt.value, ast.Name)
                                and tgt.value.id == 'self'
                                and isinstance(inner.value, ast.Name)
                                and inner.value.id == tgt.attr
                                and inner.value.id in arg_names):
                            owned_attrs.add(tgt.attr)
            if not owned_attrs:
                continue
            for member in cls.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if member.name in {'__init__', '__post_init__', '__setattr__'}:
                    continue
                lname = member.name.lower()
                # Method names that signal mutation are allowed (caller knows)
                if any(lname.startswith(p + '_') or lname == p for p in MUTATING_METHOD_NAMES):
                    continue
                if lname.startswith('set_'):
                    continue
                for inner in ast.walk(member):
                    if not isinstance(inner, ast.Assign):
                        continue
                    for tgt in inner.targets:
                        if not (isinstance(tgt, ast.Attribute)
                                and isinstance(tgt.value, ast.Name)
                                and tgt.value.id == 'self'):
                            continue
                        if tgt.attr not in owned_attrs:
                            continue
                        accept = _accept_reason(lines, inner.lineno, rule='silent-self-mutation')
                        _emit(
                            rule='silent-self-mutation',
                            variant=f'{cls.name}.{member.name} reassigns self.{tgt.attr}',
                            path=rel,
                            line=inner.lineno,
                            evidence=(lines[inner.lineno - 1].strip()[:200]
                                      if inner.lineno <= len(lines) else ''),
                            accepted=bool(accept),
                            accepted_reason=accept,
                        )

def check_return_value_shadows_instance_attr(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag class methods that return a value named identically to an
    instance attribute (either alone or as part of a tuple). The
    contract "caller must reassign self.X" is implicit and unenforced.

    Signal:
      - Class C stores `self.X` in `__init__` from a same-named arg.
      - A method M on C (other than __init__/__post_init__) returns
        either `X` directly or a tuple that contains a local `patched_X`
        / `new_X` / `X` (i.e. a Name whose id is `X` or contains `X`).
      - The method's docstring or body mutates the local value away
        from `self.X`.

    This is the `Pipeline.tokenize` pattern: returns `(tokenized,
    patched_config)` where `patched_config` is a divergent copy of
    `self.config`; callers must `self.config = patched_config` or the
    instance silently drifts.
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            owned_attrs: set[str] = set()
            init = next(
                (m for m in cls.body
                 if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and m.name == '__init__'),
                None,
            )
            if init is None:
                continue
            arg_names = {a.arg for a in init.args.args}
            for inner in ast.walk(init):
                if not isinstance(inner, ast.Assign):
                    continue
                for tgt in inner.targets:
                    if (isinstance(tgt, ast.Attribute)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == 'self'
                            and isinstance(inner.value, ast.Name)
                            and inner.value.id == tgt.attr
                            and inner.value.id in arg_names):
                        owned_attrs.add(tgt.attr)
            if not owned_attrs:
                continue
            for member in cls.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if member.name in {'__init__', '__post_init__'}:
                    continue
                # Look for Return nodes inside the method body
                for ret in ast.walk(member):
                    if not isinstance(ret, ast.Return):
                        continue
                    returned_names: list[str] = []
                    if isinstance(ret.value, ast.Name):
                        returned_names.append(ret.value.id)
                    elif isinstance(ret.value, ast.Tuple):
                        for elt in ret.value.elts:
                            if isinstance(elt, ast.Name):
                                returned_names.append(elt.id)
                    for rname in returned_names:
                        for attr in owned_attrs:
                            # exact match OR contains attr name (e.g. `patched_config`)
                            if rname == attr or (f'_{attr}' in rname) or (f'{attr}_' in rname):
                                # also require that the method body assigns a local
                                # derived from self.<attr> to that name (to avoid FPs
                                # where the method just happens to have a local named X)
                                has_derivation = False
                                for inner in ast.walk(member):
                                    if (isinstance(inner, ast.Assign)
                                            and any(isinstance(t, ast.Name) and t.id == rname
                                                    for t in inner.targets)):
                                        src = ast.unparse(inner.value) if hasattr(ast, 'unparse') else ''
                                        if f'self.{attr}' in src:
                                            has_derivation = True
                                            break
                                if not has_derivation:
                                    continue
                                accept = _accept_reason(lines, ret.lineno, rule='return-shadows-instance-attr')
                                _emit(
                                    rule='return-shadows-instance-attr',
                                    variant=f'{cls.name}.{member.name} returns `{rname}` which shadows self.{attr}; callers must reassign',
                                    path=rel,
                                    line=ret.lineno,
                                    evidence=(lines[ret.lineno - 1].strip()[:200]
                                              if ret.lineno <= len(lines) else ''),
                                    accepted=bool(accept),
                                    accepted_reason=accept,
                                )
                                break

def check_parameter_mutation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions that mutate a parameter's dict/list items while
    the function name or docstring suggests pure validation / checking.

    Signal:
      - Function F has parameter P (typed as dict/list or named like
        `merged`, `config`, `data`, `params`).
      - F's name starts with `check_`, `validate_`, `is_`, `has_`,
        `get_`, `compute_`, `resolve_`, `parse_`.
      - F's body contains `P[key] = value` or `P.update(...)` or
        `P.pop(...)` or `P.append(...)` or similar mutation on P.
    """
    # `compute_` is intentionally omitted - HF Trainer's `compute_loss` and
    # similar methods routinely mutate their `inputs` dict. The pure-naming
    # contract does not hold for overridden framework methods.
    PURE_PREFIXES = ('check_', 'validate_', 'is_', 'has_', 'get_',
                     'resolve_', 'parse_', 'find_', 'count_')
    MUTATION_METHODS = {'update', 'pop', 'append', 'extend', 'insert',
                        'remove', 'clear', 'setdefault', 'popitem'}
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(node.name.startswith(p) for p in PURE_PREFIXES):
                continue
            param_names = {a.arg for a in node.args.args}
            if not param_names:
                continue
            # Walk body for mutation of a parameter
            for inner in ast.walk(node):
                # item assignment: param[k] = v
                if isinstance(inner, ast.Assign):
                    for tgt in inner.targets:
                        if isinstance(tgt, ast.Subscript) and isinstance(tgt.value, ast.Name):
                            if tgt.value.id in param_names:
                                accept = _accept_reason(lines, inner.lineno, rule='parameter-mutation-in-pure-function')
                                _emit(
                                    rule='parameter-mutation-in-pure-function',
                                    variant=f'{node.name} mutates parameter `{tgt.value.id}` via item assignment',
                                    path=rel,
                                    line=inner.lineno,
                                    evidence=(lines[inner.lineno - 1].strip()[:200]
                                              if inner.lineno <= len(lines) else ''),
                                    accepted=bool(accept),
                                    accepted_reason=accept,
                                )
                # augmented assignment: param[k] += v
                if isinstance(inner, ast.AugAssign):
                    if (isinstance(inner.target, ast.Subscript)
                            and isinstance(inner.target.value, ast.Name)
                            and inner.target.value.id in param_names):
                        accept = _accept_reason(lines, inner.lineno, rule='parameter-mutation-in-pure-function')
                        _emit(
                            rule='parameter-mutation-in-pure-function',
                            variant=f'{node.name} mutates parameter `{inner.target.value.id}` via augmented assignment',
                            path=rel,
                            line=inner.lineno,
                            evidence=(lines[inner.lineno - 1].strip()[:200]
                                      if inner.lineno <= len(lines) else ''),
                            accepted=bool(accept),
                            accepted_reason=accept,
                        )
                # method call: param.update(...), param.append(...)
                if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute):
                    if (isinstance(inner.func.value, ast.Name)
                            and inner.func.value.id in param_names
                            and inner.func.attr in MUTATION_METHODS):
                        accept = _accept_reason(lines, inner.lineno, rule='parameter-mutation-in-pure-function')
                        _emit(
                            rule='parameter-mutation-in-pure-function',
                            variant=f'{node.name} mutates parameter `{inner.func.value.id}` via `.{inner.func.attr}()`',
                            path=rel,
                            line=inner.lineno,
                            evidence=(lines[inner.lineno - 1].strip()[:200]
                                      if inner.lineno <= len(lines) else ''),
                            accepted=bool(accept),
                            accepted_reason=accept,
                        )

_SIDE_EFFECT_CALL_NAMES = {
    'mkdir', 'rmdir', 'unlink', 'rmtree', 'makedirs', 'remove',
    'write_text', 'write_bytes', 'touch', 'copytree',
    'symlink_to', 'mkstemp', 'mkdtemp',
}

def check_pure_name_has_side_effect(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions whose name suggests a pure query/resolution but
    whose body calls a disk-write/IO side-effect function.

    Signal:
      - Function name starts with `resolve_`, `find_`, `get_`, `compute_`,
        `check_`, `parse_`, `is_`, `has_`, `validate_`, `count_`, `build_`.
      - Function body contains a call whose callee short-name is in
        {mkdir, rmdir, unlink, rmtree, makedirs, remove, write_text,
         write_bytes, touch, copy, copytree, move, rename, replace,
         symlink_to, mkstemp, mkdtemp, dump, dumps, save}.
      - The side-effect call is not inside a nested `def` (otherwise
        we'd flag factory functions that return a closure).
    """
    # `compute_` / `build_` are covered by check_build_name_has_side_effect
    # which documents allowed exceptions per-call-site rather than banning
    # the prefix outright. `load_` is deliberately omitted: load_* functions
    # legitimately perform IO.
    PURE_PREFIXES = ('resolve_', 'find_', 'get_', 'check_',
                     'parse_', 'is_', 'has_', 'validate_', 'count_',
                     'allocate_')
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(node.name.startswith(p) for p in PURE_PREFIXES):
                continue
            # Walk only the direct body (and its nested statements) but not
            # nested function definitions
            def walk_non_nested(n):
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
                if callee_short not in _SIDE_EFFECT_CALL_NAMES:
                    continue
                accept = _accept_reason(lines, sub.lineno, rule='pure-name-has-side-effect')
                _emit(
                    rule='pure-name-has-side-effect',
                    variant=f'{node.name} calls side-effect `{callee_short}` despite name implying a pure query',
                    path=rel,
                    line=sub.lineno,
                    evidence=(lines[sub.lineno - 1].strip()[:200]
                              if sub.lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
                break  # one finding per function is enough

def check_mutable_store_without_copy(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `__init__` methods that store a parameter typed as dict/list
    onto `self.<name>` without taking a defensive copy. Callers share
    the reference with the instance; if anyone mutates later, all
    observers see the change.

    Signal:
      - `__init__` has a parameter P whose annotation mentions `dict`
        or `list` (at the top level; allows `dict | None`, `list[str]`,
        `dict[str, Any]` forms).
      - The body assigns `self.<P> = <P>` with no `.copy()` /
        `.deepcopy()` / `dict(...)` / `list(...)` / `frozenset(...)`
        wrapping.
      - The parameter is not annotated as `frozenset`, `tuple`, or a
        project dataclass (which is immutable by convention).
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            init = next(
                (m for m in cls.body
                 if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and m.name == '__init__'),
                None,
            )
            if init is None:
                continue
            # Collect args typed as dict/list at top level of annotation
            mutable_args: set[str] = set()
            for arg in init.args.args:
                if arg.annotation is None:
                    continue
                try:
                    ann_src = ast.unparse(arg.annotation)
                except Exception:
                    continue
                # top-level `dict` or `list` (allow `| None`, subscripts)
                # but not inside tuple/frozenset/etc.
                normalised = ann_src.split('|')[0].strip()
                root = re.match(r'^([a-zA-Z_][a-zA-Z_0-9]*)', normalised)
                if not root:
                    continue
                root_name = root.group(1)
                if root_name in {'dict', 'list'}:
                    mutable_args.add(arg.arg)
            if not mutable_args:
                continue
            # Walk init body for self.X = X where X in mutable_args and
            # the RHS is a bare Name (no .copy() wrapping)
            for stmt in init.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                for tgt in stmt.targets:
                    if not (isinstance(tgt, ast.Attribute)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == 'self'):
                        continue
                    if not isinstance(stmt.value, ast.Name):
                        continue
                    if stmt.value.id not in mutable_args:
                        continue
                    if tgt.attr != stmt.value.id:
                        continue
                    accept = _accept_reason(lines, stmt.lineno, rule='mutable-store-without-copy')
                    _emit(
                        rule='mutable-store-without-copy',
                        variant=f'{cls.name}.__init__ stores dict/list parameter `{stmt.value.id}` by reference',
                        path=rel,
                        line=stmt.lineno,
                        evidence=(lines[stmt.lineno - 1].strip()[:200]
                                  if stmt.lineno <= len(lines) else ''),
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )

def check_assert_never_missing(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `if/elif` chains that dispatch on string equality of a single
    variable and either (a) terminate without an `else` or (b) end with a
    plain `else:` body, instead of `else: typing.assert_never(var)`.

    Only chains with >= 3 string-equality tests are considered (a 2-arm
    if/else is legitimately bi-valued). The variable may be typed as
    `Literal[...]` or an enum, but we cannot verify the type mechanically
    across files; the predicate is kept purely structural (count + shape).

    Cure: replace the trailing `else:` (or absent `else`) with
        else:
            typing.assert_never(var)
    which lets the type-checker verify exhaustion.
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            # Walk the chain, collecting tested variable names
            chain_var: str | None = None
            chain_len = 0
            cursor: ast.If | None = node
            terminal_else: list[ast.stmt] | None = None
            consistent = True
            while cursor is not None:
                test = cursor.test
                var_name = _extract_string_eq_var(test)
                if var_name is None:
                    consistent = False
                    break
                if chain_var is None:
                    chain_var = var_name
                elif var_name != chain_var:
                    consistent = False
                    break
                chain_len += 1
                orelse = cursor.orelse
                if not orelse:
                    terminal_else = None
                    cursor = None
                elif len(orelse) == 1 and isinstance(orelse[0], ast.If):
                    cursor = orelse[0]
                else:
                    terminal_else = orelse
                    cursor = None
            if not consistent or chain_var is None or chain_len < 3:
                continue
            # Already uses assert_never? OK.
            if terminal_else is not None:
                has_assert_never = False
                for stmt in terminal_else:
                    for sub in ast.walk(stmt):
                        if isinstance(sub, ast.Call):
                            src = ''
                            try:
                                src = ast.unparse(sub.func)
                            except Exception:
                                pass
                            if 'assert_never' in src:
                                has_assert_never = True
                                break
                    if has_assert_never:
                        break
                if has_assert_never:
                    continue
            accept = _accept_reason(lines, node.lineno, rule='assert-never-missing')
            _emit(
                rule='assert-never-missing',
                variant=(f'if/elif chain on `{chain_var}` with {chain_len} string-equality arms '
                         f'{"has fall-through else" if terminal_else else "has no else"}; '
                         f'should end with `else: typing.assert_never({chain_var})`'),
                path=rel,
                line=node.lineno,
                evidence=(lines[node.lineno - 1].strip()[:200]
                          if node.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )

def _extract_string_eq_var(test: ast.expr) -> str | None:
    """Return `name` if `test` is `name == "literal"` or `"literal" == name`,
    otherwise None."""
    if not isinstance(test, ast.Compare):
        return None
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return None
    left = test.left
    right = test.comparators[0]
    if (isinstance(left, ast.Name)
            and isinstance(right, ast.Constant)
            and isinstance(right.value, str)):
        return left.id
    if (isinstance(right, ast.Name)
            and isinstance(left, ast.Constant)
            and isinstance(left.value, str)):
        return right.id
    return None

def check_build_name_has_side_effect(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `build_*` / `compute_*` functions that call subprocess, clock,
    uuid, random, or filesystem-write primitives. `build_*` names imply
    pure assembly from inputs; the listed side-effect calls contradict
    that contract.

    Signal:
      - Function name starts with `build_` or `compute_`.
      - Function body contains a call whose callee short-name is in the
        side-effect set below (extends `_SIDE_EFFECT_CALL_NAMES` with
        `subprocess.run`, `datetime.now`, `uuid.uuid4`, `time.time`).
      - The call is not inside a nested function.

    The separate `check_pure_name_has_side_effect` covers the 9 other
    pure prefixes; `build_`/`compute_` are split out because their
    side-effect enumerations include clock/uuid (not relevant to the
    others) and because reporting's `build_*_data` family has a large
    number of accepted-via-comment sites that would dominate the output
    if bundled.
    """
    BUILD_SIDE_EFFECTS = _SIDE_EFFECT_CALL_NAMES | {
        'run',       # subprocess.run
        'check_output', 'check_call', 'Popen',
        'now', 'utcnow',  # datetime.now / datetime.utcnow
        'time', 'monotonic', 'perf_counter',
        'uuid1', 'uuid3', 'uuid4', 'uuid5',
        'random', 'randint', 'choice', 'shuffle',
    }
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not (node.name.startswith('build_') or node.name.startswith('compute_')):
                continue
            def walk_non_nested(n):
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
                accept = _accept_reason(lines, sub.lineno, rule='build-name-has-side-effect')
                _emit(
                    rule='build-name-has-side-effect',
                    variant=f'{node.name} calls side-effect `{callee_short}` despite `build_`/`compute_` name',
                    path=rel,
                    line=sub.lineno,
                    evidence=(lines[sub.lineno - 1].strip()[:200]
                              if sub.lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
                break

def check_mutable_module_level_exported(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag module-level mutable containers that are imported by name from
    another module in the same corpus. Externally-imported globals should
    be immutable so callers cannot mutate shared state.

    Signal:
      - Module-level `NAME = {...}` / `NAME = [...]` / `NAME = set(...)`
        where the RHS is NOT wrapped in `types.MappingProxyType`,
        `frozenset`, or `tuple`.
      - `NAME` appears in some other file's `from <this-module> import NAME`.

    Locked enumeration (per SKILL.md A20):
      dict literal -> must be `types.MappingProxyType(...)`.
      set literal  -> must be `frozenset(...)`.
      list literal -> must be `tuple(...)`.

    Private (non-imported) mutable globals are NOT flagged - that is a
    different rule.
    """
    # First pass: for every module, collect top-level Assign/AnnAssign
    # targets whose RHS is a bare dict/list/set literal, plus the module
    # dotted-import path.
    candidates: list[tuple[pathlib.Path, ast.stmt, str]] = []
    module_name_of: dict[pathlib.Path, str] = {}
    for path in _all_py_files(src_root):
        # Canonical module path (from src root, dotted)
        parts = path.relative_to(src_root).with_suffix('').parts
        if parts and parts[-1] == '__init__':
            parts = parts[:-1]
        module_dotted = '.'.join((src_root.name,) + parts)
        module_name_of[path] = module_dotted
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in tree.body:
            value = None
            name = None
            if isinstance(node, ast.Assign):
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    name = node.targets[0].id
                    value = node.value
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.value is not None:
                    name = node.target.id
                    value = node.value
            if name is None or value is None:
                continue
            if not isinstance(value, (ast.Dict, ast.List, ast.Set)):
                continue
            if name.startswith('_'):
                continue
            candidates.append((path, node, name))

    if not candidates:
        return

    # Second pass: for each candidate, check whether ANY other file uses
    # that name, either via `from <module> import NAME` or via attribute
    # access of the form `<module>.NAME`. The project coding standard
    # uses full-dotted attribute access instead of `from X import Y`, so
    # we must catch both forms.
    imports_of: dict[tuple[str, str], list[tuple[pathlib.Path, int]]] = defaultdict(list)
    for path in _all_py_files(src_root):
        try:
            src_text = path.read_text(encoding='utf-8')
            tree = ast.parse(src_text)
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                for alias in node.names:
                    imports_of[(node.module, alias.name)].append((path, node.lineno))
            elif isinstance(node, ast.Attribute):
                # Build dotted prefix for nested attribute chains:
                # `feathf.evaluation.primary.METRICS_BY_HEAD` -> module
                # `feathf.evaluation.primary`, name `METRICS_BY_HEAD`.
                parts = []
                cur: ast.AST = node
                while isinstance(cur, ast.Attribute):
                    parts.append(cur.attr)
                    cur = cur.value
                if not isinstance(cur, ast.Name):
                    continue
                parts.append(cur.id)
                parts.reverse()
                if len(parts) < 2:
                    continue
                module = '.'.join(parts[:-1])
                name = parts[-1]
                imports_of[(module, name)].append((path, node.lineno))

    for path, assign_node, name in candidates:
        module = module_name_of[path]
        importers = imports_of.get((module, name), [])
        # Only flag if imported from a DIFFERENT file
        external_importers = [(p, ln) for p, ln in importers if p != path]
        if not external_importers:
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        accept = _accept_reason(lines, assign_node.lineno, rule='mutable-module-level-exported')
        kind = type(assign_node.value).__name__
        required_wrap = {
            'Dict': 'types.MappingProxyType(...)',
            'Set': 'frozenset(...)',
            'List': 'tuple(...)',
        }.get(kind, '(immutable wrapper)')
        _emit(
            rule='mutable-module-level-exported',
            variant=(f'{name} is a mutable {kind.lower()} literal imported by '
                     f'{len(external_importers)} other file(s); wrap in {required_wrap}'),
            path=rel,
            line=assign_node.lineno,
            evidence=(lines[assign_node.lineno - 1].strip()[:200]
                      if assign_node.lineno <= len(lines) else ''),
            accepted=bool(accept),
            accepted_reason=accept,
        )

_CALLBACK_METHOD_RE = re.compile(r'^on_(step|log|evaluate|train_\w+|batch_\w+|epoch_\w+|predict_\w+|save|init_\w+)$')

def check_callback_hotpath_io(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag HF `Trainer` callback methods whose body contains per-event
    filesystem IO (`Path.open`, bare `open`, `Path.mkdir`, `write_text`,
    `write_bytes`).

    Signal:
      - Method is a member of a class that inherits from any `*Callback`
        / `TrainerCallback` base (matched by bare-name ancestry, since we
        don't resolve imports).
      - Method name matches `on_(step|log|evaluate|train_*|batch_*|epoch_*|predict_*|save|init_*)`.
      - Method body calls `open`, `Path.open`, `.mkdir`, `.write_text`,
        `.write_bytes`.
      - The call is not inside an attribute-cache guard
        (`if self._opened is None: ...`) - we can't verify that
        mechanically, so the check is coarse: any such call is flagged.

    One-time setup belongs in `__init__`; if the setup cannot move there
    (rare), add `# auditme: accept <reason>`.
    """
    HOT_IO = {'open', 'mkdir', 'write_text', 'write_bytes'}
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            # Heuristic: class inherits from a *Callback base OR file
            # imports TrainerCallback (we just check the class bases).
            base_names = []
            for b in cls.bases:
                try:
                    base_names.append(ast.unparse(b))
                except Exception:
                    pass
            base_str = ' '.join(base_names)
            looks_like_callback = (
                'Callback' in base_str or 'TrainerCallback' in base_str
            )
            # Also accept if any method in the class matches the callback pattern
            has_callback_method = any(
                isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                and _CALLBACK_METHOD_RE.match(m.name)
                for m in cls.body
            )
            if not (looks_like_callback or has_callback_method):
                continue
            for method in cls.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not _CALLBACK_METHOD_RE.match(method.name):
                    continue
                for sub in ast.walk(method):
                    if not isinstance(sub, ast.Call):
                        continue
                    short = None
                    if isinstance(sub.func, ast.Name):
                        short = sub.func.id
                    elif isinstance(sub.func, ast.Attribute):
                        short = sub.func.attr
                    if short not in HOT_IO:
                        continue
                    accept = _accept_reason(lines, sub.lineno, rule='callback-hotpath-io')
                    _emit(
                        rule='callback-hotpath-io',
                        variant=f'{cls.name}.{method.name} performs per-event `{short}`; move setup to __init__',
                        path=rel,
                        line=sub.lineno,
                        evidence=(lines[sub.lineno - 1].strip()[:200]
                                  if sub.lineno <= len(lines) else ''),
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )
                    break

def check_dataclass_optional_always_set(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag dataclass fields annotated as `X | None` (defaulting to
    `None`) where `__post_init__` unconditionally reassigns them to
    a non-None value. The `| None` is inaccurate - the field is never
    None after construction.

    Signal:
      - Class decorated with `@dataclass` or inheriting from a dataclass
        convention.
      - AnnAssign field `X: Y | None = <default>` (or `= field(default=None)`).
      - `__post_init__` method assigns `self.X = <expr>` unconditionally
        (not inside an `if`/`try`/`for`).
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            # Is it a dataclass? Check decorators
            is_dataclass = False
            for dec in cls.decorator_list:
                try:
                    dec_src = ast.unparse(dec)
                except Exception:
                    continue
                if 'dataclass' in dec_src:
                    is_dataclass = True
                    break
            if not is_dataclass:
                continue
            # Collect X | None fields defaulting to None
            nullable_fields: dict[str, int] = {}
            for item in cls.body:
                if not isinstance(item, ast.AnnAssign):
                    continue
                if not isinstance(item.target, ast.Name):
                    continue
                try:
                    ann_src = ast.unparse(item.annotation)
                except Exception:
                    continue
                if 'None' not in ann_src:
                    continue
                # Check default is None (direct or `field(default=None)`)
                default_is_none = False
                if item.value is None:
                    continue
                if isinstance(item.value, ast.Constant) and item.value.value is None:
                    default_is_none = True
                elif isinstance(item.value, ast.Call):
                    for kw in item.value.keywords:
                        if kw.arg == 'default' and isinstance(kw.value, ast.Constant) and kw.value.value is None:
                            default_is_none = True
                if default_is_none:
                    nullable_fields[item.target.id] = item.lineno
            if not nullable_fields:
                continue
            # Find __post_init__
            post_init = next(
                (m for m in cls.body
                 if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and m.name == '__post_init__'),
                None,
            )
            if post_init is None:
                continue
            # Check top-level body of __post_init__ for unconditional
            # `self.<X> = <non-None>` on each nullable field
            for stmt in post_init.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                for tgt in stmt.targets:
                    if not (isinstance(tgt, ast.Attribute)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == 'self'):
                        continue
                    if tgt.attr not in nullable_fields:
                        continue
                    # Check RHS is not None
                    if isinstance(stmt.value, ast.Constant) and stmt.value.value is None:
                        continue
                    field_lineno = nullable_fields[tgt.attr]
                    accept = _accept_reason(lines, field_lineno, rule='dataclass-optional-always-set')
                    _emit(
                        rule='dataclass-optional-always-set',
                        variant=f'{cls.name}.{tgt.attr} typed `X | None` but __post_init__ always assigns non-None',
                        path=rel,
                        line=field_lineno,
                        evidence=(lines[field_lineno - 1].strip()[:200]
                                  if field_lineno <= len(lines) else ''),
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )

def check_dead_local_init(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag function bodies where a local variable is assigned an
    initial value at the top of the body, then unconditionally reassigned
    before any use in all code paths.

    Simple signal (low-FP only):
      - First statement in function body is `x = <literal or empty constructor>`.
      - All subsequent statements in the function body before the first
        read of `x` are reassignments to `x` inside a closed branch
        structure (an `if/elif/else` chain where every branch ends with
        `return <expr involving x>` or with `x = ...`).

    Restricting to "initial empty-constructor assignment + exhaustive
    if/elif/else that returns" keeps the check low-FP.
    """
    EMPTY_CONSTRUCTORS = {'dict', 'list', 'set', 'tuple', 'frozenset'}
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = [s for s in func.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
            if len(body) < 2:
                continue
            first = body[0]
            if not isinstance(first, (ast.Assign, ast.AnnAssign)):
                continue
            targets = first.targets if isinstance(first, ast.Assign) else [first.target]
            if len(targets) != 1 or not isinstance(targets[0], ast.Name):
                continue
            var_name = targets[0].id
            value = first.value
            if value is None:
                continue
            is_empty_init = False
            if isinstance(value, ast.Dict) and not value.keys:
                is_empty_init = True
            elif isinstance(value, ast.List) and not value.elts:
                is_empty_init = True
            elif isinstance(value, ast.Set) and not value.elts:
                is_empty_init = True
            elif isinstance(value, ast.Tuple) and not value.elts:
                is_empty_init = True
            elif (isinstance(value, ast.Call)
                  and isinstance(value.func, ast.Name)
                  and value.func.id in EMPTY_CONSTRUCTORS
                  and not value.args
                  and not value.keywords):
                is_empty_init = True
            if not is_empty_init:
                continue
            # Check remaining body: is it an if/elif/else whose every
            # branch either returns or reassigns var_name before reading it?
            rest = body[1:]
            if len(rest) != 1:
                continue
            if_stmt = rest[0]
            if not isinstance(if_stmt, ast.If):
                continue
            # Walk every branch arm; ensure it starts with an assignment
            # to var_name or a return, not a read.
            def _branch_overrides(branch: list) -> bool:
                for s in branch:
                    # Assigns var_name before reading
                    if isinstance(s, (ast.Assign, ast.AnnAssign)):
                        tgts = s.targets if isinstance(s, ast.Assign) else [s.target]
                        for t in tgts:
                            if isinstance(t, ast.Name) and t.id == var_name:
                                return True
                    # Returns something that uses var_name - don't flag;
                    # this isn't dead init
                    if isinstance(s, ast.Return):
                        if s.value is not None:
                            try:
                                rs = ast.unparse(s.value)
                            except Exception:
                                return False
                            # if body reads var_name in return, branch did not override
                            if re.search(rf'\b{re.escape(var_name)}\b', rs):
                                return False
                            return True  # returned something else, initial was dead
                        return True
                return False
            def _walk_chain(stmt: ast.If) -> bool:
                if not _branch_overrides(stmt.body):
                    return False
                orelse = stmt.orelse
                while orelse:
                    if len(orelse) == 1 and isinstance(orelse[0], ast.If):
                        nxt = orelse[0]
                        if not _branch_overrides(nxt.body):
                            return False
                        orelse = nxt.orelse
                    else:
                        return _branch_overrides(orelse)
                return False  # no else branch => init might be read on that path
            if not _walk_chain(if_stmt):
                continue
            accept = _accept_reason(lines, first.lineno, rule='dead-local-init')
            _emit(
                rule='dead-local-init',
                variant=f'`{var_name} = <empty>` at top of {func.name} is unconditionally overridden in all if/elif/else branches',
                path=rel,
                line=first.lineno,
                evidence=(lines[first.lineno - 1].strip()[:200]
                          if first.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )

_SUBPROCESS_CALL_RE = re.compile(r'\b(subprocess|sp)\.(run|check_output|check_call|Popen|call)\b')

def check_subprocess_without_memoisation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
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
    PURE_PREFIXES = ('get_', 'resolve_', 'compute_', 'find_', 'check_',
                     'parse_', 'is_', 'has_', 'validate_', 'count_')
    CACHE_DECORATORS = {'cache', 'lru_cache', 'cached', 'functools.cache', 'functools.lru_cache'}
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
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
                try:
                    decorators.add(ast.unparse(target))
                except Exception:
                    pass
            if decorators & CACHE_DECORATORS:
                continue
            # Scan body for subprocess calls
            hit_line = None
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                try:
                    call_src = ast.unparse(inner.func)
                except Exception:
                    continue
                if _SUBPROCESS_CALL_RE.search(call_src):
                    hit_line = inner.lineno
                    break
            if hit_line is None:
                continue
            accept = _accept_reason(lines, hit_line, rule='subprocess-without-memoisation')
            _emit(
                rule='subprocess-without-memoisation',
                variant=f'{node.name} shells out via subprocess without @functools.cache',
                path=rel,
                line=hit_line,
                evidence=(lines[hit_line - 1].strip()[:200]
                          if hit_line <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
