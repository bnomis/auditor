"""Tests for claude/hooks/auditme-standards.sh, run against a PATH of stubs."""

import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
HOOK = REPO / 'claude' / 'hooks' / 'auditme-standards.sh'
VALID = REPO / 'tests' / 'rulesrepo' / 'fixtures' / 'valid'
BASH = shutil.which('bash')
TOOLS = ('git', 'grep')


def make_tools(tmp_path: pathlib.Path, with_auditor: bool) -> pathlib.Path:
    """A PATH directory holding what the hook needs, and the project's own auditor if asked."""
    tools = tmp_path / 'tools'
    # auditme: accept[build-name-has-side-effect] a fixture builder: making the files is its purpose
    tools.mkdir()
    for name in TOOLS:
        found = shutil.which(name)
        assert found
        (tools / name).symlink_to(found)
    if with_auditor:
        (tools / 'auditor').symlink_to(pathlib.Path(sys.executable).parent / 'auditor')
    return tools


# auditme: accept[paired-sibling-helpers] each hook's test file stays self-contained, as the tests directory has no shared module
def make_repo(tmp_path: pathlib.Path, opted_in: bool) -> pathlib.Path:
    repo = tmp_path / 'repo'
    # auditme: accept[build-name-has-side-effect] a fixture builder: making the files is its purpose
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    if opted_in:
        (repo / '.pre-commit-config.yaml').write_text('repos:\n  - hooks:\n      - id: auditme-changed\n')
    return repo


def run(tmp_path: pathlib.Path, cwd: pathlib.Path, rules_path: pathlib.Path | None, with_auditor: bool = True) -> subprocess.CompletedProcess[str]:
    env = {'HOME': str(tmp_path / 'home'), 'PATH': str(make_tools(tmp_path, with_auditor))}
    if rules_path is not None:
        env['AUDITOR_RULES_PATH'] = str(rules_path)
    return subprocess.run([str(BASH), str(HOOK)], capture_output=True, text=True, cwd=cwd, env=env, check=False)


def test_a_valid_repository_prints_its_standards(tmp_path: pathlib.Path) -> None:
    result = run(tmp_path, make_repo(tmp_path, True), VALID)
    assert result.returncode == 0
    assert result.stdout.strip()
    assert 'ERROR:' not in result.stdout


def test_an_unset_variable_prints_the_error_line(tmp_path: pathlib.Path) -> None:
    result = run(tmp_path, make_repo(tmp_path, True), None)
    assert result.returncode == 0
    assert result.stdout.startswith('ERROR: AUDITOR_RULES_PATH is not set')


def test_an_invalid_repository_prints_the_error_line(tmp_path: pathlib.Path) -> None:
    result = run(tmp_path, make_repo(tmp_path, True), tmp_path / 'missing')
    assert result.returncode == 0
    assert result.stdout.startswith('ERROR:')


def test_a_missing_auditor_prints_the_error_line(tmp_path: pathlib.Path) -> None:
    result = run(tmp_path, make_repo(tmp_path, True), VALID, with_auditor=False)
    assert result.returncode == 0
    assert result.stdout.startswith('ERROR: the auditor CLI is not installed')


def test_a_project_that_has_not_opted_in_prints_nothing(tmp_path: pathlib.Path) -> None:
    result = run(tmp_path, make_repo(tmp_path, False), VALID)
    assert result.returncode == 0
    assert result.stdout == ''


def test_a_directory_outside_a_repository_prints_nothing(tmp_path: pathlib.Path) -> None:
    result = run(tmp_path, tmp_path, VALID)
    assert result.returncode == 0
    assert result.stdout == ''
