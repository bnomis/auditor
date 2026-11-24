"""Tests for `[tool.auditme] never-accepted`: reading it and validating it against the rule ids."""

import collections.abc
import pathlib
import sys

import audit
import auditme.core
import pytest

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]


def declare(project: Builder, value: str) -> pathlib.Path:
    return project({'src/probe/mod.py': 'x = 1\n', 'pyproject.toml': f'[tool.auditme]\nnever-accepted = {value}\n'})


def test_patterns_are_returned_in_order(project: Builder) -> None:
    root = declare(project, '["literal-duplication", "leading-underscore-*"]')
    assert auditme.core.never_accepted(root) == ('literal-duplication', 'leading-underscore-*')


def test_an_absent_table_gives_no_patterns(project: Builder) -> None:
    assert auditme.core.never_accepted(project({'pyproject.toml': '[project]\nname = "probe"\n'})) == ()


def test_an_absent_key_in_the_table_gives_no_patterns(project: Builder) -> None:
    assert auditme.core.never_accepted(project({'pyproject.toml': '[tool.auditme]\n'})) == ()


@pytest.mark.parametrize(
    ('value', 'message'),
    [
        ('"literal-duplication"', 'never-accepted must be a list of strings'),
        ('[3]', 'never-accepted must be a list of strings'),
        ('["no-such-rule"]', "never-accepted 'no-such-rule' matches no rule id"),
        ('["no-such-*"]', "never-accepted 'no-such-*' matches no rule id"),
        ('["leading-*-parameter"]', "never-accepted 'leading-*-parameter' may use * only at the end"),
    ],
)
def test_an_invalid_value_exits_2_before_anything_is_printed(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    value: str,
    message: str,
) -> None:
    root = declare(project, value)
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])
    assert audit.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err.strip() == f'ERROR: pyproject.toml [tool.auditme]: {message}'


def test_ruff_and_lockfile_drift_may_be_named(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = declare(project, '["ruff", "lockfile-drift", "leading-underscore-*"]')
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])
    audit.main()
    assert 'ERROR' not in capsys.readouterr().err


# --- first-party


def first_party_project(project: Builder, value: str, extra: dict[str, str] | None = None) -> pathlib.Path:
    files = {
        'proj/src/probe/mod.py': 'x = 1\n',
        'proj/pyproject.toml': f'[tool.auditme]\nfirst-party = {value}\n',
        'lib/src/lib/__init__.py': 'y = 1\n',
        'lib/src/lib/errors.py': 'class LibError(Exception):\n    pass\n',
        'lib/empty/notes.txt': 'no python here\n',
        'lib/src/lib_file.py': 'z = 1\n',
    }
    files.update(extra or {})
    return project(files) / 'proj'


def test_first_party_dirs_are_returned_resolved_in_order(project: Builder) -> None:
    scope = first_party_project(project, '["../lib/src/lib", "../lib/src"]')
    lib = scope.parent / 'lib' / 'src'
    assert auditme.core.first_party_dirs(scope) == [(lib / 'lib').resolve(), lib.resolve()]


def test_without_the_key_first_party_dirs_is_empty(project: Builder) -> None:
    assert auditme.core.first_party_dirs(project({'pyproject.toml': '[tool.auditme]\n'})) == []
    assert auditme.core.first_party_dirs(project({'x.py': 'x = 1\n'})) == []


def test_first_party_beside_roots_and_never_accepted_is_accepted(project: Builder) -> None:
    pyproject = '[tool.auditme]\nnever-accepted = ["literal-duplication"]\nfirst-party = ["../lib/src/lib"]\nroots = [{ path = "tools" }]\n'
    scope = first_party_project(project, '[]', {'proj/pyproject.toml': pyproject, 'proj/tools/run.py': 'x = 1\n'})
    assert auditme.core.declared_roots(scope) == [(scope / 'tools', 'package')]
    assert auditme.core.first_party_dirs(scope) == [(scope.parent / 'lib' / 'src' / 'lib').resolve()]


@pytest.mark.parametrize(
    ('entries', 'message'),
    [
        ('["../lib/src/absent"]', 'first-party path ../lib/src/absent not found'),
        ('["../lib/src/lib_file.py"]', 'first-party path ../lib/src/lib_file.py not found'),
        ('["../lib/empty"]', 'first-party path ../lib/empty holds no .py file'),
        ('"../lib/src/lib"', 'first-party must be a list of strings'),
        ('[3]', 'first-party must be a list of strings'),
        ('[""]', 'first-party must be a list of strings'),
        ('["src/probe"]', 'first-party path src/probe lies inside a root the sweep audits'),
    ],
)
def test_an_invalid_first_party_entry_exits_2_before_anything_is_printed(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    entries: str,
    message: str,
) -> None:
    scope = first_party_project(project, entries)
    with pytest.raises(auditme.core.RootsError, match=message):
        auditme.core.first_party_dirs(scope)
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(scope)])
    assert audit.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err.startswith('ERROR: ')
    assert captured.err.strip().endswith(message)
