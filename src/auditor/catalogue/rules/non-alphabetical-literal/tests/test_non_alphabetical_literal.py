"""Tests for the checks of the `non-alphabetical-literal` rule."""

import collections.abc
import pathlib
import typing

import hypothesis
import hypothesis.strategies
import pytest

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

LITERALS = auditor.testing.load_check(__file__)
CHECK_MODULE = auditor.testing.load_check_module(__file__)


def rules_found(hits: list[dict[str, typing.Any]]) -> set[str]:
    return {hit['rule'] for hit in hits}


# --------------------------------------------------------------------------
# check_nonalphabetical_literals
# --------------------------------------------------------------------------


def test_an_unsorted_string_list_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "NAMES = ['bird', 'aardvark']\n"})
    hits = run_check(LITERALS, root)
    assert [hit['rule'] for hit in hits] == ['non-alphabetical-literal']
    assert hits[0]['line'] == 1


def test_an_unsorted_frozenset_literal_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "NAMES = frozenset({'bird', 'aardvark'})\n"})
    assert len(run_check(LITERALS, root)) == 1


def test_a_sorted_string_list_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "NAMES = ['aardvark', 'bird']\n"})
    assert run_check(LITERALS, root) == []


def test_a_list_of_non_strings_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """Ordering is only meaningful where the members are names."""
    root = project({'src/probe/mod.py': 'SIZES = [2, 1]\n'})
    assert run_check(LITERALS, root) == []


def test_a_single_member_list_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "NAMES = ['bird']\n"})
    assert run_check(LITERALS, root) == []


def test_a_list_inside_a_function_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """The rule is about module-level configuration, not local working values."""
    root = project({'src/probe/mod.py': "def f() -> list[str]:\n    names = ['bird', 'aardvark']\n    return names\n"})
    assert run_check(LITERALS, root) == []


@pytest.mark.parametrize(
    'source',
    [
        pytest.param("PAIR: tuple[str, str] = ('xxx', 'REDACTED')\n", id='fixed-pair'),
        pytest.param("import typing\n\nPAIR: typing.Final[tuple[str, str]] = ('b', 'a')\n", id='final-fixed-pair'),
    ],
)
def test_a_fixed_length_tuple_keeps_its_order(source: str, project: Builder, run_check: Runner) -> None:
    """Each position of a fixed-length tuple means something, so it cannot be sorted."""
    root = project({'src/probe/mod.py': source})
    assert run_check(LITERALS, root) == []


@pytest.mark.parametrize(
    'source',
    [
        pytest.param("NAMES: tuple[str, ...] = ('b', 'a')\n", id='variable-length-tuple'),
        pytest.param("NAMES = ('b', 'a')\n", id='unannotated-tuple'),
        pytest.param("NAMES: list[str] = ['b', 'a']\n", id='annotated-list'),
        pytest.param("NAMES: frozenset[str] = frozenset({'b', 'a'})\n", id='annotated-frozenset'),
    ],
)
def test_only_a_fixed_length_tuple_is_exempt(source: str, project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': source})
    assert [hit['rule'] for hit in run_check(LITERALS, root)] == ['non-alphabetical-literal']


RUFF_ORDER = "['X_Y', 'Thing', '_private', 'helper', 'item2', 'item10']"


def test_ruff_order_of_dunder_all_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': f'__all__ = {RUFF_ORDER}\n'})
    assert run_check(LITERALS, root) == []


def test_ruff_order_under_another_name_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': f'NAMES = {RUFF_ORDER}\n'})
    assert [hit['rule'] for hit in run_check(LITERALS, root)] == ['non-alphabetical-literal']


def test_a_plainly_sorted_dunder_all_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "__all__ = ['Thing', 'helper']\n"})
    assert run_check(LITERALS, root) == []


def test_a_dunder_all_in_neither_order_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "__all__ = ['helper', 'X_Y', 'Thing']\n"})
    assert [hit['rule'] for hit in run_check(LITERALS, root)] == ['non-alphabetical-literal']


def test_an_annotated_dunder_all_in_ruff_order_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': f'__all__: list[str] = {RUFF_ORDER}\n'})
    assert run_check(LITERALS, root) == []


def test_ruff_dunder_all_key_groups_then_natural_order() -> None:
    names = ['item10', 'helper', 'Thing', '_private', 'X_Y', 'item2']
    assert sorted(names, key=CHECK_MODULE.ruff_dunder_all_key) == [
        'X_Y',
        'Thing',
        '_private',
        'helper',
        'item2',
        'item10',
    ]


def test_ruff_dunder_all_key_treats_a_single_capital_as_camel_case() -> None:
    key = CHECK_MODULE.ruff_dunder_all_key
    assert key('A')[0] == 1
    assert key('AB')[0] == 0


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    name=hypothesis.strategies.from_regex(r'[A-Za-z_]{1,6}', fullmatch=True),
    low=hypothesis.strategies.integers(0, 50),
    high=hypothesis.strategies.integers(0, 50),
)
def test_ruff_dunder_all_key_groups_and_orders_digit_runs_naturally(name: str, low: int, high: int) -> None:
    key = CHECK_MODULE.ruff_dunder_all_key
    group = key(name)[0]
    if len(name) > 1 and name.isupper():
        assert group == 0
    elif name[:1].isupper():
        assert group == 1
    else:
        assert group == 2
    assert (key(f'{name}{low}') < key(f'{name}{high}')) == (low < high)
