"""Tests for the checks of the `migration-shim-consumer` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

MIGRATION_SHIM = auditor.testing.load_check(__file__)


SHIM_TREE = {
    'src/probe/core.py': 'class Thing:\n    pass\n',
    'src/probe/shim.py': 'import probe.core\n\nThing = probe.core.Thing\n',
}


def test_importing_a_symbol_through_a_shim_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({**SHIM_TREE, 'src/probe/user.py': 'from probe.shim import Thing\n\nVALUE = Thing\n'})
    hits = run_check(MIGRATION_SHIM, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('migration-shim-consumer', 'src/probe/user.py')]
    assert 'canonical home is `probe.core`' in hits[0]['variant']


def test_reading_a_symbol_off_a_shim_module_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({**SHIM_TREE, 'src/probe/user.py': 'import probe.shim\n\nVALUE = probe.shim.Thing\n'})
    hits = run_check(MIGRATION_SHIM, root)
    assert len(hits) == 1
    assert 'reads `Thing` from shim' in hits[0]['variant']


def test_importing_from_the_canonical_home_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({**SHIM_TREE, 'src/probe/user.py': 'from probe.core import Thing\n\nVALUE = Thing\n'})
    assert run_check(MIGRATION_SHIM, root) == []


def test_the_shim_module_itself_is_not_its_own_consumer(project: Builder, run_check: Runner) -> None:
    root = project(SHIM_TREE)
    assert run_check(MIGRATION_SHIM, root) == []


def test_one_shim_importing_from_another_is_not_a_consumer(project: Builder, run_check: Runner) -> None:
    """A module that is itself a shim is part of the migration, not a victim of
    it, so it is excluded even when it reads through a sibling shim."""
    root = project(
        {
            **SHIM_TREE,
            'src/probe/other.py': 'import probe.core\n\nOther = probe.core.Other\n\nfrom probe.shim import Thing\n\nVALUE = Thing\n',
        }
    )
    assert run_check(MIGRATION_SHIM, root) == []
