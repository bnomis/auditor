"""Point every test at the default rule catalogue, and register its Phase B questions.

The runner holds no rules: it loads the repository `AUDITOR_RULES_PATH` names.
A test that needs the variable unset deletes it with `monkeypatch`.
"""

import os
import pathlib
import typing

import auditor.phaseb.candidates
import auditor.testing

if typing.TYPE_CHECKING:
    import pytest

CATALOGUE = pathlib.Path(__file__).resolve().parents[1] / 'src' / 'auditor' / 'catalogue'

os.environ['AUDITOR_RULES_PATH'] = str(CATALOGUE)
auditor.phaseb.candidates.use_rules_repository()


def pytest_configure(config: pytest.Config) -> None:
    """Load the `auditor.testing` plugin, which supplies the `project` and `run_check` fixtures, once for every suite."""
    if not config.pluginmanager.has_plugin('auditor-testing'):
        config.pluginmanager.register(auditor.testing, 'auditor-testing')
