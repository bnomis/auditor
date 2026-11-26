import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


# A prohibition word, a short gap, then the keyword quoted or backticked:
# "no `as` imports either", 'Do NOT use "as" imports', "never use `as` imports".
# Requiring the quoting is what keeps ordinary prose - "no imports as such" -
# from reading as a declared rule.
AS_IMPORT_BAN_RE = re.compile(
    r"""(?:\bno\b|\bnever\b|\bavoid\b|\bdo\s+not\b|\bdon'?t\b)
        [^.\n]{0,24}?
        [`"']as[`"']
        \s+imports?\b""",
    re.IGNORECASE | re.VERBOSE,
)


def project_bans_as_imports(scope: pathlib.Path) -> bool:
    """`scan_bans_as_imports`, worked out once per run."""
    return typing.cast('bool', auditor.api.cached_per_run('project_bans_as_imports', scope, scan_bans_as_imports))


def scan_bans_as_imports(scope: pathlib.Path) -> bool:
    """True when the project's own AGENTS.md declares `import X as Y` banned.

    The check is gated because the rule is a project standard, not a universal
    one: `import numpy as np` is idiomatic nearly everywhere, and a checker
    that flagged it unasked would bury every other hit. Only AGENTS.md is read,
    the way the layering and lazy-import tables are - a rule the project states
    somewhere else is a rule the project has not stated here.
    """
    agents = scope / 'AGENTS.md'
    if not agents.is_file():
        return False
    text = auditor.api.read_source(agents)
    return text is not None and bool(AS_IMPORT_BAN_RE.search(text))


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `import X as Y` / `from M import X as Y` where the project bans it."""
    if not project_bans_as_imports(scope):
        return
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        reexport_linenos: set[int] = set()
        if path.name == '__init__.py':
            reexport_linenos = {n.lineno for n in tree.body if isinstance(n, ast.ImportFrom)}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if node.lineno in reexport_linenos:
                continue
            for alias in node.names:
                if not alias.asname:
                    continue
                if isinstance(node, ast.Import):
                    variant = 'import X as Y'
                    statement = f'import {alias.name} as {alias.asname}'
                else:
                    variant = 'from M import X as Y'
                    statement = f'from {"." * node.level}{node.module or ""} import {alias.name} as {alias.asname}'
                accept = auditor.api.accept_reason(lines, node.lineno, rule='as-import')
                auditor.api.emit(
                    rule='as-import',
                    variant=variant,
                    path=rel,
                    line=node.lineno,
                    evidence=statement,
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
