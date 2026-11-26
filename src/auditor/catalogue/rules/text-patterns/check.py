import ast
import re
import typing

import auditor.api

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


def mask_string_literals(lines: list[str], tree: ast.Module | None) -> list[str]:
    """Return `lines` with the text of every non-docstring string literal blanked.

    Each blanked character becomes a space, so columns are kept. A file that
    does not parse (`tree` is None) is returned unchanged.
    """
    if tree is None:
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


def literal_format_lines(tree: ast.Module | None) -> set[int]:
    """Return the lines on which `.format` is called on a string literal.

    The line is the one holding `.format`, where the regex matches and where
    an accept marker sits. A file that does not parse (`tree` is None) yields no lines.
    """
    if tree is None:
        return set()
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != 'format':
            continue
        receiver = node.func.value
        if isinstance(receiver, ast.Constant) and isinstance(receiver.value, str):
            found.add(node.func.end_lineno or node.lineno)
    return found


def check_line_patterns(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag source lines that match a text pattern."""
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
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        is_init = path.name == '__init__.py'
        tree = auditor.api.read_and_parse(path)
        format_lines = literal_format_lines(tree)
        code_lines = mask_string_literals(lines, tree)
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
                accept = auditor.api.accept_reason(lines, idx, rule=rule)
                auditor.api.emit(
                    rule=rule,
                    variant=variant,
                    path=rel,
                    line=idx,
                    evidence=stripped[:200],
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


def check_nested_def_class(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a leading-underscore `def`/`class` defined inside a function body.

    Emits under the same rule name as the module-level regex form
    (`leading-underscore-def-class` in `check_line_patterns`), because it is
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
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
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
            accept = auditor.api.accept_reason(lines, lineno, rule='leading-underscore-def-class')
            auditor.api.emit(
                rule='leading-underscore-def-class',
                variant=f'{kind} {name} nested inside a function body',
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag source lines that match a text pattern, and a leading-underscore def or class nested in a function."""
    check_line_patterns(scope, src_root)
    check_nested_def_class(scope, src_root)
