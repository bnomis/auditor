"""Tests for the `paired-sibling-helpers` check."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

SIBLING_HELPERS = auditor.testing.load_check(__file__)


# --------------------------------------------------------------------------
# check_paired_sibling_helpers
# --------------------------------------------------------------------------


SHARED_BODY = """
def {name}(path: str) -> str:
    resolved = path.strip().lower()
    return resolved + '-a-long-enough-suffix'
"""


def test_two_functions_with_the_same_body_in_different_files_are_hits(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': SHARED_BODY.format(name='load_a'),
            'src/probe/b.py': SHARED_BODY.format(name='load_b'),
        }
    )
    hits = run_check(SIBLING_HELPERS, root)
    assert {hit['path'] for hit in hits} == {'src/probe/a.py', 'src/probe/b.py'}
    assert all(hit['rule'] == 'paired-sibling-helpers' for hit in hits)
    assert {hit['path']: hit['related'] for hit in hits} == {'src/probe/a.py': ['src/probe/b.py'], 'src/probe/b.py': ['src/probe/a.py']}


def test_two_copies_in_one_file_are_not_a_cross_file_pair(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/a.py': SHARED_BODY.format(name='load_a') + SHARED_BODY.format(name='load_b')})
    assert run_check(SIBLING_HELPERS, root) == []


def test_a_short_body_is_below_the_threshold(project: Builder, run_check: Runner) -> None:
    """Two-line trivia matches everywhere and would drown the real finding."""
    root = project(
        {
            'src/probe/a.py': 'def load_a() -> int:\n    return 1\n',
            'src/probe/b.py': 'def load_b() -> int:\n    return 1\n',
        }
    )
    assert run_check(SIBLING_HELPERS, root) == []
