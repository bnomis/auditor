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
