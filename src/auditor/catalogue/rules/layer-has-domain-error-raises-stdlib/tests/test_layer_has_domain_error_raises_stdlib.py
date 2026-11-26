"""Tests for the checks of the `layer-has-domain-error-raises-stdlib` rule."""

import collections.abc
import pathlib

import pytest

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

STDLIB_RAISE = auditor.testing.load_check(__file__)


DOMAIN_ERRORS = 'class DataError(Exception):\n    pass\n'
NEWLY_READ_STDLIB_RAISES = ['FileNotFoundError', 'TypeError']


def test_raising_stdlib_where_the_package_has_a_domain_error_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/data/errors.py': DOMAIN_ERRORS,
            'src/probe/data/loader.py': "def load(value: int) -> int:\n    if value < 0:\n        raise ValueError('negative')\n    return value\n",
        }
    )
    hits = run_check(STDLIB_RAISE, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('layer-has-domain-error-raises-stdlib', 3)]


@pytest.mark.parametrize('exception', NEWLY_READ_STDLIB_RAISES)
def test_raising_type_or_file_not_found_error_is_a_hit(project: Builder, run_check: Runner, exception: str) -> None:
    root = project(
        {
            'src/probe/data/errors.py': DOMAIN_ERRORS,
            'src/probe/data/loader.py': f"def load(value: int) -> int:\n    if value < 0:\n        raise {exception}('negative')\n    return value\n",
        }
    )
    hits = run_check(STDLIB_RAISE, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('layer-has-domain-error-raises-stdlib', 3)]


@pytest.mark.parametrize('exception', NEWLY_READ_STDLIB_RAISES)
def test_type_or_file_not_found_error_inside_a_handler_is_not_a_hit(project: Builder, run_check: Runner, exception: str) -> None:
    root = project(
        {
            'src/probe/data/errors.py': DOMAIN_ERRORS,
            'src/probe/data/loader.py': f"def load(path: str) -> str:\n    try:\n        return open(path).read()\n    except OSError:\n        raise {exception}('bad')\n",
        }
    )
    assert run_check(STDLIB_RAISE, root) == []


def test_a_re_raise_inside_a_handler_is_the_narrowing_pattern(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/data/errors.py': DOMAIN_ERRORS,
            'src/probe/data/loader.py': """
            import probe.core


            def load(value: int) -> int:
                try:
                    return probe.core.parse(value)
                except TypeError:
                    raise ValueError('bad value')
            """,
        }
    )
    assert run_check(STDLIB_RAISE, root) == []


def test_a_package_with_no_errors_module_is_not_checked(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/data/loader.py': "def load(value: int) -> int:\n    raise ValueError('negative')\n"})
    assert run_check(STDLIB_RAISE, root) == []
