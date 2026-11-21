"""Checks on naming, ordering and annotation style."""

import ast
import collections
import re
import typing

import auditme.core

if typing.TYPE_CHECKING:
    import pathlib

# Public stdlib API spelt with a leading underscore, so not private access:
# `os._exit` (https://docs.python.org/3/library/os.html#os._exit) and the
# namedtuple methods and attribute, whose underscore only avoids clashing with
# field names (https://docs.python.org/3/library/collections.html#collections.somenamedtuple._make).
STDLIB_PUBLIC_UNDERSCORE_ATTRIBUTES = frozenset({'_asdict', '_fields', '_make', '_replace'})
STDLIB_PUBLIC_UNDERSCORE_QUALIFIED = frozenset({'os._exit'})
ATTRIBUTE_ACCESS = re.compile(r'([a-zA-Z_]\w*)\.(_[a-zA-Z]\w*)')


def is_stdlib_public_access_only(line: str) -> bool:
    """Return True when every `obj._attr` on the line is documented public stdlib API."""  # auditme: accept[leading-underscore-attribute-access] prose about the rule, not a use
    return all(
        attr in STDLIB_PUBLIC_UNDERSCORE_ATTRIBUTES or f'{obj}.{attr}' in STDLIB_PUBLIC_UNDERSCORE_QUALIFIED for obj, attr in ATTRIBUTE_ACCESS.findall(line)
    )


# The line-pattern rules that read code, not prose: a plain string literal
# (a fixture's source, a regex) is data to them. A docstring is still read.
CODE_ONLY_RULES = frozenset(
    {
        'aliased-imports',
        'leading-underscore-attribute-access',
        'leading-underscore-const-lower',
        'leading-underscore-const-upper',
        'leading-underscore-def-class',
        'leading-underscore-self',
        'legacy-typing',
        'relative-import-nonpackage',
    }
)


def docstring_nodes(tree: ast.AST) -> set[int]:
    """Return the `id` of every `ast.Constant` that sits in a docstring position."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) or not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            found.add(id(first.value))
    return found


def mask_string_literals(lines: list[str]) -> list[str]:
    """Return `lines` with the text of every non-docstring string literal blanked.

    Each blanked character becomes a space, so columns are kept. A file that
    does not parse is returned unchanged.
    """
    try:
        tree = ast.parse('\n'.join(lines))
    except SyntaxError:
        return lines
    docstrings = docstring_nodes(tree)
    masked = list(lines)

    def char_column(line: str, byte_column: int) -> int:
        return len(line.encode()[:byte_column].decode(errors='ignore'))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or id(node) in docstrings:
            continue
        end_lineno = node.end_lineno or node.lineno
        end_col = node.end_col_offset or 0
        for lineno in range(node.lineno, end_lineno + 1):
            line = masked[lineno - 1]
            start = char_column(lines[lineno - 1], node.col_offset) if lineno == node.lineno else 0
            stop = char_column(lines[lineno - 1], end_col) if lineno == end_lineno else len(line)
            masked[lineno - 1] = line[:start] + ' ' * (stop - start) + line[stop:]
    return masked


def check_text_patterns(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag source lines that match a text pattern.

    Refinement (2026-11-21): the rules in `CODE_ONLY_RULES` read each line with
    its non-docstring string literals blanked, so fixture source or a regex
    held in a plain string is not read as code. A docstring is still read.
    """
    patterns: list[tuple[str, str, re.Pattern]] = [
        ('wildcard-imports', 'from X import *', re.compile(r'^from [\w.]+ import \*')),
        ('future-annotations', 'from __future__', re.compile(r'^from __future__ ')),
        # Indented as well as top-level: a function-local import, and a recipe
        # in a docstring, which a reader copies and runs as it stands.
        ('aliased-imports', 'import X as Y', re.compile(r'^\s*import [\w.]+ as [\w]+$')),
        # `collections.abc.Set[...]` is the modern ABC, not `typing.Set`: it
        # is the only name here that collections.abc also defines.
        (
            'legacy-typing',
            'Union/Optional/List/Dict/Tuple/Set/FrozenSet/Type',
            re.compile(r'\b(Union|Optional|List|Dict|Tuple|(?<!collections\.abc\.)Set|FrozenSet|Type)\['),
        ),
        # Matched by the regex, then kept only on a line where the AST shows
        # `.format` called on a string literal (see literal_format_lines): a
        # template read at run time can never be an f-string.
        ('legacy-formatting-format', '.format() call on a string literal', re.compile(r'\.format\s*\(')),
        # %-formatting is a pain to disambiguate from strftime. Do it in a
        # dedicated check below (check_percent_formatting).
        ('stdlib-logging', 'stdlib logging import', re.compile(r'^(import logging$|from logging )')),
        ('relative-import-nonpackage', 'relative import outside __init__.py', re.compile(r'^from \.+\w')),
        ('leading-underscore-def-class', 'module-level def/class _x', re.compile(r'^(def|class) _[a-zA-Z]')),
        ('leading-underscore-const-upper', 'module-level _NAME = ...', re.compile(r'^_[A-Z][A-Z0-9_]*\s*[:=]')),
        ('leading-underscore-const-lower', 'module-level _name = ...', re.compile(r'^_[a-z][a-zA-Z0-9_]*\s*[:=]')),
        ('leading-underscore-self', 'self._attr', re.compile(r'\bself\._[a-zA-Z]')),
        ('leading-underscore-attribute-access', 'obj._attr in code or docstring', re.compile(r'[a-zA-Z_][\w]*\._[a-zA-Z]')),
    ]
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        is_init = path.name == '__init__.py'
        format_lines = literal_format_lines(lines)
        code_lines = mask_string_literals(lines)
        for idx, raw in enumerate(lines, 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith('#'):
                continue
            for rule, variant, pat in patterns:
                if rule == 'relative-import-nonpackage' and is_init:
                    continue
                if rule == 'legacy-formatting-format' and idx not in format_lines:
                    continue
                if not pat.search(code_lines[idx - 1] if rule in CODE_ONLY_RULES else raw):
                    continue
                if rule == 'leading-underscore-attribute-access' and is_stdlib_public_access_only(code_lines[idx - 1]):
                    continue
                accept = auditme.core.accept_reason(lines, idx, rule=rule)
                auditme.core.emit(
                    rule=rule,
                    variant=variant,
                    path=rel,
                    line=idx,
                    evidence=stripped[:200],
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


def literal_format_lines(lines: list[str]) -> set[int]:
    """Return the lines on which `.format` is called on a string literal.

    The line is the one holding `.format`, where the regex matches and where
    an accept marker sits. A file that does not parse yields no lines.
    """
    try:
        tree = ast.parse('\n'.join(lines))
    except SyntaxError:
        return set()
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != 'format':
            continue
        receiver = node.func.value
        if isinstance(receiver, ast.Constant) and isinstance(receiver.value, str):
            found.add(node.func.end_lineno or node.lineno)
    return found


STRFTIME_TOKENS = {'%A', '%B', '%H', '%I', '%M', '%S', '%U', '%W', '%X', '%Y', '%Z', '%a', '%b', '%c', '%d', '%f', '%j', '%m', '%p', '%x', '%y', '%z'}


def check_percent_formatting(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `%s`/`%d`/`%r`-style C-printf formatting in Python string literals,
    but do NOT flag strftime directives. Heuristic: if the literal contains
    any strftime token (e.g. `%Y`, `%m`), treat it as a strftime call site."""
    suspect_re = re.compile(r'%[sdrfg]|%\d+[sdrfg]')
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        for idx, raw in enumerate(lines, 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith('#'):
                continue
            # extract string literals
            strings = re.findall(r"""(?:[fF]?r?)?['"](?:[^'"\\]|\\.)*['"]""", raw)
            for s in strings:
                if not suspect_re.search(s):
                    continue
                if any(tok in s for tok in STRFTIME_TOKENS):
                    continue
                accept = auditme.core.accept_reason(lines, idx, rule='legacy-formatting-percent')
                auditme.core.emit(
                    rule='legacy-formatting-percent',
                    variant='%-style C-printf formatting in Python string',
                    path=rel,
                    line=idx,
                    evidence=stripped[:200],
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
                break


def is_fixed_length_tuple(annotation: ast.expr) -> bool:
    """Return True for `tuple[X, Y]` (also under `Final[...]`), not `tuple[X, ...]`.

    A fixed-length tuple's positions carry meaning - a pattern and its
    replacement, an expected order - so sorting its members would change it.
    """
    if isinstance(annotation, ast.Subscript) and ast.unparse(annotation.value) in {'Final', 'typing.Final'}:
        annotation = annotation.slice
    if not isinstance(annotation, ast.Subscript) or ast.unparse(annotation.value) != 'tuple':
        return False
    members = annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
    return not any(isinstance(m, ast.Constant) and m.value is Ellipsis for m in members)


def ruff_dunder_all_key(name: str) -> tuple[int, list[int | str]]:
    """Sort key for ruff's RUF022 order of `__all__`.

    Group 0: more than one character and `name.isupper()` (SCREAMING_SNAKE);
    group 1: first character upper case (CamelCase); group 2: the rest.
    Within a group, natural order: digit runs compare as integers.
    """
    if len(name) > 1 and name.isupper():
        group = 0
    elif name[:1].isupper():
        group = 1
    else:
        group = 2
    natural = [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', name)]
    return group, natural


def check_nonalphabetical_literals(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag module-level string tuple, list, set and `frozenset(...)` literals not in sorted order.

    Only top-level assignments are read, and a literal needs two or more string
    members. A fixed-length tuple annotation (`tuple[str, str]`) is exempt,
    since its positions carry meaning.

    Refinement (2026-11-01): an `__all__` assignment (plain or annotated, single
    target) also passes when its members equal `sorted(members,
    key=ruff_dunder_all_key)`, the order ruff's RUF022 writes. Any other name
    keeps the plain `sorted()` test.
    """
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            if isinstance(node, ast.AnnAssign) and is_fixed_length_tuple(node.annotation):
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
            if auditme.core.is_dunder_all_assignment(node) and actual == sorted(actual, key=ruff_dunder_all_key):
                continue
            accept = auditme.core.accept_reason(lines, node.lineno, rule='non-alphabetical-literal')
            auditme.core.emit(
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
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
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
            accept = auditme.core.accept_reason(lines, node.lineno, rule='non-alphabetical-dict-keys')
            auditme.core.emit(
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
    for path in auditme.core.all_py_files(src_root):
        bare_parametric_annotation_in_file(auditme.core.relpath(path, scope), auditme.core.source_lines(path))


def bare_parametric_annotation_in_file(rel: str, lines: list[str]) -> None:
    try:
        tree = ast.parse('\n'.join(lines))
    except SyntaxError:
        return
    reported: set[int] = set()

    def flag_annotation(ann: ast.AST, ctx: str) -> None:
        # Walk the annotation expression to find any `Name` matching
        # a bare generic. `Subscript(Name(id='dict'), ...)` is fine.
        # `Name(id='dict')` alone is a bare annotation. Handle
        # `dict | None`, `dict | Other`, etc. by descending into BinOp.
        def visit(node: ast.AST) -> None:
            if isinstance(node, ast.Subscript):
                # parametric; if slice is `dict` itself that's fine too, stop
                return
            if isinstance(node, ast.Name) and node.id in auditme.core.BARE_GENERIC_NAMES:
                lineno = getattr(node, 'lineno', None)
                if lineno is None or lineno in reported:
                    return
                reported.add(lineno)
                accept = auditme.core.accept_reason(lines, lineno, rule='bare-parametric-annotation')
                auditme.core.emit(
                    rule='bare-parametric-annotation',
                    variant=f'{ctx} uses bare `{node.id}` without element type',
                    path=rel,
                    line=lineno,
                    evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
            elif isinstance(node, ast.BinOp):
                visit(node.left)
                visit(node.right)
            elif isinstance(node, ast.Tuple):
                for elt in node.elts:
                    visit(elt)

        visit(ann)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in (*node.args.args, *node.args.kwonlyargs, *node.args.posonlyargs):
                if arg.annotation is not None:
                    flag_annotation(arg.annotation, f'{node.name}({arg.arg}:)')
            if node.returns is not None:
                flag_annotation(node.returns, f'{node.name} -> ')
        elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
            tgt = node.target
            ctx = 'annotation'
            if isinstance(tgt, ast.Name):
                ctx = f'{tgt.id}:'
            flag_annotation(node.annotation, ctx)


def check_duplicated_word(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    dup_re = re.compile(r'\b([a-z]{2,})\s+\1\b', re.IGNORECASE)
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
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
            accept = auditme.core.accept_reason(lines, idx, rule='duplicated-word')
            auditme.core.emit(
                rule='duplicated-word',
                variant=f'duplicated word {word!r}',
                path=rel,
                line=idx,
                evidence=s[:200],
                accepted=bool(accept),
                accepted_reason=accept,
            )


PARAMETRIC_NONBUILTIN_GENERICS = {
    'asyncio.Queue',
    'collections.Counter',
    'collections.OrderedDict',
    'collections.defaultdict',
    'collections.deque',
    'concurrent.futures.Executor',
    'concurrent.futures.Future',
    'multiprocessing.Queue',
    'multiprocessing.queues.Queue',
    'queue.Queue',
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
    for path in auditme.core.all_py_files(src_root):
        bare_nonbuiltin_generic_annotation_in_file(auditme.core.relpath(path, scope), auditme.core.source_lines(path))


def bare_nonbuiltin_generic_annotation_in_file(rel: str, lines: list[str]) -> None:
    try:
        tree = ast.parse('\n'.join(lines))
    except SyntaxError:
        return
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

    def flag_bare_annotation(ann: ast.AST) -> None:
        if isinstance(ann, ast.Subscript):
            return  # parametric
        full = None
        if isinstance(ann, ast.Attribute):
            full = ast.unparse(ann)
        elif isinstance(ann, ast.Name):
            full = alias_to_full.get(ann.id, ann.id)
        if full is None:
            return
        if full not in PARAMETRIC_NONBUILTIN_GENERICS:
            return
        lineno = getattr(ann, 'lineno', None)
        if lineno is None or lineno in reported:
            return
        reported.add(lineno)
        accept = auditme.core.accept_reason(lines, lineno, rule='bare-nonbuiltin-generic-annotation')
        auditme.core.emit(
            rule='bare-nonbuiltin-generic-annotation',
            variant=f'bare `{full}` annotation without type parameter',
            path=rel,
            line=lineno,
            evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
            accepted=bool(accept),
            accepted_reason=accept,
        )

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in (*node.args.args, *node.args.kwonlyargs, *node.args.posonlyargs):
                if arg.annotation is not None:
                    flag_bare_annotation(arg.annotation)
            if node.returns is not None:
                flag_bare_annotation(node.returns)
        elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
            flag_bare_annotation(node.annotation)


def collect_name_loads(scope: ast.AST) -> dict[str, list[int]]:
    """Return a map of Name.id -> [lineno, ...] for every Load within
    `scope` (not descending into nested function or class definitions)."""
    result: dict[str, list[int]] = collections.defaultdict(list)

    def walk(n: ast.AST) -> None:
        for sub in ast.iter_child_nodes(n):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                result[sub.id].append(sub.lineno)
            walk(sub)

    walk(scope)
    return result


def leading_underscore_names(target: ast.AST) -> list[tuple[str, int]]:
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
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
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
            loads = collect_name_loads(scope_node)
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
                    for name, lineno in leading_underscore_names(target):
                        reads_after = [ln for ln in loads.get(name, []) if ln > lineno]
                        if not reads_after:
                            continue
                        accept = auditme.core.accept_reason(lines, lineno, rule='underscore-unpack-target-read')
                        auditme.core.emit(
                            rule='underscore-unpack-target-read',
                            variant=f'`{name}` unpacked but read at line {reads_after[0]}',
                            path=rel,
                            line=lineno,
                            evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
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
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.For, ast.AsyncFor)):
                continue
            underscore_targets = leading_underscore_names(node.target)
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
                accept = auditme.core.accept_reason(lines, lineno, rule='underscore-forloop-target-read')
                auditme.core.emit(
                    rule='underscore-forloop-target-read',
                    variant=f'for-loop target `{name}` read inside body',
                    path=rel,
                    line=lineno,
                    evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


def function_nested_definitions(tree: ast.Module) -> list[tuple[ast.AST, str]]:
    """Return every def/class lexically inside a function body, with its kind.

    Descends through nested functions to any depth, so a helper defined
    inside a helper is found. A method (a def whose nearest enclosing
    definition is a class) is NOT returned: that is a different naming
    question, answered by `leading-underscore-self` and by whether the
    project treats a private method as public surface.
    """
    found: list[tuple[ast.AST, str]] = []

    def walk(node: ast.AST, inside_function: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if inside_function:
                    found.append((child, 'def'))
                walk(child, True)
            elif isinstance(child, ast.ClassDef):
                if inside_function:
                    found.append((child, 'class'))
                # A def inside this class is a method, not a nested helper,
                # so the class body is walked with inside_function reset.
                walk(child, False)
            else:
                walk(child, inside_function)

    walk(tree, False)
    return found


def check_leading_underscore_nested_def_class(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a leading-underscore `def`/`class` defined inside a function body.

    Emits under the same rule name as the module-level regex form
    (`leading-underscore-def-class` in check_text_patterns), because it is
    the same defect and a project's existing scoped accept markers should
    answer for both. The regex anchors on `^(def|class) _`, so it sees
    module-level definitions only; this check supplies the nested ones.

    Signal:
      - `ast.FunctionDef` / `ast.AsyncFunctionDef` / `ast.ClassDef` whose
        name starts with a single underscore, lexically inside a function
        body at any depth.

    Refinements (each has a test asserting it does not fire):
      - A **method** does not fire. `walk()` resets `inside_function` when
        it descends into a class body, so `def _m(self)` inside a class
        inside a function is a method, not a nested helper.
      - A **dunder** (`__init__`, `__enter__`) does not fire.
      - A name that **shadows an outer binding** does not fire: a nested
        `_foo` where `_foo` is also defined at module scope is a
        deliberate local override, and renaming it would break the
        shadowing the author wanted.
      - Bare `_` does not fire.

    Raised as a request by an audit (shipped 2026-09-01) that found
    instances which had been invisible across many audit cycles while the
    rule reported almost none.
    """
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        if not isinstance(tree, ast.Module):
            continue

        module_level_names = {node.name for node in ast.iter_child_nodes(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        module_level_names.add(target.id)

        for node, kind in function_nested_definitions(tree):
            name = getattr(node, 'name', '')
            if not name.startswith('_'):
                continue
            if name == '_' or name.startswith('__'):
                continue
            if name in module_level_names:
                continue
            lineno = node.lineno
            accept = auditme.core.accept_reason(lines, lineno, rule='leading-underscore-def-class')
            auditme.core.emit(
                rule='leading-underscore-def-class',
                variant=f'{kind} {name} nested inside a function body',
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


def is_leading_underscore(name: str | None) -> bool:
    """True for `_foo`; false for bare `_`, a dunder or a mangled `__foo`."""
    return bool(name) and name.startswith('_') and name != '_' and not name.startswith('__')


def leading_underscore_bindings(tree: ast.Module) -> list[tuple[str, int, str]]:
    """Return `(name, lineno, kind)` for every leading-underscore name a file binds.

    A binding is any name the author chose for a value: a parameter, a
    `Name` in store context (an assignment, unpack or loop target at any
    position, starred or not, a `with ... as`, a comprehension target, a
    walrus), an `except ... as` name, or a `match` capture.

    A plain-name target of a module-level assignment is left out, because the
    `leading-underscore-const-*` regexes own it and reporting it twice would
    double its count. A `def`/`class` name is left out for the same reason:
    `leading-underscore-def-class` owns it.
    """
    regex_owned: set[int] = set()
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            regex_owned.update(id(target) for target in targets if isinstance(target, ast.Name))

    found: list[tuple[str, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            prefix = 'lambda ' if isinstance(node, ast.Lambda) else ''
            arguments = node.args
            for arg in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs):
                found.append((arg.arg, arg.lineno, f'{prefix}parameter'))
            if arguments.vararg:
                found.append((arguments.vararg.arg, arguments.vararg.lineno, f'{prefix}`*` parameter'))
            if arguments.kwarg:
                found.append((arguments.kwarg.arg, arguments.kwarg.lineno, f'{prefix}`**` parameter'))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and id(node) not in regex_owned:
            found.append((node.id, node.lineno, 'binding'))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            found.append((node.name, node.lineno, '`except ... as` name'))
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            found.append((node.name, node.lineno, '`match` capture'))
        elif isinstance(node, ast.MatchMapping) and node.rest:
            found.append((node.rest, node.lineno, '`match` capture'))
    return [(name, lineno, kind) for name, lineno, kind in found if is_leading_underscore(name)]


def check_leading_underscore_binding(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a leading-underscore parameter or bound name, wherever it occurs.

    The text patterns see a leading underscore only where a regex can anchor
    on it: a module-level `def`/`class`/assignment, and once saw the first or
    second name of an unpack or loop target. That left a starred `*_rest`, a
    third-or-later tuple position, every parameter (including `*_args`,
    `**_kwargs` and lambda arguments) and every function-local assignment
    invisible. This check walks the AST for all of them and replaces the
    five `destructure`/`forloop` regexes, which it subsumes.

    Signal: see `leading_underscore_bindings`.

    Refinements (each has a test asserting it does not fire):
      - Bare `_` does not fire; it is the sanctioned throwaway.
      - A dunder or a name-mangled `__foo` does not fire.
      - A module-level `_NAME = ...` does not fire here: the const regexes
        report it.

    Whether a bound underscore name is also *read* is a separate defect,
    reported by `underscore-unpack-target-read` and
    `underscore-forloop-target-read`.

    Raised as a request by an audit (shipped 2026-10-05) whose S2 found
    many such sites across its test modules.
    """
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for name, lineno, kind in sorted(leading_underscore_bindings(tree), key=lambda item: (item[1], item[0])):
            accept = auditme.core.accept_reason(lines, lineno, rule='leading-underscore-binding')
            auditme.core.emit(
                rule='leading-underscore-binding',
                variant=f'{kind} `{name}`',
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


# Every `typing` alias PEP 585 deprecated, and where its replacement lives.
# `List`/`Dict`/`Tuple`/`Set`/`FrozenSet`/`Type` are absent: their replacement
# is a builtin, and `legacy-typing` already reports them.
TYPING_DEPRECATED_ALIASES = {
    'AbstractSet': 'collections.abc.Set',
    'AsyncContextManager': 'contextlib.AbstractAsyncContextManager',
    'AsyncGenerator': 'collections.abc.AsyncGenerator',
    'AsyncIterable': 'collections.abc.AsyncIterable',
    'AsyncIterator': 'collections.abc.AsyncIterator',
    'Awaitable': 'collections.abc.Awaitable',
    'Callable': 'collections.abc.Callable',
    'ChainMap': 'collections.ChainMap',
    'Collection': 'collections.abc.Collection',
    'Container': 'collections.abc.Container',
    'ContextManager': 'contextlib.AbstractContextManager',
    'Coroutine': 'collections.abc.Coroutine',
    'Counter': 'collections.Counter',
    'DefaultDict': 'collections.defaultdict',
    'Deque': 'collections.deque',
    'Generator': 'collections.abc.Generator',
    'Hashable': 'collections.abc.Hashable',
    'ItemsView': 'collections.abc.ItemsView',
    'Iterable': 'collections.abc.Iterable',
    'Iterator': 'collections.abc.Iterator',
    'KeysView': 'collections.abc.KeysView',
    'Mapping': 'collections.abc.Mapping',
    'MappingView': 'collections.abc.MappingView',
    'Match': 're.Match',
    'MutableMapping': 'collections.abc.MutableMapping',
    'MutableSequence': 'collections.abc.MutableSequence',
    'MutableSet': 'collections.abc.MutableSet',
    'OrderedDict': 'collections.OrderedDict',
    'Pattern': 're.Pattern',
    'Reversible': 'collections.abc.Reversible',
    'Sequence': 'collections.abc.Sequence',
    'Sized': 'collections.abc.Sized',
    'ValuesView': 'collections.abc.ValuesView',
}


def check_typing_deprecated_alias(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `typing.Sequence`, `typing.Iterator` and every other `typing` alias
    PEP 585 deprecated in favour of the standard-library class itself.

    The coding standard prefers the standard generics to their `typing`
    equivalents. `legacy-typing` reads that for the aliases of builtins -
    `List[`, `Dict[` and the rest - and saw nothing else, so an audit  # auditme: accept[legacy-typing] prose about the rule, not a use
    found `typing.Sequence` and `typing.Iterator` by hand under S4.

    Signal, on the AST so a string or a comment never fires:
      - `typing.<alias>` anywhere, subscripted or not: `isinstance(x,
        typing.Mapping)` names the same deprecated alias an annotation does.
      - `from typing import <alias>`, once per alias at the import line. The
        bare uses that follow are the same decision, made once.

    The variant names the replacement, so the fix is in the hit.

    Not this rule's: the builtin aliases (`legacy-typing`), and a `typing`
    name with no standard-library class to move to - `typing.Any`,
    `typing.Protocol`, `typing.TypeVar`.
    """
    rule = 'typing-deprecated-alias'
    for path in auditme.core.all_py_files(src_root):
        rel = auditme.core.relpath(path, scope)
        lines = auditme.core.source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        found: set[tuple[int, str]] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'typing':
                if node.attr in TYPING_DEPRECATED_ALIASES:
                    found.add((node.lineno, node.attr))
            elif isinstance(node, ast.ImportFrom) and node.module == 'typing' and node.level == 0:
                found.update((node.lineno, alias.name) for alias in node.names if alias.name in TYPING_DEPRECATED_ALIASES)
        for lineno, name in sorted(found):
            accept = auditme.core.accept_reason(lines, lineno, rule=rule)
            auditme.core.emit(
                rule=rule,
                variant=f'typing.{name} -> {TYPING_DEPRECATED_ALIASES[name]}',
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
