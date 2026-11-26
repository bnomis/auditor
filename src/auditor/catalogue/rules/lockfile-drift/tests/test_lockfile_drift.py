"""Tests for the checks of the `lockfile-drift` rule."""

import collections.abc
import pathlib
import subprocess
import typing

import auditor.core
import auditor.sweep
import auditor.testing

if typing.TYPE_CHECKING:
    import pytest

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

LOCKFILE = auditor.testing.load_check(__file__)


def test_a_project_without_a_lockfile_is_not_checked(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'VALUE = 1\n', 'pyproject.toml': '[project]\nname = "probe"\n'})
    assert run_check(LOCKFILE, root) == []


def test_drift_and_an_unanswerable_check_are_different_facts(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reporting "could not verify" as drift would be failure-as-absence in the
    checker itself."""

    class Result:
        def __init__(self, stderr: str) -> None:
            self.returncode = 1
            self.stdout = ''
            self.stderr = stderr

    root = project(
        {
            'src/probe/mod.py': 'VALUE = 1\n',
            'pyproject.toml': '[project]\nname = "probe"\n',
            'uv.lock': 'version = 1\n',
        }
    )

    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: Result('error: The lockfile at `uv.lock` needs to be updated\n'))
    drift = run_check(LOCKFILE, root)
    assert len(drift) == 1
    assert 'out of date' in drift[0]['variant']

    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: Result('error: network unreachable\n'))
    unverified = run_check(LOCKFILE, root)
    assert len(unverified) == 1
    assert 'could not verify' in unverified[0]['variant']


def test_a_resolution_timestamp_is_masked_out_of_the_evidence(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The evidence string has to be identical between runs or the audit reads
    an unchanged tree as a changed one."""

    class Result:
        returncode = 1
        stdout = ''
        stderr = 'error: failed at 2026-08-15T10:11:12.345Z on `uv.lock`\n'

    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: Result())
    root = project(
        {
            'src/probe/mod.py': 'VALUE = 1\n',
            'pyproject.toml': '[project]\nname = "probe"\n',
            'uv.lock': 'version = 1\n',
        }
    )
    hits = run_check(LOCKFILE, root)
    assert '<timestamp>' in hits[0]['evidence']
    assert '2026-08-15' not in hits[0]['evidence']


LOCK_PROJECT = {
    'pyproject.toml': '[project]\nname = "probe"\n',
    'src/probe/mod.py': 'VALUE = 1\n',
    'uv.lock': 'version = 1\n',
}
USER_EXCLUDE_NEWER = (
    'Resolving despite existing lockfile due to addition of global exclude newer 2026-10-18T09:17:10Z\n'
    'error: The lockfile at `uv.lock` needs to be updated, but `--check` was provided.\n'
)


class LockResult:
    def __init__(self, returncode: int, stderr: str = '') -> None:
        self.returncode = returncode
        self.stdout = ''
        self.stderr = stderr


def recording_run(results: list[LockResult], calls: list[dict[str, object]]) -> collections.abc.Callable[..., LockResult]:
    def fake_run(*args: object, **kwargs: object) -> LockResult:
        calls.append(kwargs)
        return results[len(calls) - 1]

    return fake_run


def test_drift_from_a_user_exclude_newer_alone_is_not_reported(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A user-level `exclude-newer` the lock was not made with re-resolves it on
    one machine only; CI, without that config, sees no drift."""
    calls: list[dict[str, object]] = []
    monkeypatch.setenv('PROBE_VAR', 'kept')
    monkeypatch.setattr(subprocess, 'run', recording_run([LockResult(1, USER_EXCLUDE_NEWER), LockResult(0)], calls))
    assert run_check(LOCKFILE, project(LOCK_PROJECT)) == []
    assert len(calls) == 2
    assert 'env' not in calls[0]
    env = calls[1]['env']
    assert isinstance(env, dict)
    assert env['UV_NO_CONFIG'] == '1'
    assert env['PROBE_VAR'] == 'kept'


def test_a_lock_that_passes_is_checked_once_with_the_user_config(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lock made with the user's `exclude-newer` records it, so dropping the
    config for it would report drift."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(subprocess, 'run', recording_run([LockResult(0)], calls))
    assert run_check(LOCKFILE, project(LOCK_PROJECT)) == []
    assert len(calls) == 1
    assert 'env' not in calls[0]


def test_other_drift_is_reported_without_a_retry(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    stale = 'error: The lockfile at `uv.lock` needs to be updated, but `--check` was provided.\n'
    monkeypatch.setattr(subprocess, 'run', recording_run([LockResult(1, stale)], calls))
    hits = run_check(LOCKFILE, project(LOCK_PROJECT))
    assert len(hits) == 1
    assert 'out of date' in hits[0]['variant']
    assert len(calls) == 1


def test_drift_that_remains_without_the_user_config_is_reported(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    stale = 'error: The lockfile at `uv.lock` needs to be updated, but `--check` was provided.\n'
    monkeypatch.setattr(subprocess, 'run', recording_run([LockResult(1, USER_EXCLUDE_NEWER), LockResult(1, stale)], calls))
    hits = run_check(LOCKFILE, project(LOCK_PROJECT))
    assert len(hits) == 1
    assert 'out of date' in hits[0]['variant']


def test_a_missing_uv_is_a_hit(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError(2, 'No such file or directory', 'uv')

    monkeypatch.setattr(subprocess, 'run', missing)
    root = project(
        {
            'src/probe/mod.py': 'VALUE = 1\n',
            'pyproject.toml': '[project]\nname = "probe"\n',
            'uv.lock': 'version = 1\n',
        }
    )
    hits = run_check(LOCKFILE, root)
    assert len(hits) == 1
    assert hits[0]['rule'] == 'lockfile-drift'
    assert 'uv' in hits[0]['variant']
