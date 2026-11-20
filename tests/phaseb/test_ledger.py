"""Tests for reading, merging and dismissing ledger verdicts."""

import dataclasses
import json
import os
import pathlib

import pytest
from auditme import phaseb
from auditme.phaseb import ledger


def _verdict(candidate_id: str = 'src/pkg/mod.py::probe', **overrides) -> phaseb.Verdict:
    fields = {
        'question': 'Q1',
        'id': candidate_id,
        'hash': 'abc',
        'brief_version': 1,
        'findings': {'missing': [], 'extra': []},
        'reason': 'ok',
        'judged': '2026-01-01',
    }
    fields.update(overrides)
    return phaseb.Verdict(**fields)


def _candidate(candidate_id: str) -> phaseb.Candidate:
    return phaseb.Candidate(question='Q1', id=candidate_id, path='src/pkg/mod.py', start=1, end=2, payload={}, hash='h')


def _write(path: pathlib.Path, verdicts: list[phaseb.Verdict]) -> None:
    path.write_text(''.join(json.dumps(dataclasses.asdict(verdict)) + '\n' for verdict in verdicts), encoding='utf-8')


def test_missing_ledger_reads_as_empty(tmp_path: pathlib.Path) -> None:
    assert ledger.read_ledger(tmp_path / 'Q1.jsonl') == {}


def test_ledger_round_trips(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    verdict = _verdict(findings={'missing': ['ProbeError'], 'extra': []})
    _write(path, [verdict])
    assert ledger.read_ledger(path) == {verdict.id: verdict}


def test_unparseable_line_raises(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    path.write_text('{not json\n', encoding='utf-8')
    with pytest.raises(phaseb.PhaseBError):
        ledger.read_ledger(path)


def test_line_missing_a_field_raises(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    record = dataclasses.asdict(_verdict())
    del record['reason']
    path.write_text(json.dumps(record) + '\n', encoding='utf-8')
    with pytest.raises(phaseb.PhaseBError, match='reason'):
        ledger.read_ledger(path)


def test_directory_in_place_of_ledger_raises(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    path.mkdir()
    with pytest.raises(phaseb.PhaseBError):
        ledger.read_ledger(path)


def test_merge_writes_new_and_keeps_current(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'ledger' / 'Q1.jsonl'
    path.parent.mkdir()
    old = _verdict('a')
    _write(path, [old])
    new = _verdict('b')
    result = ledger.merge_verdicts(path, [_candidate('a'), _candidate('b')], [new])
    assert (result.written, result.kept, result.dropped) == (1, 1, 0)
    assert ledger.read_ledger(path) == {'a': old, 'b': new}


def test_merge_creates_missing_directory(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'agents' / 'ledger' / 'Q1.jsonl'
    ledger.merge_verdicts(path, [_candidate('a')], [_verdict('a')])
    assert set(ledger.read_ledger(path)) == {'a'}


def test_merge_drops_entry_that_is_no_longer_a_candidate(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    _write(path, [_verdict('a'), _verdict('gone')])
    result = ledger.merge_verdicts(path, [_candidate('a')], [])
    assert (result.written, result.kept, result.dropped) == (0, 1, 1)
    assert set(ledger.read_ledger(path)) == {'a'}


def test_unchanged_findings_keep_the_dismissal(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    findings = {'missing': ['ProbeError'], 'extra': []}
    _write(path, [_verdict('a', findings=findings, dismissed='2026-01-02: intended')])
    ledger.merge_verdicts(path, [_candidate('a')], [_verdict('a', hash='new', findings=findings)])
    merged = ledger.read_ledger(path)['a']
    assert merged.hash == 'new'
    assert merged.dismissed == '2026-01-02: intended'
    assert not merged.flagged


def test_changed_findings_drop_the_dismissal(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    _write(path, [_verdict('a', findings={'missing': ['ProbeError'], 'extra': []}, dismissed='2026-01-02: intended')])
    ledger.merge_verdicts(path, [_candidate('a')], [_verdict('a', findings={'missing': ['OtherError'], 'extra': []})])
    merged = ledger.read_ledger(path)['a']
    assert merged.dismissed is None
    assert merged.flagged


def test_dismiss_records_date_and_reason(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    _write(path, [_verdict('a', findings={'missing': ['ProbeError'], 'extra': []})])
    ledger.dismiss_verdict(path, 'a', 'intended', today='2026-02-03')
    dismissed = ledger.read_ledger(path)['a']
    assert dismissed.dismissed == '2026-02-03: intended'
    assert not dismissed.flagged


def test_dismiss_unknown_id_raises(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    _write(path, [_verdict('a')])
    with pytest.raises(phaseb.PhaseBError, match='nope'):
        ledger.dismiss_verdict(path, 'nope', 'reason', today='2026-02-03')


def test_ledger_is_written_one_sorted_line_per_verdict(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    ledger.merge_verdicts(path, [_candidate('b'), _candidate('a')], [_verdict('b'), _verdict('a')])
    lines = path.read_text(encoding='utf-8').splitlines()
    assert [json.loads(line)['id'] for line in lines] == ['a', 'b']


def test_failed_write_leaves_old_ledger_intact(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / 'Q1.jsonl'
    _write(path, [_verdict('a')])
    before = path.read_bytes()

    def fail(*_args: object, **_kwargs: object) -> None:
        raise OSError('disk full')

    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(phaseb.PhaseBError):
        ledger.merge_verdicts(path, [_candidate('a'), _candidate('b')], [_verdict('b')])
    assert path.read_bytes() == before
    assert [entry.name for entry in tmp_path.iterdir()] == ['Q1.jsonl']
