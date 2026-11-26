"""Tests for the checks of the `broad-except-wrong-level` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

WRONG_LEVEL = auditor.testing.load_check(__file__)


def test_a_broad_except_logging_at_warning_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import loguru
            import probe.core


            def run() -> None:
                try:
                    probe.core.risky()
                except Exception:
                    loguru.logger.warning('failed')
            """
        }
    )
    hits = run_check(WRONG_LEVEL, root)
    assert [hit['rule'] for hit in hits] == ['broad-except-wrong-level']


def test_a_broad_except_logging_at_exception_is_correct(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import loguru
            import probe.core


            def run() -> None:
                try:
                    probe.core.risky()
                except Exception:
                    loguru.logger.exception('failed')
            """
        }
    )
    assert run_check(WRONG_LEVEL, root) == []
