"""Tests that pre-commit installs and runs the published audit hooks from this checkout.

The manifest's fields are tested in `tests/test_published_hooks.py`.
"""

import os
import pathlib
import shutil
import subprocess

import conftest
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / '.pre-commit-hooks.yaml'


def make_hook_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A copy of the manifest and the package, committed, for try-repo to install and run."""
    root = tmp_path / 'hooks'
    # auditme: accept[build-name-has-side-effect] a fixture builder: making the files is its purpose
    root.mkdir()
    # The package needs Python 3.14 (pyproject.toml's requires-python), and the machine's default python3 may be newer.
    manifest = MANIFEST.read_text(encoding='utf-8').replace('language: python\n', 'language: python\n  language_version: python3.14\n')
    (root / '.pre-commit-hooks.yaml').write_text(manifest, encoding='utf-8')
    shutil.copy(REPO_ROOT / 'pyproject.toml', root / 'pyproject.toml')
    shutil.copytree(REPO_ROOT / 'src', root / 'src', ignore=shutil.ignore_patterns('__pycache__'))
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
