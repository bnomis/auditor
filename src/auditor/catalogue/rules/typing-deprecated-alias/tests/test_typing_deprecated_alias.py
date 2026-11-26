"""Tests for the checks of the `typing-deprecated-alias` rule."""

import collections.abc
import pathlib
import typing

import pytest

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

TYPING_ALIAS = auditor.testing.load_check(__file__)


def rules_found(hits: list[dict[str, typing.Any]]) -> set[str]:
    return {hit['rule'] for hit in hits}


# --------------------------------------------------------------------------
# check_typing_deprecated_alias
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('source', 'variant'),
    [
        pytest.param(
            'import collections.abc\nimport typing\n\n\ndef f(items: typing.Sequence[int]) -> None:\n    return None\n',
            'typing.Sequence -> collections.abc.Sequence',
            id='sequence',
        ),
        pytest.param(
            'import typing\n\n\ndef f() -> typing.Iterator[int]:\n    yield 1\n',
            'typing.Iterator -> collections.abc.Iterator',
            id='iterator',
        ),
        pytest.param(
            'import typing\n\n\ndef f(x: object) -> bool:\n    return isinstance(x, typing.Mapping)\n',
            'typing.Mapping -> collections.abc.Mapping',
            id='unsubscripted',
        ),
        pytest.param('import typing\n\nvalue: typing.Deque[int]\n', 'typing.Deque -> collections.deque', id='collections'),
        pytest.param('import typing\n\nvalue: typing.Pattern[str]\n', 'typing.Pattern -> re.Pattern', id='re'),
        pytest.param(
            'import typing\n\nvalue: typing.ContextManager[None]\n',
            'typing.ContextManager -> contextlib.AbstractContextManager',
            id='contextlib',
        ),
    ],
)
def test_a_deprecated_typing_alias_is_a_hit(source: str, variant: str, project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': source})
    hits = run_check(TYPING_ALIAS, root)
    assert [(hit['rule'], hit['variant']) for hit in hits] == [('typing-deprecated-alias', variant)]


def test_a_from_typing_import_is_reported_once_at_the_import(project: Builder, run_check: Runner) -> None:
    """The bare uses that follow are the same decision."""
    root = project(
        {
            'src/probe/mod.py': """
            from typing import Any, Iterable, Sequence


            def f(items: Sequence[int], more: Iterable[Any]) -> Sequence[int]:
                return items
            """,
        }
    )
    hits = run_check(TYPING_ALIAS, root)
    assert [(hit['line'], hit['variant']) for hit in hits] == [
        (1, 'typing.Iterable -> collections.abc.Iterable'),
        (1, 'typing.Sequence -> collections.abc.Sequence'),
    ]


def test_two_aliases_on_one_line_are_two_hits_and_one_alias_used_twice_is_one(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import typing\n\nvalue: typing.Mapping[str, typing.Sequence[int]] | typing.Sequence[str]\n'})
    assert [hit['variant'] for hit in run_check(TYPING_ALIAS, root)] == [
        'typing.Mapping -> collections.abc.Mapping',
        'typing.Sequence -> collections.abc.Sequence',
    ]


@pytest.mark.parametrize(
    'source',
    [
        pytest.param('import collections.abc\n\nvalue: collections.abc.Sequence[int]\n', id='collections-abc'),
        pytest.param('import typing\n\nvalue: typing.Any\nT = typing.TypeVar("T")\n', id='no-stdlib-replacement'),
        pytest.param('import typing\n\nvalue: typing.List[int]\n', id='builtin-alias-is-legacy-typing'),
        pytest.param("NOTE = 'use typing.Sequence'\n# typing.Iterator\n", id='string-and-comment'),
    ],
)
def test_names_this_rule_does_not_own_are_not_hits(source: str, project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': source})
    assert run_check(TYPING_ALIAS, root) == []


def test_a_scoped_accept_marker_dismisses_the_typing_alias(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import typing\n\nvalue: typing.Sequence[int]  # auditme: accept[typing-deprecated-alias] stub mirror\n'})
    assert [(hit['accepted'], hit['accepted_reason']) for hit in run_check(TYPING_ALIAS, root)] == [(True, 'stub mirror')]


def test_a_marker_scoped_to_another_rule_does_not_dismiss_the_typing_alias(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import typing\n\nvalue: typing.Sequence[int]  # auditme: accept[legacy-typing] unrelated\n'})
    assert [hit['accepted'] for hit in run_check(TYPING_ALIAS, root)] == [False]
