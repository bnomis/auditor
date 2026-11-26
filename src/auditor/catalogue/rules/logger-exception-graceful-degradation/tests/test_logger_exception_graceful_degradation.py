"""Tests for the checks of the `logger-exception-graceful-degradation` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

GRACEFUL = auditor.testing.load_check(__file__)


def test_logging_at_exception_then_returning_a_default_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import loguru
            import probe.core


            def lookup(key: str) -> str | None:
                try:
                    return probe.core.fetch(key)
                except Exception:
                    loguru.logger.exception('lookup failed')
                    return None
            """
        }
    )
    hits = run_check(GRACEFUL, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('logger-exception-graceful-degradation', 10)]


def test_a_cli_exit_code_is_the_canonical_error_contract(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import loguru
            import probe.core


            def run_train(label: str) -> int:
                try:
                    probe.core.train(label)
                except Exception:
                    loguru.logger.exception('train failed')
                    return 2
                return 0
            """
        }
    )
    assert run_check(GRACEFUL, root) == []


def test_a_handler_that_re_raises_is_not_degradation(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import loguru
            import probe.core


            def lookup(key: str) -> str | None:
                try:
                    return probe.core.fetch(key)
                except Exception:
                    loguru.logger.exception('lookup failed')
                    raise
            """
        }
    )
    assert run_check(GRACEFUL, root) == []
