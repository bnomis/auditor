import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag methods (other than __init__ / __post_init__ / setters / setX-named
    methods / clear / reset / update / mutate / merge / replace / apply / patch /
    override) that reassign `self.<attr>` where `<attr>`
    was set from a constructor argument of the same name in __init__.

    The pattern is: a method whose name signals a non-mutating operation
    (a stage, a compute, a build, a load, a predict, a tokenize, a train,
    an evaluate) silently mutates state the caller passed in. Downstream
    stages consume the mutation through `self.<attr>` but a Python-API
    caller holding a reference to the original sees their view drift.
    """
    MUTATING_METHOD_NAMES = {
        'set',
        'reset',
        'clear',
        'update',
        'mutate',
        'merge',
        'replace',
        'apply',
        'patch',
        'override',
    }
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            # Find attrs assigned in __init__ from a same-named argument
            owned_attrs: set[str] = set()
            init = next(
                (m for m in cls.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name == '__init__'),
                None,
            )
            if init is not None:
                arg_names = {a.arg for a in init.args.args}
                for inner in ast.walk(init):
                    if not isinstance(inner, ast.Assign):
                        continue
                    for tgt in inner.targets:
                        if (
                            isinstance(tgt, ast.Attribute)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == 'self'
                            and isinstance(inner.value, ast.Name)
                            and inner.value.id == tgt.attr
                            and inner.value.id in arg_names
                        ):
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
                        if not (isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name) and tgt.value.id == 'self'):
                            continue
                        if tgt.attr not in owned_attrs:
                            continue
                        accept = auditor.api.accept_reason(lines, inner.lineno, rule='silent-self-mutation')
                        auditor.api.emit(
                            rule='silent-self-mutation',
                            variant=f'{cls.name}.{member.name} reassigns self.{tgt.attr}',
                            path=rel,
                            line=inner.lineno,
                            evidence=(lines[inner.lineno - 1].strip()[:200] if inner.lineno <= len(lines) else ''),
                            accepted=bool(accept),
                            accepted_reason=accept,
                        )
