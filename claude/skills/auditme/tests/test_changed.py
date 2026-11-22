"""Tests for the changed-files runner, each in a temporary git repository.

Most cases swap `changed.AUDIT_SCRIPT` for a stub that prints canned hits, so
they exercise the runner and not the checker; one case runs the real `audit.py`.
"""

import json
import pathlib
import typing

import changed
import conftest
import hypothesis
import hypothesis.strategies
import pytest

if typing.TYPE_CHECKING:
    import collections.abc


def commit_all(repo: pathlib.Path, message: str) -> None:
    conftest.git(repo, 'add', '-A')
    conftest.git(repo, 'commit', '-q', '-m', message)


def write(repo: pathlib.Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A repository on `main` holding a.py and b.py, with HEAD on branch `feature`."""
    root = tmp_path / 'repo'
    root.mkdir()
    conftest.git(root, 'init', '-q', '-b', 'main')
    write(root, {'src/pkg/a.py': 'a = 1\n', 'src/pkg/b.py': 'b = 1\n'})
    commit_all(root, 'base')
    conftest.git(root, 'checkout', '-q', '-b', 'feature')
    return root


@pytest.fixture
def stub_sweep(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> collections.abc.Callable[..., None]:
    """Return a function that installs a stub `audit.py` printing the given lines."""

    def install(lines: list[str], exit_code: int = 0, sleep: float = 0) -> None:
        script = tmp_path / 'stub-audit.py'
        script.write_text(
            f'import sys, time\ntime.sleep({sleep})\nsys.stdout.write({"".join(line + chr(10) for line in lines)!r})\nsys.exit({exit_code})\n',
            encoding='utf-8',
        )
        monkeypatch.setattr(changed, 'AUDIT_SCRIPT', script)

    return install


def hit(path: str, rule: str = 'demo-rule', related: list[str] | None = None, accepted: bool = False) -> str:
    body: dict[str, object] = {
        'accepted': accepted,
        'accepted_reason': 'because' if accepted else None,
        'evidence': 'x',
        'line': 3,
        'path': path,
        'rule': rule,
        'variant': 'demo variant',
    }
    if related:
        body['related'] = related
    return json.dumps(body, sort_keys=True)


def test_scope_is_the_files_changed_since_the_base(repo, stub_sweep, capsys) -> None:
    write(repo, {'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add c')
    stub_sweep([hit('src/pkg/a.py'), hit('src/pkg/c.py')])
    assert changed.main([str(repo)]) == 1
    out = capsys.readouterr().out
    assert 'src/pkg/c.py:3  demo-rule' in out
    assert 'src/pkg/a.py' not in out
    assert 'SKIP=auditme-changed git commit' in out
    assert '# auditme: accept[<rule>] <reason>' in out


def test_unchanged_file_hit_passes_without_all_and_fails_with_it(repo, stub_sweep) -> None:
    write(repo, {'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add c')
    stub_sweep([hit('src/pkg/a.py')])
    assert changed.main([str(repo)]) == 0
    assert changed.main(['--all', str(repo)]) == 1


def test_staged_file_counts_as_changed(repo, stub_sweep) -> None:
    write(repo, {'src/pkg/c.py': 'c = 1\n'})
    conftest.git(repo, 'add', 'src/pkg/c.py')
    stub_sweep([hit('src/pkg/c.py')])
    assert changed.main([str(repo)]) == 1


def test_accepted_hit_passes(repo, stub_sweep) -> None:
    write(repo, {'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add c')
    stub_sweep([hit('src/pkg/c.py', accepted=True)])
    assert changed.main(['--all', str(repo)]) == 0


def test_hit_on_unchanged_file_is_reported_when_its_peer_changed(repo, stub_sweep, capsys) -> None:
    write(repo, {'src/pkg/b.py': 'b = 2\n'})
    commit_all(repo, 'touch b')
    stub_sweep([hit('src/pkg/a.py', related=['src/pkg/b.py'])])
    assert changed.main([str(repo)]) == 1
    assert 'src/pkg/a.py:3' in capsys.readouterr().out


def test_hit_with_no_changed_path_or_peer_is_not_reported(repo, stub_sweep) -> None:
    write(repo, {'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add c')
    stub_sweep([hit('src/pkg/a.py', related=['src/pkg/b.py'])])
    assert changed.main([str(repo)]) == 0


def test_in_scope_is_pure() -> None:
    scope = frozenset({'x.py'})
    assert changed.in_scope({'path': 'y.py'}, None)
    assert changed.in_scope({'path': 'x.py'}, scope)
    assert changed.in_scope({'path': 'y.py', 'related': ['x.py']}, scope)
    assert not changed.in_scope({'path': 'y.py', 'related': ['z.py']}, scope)
    assert not changed.in_scope({'path': None}, scope)


def test_changed_files_excludes_deletions(repo) -> None:
    conftest.git(repo, 'rm', '-q', 'src/pkg/a.py')
    commit_all(repo, 'remove a')
    write(repo, {'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add c')
    assert changed.changed_files(repo, 'main') == frozenset({'src/pkg/c.py'})


@pytest.mark.parametrize('argv', [['--base', '-x'], ['--base=-x']])
def test_base_starting_with_a_dash_is_refused(repo, stub_sweep, capsys, argv) -> None:
    stub_sweep([hit('src/pkg/a.py')])
    assert changed.main([*argv, str(repo)]) == 1
    assert '--base' in capsys.readouterr().out


def test_no_base_resolves_exits_zero(tmp_path, stub_sweep, capsys) -> None:
    root = tmp_path / 'trunk'
    root.mkdir()
    conftest.git(root, 'init', '-q', '-b', 'trunk')
    write(root, {'a.py': 'a = 1\n'})
    commit_all(root, 'base')
    stub_sweep([hit('a.py')])
    assert changed.main([str(root)]) == 0
    assert 'no diff base resolves' in capsys.readouterr().out


def test_unresolvable_explicit_base_fails(repo, stub_sweep, capsys) -> None:
    stub_sweep([])
    assert changed.main(['--base', 'no-such-ref', str(repo)]) == 1
    assert 'git diff' in capsys.readouterr().out


def test_cwd_failure_is_reported_as_an_error_line(stub_sweep, monkeypatch, capsys) -> None:
    stub_sweep([])

    def broken_cwd() -> None:
        raise OSError('cwd is gone')

    monkeypatch.setattr(pathlib.Path, 'cwd', broken_cwd)
    assert changed.main(['--all']) == 1
    out = capsys.readouterr().out
    assert 'changed.py:' in out
    assert 'cwd is gone' in out
    assert 'Traceback' not in out


def test_resolve_failure_is_reported_as_an_error_line(repo, stub_sweep, monkeypatch, capsys) -> None:
    stub_sweep([])

    def broken_resolve(self: pathlib.Path, strict: bool = False) -> None:
        raise OSError('resolve failed')

    monkeypatch.setattr(pathlib.Path, 'resolve', broken_resolve)
    assert changed.main(['--all', str(repo)]) == 1
    out = capsys.readouterr().out
    assert 'resolve failed' in out
    assert 'Traceback' not in out


def test_sweep_exit_status_fails(repo, stub_sweep, capsys) -> None:
    stub_sweep([], exit_code=2)
    assert changed.main(['--all', str(repo)]) == 1
    assert 'exited 2' in capsys.readouterr().out


def test_sweep_timeout_fails(repo, stub_sweep, monkeypatch, capsys) -> None:
    stub_sweep([], sleep=5)
    monkeypatch.setattr(changed, 'SWEEP_TIMEOUT', 0.5)
    assert changed.main(['--all', str(repo)]) == 1
    assert 'timed out' in capsys.readouterr().out


def test_non_json_line_fails(repo, stub_sweep, capsys) -> None:
    stub_sweep(['this is not json'])
    assert changed.main(['--all', str(repo)]) == 1
    assert 'not JSON' in capsys.readouterr().out


def test_crashed_check_fails_even_when_out_of_scope(repo, stub_sweep, capsys) -> None:
    write(repo, {'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add c')
    stub_sweep([hit('src/pkg/zzz.py', rule='auditme-check-crash')])
    assert changed.main([str(repo)]) == 1
    assert 'crashed' in capsys.readouterr().out


def test_nothing_reportable_changed_skips_the_sweep(repo, stub_sweep, capsys) -> None:
    write(repo, {'notes.txt': 'hello\n', 'tasks/plan.md': 'x\n', '.hidden/y.md': 'x\n'})
    commit_all(repo, 'non-reportable')
    stub_sweep([], exit_code=1)
    assert changed.main([str(repo)]) == 0
    assert 'sweep skipped' in capsys.readouterr().out


@pytest.mark.parametrize(
    ('path', 'expected'),
    [
        ('a.py', True),
        ('docs/setup.md', True),
        ('agents/tasks/t.md', False),
        ('.claude/x.md', False),
        ('uv.lock', True),
        ('sub/uv.lock', True),
        ('data.json', False),
    ],
)
def test_reportable(path: str, expected: bool) -> None:
    assert changed.reportable(path) is expected


def test_end_to_end_against_the_real_checker(tmp_path, capsys) -> None:
    root = tmp_path / 'project'
    root.mkdir()
    conftest.git(root, 'init', '-q', '-b', 'main')
    write(root, {'src/pkg/__init__.py': '', 'src/pkg/old.py': conftest.FUTURE_IMPORT})
    commit_all(root, 'base')
    conftest.git(root, 'checkout', '-q', '-b', 'feature')
    write(root, {'src/pkg/new.py': conftest.FUTURE_IMPORT})
    commit_all(root, 'add new')
    assert changed.main([str(root)]) == 1
    out = capsys.readouterr().out
    assert 'src/pkg/new.py:1  future-annotations' in out
    assert 'old.py' not in out
    assert changed.main(['--all', str(root)]) == 1
    assert 'src/pkg/old.py:1  future-annotations' in capsys.readouterr().out


def test_cross_file_hit_on_an_unchanged_file_fails_when_its_peer_changes(tmp_path, capsys) -> None:
    root = tmp_path / 'project'
    root.mkdir()
    conftest.git(root, 'init', '-q', '-b', 'main')
    write(root, {'src/pkg/__init__.py': '', 'src/pkg/a.py': "NAMES = ('x', 'y', 'z')\n", 'src/pkg/b.py': 'b = 1\n'})
    commit_all(root, 'base')
    conftest.git(root, 'checkout', '-q', '-b', 'feature')
    write(root, {'src/pkg/c.py': 'c = 1\n'})
    commit_all(root, 'unrelated change')
    assert changed.main([str(root)]) == 0
    write(root, {'src/pkg/b.py': "OTHER = ('x', 'y', 'z')\n"})
    commit_all(root, 'copy the literal')
    assert changed.main([str(root)]) == 1
    out = capsys.readouterr().out
    assert 'src/pkg/a.py:1  literal-duplication' in out
    assert 'src/pkg/b.py:1  literal-duplication' in out


def start_script_project(tmp_path: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    """A repository with no `src/package`, a base commit, and `files` committed on `feature`."""
    root = tmp_path / 'project'
    root.mkdir()
    conftest.git(root, 'init', '-q', '-b', 'main')
    write(root, {'README.md': 'x\n'})
    commit_all(root, 'base')
    conftest.git(root, 'checkout', '-q', '-b', 'feature')
    write(root, files)
    commit_all(root, 'add files')
    return root


def test_a_clean_script_in_a_project_without_src_passes(tmp_path) -> None:
    root = start_script_project(tmp_path, {'bin/tool.py': 'TOOL = 1\n'})
    assert changed.main([str(root)]) == 0


def test_a_hit_in_a_script_in_a_project_without_src_fails(tmp_path, capsys) -> None:
    root = start_script_project(tmp_path, {'bin/tool.py': 'def _helper() -> int:\n    return 1\n'})
    assert changed.main([str(root)]) == 1
    out = capsys.readouterr().out
    assert 'bin/tool.py' in out
    assert 'leading-underscore-def-class' in out


def test_a_loose_src_module_fails_until_accepted(tmp_path, capsys) -> None:
    root = start_script_project(tmp_path, {'src/a.py': 'A = 1\n'})
    assert changed.main([str(root)]) == 1
    assert 'src/a.py:1  src-loose-module' in capsys.readouterr().out
    write(root, {'src/a.py': '# auditme: accept[src-loose-module] a single-file script\nA = 1\n'})
    commit_all(root, 'accept the loose module')
    assert changed.main([str(root)]) == 0


def test_all_names_the_push_skip_not_the_commit_skip(repo, stub_sweep, capsys) -> None:
    """`--all` runs as `auditme-all`, on push or in CI, where skipping
    `auditme-changed` on a commit does nothing."""
    stub_sweep([hit('src/pkg/a.py')])
    assert changed.main(['--all', str(repo)]) == 1
    out = capsys.readouterr().out
    assert 'SKIP=auditme-all git push' in out
    assert 'SKIP=auditme-changed' not in out


def test_hits_no_marker_accepts_get_their_own_advice(repo, stub_sweep, capsys) -> None:
    write(repo, {'uv.lock': 'version = 1\n', 'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add lock and c')
    stub_sweep([hit('uv.lock', rule='lockfile-drift'), hit('src/pkg/c.py', rule='ruff')])
    assert changed.main([str(repo)]) == 1
    out = capsys.readouterr().out
    assert 'lockfile-drift: run `uv lock`' in out
    assert '# noqa: <code>' in out
    assert '# auditme: accept[<rule>] <reason>' not in out


def test_marker_advice_is_given_beside_rule_advice(repo, stub_sweep, capsys) -> None:
    write(repo, {'uv.lock': 'version = 1\n', 'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add lock and c')
    stub_sweep([hit('uv.lock', rule='lockfile-drift'), hit('src/pkg/c.py')])
    assert changed.main([str(repo)]) == 1
    out = capsys.readouterr().out
    assert 'lockfile-drift: run `uv lock`' in out
    assert '# auditme: accept[<rule>] <reason>' in out


DECLARED = '[[tool.auditme.roots]]\npath = "lib/pkg"\n'


def test_all_sweeps_a_declared_root_outside_src(tmp_path, capsys) -> None:
    root = start_script_project(
        tmp_path,
        {'pyproject.toml': DECLARED, 'lib/pkg/__init__.py': '', 'lib/pkg/mod.py': conftest.FUTURE_IMPORT},
    )
    assert changed.main(['--all', str(root)]) == 1
    assert 'lib/pkg/mod.py:1  future-annotations' in capsys.readouterr().out


def test_a_malformed_declaration_fails_the_sweep(tmp_path, capsys) -> None:
    root = start_script_project(tmp_path, {'pyproject.toml': '[tool.auditme]\nroots = "lib"\n', 'lib/a.py': 'A = 1\n'})
    assert changed.main(['--all', str(root)]) == 1
    assert 'ERROR: ' in capsys.readouterr().out


ARGV_ITEM = hypothesis.strategies.sampled_from(['--all', 'x.py', '-q', '--base=main', '--base=-x', '--base', 'main', '-v'])


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(argv=hypothesis.strategies.lists(ARGV_ITEM, max_size=5))
def test_option_value_is_flag_matches_the_first_base_occurrence(argv: list[str]) -> None:
    expected = False
    for index, arg in enumerate(argv):
        if arg.startswith('--base='):
            expected = arg.removeprefix('--base=').startswith('-')
            break
        if arg == '--base' and index + 1 < len(argv):
            expected = argv[index + 1].startswith('-')
            break
    assert changed.option_value_is_flag(argv) == expected
    if not any(arg == '--base' or arg.startswith('--base=') for arg in argv):
        assert not changed.option_value_is_flag(argv)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    parts=hypothesis.strategies.lists(hypothesis.strategies.from_regex(r'[a-z]{1,4}', fullmatch=True), max_size=3),
    stem=hypothesis.strategies.from_regex(r'[a-z]{1,5}', fullmatch=True),
    dot=hypothesis.strategies.from_regex(r'\.[a-z]{1,4}', fullmatch=True),
)
def test_reportable_by_suffix_and_dot_directory(parts: list[str], stem: str, dot: str) -> None:
    prefix = '/'.join(parts) + '/' if parts else ''
    assert changed.reportable(f'{prefix}{stem}.py')
    assert changed.reportable(f'{prefix}uv.lock')
    other = f'{prefix}{stem}.txt'
    assert not changed.reportable(other)
    assert not changed.reportable(f'{prefix}{dot}/{stem}.md')
