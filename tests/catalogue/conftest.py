"""Load the `auditor.testing` plugin, which supplies the `project` and `run_check` fixtures."""

import typing

import auditor.testing

if typing.TYPE_CHECKING:
    import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register the plugin for this suite, as `tests/checker/conftest.py` does."""
    if not config.pluginmanager.has_plugin('auditor-testing'):
        config.pluginmanager.register(auditor.testing, 'auditor-testing')
