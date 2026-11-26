"""Tests for the checks of the `unused-submodule-import` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

UNUSED_SUBMODULE = auditor.testing.load_check(__file__)


def test_an_unreferenced_submodule_import_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import os.path\n\nVALUE = 1\n'})
    hits = run_check(UNUSED_SUBMODULE, root)
    assert [(hit['rule'], hit['evidence']) for hit in hits] == [('unused-submodule-import', 'import os.path')]


def test_a_referenced_submodule_import_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "import os.path\n\nVALUE = os.path.join('a', 'b')\n"})
    assert run_check(UNUSED_SUBMODULE, root) == []


def test_a_reference_through_the_root_package_counts_as_use(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import os.path\n\nVALUE = os.getcwd()\n'})
    assert run_check(UNUSED_SUBMODULE, root) == []


def test_a_plain_import_without_a_dot_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import os\n\nVALUE = 1\n'})
    assert run_check(UNUSED_SUBMODULE, root) == []
