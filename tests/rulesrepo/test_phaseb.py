import json
import pathlib
import sys
import typing

import pytest

import auditor.core
import auditor.phaseb
import auditor.phaseb.candidates
import auditor.phasebcli
import auditor.rulesrepo

if typing.TYPE_CHECKING:
    import collections.abc

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'


@pytest.fixture(autouse=True)
def isolate_registry() -> collections.abc.Iterator[None]:
    """Restore the built-in registrations and drop the modules a rules repository registered."""
    registry = dict(auditor.phaseb.candidates.REGISTRY)
    kinds = dict(auditor.phaseb.candidates.KINDS)
    depth = set(auditor.phaseb.candidates.TAKES_DEPTH)
    auditor.core.clear_source_cache()
    yield
    auditor.phaseb.candidates.REGISTRY.clear()
    auditor.phaseb.candidates.REGISTRY.update(registry)
    auditor.phaseb.candidates.KINDS.clear()
    auditor.phaseb.candidates.KINDS.update(kinds)
    auditor.phaseb.candidates.TAKES_DEPTH.clear()
    auditor.phaseb.candidates.TAKES_DEPTH.update(depth)
    for name in [name for name in sys.modules if name.startswith(auditor.rulesrepo.MODULE_PREFIX)]:
        del sys.modules[name]


@pytest.fixture
def repository(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(auditor.rulesrepo.RULES_PATH_VARIABLE, str(FIXTURES / 'phaseb'))


def phaseb(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = auditor.phasebcli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_candidates_come_from_the_lister(repository: None, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = phaseb(capsys, 'candidates', '--question', 'Q2', str(tmp_path))

    assert code == 0
    assert [json.loads(line)['id'] for line in out.splitlines()] == ['b.py::g']


def test_the_depth_reaches_a_question_that_takes_it(repository: None, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = phaseb(capsys, 'candidates', '--question', 'Q1', '--depth', '5', str(tmp_path))

    assert code == 0
    assert [json.loads(line)['payload'] for line in out.splitlines()] == [{'depth': 5}]


def test_the_depth_is_refused_for_a_question_that_takes_none(repository: None, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        auditor.phasebcli.main(['candidates', '--question', 'Q2', '--depth', '5', str(tmp_path)])


def test_the_plan_records_the_brief_version(repository: None, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = phaseb(capsys, 'plan', '--question', 'Q1', str(tmp_path), '--out', str(tmp_path / 'run'))

    assert code == 0
    assert 'brief version 3' in out


def test_the_batch_size_comes_from_rule_toml_or_the_default(repository: None, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, _ = phaseb(capsys, 'candidates', '--question', 'Q2', str(tmp_path))

    assert code == 0
    assert auditor.phaseb.question_batch_size('Q1') == 7
    assert auditor.phaseb.question_batch_size('Q2') == auditor.phaseb.candidates.DEFAULT_BATCH_SIZE


def test_the_kinds_and_the_depth_questions_come_from_rule_toml(repository: None, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, _ = phaseb(capsys, 'candidates', '--question', 'Q2', str(tmp_path))

    assert code == 0
    assert auditor.phaseb.candidates.question_kinds('Q1') == ('missing', 'extra')
    assert auditor.phaseb.depth_questions() == ['Q1']


def test_only_questions_with_a_lister_are_registered(repository: None, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, _ = phaseb(capsys, 'candidates', '--question', 'Q2', str(tmp_path))

    assert code == 0
    assert auditor.phaseb.registered_questions() == ['Q1', 'Q2']


def test_the_brief_is_the_rules_brief(repository: None, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, _ = phaseb(capsys, 'candidates', '--question', 'Q2', str(tmp_path))

    assert code == 0
    assert auditor.phaseb.question_brief('Q1') == FIXTURES / 'phaseb' / 'rules' / 'q1' / 'brief.md'


def test_an_invalid_repository_stops_with_its_message(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv(auditor.rulesrepo.RULES_PATH_VARIABLE, str(FIXTURES / 'no-manifest'))

    code, _, err = phaseb(capsys, 'candidates', '--question', 'Q1', str(tmp_path))

    assert code == 2
    assert 'auditor-rules.toml' in err


def test_the_built_in_registrations_stay_when_the_variable_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(auditor.rulesrepo.RULES_PATH_VARIABLE, raising=False)
    before = auditor.phaseb.registered_questions()

    auditor.phaseb.candidates.use_rules_repository()

    assert auditor.phaseb.registered_questions() == before
    assert 'A4' in before
