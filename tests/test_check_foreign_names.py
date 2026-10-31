"""Tests for bin/check-foreign-names.sh, the hook that keeps project names out."""

import pathlib
import subprocess

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / 'bin' / 'check-foreign-names.sh'


def run(tmp_path: pathlib.Path, names: str | None, *files: str) -> subprocess.CompletedProcess[str]:
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(tmp_path / 'home')}
    if names is not None:
        listing = tmp_path / 'names'
        listing.write_text(names)
        env['AGENTS_FOREIGN_NAMES'] = str(listing)
    return subprocess.run(['bash', str(SCRIPT), *files], capture_output=True, text=True, env=env, cwd=tmp_path, check=False)


def test_a_file_naming_a_listed_project_fails(tmp_path: pathlib.Path) -> None:
    (tmp_path / 'doc.md').write_text('On the Acmeproj project the sweep missed it.\n')
    result = run(tmp_path, '# projects\nacmeproj\n\n', 'doc.md')
    assert result.returncode == 1
    assert 'doc.md:1:' in result.stdout


def test_a_name_inside_a_longer_word_does_not_fail(tmp_path: pathlib.Path) -> None:
    (tmp_path / 'doc.md').write_text('acmeprojects is a different word.\n')
    assert run(tmp_path, 'acmeproj\n', 'doc.md').returncode == 0


def test_a_clean_file_passes(tmp_path: pathlib.Path) -> None:
    (tmp_path / 'doc.md').write_text('On one project the sweep missed it.\n')
    assert run(tmp_path, 'acmeproj\n', 'doc.md').returncode == 0


def test_no_list_checks_nothing_and_says_so(tmp_path: pathlib.Path) -> None:
    (tmp_path / 'doc.md').write_text('acmeproj\n')
    result = run(tmp_path, None, 'doc.md')
    assert result.returncode == 0
    assert 'no list' in result.stderr


def test_a_list_of_only_comments_checks_nothing(tmp_path: pathlib.Path) -> None:
    (tmp_path / 'doc.md').write_text('acmeproj\n')
    assert run(tmp_path, '# none yet\n', 'doc.md').returncode == 0
