"""Tests for the checks of the `legacy-formatting-percent` rule."""

import collections.abc
import pathlib
import typing

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

PERCENT = auditor.testing.load_check(__file__)


def rules_found(hits: list[dict[str, typing.Any]]) -> set[str]:
    return {hit['rule'] for hit in hits}


# --------------------------------------------------------------------------
# check_percent_formatting
# --------------------------------------------------------------------------


def test_percent_s_formatting_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "def f(e: Exception) -> str:\n    return 'Exception: %s' % e\n"})
    hits = run_check(PERCENT, root)
    assert [hit['rule'] for hit in hits] == ['legacy-formatting-percent']
    assert hits[0]['line'] == 2


def test_a_strftime_directive_is_not_percent_formatting(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "import datetime\n\n\ndef f(when: datetime.datetime) -> str:\n    return when.strftime('%Y-%m-%d %H:%M:%S')\n"})
    assert run_check(PERCENT, root) == []


def test_a_line_with_several_percent_literals_reports_once(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "def f(a: str, b: str) -> str:\n    return '%s' + '%d' + a + b\n"})
    assert len(run_check(PERCENT, root)) == 1
