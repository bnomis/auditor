import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
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
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            init = next(
                (m for m in cls.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name == '__init__'),
                None,
            )
            if init is None:
                continue
            # Collect args typed as dict/list at top level of annotation
            mutable_args: set[str] = set()
            for arg in init.args.args:
                if arg.annotation is None:
                    continue
                ann_src = ast.unparse(arg.annotation)
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
                    if not (isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name) and tgt.value.id == 'self'):
                        continue
                    if not isinstance(stmt.value, ast.Name):
                        continue
                    if stmt.value.id not in mutable_args:
                        continue
                    if tgt.attr != stmt.value.id:
                        continue
                    accept = auditor.api.accept_reason(lines, stmt.lineno, rule='mutable-store-without-copy')
                    auditor.api.emit(
                        rule='mutable-store-without-copy',
                        variant=f'{cls.name}.__init__ stores dict/list parameter `{stmt.value.id}` by reference',
                        path=rel,
                        line=stmt.lineno,
                        evidence=(lines[stmt.lineno - 1].strip()[:200] if stmt.lineno <= len(lines) else ''),
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )
