"""Tests for the checks of the `ruff` rule."""

import collections.abc
import pathlib
import subprocess

import pytest

import auditor.core
import auditor.sweep
import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

RUFF = auditor.testing.load_check(__file__)


def require_ruff() -> None:
    try:
        subprocess.run(['ruff', '--version'], capture_output=True, check=False)
    except FileNotFoundError:
        pytest.skip('ruff is not installed')


def test_a_lint_error_is_reported_with_its_ruff_code(project: Builder, run_check: Runner) -> None:
    require_ruff()
    root = project({'src/probe/mod.py': 'import os\n'})
    hits = [hit for hit in run_check(RUFF, root) if hit['rule'] == 'ruff']
    assert 'F401' in {hit['variant'] for hit in hits}
    unused = [hit for hit in hits if hit['variant'] == 'F401']
    assert unused[0]['path'] == 'src/probe/mod.py'
    assert unused[0]['line'] == 1


def test_clean_source_produces_no_ruff_hits(project: Builder, run_check: Runner) -> None:
    require_ruff()
    root = project({'src/probe/mod.py': 'VALUE = 1\n'})
    assert [hit for hit in run_check(RUFF, root) if hit['rule'] == 'ruff'] == []


def test_an_unformatted_file_is_reported_at_its_path_and_line(project: Builder, run_check: Runner) -> None:
    """The `ruff format --check` half reports each file it would reformat, by path."""
    require_ruff()
    root = project({'src/probe/mod.py': 'def f( a ):\n    return   a\n', 'src/probe/ok.py': 'VALUE = 1\n'})
    hits = [hit for hit in run_check(RUFF, root) if hit['variant'] == 'ruff-format']
    assert [hit['path'] for hit in hits] == ['src/probe/mod.py']
    assert hits[0]['line'] == 1
    assert hits[0]['evidence'] == 'File would be reformatted'


# Captured from `ruff format --check --output-format=json` (ruff 0.17.4, the pinned version) on 2026-11-22.
FORMAT_JSON = '[{"cell": null, "code": "unformatted", "end_location": {"column": 13, "row": 2}, "filename": "{root}/src/probe/mod.py", "fix": null, "location": {"column": 7, "row": 1}, "message": "File would be reformatted", "name": "unformatted", "noqa_row": null, "severity": "error", "url": null}]'


def test_format_output_from_the_pinned_ruff_is_parsed(project: Builder, run_check: Runner, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'src/probe/mod.py': 'VALUE = 1\n'})

    def fake(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if cmd[1] == 'format':
            return subprocess.CompletedProcess(cmd, 1, FORMAT_JSON.replace('{root}', str(root)), '')
        return subprocess.CompletedProcess(cmd, 0, '[]', '')

    monkeypatch.setattr(subprocess, 'run', fake)
    hits = run_check(RUFF, root)
    assert [(hit['variant'], hit['path'], hit['line']) for hit in hits] == [('ruff-format', 'src/probe/mod.py', 1)]


def test_format_output_that_is_not_json_is_a_hit(project: Builder, run_check: Runner, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'src/probe/mod.py': 'VALUE = 1\n'})

    def fake(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if cmd[1] == 'format':
            return subprocess.CompletedProcess(cmd, 1, 'Would reformat: src/probe/mod.py', '')
        return subprocess.CompletedProcess(cmd, 0, '[]', '')

    monkeypatch.setattr(subprocess, 'run', fake)
    assert [hit['variant'] for hit in run_check(RUFF, root)] == ['ruff-format-parse-error']


def test_a_missing_ruff_is_reported_rather_than_passing_silently(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A check that cannot run has not answered its question."""

    def missing(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError('ruff')

    monkeypatch.setattr(subprocess, 'run', missing)
    root = project({'src/probe/mod.py': 'VALUE = 1\n'})
    hits = run_check(RUFF, root)
    assert {hit['variant'] for hit in hits} == {'ruff-check', 'ruff-format'}
    assert all(hit['evidence'] == 'ruff not installed' for hit in hits)


def test_a_ruff_that_cannot_be_executed_gets_the_same_report(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def denied(*args: object, **kwargs: object) -> None:
        raise PermissionError('ruff')

    monkeypatch.setattr(subprocess, 'run', denied)
    root = project({'src/probe/mod.py': 'VALUE = 1\n'})
    hits = run_check(RUFF, root)
    assert {hit['variant'] for hit in hits} == {'ruff-check', 'ruff-format'}
