"""Tests for planning batches and checking a run's output."""

import json
import pathlib

import auditme.phaseb
import auditme.phaseb.batches
import auditme.phaseb.candidates
import pytest


def make_batch_candidate(name: str, hash_: str = 'h1') -> auditme.phaseb.Candidate:
    return auditme.phaseb.Candidate(question='Q1', id=f'src/pkg/mod.py::{name}', path='src/pkg/mod.py', start=1, end=2, payload={'raises': 'x'}, hash=hash_)


def make_batch_verdict(candidate: auditme.phaseb.Candidate, brief_version: int = 1) -> auditme.phaseb.Verdict:
    return auditme.phaseb.Verdict(
        question='Q1',
        id=candidate.id,
        hash=candidate.hash,
        brief_version=brief_version,
        findings={'missing': [], 'extra': []},
        reason='ok',
        judged='2026-01-01',
    )


def candidate_names(plan: list[list[auditme.phaseb.Candidate]]) -> list[list[str]]:
    return [[candidate.id.split('::')[1] for candidate in batch] for batch in plan]


def test_current_verdict_is_not_planned() -> None:
    candidate = make_batch_candidate('a')
    ledger = {candidate.id: make_batch_verdict(candidate)}
    assert auditme.phaseb.batches.plan_batches([candidate], ledger, 1, 10) == []


def test_missing_changed_hash_and_older_brief_are_planned() -> None:
    a, b, c = make_batch_candidate('a'), make_batch_candidate('b'), make_batch_candidate('c')
    ledger = {
        b.id: make_batch_verdict(make_batch_candidate('b', 'old'), brief_version=2),
        c.id: make_batch_verdict(c, brief_version=1),
    }
    plan = auditme.phaseb.batches.plan_batches([a, b, c], ledger, 2, 10)
    assert candidate_names(plan) == [['a', 'b', 'c']]


def test_current_brief_version_with_same_hash_is_reused() -> None:
    a, b = make_batch_candidate('a'), make_batch_candidate('b')
    ledger = {a.id: make_batch_verdict(a, brief_version=2)}
    assert candidate_names(auditme.phaseb.batches.plan_batches([a, b], ledger, 2, 10)) == [['b']]


def test_rejudge_plans_every_candidate() -> None:
    candidate = make_batch_candidate('a')
    ledger = {candidate.id: make_batch_verdict(candidate)}
    assert candidate_names(auditme.phaseb.batches.plan_batches([candidate], ledger, 1, 10, rejudge=True)) == [['a']]


def test_batches_keep_id_order_and_size() -> None:
    candidates = [make_batch_candidate(name) for name in 'ecabd']
    plan = auditme.phaseb.batches.plan_batches(candidates, {}, 1, 2)
    assert candidate_names(plan) == [['a', 'b'], ['c', 'd'], ['e']]


def test_plan_json_and_batch_files(tmp_path: pathlib.Path) -> None:
    plan = auditme.phaseb.batches.plan_batches([make_batch_candidate('a'), make_batch_candidate('b'), make_batch_candidate('c')], {}, 3, 2)
    auditme.phaseb.batches.write_plan('Q1', pathlib.Path('briefs/Q1.md'), 3, plan, tmp_path / 'run')
    run = tmp_path / 'run'
    document = json.loads((run / 'plan.json').read_text(encoding='utf-8'))
    assert document['question'] == 'Q1'
    assert document['brief'] == 'briefs/Q1.md'
    assert document['brief_version'] == 3
    assert document['depth'] == auditme.phaseb.candidates.DEFAULT_DEPTH
    assert document['batches'] == [
        ['src/pkg/mod.py::a', 'src/pkg/mod.py::b'],
        ['src/pkg/mod.py::c'],
    ]
    lines = (run / 'batch-01.jsonl').read_text(encoding='utf-8').splitlines()
    assert [json.loads(line)['id'] for line in lines] == ['src/pkg/mod.py::a', 'src/pkg/mod.py::b']
    assert (run / 'batch-02.jsonl').is_file()


def make_result_line(candidate_id: str, **overrides) -> str:
    findings = {'missing': [], 'extra': []}
    findings.update(overrides.pop('findings', {}))
    record = {'id': candidate_id, 'findings': findings, 'reason': 'ok'}
    record.update(overrides)
    return json.dumps(record)


def planned_run(tmp_path: pathlib.Path) -> pathlib.Path:
    plan = auditme.phaseb.batches.plan_batches([make_batch_candidate(name) for name in 'abcdef'], {}, 1, 2)
    run = tmp_path / 'run'
    auditme.phaseb.batches.write_plan('A4', pathlib.Path('briefs/A4.md'), 1, plan, run)
    return run


def write_result(run: pathlib.Path, number: int, lines: list[str]) -> None:
    (run / f'result-{number:02d}.jsonl').write_text(''.join(line + '\n' for line in lines), encoding='utf-8')


def complete_run(run: pathlib.Path) -> None:
    write_result(run, 1, [make_result_line('src/pkg/mod.py::a'), make_result_line('src/pkg/mod.py::b')])
    write_result(run, 2, [make_result_line('src/pkg/mod.py::c'), make_result_line('src/pkg/mod.py::d')])
    write_result(run, 3, [make_result_line('src/pkg/mod.py::e'), make_result_line('src/pkg/mod.py::f')])


def test_complete_run_has_no_problems(tmp_path: pathlib.Path) -> None:
    run = planned_run(tmp_path)
    complete_run(run)
    result = auditme.phaseb.batches.check_run(run)
    assert result.problems == {}
    assert result.retry == []


def test_each_problem_kind_is_reported_against_its_batch(tmp_path: pathlib.Path) -> None:
    run = planned_run(tmp_path)
    write_result(run, 1, [make_result_line('src/pkg/mod.py::a'), '{not json'])
    write_result(run, 2, [make_result_line('src/pkg/mod.py::c'), make_result_line('src/pkg/mod.py::c')])
    result = auditme.phaseb.batches.check_run(run)
    assert result.retry == [1, 2, 3]
    assert any('unparseable' in problem for problem in result.problems[1])
    assert any('missing' in problem and 'mod.py::b' in problem for problem in result.problems[1])
    assert any('duplicate' in problem and 'mod.py::c' in problem for problem in result.problems[2])
    assert any('missing' in problem and 'mod.py::d' in problem for problem in result.problems[2])
    assert any('no output' in problem for problem in result.problems[3])


def test_unexpected_id_is_reported(tmp_path: pathlib.Path) -> None:
    run = planned_run(tmp_path)
    complete_run(run)
    write_result(run, 1, [make_result_line('src/pkg/mod.py::a'), make_result_line('src/pkg/mod.py::b'), make_result_line('src/pkg/mod.py::zzz')])
    result = auditme.phaseb.batches.check_run(run)
    assert result.retry == [1]
    assert any('unexpected' in problem and 'zzz' in problem for problem in result.problems[1])


def test_malformed_fields_are_reported_not_raised(tmp_path: pathlib.Path) -> None:
    run = planned_run(tmp_path)
    complete_run(run)
    write_result(run, 2, [make_result_line('src/pkg/mod.py::c', findings={'missing': 'nope'}), '[1]'])
    result = auditme.phaseb.batches.check_run(run)
    assert result.retry == [2]


def test_check_run_without_plan_raises(tmp_path: pathlib.Path) -> None:
    with pytest.raises(auditme.phaseb.PhaseBError):
        auditme.phaseb.batches.check_run(tmp_path)


def test_unreadable_plan_raises(tmp_path: pathlib.Path) -> None:
    (tmp_path / 'plan.json').write_text('{bad', encoding='utf-8')
    with pytest.raises(auditme.phaseb.PhaseBError):
        auditme.phaseb.batches.check_run(tmp_path)


def test_read_run_verdicts_stamps_hash_brief_version_and_date(tmp_path: pathlib.Path) -> None:
    candidates = [make_batch_candidate(name, f'hash-{name}') for name in 'ab']
    plan = auditme.phaseb.batches.plan_batches(candidates, {}, 4, 10)
    run = tmp_path / 'run'
    auditme.phaseb.batches.write_plan('A4', pathlib.Path('briefs/A4.md'), 4, plan, run)
    write_result(
        run,
        1,
        [
            make_result_line('src/pkg/mod.py::b', findings={'missing': ['ProbeError']}, reason='raises it'),
            make_result_line('src/pkg/mod.py::a'),
        ],
    )
    verdicts = auditme.phaseb.batches.read_run_verdicts(run, candidates, today='2026-02-03')
    assert [verdict.id for verdict in verdicts] == ['src/pkg/mod.py::a', 'src/pkg/mod.py::b']
    flagged = verdicts[1]
    assert flagged.hash == 'hash-b'
    assert flagged.brief_version == 4
    assert flagged.judged == '2026-02-03'
    assert flagged.findings == {'missing': ['ProbeError'], 'extra': []}
    assert flagged.flagged


def test_read_run_verdicts_refuses_a_run_with_problems(tmp_path: pathlib.Path) -> None:
    run = planned_run(tmp_path)
    with pytest.raises(auditme.phaseb.PhaseBError):
        auditme.phaseb.batches.read_run_verdicts(run, [], today='2026-02-03')


def one_candidate_run(tmp_path: pathlib.Path, question: str) -> pathlib.Path:
    run = tmp_path / 'run'
    auditme.phaseb.batches.write_plan(question, pathlib.Path('briefs/x.md'), 1, [[make_batch_candidate('a')]], run)
    return run


def make_findings_line(findings: object, **extra: object) -> str:
    return json.dumps({'id': 'src/pkg/mod.py::a', 'findings': findings, 'reason': 'ok', **extra})


@pytest.mark.parametrize('question', sorted(auditme.phaseb.candidates.REGISTRY))
def test_every_registered_questions_shape_passes_and_reads_back_sorted(tmp_path: pathlib.Path, question: str) -> None:
    kinds = auditme.phaseb.question_kinds(question)
    run = one_candidate_run(tmp_path, question)
    findings: dict[str, list[str]] = {kind: [] for kind in kinds}
    findings[kinds[0]] = ['zeta', 'alpha']
    write_result(run, 1, [make_findings_line(findings)])
    result = auditme.phaseb.batches.check_run(run)
    assert result.problems == {}
    assert result.retry == []
    verdicts = auditme.phaseb.batches.read_run_verdicts(run, [make_batch_candidate('a')], today='2026-02-03')
    assert verdicts[0].findings == {**{kind: [] for kind in kinds}, kinds[0]: ['alpha', 'zeta']}


@pytest.mark.parametrize(
    'line',
    [
        make_findings_line({'missing': [], 'extra': [], 'bogus': []}),
        make_findings_line({'missing': []}),
        make_findings_line({'missing': 'x', 'extra': []}),
        make_findings_line({'missing': [1], 'extra': []}),
        make_findings_line({'missing': [], 'extra': []}, stray=1),
        json.dumps({'id': 'src/pkg/mod.py::a', 'missing': [], 'extra': [], 'reason': 'ok'}),
    ],
)
def test_malformed_findings_lines_are_unparseable(tmp_path: pathlib.Path, line: str) -> None:
    run = one_candidate_run(tmp_path, 'A4')
    write_result(run, 1, [line])
    result = auditme.phaseb.batches.check_run(run)
    assert result.retry == [1]
    assert any('unparseable' in problem for problem in result.problems[1])
