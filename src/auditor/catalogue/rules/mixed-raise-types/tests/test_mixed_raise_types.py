"""Tests for the checks of the `mixed-raise-types` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

MIXED_RAISE = auditor.testing.load_check(__file__)


def test_a_function_mixing_stdlib_and_project_errors_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def check(value: int) -> int:
                if value < 0:
                    raise ValueError('negative')
                if value > 10:
                    raise probe.errors.ProbeError('too large')
                return value
            """
        }
    )
    hits = run_check(MIXED_RAISE, root)
    assert [hit['rule'] for hit in hits] == ['mixed-raise-types']
    assert "['ValueError']" in hits[0]['variant']


def test_a_function_raising_only_project_errors_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def check(value: int) -> int:
                if value < 0:
                    raise probe.errors.RangeError('negative')
                if value > 10:
                    raise probe.errors.ProbeError('too large')
                return value
            """
        }
    )
    assert run_check(MIXED_RAISE, root) == []
