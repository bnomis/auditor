"""Tests for `.pre-commit-hooks.yaml`, the manifest that publishes the hooks.

The manifest has a flat shape, so a minimal reader stands in for a YAML
parser: the checker is stdlib-only and so are its tests.
"""

import os
import pathlib
import shlex
import shutil
import subprocess

import conftest
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
MANIFEST = REPO_ROOT / '.pre-commit-hooks.yaml'

COMMON = {
    'always_run': 'true',
    'language': 'script',
    'pass_filenames': 'false',
}

EXPECTED = {
    'auditme-all': {
        'entry': 'claude/skills/auditme/checks/changed.py --all',
        'stages': '[manual]',
    },
    'auditme-changed': {
        'entry': 'claude/skills/auditme/checks/changed.py',
        'stages': '[pre-commit]',
    },
}


def read_manifest() -> dict[str, dict[str, str]]:
    hooks: dict[str, dict[str, str]] = {}
    current: dict[str, str] = {}
    for line in MANIFEST.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        text = line.removeprefix('- ').strip()
        key, _, value = text.partition(':')
        if line.startswith('- '):
            current = {}
        current[key.strip()] = value.strip()
        if key.strip() == 'id':
            hooks[current['id']] = current
    return hooks


def test_manifest_publishes_the_audit_hooks() -> None:
    hooks = read_manifest()
    assert set(EXPECTED) <= set(hooks)
    for hook_id, expected in EXPECTED.items():
        hook = hooks[hook_id]
        assert hook['entry'] == expected['entry']
        assert hook['stages'] == expected['stages']
        assert {key: hook[key] for key in COMMON} == COMMON


@pytest.mark.parametrize('hook_id', sorted(EXPECTED))
def test_entry_script_is_executable_in_the_index(hook_id: str) -> None:
    script = shlex.split(read_manifest()[hook_id]['entry'])[0]
    assert (REPO_ROOT / script).is_file()
    staged = subprocess.run(
        ['git', 'ls-files', '-s', script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert staged.startswith('100755 ')


def make_hook_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A copy of the manifest and the checker, committed, for try-repo to run."""
    root = tmp_path / 'hooks'
    # auditme: accept[build-name-has-side-effect] a fixture builder: making the files is its purpose
    root.mkdir()
    shutil.copy(MANIFEST, root / '.pre-commit-hooks.yaml')
    checks = REPO_ROOT / 'claude' / 'skills' / 'auditme' / 'checks'
    shutil.copytree(
        checks,
        root / 'claude' / 'skills' / 'auditme' / 'checks',
        ignore=shutil.ignore_patterns('__pycache__'),
    )
    conftest.git(root, 'init', '-q', '-b', 'main')
    conftest.git(root, 'add', '-A')
    conftest.git(root, 'commit', '-q', '-m', 'hooks')
    return root


def make_project(tmp_path: pathlib.Path) -> pathlib.Path:
    """A project whose last commit touches a file other than the one with the hit."""
    root = tmp_path / 'project'
    # auditme: accept[build-name-has-side-effect] a fixture builder: making the files is its purpose
    (root / 'src' / 'pkg').mkdir(parents=True)
    (root / 'src' / 'pkg' / '__init__.py').write_text('', encoding='utf-8')
    (root / 'src' / 'pkg' / 'old.py').write_text(conftest.FUTURE_IMPORT, encoding='utf-8')
    conftest.git(root, 'init', '-q', '-b', 'main')
    conftest.git(root, 'add', '-A')
    conftest.git(root, 'commit', '-q', '-m', 'base')
    (root / 'src' / 'pkg' / 'other.py').write_text('x = 1\n', encoding='utf-8')
    conftest.git(root, 'add', '-A')
    conftest.git(root, 'commit', '-q', '-m', 'touch another file')
    return root


@pytest.mark.skipif(shutil.which('pre-commit') is None, reason='pre-commit is not on PATH')
def test_try_repo_runs_both_hooks_and_all_sees_untouched_files(tmp_path: pathlib.Path) -> None:
    hook_repo = make_hook_repo(tmp_path)
    project = make_project(tmp_path)
    env = {**os.environ, 'PRE_COMMIT_HOME': str(tmp_path / 'cache')}

    def try_repo(hook_id: str, stage: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ['pre-commit', 'try-repo', str(hook_repo), hook_id, '--hook-stage', stage, '--all-files'],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
        )

    everything = try_repo('auditme-all', 'manual')
    assert everything.returncode != 0
    assert 'src/pkg/old.py:1  future-annotations' in everything.stdout + everything.stderr

    changed = try_repo('auditme-changed', 'pre-commit')
    assert changed.returncode == 0, changed.stdout + changed.stderr
