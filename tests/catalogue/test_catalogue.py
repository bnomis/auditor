"""The default rule catalogue is a valid rules repository."""

import pathlib
import typing

import auditor.rulescli
import auditor.rulesrepo

CATALOGUE = pathlib.Path(__file__).resolve().parents[2] / 'src' / 'auditor' / 'catalogue'


def test_rules_check_passes_over_the_catalogue(monkeypatch, capsys) -> None:
    monkeypatch.setenv(auditor.rulesrepo.RULES_PATH_VARIABLE, str(CATALOGUE))
    assert auditor.rulescli.main(['check']) == 0, capsys.readouterr()


def test_every_standards_entry_names_a_standard_rule() -> None:
    repo = auditor.rulesrepo.load(CATALOGUE)
    standards = {rule.name for rule in repo.rules if rule.kind == 'standard'}
    for rule in repo.rules:
        for name in typing.cast('list[str]', rule.meta.get('standards', [])):
            assert name in standards, f'{rule.name} lists {name}, which is not a standard rule'
