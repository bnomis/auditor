"""Tests for the sweep driver: scope discovery, crash isolation, end-to-end run.

The driver's job is to hand every check the right scope. Its historical failure
was silent under-coverage - `--package` used to default to the
alphabetically-first directory under `src/`, so a project with both a library
and a test tree had the test tree dropped and the sweep still looked clean.
The same failure had a second instance outside `src/`: scripts in `bin/` were
not swept at all, and three consecutive litrev summaries recorded them as being
at zero unaccepted hits.
"""

import collections.abc
import json
import pathlib
import subprocess
import sys

import audit
import auditme.core
import auditme.registry
import pytest

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]

AUDIT_SCRIPT = pathlib.Path(audit.__file__).resolve()

CHECKS_ROOT = AUDIT_SCRIPT.parent


def test_every_package_under_src_is_discovered(project: Builder) -> None:
    root = project({'src/probe/mod.py': 'x = 1\n', 'src/tests/test_mod.py': 'y = 1\n'})
    assert [path.name for path in auditme.core._packages_under(root / 'src')] == ['probe', 'tests']


def test_caches_and_build_artefacts_are_not_packages(project: Builder) -> None:
    root = project(
        {
            'src/probe/mod.py': 'x = 1\n',
            'src/__pycache__/mod.cpython-314.pyc': 'not python\n',
            'src/probe.egg-info/PKG-INFO': 'Name: probe\n',
            'src/.hidden/mod.py': 'x = 1\n',
            'src/docs/notes.md': 'no python here\n',
        }
    )
    assert [path.name for path in auditme.core._packages_under(root / 'src')] == ['probe']


def test_a_script_root_outside_src_is_audited_as_its_own_pass(project: Builder) -> None:
    """`bin/` is not under `src/`, so package discovery alone never sees it."""
    root = project({'src/probe/mod.py': 'x = 1\n', 'bin/report.py': 'y = 1\n'})
    assert [path.name for path in auditme.core._audit_roots(root)] == ['probe', 'bin']


def test_a_script_root_holding_no_python_is_not_a_pass(project: Builder) -> None:
    """A `bin/` of shell wrappers is not an empty audit; it is no audit."""
    root = project({'src/probe/mod.py': 'x = 1\n', 'bin/activate.sh': 'echo hello\n'})
    assert [path.name for path in auditme.core._audit_roots(root)] == ['probe']


def test_a_project_with_no_script_root_is_swept_unchanged(project: Builder) -> None:
    root = project({'src/probe/mod.py': 'x = 1\n'})
    assert [path.name for path in auditme.core._audit_roots(root)] == ['probe']


def test_a_project_with_only_bin_is_swept_over_bin(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = project({'bin/tool.py': 'def _helper() -> None:\n    pass\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])
    assert audit.main() == 0
    hits = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [(hit['rule'], hit['path']) for hit in hits if hit['rule'] == 'leading-underscore-def-class'] == [('leading-underscore-def-class', 'bin/tool.py')]


def test_an_empty_project_gives_a_notice_and_exit_0(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = project({'src/notes.md': 'no packages here\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])
    assert audit.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'audit.py: no package under src/ and no extra root; nothing to audit' in captured.err


def test_a_scope_that_is_not_a_directory_is_an_error(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(tmp_path / 'absent')])
    assert audit.main() == 2


def test_a_named_package_that_does_not_exist_is_an_error(project: Builder, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'src/probe/mod.py': 'x = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root), '--package', 'absent'])
    assert audit.main() == 2


def test_a_crashing_check_is_reported_and_the_sweep_continues(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One broken predicate must not take the whole sweep down with it."""

    def exploding_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        raise RuntimeError('predicate is broken')

    def working_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        auditme.core._emit(rule='probe', variant='v', path='src/probe/mod.py', line=1, evidence='x', accepted=False, accepted_reason=None)

    monkeypatch.setattr(auditme.registry, 'CHECKS', (exploding_check, working_check))
    root = project({'src/probe/mod.py': 'x = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 0
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    crash = [record for record in records if record['rule'] == 'auditme-check-crash']
    assert [record['variant'] for record in crash] == ['exploding_check']
    assert 'RuntimeError: predicate is broken' in crash[0]['evidence']
    assert [record['rule'] for record in records if record['rule'] == 'probe'] == ['probe']


def test_a_project_level_hit_is_reported_once_per_project_not_once_per_package(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Checks that read AGENTS.md or the lockfile see the project once per package."""

    def project_level_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        auditme.core._emit(rule='lockfile-drift', variant='stale', path='uv.lock', line=None, evidence='x', accepted=False, accepted_reason=None)

    monkeypatch.setattr(auditme.registry, 'CHECKS', (project_level_check,))
    root = project({'src/probe/mod.py': 'x = 1\n', 'src/tests/test_mod.py': 'y = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 0
    assert len(capsys.readouterr().out.splitlines()) == 1


def test_each_package_is_audited_in_its_own_pass(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`src_root.name` is the package's dotted root, so one pass over `src/`
    would rename every module to `src.<pkg>.<mod>`."""
    seen: list[str] = []

    def recording_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        seen.append(src_root.name)

    monkeypatch.setattr(auditme.registry, 'CHECKS', (recording_check,))
    root = project({'src/probe/mod.py': 'x = 1\n', 'src/tests/test_mod.py': 'y = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 0
    assert seen == ['probe', 'tests']
    capsys.readouterr()


def test_the_package_flag_restricts_the_sweep_to_one_package(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen: list[str] = []

    def recording_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        seen.append(src_root.name)

    monkeypatch.setattr(auditme.registry, 'CHECKS', (recording_check,))
    root = project({'src/probe/mod.py': 'x = 1\n', 'src/tests/test_mod.py': 'y = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root), '--package', 'probe'])

    assert audit.main() == 0
    assert seen == ['probe']
    capsys.readouterr()


def test_the_default_sweep_covers_the_script_root_after_the_packages(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`bin/` was previously swept by nothing, so its hits could not exist."""
    seen: list[str] = []

    def recording_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        seen.append(src_root.name)

    monkeypatch.setattr(auditme.registry, 'CHECKS', (recording_check,))
    root = project({'src/probe/mod.py': 'x = 1\n', 'src/tests/test_mod.py': 'y = 1\n', 'bin/report.py': 'z = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 0
    assert seen == ['probe', 'tests', 'bin']
    capsys.readouterr()


def test_the_extra_root_flag_replaces_the_default_script_root(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen: list[str] = []

    def recording_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        seen.append(src_root.name)

    monkeypatch.setattr(auditme.registry, 'CHECKS', (recording_check,))
    root = project({'src/probe/mod.py': 'x = 1\n', 'bin/report.py': 'y = 1\n', 'scripts/tidy.py': 'z = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root), '--extra-root', 'scripts'])

    assert audit.main() == 0
    assert seen == ['probe', 'scripts']
    capsys.readouterr()


def test_a_named_extra_root_that_does_not_exist_is_an_error(project: Builder, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dropping it silently would reinstate the empty pass the flag ends."""
    root = project({'src/probe/mod.py': 'x = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root), '--extra-root', 'absent'])
    assert audit.main() == 2


def test_the_package_flag_drops_the_script_root_too(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--package` asks for one package; it is not a whole-project sweep."""
    seen: list[str] = []

    def recording_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        seen.append(src_root.name)

    monkeypatch.setattr(auditme.registry, 'CHECKS', (recording_check,))
    root = project({'src/probe/mod.py': 'x = 1\n', 'bin/report.py': 'y = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root), '--package', 'probe'])

    assert audit.main() == 0
    assert seen == ['probe']
    capsys.readouterr()


def test_the_shipped_entry_point_emits_parseable_jsonl(project: Builder) -> None:
    """End to end, as the skill documents running it: bare `python3 audit.py`."""
    root = project(
        {
            'src/probe/__init__.py': "__all__: list[str] = ['thing']\n",
            'src/probe/mod.py': """
            import json

            thing = 1


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})
                return usage.get('input_tokens', 0)
            """,
            'src/tests/test_surface.py': """
            import ast


            def declares_all(tree: ast.AST) -> bool:
                return any(isinstance(node, ast.Assign) and node.targets[0].id == '__all__' for node in ast.walk(tree))
            """,
            'bin/probe-report.py': """
            import json


            def report(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})
                return usage.get('input_tokens', 0)
            """,
        }
    )
    result = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), str(root)],
        capture_output=True,
        text=True,
        cwd=str(root),
        env={'PYTHONPATH': str(CHECKS_ROOT), 'PATH': '/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin'},
    )
    assert result.returncode == 0, result.stderr
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert records, 'the sweep produced no output at all'
    assert not [record for record in records if record['rule'] == 'auditme-check-crash'], result.stdout
    for record in records:
        assert set(record) == {'accepted', 'accepted_reason', 'evidence', 'line', 'path', 'rule', 'variant'}
    rules = {record['rule'] for record in records}
    assert 'get-container-default-then-method-call' in rules
    assert 'annotated-all-assignment' in rules
    # The script root reaches the output, rather than being a pass nobody runs.
    assert [record['path'] for record in records if (record['path'] or '').startswith('bin/')], result.stdout
