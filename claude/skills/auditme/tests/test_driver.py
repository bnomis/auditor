"""Tests for the sweep driver: scope discovery, crash isolation, end-to-end run.

The driver's job is to hand every check the right scope. Its historical failure
was silent under-coverage - `--package` used to default to the
alphabetically-first directory under `src/`, so a project with both a library
and a test tree had the test tree dropped and the sweep still looked clean.
The same failure had a second instance outside `src/`: scripts in `bin/` were
not swept at all, and consecutive audit summaries recorded them as being at
zero unaccepted hits.
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
    assert [path.name for path in auditme.core.packages_under(root / 'src')] == ['probe', 'tests']


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
    assert [path.name for path in auditme.core.packages_under(root / 'src')] == ['probe']


def test_a_script_root_outside_src_is_audited_as_its_own_pass(project: Builder) -> None:
    """`bin/` is not under `src/`, so package discovery alone never sees it."""
    root = project({'src/probe/mod.py': 'x = 1\n', 'bin/report.py': 'y = 1\n'})
    assert [path.name for path in auditme.core.audit_roots(root)] == ['probe', 'bin']


def test_a_script_root_holding_no_python_is_not_a_pass(project: Builder) -> None:
    """A `bin/` of shell wrappers is not an empty audit; it is no audit."""
    root = project({'src/probe/mod.py': 'x = 1\n', 'bin/activate.sh': 'echo hello\n'})
    assert [path.name for path in auditme.core.audit_roots(root)] == ['probe']


def test_a_project_with_no_script_root_is_swept_unchanged(project: Builder) -> None:
    root = project({'src/probe/mod.py': 'x = 1\n'})
    assert [path.name for path in auditme.core.audit_roots(root)] == ['probe']


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
    assert 'audit.py: no package under src/ and no extra root; running the project-level checks only' in captured.err


def test_a_project_with_no_root_does_not_sweep_its_venv(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With no root there is no corpus: the project-level checks read no `.py` file."""
    root = project({'docs/index.md': '# Notes\n'})
    (root / '.venv/lib').mkdir(parents=True)
    (root / '.venv/lib/bad.py').write_bytes(b'x = "\xff\xfe"\n')
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 0
    assert [json.loads(line) for line in capsys.readouterr().out.splitlines()] == []


def test_a_project_with_no_root_runs_only_the_project_level_checks_once(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A project with no Python still has a lockfile and a ruff pin to check."""
    calls: list[str] = []

    def per_root_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        calls.append('per_root')

    def project_level_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        calls.append('project')
        auditme.core.emit(rule='lockfile-drift', variant='stale', path='uv.lock', line=None, evidence='x', accepted=False, accepted_reason=None)

    monkeypatch.setattr(auditme.registry, 'CHECKS', (per_root_check,))
    monkeypatch.setattr(auditme.registry, 'PROJECT_CHECKS', (project_level_check,))
    root = project({'docs/index.md': '# Notes\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 0
    assert calls == ['project']
    assert [json.loads(line)['rule'] for line in capsys.readouterr().out.splitlines()] == ['lockfile-drift']


def test_a_crashing_project_level_check_with_no_root_is_reported(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def exploding_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        raise RuntimeError('predicate is broken')

    monkeypatch.setattr(auditme.registry, 'CHECKS', ())
    monkeypatch.setattr(auditme.registry, 'PROJECT_CHECKS', (exploding_check,))
    root = project({'docs/index.md': '# Notes\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 0
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [(record['rule'], record['variant']) for record in records] == [('auditme-check-crash', 'exploding_check')]


def test_the_project_level_checks_are_not_per_root_checks() -> None:
    """A per-root pass would repeat a check that reads only the project."""
    assert {check.__name__ for check in auditme.registry.PROJECT_CHECKS} == {'check_lockfile', 'check_ruff_version', 'check_spec_api_signature_drift'}
    assert not set(auditme.registry.PROJECT_CHECKS) & set(auditme.registry.CHECKS)


def test_with_three_roots_each_project_level_check_runs_once(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def per_root_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        calls.append(f'root:{src_root.name}')

    def project_level_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        calls.append('project')

    monkeypatch.setattr(auditme.registry, 'CHECKS', (per_root_check,))
    monkeypatch.setattr(auditme.registry, 'PROJECT_CHECKS', (project_level_check,))
    root = project({'src/a/m.py': 'x = 1\n', 'src/b/m.py': 'x = 1\n', 'src/c/m.py': 'x = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 0
    assert calls == ['project', 'root:a', 'root:b', 'root:c']


def test_a_project_with_no_python_gets_its_ruff_pin_checked(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """End to end through the real registry: no root, a ruff pin the project's ruff does not match."""
    root = project(
        {
            '.pre-commit-config.yaml': 'repos:\n  - repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: v0.17.3\n    hooks:\n      - id: ruff\n',
            'docs/index.md': '# Notes\n',
        }
    )
    script = root / '.venv' / 'bin' / 'ruff'
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/sh\necho 'ruff 0.17.1'\n")
    script.chmod(0o755)
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 0
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [(record['rule'], record['evidence']) for record in records] == [('ruff-version-drift', '.venv/bin/ruff is 0.17.1; the hook pins v0.17.3')]


def loose_hits(
    root: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *extra: str
) -> tuple[int, list[dict[str, object]], str]:
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root), *extra])
    code = audit.main()
    captured = capsys.readouterr()
    hits = [json.loads(line) for line in captured.out.splitlines()]
    return code, [hit for hit in hits if hit['rule'] == 'src-loose-module'], captured.err


def test_a_loose_src_module_is_reported_and_the_notice_still_prints(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = project({'src/a.py': 'x = 1\n'})
    code, hits, err = loose_hits(root, monkeypatch, capsys)
    assert code == 0
    assert hits == [
        {
            'rule': 'src-loose-module',
            'variant': 'module directly under src/, outside any package',
            'path': 'src/a.py',
            'line': 1,
            'evidence': 'a.py',
            'accepted': False,
            'accepted_reason': None,
        }
    ]
    assert 'running the project-level checks only' in err


def test_a_loose_src_module_is_reported_beside_a_package(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = project({'src/a.py': 'x = 1\n', 'src/probe/mod.py': 'x = 1\n'})
    _, hits, _ = loose_hits(root, monkeypatch, capsys)
    assert [hit['path'] for hit in hits] == ['src/a.py']


def test_a_line_1_marker_accepts_a_loose_src_module(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = project({'src/a.py': '# auditme: accept[src-loose-module] shim kept for old imports\nx = 1\n'})
    _, hits, _ = loose_hits(root, monkeypatch, capsys)
    assert [(hit['accepted'], hit['accepted_reason']) for hit in hits] == [(True, 'shim kept for old imports')]


def test_the_package_flag_emits_no_loose_module_hit(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = project({'src/a.py': 'x = 1\n', 'src/probe/mod.py': 'x = 1\n'})
    _, hits, _ = loose_hits(root, monkeypatch, capsys, '--package', 'probe')
    assert hits == []


def test_loose_src_modules_come_out_sorted(project: Builder) -> None:
    root = project({'src/b.py': 'x = 1\n', 'src/a.py': 'x = 1\n', 'src/probe/mod.py': 'x = 1\n', 'src/notes.md': 'x\n'})
    assert [path.name for path in auditme.core.loose_src_modules(root)] == ['a.py', 'b.py']


def test_loose_src_modules_is_empty_without_src(tmp_path: pathlib.Path) -> None:
    assert auditme.core.loose_src_modules(tmp_path) == []


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
        auditme.core.emit(rule='probe', variant='v', path='src/probe/mod.py', line=1, evidence='x', accepted=False, accepted_reason=None)

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
        auditme.core.emit(rule='lockfile-drift', variant='stale', path='uv.lock', line=None, evidence='x', accepted=False, accepted_reason=None)

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


@pytest.mark.parametrize('extra', ['../outside', '/elsewhere'])
def test_an_extra_root_outside_the_project_is_an_error(
    project: Builder, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], extra: str
) -> None:
    root = project({'src/probe/mod.py': 'x = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root), '--extra-root', extra])
    assert audit.main() == 2
    assert 'is outside' in capsys.readouterr().err


@pytest.mark.parametrize('package', ['../x', 'a/b', '..', '.', '/elsewhere'])
def test_a_package_that_is_not_a_directory_under_src_is_an_error(
    project: Builder, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], package: str
) -> None:
    root = project({'src/probe/mod.py': 'x = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root), '--package', package])
    assert audit.main() == 2
    assert 'directly under src/' in capsys.readouterr().err


def test_a_package_that_is_a_file_is_an_error(project: Builder, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    root = project({'src/pkg': 'not a directory\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root), '--package', 'pkg'])
    assert audit.main() == 2
    assert 'is not a directory' in capsys.readouterr().err


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


DECLARED = '[tool.auditme]\nroots = [{ path = "tools", modules = "top-level" }]\n'


@pytest.fixture(autouse=True)
def restore_driver_globals(monkeypatch: pytest.MonkeyPatch) -> None:
    """`main()` rebinds these for `--extra-root`; give each test the defaults."""
    monkeypatch.setattr(auditme.core, 'EXTRA_ROOT_NAMES', auditme.core.EXTRA_ROOT_NAMES)
    monkeypatch.setattr(auditme.core, 'DECLARATION_IGNORED', False)
    monkeypatch.setattr(auditme.core, 'ROOT_MODULES', auditme.core.ROOT_MODULES)


def test_a_declared_list_is_swept_and_src_is_not(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen: list[str] = []

    def recording_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        seen.append(src_root.name)

    monkeypatch.setattr(auditme.registry, 'CHECKS', (recording_check,))
    root = project({'pyproject.toml': DECLARED, 'tools/run.py': 'x = 1\n', 'src/probe/mod.py': 'y = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 0
    assert seen == ['tools']
    capsys.readouterr()


@pytest.mark.parametrize(
    ('pyproject', 'message'),
    [
        ('[tool.auditme]\nroots = [{ modules = "top-level" }]\n', 'has no path'),
        ('[tool.auditme]\nroots = [{ path = "tools", modules = "flat" }]\n', 'modules must be'),
        ('[tool.auditme]\nroots = [{ path = "absent" }]\n', 'declared root absent not found'),
        ('[tool.auditme]\nroots = [{ path = "tools" }, { path = "tools/sub" }]\n', 'overlap'),
        ('[tool.auditme\n', 'pyproject.toml:'),
    ],
)
def test_an_invalid_declaration_exits_2_with_nothing_on_stdout(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    pyproject: str,
    message: str,
) -> None:
    root = project({'pyproject.toml': pyproject, 'tools/run.py': 'x = 1\n', 'tools/sub/m.py': 'y = 1\n', 'src/a.py': 'z = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 2
    out = capsys.readouterr()
    assert out.out == ''
    assert out.err.startswith('ERROR: ')
    assert message in out.err


def test_a_missing_first_party_entry_exits_2_before_any_hit_is_printed(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def hitting_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        auditme.core.emit(rule='probe', variant='v', path='x.py', line=1, evidence='e', accepted=False, accepted_reason=None)

    monkeypatch.setattr(auditme.registry, 'CHECKS', (hitting_check,))
    root = project({'pyproject.toml': '[tool.auditme]\nfirst-party = ["../lib/src/lib"]\n', 'src/probe/mod.py': 'x = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 2
    out = capsys.readouterr()
    assert out.out == ''
    assert out.err.strip() == 'ERROR: first-party path ../lib/src/lib not found'


def test_the_extra_root_flag_overrides_the_declaration(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen: list[str] = []

    def recording_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        seen.append(src_root.name)

    monkeypatch.setattr(auditme.registry, 'CHECKS', (recording_check,))
    root = project({'pyproject.toml': DECLARED, 'tools/run.py': 'x = 1\n', 'scripts/tidy.py': 'y = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root), '--extra-root', 'scripts'])

    assert audit.main() == 0
    assert seen == ['scripts']
    capsys.readouterr()


def test_a_top_level_root_names_its_files_by_path(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def hitting_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        for path in auditme.core.all_py_files(src_root):
            auditme.core.emit(rule='probe', variant='v', path=path.relative_to(scope).as_posix(), line=1, evidence='e', accepted=False, accepted_reason=None)

    monkeypatch.setattr(auditme.registry, 'CHECKS', (hitting_check,))
    root = project({'pyproject.toml': DECLARED, 'tools/run.py': 'x = 1\n', 'tools/sub/m.py': 'y = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 0
    paths = [json.loads(line)['path'] for line in capsys.readouterr().out.splitlines()]
    assert paths == ['tools/run.py']


def test_an_invalid_declaration_prints_its_cause(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = project({'pyproject.toml': '[tool.auditme\n', 'tools/run.py': 'x = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 2
    err = capsys.readouterr().err
    assert err.startswith('ERROR: pyproject.toml: not valid TOML (')
    assert err.rstrip().endswith(')')


def test_a_file_removed_between_listing_and_reading_is_an_unreadable_hit(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A vanished file is named, and the check's other hits in the root survive."""

    def reading_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        for path in auditme.core.all_py_files(src_root):
            if path.name == 'gone.py':
                path.unlink()
            if auditme.core.read_and_parse(path) is not None:
                auditme.core.emit(rule='probe', variant='v', path=path.name, line=1, evidence='x', accepted=False, accepted_reason=None)

    monkeypatch.setattr(auditme.registry, 'CHECKS', (reading_check,))
    root = project({'src/probe/a_gone.py': 'x = 1\n', 'src/probe/gone.py': 'x = 1\n', 'src/probe/ok.py': 'y = 1\n'})
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 0
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    unreadable = [record for record in records if record['rule'] == 'unreadable-file']
    assert [record['path'] for record in unreadable] == ['src/probe/gone.py']
    assert unreadable[0]['line'] is None
    assert unreadable[0]['accepted'] is False
    assert sorted(record['path'] for record in records if record['rule'] == 'probe') == ['a_gone.py', 'ok.py']


def test_a_file_with_bad_bytes_is_an_unreadable_hit(
    project: Builder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = project({'src/probe/ok.py': 'y = 1\n'})
    (root / 'src' / 'probe' / 'bad.py').write_bytes(b'x = "\xff\xfe"\n')

    def reading_check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        for path in auditme.core.all_py_files(src_root):
            auditme.core.read_and_parse(path)

    monkeypatch.setattr(auditme.registry, 'CHECKS', (reading_check,))
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root)])

    assert audit.main() == 0
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [record['path'] for record in records if record['rule'] == 'unreadable-file'] == ['src/probe/bad.py']


EXTRA_FLAGS = [(), ('--package', 'probe')]

MARKED_DUPLICATE = {
    'src/probe/a.py': "NAMES = ['alpha', 'beta']\n",
    'src/probe/b.py': "# auditme: accept[literal-duplication] probe reason\nLABELS = ['alpha', 'beta']\n",
}


def duplication_hits(root: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *extra: str) -> list[dict[str, object]]:
    monkeypatch.setattr(sys, 'argv', ['audit.py', str(root), *extra])
    audit.main()
    hits = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    return [hit for hit in hits if hit['rule'] == 'literal-duplication' and hit['path'] == 'src/probe/b.py']


@pytest.mark.parametrize('extra', EXTRA_FLAGS)
def test_a_listed_rule_refuses_its_marker(
    project: Builder, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], extra: tuple[str, ...]
) -> None:
    root = project({**MARKED_DUPLICATE, 'pyproject.toml': '[tool.auditme]\nnever-accepted = ["literal-duplication"]\n'})
    (hit,) = duplication_hits(root, monkeypatch, capsys, *extra)
    assert hit['accepted'] is False
    assert hit['accepted_reason'] is None
    assert hit['refused_reason'] == 'probe reason'


@pytest.mark.parametrize('extra', EXTRA_FLAGS)
def test_an_unlisted_rule_keeps_its_marker(
    project: Builder, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], extra: tuple[str, ...]
) -> None:
    root = project(MARKED_DUPLICATE)
    (hit,) = duplication_hits(root, monkeypatch, capsys, *extra)
    assert hit['accepted'] is True
    assert 'refused_reason' not in hit
