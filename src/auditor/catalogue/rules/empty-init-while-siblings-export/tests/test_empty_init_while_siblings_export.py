"""Tests for the checks of the `empty-init-while-siblings-export` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

EMPTY_INIT = auditor.testing.load_check(__file__)


EXPORTING_SIBLING = "__all__ = ['A', 'B', 'C', 'D', 'E']\n"


def test_an_empty_init_beside_an_exporting_sibling_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/__init__.py': '',
            'src/probe/rich/__init__.py': EXPORTING_SIBLING,
            'src/probe/sparse/__init__.py': '"""Nothing exported."""\n',
        }
    )
    hits = run_check(EMPTY_INIT, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('empty-init-while-siblings-export', 'src/probe/sparse/__init__.py')]


def test_no_sibling_with_a_real_surface_means_the_rule_does_not_apply(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/__init__.py': '',
            'src/probe/thin/__init__.py': "__all__ = ['A']\n",
            'src/probe/sparse/__init__.py': '"""Nothing exported."""\n',
        }
    )
    assert run_check(EMPTY_INIT, root) == []


def test_a_marker_anywhere_in_the_file_accepts_the_finding(project: Builder, run_check: Runner) -> None:
    """A docstring-only `__init__.py` has no line to hang an inline marker on."""
    root = project(
        {
            'src/probe/__init__.py': '',
            'src/probe/rich/__init__.py': EXPORTING_SIBLING,
            'src/probe/sparse/__init__.py': '"""Nothing exported."""\n\n# auditme: accept[empty-init-while-siblings-export] internal grouping only\n',
        }
    )
    hits = run_check(EMPTY_INIT, root)
    assert len(hits) == 1
    assert hits[0]['accepted']
    assert hits[0]['accepted_reason'] == 'internal grouping only'
