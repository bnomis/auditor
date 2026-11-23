"""Tests for the project-level predicates: ruff, the lockfile, spec references."""

import collections.abc
import contextlib
import io
import os
import pathlib
import subprocess
import sys

import audit
import auditme.core
import auditme.rules.project_hygiene
import hypothesis
import hypothesis.strategies
import pytest

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

RUFF = auditme.rules.project_hygiene.check_ruff
LOCKFILE = auditme.rules.project_hygiene.check_lockfile
RUFF_VERSION = auditme.rules.project_hygiene.check_ruff_version
PHASE_SECTION = auditme.rules.project_hygiene.check_phase_section_doc_reference


def require_ruff() -> None:
    try:
        subprocess.run(['ruff', '--version'], capture_output=True, check=False)
    except FileNotFoundError:
        pytest.skip('ruff is not installed')


# --------------------------------------------------------------------------
# check_ruff
# --------------------------------------------------------------------------


def test_a_lint_error_is_reported_with_its_ruff_code(project: Builder, run_check: Runner) -> None:
    require_ruff()
    root = project({'src/probe/mod.py': 'import os\n'})
    hits = [hit for hit in run_check(RUFF, root) if hit['rule'] == 'ruff']
    assert 'F401' in {hit['variant'] for hit in hits}
    unused = [hit for hit in hits if hit['variant'] == 'F401']
    assert unused[0]['path'] == 'src/probe/mod.py'
    assert unused[0]['line'] == 1


def test_clean_source_produces_no_ruff_hits(project: Builder, run_check: Runner) -> None:
    require_ruff()
    root = project({'src/probe/mod.py': 'VALUE = 1\n'})
    assert [hit for hit in run_check(RUFF, root) if hit['rule'] == 'ruff'] == []


def test_an_unformatted_file_is_reported_at_its_path_and_line(project: Builder, run_check: Runner) -> None:
    """The `ruff format --check` half reports each file it would reformat, by path."""
    require_ruff()
    root = project({'src/probe/mod.py': 'def f( a ):\n    return   a\n', 'src/probe/ok.py': 'VALUE = 1\n'})
    hits = [hit for hit in run_check(RUFF, root) if hit['variant'] == 'ruff-format']
    assert [hit['path'] for hit in hits] == ['src/probe/mod.py']
    assert hits[0]['line'] == 1
    assert hits[0]['evidence'] == 'File would be reformatted'


# Captured from `ruff format --check --output-format=json` (ruff 0.17.4, the pinned version) on 2026-11-22.
FORMAT_JSON = '[{"cell": null, "code": "unformatted", "end_location": {"column": 13, "row": 2}, "filename": "{root}/src/probe/mod.py", "fix": null, "location": {"column": 7, "row": 1}, "message": "File would be reformatted", "name": "unformatted", "noqa_row": null, "severity": "error", "url": null}]'


def test_format_output_from_the_pinned_ruff_is_parsed(project: Builder, run_check: Runner, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'src/probe/mod.py': 'VALUE = 1\n'})

    def fake(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if cmd[1] == 'format':
            return subprocess.CompletedProcess(cmd, 1, FORMAT_JSON.replace('{root}', str(root)), '')
        return subprocess.CompletedProcess(cmd, 0, '[]', '')

    monkeypatch.setattr(subprocess, 'run', fake)
    hits = run_check(RUFF, root)
    assert [(hit['variant'], hit['path'], hit['line']) for hit in hits] == [('ruff-format', 'src/probe/mod.py', 1)]


def test_format_output_that_is_not_json_is_a_hit(project: Builder, run_check: Runner, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'src/probe/mod.py': 'VALUE = 1\n'})

    def fake(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if cmd[1] == 'format':
            return subprocess.CompletedProcess(cmd, 1, 'Would reformat: src/probe/mod.py', '')
        return subprocess.CompletedProcess(cmd, 0, '[]', '')

    monkeypatch.setattr(subprocess, 'run', fake)
    assert [hit['variant'] for hit in run_check(RUFF, root)] == ['ruff-format-parse-error']


def test_a_missing_ruff_is_reported_rather_than_passing_silently(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A check that cannot run has not answered its question."""

    def missing(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError('ruff')

    monkeypatch.setattr(subprocess, 'run', missing)
    root = project({'src/probe/mod.py': 'VALUE = 1\n'})
    hits = run_check(RUFF, root)
    assert {hit['variant'] for hit in hits} == {'ruff-check', 'ruff-format'}
    assert all(hit['evidence'] == 'ruff not installed' for hit in hits)


def test_a_ruff_that_cannot_be_executed_gets_the_same_report(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def denied(*args: object, **kwargs: object) -> None:
        raise PermissionError('ruff')

    monkeypatch.setattr(subprocess, 'run', denied)
    root = project({'src/probe/mod.py': 'VALUE = 1\n'})
    hits = run_check(RUFF, root)
    assert {hit['variant'] for hit in hits} == {'ruff-check', 'ruff-format'}


# --------------------------------------------------------------------------
# check_lockfile
# --------------------------------------------------------------------------


def test_a_project_without_a_lockfile_is_not_checked(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'VALUE = 1\n', 'pyproject.toml': '[project]\nname = "probe"\n'})
    assert run_check(LOCKFILE, root) == []


def test_drift_and_an_unanswerable_check_are_different_facts(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reporting "could not verify" as drift would be failure-as-absence in the
    checker itself."""

    class Result:
        def __init__(self, stderr: str) -> None:
            self.returncode = 1
            self.stdout = ''
            self.stderr = stderr

    root = project(
        {
            'src/probe/mod.py': 'VALUE = 1\n',
            'pyproject.toml': '[project]\nname = "probe"\n',
            'uv.lock': 'version = 1\n',
        }
    )

    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: Result('error: The lockfile at `uv.lock` needs to be updated\n'))
    drift = run_check(LOCKFILE, root)
    assert len(drift) == 1
    assert 'out of date' in drift[0]['variant']

    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: Result('error: network unreachable\n'))
    unverified = run_check(LOCKFILE, root)
    assert len(unverified) == 1
    assert 'could not verify' in unverified[0]['variant']


def test_a_resolution_timestamp_is_masked_out_of_the_evidence(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The evidence string has to be identical between runs or the audit reads
    an unchanged tree as a changed one."""

    class Result:
        returncode = 1
        stdout = ''
        stderr = 'error: failed at 2026-08-15T10:11:12.345Z on `uv.lock`\n'

    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: Result())
    root = project(
        {
            'src/probe/mod.py': 'VALUE = 1\n',
            'pyproject.toml': '[project]\nname = "probe"\n',
            'uv.lock': 'version = 1\n',
        }
    )
    hits = run_check(LOCKFILE, root)
    assert '<timestamp>' in hits[0]['evidence']
    assert '2026-08-15' not in hits[0]['evidence']


LOCK_PROJECT = {
    'pyproject.toml': '[project]\nname = "probe"\n',
    'src/probe/mod.py': 'VALUE = 1\n',
    'uv.lock': 'version = 1\n',
}
USER_EXCLUDE_NEWER = (
    'Resolving despite existing lockfile due to addition of global exclude newer 2026-10-18T09:17:10Z\n'
    'error: The lockfile at `uv.lock` needs to be updated, but `--check` was provided.\n'
)


class LockResult:
    def __init__(self, returncode: int, stderr: str = '') -> None:
        self.returncode = returncode
        self.stdout = ''
        self.stderr = stderr


def recording_run(results: list[LockResult], calls: list[dict[str, object]]) -> collections.abc.Callable[..., LockResult]:
    def fake_run(*args: object, **kwargs: object) -> LockResult:
        calls.append(kwargs)
        return results[len(calls) - 1]

    return fake_run


def test_drift_from_a_user_exclude_newer_alone_is_not_reported(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A user-level `exclude-newer` the lock was not made with re-resolves it on
    one machine only; CI, without that config, sees no drift."""
    calls: list[dict[str, object]] = []
    monkeypatch.setenv('PROBE_VAR', 'kept')
    monkeypatch.setattr(subprocess, 'run', recording_run([LockResult(1, USER_EXCLUDE_NEWER), LockResult(0)], calls))
    assert run_check(LOCKFILE, project(LOCK_PROJECT)) == []
    assert len(calls) == 2
    assert 'env' not in calls[0]
    env = calls[1]['env']
    assert isinstance(env, dict)
    assert env['UV_NO_CONFIG'] == '1'
    assert env['PROBE_VAR'] == 'kept'


def test_a_lock_that_passes_is_checked_once_with_the_user_config(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lock made with the user's `exclude-newer` records it, so dropping the
    config for it would report drift."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(subprocess, 'run', recording_run([LockResult(0)], calls))
    assert run_check(LOCKFILE, project(LOCK_PROJECT)) == []
    assert len(calls) == 1
    assert 'env' not in calls[0]


def test_other_drift_is_reported_without_a_retry(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    stale = 'error: The lockfile at `uv.lock` needs to be updated, but `--check` was provided.\n'
    monkeypatch.setattr(subprocess, 'run', recording_run([LockResult(1, stale)], calls))
    hits = run_check(LOCKFILE, project(LOCK_PROJECT))
    assert len(hits) == 1
    assert 'out of date' in hits[0]['variant']
    assert len(calls) == 1


def test_drift_that_remains_without_the_user_config_is_reported(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    stale = 'error: The lockfile at `uv.lock` needs to be updated, but `--check` was provided.\n'
    monkeypatch.setattr(subprocess, 'run', recording_run([LockResult(1, USER_EXCLUDE_NEWER), LockResult(1, stale)], calls))
    hits = run_check(LOCKFILE, project(LOCK_PROJECT))
    assert len(hits) == 1
    assert 'out of date' in hits[0]['variant']


def test_a_missing_uv_is_a_hit(
    project: Builder,
    run_check: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError(2, 'No such file or directory', 'uv')

    monkeypatch.setattr(subprocess, 'run', missing)
    root = project(
        {
            'src/probe/mod.py': 'VALUE = 1\n',
            'pyproject.toml': '[project]\nname = "probe"\n',
            'uv.lock': 'version = 1\n',
        }
    )
    hits = run_check(LOCKFILE, root)
    assert len(hits) == 1
    assert hits[0]['rule'] == 'lockfile-drift'
    assert 'uv' in hits[0]['variant']


# --------------------------------------------------------------------------
# check_ruff_version
# --------------------------------------------------------------------------

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


def drift_hits(run_check: Runner, root: pathlib.Path) -> list[dict]:
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
    auditme.core.EMITTED.clear()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        RUFF_VERSION(root, root / 'src' / 'probe')
        RUFF_VERSION(root, root / 'bin')
    assert len(buffer.getvalue().splitlines()) == 1


# --------------------------------------------------------------------------
# check_phase_section_doc_reference
# --------------------------------------------------------------------------


def test_a_phase_reference_in_a_docstring_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': '"""Runs the Phase 2 sweep."""\n'})
    hits = run_check(PHASE_SECTION, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('phase-section-doc-reference', 1)]
    assert "'Phase 2'" in hits[0]['variant']


def test_a_section_reference_in_a_comment_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': '# see Section 3.1 of the spec\nVALUE = 1\n'})
    assert len(run_check(PHASE_SECTION, root)) == 1


def test_a_phase_reference_in_running_code_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """The rule is about cross-references that rot, not about user-facing text."""
    root = project({'src/probe/mod.py': "LABEL = 'Phase 2'\n"})
    assert run_check(PHASE_SECTION, root) == []


def test_a_file_level_marker_excuses_the_whole_module(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            # auditme: accept phase-section this module renders the user-facing phase vocabulary
            \"\"\"Runs the Phase 2 sweep.\"\"\"

            # and Section 3.1 too
            VALUE = 1
            """
        }
    )
    assert run_check(PHASE_SECTION, root) == []


def test_spec_markdown_files_skip_records_and_hidden_directories(tmp_path: pathlib.Path) -> None:
    for relative in ('README.md', 'docs/spec.md', 'tasks/list.md', 'audit-reviews/review.md', '.claude/worktrees/w/spec.md', 'docs/.hidden/x.md'):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# x\n', encoding='utf-8')
    found = auditme.rules.project_hygiene.spec_markdown_files(tmp_path)
    assert [path.relative_to(tmp_path).as_posix() for path in found] == ['README.md', 'docs/spec.md']


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
    pin = auditme.rules.project_hygiene.ruff_hook_pin(lines)
    if pin is None:
        return
    repo_line, rev_line, version = pin
    assert 1 <= repo_line <= len(lines)
    if rev_line is None:
        assert version is None
    else:
        assert repo_line < rev_line <= len(lines)


def test_ruff_executable_is_resolved_once_per_run(project: Builder, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'.venv/bin/ruff': '#!/bin/sh\n'})
    auditme.core.clear_source_cache()
    calls: list[object] = []
    real = os.access

    def counting(path: object, mode: int) -> bool:
        calls.append(path)
        return real(path, mode)  # type: ignore[arg-type]

    monkeypatch.setattr(os, 'access', counting)
    first = auditme.rules.project_hygiene.ruff_executable(root)
    second = auditme.rules.project_hygiene.ruff_executable(root)
    assert first == second
    assert len(calls) == 1


def make_executable(path: pathlib.Path) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('#!/bin/sh\n')
    path.chmod(0o755)
    return path


def test_auditme_ruff_wins_over_the_project_venv(project: Builder, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    root = project({'.venv/bin/ruff': '#!/bin/sh\n'})
    (root / '.venv' / 'bin' / 'ruff').chmod(0o755)
    shared = make_executable(tmp_path / 'shared' / 'ruff')
    monkeypatch.setenv('AUDITME_RUFF', str(shared))
    auditme.core.clear_source_cache()
    assert auditme.rules.project_hygiene.ruff_executable(root) == (str(shared), 'AUDITME_RUFF')


def unset_or_empty(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv('AUDITME_RUFF', raising=False)
    else:
        monkeypatch.setenv('AUDITME_RUFF', value)
    auditme.core.clear_source_cache()


@pytest.mark.parametrize('value', [None, ''])
def test_unset_or_empty_auditme_ruff_falls_through_to_the_venv(project: Builder, monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    root = project({'.venv/bin/ruff': '#!/bin/sh\n'})
    (root / '.venv' / 'bin' / 'ruff').chmod(0o755)
    unset_or_empty(monkeypatch, value)
    assert auditme.rules.project_hygiene.ruff_executable(root)[1] == '.venv/bin/ruff'


@pytest.mark.parametrize('value', [None, ''])
def test_unset_or_empty_auditme_ruff_falls_through_to_path(project: Builder, monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    root = project({'src/probe/mod.py': 'x = 1\n'})
    unset_or_empty(monkeypatch, value)
    assert auditme.rules.project_hygiene.ruff_executable(root) == ('ruff', 'ruff on PATH')


@pytest.mark.parametrize('kind', ['missing', 'not-executable'])
def test_an_invalid_auditme_ruff_exits_2_before_anything_is_printed(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: pathlib.Path,
    kind: str,
) -> None:
    root = project({'src/probe/mod.py': 'x = 1\n'})
    target = tmp_path / 'ruff'
    if kind == 'not-executable':
        target.write_text('#!/bin/sh\n')
        target.chmod(0o644)
    monkeypatch.setenv('AUDITME_RUFF', str(target))
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])
    assert audit.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err.strip() == f'ERROR: AUDITME_RUFF={target} is not an executable file'
