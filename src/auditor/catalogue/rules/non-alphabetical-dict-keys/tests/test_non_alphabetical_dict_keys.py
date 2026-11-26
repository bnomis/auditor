"""Tests for the checks of the `non-alphabetical-dict-keys` rule."""

import collections.abc
import pathlib
import typing

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

DICT_KEYS = auditor.testing.load_check(__file__)


def rules_found(hits: list[dict[str, typing.Any]]) -> set[str]:
    return {hit['rule'] for hit in hits}


# --------------------------------------------------------------------------
# check_non_alphabetical_dict_keys
# --------------------------------------------------------------------------


def test_an_unsorted_dict_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "SCORERS = {'recall': 1, 'accuracy': 2}\n"})
    hits = run_check(DICT_KEYS, root)
    assert [hit['rule'] for hit in hits] == ['non-alphabetical-dict-keys']


def test_a_sorted_dict_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "SCORERS = {'accuracy': 2, 'recall': 1}\n"})
    assert run_check(DICT_KEYS, root) == []


def test_a_dict_with_non_string_keys_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'CODES = {2: "b", 1: "a"}\n'})
    assert run_check(DICT_KEYS, root) == []
