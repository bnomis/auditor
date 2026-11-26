"""Tests for the checks of the `subprocess-without-memoisation` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

SUBPROCESS = auditor.testing.load_check(__file__)


def test_an_uncached_query_that_shells_out_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import subprocess


            def get_head_sha() -> str:
                return subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True).stdout
            """
        }
    )
    hits = run_check(SUBPROCESS, root)
    assert [hit['rule'] for hit in hits] == ['subprocess-without-memoisation']


def test_a_cached_query_that_shells_out_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import functools
            import subprocess


            @functools.cache
            def get_head_sha() -> str:
                return subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True).stdout
            """
        }
    )
    assert run_check(SUBPROCESS, root) == []


def test_a_name_that_does_not_promise_invariance_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import subprocess


            def run_git_command() -> str:
                return subprocess.run(['git', 'status'], capture_output=True).stdout
            """
        }
    )
    assert run_check(SUBPROCESS, root) == []
