import json
import pathlib
import sys
import typing

import pytest

import auditor.core
import auditor.rulesrepo
import auditor.sweep

if typing.TYPE_CHECKING:
    import collections.abc

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'


@pytest.fixture(autouse=True)
def isolate_sweep_state() -> collections.abc.Iterator[None]:
    """Clear the process-wide state a sweep leaves behind, and the modules a rules repository registered."""
    extra_roots = auditor.core.EXTRA_ROOT_NAMES
    never_accepted = auditor.core.NEVER_ACCEPTED
    auditor.core.clear_source_cache()
    auditor.core.EMITTED.clear()
    auditor.core.UNREADABLE.clear()
    yield
    auditor.core.EXTRA_ROOT_NAMES = extra_roots
    auditor.core.NEVER_ACCEPTED = never_accepted
    auditor.core.EMITTED.clear()
    auditor.core.UNREADABLE.clear()
    for name in [name for name in sys.modules if name.startswith(auditor.rulesrepo.MODULE_PREFIX)]:
        del sys.modules[name]


@pytest.fixture
def scope(tmp_path: pathlib.Path) -> pathlib.Path:
    """A project with two packages under src/ and nothing else."""
    for package in ('one', 'two'):
        (tmp_path / 'src' / package).mkdir(parents=True)
        (tmp_path / 'src' / package / '__init__.py').write_text('', encoding='utf-8')
    return tmp_path


def sweep(
    scope: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    case: str | None,
) -> tuple[int, list[dict[str, typing.Any]], str]:
    if case is None:
        monkeypatch.delenv(auditor.rulesrepo.RULES_PATH_VARIABLE, raising=False)
    else:
        monkeypatch.setenv(auditor.rulesrepo.RULES_PATH_VARIABLE, str(FIXTURES / case))
    code = auditor.sweep.main([str(scope)])
    captured = capsys.readouterr()
    return code, [json.loads(line) for line in captured.out.splitlines()], captured.err


def test_sweep_emits_exactly_the_fixtures_hits(scope: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    code, hits, err = sweep(scope, capsys, monkeypatch, 'sweep-ok')
    assert code == 0, err
    # The project-check runs once, before the per-root passes, and the check once per root
    assert [(hit['rule'], hit['evidence']) for hit in hits] == [
        ('fixture-project', scope.name),
        ('fixture-hit', 'one'),
        ('fixture-hit', 'two'),
    ]


def test_a_raising_rule_is_one_crash_hit_and_the_others_still_run(
    scope: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    code, hits, _ = sweep(scope, capsys, monkeypatch, 'sweep-crash')
    assert code == 0
    crashes = [hit for hit in hits if hit['rule'] == 'auditme-check-crash']
    # One crash hit for each failing rule, though each is attempted for both roots: the hit repeats identically, so it is reported once
    assert sorted(hit['variant'] for hit in crashes) == ['rules/a-raises/check.py', 'rules/b-import-error/check.py']
    assert {hit['evidence'] for hit in crashes} == {'ValueError: boom', 'RuntimeError: at import'}
    assert [hit['evidence'] for hit in hits if hit['rule'] == 'fixture-hit'] == ['one', 'two']


def test_a_rule_cannot_import_a_sibling_rule(scope: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    code, hits, _ = sweep(scope, capsys, monkeypatch, 'sweep-sibling')
    assert code == 0
    crashes = [hit for hit in hits if hit['rule'] == 'auditme-check-crash']
    assert [hit['variant'] for hit in crashes] == ['rules/b-two/check.py']
    assert 'auditor_rules' in crashes[0]['evidence']
    assert [hit['variant'] for hit in hits if hit['rule'] == 'fixture-hit'] == ['one', 'one']


def test_nothing_is_put_on_sys_path(scope: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    before = list(sys.path)
    code, _, err = sweep(scope, capsys, monkeypatch, 'sweep-ok')
    assert code == 0, err
    assert sys.path == before


def test_never_accepted_is_validated_against_the_repositorys_rule_ids(
    scope: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (scope / 'pyproject.toml').write_text('[tool.auditme]\nnever-accepted = ["fixture-hit"]\n', encoding='utf-8')
    code, _, err = sweep(scope, capsys, monkeypatch, 'sweep-ok')
    assert code == 0, err

    # A built-in id the repository does not emit is not a rule id for this sweep
    (scope / 'pyproject.toml').write_text('[tool.auditme]\nnever-accepted = ["silent-broad-except"]\n', encoding='utf-8')
    code, hits, err = sweep(scope, capsys, monkeypatch, 'sweep-ok')
    assert code == 2
    assert hits == []
    assert err.startswith('ERROR: ')
    assert "never-accepted 'silent-broad-except' matches no rule id" in err


def test_an_invalid_repository_is_an_error_with_nothing_on_stdout(
    scope: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    code, hits, err = sweep(scope, capsys, monkeypatch, 'no-manifest')
    assert code == 2
    assert hits == []
    assert err.startswith('ERROR: auditor-rules.toml: file not found')


def test_an_empty_variable_is_an_error(scope: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(auditor.rulesrepo.RULES_PATH_VARIABLE, '')
    code = auditor.sweep.main([str(scope)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ''
    assert captured.err.startswith(f'ERROR: {auditor.rulesrepo.RULES_PATH_VARIABLE} is not set')


def test_an_unset_variable_is_an_error(scope: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    code, hits, err = sweep(scope, capsys, monkeypatch, None)
    assert code == 2
    assert hits == []
    assert err.startswith(f'ERROR: {auditor.rulesrepo.RULES_PATH_VARIABLE} is not set')


def test_a_missing_entry_function_is_an_error(tmp_path: pathlib.Path) -> None:
    rule_dir = tmp_path / 'rules' / 'r'
    rule_dir.mkdir(parents=True)
    (rule_dir / 'check.py').write_text('x = 1\n', encoding='utf-8')
    rule = auditor.rulesrepo.Rule(name='r', kind='check', path=rule_dir, meta={})
    with pytest.raises(auditor.rulesrepo.RulesRepoError, match=r'rules/r/check.py: does not define check\(\)'):
        auditor.rulesrepo.import_entry(rule, 'check.py')
    assert 'auditor_rules.r.check' not in sys.modules
