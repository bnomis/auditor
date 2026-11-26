"""With `AUDITOR_RULES_PATH` unset, the runner has no rules to fall back on and says so."""

import typing

import pytest

import auditor.cli
import auditor.rulesrepo

if typing.TYPE_CHECKING:
    import pathlib


@pytest.mark.parametrize(
    'command',
    [
        ['check'],
        ['phaseb', 'candidates', '--question', 'Q1'],
        ['rules', 'list'],
    ],
)
def test_every_command_exits_2_with_the_unset_variable_message(
    command: list[str], tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(auditor.rulesrepo.RULES_PATH_VARIABLE, raising=False)
    argv = [*command, str(tmp_path)] if command[0] != 'rules' else command
    assert auditor.cli.main(argv) == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert f'{auditor.rulesrepo.RULES_PATH_VARIABLE} is not set: create a rules repository' in captured.err
