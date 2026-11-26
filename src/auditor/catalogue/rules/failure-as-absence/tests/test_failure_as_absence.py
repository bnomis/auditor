"""Tests for the checks of the `failure-as-absence` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

FAILURE_AS_ABSENCE = auditor.testing.load_check(__file__)


def test_an_adapter_returning_none_from_a_handler_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/sources/api.py': """
            import probe.core


            def fetch(url: str) -> dict | None:
                try:
                    return probe.core.get(url)
                except OSError:
                    return None
            """
        }
    )
    hits = run_check(FAILURE_AS_ABSENCE, root)
    assert [hit['rule'] for hit in hits] == ['failure-as-absence']
    assert 'caught exception returns empty' in hits[0]['variant']


def test_an_adapter_returning_none_on_a_non_200_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/sources/api.py': """
            import probe.core


            def fetch(url: str) -> dict | None:
                response = probe.core.get(url)
                if response.status != 200:
                    return None
                return response.body
            """
        }
    )
    hits = run_check(FAILURE_AS_ABSENCE, root)
    assert [hit['variant'] for hit in hits] == ['non-200 branch returns empty (return None)']


def test_a_handler_that_raises_records_the_failure(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/sources/api.py': """
            import probe.core
            import probe.errors


            def fetch(url: str) -> dict:
                try:
                    return probe.core.get(url)
                except OSError as exc:
                    raise probe.errors.SearchError('fetch failed') from exc
            """
        }
    )
    assert run_check(FAILURE_AS_ABSENCE, root) == []


def test_the_same_shape_outside_an_adapter_directory_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    """Outside an adapter a bare `return None` is often a legitimate cache miss."""
    root = project(
        {
            'src/probe/util/api.py': """
            import probe.core


            def fetch(url: str) -> dict | None:
                try:
                    return probe.core.get(url)
                except OSError:
                    return None
            """
        }
    )
    assert run_check(FAILURE_AS_ABSENCE, root) == []
