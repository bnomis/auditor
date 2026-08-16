"""Tests for the project-level predicates: ruff, the lockfile, spec references."""

import collections.abc
import pathlib
import subprocess

import auditme.rules.project_hygiene
import pytest

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

RUFF = auditme.rules.project_hygiene.check_ruff
LOCKFILE = auditme.rules.project_hygiene.check_lockfile
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
