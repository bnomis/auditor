import ast
import collections
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a module-level `re.compile` constant whose name is also assigned in another file."""
    # name -> list of (path, lineno, literal)
    sites: dict[str, list[tuple[pathlib.Path, int, str]]] = collections.defaultdict(list)
    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            target_name: str | None = None
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    target_name = node.targets[0].id
                    value = node.value
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    target_name = node.target.id
                    value = node.value
            if target_name is None or value is None:
                continue
            if not isinstance(value, ast.Call):
                continue
            is_re_compile = False
            if isinstance(value.func, ast.Attribute) and value.func.attr == 'compile':
                if isinstance(value.func.value, ast.Name) and value.func.value.id == 're':
                    is_re_compile = True
            if not is_re_compile:
                continue
            if not value.args:
                continue
            arg0 = value.args[0]
            if not (isinstance(arg0, ast.Constant) and isinstance(arg0.value, str)):
                continue
            sites[target_name].append((path, node.lineno, arg0.value))

    for name, locations in sites.items():
        distinct_paths = {p for p, _, _ in locations}
        if len(distinct_paths) < 2:
            continue
        for path, lineno, _ in locations:
            rel = auditor.api.relpath(path, scope)
            lines = auditor.api.source_lines(path)
            accept = auditor.api.accept_reason(lines, lineno, rule='recompile-duplication')
            other_paths = sorted({auditor.api.relpath(p, scope) for p, _, _ in locations if p != path})
            auditor.api.emit(
                related=other_paths,
                rule='recompile-duplication',
                variant=(f'constant `{name} = re.compile(...)` also defined in {other_paths!r}; canonicalise to one home'),
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
