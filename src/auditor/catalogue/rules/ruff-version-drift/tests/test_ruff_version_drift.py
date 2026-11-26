"""Tests for the checks of the `ruff-version-drift` rule."""

import collections.abc
import contextlib
import io
import pathlib
import typing

import hypothesis
import hypothesis.strategies
import pytest

import auditor.core
import auditor.sweep
import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

RUFF_VERSION = auditor.testing.load_check(__file__)
RULE = auditor.testing.load_check_module(__file__)
RUFF = auditor.testing.load_check(__file__, 'ruff')


HOOK_REPO = 'https://github.com/astral-sh/ruff-pre-commit'
StubRuff = collections.abc.Callable[[str | None], None]


def hook_config(rev_line: str | None = '    rev: v0.17.3', repo: str = HOOK_REPO) -> dict[str, str]:
    lines = ['repos:', f'  - repo: {repo}']
    if rev_line is not None:
        lines.append(rev_line)
    lines.extend(['    hooks:', '      - id: ruff-check'])
    return {'.pre-commit-config.yaml': '\n'.join(lines) + '\n'}


@pytest.fixture
def stub_ruff(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> StubRuff:
    """Make a `ruff` stub the only thing on PATH; `None` leaves PATH without ruff."""

    def install(output: str | None) -> None:
        directory = tmp_path_factory.mktemp('stub-bin')
        if output is not None:
            script = directory / 'ruff'
            script.write_text(f"#!/bin/sh\necho '{output}'\n", encoding='utf-8')
            script.chmod(0o755)
        monkeypatch.setenv('PATH', str(directory))

    return install


def drift_hits(run_check: Runner, root: pathlib.Path) -> list[dict[str, typing.Any]]:
    return [hit for hit in run_check(RUFF_VERSION, root) if hit['rule'] == 'ruff-version-drift']


def test_equal_versions_give_no_hit(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    stub_ruff('ruff 0.17.3')
    assert drift_hits(run_check, project(hook_config())) == []


def test_different_versions_give_one_hit_at_the_rev_line(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    stub_ruff('ruff 0.17.1')
    hits = drift_hits(run_check, project(hook_config()))
    assert len(hits) == 1
    assert hits[0]['path'] == '.pre-commit-config.yaml'
    assert hits[0]['line'] == 3
    assert hits[0]['variant'] == 'the ruff the audit runs differs from the ruff-pre-commit rev'
    assert hits[0]['evidence'] == 'ruff on PATH is 0.17.1; the hook pins v0.17.3'
    assert hits[0]['accepted'] is False


def test_a_rev_without_the_v_compares_the_same(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    stub_ruff('ruff 0.17.3')
    assert drift_hits(run_check, project(hook_config('    rev: 0.17.3'))) == []


def test_a_sha_rev_uses_its_frozen_comment(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    root = project(hook_config(f'    rev: {"a" * 40}  # frozen: v0.17.3'))
    stub_ruff('ruff 0.17.3')
    assert drift_hits(run_check, root) == []
    stub_ruff('ruff 0.17.1')
    hits = drift_hits(run_check, root)
    assert len(hits) == 1
    assert hits[0]['variant'] == 'the ruff the audit runs differs from the ruff-pre-commit rev'


def test_a_sha_rev_with_no_comment_names_no_version(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    stub_ruff('ruff 0.17.3')
    hits = drift_hits(run_check, project(hook_config(f'    rev: {"a" * 40}')))
    assert len(hits) == 1
    assert hits[0]['variant'] == 'the ruff-pre-commit rev names no version'
    assert hits[0]['line'] == 3


def test_a_repo_with_no_rev_names_no_version_at_the_repo_line(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    stub_ruff('ruff 0.17.3')
    hits = drift_hits(run_check, project(hook_config(None)))
    assert len(hits) == 1
    assert hits[0]['variant'] == 'the ruff-pre-commit rev names no version'
    assert hits[0]['line'] == 2


def test_a_stub_printing_no_version_is_a_hit(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    stub_ruff('something else')
    hits = drift_hits(run_check, project(hook_config()))
    assert len(hits) == 1
    assert hits[0]['variant'] == 'ruff --version printed no version'
    assert hits[0]['line'] == 3
    assert hits[0]['evidence'] == 'something else'


def test_no_config_gives_no_hit(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    stub_ruff('ruff 0.17.1')
    assert drift_hits(run_check, project({'src/probe/mod.py': 'VALUE = 1\n'})) == []


def test_a_config_without_the_ruff_hook_gives_no_hit(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    stub_ruff('ruff 0.17.1')
    root = project({'.pre-commit-config.yaml': 'repos:\n  - repo: https://github.com/example/other\n    rev: v1.0.0\n'})
    assert drift_hits(run_check, root) == []


def test_no_ruff_on_path_is_a_hit(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    stub_ruff(None)
    hits = drift_hits(run_check, project(hook_config()))
    assert len(hits) == 1
    assert 'could not run' in hits[0]['variant']


@pytest.mark.parametrize('placement', ['same-line', 'line-above'])
def test_a_scoped_marker_accepts_the_hit(project: Builder, run_check: Runner, stub_ruff: StubRuff, placement: str) -> None:
    stub_ruff('ruff 0.17.1')
    marker = '# auditme: accept[ruff-version-drift] cooldown has not admitted it'
    rev_line = f'    rev: v0.17.3  {marker}' if placement == 'same-line' else f'    {marker}\n    rev: v0.17.3'
    hits = drift_hits(run_check, project(hook_config(rev_line)))
    assert len(hits) == 1
    assert hits[0]['accepted'] is True
    assert hits[0]['accepted_reason'] == 'cooldown has not admitted it'


def test_a_marker_scoped_to_another_rule_does_not_accept(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    stub_ruff('ruff 0.17.1')
    hits = drift_hits(run_check, project(hook_config('    rev: v0.17.3  # auditme: accept[lockfile-drift] unrelated')))
    assert len(hits) == 1
    assert hits[0]['accepted'] is False


@pytest.mark.parametrize('suffix', ['.git', '/', '.git/'])
def test_a_repo_url_with_a_suffix_is_still_found(project: Builder, run_check: Runner, stub_ruff: StubRuff, suffix: str) -> None:
    stub_ruff('ruff 0.17.1')
    assert len(drift_hits(run_check, project(hook_config(repo=f'{HOOK_REPO}{suffix}')))) == 1


def venv_ruff(root: pathlib.Path, output: str, executable: bool = True) -> None:
    """Write a stub `<root>/.venv/bin/ruff` that prints `output`."""
    script = root / '.venv' / 'bin' / 'ruff'
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(f"#!/bin/sh\necho '{output}'\n", encoding='utf-8')
    script.chmod(0o755 if executable else 0o644)


def test_the_project_venv_ruff_is_preferred_over_path(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    """A shell whose PATH starts with another ruff must not change the answer."""
    stub_ruff('ruff 0.17.1')
    root = project(hook_config())
    venv_ruff(root, 'ruff 0.17.3')
    assert drift_hits(run_check, root) == []


def test_a_differing_venv_ruff_is_named_in_the_evidence(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    stub_ruff('ruff 0.17.3')
    root = project(hook_config())
    venv_ruff(root, 'ruff 0.17.1')
    hits = drift_hits(run_check, root)
    assert len(hits) == 1
    assert hits[0]['evidence'] == '.venv/bin/ruff is 0.17.1; the hook pins v0.17.3'


def test_a_venv_ruff_that_is_not_executable_falls_back_to_path(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    stub_ruff('ruff 0.17.3')
    root = project(hook_config())
    venv_ruff(root, 'ruff 0.17.1', executable=False)
    assert drift_hits(run_check, root) == []


def test_check_ruff_runs_the_project_venv_ruff(project: Builder, run_check: Runner, stub_ruff: StubRuff) -> None:
    """With no ruff on PATH, a project ruff still runs: no `ruff not installed` hit."""
    stub_ruff(None)
    root = project({'src/probe/mod.py': 'VALUE = 1\n'})
    venv_ruff(root, '[]')
    assert [hit for hit in run_check(RUFF, root) if hit['rule'] == 'ruff'] == []


def test_two_roots_of_one_project_print_one_hit(project: Builder, stub_ruff: StubRuff) -> None:
    stub_ruff('ruff 0.17.1')
    root = project(hook_config())
    auditor.core.EMITTED.clear()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        RUFF_VERSION(root, root / 'src' / 'probe')
        RUFF_VERSION(root, root / 'bin')
    assert len(buffer.getvalue().splitlines()) == 1


YAML_LINE = hypothesis.strategies.sampled_from(
    [
        'repos:',
        '  - repo: https://github.com/astral-sh/ruff-pre-commit',
        '  - repo: https://github.com/other/hooks',
        '    rev: v0.1.2',
        '    rev: abc123 # frozen: v0.4.5',
        '    rev: abc123',
        '    hooks:',
        '      - id: ruff',
        '',
    ]
)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(lines=hypothesis.strategies.lists(YAML_LINE, max_size=10))
def test_ruff_hook_pin_reports_lines_inside_the_file(lines: list[str]) -> None:
    pin = RULE.ruff_hook_pin(lines)
    if pin is None:
        return
    repo_line, rev_line, version = pin
    assert 1 <= repo_line <= len(lines)
    if rev_line is None:
        assert version is None
    else:
        assert repo_line < rev_line <= len(lines)
