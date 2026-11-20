"""Architecture questions: the listers for A11, A19, A1 and A17 and their shared helpers.

`capture_hits` runs sweep rules and returns where they hit, so a lister can
drop a site the sweep already reports. The other helpers parse every audited
file, number the sites in a qualname and walk a tree with qualified names.
"""

import ast
import collections
import collections.abc
import contextlib
import dataclasses
import io
import json
import pathlib

import auditme.core
from auditme.phaseb.errors import PhaseBError

Check = collections.abc.Callable[[pathlib.Path, pathlib.Path], None]

MODULE_QUALNAME = '<module>'


def capture_hits(scope: pathlib.Path, checks: collections.abc.Sequence[Check]) -> set[tuple[str, str, int]]:
    """Run checks over every audit root and return each hit as (rule, path, line).

    Saves and restores `_EMITTED` and captures stdout. Accepted hits are included.

    Raises:
        PhaseBError: a check raised; the message names the check.
    """
    saved = set(auditme.core._EMITTED)
    hits: set[tuple[str, str, int]] = set()
    try:
        for check in checks:
            auditme.core._EMITTED.clear()
            buffer = io.StringIO()
            try:
                with contextlib.redirect_stdout(buffer):
                    for src_root in auditme.core._audit_roots(scope):
                        check(scope, src_root)
            except Exception as error:  # a check's failure must stop the lister, whatever its type
                raise PhaseBError(f'check {getattr(check, "__name__", check)!r} failed: {error}') from error
            for line in buffer.getvalue().splitlines():
                record = json.loads(line)
                hits.add((record['rule'], record['path'], record['line']))
    finally:
        auditme.core._EMITTED.clear()
        auditme.core._EMITTED.update(saved)
    return hits


@dataclasses.dataclass(frozen=True)
class ParsedSource:
    """An audited file parsed once, with its repo-relative path and dotted module."""

    path: pathlib.Path
    rel: str
    module: str
    tree: ast.Module
    lines: list[str]


def parse_audited_files(scope: pathlib.Path) -> list[ParsedSource]:
    """Every Python file under an audit root, parsed once, in path order.

    Raises:
        PhaseBError: a file does not parse; the rules skip it, but a skipped
            file would hide its candidates and let `merge` drop their ledger
            entries as vanished.
    """
    files: list[ParsedSource] = []
    for src_root in auditme.core._audit_roots(scope):
        for path in auditme.core._all_py_files(src_root):
            try:
                text = path.read_text(encoding='utf-8')
                tree = ast.parse(text)
            except (OSError, UnicodeDecodeError, SyntaxError) as error:
                raise PhaseBError(f'cannot parse {path}: {error}') from error
            files.append(ParsedSource(path, auditme.core._relpath(path, scope), auditme.core.module_dotted(path, src_root), tree, text.splitlines()))
    return files


class SiteCounter:
    """Numbers the sites of one qualname by order of appearance, from 1.

    An edit in another function does not change a site's number, so candidate
    ids stay stable.
    """

    def __init__(self) -> None:
        self._counts: collections.Counter[str] = collections.Counter()

    def next(self, qualname: str) -> int:
        """The number of the next site in this qualname."""
        self._counts[qualname] += 1
        return self._counts[qualname]


def walk_with_qualname(tree: ast.AST, qualname: str = MODULE_QUALNAME) -> collections.abc.Iterator[tuple[str, ast.AST]]:
    """Yield (enclosing qualname, node) for every node below `tree`, in source order.

    Module-level code has the qualname `<module>`; a function or class body
    extends the qualname with its name.
    """
    for node in ast.iter_child_nodes(tree):
        yield qualname, node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            inner = node.name if qualname == MODULE_QUALNAME else f'{qualname}.{node.name}'
            yield from walk_with_qualname(node, inner)
        else:
            yield from walk_with_qualname(node, qualname)


def hit_on_anchor(hits: set[tuple[str, str, int]], path: str, lines: collections.abc.Iterable[int], rules: collections.abc.Iterable[str]) -> bool:
    """True when a hit of one of `rules` falls on `path` at one of the anchor `lines`."""
    wanted = set(rules)
    anchors = set(lines)
    return any(rule in wanted and hit_path == path and line in anchors for rule, hit_path, line in hits)
