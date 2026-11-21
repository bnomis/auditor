"""Tests for bin/install-claude.sh, the wrapper around the shared installer.

The installer itself (linking, the settings merge) is tested in its own
repository; these check only what this repository passes it.
"""

import json
import os
import pathlib
import re
import subprocess

REPO = pathlib.Path(__file__).resolve().parent.parent
WRAPPER = REPO / 'bin' / 'install-claude.sh'
STOP_HOOK = 'hooks.Stop[auditme-stop.sh]={"hooks":[{"type":"command","command":"bash \\"$HOME/.claude/hooks/auditme-stop.sh\\""}]}'


def run_with_stub_uvx(tmp_path: pathlib.Path, *args: str) -> list[str]:
    """Run the wrapper with a uvx that records its arguments instead of running."""
    stub_dir = tmp_path / 'bin'
    stub_dir.mkdir()
    record = tmp_path / 'argv.json'
    stub = stub_dir / 'uvx'
    stub.write_text(f'#!/usr/bin/env python3\nimport json, sys\nopen({str(record)!r}, "w").write(json.dumps(sys.argv[1:]))\n')
    stub.chmod(0o755)
    env = {**os.environ, 'PATH': f'{stub_dir}{os.pathsep}{os.environ["PATH"]}'}
    subprocess.run(['bash', str(WRAPPER), *args], check=True, env=env)
    return json.loads(record.read_text())


def test_the_wrapper_passes_the_pinned_installer_and_this_repository(tmp_path):
    argv = run_with_stub_uvx(tmp_path)
    assert argv[0] == '--from'
    assert re.fullmatch(r'git\+ssh://git@github\.com/bnomis/install-in-claude\.git@[0-9a-f]{40}', argv[1])
    assert argv[2:] == ['install-in-claude', '--source', str(REPO / 'claude'), '--append', STOP_HOOK]


def test_the_stop_hook_value_is_the_registered_command(tmp_path):
    argv = run_with_stub_uvx(tmp_path)
    value = json.loads(argv[argv.index('--append') + 1].split('=', 1)[1])
    assert value == {'hooks': [{'type': 'command', 'command': 'bash "$HOME/.claude/hooks/auditme-stop.sh"'}]}


def test_extra_arguments_pass_through(tmp_path):
    argv = run_with_stub_uvx(tmp_path, '--dry-run', '--target', '/x')
    assert argv[-3:] == ['--dry-run', '--target', '/x']
