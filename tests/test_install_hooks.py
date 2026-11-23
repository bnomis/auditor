"""Tests for bin/install-hooks.sh, which adds or updates the auditor block in a repository's pre-commit config."""

import pathlib
import subprocess

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / 'bin' / 'install-hooks.sh'
OLD = 'abc1111'
NEW = 'def2222'

RUFF = """repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.17.3
    hooks:
      - id: ruff-check
"""

PINNED = f"""repos:
  - repo: git@github.com:bnomis/auditor.git
    rev: {OLD}
    hooks:
      - id: auditme-changed
      - id: auditme-all
        stages: [manual, pre-push]

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.17.3
    hooks:
      - id: ruff-check
"""


def run(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    # No pre-commit on this PATH, so the script skips validation; tests pass --no-install.
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(repo.parent / 'home')}
    return subprocess.run(['bash', str(SCRIPT), *args], capture_output=True, text=True, env=env, cwd=repo, check=False)


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    path = tmp_path / 'repo'
    subprocess.run(['git', 'init', '-q', str(path)], check=True)
    return path


def config(repo: pathlib.Path) -> str:
    return (repo / '.pre-commit-config.yaml').read_text(encoding='utf-8')


def write_config(repo: pathlib.Path, text: str) -> None:
    (repo / '.pre-commit-config.yaml').write_text(text, encoding='utf-8')


def test_a_repository_with_no_config_gets_one(repo: pathlib.Path) -> None:
    result = run(repo, '--rev', NEW, '--no-install')
    assert result.returncode == 0, result.stderr
    assert (
        config(repo)
        == f'repos:\n  - repo: git@github.com:bnomis/auditor.git\n    rev: {NEW}\n    hooks:\n      - id: auditme-changed\n      - id: auditme-all\n'
    )


def test_the_block_is_added_at_the_end_of_the_repos_list(repo: pathlib.Path) -> None:
    write_config(repo, RUFF)
    assert run(repo, '--rev', NEW, '--no-install').returncode == 0
    assert (
        config(repo)
        == RUFF + f'\n  - repo: git@github.com:bnomis/auditor.git\n    rev: {NEW}\n    hooks:\n      - id: auditme-changed\n      - id: auditme-all\n'
    )


def test_an_empty_repos_list_gets_the_block_straight_after_it(repo: pathlib.Path) -> None:
    write_config(repo, 'repos:\n')
    assert run(repo, '--rev', NEW, '--no-install').returncode == 0
    assert config(repo).startswith('repos:\n  - repo: git@github.com:bnomis/auditor.git\n')


def test_the_block_goes_before_a_top_level_key_after_the_list(repo: pathlib.Path) -> None:
    write_config(repo, RUFF + '\ndefault_stages: [pre-commit]\n')
    assert run(repo, '--rev', NEW, '--no-install').returncode == 0
    text = config(repo)
    assert text.index('bnomis/auditor.git') < text.index('default_stages:')
    assert text.endswith('      - id: auditme-all\n\ndefault_stages: [pre-commit]\n')


def test_the_block_follows_the_list_indentation(repo: pathlib.Path) -> None:
    write_config(repo, 'repos:\n- repo: https://github.com/astral-sh/ruff-pre-commit\n  rev: v0.17.3\n  hooks:\n  - id: ruff-check\n')
    assert run(repo, '--rev', NEW, '--no-install').returncode == 0
    assert f'\n- repo: git@github.com:bnomis/auditor.git\n  rev: {NEW}\n  hooks:\n    - id: auditme-changed\n' in config(repo)


def test_push_runs_the_whole_tree_sweep_on_push(repo: pathlib.Path) -> None:
    assert run(repo, '--rev', NEW, '--push', '--no-install').returncode == 0
    assert config(repo).endswith('      - id: auditme-all\n        stages: [manual, pre-push]\n')


def test_an_existing_block_moves_to_the_new_rev_and_nothing_else_changes(repo: pathlib.Path) -> None:
    write_config(repo, PINNED)
    result = run(repo, '--rev', NEW, '--no-install')
    assert result.returncode == 0, result.stderr
    assert config(repo) == PINNED.replace(f'rev: {OLD}', f'rev: {NEW}')
    assert f'moved the auditor hooks from {OLD} to {NEW}' in result.stdout


def test_a_rev_comment_is_replaced_with_the_rev(repo: pathlib.Path) -> None:
    write_config(repo, PINNED.replace(f'rev: {OLD}', f'rev: {OLD}  # frozen: main'))
    assert run(repo, '--rev', NEW, '--no-install').returncode == 0
    assert f'    rev: {NEW}\n' in config(repo)


def test_a_block_missing_a_hook_gets_it(repo: pathlib.Path) -> None:
    write_config(repo, PINNED.replace('      - id: auditme-all\n        stages: [manual, pre-push]\n', ''))
    assert run(repo, '--rev', NEW, '--no-install').returncode == 0
    assert f'    rev: {NEW}\n    hooks:\n      - id: auditme-all\n      - id: auditme-changed\n' in config(repo)


def test_a_second_run_changes_nothing(repo: pathlib.Path) -> None:
    write_config(repo, PINNED)
    assert run(repo, '--rev', NEW, '--no-install').returncode == 0
    before = config(repo)
    result = run(repo, '--rev', NEW, '--no-install')
    assert result.returncode == 0
    assert config(repo) == before
    assert 'is unchanged' in result.stdout


def test_a_dry_run_prints_the_diff_and_writes_nothing(repo: pathlib.Path) -> None:
    write_config(repo, PINNED)
    result = run(repo, '--rev', NEW, '--dry-run')
    assert result.returncode == 0
    assert f'+    rev: {NEW}' in result.stdout
    assert config(repo) == PINNED


def test_a_pin_from_the_agents_repository_is_refused(repo: pathlib.Path) -> None:
    write_config(repo, PINNED.replace('bnomis/auditor.git', 'bnomis/agents.git'))
    result = run(repo, '--rev', NEW, '--no-install')
    assert result.returncode == 1
    assert 'Moving a project from agents' in result.stderr
    assert 'bnomis/agents.git' in config(repo)


def test_two_auditor_blocks_are_refused(repo: pathlib.Path) -> None:
    write_config(repo, PINNED + PINNED.removeprefix('repos:\n'))
    assert run(repo, '--rev', NEW, '--no-install').returncode == 1


def test_an_inline_repos_list_is_refused(repo: pathlib.Path) -> None:
    write_config(repo, 'repos: []\n')
    result = run(repo, '--rev', NEW, '--no-install')
    assert result.returncode == 1
    assert config(repo) == 'repos: []\n'


@pytest.mark.parametrize('rev', ['main', 'v1.0', 'abc12'])
def test_a_rev_that_is_not_a_commit_hash_is_refused(repo: pathlib.Path, rev: str) -> None:
    assert run(repo, '--rev', rev, '--no-install').returncode == 2


def test_a_directory_outside_git_is_refused(tmp_path: pathlib.Path) -> None:
    plain = tmp_path / 'plain'
    plain.mkdir()
    result = run(plain, '--rev', NEW, '--no-install')
    assert result.returncode == 2
    assert 'not a git repository' in result.stderr


def test_an_unknown_option_is_refused(repo: pathlib.Path) -> None:
    assert run(repo, '--force').returncode == 2


def test_installing_without_pre_commit_fails_before_writing(repo: pathlib.Path) -> None:
    result = run(repo, '--rev', NEW)
    assert result.returncode == 1
    assert 'pre-commit is not installed' in result.stderr
    assert not (repo / '.pre-commit-config.yaml').exists()


def test_the_repository_path_can_be_given(repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    assert run(elsewhere, '--rev', NEW, '--no-install', str(repo)).returncode == 0
    assert f'rev: {NEW}' in config(repo)
