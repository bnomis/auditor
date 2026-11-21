"""Tests for bin/check-foreign-names.sh, the hook that keeps project names out."""

import pathlib
import subprocess

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / 'bin' / 'check-foreign-names.sh'


def run(tmp_path: pathlib.Path, names: str | None, *files: str) -> subprocess.CompletedProcess[str]:
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(tmp_path / 'home')}
    if names is not None:
        listing = tmp_path / 'names'
        listing.write_text(names)
        env['AUDITOR_FOREIGN_NAMES'] = str(listing)
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


def test_an_allowed_name_does_not_fail(tmp_path: pathlib.Path) -> None:
    # A project that runs the hook on itself allows its own names.
    (tmp_path / 'doc.md').write_text('Acmeproj runs the queue.\n')
    assert run(tmp_path, 'acmeproj\notherproj\n', '--allow=acmeproj', 'doc.md').returncode == 0


def test_an_allowed_name_still_fails_the_others(tmp_path: pathlib.Path) -> None:
    (tmp_path / 'doc.md').write_text('Acmeproj ran an otherproj queue.\n')
    result = run(tmp_path, 'acmeproj\notherproj\n', '--allow=ACMEPROJ', 'doc.md')
    assert result.returncode == 1
    assert 'doc.md:1:' in result.stdout


def test_allowing_every_name_checks_nothing(tmp_path: pathlib.Path) -> None:
    (tmp_path / 'doc.md').write_text('acmeproj\n')
    assert run(tmp_path, 'acmeproj\n', '--allow=acmeproj', 'doc.md').returncode == 0


def test_the_default_list_is_under_config_auditor(tmp_path: pathlib.Path) -> None:
    listing = tmp_path / 'home' / '.config' / 'auditor' / 'foreign-names'
    listing.parent.mkdir(parents=True)
    listing.write_text('acmeproj\n')
    (tmp_path / 'doc.md').write_text('acmeproj\n')
    result = run(tmp_path, None, 'doc.md')
    assert result.returncode == 1
