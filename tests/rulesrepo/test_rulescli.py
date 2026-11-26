import pathlib
import shutil
import sys
import typing

import pytest

import auditor.cli
import auditor.core
import auditor.rulesrepo

if typing.TYPE_CHECKING:
    import collections.abc

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'


@pytest.fixture(autouse=True)
def isolate_state() -> collections.abc.Iterator[None]:
    auditor.core.clear_source_cache()
    yield
    for name in [name for name in sys.modules if name.startswith(auditor.rulesrepo.MODULE_PREFIX)]:
        del sys.modules[name]


def run(monkeypatch: pytest.MonkeyPatch, root: pathlib.Path, *args: str) -> int:
    monkeypatch.setenv(auditor.rulesrepo.RULES_PATH_VARIABLE, str(root))
    return auditor.cli.main(['rules', *args])


def test_list_prints_one_line_per_rule(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(monkeypatch, FIXTURES / 'valid', 'list') == 0
    lines = capsys.readouterr().out.splitlines()
    assert 'a4\tquestion\tA4\tA question' in lines
    assert 'my-check\tcheck\tmy-check\tA check' in lines
    assert len(lines) == 5


def test_list_filters_by_kind(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(monkeypatch, FIXTURES / 'valid', 'list', '--kind', 'standard') == 0
    assert capsys.readouterr().out.splitlines() == ['my-standard\tstandard\tmy-standard\tA standard']


def test_check_passes_on_a_clean_repository(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(monkeypatch, FIXTURES / 'sweep-ok', 'check') == 0
    assert capsys.readouterr().out == ''


def test_check_reports_an_import_outside_the_api(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(monkeypatch, FIXTURES / 'import-boundary', 'check') == 1
    out = capsys.readouterr().out
    assert 'check.py:2: imports auditor.core: import auditor.api only' in out
    assert 'auditor.api:' not in out


def test_check_reports_an_entry_that_raises_on_import(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(monkeypatch, FIXTURES / 'valid', 'check') == 1
    assert 'rules/my-check/check.py: raises on import' in capsys.readouterr().out


def test_standards_prints_each_standard_in_name_order(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(monkeypatch, FIXTURES / 'valid', 'standards') == 0
    expected = (FIXTURES / 'valid' / 'rules' / 'my-standard' / 'rule.md').read_text(encoding='utf-8').rstrip('\n')
    assert capsys.readouterr().out == f'{expected}\n'


def test_questions_prints_the_checklist(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(monkeypatch, FIXTURES / 'valid', 'questions') == 0
    out = capsys.readouterr().out
    assert '## A4: A question' in out
    assert '## S1: Prose question' in out
    assert out.index('## A4') < out.index('## S1')


def test_questions_filters_by_category(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(monkeypatch, FIXTURES / 'valid', 'questions', '--category', 'S') == 0
    out = capsys.readouterr().out
    assert '## S1' in out
    assert '## A4' not in out


def test_an_invalid_repository_is_an_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(monkeypatch, FIXTURES / 'unknown-key', 'list') == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err.startswith('ERROR: ')


def test_an_unset_variable_is_an_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv(auditor.rulesrepo.RULES_PATH_VARIABLE, raising=False)
    assert auditor.cli.main(['rules', 'list']) == 2
    assert 'AUDITOR_RULES_PATH is not set' in capsys.readouterr().err


@pytest.fixture
def repository(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / 'rules-repo'
    shutil.copytree(FIXTURES / 'sweep-ok', root, ignore=shutil.ignore_patterns('__pycache__'))
    return root


def test_pending_without_a_todo_exits_zero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], repository: pathlib.Path) -> None:
    assert run(monkeypatch, repository, 'pending') == 0
    assert capsys.readouterr().out == ''


def test_pending_without_a_heading_exits_zero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], repository: pathlib.Path) -> None:
    (repository / 'TODO.md').write_text('# TODO\n\nNothing open.\n', encoding='utf-8')
    assert run(monkeypatch, repository, 'pending') == 0
    assert capsys.readouterr().out == ''


def test_pending_ignores_a_heading_in_a_fenced_block(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], repository: pathlib.Path) -> None:
    (repository / 'TODO.md').write_text('# TODO\n\n```markdown\n## Example item\n```\n', encoding='utf-8')
    assert run(monkeypatch, repository, 'pending') == 0
    assert capsys.readouterr().out == ''


def test_pending_lists_each_open_item(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], repository: pathlib.Path) -> None:
    (repository / 'TODO.md').write_text('# TODO\n\n## First item\n\ntext\n\n## Second item\n', encoding='utf-8')
    assert run(monkeypatch, repository, 'pending') == 1
    assert capsys.readouterr().out.splitlines() == ['## First item', '## Second item']
