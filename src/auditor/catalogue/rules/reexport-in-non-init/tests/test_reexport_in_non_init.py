"""Tests for the checks of the `reexport-in-non-init` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

REEXPORT = auditor.testing.load_check(__file__)


def test_a_reexport_outside_an_init_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import probe.core\n\nThing = probe.core.Thing\n'})
    hits = run_check(REEXPORT, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('reexport-in-non-init', 3)]


def test_a_reexport_inside_an_init_is_the_sanctioned_place(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/__init__.py': 'import probe.core\n\nThing = probe.core.Thing\n'})
    assert run_check(REEXPORT, root) == []


def test_an_assignment_whose_name_differs_is_not_a_reexport(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import probe.core\n\nDEFAULT = probe.core.Thing\n'})
    assert run_check(REEXPORT, root) == []
