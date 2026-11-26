"""Tests for the project-hygiene helpers the rules share: spec file discovery and the ruff lookup."""

import collections.abc
import os
import pathlib
import sys

import pytest

import auditor.api
import auditor.core
import auditor.sweep

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]


def test_spec_markdown_files_skip_records_and_hidden_directories(tmp_path: pathlib.Path) -> None:
    for relative in ('README.md', 'docs/spec.md', 'tasks/list.md', 'audit-reviews/review.md', '.claude/worktrees/w/spec.md', 'docs/.hidden/x.md'):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# x\n', encoding='utf-8')
    found = auditor.api.spec_markdown_files(tmp_path)
    assert [path.relative_to(tmp_path).as_posix() for path in found] == ['README.md', 'docs/spec.md']


def test_ruff_executable_is_resolved_once_per_run(project: Builder, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'.venv/bin/ruff': '#!/bin/sh\n'})
    auditor.core.clear_source_cache()
    calls: list[object] = []
    real = os.access

    def counting(path: object, mode: int) -> bool:
        calls.append(path)
        return real(path, mode)  # type: ignore[arg-type]

    monkeypatch.setattr(os, 'access', counting)
    first = auditor.api.ruff_executable(root)
    second = auditor.api.ruff_executable(root)
    assert first == second
    assert len(calls) == 1


def make_executable(path: pathlib.Path) -> pathlib.Path:
    # auditme: accept[build-name-has-side-effect] a fixture builder: making the files is its purpose
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('#!/bin/sh\n')
    path.chmod(0o755)
    return path


def test_auditme_ruff_wins_over_the_project_venv(project: Builder, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    root = project({'.venv/bin/ruff': '#!/bin/sh\n'})
    (root / '.venv' / 'bin' / 'ruff').chmod(0o755)
    shared = make_executable(tmp_path / 'shared' / 'ruff')
    monkeypatch.setenv('AUDITME_RUFF', str(shared))
    auditor.core.clear_source_cache()
    assert auditor.api.ruff_executable(root) == (str(shared), 'AUDITME_RUFF')


def unset_or_empty(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv('AUDITME_RUFF', raising=False)
    else:
        monkeypatch.setenv('AUDITME_RUFF', value)
    auditor.core.clear_source_cache()


@pytest.mark.parametrize('value', [None, ''])
def test_unset_or_empty_auditme_ruff_falls_through_to_the_venv(project: Builder, monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    root = project({'.venv/bin/ruff': '#!/bin/sh\n'})
    (root / '.venv' / 'bin' / 'ruff').chmod(0o755)
    unset_or_empty(monkeypatch, value)
    assert auditor.api.ruff_executable(root)[1] == '.venv/bin/ruff'


@pytest.mark.parametrize('value', [None, ''])
def test_unset_or_empty_auditme_ruff_falls_through_to_path(project: Builder, monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    root = project({'src/probe/mod.py': 'x = 1\n'})
    unset_or_empty(monkeypatch, value)
    assert auditor.api.ruff_executable(root) == ('ruff', 'ruff on PATH')


@pytest.mark.parametrize('kind', ['missing', 'not-executable'])
def test_an_invalid_auditme_ruff_exits_2_before_anything_is_printed(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: pathlib.Path,
    kind: str,
) -> None:
    root = project({'src/probe/mod.py': 'x = 1\n'})
    target = tmp_path / 'ruff'
    if kind == 'not-executable':
        target.write_text('#!/bin/sh\n')
        target.chmod(0o644)
    monkeypatch.setenv('AUDITME_RUFF', str(target))
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])
    assert auditor.sweep.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err.strip() == f'ERROR: AUDITME_RUFF={target} is not an executable file'
