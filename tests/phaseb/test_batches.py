"""Tests for planning batches and checking a run's output."""

import json
import pathlib

import pytest
from auditme import phaseb
from auditme.phaseb import batches


def _candidate(name: str, hash_: str = 'h1') -> phaseb.Candidate:
    return phaseb.Candidate(question='Q1', id=f'src/pkg/mod.py::{name}', path='src/pkg/mod.py', start=1, end=2, payload={'raises': 'x'}, hash=hash_)


def _verdict(candidate: phaseb.Candidate, brief_version: int = 1) -> phaseb.Verdict:
    return phaseb.Verdict(
        question='Q1',
        id=candidate.id,
        hash=candidate.hash,
        brief_version=brief_version,
        findings={'missing': [], 'extra': []},
        reason='ok',
        judged='2026-01-01',
    )


def _names(plan: list[list[phaseb.Candidate]]) -> list[list[str]]:
    return [[candidate.id.split('::')[1] for candidate in batch] for batch in plan]


def test_current_verdict_is_not_planned() -> None:
    candidate = _candidate('a')
    ledger = {candidate.id: _verdict(candidate)}
    assert batches.plan_batches([candidate], ledger, 1, 10) == []


def test_missing_changed_hash_and_older_brief_are_planned() -> None:
    a, b, c = _candidate('a'), _candidate('b'), _candidate('c')
    ledger = {
        b.id: _verdict(_candidate('b', 'old'), brief_version=2),
        c.id: _verdict(c, brief_version=1),
    }
    plan = batches.plan_batches([a, b, c], ledger, 2, 10)
    assert _names(plan) == [['a', 'b', 'c']]


def test_current_brief_version_with_same_hash_is_reused() -> None:
    a, b = _candidate('a'), _candidate('b')
    ledger = {a.id: _verdict(a, brief_version=2)}
    assert _names(batches.plan_batches([a, b], ledger, 2, 10)) == [['b']]


def test_rejudge_plans_every_candidate() -> None:
    candidate = _candidate('a')
    ledger = {candidate.id: _verdict(candidate)}
    assert _names(batches.plan_batches([candidate], ledger, 1, 10, rejudge=True)) == [['a']]


def test_batches_keep_id_order_and_size() -> None:
    candidates = [_candidate(name) for name in 'ecabd']
    plan = batches.plan_batches(candidates, {}, 1, 2)
    assert _names(plan) == [['a', 'b'], ['c', 'd'], ['e']]


def test_plan_json_and_batch_files(tmp_path: pathlib.Path) -> None:
    plan = batches.plan_batches([_candidate('a'), _candidate('b'), _candidate('c')], {}, 3, 2)
    batches.write_plan('Q1', pathlib.Path('briefs/Q1.md'), 3, plan, tmp_path / 'run')
    run = tmp_path / 'run'
    document = json.loads((run / 'plan.json').read_text(encoding='utf-8'))
    assert document['question'] == 'Q1'
    assert document['brief'] == 'briefs/Q1.md'
    assert document['brief_version'] == 3
    assert document['batches'] == [
        ['src/pkg/mod.py::a', 'src/pkg/mod.py::b'],
        ['src/pkg/mod.py::c'],
    ]
    lines = (run / 'batch-01.jsonl').read_text(encoding='utf-8').splitlines()
    assert [json.loads(line)['id'] for line in lines] == ['src/pkg/mod.py::a', 'src/pkg/mod.py::b']
    assert (run / 'batch-02.jsonl').is_file()


def _result_line(candidate_id: str, **overrides) -> str:
    record = {'id': candidate_id, 'missing': [], 'extra': [], 'reason': 'ok'}
    record.update(overrides)
    return json.dumps(record)


def _planned(tmp_path: pathlib.Path) -> pathlib.Path:
    plan = batches.plan_batches([_candidate(name) for name in 'abcdef'], {}, 1, 2)
    run = tmp_path / 'run'
    batches.write_plan('Q1', pathlib.Path('briefs/Q1.md'), 1, plan, run)
    return run


def _write_result(run: pathlib.Path, number: int, lines: list[str]) -> None:
    (run / f'result-{number:02d}.jsonl').write_text(''.join(line + '\n' for line in lines), encoding='utf-8')


def _complete(run: pathlib.Path) -> None:
    _write_result(run, 1, [_result_line('src/pkg/mod.py::a'), _result_line('src/pkg/mod.py::b')])
    _write_result(run, 2, [_result_line('src/pkg/mod.py::c'), _result_line('src/pkg/mod.py::d')])
    _write_result(run, 3, [_result_line('src/pkg/mod.py::e'), _result_line('src/pkg/mod.py::f')])


def test_complete_run_has_no_problems(tmp_path: pathlib.Path) -> None:
    run = _planned(tmp_path)
    _complete(run)
    result = batches.check_run(run)
    assert result.problems == {}
    assert result.retry == []


def test_each_problem_kind_is_reported_against_its_batch(tmp_path: pathlib.Path) -> None:
    run = _planned(tmp_path)
    _write_result(run, 1, [_result_line('src/pkg/mod.py::a'), '{not json'])
    _write_result(run, 2, [_result_line('src/pkg/mod.py::c'), _result_line('src/pkg/mod.py::c')])
    result = batches.check_run(run)
    assert result.retry == [1, 2, 3]
    assert any('unparseable' in problem for problem in result.problems[1])
    assert any('missing' in problem and 'mod.py::b' in problem for problem in result.problems[1])
    assert any('duplicate' in problem and 'mod.py::c' in problem for problem in result.problems[2])
    assert any('missing' in problem and 'mod.py::d' in problem for problem in result.problems[2])
    assert any('no output' in problem for problem in result.problems[3])


def test_unexpected_id_is_reported(tmp_path: pathlib.Path) -> None:
    run = _planned(tmp_path)
    _complete(run)
    _write_result(run, 1, [_result_line('src/pkg/mod.py::a'), _result_line('src/pkg/mod.py::b'), _result_line('src/pkg/mod.py::zzz')])
    result = batches.check_run(run)
    assert result.retry == [1]
    assert any('unexpected' in problem and 'zzz' in problem for problem in result.problems[1])


def test_malformed_fields_are_reported_not_raised(tmp_path: pathlib.Path) -> None:
    run = _planned(tmp_path)
    _complete(run)
    _write_result(run, 2, [_result_line('src/pkg/mod.py::c', missing='nope'), '[1]'])
    result = batches.check_run(run)
    assert result.retry == [2]


def test_check_run_without_plan_raises(tmp_path: pathlib.Path) -> None:
    with pytest.raises(phaseb.PhaseBError):
        batches.check_run(tmp_path)


def test_unreadable_plan_raises(tmp_path: pathlib.Path) -> None:
    (tmp_path / 'plan.json').write_text('{bad', encoding='utf-8')
    with pytest.raises(phaseb.PhaseBError):
        batches.check_run(tmp_path)


def test_read_run_verdicts_stamps_hash_brief_version_and_date(tmp_path: pathlib.Path) -> None:
    candidates = [_candidate(name, f'hash-{name}') for name in 'ab']
    plan = batches.plan_batches(candidates, {}, 4, 10)
    run = tmp_path / 'run'
    batches.write_plan('Q1', pathlib.Path('briefs/Q1.md'), 4, plan, run)
    _write_result(
        run,
        1,
        [
            _result_line('src/pkg/mod.py::b', missing=['ProbeError'], reason='raises it'),
            _result_line('src/pkg/mod.py::a'),
        ],
    )
    verdicts = batches.read_run_verdicts(run, candidates, today='2026-02-03')
    assert [verdict.id for verdict in verdicts] == ['src/pkg/mod.py::a', 'src/pkg/mod.py::b']
    flagged = verdicts[1]
    assert flagged.hash == 'hash-b'
    assert flagged.brief_version == 4
    assert flagged.judged == '2026-02-03'
    assert flagged.findings == {'missing': ['ProbeError'], 'extra': []}
    assert flagged.flagged


def test_read_run_verdicts_refuses_a_run_with_problems(tmp_path: pathlib.Path) -> None:
    run = _planned(tmp_path)
    with pytest.raises(phaseb.PhaseBError):
        batches.read_run_verdicts(run, [], today='2026-02-03')
