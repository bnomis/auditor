"""Checks on naming, ordering and annotation style."""

from __future__ import annotations
import ast
import pathlib
import re
from collections import defaultdict

from auditme.core import _accept_reason, _all_py_files, _emit, _relpath, _source_lines


def check_text_patterns(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    patterns: list[tuple[str, str, re.Pattern]] = [
        ('wildcard-imports', 'from X import *', re.compile(r'^from [\w.]+ import \*')),
        ('future-annotations', 'from __future__', re.compile(r'^from __future__ ')),
        ('aliased-imports', 'import X as Y', re.compile(r'^import [\w.]+ as [\w]+$')),
        ('legacy-typing', 'Union/Optional/List/Dict/Tuple/Set/FrozenSet/Type', re.compile(r'\b(Union|Optional|List|Dict|Tuple|Set|FrozenSet|Type)\[')),
        ('legacy-formatting-format', '.format() call', re.compile(r'\.format\s*\(')),
        # %-formatting is a pain to disambiguate from strftime. Do it in a
        # dedicated check below (check_percent_formatting).
        ('stdlib-logging', 'stdlib logging import', re.compile(r'^(import logging$|from logging )')),
        ('relative-import-nonpackage', 'relative import outside __init__.py', re.compile(r'^from \.+\w')),
        ('leading-underscore-def-class', 'module-level def/class _x', re.compile(r'^(def|class) _[a-zA-Z]')),
        ('leading-underscore-const-upper', 'module-level _NAME = ...', re.compile(r'^_[A-Z][A-Z0-9_]*\s*[:=]')),
        ('leading-underscore-const-lower', 'module-level _name = ...', re.compile(r'^_[a-z][a-zA-Z0-9_]*\s*[:=]')),
        ('leading-underscore-self', 'self._attr', re.compile(r'\bself\._[a-zA-Z]')),
        ('leading-underscore-destructure-first', 'destructured `_x, y = ...`', re.compile(r'^\s+_[a-z][a-zA-Z0-9_]*\s*,\s*[a-zA-Z]')),
        ('leading-underscore-destructure-second', 'destructured `x, _y = ...`', re.compile(r'^\s+[a-zA-Z][a-zA-Z0-9_]*\s*,\s*_[a-zA-Z][a-zA-Z0-9_]*\s*=')),
        ('leading-underscore-forloop-single', 'for _x in', re.compile(r'\bfor\s+_[a-z][a-zA-Z0-9_]+\s+in\b')),
        ('leading-underscore-forloop-first', 'for _x, y in', re.compile(r'\bfor\s+_[a-z][a-zA-Z0-9_]*\s*,\s*[a-zA-Z_][a-zA-Z0-9_]*\s+in\b')),
        ('leading-underscore-forloop-second', 'for x, _y in', re.compile(r'\bfor\s+[a-zA-Z][a-zA-Z0-9_]*\s*,\s*_[a-zA-Z][a-zA-Z0-9_]*\s+in\b')),
        ('leading-underscore-attribute-access', 'obj._attr in code or docstring', re.compile(r'[a-zA-Z_][\w]*\._[a-zA-Z]')),
    ]
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        is_init = path.name == '__init__.py'
        for idx, raw in enumerate(lines, 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith('#'):
                continue
            for rule, variant, pat in patterns:
                if rule == 'relative-import-nonpackage' and is_init:
                    continue
                if not pat.search(raw):
                    continue
                accept = _accept_reason(lines, idx, rule=rule)
                _emit(
                    rule=rule,
                    variant=variant,
                    path=rel,
                    line=idx,
                    evidence=stripped[:200],
                    accepted=bool(accept),
                    accepted_reason=accept,
                )

_STRFTIME_TOKENS = {'%Y', '%y', '%m', '%d', '%H', '%I', '%M', '%S', '%p', '%A', '%a', '%B', '%b', '%j', '%U', '%W', '%c', '%x', '%X', '%Z', '%z', '%f'}

def check_percent_formatting(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `%s`/`%d`/`%r`-style C-printf formatting in Python string literals,
    but do NOT flag strftime directives. Heuristic: if the literal contains
    any strftime token (e.g. `%Y`, `%m`), treat it as a strftime call site."""
    suspect_re = re.compile(r'%[sdrfg]|%\d+[sdrfg]')
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        for idx, raw in enumerate(lines, 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith('#'):
                continue
            # extract string literals
            strings = re.findall(r"""(?:[fF]?r?)?['"](?:[^'"\\]|\\.)*['"]""", raw)
            for s in strings:
                if not suspect_re.search(s):
                    continue
                if any(tok in s for tok in _STRFTIME_TOKENS):
                    continue
                accept = _accept_reason(lines, idx, rule='legacy-formatting-percent')
                _emit(
                    rule='legacy-formatting-percent',
                    variant='%-style C-printf formatting in Python string',
                    path=rel,
                    line=idx,
                    evidence=stripped[:200],
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
                break

def check_nonalphabetical_literals(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if value is None:
                continue
            members = None
            if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
                members = value.elts
            elif (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == 'frozenset'
                and value.args
                and isinstance(value.args[0], (ast.Set, ast.List, ast.Tuple))
            ):
                members = value.args[0].elts
            if not members or len(members) < 2:
                continue
            if not all(isinstance(m, ast.Constant) and isinstance(m.value, str) for m in members):
                continue
            actual = [m.value for m in members]
            if actual == sorted(actual):
                continue
            accept = _accept_reason(lines, node.lineno, rule='non-alphabetical-literal')
            _emit(
                rule='non-alphabetical-literal',
                variant='string members not alphabetically sorted',
                path=rel,
                line=node.lineno,
                evidence=f'{actual!r}',
                accepted=bool(accept),
                accepted_reason=accept,
            )

def check_non_alphabetical_dict_keys(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag module-level dict assignments whose keys are all string
    literals and NOT in alphabetical order. Companion to
    `check_nonalphabetical_literals` which covers list/tuple/set/frozenset.

    The project-wide ordering rule treats enum-like collections as a
    shared convention: a dict mapping a closed domain (metric-name to
    scorer, error-code to message, etc.) should be alphabetised unless
    the order carries semantic meaning.
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if not isinstance(value, ast.Dict):
                continue
            keys = value.keys
            if not keys or len(keys) < 2:
                continue
            if not all(isinstance(k, ast.Constant) and isinstance(k.value, str) for k in keys):
                continue
            actual = [k.value for k in keys]
            if actual == sorted(actual):
                continue
            accept = _accept_reason(lines, node.lineno, rule='non-alphabetical-dict-keys')
            _emit(
                rule='non-alphabetical-dict-keys',
                variant='dict with string keys not alphabetically sorted',
                path=rel,
                line=node.lineno,
                evidence=f'keys: {actual!r}',
                accepted=bool(accept),
                accepted_reason=accept,
            )

def check_bare_parametric_annotation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag annotations that use `dict`, `list`, `tuple`, `set`, or
    `frozenset` without a parametric type (`dict[str, int]`, `list[X]`,
    etc.). Bare `dict` / `list` loses type information that pyright /
    mypy / readers need.

    Applies to:
      - function parameter annotations
      - function return annotations
      - class / module-level AnnAssign targets
      - local AnnAssign targets inside function bodies
    """
    BARE_GENERICS = {'dict', 'list', 'tuple', 'set', 'frozenset'}
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        reported: set[int] = set()

        def _flag_annotation(ann: ast.AST, ctx: str) -> None:
            # Walk the annotation expression to find any `Name` matching
            # a bare generic. `Subscript(Name(id='dict'), ...)` is fine.
            # `Name(id='dict')` alone is a bare annotation. Handle
            # `dict | None`, `dict | Other`, etc. by descending into BinOp.
            def _visit(node: ast.AST) -> None:
                if isinstance(node, ast.Subscript):
                    # parametric; if slice is `dict` itself that's fine too, stop
                    return
                if isinstance(node, ast.Name) and node.id in BARE_GENERICS:
                    lineno = getattr(node, 'lineno', None)
                    if lineno is None or lineno in reported:
                        return
                    reported.add(lineno)
                    accept = _accept_reason(lines, lineno, rule='bare-parametric-annotation')
                    _emit(
                        rule='bare-parametric-annotation',
                        variant=f'{ctx} uses bare `{node.id}` without element type',
                        path=rel,
                        line=lineno,
                        evidence=(lines[lineno - 1].strip()[:200]
                                  if 1 <= lineno <= len(lines) else ''),
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )
                elif isinstance(node, ast.BinOp):
                    _visit(node.left)
                    _visit(node.right)
                elif isinstance(node, ast.Tuple):
                    for elt in node.elts:
                        _visit(elt)
            _visit(ann)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in (*node.args.args, *node.args.kwonlyargs, *node.args.posonlyargs):
                    if arg.annotation is not None:
                        _flag_annotation(arg.annotation, f'{node.name}({arg.arg}:)')
                if node.returns is not None:
                    _flag_annotation(node.returns, f'{node.name} -> ')
            elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
                tgt = node.target
                ctx = 'annotation'
                if isinstance(tgt, ast.Name):
                    ctx = f'{tgt.id}:'
                _flag_annotation(node.annotation, ctx)

def check_duplicated_word(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    dup_re = re.compile(r'\b([a-z]{2,})\s+\1\b', re.IGNORECASE)
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        for idx, raw in enumerate(lines, 1):
            m = dup_re.search(raw)
            if not m:
                continue
            word = m.group(1).lower()
            if word in {'that', 'had', 'has', 'as', 'in', 'is'}:
                continue
            s = raw.strip()
            if not (s.startswith('#') or '"""' in raw or "'''" in raw or '"' in raw or "'" in raw):
                continue
            accept = _accept_reason(lines, idx, rule='duplicated-word')
            _emit(
                rule='duplicated-word',
                variant=f'duplicated word {word!r}',
                path=rel,
                line=idx,
                evidence=s[:200],
                accepted=bool(accept),
                accepted_reason=accept,
            )

_PARAMETRIC_NONBUILTIN_GENERICS = {
    'multiprocessing.Queue',
    'multiprocessing.queues.Queue',
    'queue.Queue',
    'asyncio.Queue',
    'concurrent.futures.Future',
    'concurrent.futures.Executor',
    'collections.deque',
    'collections.OrderedDict',
    'collections.defaultdict',
    'collections.Counter',
    'weakref.WeakKeyDictionary',
    'weakref.WeakValueDictionary',
}

def check_bare_nonbuiltin_generic_annotation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag annotations that reference a parameterisable non-builtin
    class without its type parameter.

    Signal:
      - `ast.AnnAssign.annotation` or a parameter annotation is an
        `ast.Attribute` (e.g. `multiprocessing.Queue`) OR an `ast.Name`
        whose resolved full name is in the parametric-non-builtin set.
      - The annotation is NOT wrapped in `ast.Subscript` (which would
        indicate parametric use like `multiprocessing.Queue[int]`).

    Builtin generics (`dict`/`list`/`tuple`/`set`/`frozenset`) are
    handled by `check_bare_parametric_annotation` and skipped here.
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        # Build import alias map so `Queue` resolves to `multiprocessing.Queue`
        # when imported as `from multiprocessing import Queue`.
        alias_to_full: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    alias_to_full[alias.asname or alias.name] = f'{node.module}.{alias.name}'
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    alias_to_full[alias.asname or alias.name.split('.')[0]] = alias.name

        reported: set[int] = set()

        def _flag(ann: ast.AST) -> None:
            if isinstance(ann, ast.Subscript):
                return  # parametric
            full = None
            if isinstance(ann, ast.Attribute):
                try:
                    full = ast.unparse(ann)
                except Exception:
                    return
            elif isinstance(ann, ast.Name):
                full = alias_to_full.get(ann.id, ann.id)
            if full is None:
                return
            if full not in _PARAMETRIC_NONBUILTIN_GENERICS:
                return
            lineno = getattr(ann, 'lineno', None)
            if lineno is None or lineno in reported:
                return
            reported.add(lineno)
            accept = _accept_reason(lines, lineno, rule='bare-nonbuiltin-generic-annotation')
            _emit(
                rule='bare-nonbuiltin-generic-annotation',
                variant=f'bare `{full}` annotation without type parameter',
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200]
                          if 1 <= lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in (*node.args.args, *node.args.kwonlyargs, *node.args.posonlyargs):
                    if arg.annotation is not None:
                        _flag(arg.annotation)
                if node.returns is not None:
                    _flag(node.returns)
            elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
                _flag(node.annotation)

def _collect_name_loads(scope: ast.AST) -> dict[str, list[int]]:
    """Return a map of Name.id -> [lineno, ...] for every Load within
    `scope` (not descending into nested function or class definitions)."""
    result: dict[str, list[int]] = defaultdict(list)

    def walk(n: ast.AST) -> None:
        for sub in ast.iter_child_nodes(n):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                result[sub.id].append(sub.lineno)
            walk(sub)
    walk(scope)
    return result

def _leading_underscore_names(target: ast.AST) -> list[tuple[str, int]]:
    """Return `(name, lineno)` for every `_foo` Store-name inside a
    tuple-unpack target (or a bare `_foo`). Skips bare `_`."""
    out: list[tuple[str, int]] = []

    def walk(n: ast.AST) -> None:
        if isinstance(n, ast.Name):
            if n.id.startswith('_') and n.id != '_' and not n.id.startswith('__'):
                out.append((n.id, n.lineno))
        elif isinstance(n, (ast.Tuple, ast.List)):
            for elt in n.elts:
                walk(elt)
        elif isinstance(n, ast.Starred):
            walk(n.value)
    walk(target)
    return out

def check_underscore_unpack_target_read(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag tuple-unpack assignments with a leading-underscore target
    whose name is subsequently READ in the enclosing scope. A leading
    underscore conventionally marks an unused binding; reading it is
    misleading.

    Signal:
      - `ast.Assign` or `ast.AnnAssign` where the target is a Tuple/List
        containing `Name(id='_foo', ctx=Store)` with a leading underscore
        (not bare `_`, not dunder).
      - `_foo` appears as `ast.Name(ctx=Load)` somewhere later in the
        same function (or module scope if at module level).
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        # Enclosing scopes: module-level plus each function
        scopes: list[ast.AST] = [tree]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.append(node)
        for scope_node in scopes:
            loads = _collect_name_loads(scope_node)
            for node in ast.iter_child_nodes(scope_node) if scope_node is tree else ast.walk(scope_node):
                if scope_node is not tree and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)) and node is not scope_node:
                    continue
                targets: list[ast.AST] = []
                if isinstance(node, ast.Assign):
                    targets = list(node.targets)
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                else:
                    continue
                for target in targets:
                    if not isinstance(target, (ast.Tuple, ast.List)):
                        continue
                    for name, lineno in _leading_underscore_names(target):
                        reads_after = [ln for ln in loads.get(name, []) if ln > lineno]
                        if not reads_after:
                            continue
                        accept = _accept_reason(lines, lineno, rule='underscore-unpack-target-read')
                        _emit(
                            rule='underscore-unpack-target-read',
                            variant=f'`{name}` unpacked but read at line {reads_after[0]}',
                            path=rel,
                            line=lineno,
                            evidence=(lines[lineno - 1].strip()[:200]
                                      if 1 <= lineno <= len(lines) else ''),
                            accepted=bool(accept),
                            accepted_reason=accept,
                        )

def check_underscore_forloop_target_read(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `for _x in ...:` (or tuple form `for _x, y in ...:`) where
    `_x` is subsequently READ inside the loop body.

    Signal:
      - `ast.For` / `ast.AsyncFor` with a target that contains a leading-
        underscore `Name(ctx=Store)` (not bare `_`, not dunder).
      - The same name appears as `ast.Name(ctx=Load)` within the loop's
        body statements (not nested function defs).
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.For, ast.AsyncFor)):
                continue
            underscore_targets = _leading_underscore_names(node.target)
            if not underscore_targets:
                continue
            # Collect loads inside loop body
            body_loads: set[str] = set()
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                        continue
                    if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                        body_loads.add(sub.id)
            for name, lineno in underscore_targets:
                if name not in body_loads:
                    continue
                accept = _accept_reason(lines, lineno, rule='underscore-forloop-target-read')
                _emit(
                    rule='underscore-forloop-target-read',
                    variant=f'for-loop target `{name}` read inside body',
                    path=rel,
                    line=lineno,
                    evidence=(lines[lineno - 1].strip()[:200]
                              if 1 <= lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
