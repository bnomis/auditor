"""Tests for claude/hooks/auditme-stop.sh, run against a temporary HOME and a PATH of stubs."""

import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

import auditor.rulesrepo

HOOK = pathlib.Path(__file__).resolve().parent.parent / 'claude' / 'hooks' / 'auditme-stop.sh'
REPORT = 'src/a.py:3  some-rule\n'
OWN_REPORT = 'src/auditor/core.py:9  own-rule\n'
MISSING = "The auditor CLI is not installed: run 'uv tool install <source>' (see docs/setup.md)."
BASH = shutil.which('bash')
TOOLS = ('cat', 'git', 'grep', 'jq')

pytestmark = pytest.mark.skipif(shutil.which('jq') is None, reason='jq not installed')


def write_stub(path: pathlib.Path, report: str, exit_code: int, record: pathlib.Path | None = None) -> None:
    """An executable that prints `report` and exits `exit_code`, noting its arguments in `record`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    note = f'printf "%s\\n" "$*" > {record}\n' if record else ''
    path.write_text(f'#!/bin/sh\n{note}printf "%b" {report!r}\nexit {exit_code}\n')
    path.chmod(0o755)


def make_tools(tmp_path: pathlib.Path) -> pathlib.Path:
    """A PATH directory holding only what the hook needs, so no installed `auditor` is on it."""
    tools = tmp_path / 'tools'
    # auditme: accept[build-name-has-side-effect] a fixture builder: making the files is its purpose
    tools.mkdir()
    for name in TOOLS:
        found = shutil.which(name)
        assert found
        (tools / name).symlink_to(found)
    return tools


# auditme: accept[paired-sibling-helpers] each hook's test file stays self-contained, as the tests directory has no shared module
def make_repo(tmp_path: pathlib.Path, opted_in: bool) -> pathlib.Path:
    repo = tmp_path / 'repo'
    # auditme: accept[build-name-has-side-effect] a fixture builder: making the files is its purpose
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    if opted_in:
        (repo / '.pre-commit-config.yaml').write_text('repos:\n  - hooks:\n      - id: auditme-changed\n')
    return repo


def run(tmp_path: pathlib.Path, cwd: pathlib.Path, payload: dict[str, object], path: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(BASH), str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd,
        env={
            'HOME': str(tmp_path / 'home'),
            'PATH': path or str(tmp_path / 'tools'),
            auditor.rulesrepo.RULES_PATH_VARIABLE: os.environ[auditor.rulesrepo.RULES_PATH_VARIABLE],
        },
        check=False,
    )


def with_auditor(tmp_path: pathlib.Path, exit_code: int) -> None:
    make_tools(tmp_path)
    write_stub(tmp_path / 'tools' / 'auditor', REPORT, exit_code)


def test_blocks_with_runner_text(tmp_path: pathlib.Path) -> None:
    with_auditor(tmp_path, 1)
    result = run(tmp_path, make_repo(tmp_path, True), {})
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision['decision'] == 'block'
    assert decision['reason'] == REPORT.rstrip('\n')


def test_runs_auditor_changed_from_path(tmp_path: pathlib.Path) -> None:
    make_tools(tmp_path)
    record = tmp_path / 'argv.txt'
    write_stub(tmp_path / 'tools' / 'auditor', REPORT, 0, record)
    result = run(tmp_path, make_repo(tmp_path, True), {})
    assert (result.returncode, result.stdout) == (0, '')
    assert record.read_text() == 'changed\n'


def test_passes_when_stop_hook_active(tmp_path: pathlib.Path) -> None:
    with_auditor(tmp_path, 1)
    result = run(tmp_path, make_repo(tmp_path, True), {'stop_hook_active': True})
    assert (result.returncode, result.stdout) == (0, '')


def test_silent_when_not_opted_in(tmp_path: pathlib.Path) -> None:
    with_auditor(tmp_path, 1)
    result = run(tmp_path, make_repo(tmp_path, False), {})
    assert (result.returncode, result.stdout) == (0, '')


def test_silent_outside_a_repository(tmp_path: pathlib.Path) -> None:
    with_auditor(tmp_path, 1)
    outside = tmp_path / 'plain'
    outside.mkdir()
    result = run(tmp_path, outside, {})
    assert (result.returncode, result.stdout) == (0, '')


def test_silent_when_runner_passes(tmp_path: pathlib.Path) -> None:
    with_auditor(tmp_path, 0)
    result = run(tmp_path, make_repo(tmp_path, True), {})
    assert (result.returncode, result.stdout) == (0, '')


def test_blocks_when_auditor_is_not_on_path(tmp_path: pathlib.Path) -> None:
    make_tools(tmp_path)
    result = run(tmp_path, make_repo(tmp_path, True), {})
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision['decision'] == 'block'
    assert decision['reason'] == MISSING


def test_blocks_when_checker_cannot_run(tmp_path: pathlib.Path) -> None:
    with_auditor(tmp_path, 2)
    result = run(tmp_path, make_repo(tmp_path, True), {})
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision['decision'] == 'block'
    assert 'exit 2' in decision['reason']
    assert REPORT.rstrip('\n') in decision['reason']


def test_missing_auditor_passes_when_stop_hook_active(tmp_path: pathlib.Path) -> None:
    make_tools(tmp_path)
    result = run(tmp_path, make_repo(tmp_path, True), {'stop_hook_active': True})
    assert (result.returncode, result.stdout) == (0, '')


def git(repo: pathlib.Path, *args: str) -> str:
    result = subprocess.run(
        ['git', '-C', str(repo), '-c', 'core.hooksPath=/dev/null', '-c', 'user.name=t', '-c', 'user.email=t@t', *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def make_source_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """An opted-in repository holding src/auditor/cli.py, recorded as the installed tool's source."""
    repo = make_repo(tmp_path, True)
    # auditme: accept[build-name-has-side-effect] a fixture builder: making the files is its purpose
    (repo / 'src' / 'auditor').mkdir(parents=True)
    (repo / 'src' / 'auditor' / 'cli.py').write_text('')
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', 'init')
    record_source(tmp_path, repo)
    return repo


def record_source(tmp_path: pathlib.Path, repo: pathlib.Path) -> None:
    claude = tmp_path / 'home' / '.claude'
    claude.mkdir(parents=True, exist_ok=True)
    (claude / 'auditor-source').write_text(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir').strip() + '\n')


def test_worktree_of_the_source_repository_runs_its_own_code(tmp_path: pathlib.Path) -> None:
    make_tools(tmp_path)
    record = tmp_path / 'argv.txt'
    write_stub(tmp_path / 'tools' / 'uv', OWN_REPORT, 1, record)
    write_stub(tmp_path / 'tools' / 'auditor', REPORT, 0)
    repo = make_source_repo(tmp_path)
    worktree = tmp_path / 'worktree'
    git(repo, 'worktree', 'add', '-q', str(worktree))
    decision = json.loads(run(tmp_path, worktree, {}).stdout)
    assert decision['decision'] == 'block'
    assert decision['reason'] == OWN_REPORT.rstrip('\n')
    assert record.read_text() == f'run --project {worktree.resolve()} auditor changed\n'


def test_another_repository_with_src_auditor_never_runs_its_own_code(tmp_path: pathlib.Path) -> None:
    make_tools(tmp_path)
    record = tmp_path / 'argv.txt'
    write_stub(tmp_path / 'tools' / 'uv', OWN_REPORT, 1, record)
    write_stub(tmp_path / 'tools' / 'auditor', REPORT, 0)
    source = tmp_path / 'source'
    source.mkdir()
    # auditme: accept[build-name-has-side-effect] a fixture builder: making the files is its purpose
    subprocess.run(['git', 'init', '-q', str(source)], check=True)
    record_source(tmp_path, source)
    other = make_source_repo_without_record(tmp_path)
    result = run(tmp_path, other, {})
    assert (result.returncode, result.stdout) == (0, '')
    assert not record.exists()


def make_source_repo_without_record(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = make_repo(tmp_path, True)
    # auditme: accept[build-name-has-side-effect] a fixture builder: making the files is its purpose
    (repo / 'src' / 'auditor').mkdir(parents=True)
    (repo / 'src' / 'auditor' / 'cli.py').write_text('')
    return repo


FUTURE_IMPORT = 'from __future__ import annotations\n'
REAL_PATH = os.pathsep.join([str(pathlib.Path(sys.executable).parent), os.environ['PATH']])


def make_real_repo(tmp_path: pathlib.Path, new_source: str) -> pathlib.Path:
    """An opted-in repository on branch `feature`, one commit after `main`, adding src/pkg/new.py."""
    repo = tmp_path / 'project'
    # auditme: accept[build-name-has-side-effect] a fixture builder: making the files is its purpose
    repo.mkdir()
    git(repo, 'init', '-q', '-b', 'main')
    (repo / '.pre-commit-config.yaml').write_text('repos:\n  - hooks:\n      - id: auditme-changed\n')
    (repo / 'src' / 'pkg').mkdir(parents=True)
    (repo / 'src' / 'pkg' / '__init__.py').write_text('')
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', 'base')
    git(repo, 'checkout', '-q', '-b', 'feature')
    (repo / 'src' / 'pkg' / 'new.py').write_text(new_source)
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', 'add new')
    return repo


def test_real_checker_blocks_on_an_unaccepted_hit(tmp_path: pathlib.Path) -> None:
    result = run(tmp_path, make_real_repo(tmp_path, FUTURE_IMPORT), {}, REAL_PATH)
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision['decision'] == 'block'
    assert 'src/pkg/new.py:1  future-annotations' in decision['reason']


def test_real_checker_is_silent_with_no_hit(tmp_path: pathlib.Path) -> None:
    result = run(tmp_path, make_real_repo(tmp_path, 'value = 1\n'), {}, REAL_PATH)
    assert (result.returncode, result.stdout) == (0, '')
