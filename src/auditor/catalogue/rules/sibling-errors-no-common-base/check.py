import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Detect project error classes that sit side-by-side in a `*/errors.py`
    module but have different base classes (one subclasses ProjectError,
    another subclasses stdlib Exception). The mismatch is a smell:
    existing `except ProjectError` catch sites will miss the sibling.

    Signal:
      - A file named `errors.py` defines >= 2 classes whose names end in
        `Error`.
      - At least one of the classes subclasses a project-local error base
        (any name ending in 'Error' that is not stdlib Exception).
      - At least one of the classes subclasses stdlib `Exception`
        (or has no explicit base).
      - The two groups are not related by inheritance within the file.

    A common mistake is defining `SignatureError(Exception)` next to
    `RegistryError(Exception)` without making them share a hierarchy.
    Call sites that catch `RegistryError` never catch `SignatureError`.
    """
    for path in auditor.api.all_py_files(src_root):
        if path.name != 'errors.py':
            continue
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        error_classes: list[tuple[str, int, list[str]]] = []
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith('Error'):
                continue
            base_names = [ast.unparse(base) for base in node.bases]
            error_classes.append((node.name, node.lineno, base_names))
        if len(error_classes) < 2:
            continue
        # Partition into "rooted at stdlib Exception" vs "rooted at a
        # project Error parent"
        rooted_at_stdlib: list[tuple[str, int, list[str]]] = []
        rooted_at_project: list[tuple[str, int, list[str]]] = []
        for name, lineno, bases in error_classes:
            if not bases or any(b.split('.')[-1] == 'Exception' for b in bases):
                rooted_at_stdlib.append((name, lineno, bases))
            elif any(b.split('.')[-1].endswith('Error') for b in bases):
                # If the base is one of the other classes defined in this file,
                # that's a real hierarchy; otherwise it's a new root
                sibling_names = {n for n, _, _ in error_classes}
                if any(b.split('.')[-1] in sibling_names for b in bases):
                    rooted_at_project.append((name, lineno, bases))
                else:
                    rooted_at_stdlib.append((name, lineno, bases))
            else:
                rooted_at_stdlib.append((name, lineno, bases))
        if len(rooted_at_stdlib) < 2:
            continue
        # One finding per errors.py that holds two or more error classes with
        # no shared parent in the file.
        sibling_names = {name for name, _, _ in rooted_at_stdlib}
        if len(sibling_names) < 2:
            continue
        first_name, first_line, _ = rooted_at_stdlib[0]
        accept = auditor.api.accept_reason(lines, first_line, rule='sibling-errors-no-common-base')
        auditor.api.emit(
            rule='sibling-errors-no-common-base',
            variant=f'{len(sibling_names)} Error classes co-defined with no shared parent: {sorted(sibling_names)}',
            path=rel,
            line=first_line,
            evidence=f'classes: {", ".join(sorted(sibling_names))}',
            accepted=bool(accept),
            accepted_reason=accept,
        )
