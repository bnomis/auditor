"""Tests for the checks of the `mutable-store-without-copy` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

STORE_WITHOUT_COPY = auditor.testing.load_check(__file__)


def test_storing_a_dict_parameter_by_reference_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Store:
                def __init__(self, options: dict[str, int]) -> None:
                    self.options = options
            """
        }
    )
    hits = run_check(STORE_WITHOUT_COPY, root)
    assert [hit['rule'] for hit in hits] == ['mutable-store-without-copy']


def test_a_defensive_copy_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Store:
                def __init__(self, options: dict[str, int]) -> None:
                    self.options = dict(options)
            """
        }
    )
    assert run_check(STORE_WITHOUT_COPY, root) == []


def test_an_immutable_parameter_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Store:
                def __init__(self, options: tuple[int, ...]) -> None:
                    self.options = options
            """
        }
    )
    assert run_check(STORE_WITHOUT_COPY, root) == []
