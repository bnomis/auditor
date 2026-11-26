"""Tests for the checks of the `try-wrapping-with-block-too-broad` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

TRY_WITH = auditor.testing.load_check(__file__)


def test_a_handler_that_re_runs_the_wrapped_work_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import probe.errors


            def run_batch(config: dict) -> None:
                try:
                    with probe.core.open_batch_run(config):
                        probe.core.run_pipeline(config)
                except probe.errors.RegistryError:
                    probe.core.run_pipeline(config)
            """
        }
    )
    hits = run_check(TRY_WITH, root)
    assert [hit['rule'] for hit in hits] == ['try-wrapping-with-block-too-broad']
    assert 'run_pipeline' in hits[0]['variant']


def test_a_handler_that_only_reports_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import loguru
            import probe.core
            import probe.errors


            def run_batch(config: dict) -> None:
                try:
                    with probe.core.open_batch_run(config):
                        probe.core.run_pipeline(config)
                except probe.errors.RegistryError:
                    loguru.logger.exception('startup failed')
            """
        }
    )
    assert run_check(TRY_WITH, root) == []
