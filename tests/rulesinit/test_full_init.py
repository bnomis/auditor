import json
import sys
import typing

import auditor.cli
import auditor.core
import auditor.rulesinit
import auditor.sweep

if typing.TYPE_CHECKING:
    import pathlib

    import pytest


def sweep_hits(
    project: pathlib.Path,
    rules: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> list[dict[str, typing.Any]]:
    monkeypatch.setenv('AUDITOR_RULES_PATH', str(rules))
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(project)])
    auditor.core.EMITTED.clear()
    auditor.sweep.main()
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_a_full_init_sweeps_the_same_as_the_catalogue(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dest = tmp_path / 'rules-repo'
    assert auditor.cli.main(['rules', 'init', str(dest)]) == 0
    assert auditor.cli.main(['rules', 'apply', str(dest)]) == 0
    capsys.readouterr()

    project = tmp_path / 'project'
    (project / 'src' / 'pkg').mkdir(parents=True)
    (project / 'src' / 'pkg' / '__init__.py').write_text('', encoding='utf-8')
    (project / 'src' / 'pkg' / 'mod.py').write_text('def _helper() -> None:\n    pass\n', encoding='utf-8')
    (project / 'bin').mkdir()
    (project / 'bin' / 'tool.py').write_text('def _other() -> None:\n    pass\n', encoding='utf-8')

    from_catalogue = sweep_hits(project, auditor.rulesinit.catalogue_root(), monkeypatch, capsys)
    from_init = sweep_hits(project, dest, monkeypatch, capsys)
    assert from_catalogue
    assert from_init == from_catalogue
