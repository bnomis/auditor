"""Tests for the changed-files runner, each in a temporary git repository.

Most cases swap `auditor.changed.SWEEP_COMMAND` for a stub that prints canned hits, so
they exercise the runner and not the checker; one case runs the real `audit.py`.
"""

import json
import pathlib
import sys
import typing

import conftest
import hypothesis
import hypothesis.strategies
import pytest

import auditor.changed

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
        monkeypatch.setattr(auditor.changed, 'SWEEP_COMMAND', [sys.executable, str(script)])

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
    assert auditor.changed.main([str(repo)]) == 1
    out = capsys.readouterr().out
    assert 'src/pkg/c.py:3  demo-rule' in out
    assert 'src/pkg/a.py' not in out
    assert 'SKIP=auditme-changed git commit' in out
    assert '# auditme: accept[<rule>] <reason>' in out


def test_unchanged_file_hit_passes_without_all_and_fails_with_it(repo, stub_sweep) -> None:
    write(repo, {'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add c')
    stub_sweep([hit('src/pkg/a.py')])
    assert auditor.changed.main([str(repo)]) == 0
    assert auditor.changed.main(['--all', str(repo)]) == 1


def test_staged_file_counts_as_changed(repo, stub_sweep) -> None:
    write(repo, {'src/pkg/c.py': 'c = 1\n'})
    conftest.git(repo, 'add', 'src/pkg/c.py')
    stub_sweep([hit('src/pkg/c.py')])
    assert auditor.changed.main([str(repo)]) == 1


def test_accepted_hit_passes(repo, stub_sweep) -> None:
    write(repo, {'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add c')
    stub_sweep([hit('src/pkg/c.py', accepted=True)])
    assert auditor.changed.main(['--all', str(repo)]) == 0


def test_hit_on_unchanged_file_is_reported_when_its_peer_changed(repo, stub_sweep, capsys) -> None:
    write(repo, {'src/pkg/b.py': 'b = 2\n'})
    commit_all(repo, 'touch b')
    stub_sweep([hit('src/pkg/a.py', related=['src/pkg/b.py'])])
    assert auditor.changed.main([str(repo)]) == 1
    assert 'src/pkg/a.py:3' in capsys.readouterr().out


def test_hit_with_no_changed_path_or_peer_is_not_reported(repo, stub_sweep) -> None:
    write(repo, {'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add c')
    stub_sweep([hit('src/pkg/a.py', related=['src/pkg/b.py'])])
    assert auditor.changed.main([str(repo)]) == 0


def test_in_scope_is_pure() -> None:
    scope = frozenset({'x.py'})
    assert auditor.changed.in_scope({'path': 'y.py'}, None)
    assert auditor.changed.in_scope({'path': 'x.py'}, scope)
    assert auditor.changed.in_scope({'path': 'y.py', 'related': ['x.py']}, scope)
    assert not auditor.changed.in_scope({'path': 'y.py', 'related': ['z.py']}, scope)
    assert not auditor.changed.in_scope({'path': None}, scope)


def test_changed_files_excludes_deletions(repo) -> None:
    conftest.git(repo, 'rm', '-q', 'src/pkg/a.py')
    commit_all(repo, 'remove a')
    write(repo, {'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add c')
    assert auditor.changed.changed_files(repo, 'main') == frozenset({'src/pkg/c.py'})


@pytest.mark.parametrize(
    'argv',
    [['--base', '-x'], ['--base=-x'], ['--bas=-x'], ['--base', 'main', '--base=-x']],
)
def test_base_starting_with_a_dash_is_refused(repo, stub_sweep, capsys, monkeypatch, argv) -> None:
    stub_sweep([hit('src/pkg/a.py')])
    calls: list[tuple[str, ...]] = []
    real = auditor.changed.run_git

    def spy(root, *args):
        calls.append(args)
        return real(root, *args)

    monkeypatch.setattr(auditor.changed, 'run_git', spy)
    assert auditor.changed.main([*argv, str(repo)]) == 1
    captured = capsys.readouterr()
    assert '--base' in captured.out + captured.err
    assert not [call for call in calls if call[0] == 'diff']


def test_changed_files_ends_options_before_the_base(repo) -> None:
    with pytest.raises(auditor.changed.ChangedError):
        auditor.changed.changed_files(repo, '--output=should-not-exist')
    assert not (repo / 'should-not-exist...HEAD').exists()


def test_no_base_resolves_exits_zero(tmp_path, stub_sweep, capsys) -> None:
    root = tmp_path / 'trunk'
    root.mkdir()
    conftest.git(root, 'init', '-q', '-b', 'trunk')
    write(root, {'a.py': 'a = 1\n'})
    commit_all(root, 'base')
    stub_sweep([hit('a.py')])
    assert auditor.changed.main([str(root)]) == 0
    assert 'no diff base resolves' in capsys.readouterr().out


def test_unresolvable_explicit_base_fails(repo, stub_sweep, capsys) -> None:
    stub_sweep([])
    assert auditor.changed.main(['--base', 'no-such-ref', str(repo)]) == 1
    assert 'git diff' in capsys.readouterr().out


def test_cwd_failure_is_reported_as_an_error_line(stub_sweep, monkeypatch, capsys) -> None:
    stub_sweep([])

    def broken_cwd() -> None:
        raise OSError('cwd is gone')

    monkeypatch.setattr(pathlib.Path, 'cwd', broken_cwd)
    assert auditor.changed.main(['--all']) == 1
    out = capsys.readouterr().out
    assert 'changed.py:' in out
    assert 'cwd is gone' in out
    assert 'Traceback' not in out


def test_resolve_failure_is_reported_as_an_error_line(repo, stub_sweep, monkeypatch, capsys) -> None:
    stub_sweep([])

    def broken_resolve(self: pathlib.Path, strict: bool = False) -> None:
        raise OSError('resolve failed')

    monkeypatch.setattr(pathlib.Path, 'resolve', broken_resolve)
    assert auditor.changed.main(['--all', str(repo)]) == 1
    out = capsys.readouterr().out
    assert 'resolve failed' in out
    assert 'Traceback' not in out


def test_sweep_exit_status_fails(repo, stub_sweep, capsys) -> None:
    stub_sweep([], exit_code=2)
    assert auditor.changed.main(['--all', str(repo)]) == 1
    assert 'exited 2' in capsys.readouterr().out


def test_sweep_timeout_fails(repo, stub_sweep, monkeypatch, capsys) -> None:
    stub_sweep([], sleep=5)
    monkeypatch.setattr(auditor.changed, 'SWEEP_TIMEOUT', 0.5)
    assert auditor.changed.main(['--all', str(repo)]) == 1
    assert 'timed out' in capsys.readouterr().out


def test_non_json_line_fails(repo, stub_sweep, capsys) -> None:
    stub_sweep(['this is not json'])
    assert auditor.changed.main(['--all', str(repo)]) == 1
    assert 'not JSON' in capsys.readouterr().out


def test_crashed_check_fails_even_when_out_of_scope(repo, stub_sweep, capsys) -> None:
    write(repo, {'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add c')
    stub_sweep([hit('src/pkg/zzz.py', rule='auditme-check-crash')])
    assert auditor.changed.main([str(repo)]) == 1
    assert 'crashed' in capsys.readouterr().out


def test_nothing_reportable_changed_skips_the_sweep(repo, stub_sweep, capsys) -> None:
    write(repo, {'notes.txt': 'hello\n', 'tasks/plan.md': 'x\n', '.hidden/y.md': 'x\n'})
    commit_all(repo, 'non-reportable')
    stub_sweep([], exit_code=1)
    assert auditor.changed.main([str(repo)]) == 0
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
    assert auditor.changed.reportable(path) is expected


def test_end_to_end_against_the_real_checker(tmp_path, capsys) -> None:
    root = tmp_path / 'project'
    root.mkdir()
    conftest.git(root, 'init', '-q', '-b', 'main')
    write(root, {'src/pkg/__init__.py': '', 'src/pkg/old.py': conftest.FUTURE_IMPORT})
    commit_all(root, 'base')
    conftest.git(root, 'checkout', '-q', '-b', 'feature')
    write(root, {'src/pkg/new.py': conftest.FUTURE_IMPORT})
    commit_all(root, 'add new')
    assert auditor.changed.main([str(root)]) == 1
    out = capsys.readouterr().out
    assert 'src/pkg/new.py:1  future-annotations' in out
    assert 'old.py' not in out
    assert auditor.changed.main(['--all', str(root)]) == 1
    assert 'src/pkg/old.py:1  future-annotations' in capsys.readouterr().out


def never_accepted_project(tmp_path: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    root = tmp_path / 'project'
    root.mkdir()
    conftest.git(root, 'init', '-q', '-b', 'main')
    write(root, {'pyproject.toml': '[tool.auditme]\nnever-accepted = ["literal-duplication"]\n', 'src/probe/__init__.py': ''})
    commit_all(root, 'base')
    conftest.git(root, 'checkout', '-q', '-b', 'feature')
    write(root, files)
    commit_all(root, 'add files')
    return root


REFUSED_ADVICE = 'literal-duplication: this project does not accept markers for this rule ([tool.auditme] never-accepted); fix the code.'


def test_a_refused_marker_names_the_never_accepted_rule(tmp_path, capsys) -> None:
    root = never_accepted_project(
        tmp_path,
        {
            'src/probe/a.py': "NAMES = ['alpha', 'beta']\n",
            'src/probe/b.py': "# auditme: accept[literal-duplication] probe reason\nLABELS = ['alpha', 'beta']\n",
        },
    )
    assert auditor.changed.main(['--all', str(root)]) == 1
    out = capsys.readouterr().out
    assert 'src/probe/b.py:2  literal-duplication' in out
    assert out.count(REFUSED_ADVICE) == 1
    assert 'auditme: accept[<rule>]' not in out


def test_two_refused_hits_of_one_rule_print_the_advice_once(tmp_path, capsys) -> None:
    root = never_accepted_project(
        tmp_path,
        {
            'src/probe/a.py': "# auditme: accept[literal-duplication] one\nNAMES = ['alpha', 'beta']\n",
            'src/probe/b.py': "# auditme: accept[literal-duplication] two\nLABELS = ['alpha', 'beta']\n",
        },
    )
    assert auditor.changed.main(['--all', str(root)]) == 1
    out = capsys.readouterr().out
    assert out.count('literal-duplication  ') + out.count('  literal-duplication') >= 2
    assert out.count(REFUSED_ADVICE) == 1


def test_a_hit_without_refused_reason_gets_the_generic_advice(repo, stub_sweep, capsys) -> None:
    stub_sweep([hit('src/pkg/a.py')])
    assert auditor.changed.main(['--all', str(repo)]) == 1
    out = capsys.readouterr().out
    assert 'auditme: accept[<rule>]' in out
    assert 'never-accepted' not in out


def test_cross_file_hit_on_an_unchanged_file_fails_when_its_peer_changes(tmp_path, capsys) -> None:
    root = tmp_path / 'project'
    root.mkdir()
    conftest.git(root, 'init', '-q', '-b', 'main')
    write(root, {'src/pkg/__init__.py': '', 'src/pkg/a.py': "NAMES = ('x', 'y', 'z')\n", 'src/pkg/b.py': 'b = 1\n'})
    commit_all(root, 'base')
    conftest.git(root, 'checkout', '-q', '-b', 'feature')
    write(root, {'src/pkg/c.py': 'c = 1\n'})
    commit_all(root, 'unrelated change')
    assert auditor.changed.main([str(root)]) == 0
    write(root, {'src/pkg/b.py': "OTHER = ('x', 'y', 'z')\n"})
    commit_all(root, 'copy the literal')
    assert auditor.changed.main([str(root)]) == 1
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
    assert auditor.changed.main([str(root)]) == 0


def test_a_hit_in_a_script_in_a_project_without_src_fails(tmp_path, capsys) -> None:
    root = start_script_project(tmp_path, {'bin/tool.py': 'def _helper() -> int:\n    return 1\n'})
    assert auditor.changed.main([str(root)]) == 1
    out = capsys.readouterr().out
    assert 'bin/tool.py' in out
    assert 'leading-underscore-def-class' in out


def test_a_loose_src_module_fails_until_accepted(tmp_path, capsys) -> None:
    root = start_script_project(tmp_path, {'src/a.py': 'A = 1\n'})
    assert auditor.changed.main([str(root)]) == 1
    assert 'src/a.py:1  src-loose-module' in capsys.readouterr().out
    write(root, {'src/a.py': '# auditme: accept[src-loose-module] a single-file script\nA = 1\n'})
    commit_all(root, 'accept the loose module')
    assert auditor.changed.main([str(root)]) == 0


def test_all_names_the_push_skip_not_the_commit_skip(repo, stub_sweep, capsys) -> None:
    """`--all` runs as `auditme-all`, on push or in CI, where skipping
    `auditme-changed` on a commit does nothing."""
    stub_sweep([hit('src/pkg/a.py')])
    assert auditor.changed.main(['--all', str(repo)]) == 1
    out = capsys.readouterr().out
    assert 'SKIP=auditme-all git push' in out
    assert 'SKIP=auditme-changed' not in out


def test_hits_no_marker_accepts_get_their_own_advice(repo, stub_sweep, capsys) -> None:
    write(repo, {'uv.lock': 'version = 1\n', 'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add lock and c')
    stub_sweep([hit('uv.lock', rule='lockfile-drift'), hit('src/pkg/c.py', rule='ruff')])
    assert auditor.changed.main([str(repo)]) == 1
    out = capsys.readouterr().out
    assert 'lockfile-drift: run `uv lock`' in out
    assert '# noqa: <code>' in out
    assert '# auditme: accept[<rule>] <reason>' not in out


def test_marker_advice_is_given_beside_rule_advice(repo, stub_sweep, capsys) -> None:
    write(repo, {'uv.lock': 'version = 1\n', 'src/pkg/c.py': 'c = 1\n'})
    commit_all(repo, 'add lock and c')
    stub_sweep([hit('uv.lock', rule='lockfile-drift'), hit('src/pkg/c.py')])
    assert auditor.changed.main([str(repo)]) == 1
    out = capsys.readouterr().out
    assert 'lockfile-drift: run `uv lock`' in out
    assert '# auditme: accept[<rule>] <reason>' in out


DECLARED = '[[tool.auditme.roots]]\npath = "lib/pkg"\n'


def test_all_sweeps_a_declared_root_outside_src(tmp_path, capsys) -> None:
    root = start_script_project(
        tmp_path,
        {'pyproject.toml': DECLARED, 'lib/pkg/__init__.py': '', 'lib/pkg/mod.py': conftest.FUTURE_IMPORT},
    )
    assert auditor.changed.main(['--all', str(root)]) == 1
    assert 'lib/pkg/mod.py:1  future-annotations' in capsys.readouterr().out


def test_a_malformed_declaration_fails_the_sweep(tmp_path, capsys) -> None:
    root = start_script_project(tmp_path, {'pyproject.toml': '[tool.auditme]\nroots = "lib"\n', 'lib/a.py': 'A = 1\n'})
    assert auditor.changed.main(['--all', str(root)]) == 1
    assert 'ERROR: ' in capsys.readouterr().out


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    parts=hypothesis.strategies.lists(hypothesis.strategies.from_regex(r'[a-z]{1,4}', fullmatch=True), max_size=3),
    stem=hypothesis.strategies.from_regex(r'[a-z]{1,5}', fullmatch=True),
    dot=hypothesis.strategies.from_regex(r'\.[a-z]{1,4}', fullmatch=True),
)
def test_reportable_by_suffix_and_dot_directory(parts: list[str], stem: str, dot: str) -> None:
    prefix = '/'.join(parts) + '/' if parts else ''
    assert auditor.changed.reportable(f'{prefix}{stem}.py')
    assert auditor.changed.reportable(f'{prefix}uv.lock')
    other = f'{prefix}{stem}.txt'
    assert not auditor.changed.reportable(other)
    assert not auditor.changed.reportable(f'{prefix}{dot}/{stem}.md')


THREE_FUNCTIONS = (
    'def first():\n'  # 1
    '    return 1\n'  # 2
    '\n'  # 3
    '\n'  # 4
    'def second():\n'  # 5
    '    value = 2\n'  # 6
    '    return value\n'  # 7
    '\n'  # 8
    '\n'  # 9
    'def third():\n'  # 10
    '    return 3\n'  # 11
)


def scope_lines(repo: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> dict[str, list[list[int]]]:
    assert auditor.changed.main(['--scope', '--base', 'main', str(repo)]) == 0
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    return {record['path']: record['ranges'] for record in records}


def edit_on_new_branch(repo: pathlib.Path, files: dict[str, str]) -> None:
    """Move `main` to the current commit, then commit `files` on a new branch."""
    conftest.git(repo, 'branch', '-f', 'main', 'HEAD')
    conftest.git(repo, 'checkout', '-q', '-b', 'edit')
    write(repo, files)
    commit_all(repo, 'edit')


def test_scope_widens_a_change_to_its_enclosing_function(repo, capsys) -> None:
    write(repo, {'src/pkg/m.py': THREE_FUNCTIONS})
    commit_all(repo, 'add m')
    edit_on_new_branch(repo, {'src/pkg/m.py': THREE_FUNCTIONS.replace('value = 2', 'value = 20')})
    assert scope_lines(repo, capsys) == {'src/pkg/m.py': [[5, 7]]}


def test_scope_keeps_module_level_lines_as_changed(repo, capsys) -> None:
    write(repo, {'src/pkg/m.py': 'A = 1\nB = 2\nC = 3\n'})
    commit_all(repo, 'add m')
    edit_on_new_branch(repo, {'src/pkg/m.py': 'A = 1\nB = 20\nC = 3\n'})
    assert scope_lines(repo, capsys) == {'src/pkg/m.py': [[2, 2]]}


def test_scope_gives_a_new_file_its_whole_range(repo, capsys) -> None:
    write(repo, {'src/pkg/new.py': THREE_FUNCTIONS})
    commit_all(repo, 'add new')
    assert scope_lines(repo, capsys) == {'src/pkg/new.py': [[1, 11]]}


def test_scope_prints_nothing_for_a_deleted_file(repo, capsys) -> None:
    (repo / 'src/pkg/b.py').unlink()
    commit_all(repo, 'delete b')
    assert scope_lines(repo, capsys) == {}


def test_scope_keeps_shell_hunks_and_ignores_other_files(repo, capsys) -> None:
    write(repo, {'bin/run.sh': 'a\nb\nc\n', 'notes.md': 'x\n'})
    commit_all(repo, 'add files')
    edit_on_new_branch(repo, {'bin/run.sh': 'a\nB\nc\n', 'notes.md': 'y\n'})
    assert scope_lines(repo, capsys) == {'bin/run.sh': [[2, 2]]}


def test_scope_does_not_read_an_added_line_as_a_file_header(repo, capsys) -> None:
    write(repo, {'notes.sh': 'a\n'})
    commit_all(repo, 'add notes')
    edit_on_new_branch(repo, {'notes.sh': 'a\n++ b/other.py\n'})
    assert scope_lines(repo, capsys) == {'notes.sh': [[2, 2]]}


LINE = hypothesis.strategies.integers(min_value=1, max_value=12)
SPANS = hypothesis.strategies.tuples(LINE, LINE).map(lambda pair: (min(pair), max(pair)))


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(ranges=hypothesis.strategies.lists(SPANS, max_size=12))
def test_merge_ranges_is_the_sorted_disjoint_union(ranges: list[tuple[int, int]]) -> None:
    merged = auditor.changed.merge_ranges(ranges)
    assert merged == sorted(merged)
    for earlier, later in zip(merged, merged[1:], strict=False):
        assert earlier[1] + 1 < later[0]
    covered = {line for start, end in ranges for line in range(start, end + 1)}
    assert {line for start, end in merged for line in range(start, end + 1)} == covered
    assert auditor.changed.merge_ranges([(start, end) for start, end in merged]) == merged


SCOPES = hypothesis.strategies.lists(
    hypothesis.strategies.tuples(SPANS, hypothesis.strategies.booleans()).map(lambda pair: (*pair[0], pair[1])),
    max_size=6,
)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(hunk=SPANS, scopes=SCOPES)
def test_widen_gives_each_line_its_shortest_enclosing_scope(
    hunk: tuple[int, int],
    scopes: list[tuple[int, int, bool]],
) -> None:
    widened = auditor.changed.widen(hunk, scopes)
    assert len(widened) == hunk[1] - hunk[0] + 1
    for number, (start, end) in zip(range(hunk[0], hunk[1] + 1), widened, strict=True):
        assert start <= number <= end
        holding = [scope for scope in scopes if scope[0] <= number <= scope[1]]
        if not holding:
            assert (start, end) == (number, number)
            continue
        pool = [scope for scope in holding if scope[2]] or holding
        assert (start, end, True) in pool or (start, end, False) in pool
        assert end - start == min(scope[1] - scope[0] for scope in pool)


Node = tuple[str, int, tuple['Node', ...]]

KINDS = hypothesis.strategies.sampled_from(['def', 'async def', 'class'])
DECORATORS = hypothesis.strategies.integers(min_value=0, max_value=2)
NODES = hypothesis.strategies.recursive(
    hypothesis.strategies.tuples(
        KINDS,
        DECORATORS,
        hypothesis.strategies.just(()),
    ),
    lambda children: hypothesis.strategies.tuples(
        KINDS,
        DECORATORS,
        hypothesis.strategies.lists(children, min_size=1, max_size=3).map(tuple),
    ),
    max_leaves=8,
)


def render(node: Node, depth: int, lines: list[str], expected: list[tuple[int, int, bool]]) -> None:
    kind, decorators, children = node
    pad = '    ' * depth
    first = len(lines) + 1
    lines.extend(f'{pad}@decorator' for _ in range(decorators))
    lines.append(f'{pad}class C:' if kind == 'class' else f'{pad}{kind} f():')
    slot = len(expected)
    expected.append((first, 0, kind != 'class'))
    if children:
        for child in children:
            render(child, depth + 1, lines, expected)
    else:
        lines.append(f'{pad}    pass')
    expected[slot] = (first, len(lines), kind != 'class')


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(nodes=hypothesis.strategies.lists(NODES, min_size=1, max_size=3))
def test_enclosing_ranges_cover_each_scope_from_its_decorator(nodes: list[Node]) -> None:
    lines: list[str] = []
    expected: list[tuple[int, int, bool]] = []
    for node in nodes:
        render(node, 0, lines, expected)
    found = auditor.changed.enclosing_ranges('\n'.join(lines) + '\n')
    assert sorted(found) == sorted(expected)
    assert all(1 <= start <= end <= len(lines) for start, end, _ in found)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(tail=hypothesis.strategies.text(alphabet='abc \n', max_size=30))
def test_enclosing_ranges_of_unparseable_source_is_empty(tail: str) -> None:
    assert auditor.changed.enclosing_ranges(f'def broken(:\n{tail}') == []
