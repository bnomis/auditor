import builtins
import pathlib
import shutil
import typing

import auditor.cli
import auditor.rulesrepo

if typing.TYPE_CHECKING:
    import pytest

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'


def run(monkeypatch: pytest.MonkeyPatch, root: pathlib.Path, *args: str) -> int:
    monkeypatch.setenv(auditor.rulesrepo.RULES_PATH_VARIABLE, str(root))
    return auditor.cli.main(['rules', 'test', *args])


def test_a_rules_own_test_passes_through_the_command(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(monkeypatch, FIXTURES / 'with-tests', '-p', 'no:cacheprovider') == 0
    assert '1 passed' in capsys.readouterr().out


def test_a_failing_rule_test_fails_the_command(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    root = tmp_path / 'repo'
    shutil.copytree(FIXTURES / 'with-tests', root)
    (root / 'rules' / 'a-check' / 'tests' / 'test_a_check.py').write_text('def test_fails():\n    assert False\n', encoding='utf-8')
    assert run(monkeypatch, root, '-p', 'no:cacheprovider') == 1


def test_without_pytest_the_command_names_the_extra(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    real_import = builtins.__import__

    def refuse(name: str, *args: object, **kwargs: object) -> object:
        if name == 'pytest':
            raise ImportError(name)
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, '__import__', refuse)
    assert run(monkeypatch, FIXTURES / 'with-tests') == 2
    captured = capsys.readouterr()
    assert 'auditor[test]' in captured.err
    assert captured.out == ''
