"""Tests for the checks of the `constructor-disk-io` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

CONSTRUCTOR_IO = auditor.testing.load_check(__file__)


def test_a_constructor_that_touches_disk_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib


            class Store:
                def __init__(self, root: pathlib.Path) -> None:
                    root.mkdir(parents=True, exist_ok=True)
                    self.root = root
            """
        }
    )
    hits = run_check(CONSTRUCTOR_IO, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('constructor-disk-io', 6)]
    assert hits[0]['variant'] == 'Store.__init__ calls disk-IO `mkdir`'


def test_disk_io_in_an_ordinary_method_is_not_a_constructor_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib


            class Store:
                def __init__(self, root: pathlib.Path) -> None:
                    self.root = root

                def prepare(self) -> None:
                    self.root.mkdir(parents=True, exist_ok=True)
            """
        }
    )
    assert run_check(CONSTRUCTOR_IO, root) == []
