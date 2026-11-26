"""Tests for bin/install-claude.sh, the wrapper around the shared installer.

The installer itself (linking, the settings merge) is tested in its own
repository; these check only what this repository passes it.
"""

import json
import os
import pathlib
import re
import shutil
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
WRAPPER = REPO / 'bin' / 'install-claude.sh'
STOP_HOOK = 'hooks.Stop[auditme-stop.sh]={"hooks":[{"type":"command","command":"bash \\"$HOME/.claude/hooks/auditme-stop.sh\\""}]}'
START_HOOK = 'hooks.SessionStart[auditme-standards.sh]={"hooks":[{"type":"command","command":"bash \\"$HOME/.claude/hooks/auditme-standards.sh\\""}]}'


def write_recorder(path: pathlib.Path, record: pathlib.Path, label: str) -> None:
    """An executable that appends its label and arguments, as one JSON line, to `record`."""
    path.write_text(f'#!/usr/bin/env python3\nimport json, sys\nopen({str(record)!r}, "a").write(json.dumps([{label!r}, *sys.argv[1:]]) + "\\n")\n')
    path.chmod(0o755)


def run_with_stubs(tmp_path: pathlib.Path, *args: str) -> list[list[str]]:
    """Run the wrapper with uv and uvx stubs that record their calls, and HOME in tmp_path."""
    stub_dir = tmp_path / 'bin'
    stub_dir.mkdir()
    record = tmp_path / 'calls.jsonl'
    write_recorder(stub_dir / 'uvx', record, 'uvx')
    write_recorder(stub_dir / 'uv', record, 'uv')
    env = {**os.environ, 'HOME': str(tmp_path / 'home'), 'PATH': f'{stub_dir}{os.pathsep}{os.environ["PATH"]}'}
    subprocess.run(['bash', str(WRAPPER), *args], check=True, env=env)
    return [json.loads(line) for line in record.read_text().splitlines()]


def run_with_stub_uvx(tmp_path: pathlib.Path, *args: str) -> list[str]:
    """The arguments the wrapper passed to uvx."""
    calls = run_with_stubs(tmp_path, *args)
    return next(call[1:] for call in calls if call[0] == 'uvx')


def test_the_wrapper_installs_the_tool_before_the_installer(tmp_path):
    calls = run_with_stubs(tmp_path)
    assert [call[0] for call in calls] == ['uv', 'uvx']
    assert calls[0] == ['uv', 'tool', 'install', '--editable', str(REPO)]


def test_the_wrapper_records_the_source_git_directory(tmp_path):
    run_with_stubs(tmp_path)
    expected = subprocess.run(
        ['git', '-C', str(REPO), 'rev-parse', '--path-format=absolute', '--git-common-dir'],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert (tmp_path / 'home' / '.claude' / 'auditor-source').read_text() == expected


def test_the_wrapper_passes_the_pinned_installer_and_this_repository(tmp_path):
    argv = run_with_stub_uvx(tmp_path)
    assert argv[0] == '--from'
    assert re.fullmatch(r'git\+ssh://git@github\.com/bnomis/install-in-claude\.git@[0-9a-f]{40}', argv[1])
    assert argv[2:] == ['install-in-claude', '--source', str(REPO / 'claude'), '--append', STOP_HOOK, '--append', START_HOOK]


def test_the_stop_hook_value_is_the_registered_command(tmp_path):
    argv = run_with_stub_uvx(tmp_path)
    value = json.loads(argv[argv.index('--append') + 1].split('=', 1)[1])
    assert value == {'hooks': [{'type': 'command', 'command': 'bash "$HOME/.claude/hooks/auditme-stop.sh"'}]}


def test_the_session_start_hook_value_is_the_registered_command(tmp_path):
    argv = run_with_stub_uvx(tmp_path)
    value = json.loads(argv[argv.index(START_HOOK)].split('=', 1)[1])
    assert value == {'hooks': [{'type': 'command', 'command': 'bash "$HOME/.claude/hooks/auditme-standards.sh"'}]}


def test_extra_arguments_pass_through(tmp_path):
    argv = run_with_stub_uvx(tmp_path, '--dry-run', '--target', '/x')
    assert argv[-3:] == ['--dry-run', '--target', '/x']


def test_the_real_installer_links_the_files_and_registers_the_hook(tmp_path):
    """Runs the pinned installer for real; offline, so it needs it in the uv cache."""
    if shutil.which('uvx') is None:
        pytest.skip('uvx not installed')
    home = tmp_path / 'home'
    home.mkdir()
    env = {**os.environ, 'HOME': str(home), 'UV_OFFLINE': '1'}
    result = subprocess.run(['bash', str(WRAPPER)], env=env, capture_output=True, text=True, check=False)
    if result.returncode != 0 and 'offline' in (result.stdout + result.stderr).lower():
        pytest.skip('the pinned installer is not in the uv cache and the test runs with no network')
    assert result.returncode == 0, result.stderr
    claude = home / '.claude'
    assert (claude / 'hooks' / 'auditme-stop.sh').resolve() == (REPO / 'claude' / 'hooks' / 'auditme-stop.sh').resolve()
    assert (claude / 'skills' / 'auditme').resolve() == (REPO / 'claude' / 'skills' / 'auditme').resolve()
    settings = json.loads((claude / 'settings.json').read_text())
    assert settings['hooks']['Stop'][0]['hooks'] == [{'type': 'command', 'command': 'bash "$HOME/.claude/hooks/auditme-stop.sh"'}]
