import tomllib
import typing

import pytest

import auditor.cli
import auditor.rulesinit

if typing.TYPE_CHECKING:
    import pathlib

PACKS = tomllib.loads((auditor.rulesinit.catalogue_root() / 'packs.toml').read_text(encoding='utf-8'))['packs']


def selected(path: pathlib.Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        text = line.split('#', 1)[0].strip()
        if text:
            names.add(text)
    return names


def test_one_pack_is_uncommented_and_the_others_are_commented_out(tmp_path: pathlib.Path) -> None:
    path = auditor.rulesinit.write_selection(tmp_path / 'new', ['imports'])
    assert path == tmp_path / 'new' / 'selection.txt'
    assert selected(path) == set(PACKS['imports']['rules'])
    text = path.read_text(encoding='utf-8')
    assert f'## imports: {PACKS["imports"]["description"]}' in text
    other = PACKS['security']['rules'][0]
    assert any(line.startswith(f'# {other}') for line in text.splitlines())


def test_each_rule_line_ends_with_its_title(tmp_path: pathlib.Path) -> None:
    path = auditor.rulesinit.write_selection(tmp_path, ['imports'])
    assert any(line.startswith('d1  # ') for line in path.read_text(encoding='utf-8').splitlines())


def test_no_pack_selects_every_rule(tmp_path: pathlib.Path) -> None:
    path = auditor.rulesinit.write_selection(tmp_path, [])
    every = {name for pack in PACKS.values() for name in pack['rules']}
    assert selected(path) == every


def test_an_unknown_pack_fails_and_writes_nothing(tmp_path: pathlib.Path) -> None:
    with pytest.raises(auditor.rulesinit.RulesInitError, match=r"unknown pack 'nope': known packs are .*imports"):
        auditor.rulesinit.write_selection(tmp_path / 'new', ['nope'])
    assert not (tmp_path / 'new').exists()


@pytest.mark.parametrize('existing', ['rules', 'auditor-rules.toml'])
def test_a_destination_holding_a_repository_is_refused(tmp_path: pathlib.Path, existing: str) -> None:
    (tmp_path / existing).mkdir()
    with pytest.raises(auditor.rulesinit.RulesInitError, match='already exists'):
        auditor.rulesinit.write_selection(tmp_path, [])
    assert not (tmp_path / 'selection.txt').exists()


def test_init_command_prints_the_next_command(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert auditor.cli.main(['rules', 'init', str(tmp_path / 'r'), '--pack', 'imports']) == 0
    out = capsys.readouterr().out
    assert str(tmp_path / 'r' / 'selection.txt') in out
    assert f'auditor rules apply {tmp_path / "r"}' in out


def test_init_command_reports_an_error_with_exit_2(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert auditor.cli.main(['rules', 'init', str(tmp_path), '--pack', 'nope']) == 2
    captured = capsys.readouterr()
    assert captured.err.startswith("ERROR: unknown pack 'nope'")
    assert captured.out == ''


def test_packs_command_lists_name_count_and_description(capsys: pytest.CaptureFixture[str]) -> None:
    assert auditor.cli.main(['rules', 'packs']) == 0
    lines = capsys.readouterr().out.splitlines()
    assert f'imports\t{len(PACKS["imports"]["rules"])}\t{PACKS["imports"]["description"]}' in lines
    assert len(lines) == len(PACKS)
