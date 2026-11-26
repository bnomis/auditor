"""Tests for the checks of the `underscore-forloop-target-read` rule."""

import collections.abc
import pathlib
import typing

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

FORLOOP_READ = auditor.testing.load_check(__file__)


def rules_found(hits: list[dict[str, typing.Any]]) -> set[str]:
    return {hit['rule'] for hit in hits}


# --------------------------------------------------------------------------
# check_underscore_forloop_target_read
# --------------------------------------------------------------------------


def test_a_loop_target_marked_unused_but_read_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def f(items: list[int]) -> int:
                total = 0
                for _item in items:
                    total += _item
                return total
            """
        }
    )
    hits = run_check(FORLOOP_READ, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('underscore-forloop-target-read', 3)]


def test_a_loop_target_marked_unused_and_unused_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def f(items: list[int]) -> int:
                total = 0
                for _item in items:
                    total += 1
                return total
            """
        }
    )
    assert run_check(FORLOOP_READ, root) == []
