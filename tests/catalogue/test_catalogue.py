"""The default rule catalogue is a valid rules repository."""

import json
import pathlib
import typing

import auditor.rulescli
import auditor.rulesrepo
import auditor.sweep

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


SWEPT_BODY = (
    'import json\n\n\ndef parse(payload):\n    parsed = json.loads(payload)\n    usage = parsed.get("usage", {})\n    return usage.get("input_tokens", 0)\n'
)


def test_the_sweep_reads_each_catalogue_rule_file_once_by_its_path(project, capsys) -> None:
    root = project(
        {
            'src/probe/__init__.py': '__all__: list[str] = []\n',
            'src/probe/catalogue/rules/probe-rule/check.py': SWEPT_BODY,
            'src/probe/catalogue/rules/probe-rule/lister.py': SWEPT_BODY,
        }
    )
    assert auditor.sweep.main([str(root)]) == 0
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    paths = [record['path'] for record in records if record['rule'] == 'get-container-default-then-method-call']
    assert sorted(paths) == [
        'src/probe/catalogue/rules/probe-rule/check.py',
        'src/probe/catalogue/rules/probe-rule/lister.py',
    ]
