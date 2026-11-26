"""Tests for the checks of the `dead-local-init` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

DEAD_LOCAL = auditor.testing.load_check(__file__)


def test_an_initial_value_overridden_on_every_branch_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def resolve(flag: bool) -> dict:
                result = {}
                if flag:
                    result = {'a': 1}
                    return result
                else:
                    result = {'b': 2}
                    return result
            """
        }
    )
    hits = run_check(DEAD_LOCAL, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('dead-local-init', 2)]


def test_an_initial_value_with_no_else_branch_is_not_dead(project: Builder, run_check: Runner) -> None:
    """Without an else the initial value is what the fall-through path returns."""
    root = project(
        {
            'src/probe/mod.py': """
            def resolve(flag: bool) -> dict:
                result = {}
                if flag:
                    result = {'a': 1}
                    return result
            """
        }
    )
    assert run_check(DEAD_LOCAL, root) == []
