import hashlib
import subprocess
import tomllib
import typing

import pytest

import auditor.cli
import auditor.rulesinit

if typing.TYPE_CHECKING:
    import pathlib

CATALOGUE_RULES = auditor.rulesinit.catalogue_root() / 'rules'


def snapshot(root: pathlib.Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(root.rglob('*')) if path.is_file()}


def rule_with_standard() -> tuple[str, str]:
    for directory in sorted(path for path in CATALOGUE_RULES.iterdir() if path.is_dir()):
        meta = tomllib.loads((directory / 'rule.toml').read_text(encoding='utf-8'))
        if meta.get('standards'):
            return directory.name, meta['standards'][0]
    raise AssertionError('the catalogue has no rule that names a standard')


def write_selection(dest: pathlib.Path, *lines: str) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'selection.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def test_apply_copies_exactly_the_uncommented_names_with_their_tests(tmp_path: pathlib.Path) -> None:
    auditor.rulesinit.write_selection(tmp_path, ['imports'])
    copied = auditor.rulesinit.apply_selection(tmp_path)
    packs = auditor.rulesinit.read_packs()
    assert copied == sorted(packs['imports']['rules'])
    assert sorted(path.name for path in (tmp_path / 'rules').iterdir()) == copied
    with_tests = [name for name in copied if (CATALOGUE_RULES / name / 'tests').is_dir()]
    assert with_tests
    assert all((tmp_path / 'rules' / name / 'tests').is_dir() for name in with_tests)


def test_apply_writes_the_repository_files(tmp_path: pathlib.Path) -> None:
    auditor.rulesinit.write_selection(tmp_path, ['imports'])
    auditor.rulesinit.apply_selection(tmp_path)
    manifest = tomllib.loads((tmp_path / 'auditor-rules.toml').read_text(encoding='utf-8'))
    assert manifest['api'] == '1.0'
    assert set(manifest['source']) >= {'auditor', 'date'}
    assert (tmp_path / 'TODO.md').read_text(encoding='utf-8').startswith('# TODO')
    assert (tmp_path / 'DONE.md').read_text(encoding='utf-8').startswith('# DONE')
    assert 'AUDITOR_RULES_PATH' in (tmp_path / 'README.md').read_text(encoding='utf-8')
    assert '__pycache__/' in (tmp_path / '.gitignore').read_text(encoding='utf-8')
    assert (tmp_path / 'selection.txt').is_file()
    assert (tmp_path / '.git').is_dir()


def test_the_result_passes_check_and_pending(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest = tmp_path / 'new'
    auditor.rulesinit.write_selection(dest, [])
    assert auditor.cli.main(['rules', 'apply', str(dest)]) == 0
    monkeypatch.setenv('AUDITOR_RULES_PATH', str(dest))
    assert auditor.cli.main(['rules', 'check']) == 0
    assert auditor.cli.main(['rules', 'pending']) == 0


def test_apply_inside_a_work_tree_does_not_start_another(tmp_path: pathlib.Path) -> None:
    subprocess.run(['git', 'init', '--quiet'], cwd=tmp_path, check=True)
    dest = tmp_path / 'sub'
    auditor.rulesinit.write_selection(dest, ['security'])
    auditor.rulesinit.apply_selection(dest)
    assert not (dest / '.git').exists()


def test_a_missing_selection_file_is_refused(tmp_path: pathlib.Path) -> None:
    with pytest.raises(auditor.rulesinit.RulesInitError, match=r'selection\.txt'):
        auditor.rulesinit.apply_selection(tmp_path)


def failing(dest: pathlib.Path, match: str) -> None:
    before = snapshot(dest)
    with pytest.raises(auditor.rulesinit.RulesInitError, match=match):
        auditor.rulesinit.apply_selection(dest)
    assert snapshot(dest) == before
    assert not (dest / '.git').exists()


def test_a_misspelt_name_names_the_line(tmp_path: pathlib.Path) -> None:
    write_selection(tmp_path, '# comment', '', 'd1', 'raise-drift  # a title')
    failing(tmp_path, r"selection\.txt line 4: no catalogue rule 'raise-drift'")


def test_a_selected_rule_without_its_standard_is_refused(tmp_path: pathlib.Path) -> None:
    rule, standard = rule_with_standard()
    write_selection(tmp_path, rule)
    failing(tmp_path, f"rule '{rule}' needs standard '{standard}', which is not selected")


@pytest.mark.parametrize('existing', auditor.rulesinit.REPOSITORY_ENTRIES)
def test_an_existing_repository_is_refused(tmp_path: pathlib.Path, existing: str) -> None:
    write_selection(tmp_path, 'd1')
    (tmp_path / existing).mkdir()
    failing(tmp_path, 'already exists')


def test_apply_command_reports_an_error_with_exit_2(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_selection(tmp_path, 'nope')
    assert auditor.cli.main(['rules', 'apply', str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert captured.err.startswith("ERROR: selection.txt line 1: no catalogue rule 'nope'")
    assert captured.out == ''
