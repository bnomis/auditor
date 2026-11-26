"""Tests for the checks of the `from-import` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

FROM_IMPORT = auditor.testing.load_check(__file__)


def test_a_from_import_in_a_module_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'from pathlib import Path, PurePath\n'})
    hits = run_check(FROM_IMPORT, root)
    assert [(hit['rule'], hit['line'], hit['evidence']) for hit in hits] == [('from-import', 1, 'from pathlib import Path, PurePath')]


def test_a_from_import_inside_a_function_or_type_checking_block_is_a_hit(project: Builder, run_check: Runner) -> None:
    """A from-import is one wherever it is written; the sites that prompted the
    check included a conftest fixture body."""
    root = project(
        {
            'src/probe/mod.py': """
            import typing

            if typing.TYPE_CHECKING:
                from probe.core import Thing


            def fixture() -> object:
                from probe.core import Widget

                return Widget
            """,
        }
    )
    assert [hit['line'] for hit in run_check(FROM_IMPORT, root)] == [4, 8]


def test_a_relative_from_import_in_a_module_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'from . import core\n'})
    assert [hit['evidence'] for hit in run_check(FROM_IMPORT, root)] == ['from . import core']


def test_the_test_tree_is_swept_like_any_other_root(project: Builder, run_check: Runner) -> None:
    root = project({'src/tests/conftest.py': 'from probe.core import Thing\n'})
    assert [hit['path'] for hit in run_check(FROM_IMPORT, root, package='tests')] == ['src/tests/conftest.py']


def test_a_from_import_in_an_init_is_the_sanctioned_re_export(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/__init__.py': "from .core import Thing\nfrom probe.base import Widget\n\n__all__ = ['Thing', 'Widget']\n"})
    assert run_check(FROM_IMPORT, root) == []


def test_future_and_star_imports_are_left_to_their_own_rules(project: Builder, run_check: Runner) -> None:
    """`future-annotations` and `wildcard-imports` already report these lines."""
    root = project({'src/probe/mod.py': 'from __future__ import annotations\nfrom os import *\n'})
    assert run_check(FROM_IMPORT, root) == []


def test_a_plain_import_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import pathlib\nimport probe.core\n'})
    assert run_check(FROM_IMPORT, root) == []


def test_the_check_needs_no_declaration_in_agents(project: Builder, run_check: Runner) -> None:
    """Unlike `as-import`, the rule is the shared standard, not a project opt-in."""
    root = project({'AGENTS.md': '# probe\n\n## Imports\n\nFollow isort ordering.\n', 'src/probe/mod.py': 'from pathlib import Path\n'})
    assert [hit['rule'] for hit in run_check(FROM_IMPORT, root)] == ['from-import']


def test_a_marker_on_a_continuation_line_accepts_a_multiline_from_import(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            from probe.core import (
                Thing,  # auditme: accept[from-import] vendored module
            )
            """,
        }
    )
    assert [(hit['accepted'], hit['accepted_reason']) for hit in run_check(FROM_IMPORT, root)] == [(True, 'vendored module')]


def test_a_scoped_accept_marker_dismisses_the_from_import(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'from pathlib import Path  # auditme: accept[from-import] generated code\n'})
    assert [(hit['accepted'], hit['accepted_reason']) for hit in run_check(FROM_IMPORT, root)] == [(True, 'generated code')]


def test_a_marker_scoped_to_another_rule_does_not_dismiss_the_from_import(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'from pathlib import Path  # auditme: accept[as-import] unrelated\n'})
    assert [hit['accepted'] for hit in run_check(FROM_IMPORT, root)] == [False]
