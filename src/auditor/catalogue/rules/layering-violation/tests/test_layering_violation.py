"""Tests for the checks of the `layering-violation` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

LAYERING = auditor.testing.load_check(__file__)

LAYERING_AGENTS = """
# probe

## Package Layering

data < config < models

### Accepted cross-layer exceptions

| Importer | Imported | Reason |
|----------|----------|--------|
| `data` | `config` | settings are read at load time |
"""


def test_an_upward_import_violates_the_layering(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'AGENTS.md': LAYERING_AGENTS,
            'src/probe/data/loader.py': 'import probe.models.thing\n\nVALUE = probe.models.thing\n',
        }
    )
    hits = run_check(LAYERING, root)
    assert [(hit['rule'], hit['variant']) for hit in hits] == [('layering-violation', 'data imports models (upward)')]


def test_a_downward_import_is_not_a_violation(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'AGENTS.md': LAYERING_AGENTS,
            'src/probe/models/thing.py': 'import probe.data.loader\n\nVALUE = probe.data.loader\n',
        }
    )
    assert run_check(LAYERING, root) == []


def test_an_agents_exception_row_permits_the_inversion(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'AGENTS.md': LAYERING_AGENTS,
            'src/probe/data/loader.py': 'import probe.config.settings\n\nVALUE = probe.config.settings\n',
        }
    )
    assert run_check(LAYERING, root) == []


def test_a_project_that_declares_no_layering_is_not_checked(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/data/loader.py': 'import probe.models.thing\n\nVALUE = probe.models.thing\n'})
    assert run_check(LAYERING, root) == []


def test_a_layering_violation_under_type_checking_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'AGENTS.md': LAYERING_AGENTS,
            'src/probe/data/loader.py': 'import typing\n\nif typing.TYPE_CHECKING:\n    import probe.models.thing\n',
        }
    )
    assert run_check(LAYERING, root) == []
