"""Tests for the checks of the `silent-broad-except` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

SILENT_BROAD = auditor.testing.load_check(__file__)


def test_a_broad_except_that_neither_logs_nor_raises_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def run() -> None:
                try:
                    probe.core.risky()
                except Exception:
                    pass
            """
        }
    )
    hits = run_check(SILENT_BROAD, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('silent-broad-except', 7)]


def test_a_broad_except_that_logs_is_not_silent(project: Builder, run_check: Runner) -> None:
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
    assert run_check(SILENT_BROAD, root) == []


def test_a_narrow_except_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def run() -> None:
                try:
                    probe.core.risky()
                except OSError:
                    pass
            """
        }
    )
    assert run_check(SILENT_BROAD, root) == []
