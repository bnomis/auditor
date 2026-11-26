import pathlib

import pytest

import auditor.api
import auditor.core
import auditor.rulesrepo

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'


@pytest.fixture(autouse=True)
def fresh_cache() -> None:
    auditor.core.clear_source_cache()


def load_case(case: str) -> auditor.rulesrepo.RulesRepo:
    return auditor.rulesrepo.load(FIXTURES / case)


def test_valid_repository_loads_one_rule_of_each_kind() -> None:
    repo = load_case('valid')
    assert repo.api == (1, 0)
    assert [rule.name for rule in repo.rules] == ['a4', 'my-check', 'my-project-check', 'my-standard', 's1']
    assert {rule.kind for rule in repo.rules} == {'check', 'project-check', 'question', 'standard'}
    assert repo.root == (FIXTURES / 'valid').resolve()


def test_rule_ids_include_emitted_and_runner_ids() -> None:
    ids = load_case('valid').rule_ids()
    assert {'my-check', 'my-project-check', 'ruff', 'auditme-check-crash'} <= ids
    assert 'A4' not in ids


def test_load_imports_no_rule_code() -> None:
    # every fixture check.py raises when imported, so a clean load proves nothing ran
    assert load_case('valid').rules


def test_load_is_cached_until_the_source_cache_is_cleared() -> None:
    first = load_case('valid')
    assert load_case('valid') is first
    auditor.core.clear_source_cache()
    assert load_case('valid') is not first


@pytest.mark.parametrize(
    ('case', 'message'),
    [
        ('unknown-key', "rules/r/rule.toml: unknown key 'colour'"),
        ('unknown-kind', "rules/r/rule.toml: kind must be one of check, project-check, question, standard, not 'lint'"),
        ('missing-rule-md', 'rules/my-check/rule.md: file not found'),
        ('check-without-check-py', 'rules/my-check/check.py: file not found'),
        ('lister-without-kinds', 'rules/a4/rule.toml: a question with lister.py needs kinds'),
        ('duplicate-id', "rules/two/rule.toml: rule id 'my-check' is also used by rules/one/rule.toml"),
        ('api-major', 'rules repository needs API 2.0; this auditor serves 1.0: upgrade auditor or use an older rules repository'),
        ('api-minor', 'rules repository needs API 1.1; this auditor serves 1.0: upgrade auditor or use an older rules repository'),
        ('no-manifest', 'auditor-rules.toml: file not found'),
        ('bad-standards', "rules/my-check/rule.toml: standards names 'nope'"),
    ],
)
def test_error_case_names_the_file(case: str, message: str) -> None:
    with pytest.raises(auditor.rulesrepo.RulesRepoError) as raised:
        load_case(case)
    assert message in str(raised.value)
    assert isinstance(raised.value, auditor.core.SettingsError)


def test_rules_root_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('AUDITOR_RULES_PATH', raising=False)
    with pytest.raises(auditor.rulesrepo.RulesRepoError, match="AUDITOR_RULES_PATH is not set: create a rules repository with 'auditor rules init <dir>'"):
        auditor.rulesrepo.rules_root()


def test_rules_root_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('AUDITOR_RULES_PATH', '')
    with pytest.raises(auditor.rulesrepo.RulesRepoError, match='AUDITOR_RULES_PATH is not set'):
        auditor.rulesrepo.rules_root()


def test_rules_root_missing_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setenv('AUDITOR_RULES_PATH', str(tmp_path / 'absent'))
    with pytest.raises(auditor.rulesrepo.RulesRepoError, match='which is not a directory'):
        auditor.rulesrepo.rules_root()


def test_rules_root_resolves_the_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('AUDITOR_RULES_PATH', str(FIXTURES / 'valid'))
    assert auditor.rulesrepo.rules_root() == (FIXTURES / 'valid').resolve()


def test_api_version_matches_the_helper_api() -> None:
    assert auditor.rulesrepo.API_VERSION == auditor.api.API_VERSION
