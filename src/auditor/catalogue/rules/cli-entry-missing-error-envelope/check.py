import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag CLI entry-point functions (top-level functions in `cli/*.py`
    whose name starts with `run_`) that have no top-level try/except.

    The rule: if at least one sibling CLI entry in the project does have
    a top-level try/except catching a project error class, flag every
    CLI entry that does not. CLI entries are the error envelope for
    user-facing errors; an unenveloped entry will surface untranslated
    third-party exceptions.
    """
    cli_dir = src_root / 'cli'
    if not cli_dir.is_dir():
        return
    # First pass: enumerate all CLI run_* entries and whether they wrap
    # something in a top-level try/except.
    entries: list[tuple[str, int, str, bool]] = []  # (path, lineno, fname, has_outer_try)
    for path in sorted(cli_dir.rglob('*.py')):
        if path.name == '__init__.py':
            continue
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith('run_'):
                continue
            # Only consider true CLI dispatch entries. Heuristics to
            # exclude helper functions in cli/*.py:
            #   - return annotation is `int` (CLI commands return an
            #     exit code)
            #   - OR has a parameter annotated with a name ending in
            #     `.App` / `.Cmd` / any cappa dispatcher root (the
            #     dispatcher-aware second argument)
            returns_int = False
            if node.returns is not None:
                if ast.unparse(node.returns).strip() == 'int':
                    returns_int = True
            # params whose annotation string contains a capitalised cappa
            # command class (the `parent: 'pkg.cli.app.App'` style)
            has_cappa_param = False
            for arg in node.args.args:
                if arg.annotation is None:
                    continue
                ann_src = ast.unparse(arg.annotation)
                if re.search(r"\.[A-Z]\w+['\"]?$", ann_src.strip('\'"')):
                    has_cappa_param = True
                    break
            if not (returns_int or has_cappa_param):
                continue
            # Is there any Try in the function body? (Any depth.) The
            # rule is: CLI entry must have at least one try/except
            # somewhere to be considered "enveloped".
            has_try = any(isinstance(sub, ast.Try) for sub in ast.walk(node))
            entries.append((rel, node.lineno, node.name, has_try))
    if not entries:
        return
    # If at least one entry has a try/except, any entry without one is flagged.
    any_has_try = any(has_try for (_, _, _, has_try) in entries)
    if not any_has_try:
        return
    for rel, lineno, fname, has_try in entries:
        if has_try:
            continue
        full = scope / rel
        lines = auditor.api.source_lines(full)
        accept = auditor.api.accept_reason(lines, lineno, rule='cli-entry-missing-error-envelope')
        auditor.api.emit(
            rule='cli-entry-missing-error-envelope',
            variant=f'{fname} has no top-level try/except',
            path=rel,
            line=lineno,
            evidence=f'def {fname}(...): (no try/except; siblings do wrap)',
            accepted=bool(accept),
            accepted_reason=accept,
        )
