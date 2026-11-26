"""Tests for the checks of the `build-name-has-side-effect` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

BUILD_NAME = auditor.testing.load_check(__file__)


def test_a_build_function_that_reads_the_clock_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import datetime


            def build_run_name(prefix: str) -> str:
                return prefix + datetime.datetime.now().isoformat()
            """
        }
    )
    hits = run_check(BUILD_NAME, root)
    assert [hit['rule'] for hit in hits] == ['build-name-has-side-effect']
    assert '`now`' in hits[0]['variant']


def test_a_build_function_that_only_assembles_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def build_run_name(prefix: str, suffix: str) -> str:
                return prefix + '-' + suffix
            """
        }
    )
    assert run_check(BUILD_NAME, root) == []


def test_a_make_function_that_reads_the_clock_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import datetime


            def make_run_name(prefix: str) -> str:
                return prefix + datetime.datetime.now().isoformat()
            """
        }
    )
    hits = run_check(BUILD_NAME, root)
    assert [hit['rule'] for hit in hits] == ['build-name-has-side-effect']


def test_a_function_that_promises_nothing_may_read_the_clock(project: Builder, run_check: Runner) -> None:
    """Only `build_`/`compute_` names carry the pure-assembly contract."""
    root = project(
        {
            'src/probe/mod.py': """
            import datetime


            def stamp_run_name(prefix: str) -> str:
                return prefix + datetime.datetime.now().isoformat()
            """
        }
    )
    assert run_check(BUILD_NAME, root) == []
