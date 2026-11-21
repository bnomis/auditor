"""Tests for claude/hooks/auditme-stop.sh, run against a temporary HOME."""

import json
import os
import pathlib
import shutil
import subprocess

import pytest

HOOK = pathlib.Path(__file__).resolve().parent.parent / 'claude' / 'hooks' / 'auditme-stop.sh'
REPORT = 'src/a.py:3  some-rule\n'

pytestmark = pytest.mark.skipif(shutil.which('jq') is None, reason='jq not installed')


def make_home(tmp_path: pathlib.Path, exit_code: int) -> pathlib.Path:
    home = tmp_path / 'home'
    checks = home / '.claude' / 'skills' / 'auditme' / 'checks'
    checks.mkdir(parents=True)
    (checks / 'changed.py').write_text(f"import sys\nprint({REPORT!r}, end='')\nsys.exit({exit_code})\n")
    return home


def make_repo(tmp_path: pathlib.Path, opted_in: bool) -> pathlib.Path:
    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    if opted_in:
        (repo / '.pre-commit-config.yaml').write_text('repos:\n  - hooks:\n      - id: auditme-changed\n')
    return repo


def run(home: pathlib.Path, cwd: pathlib.Path, payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['bash', str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd,
        env={'HOME': str(home), 'PATH': os.environ['PATH']},
        check=False,
    )


def test_blocks_with_runner_text(tmp_path: pathlib.Path) -> None:
    result = run(make_home(tmp_path, 1), make_repo(tmp_path, True), {})
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision['decision'] == 'block'
    assert decision['reason'] == REPORT.rstrip('\n')


def test_passes_when_stop_hook_active(tmp_path: pathlib.Path) -> None:
    result = run(make_home(tmp_path, 1), make_repo(tmp_path, True), {'stop_hook_active': True})
    assert (result.returncode, result.stdout) == (0, '')


def test_silent_when_not_opted_in(tmp_path: pathlib.Path) -> None:
    result = run(make_home(tmp_path, 1), make_repo(tmp_path, False), {})
    assert (result.returncode, result.stdout) == (0, '')


def test_silent_outside_a_repository(tmp_path: pathlib.Path) -> None:
    outside = tmp_path / 'plain'
    outside.mkdir()
    result = run(make_home(tmp_path, 1), outside, {})
    assert (result.returncode, result.stdout) == (0, '')


def test_silent_when_runner_passes(tmp_path: pathlib.Path) -> None:
    result = run(make_home(tmp_path, 0), make_repo(tmp_path, True), {})
    assert (result.returncode, result.stdout) == (0, '')


def checker_path(home: pathlib.Path) -> pathlib.Path:
    return home / '.claude' / 'skills' / 'auditme' / 'checks' / 'changed.py'


def assert_missing_checker_block(result: subprocess.CompletedProcess[str], home: pathlib.Path) -> None:
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision['decision'] == 'block'
    assert str(checker_path(home)) in decision['reason']
    assert 'bin/install-claude.sh' in decision['reason']


def test_blocks_when_checker_missing(tmp_path: pathlib.Path) -> None:
    home = tmp_path / 'home'
    home.mkdir()
    result = run(home, make_repo(tmp_path, True), {})
    assert_missing_checker_block(result, home)


def test_blocks_when_checker_link_dangles(tmp_path: pathlib.Path) -> None:
    home = tmp_path / 'home'
    checker_path(home).parent.mkdir(parents=True)
    checker_path(home).symlink_to(tmp_path / 'gone' / 'changed.py')
    result = run(home, make_repo(tmp_path, True), {})
    assert_missing_checker_block(result, home)


def test_blocks_when_checker_cannot_run(tmp_path: pathlib.Path) -> None:
    result = run(make_home(tmp_path, 2), make_repo(tmp_path, True), {})
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision['decision'] == 'block'
    assert 'exit 2' in decision['reason']
    assert REPORT.rstrip('\n') in decision['reason']


def test_missing_checker_passes_when_stop_hook_active(tmp_path: pathlib.Path) -> None:
    home = tmp_path / 'home'
    home.mkdir()
    result = run(home, make_repo(tmp_path, True), {'stop_hook_active': True})
    assert (result.returncode, result.stdout) == (0, '')
