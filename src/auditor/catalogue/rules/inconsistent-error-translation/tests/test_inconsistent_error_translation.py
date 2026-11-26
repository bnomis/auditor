"""Tests for the checks of the `inconsistent-error-translation` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

INCONSISTENT = auditor.testing.load_check(__file__)


TRANSLATING_CALLER = """
import probe.errors
import probe.helper


def {name}(label: str) -> int:
    try:
        return probe.helper.load(label)
    except LoadError:
        raise probe.errors.{target}('load failed')
"""


def test_a_domain_error_translated_two_ways_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/helper.py': "def load(label: str) -> int:\n    raise LoadError('nope')\n",
            'src/probe/a.py': TRANSLATING_CALLER.format(name='run_a', target='AlphaError'),
            'src/probe/b.py': TRANSLATING_CALLER.format(name='run_b', target='BetaError'),
        }
    )
    hits = run_check(INCONSISTENT, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('inconsistent-error-translation', 'src/probe/helper.py')]
    assert "['AlphaError', 'BetaError']" in hits[0]['variant']


def test_a_domain_error_translated_consistently_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/helper.py': "def load(label: str) -> int:\n    raise LoadError('nope')\n",
            'src/probe/a.py': TRANSLATING_CALLER.format(name='run_a', target='AlphaError'),
            'src/probe/b.py': TRANSLATING_CALLER.format(name='run_b', target='AlphaError'),
        }
    )
    assert run_check(INCONSISTENT, root) == []
