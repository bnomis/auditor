"""Tests for the checks of the `duplicated-word` rule."""

import collections.abc
import pathlib
import typing

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

DUPLICATED_WORD = auditor.testing.load_check(__file__)


def rules_found(hits: list[dict[str, typing.Any]]) -> set[str]:
    return {hit['rule'] for hit in hits}


# --------------------------------------------------------------------------
# check_duplicated_word
# --------------------------------------------------------------------------


def test_a_duplicated_word_in_a_comment_is_a_hit(project: Builder, run_check: Runner) -> None:
    # auditme: accept[duplicated-word] the duplication is the fixture
    root = project({'src/probe/mod.py': '# resolve the the settings first\nvalue = 1\n'})
    hits = run_check(DUPLICATED_WORD, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('duplicated-word', 1)]


def test_a_duplicated_word_in_a_docstring_is_a_hit(project: Builder, run_check: Runner) -> None:
    # auditme: accept[duplicated-word] the duplication is the fixture
    root = project({'src/probe/mod.py': '"""Resolve the the settings."""\n'})
    assert len(run_check(DUPLICATED_WORD, root)) == 1


def test_a_grammatical_repeat_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """`that that` and friends are ordinary English, not a typo."""
    root = project({'src/probe/mod.py': '# the value that that helper returns\n'})
    assert run_check(DUPLICATED_WORD, root) == []


def test_a_repeat_in_code_rather_than_prose_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """`not not value` repeats a word, but the line is neither comment nor string."""  # auditme: accept[duplicated-word] the duplication is the fixture
    # auditme: accept[duplicated-word] the duplication is the fixture
    root = project({'src/probe/mod.py': 'def f(value: object) -> bool:\n    return not not value\n'})
    assert run_check(DUPLICATED_WORD, root) == []
