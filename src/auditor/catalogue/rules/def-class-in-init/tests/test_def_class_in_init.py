"""Tests for the checks of the `def-class-in-init` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

DEF_CLASS_IN_INIT = auditor.testing.load_check(__file__)


def test_a_def_in_an_init_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/__init__.py': 'def helper() -> None:\n    return None\n'})
    hits = run_check(DEF_CLASS_IN_INIT, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('def-class-in-init', 1)]


def test_a_class_in_an_init_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/__init__.py': 'class Thing:\n    pass\n'})
    assert len(run_check(DEF_CLASS_IN_INIT, root)) == 1


def test_a_def_in_an_ordinary_module_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'def helper() -> None:\n    return None\n'})
    assert run_check(DEF_CLASS_IN_INIT, root) == []


def test_an_indented_def_in_an_init_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """The rule is about top-level definitions; a method inside a re-exported
    class body is not one."""
    root = project({'src/probe/__init__.py': 'if True:\n    def helper() -> None:\n        return None\n'})
    assert run_check(DEF_CLASS_IN_INIT, root) == []
