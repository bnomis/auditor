"""Tests for the checks of the `passthrough-shim` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

PASSTHROUGH = auditor.testing.load_check(__file__)


def test_a_function_that_only_forwards_its_arguments_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def load(path: str, mode: str) -> object:
                return probe.core.load(path, mode)
            """
        }
    )
    hits = run_check(PASSTHROUGH, root)
    assert [(hit['rule'], hit['variant']) for hit in hits] == [('passthrough-shim', 'load is a pass-through wrapper for probe.core.load')]


def test_a_docstring_does_not_stop_it_being_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def load(path: str) -> object:
                \"\"\"Load the thing.\"\"\"
                return probe.core.load(path)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 1


def test_a_function_that_does_more_than_forward_is_not_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def load(path: str) -> object:
                resolved = path.strip()
                return probe.core.load(resolved)
            """
        }
    )
    assert run_check(PASSTHROUGH, root) == []


def test_a_call_with_a_computed_argument_is_not_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def load(path: str) -> object:
                return probe.core.load(path.strip())
            """
        }
    )
    assert run_check(PASSTHROUGH, root) == []


def test_a_call_that_repeats_a_parameter_is_not_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            def load(name: str) -> object:
                return probe.core.get(name, name)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 0


def test_a_keyword_with_a_computed_value_is_not_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            def load(x: str) -> object:
                return probe.core.load(x, size=len(x))
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 0


def test_a_double_star_keyword_is_not_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            def load(x: str, **opts: object) -> object:
                return probe.core.load(x, **opts)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 0


def test_a_pytest_fixture_is_not_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            @pytest.fixture
            def load(x: str) -> object:
                return probe.core.load(x)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 0


def test_a_pytest_fixture_with_arguments_is_not_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            @pytest.fixture(scope='module')
            def load(x: str) -> object:
                return probe.core.load(x)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 0


def test_any_decorator_excludes_a_function_from_being_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            @probe.core.register
            def load(x: str) -> object:
                return probe.core.load(x)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 0


def test_a_forward_with_a_keyword_parameter_is_still_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            def load(a: str, key: str) -> object:
                return probe.core.load(a, key=key)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 1


def test_a_forward_of_two_positionals_is_still_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            def load(a: str, b: str) -> object:
                return probe.core.load(a, b)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 1
