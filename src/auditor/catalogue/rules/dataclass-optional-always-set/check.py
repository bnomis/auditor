import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
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
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            # Is it a dataclass? Check decorators
            is_dataclass = False
            for dec in cls.decorator_list:
                dec_src = ast.unparse(dec)
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
                ann_src = ast.unparse(item.annotation)
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
                (m for m in cls.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name == '__post_init__'),
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
                    if not (isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name) and tgt.value.id == 'self'):
                        continue
                    if tgt.attr not in nullable_fields:
                        continue
                    # Check RHS is not None
                    if isinstance(stmt.value, ast.Constant) and stmt.value.value is None:
                        continue
                    field_lineno = nullable_fields[tgt.attr]
                    accept = auditor.api.accept_reason(lines, field_lineno, rule='dataclass-optional-always-set')
                    auditor.api.emit(
                        rule='dataclass-optional-always-set',
                        variant=f'{cls.name}.{tgt.attr} typed `X | None` but __post_init__ always assigns non-None',
                        path=rel,
                        line=field_lineno,
                        evidence=(lines[field_lineno - 1].strip()[:200] if field_lineno <= len(lines) else ''),
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )
