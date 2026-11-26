import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


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


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `typing.<alias>` for every alias PEP 585 deprecated in favour of a standard-library class."""
    rule = 'typing-deprecated-alias'
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        found: set[tuple[int, str]] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'typing':
                if node.attr in TYPING_DEPRECATED_ALIASES:
                    found.add((node.lineno, node.attr))
            elif isinstance(node, ast.ImportFrom) and node.module == 'typing' and node.level == 0:
                found.update((node.lineno, alias.name) for alias in node.names if alias.name in TYPING_DEPRECATED_ALIASES)
        for lineno, name in sorted(found):
            accept = auditor.api.accept_reason(lines, lineno, rule=rule)
            auditor.api.emit(
                rule=rule,
                variant=f'typing.{name} -> {TYPING_DEPRECATED_ALIASES[name]}',
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200] if 1 <= lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
