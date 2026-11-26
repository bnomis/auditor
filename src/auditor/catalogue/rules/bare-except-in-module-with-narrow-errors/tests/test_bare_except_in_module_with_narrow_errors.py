"""Tests for the checks of the `bare-except-in-module-with-narrow-errors` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

MIXED_EXCEPT = auditor.testing.load_check(__file__)


def test_a_module_that_mixes_narrow_tuples_with_broad_catches_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core

            NETWORK_ERRORS = (OSError, TimeoutError)


            def fetch(url: str) -> str:
                try:
                    return probe.core.get(url)
                except NETWORK_ERRORS:
                    return ''


            def post(url: str) -> str:
                try:
                    return probe.core.post(url)
                except Exception:
                    return ''
            """
        }
    )
    hits = run_check(MIXED_EXCEPT, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('bare-except-in-module-with-narrow-errors', 16)]
    assert hits[0]['evidence'] == 'except Exception:'


def test_a_module_with_only_broad_catches_is_not_mid_sweep(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def post(url: str) -> str:
                try:
                    return probe.core.post(url)
                except Exception:
                    return ''
            """
        }
    )
    assert run_check(MIXED_EXCEPT, root) == []
