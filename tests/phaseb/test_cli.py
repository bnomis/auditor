"""Tests for the `phaseb.py` command line, run as a subprocess on a fixture project."""

import collections.abc
import json
import pathlib
import subprocess
import sys

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / 'checks' / 'phaseb.py'

Project = collections.abc.Callable[[dict[str, str]], pathlib.Path]

MOD = '''
    class ProbeError(Exception):
        pass


    def first():
        """Do it.

        Raises:
            ProbeError: always.
        """
        raise ProbeError('x')


    def second():
        """Do it too.

        Raises:
            ProbeError: always.
        """
        raise ProbeError('y')
'''

FIRST = 'src/pkg/mod.py::first'
SECOND = 'src/pkg/mod.py::second'


def run(*args: str | pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, check=False)


@pytest.fixture
def root(project: Project) -> pathlib.Path:
    return project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD})


def write_results(run_dir: pathlib.Path, number: int, ids: list[str], missing: list[str] | None = None) -> None:
    lines = [json.dumps({'id': item, 'missing': missing or [], 'extra': [], 'reason': 'ok'}) for item in ids]
    (run_dir / f'result-{number:02d}.jsonl').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def ledger_of(root: pathlib.Path) -> pathlib.Path:
    return root / 'agents' / 'audit-reviews' / 'ledger' / 'A4.jsonl'


def test_candidates_prints_one_json_line_per_candidate(root: pathlib.Path) -> None:
    done = run('candidates', root, '--question', 'A4')
    assert done.returncode == 0, done.stderr
    records = [json.loads(line) for line in done.stdout.splitlines()]
    assert [record['id'] for record in records] == [FIRST, SECOND]
    assert {'id', 'hash', 'payload'} <= set(records[0])


@pytest.mark.parametrize('question', ['Doc1', 'Doc2', 'Doc4', 'Doc5'])
def test_candidates_runs_for_listers_that_take_no_depth(root: pathlib.Path, question: str) -> None:
    subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)
    done = run('candidates', root, '--question', question)
    assert done.returncode == 0, done.stderr


def test_plan_writes_batches_and_reports_counts(root: pathlib.Path, tmp_path: pathlib.Path) -> None:
    out = tmp_path / 'run'
    done = run('plan', root, '--question', 'A4', '--out', out)
    assert done.returncode == 0, done.stderr
    assert '2 planned' in done.stdout
    assert '0 reused' in done.stdout
    assert (out / 'batch-01.jsonl').is_file()
    plan = json.loads((out / 'plan.json').read_text(encoding='utf-8'))
    assert plan['question'] == 'A4'
    assert plan['batches'] == [[FIRST, SECOND]]
    assert isinstance(plan['brief_version'], int)


def test_batch_size_splits_the_plan(root: pathlib.Path, tmp_path: pathlib.Path) -> None:
    out = tmp_path / 'run'
    assert run('plan', root, '--question', 'A4', '--out', out, '--batch-size', '1').returncode == 0
    plan = json.loads((out / 'plan.json').read_text(encoding='utf-8'))
    assert plan['batches'] == [[FIRST], [SECOND]]


def test_check_passes_a_complete_run(root: pathlib.Path, tmp_path: pathlib.Path) -> None:
    out = tmp_path / 'run'
    run('plan', root, '--question', 'A4', '--out', out)
    write_results(out, 1, [FIRST, SECOND])
    assert run('check', out).returncode == 0


def test_check_names_the_batch_with_a_missing_id(root: pathlib.Path, tmp_path: pathlib.Path) -> None:
    out = tmp_path / 'run'
    run('plan', root, '--question', 'A4', '--out', out)
    write_results(out, 1, [FIRST])
    done = run('check', out)
    assert done.returncode == 1
    assert 'batch 1' in done.stdout
    assert SECOND in done.stdout


def test_merge_writes_the_ledger_and_a_second_plan_finds_nothing(root: pathlib.Path, tmp_path: pathlib.Path) -> None:
    out = tmp_path / 'run'
    run('plan', root, '--question', 'A4', '--out', out)
    write_results(out, 1, [FIRST, SECOND])
    done = run('merge', root, '--question', 'A4', out)
    assert done.returncode == 0, done.stderr
    assert len(ledger_of(root).read_text(encoding='utf-8').splitlines()) == 2
    again = run('plan', root, '--question', 'A4', '--out', tmp_path / 'again')
    assert '0 planned' in again.stdout
    assert '2 reused' in again.stdout


def test_rejudge_plans_every_candidate_again(root: pathlib.Path, tmp_path: pathlib.Path) -> None:
    out = tmp_path / 'run'
    run('plan', root, '--question', 'A4', '--out', out)
    write_results(out, 1, [FIRST, SECOND])
    run('merge', root, '--question', 'A4', out)
    again = run('plan', root, '--question', 'A4', '--out', tmp_path / 'again', '--rejudge')
    assert '2 planned' in again.stdout


def test_merge_refuses_an_incomplete_run(root: pathlib.Path, tmp_path: pathlib.Path) -> None:
    out = tmp_path / 'run'
    run('plan', root, '--question', 'A4', '--out', out)
    write_results(out, 1, [FIRST])
    done = run('merge', root, '--question', 'A4', out)
    assert done.returncode == 2
    assert not ledger_of(root).exists()


def verdict_line(candidate: str, judged: str, missing: list[str], dismissed: str | None = None) -> str:
    return json.dumps(
        {
            'question': 'A4',
            'id': candidate,
            'hash': 'h',
            'brief_version': 1,
            'findings': {'missing': missing, 'extra': []},
            'reason': f'why {candidate}',
            'judged': judged,
            'dismissed': dismissed,
        }
    )


def test_report_splits_new_from_carried_and_leaves_out_dismissed(project: Project) -> None:
    functions = '\n\n'.join(f'def {name}():\n    """Do it.\n\n    Raises:\n        ProbeError: always.\n    """\n    raise ProbeError()' for name in 'abcd')
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': f'class ProbeError(Exception):\n    pass\n\n\n{functions}\n'})
    ledger = ledger_of(root)
    ledger.parent.mkdir(parents=True)
    lines = [
        verdict_line('src/pkg/mod.py::a', '2026-01-01', ['ProbeError']),
        verdict_line('src/pkg/mod.py::b', '2026-02-01', ['ProbeError']),
        verdict_line('src/pkg/mod.py::c', '2026-02-01', ['ProbeError'], dismissed='2026-02-02: fine'),
        verdict_line('src/pkg/mod.py::d', '2026-02-01', []),
    ]
    ledger.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    done = run('report', root, '--question', 'A4')
    assert done.returncode == 0, done.stderr
    assert 'new src/pkg/mod.py::b' in done.stdout
    assert 'carried src/pkg/mod.py::a' in done.stdout
    assert 'mod.py::c' not in done.stdout
    assert 'mod.py::d' not in done.stdout


def test_dismiss_records_the_reason(root: pathlib.Path) -> None:
    ledger = ledger_of(root)
    ledger.parent.mkdir(parents=True)
    ledger.write_text(verdict_line(FIRST, '2026-02-01', ['ProbeError']) + '\n', encoding='utf-8')
    done = run('dismiss', root, '--question', 'A4', FIRST, '--reason', 'intended')
    assert done.returncode == 0, done.stderr
    assert json.loads(ledger.read_text(encoding='utf-8'))['dismissed'].endswith(': intended')


def test_unknown_question_exits_2_with_the_message_on_stderr(root: pathlib.Path) -> None:
    done = run('candidates', root, '--question', 'Z9')
    assert done.returncode == 2
    assert 'Z9' in done.stderr
    assert done.stdout == ''


# registered batch size


def _plan_in_process(monkeypatch: pytest.MonkeyPatch, root: pathlib.Path, out: pathlib.Path, *extra: str) -> list[list[str]]:
    """Run `phaseb.py plan` in this process for a question registered with a batch size of 1."""
    import phaseb  # noqa: PLC0415  the script lives in checks/, which conftest puts on sys.path
    from auditme.phaseb import candidates  # noqa: PLC0415

    lister, brief, _ = candidates.REGISTRY['A4']
    monkeypatch.setitem(candidates.REGISTRY, 'A4', (lister, brief, 1))
    monkeypatch.setattr(sys, 'argv', ['phaseb.py', 'plan', str(root), '--question', 'A4', '--out', str(out), *extra])
    assert phaseb.main() == 0
    return json.loads((out / 'plan.json').read_text(encoding='utf-8'))['batches']


def test_plan_uses_the_registered_size_without_batch_size(root: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _plan_in_process(monkeypatch, root, tmp_path / 'out') == [[FIRST], [SECOND]]


def test_plan_batch_size_option_overrides_the_registered_size(root: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _plan_in_process(monkeypatch, root, tmp_path / 'out', '--batch-size', '2') == [[FIRST, SECOND]]
