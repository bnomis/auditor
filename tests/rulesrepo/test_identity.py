import json
import pathlib
import shutil
import subprocess

import pytest

import auditor.cli
import auditor.core
import auditor.rulesrepo

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'


def git(root: pathlib.Path, *args: str) -> str:
    return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / 'rules-repo'
    shutil.copytree(FIXTURES / 'sweep-ok', root)
    git(root, 'init', '-q')
    git(root, 'config', 'user.email', 'test@example.com')
    git(root, 'config', 'user.name', 'Test')
    git(root, 'add', '.')
    git(root, 'commit', '-q', '-m', 'initial')
    return root


def run(monkeypatch: pytest.MonkeyPatch, root: pathlib.Path, *args: str) -> int:
    monkeypatch.setenv(auditor.rulesrepo.RULES_PATH_VARIABLE, str(root))
    auditor.core.clear_source_cache()
    return auditor.cli.main(['rules', 'identity', *args])


def test_identity_prints_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], repo: pathlib.Path) -> None:
    assert run(monkeypatch, repo) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed['api'] == '1.0'
    assert printed['rules_path'] == str(repo.resolve())
    assert printed['rules_dirty'] is False
    assert len(printed['rules_commit']) == 40
    assert len(printed['rules_digest']) == 64
    assert printed['runner']


def test_expect_passes_on_same_identity(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], repo: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    run(monkeypatch, repo)
    expected = tmp_path / 'expected.json'
    expected.write_text(capsys.readouterr().out, encoding='utf-8')
    assert run(monkeypatch, repo, '--expect', str(expected)) == 0


def test_expect_fails_after_a_commit(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    run(monkeypatch, repo)
    expected = tmp_path / 'expected.json'
    expected.write_text(capsys.readouterr().out, encoding='utf-8')
    rule_md = next((repo / 'rules').glob('*/rule.md'))
    rule_md.write_text(rule_md.read_text(encoding='utf-8') + '\nMore.\n', encoding='utf-8')
    git(repo, 'commit', '-q', '-am', 'change')
    assert run(monkeypatch, repo, '--expect', str(expected)) == 1
    out = capsys.readouterr().out
    assert 'rules_commit' in out
    assert 'rules_digest' in out


def test_dirty_after_uncommitted_edit(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], repo: pathlib.Path) -> None:
    rule_md = next((repo / 'rules').glob('*/rule.md'))
    rule_md.write_text(rule_md.read_text(encoding='utf-8') + '\nMore.\n', encoding='utf-8')
    assert run(monkeypatch, repo) == 0
    assert json.loads(capsys.readouterr().out)['rules_dirty'] is True


def test_commit_is_null_outside_a_work_tree(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: pathlib.Path) -> None:
    root = tmp_path / 'plain'
    shutil.copytree(FIXTURES / 'sweep-ok', root)
    assert run(monkeypatch, root) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed['rules_commit'] is None
    assert printed['rules_dirty'] is False
    assert len(printed['rules_digest']) == 64
