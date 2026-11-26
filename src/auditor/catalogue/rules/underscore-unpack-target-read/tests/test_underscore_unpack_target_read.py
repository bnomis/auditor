"""Tests for the checks of the `underscore-unpack-target-read` rule."""

import collections.abc
import pathlib
import typing

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

UNPACK_READ = auditor.testing.load_check(__file__)


def rules_found(hits: list[dict[str, typing.Any]]) -> set[str]:
    return {hit['rule'] for hit in hits}


# --------------------------------------------------------------------------
# check_underscore_unpack_target_read
# --------------------------------------------------------------------------


def test_an_unpacked_underscore_name_that_is_read_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def f(pair: tuple[int, int]) -> int:
                _first, second = pair
                return _first + second
            """
        }
    )
    hits = run_check(UNPACK_READ, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('underscore-unpack-target-read', 2)]
    assert '_first' in hits[0]['variant']


def test_an_unpacked_underscore_name_that_is_never_read_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def f(pair: tuple[int, int]) -> int:
                _first, second = pair
                return second
            """
        }
    )
    assert run_check(UNPACK_READ, root) == []


def test_a_bare_underscore_target_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """Single `_` is the sanctioned throwaway."""
    root = project(
        {
            'src/probe/mod.py': """
            def f(pair: tuple[int, int]) -> int:
                _, second = pair
                return second
            """
        }
    )
    assert run_check(UNPACK_READ, root) == []
