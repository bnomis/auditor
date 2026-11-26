"""Tests for the `auditor` command, run as a subprocess of the installed entry point."""

import importlib.metadata
import pathlib
import subprocess
import sys

import auditor.sweep

AUDITOR = pathlib.Path(sys.executable).parent / 'auditor'


def run(*args: str | pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(AUDITOR), *map(str, args)], capture_output=True, text=True, check=False)


def test_version_prints_the_installed_version() -> None:
    result = run('--version')
    assert result.returncode == 0
    assert result.stdout == f'auditor {importlib.metadata.version("auditor")}\n'


def test_check_emits_the_lines_the_sweep_emits(project, capsys) -> None:
    root = project(
        {
            'src/probe/__init__.py': '__all__: list[str] = []\n',
            'src/probe/mod.py': 'import json\n\n\ndef parse(payload):\n    parsed = json.loads(payload)\n    usage = parsed.get("usage", {})\n    return usage.get("input_tokens", 0)\n',
        }
    )
    assert auditor.sweep.main([str(root)]) == 0
    expected = capsys.readouterr().out
    result = run('check', root)
    assert result.returncode == 0, result.stderr
    assert expected
    assert result.stdout == expected


def test_an_unknown_command_exits_2() -> None:
    result = run('no-such-command')
    assert result.returncode == 2
    assert 'unknown command' in result.stderr
