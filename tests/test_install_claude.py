"""Tests for bin/install-claude.py's Stop hook registration."""

import importlib.util
import json
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / 'bin' / 'install-claude.py'


@pytest.fixture
def installer():
    spec = importlib.util.spec_from_file_location('install_claude', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def settings(tmp_path):
    return tmp_path / 'settings.json'


def stop_commands(path):
    data = json.loads(path.read_text())
    return [h['command'] for e in data['hooks']['Stop'] for h in e['hooks']]


def test_creates_file_when_absent(installer, settings):
    installer.register_stop_hook(None, settings)
    assert stop_commands(settings) == [installer.STOP_HOOK_COMMAND]
    assert not settings.with_name('settings.json.orig').exists()


def test_added_once_on_two_runs(installer, settings):
    installer.register_stop_hook(None, settings)
    installer.register_stop_hook(None, settings)
    assert stop_commands(settings) == [installer.STOP_HOOK_COMMAND]


def test_keeps_other_keys_and_hooks(installer, settings):
    original = {
        'model': 'x',
        'permissions': {'allow': ['Bash(ls)']},
        'hooks': {
            'Stop': [{'hooks': [{'type': 'command', 'command': 'other-stop'}]}],
            'PreToolUse': [{'matcher': 'Bash', 'hooks': []}],
        },
    }
    settings.write_text(json.dumps(original))
    installer.register_stop_hook(None, settings)
    data = json.loads(settings.read_text())
    assert data['model'] == 'x'
    assert data['permissions'] == original['permissions']
    assert data['hooks']['PreToolUse'] == original['hooks']['PreToolUse']
    assert stop_commands(settings) == ['other-stop', installer.STOP_HOOK_COMMAND]


def test_existing_registration_is_not_duplicated(installer, settings):
    command = 'bash /elsewhere/auditme-stop.sh'
    original = json.dumps({'hooks': {'Stop': [{'hooks': [{'command': command}]}]}})
    settings.write_text(original)
    installer.register_stop_hook(None, settings)
    assert settings.read_text() == original
    assert not settings.with_name('settings.json.orig').exists()


@pytest.mark.parametrize('content', ['{not json', '[1, 2]'])
def test_invalid_settings_refused(installer, settings, content):
    settings.write_text(content)
    with pytest.raises(installer.SettingsError, match='settings.json'):
        installer.register_stop_hook(None, settings)
    assert settings.read_text() == content
    assert not settings.with_name('settings.json.orig').exists()


def test_orig_written_once(installer, settings):
    first = json.dumps({'model': 'x'})
    settings.write_text(first)
    orig = settings.with_name('settings.json.orig')
    installer.register_stop_hook(None, settings)
    assert orig.read_text() == first

    data = json.loads(settings.read_text())
    data['hooks']['Stop'] = []
    settings.write_text(json.dumps(data))
    installer.register_stop_hook(None, settings)
    assert orig.read_text() == first


def test_full_install_into_temporary_home(installer, tmp_path, monkeypatch):
    home = tmp_path.resolve()
    monkeypatch.setenv('HOME', str(home))
    (home / '.claude').mkdir()
    installer.install_claude(None)
    installer.install_claude(None)
    assert stop_commands(home / '.claude' / 'settings.json') == [installer.STOP_HOOK_COMMAND]
    assert (home / '.claude' / 'hooks' / 'auditme-stop.sh').exists()


def test_file_mode_kept(installer, settings):
    settings.write_text('{}')
    settings.chmod(0o600)
    installer.register_stop_hook(None, settings)
    assert settings.stat().st_mode & 0o777 == 0o600
    assert list(settings.parent.glob('settings.json.*')) == [settings.with_name('settings.json.orig')]


def test_install_into_home_without_claude_dir(installer, tmp_path, monkeypatch):
    home = tmp_path.resolve()
    monkeypatch.setenv('HOME', str(home))
    installer.install_claude(None)
    assert stop_commands(home / '.claude' / 'settings.json') == [installer.STOP_HOOK_COMMAND]
    assert (home / '.claude' / 'skills').is_dir()


def test_main_exits_with_the_settings_error(installer, tmp_path, monkeypatch, capsys):
    home = tmp_path.resolve()
    monkeypatch.setenv('HOME', str(home))
    (home / '.claude').mkdir()
    (home / '.claude' / 'settings.json').write_text('{not json')
    with pytest.raises(SystemExit) as exc:
        installer.main([])
    assert exc.value.code != 0
    assert 'settings.json is not valid JSON' in str(exc.value.code)
