"""Tests for the `literal-duplication` check."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

LITERAL = auditor.testing.load_check(__file__)


# --------------------------------------------------------------------------
# check_literal_duplication
# --------------------------------------------------------------------------


def test_the_same_string_list_in_two_files_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': "NAMES = ['alpha', 'beta']\n",
            'src/probe/b.py': "LABELS = ['alpha', 'beta']\n",
        }
    )
    hits = run_check(LITERAL, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [
        ('literal-duplication', 'src/probe/a.py'),
        ('literal-duplication', 'src/probe/b.py'),
    ]
    assert [hit['related'] for hit in hits] == [['src/probe/b.py'], ['src/probe/a.py']]


def test_set_membership_is_compared_without_order(project: Builder, run_check: Runner) -> None:
    """A frozenset is unordered, so two spellings of the same set collide."""
    root = project(
        {
            'src/probe/a.py': "NAMES = frozenset({'alpha', 'beta'})\n",
            'src/probe/b.py': "LABELS = frozenset({'beta', 'alpha'})\n",
        }
    )
    assert len(run_check(LITERAL, root)) == 2


def test_a_reordered_list_is_a_different_literal(project: Builder, run_check: Runner) -> None:
    """A list is ordered, so the order is part of what makes it the same."""
    root = project(
        {
            'src/probe/a.py': "NAMES = ['alpha', 'beta']\n",
            'src/probe/b.py': "LABELS = ['beta', 'alpha']\n",
        }
    )
    assert run_check(LITERAL, root) == []


def test_a_literal_that_appears_once_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/a.py': "NAMES = ['alpha', 'beta']\n"})
    assert run_check(LITERAL, root) == []


def test_a_one_member_literal_in_a_test_file_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': "NAMES = ['alpha']\n",
            'src/probe/test_b.py': "def test_x() -> None:\n    assert sorted(['alpha']) == ['alpha']\n    names = ['alpha']\n",
        }
    )
    assert run_check(LITERAL, root) == []


def test_a_literal_inside_an_assert_or_pytest_param_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': "NAMES = ['alpha', 'beta']\n",
            'src/probe/test_b.py': (
                'import pytest\n'
                "CASES = [pytest.param(['alpha', 'beta'], id='x')]\n"
                'def test_x() -> None:\n'
                "    assert sorted(['beta', 'alpha']) == ['alpha', 'beta']\n"
            ),
        }
    )
    assert run_check(LITERAL, root) == []


def test_the_same_one_member_literal_in_source_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': "NAMES = ['alpha']\n",
            'src/probe/b.py': "LABELS = ['alpha']\n",
        }
    )
    assert len(run_check(LITERAL, root)) == 2


def test_a_repeated_multi_member_literal_in_test_set_up_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/test_a.py': "def test_a() -> None:\n    names = ['alpha', 'beta']\n",
            'src/probe/test_b.py': "def test_b() -> None:\n    names = ['alpha', 'beta']\n",
        }
    )
    assert len(run_check(LITERAL, root)) == 2


def test_a_list_of_non_strings_is_not_compared(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/a.py': 'SIZES = [1, 2]\n', 'src/probe/b.py': 'LIMITS = [1, 2]\n'})
    assert run_check(LITERAL, root) == []
