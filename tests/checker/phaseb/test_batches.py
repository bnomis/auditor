"""Tests for planning batches and checking a run's output."""

import json
import pathlib

import conftest
import pytest

import auditor.phaseb
import auditor.phaseb.batches
import auditor.phaseb.candidates


def candidate_names(plan: list[list[auditor.api.candidates.Candidate]]) -> list[list[str]]:
    return [[candidate.id.split('::')[1] for candidate in batch] for batch in plan]


def test_current_verdict_is_not_planned() -> None:
    candidate = conftest.make_candidate('src/pkg/mod.py::a')
    ledger = {candidate.id: conftest.make_verdict(candidate.id, hash=candidate.hash)}
    assert auditor.phaseb.batches.plan_batches([candidate], ledger, 1, 10) == []


def test_missing_changed_hash_and_older_brief_are_planned() -> None:
    a, b, c = conftest.make_candidate('src/pkg/mod.py::a'), conftest.make_candidate('src/pkg/mod.py::b'), conftest.make_candidate('src/pkg/mod.py::c')
    ledger = {
        b.id: conftest.make_verdict(b.id, hash='old', brief_version=2),
        c.id: conftest.make_verdict(c.id, hash=c.hash, brief_version=1),
    }
    plan = auditor.phaseb.batches.plan_batches([a, b, c], ledger, 2, 10)
    assert candidate_names(plan) == [['a', 'b', 'c']]


def test_current_brief_version_with_same_hash_is_reused() -> None:
    a, b = conftest.make_candidate('src/pkg/mod.py::a'), conftest.make_candidate('src/pkg/mod.py::b')
    ledger = {a.id: conftest.make_verdict(a.id, hash=a.hash, brief_version=2)}
    assert candidate_names(auditor.phaseb.batches.plan_batches([a, b], ledger, 2, 10)) == [['b']]


def test_replanned_candidate_carries_its_earlier_verdict_and_a_new_one_does_not(tmp_path: pathlib.Path) -> None:
    changed, fresh = conftest.make_candidate('src/pkg/mod.py::a'), conftest.make_candidate('src/pkg/mod.py::b')
    earlier = conftest.make_verdict(conftest.make_candidate('src/pkg/mod.py::a').id, hash='old', brief_version=1)
    ledger = {changed.id: earlier}
    plan = auditor.phaseb.batches.plan_batches([changed, fresh], ledger, 1, 10)
    run = tmp_path / 'run'
    auditor.phaseb.batches.write_plan('Q1', pathlib.Path('briefs/Q1.md'), 1, plan, run, ledger=ledger)
    lines = [json.loads(line) for line in (run / 'batch-01.jsonl').read_text(encoding='utf-8').splitlines()]
    by_id = {line['id']: line for line in lines}
    assert by_id[changed.id]['earlier'] == {'findings': earlier.findings, 'reason': 'ok', 'brief_version': 1, 'judged': '2026-01-01'}
    assert 'earlier' not in by_id[fresh.id]


def test_plan_without_a_ledger_writes_no_earlier(tmp_path: pathlib.Path) -> None:
    plan = auditor.phaseb.batches.plan_batches([conftest.make_candidate('src/pkg/mod.py::a')], {}, 1, 10)
    auditor.phaseb.batches.write_plan('Q1', pathlib.Path('briefs/Q1.md'), 1, plan, tmp_path / 'run')
    assert 'earlier' not in json.loads((tmp_path / 'run' / 'batch-01.jsonl').read_text(encoding='utf-8'))


def test_rejudge_plans_every_candidate() -> None:
    candidate = conftest.make_candidate('src/pkg/mod.py::a')
    ledger = {candidate.id: conftest.make_verdict(candidate.id, hash=candidate.hash)}
    assert candidate_names(auditor.phaseb.batches.plan_batches([candidate], ledger, 1, 10, rejudge=True)) == [['a']]


def test_batches_keep_id_order_and_size() -> None:
    candidates = [conftest.make_candidate(f'src/pkg/mod.py::{name}') for name in 'ecabd']
    plan = auditor.phaseb.batches.plan_batches(candidates, {}, 1, 2)
    assert candidate_names(plan) == [['a', 'b'], ['c', 'd'], ['e']]


def test_plan_json_and_batch_files(tmp_path: pathlib.Path) -> None:
    plan = auditor.phaseb.batches.plan_batches(
        [conftest.make_candidate('src/pkg/mod.py::a'), conftest.make_candidate('src/pkg/mod.py::b'), conftest.make_candidate('src/pkg/mod.py::c')], {}, 3, 2
    )
    auditor.phaseb.batches.write_plan('Q1', pathlib.Path('briefs/Q1.md'), 3, plan, tmp_path / 'run')
    run = tmp_path / 'run'
    document = json.loads((run / 'plan.json').read_text(encoding='utf-8'))
    assert document['question'] == 'Q1'
    assert document['brief'] == 'briefs/Q1.md'
    assert document['brief_version'] == 3
    assert document['depth'] == auditor.api.candidates.DEFAULT_DEPTH
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
    plan = auditor.phaseb.batches.plan_batches([conftest.make_candidate(f'src/pkg/mod.py::{name}') for name in 'abcdef'], {}, 1, 2)
    run = tmp_path / 'run'
    auditor.phaseb.batches.write_plan('A4', pathlib.Path('briefs/A4.md'), 1, plan, run)
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
    result = auditor.phaseb.batches.read_run_check(run)
    assert result.problems == {}
    assert result.retry == []


def test_each_problem_kind_is_reported_against_its_batch(tmp_path: pathlib.Path) -> None:
    run = planned_run(tmp_path)
    write_result(run, 1, [make_result_line('src/pkg/mod.py::a'), '{not json'])
    write_result(run, 2, [make_result_line('src/pkg/mod.py::c'), make_result_line('src/pkg/mod.py::c')])
    result = auditor.phaseb.batches.read_run_check(run)
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
    result = auditor.phaseb.batches.read_run_check(run)
    assert result.retry == [1]
    assert any('unexpected' in problem and 'zzz' in problem for problem in result.problems[1])


def test_malformed_fields_are_reported_not_raised(tmp_path: pathlib.Path) -> None:
    run = planned_run(tmp_path)
    complete_run(run)
    write_result(run, 2, [make_result_line('src/pkg/mod.py::c', findings={'missing': 'nope'}), '[1]'])
    result = auditor.phaseb.batches.read_run_check(run)
    assert result.retry == [2]


def test_check_run_without_plan_raises(tmp_path: pathlib.Path) -> None:
    with pytest.raises(auditor.phaseb.PhaseBError):
        auditor.phaseb.batches.read_run_check(tmp_path)


def test_unreadable_plan_raises(tmp_path: pathlib.Path) -> None:
    (tmp_path / 'plan.json').write_text('{bad', encoding='utf-8')
    with pytest.raises(auditor.phaseb.PhaseBError):
        auditor.phaseb.batches.read_run_check(tmp_path)


def test_read_run_verdicts_stamps_hash_brief_version_and_date(tmp_path: pathlib.Path) -> None:
    candidates = [conftest.make_candidate(f'src/pkg/mod.py::{name}', hash=f'hash-{name}') for name in 'ab']
    plan = auditor.phaseb.batches.plan_batches(candidates, {}, 4, 10)
    run = tmp_path / 'run'
    auditor.phaseb.batches.write_plan('A4', pathlib.Path('briefs/A4.md'), 4, plan, run)
    write_result(
        run,
        1,
        [
            make_result_line('src/pkg/mod.py::b', findings={'missing': ['ProbeError']}, reason='raises it'),
            make_result_line('src/pkg/mod.py::a'),
        ],
    )
    verdicts = auditor.phaseb.batches.read_run_verdicts(run, candidates, today='2026-02-03')
    assert [verdict.id for verdict in verdicts] == ['src/pkg/mod.py::a', 'src/pkg/mod.py::b']
    flagged = verdicts[1]
    assert flagged.hash == 'hash-b'
    assert flagged.brief_version == 4
    assert flagged.judged == '2026-02-03'
    assert flagged.findings == {'missing': ['ProbeError'], 'extra': []}
    assert flagged.flagged


def test_read_run_verdicts_refuses_a_run_with_problems(tmp_path: pathlib.Path) -> None:
    run = planned_run(tmp_path)
    with pytest.raises(auditor.phaseb.PhaseBError):
        auditor.phaseb.batches.read_run_verdicts(run, [], today='2026-02-03')


def one_candidate_run(tmp_path: pathlib.Path, question: str) -> pathlib.Path:
    run = tmp_path / 'run'
    auditor.phaseb.batches.write_plan(question, pathlib.Path('briefs/x.md'), 1, [[conftest.make_candidate('src/pkg/mod.py::a')]], run)
    return run


def make_findings_line(findings: object, **extra: object) -> str:
    return json.dumps({'id': 'src/pkg/mod.py::a', 'findings': findings, 'reason': 'ok', **extra})


@pytest.mark.parametrize('question', sorted(auditor.phaseb.candidates.REGISTRY))
def test_every_registered_questions_shape_passes_and_reads_back_sorted(tmp_path: pathlib.Path, question: str) -> None:
    kinds = auditor.phaseb.candidates.question_kinds(question)
    run = one_candidate_run(tmp_path, question)
    findings: dict[str, list[str]] = {kind: [] for kind in kinds}
    findings[kinds[0]] = ['zeta', 'alpha']
    write_result(run, 1, [make_findings_line(findings)])
    result = auditor.phaseb.batches.read_run_check(run)
    assert result.problems == {}
    assert result.retry == []
    verdicts = auditor.phaseb.batches.read_run_verdicts(run, [conftest.make_candidate('src/pkg/mod.py::a')], today='2026-02-03')
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
    result = auditor.phaseb.batches.read_run_check(run)
    assert result.retry == [1]
    assert any('unparseable' in problem for problem in result.problems[1])


def test_read_plan_round_trips_a_written_plan(tmp_path: pathlib.Path) -> None:
    document = {'question': 'Q1', 'brief': 'Q1.md', 'brief_version': 2, 'batches': [['a'], ['b', 'c']], 'depth': 5}
    (tmp_path / 'plan.json').write_text(json.dumps(document), encoding='utf-8')
    plan = auditor.phaseb.batches.read_plan(tmp_path)
    assert plan == auditor.phaseb.batches.Plan('Q1', 'Q1.md', 2, [['a'], ['b', 'c']], 5)


def test_read_plan_reads_a_plan_without_a_depth_as_the_default_depth(tmp_path: pathlib.Path) -> None:
    document = {'question': 'Q1', 'brief': 'Q1.md', 'brief_version': 2, 'batches': []}
    (tmp_path / 'plan.json').write_text(json.dumps(document), encoding='utf-8')
    assert auditor.phaseb.batches.read_plan(tmp_path).depth == auditor.phaseb.batches.DEFAULT_DEPTH


def test_read_plan_refuses_an_absent_plan(tmp_path: pathlib.Path) -> None:
    with pytest.raises(auditor.phaseb.PhaseBError, match='cannot read plan'):
        auditor.phaseb.batches.read_plan(tmp_path)
