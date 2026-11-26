"""Tests for reading, merging and dismissing ledger verdicts."""

import dataclasses
import json
import os
import typing

import conftest
import pytest

import auditor.phaseb
import auditor.phaseb.candidates
import auditor.phaseb.ledger

if typing.TYPE_CHECKING:
    import pathlib


def write_verdicts(path: pathlib.Path, verdicts: list[auditor.phaseb.candidates.Verdict]) -> None:
    path.write_text(''.join(json.dumps(dataclasses.asdict(verdict)) + '\n' for verdict in verdicts), encoding='utf-8')


def test_missing_ledger_reads_as_empty(tmp_path: pathlib.Path) -> None:
    assert auditor.phaseb.ledger.read_ledger(tmp_path / 'Q1.jsonl') == {}


def test_ledger_round_trips(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    verdict = conftest.make_verdict(findings={'missing': ['ProbeError'], 'extra': []})
    write_verdicts(path, [verdict])
    assert auditor.phaseb.ledger.read_ledger(path) == {verdict.id: verdict}


def test_unparseable_line_raises(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    path.write_text('{not json\n', encoding='utf-8')
    with pytest.raises(auditor.phaseb.PhaseBError):
        auditor.phaseb.ledger.read_ledger(path)


def test_line_missing_a_field_raises(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    record = dataclasses.asdict(conftest.make_verdict())
    del record['reason']
    path.write_text(json.dumps(record) + '\n', encoding='utf-8')
    with pytest.raises(auditor.phaseb.PhaseBError, match='reason'):
        auditor.phaseb.ledger.read_ledger(path)


def test_directory_in_place_of_ledger_raises(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    path.mkdir()
    with pytest.raises(auditor.phaseb.PhaseBError):
        auditor.phaseb.ledger.read_ledger(path)


def test_merge_writes_new_and_keeps_current(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'ledger' / 'Q1.jsonl'
    path.parent.mkdir()
    old = conftest.make_verdict('a')
    write_verdicts(path, [old])
    new = conftest.make_verdict('b')
    result = auditor.phaseb.ledger.merge_verdicts(path, [conftest.make_candidate('a'), conftest.make_candidate('b')], [new])
    assert (result.written, result.kept, result.dropped) == (1, 1, 0)
    assert auditor.phaseb.ledger.read_ledger(path) == {'a': old, 'b': new}


def test_merge_creates_missing_directory(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'agents' / 'ledger' / 'Q1.jsonl'
    auditor.phaseb.ledger.merge_verdicts(path, [conftest.make_candidate('a')], [conftest.make_verdict('a')])
    assert set(auditor.phaseb.ledger.read_ledger(path)) == {'a'}


def test_merge_drops_entry_that_is_no_longer_a_candidate(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    write_verdicts(path, [conftest.make_verdict('a'), conftest.make_verdict('gone')])
    result = auditor.phaseb.ledger.merge_verdicts(path, [conftest.make_candidate('a')], [])
    assert (result.written, result.kept, result.dropped) == (0, 1, 1)
    assert set(auditor.phaseb.ledger.read_ledger(path)) == {'a'}


def test_unchanged_findings_keep_the_dismissal(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    findings = {'missing': ['ProbeError'], 'extra': []}
    write_verdicts(path, [conftest.make_verdict('a', findings=findings, dismissed='2026-01-02: intended')])
    auditor.phaseb.ledger.merge_verdicts(path, [conftest.make_candidate('a')], [conftest.make_verdict('a', hash='new', findings=findings)])
    merged = auditor.phaseb.ledger.read_ledger(path)['a']
    assert merged.hash == 'new'
    assert merged.dismissed == '2026-01-02: intended'
    assert not merged.flagged


def test_changed_findings_and_code_drop_the_dismissal(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    write_verdicts(path, [conftest.make_verdict('a', findings={'missing': ['ProbeError'], 'extra': []}, dismissed='2026-01-02: intended')])
    auditor.phaseb.ledger.merge_verdicts(
        path, [conftest.make_candidate('a')], [conftest.make_verdict('a', hash='new', findings={'missing': ['OtherError'], 'extra': []})]
    )
    merged = auditor.phaseb.ledger.read_ledger(path)['a']
    assert merged.dismissed is None
    assert merged.flagged


def test_unchanged_code_keeps_the_dismissal_across_a_brief_bump_and_reworded_findings(tmp_path: pathlib.Path) -> None:
    """A re-judge under a new brief writes the findings afresh; the code is unchanged, so the dismissal stands."""
    path = tmp_path / 'Q1.jsonl'
    write_verdicts(path, [conftest.make_verdict('a', findings={'missing': ['ProbeError is never raised'], 'extra': []}, dismissed='2026-01-02: intended')])
    reworded = conftest.make_verdict('a', brief_version=2, findings={'missing': ['the body never raises ProbeError'], 'extra': []})
    auditor.phaseb.ledger.merge_verdicts(path, [conftest.make_candidate('a')], [reworded])
    merged = auditor.phaseb.ledger.read_ledger(path)['a']
    assert merged.brief_version == 2
    assert merged.findings == reworded.findings
    assert merged.dismissed == '2026-01-02: intended'
    assert not merged.flagged


def test_dismiss_records_date_and_reason(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    write_verdicts(path, [conftest.make_verdict('a', findings={'missing': ['ProbeError'], 'extra': []})])
    auditor.phaseb.ledger.dismiss_verdict(path, 'a', 'intended', today='2026-02-03')
    dismissed = auditor.phaseb.ledger.read_ledger(path)['a']
    assert dismissed.dismissed == '2026-02-03: intended'
    assert not dismissed.flagged


def test_dismiss_unknown_id_raises(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    write_verdicts(path, [conftest.make_verdict('a')])
    with pytest.raises(auditor.phaseb.PhaseBError, match='nope'):
        auditor.phaseb.ledger.dismiss_verdict(path, 'nope', 'reason', today='2026-02-03')


def test_ledger_is_written_one_sorted_line_per_verdict(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'Q1.jsonl'
    auditor.phaseb.ledger.merge_verdicts(
        path, [conftest.make_candidate('b'), conftest.make_candidate('a')], [conftest.make_verdict('b'), conftest.make_verdict('a')]
    )
    lines = path.read_text(encoding='utf-8').splitlines()
    assert [json.loads(line)['id'] for line in lines] == ['a', 'b']


def test_failed_write_leaves_old_ledger_intact(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / 'Q1.jsonl'
    write_verdicts(path, [conftest.make_verdict('a')])
    before = path.read_bytes()

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError('disk full')

    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(auditor.phaseb.PhaseBError):
        auditor.phaseb.ledger.merge_verdicts(path, [conftest.make_candidate('a'), conftest.make_candidate('b')], [conftest.make_verdict('b')])
    assert path.read_bytes() == before
    assert [entry.name for entry in tmp_path.iterdir()] == ['Q1.jsonl']
