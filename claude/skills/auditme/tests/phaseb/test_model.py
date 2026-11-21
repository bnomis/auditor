"""Tests for the Phase B data model and question registry."""

import collections.abc
import dataclasses
import pathlib

import pytest
from auditme import phaseb
from auditme.phaseb import candidates


def _verdict(**overrides) -> phaseb.Verdict:
    fields = {
        'question': 'Q1',
        'id': 'src/pkg/mod.py::probe',
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


@pytest.fixture
def isolated_registry() -> collections.abc.Iterator[None]:
    """Run a test against an empty registry and restore the real one after."""
    saved = dict(candidates.REGISTRY)
    saved_kinds = dict(candidates.KINDS)
    candidates.REGISTRY.clear()
    candidates.KINDS.clear()
    yield
    candidates.REGISTRY.clear()
    candidates.REGISTRY.update(saved)
    candidates.KINDS.clear()
    candidates.KINDS.update(saved_kinds)


def test_flagged_when_any_findings_list_is_non_empty() -> None:
    assert _verdict(findings={'missing': ['ProbeError'], 'extra': []}).flagged
    assert _verdict(findings={'missing': [], 'extra': ['ProbeError']}).flagged


def test_not_flagged_when_all_findings_lists_are_empty() -> None:
    assert not _verdict().flagged


def test_not_flagged_when_dismissed() -> None:
    assert not _verdict(findings={'missing': ['ProbeError'], 'extra': []}, dismissed='2026-01-02: intended').flagged


def test_candidate_and_verdict_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        _candidate('a').hash = 'x'  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        _verdict().reason = 'x'  # type: ignore[misc]


def test_register_question_records_lister_and_brief(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    brief = tmp_path / 'Q1.md'

    @phaseb.register_question('Q1', brief, ('missing',))
    def lister(root: pathlib.Path) -> list[phaseb.Candidate]:
        return [_candidate('b'), _candidate('a')]

    assert phaseb.question_brief('Q1') == brief
    assert [c.id for c in phaseb.list_candidates('Q1', tmp_path)] == ['a', 'b']


def test_register_question_returns_the_lister(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    def lister(root: pathlib.Path) -> list[phaseb.Candidate]:
        return []

    assert phaseb.register_question('Q1', tmp_path / 'Q1.md', ('missing',))(lister) is lister


def test_list_candidates_on_unregistered_question_raises(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    with pytest.raises(phaseb.PhaseBError, match='Q9'):
        phaseb.list_candidates('Q9', tmp_path)


def test_question_brief_on_unregistered_question_raises(isolated_registry: None) -> None:
    with pytest.raises(phaseb.PhaseBError, match='Q9'):
        phaseb.question_brief('Q9')


def test_question_registered_without_a_size_reads_back_the_default(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    phaseb.register_question('Q1', tmp_path / 'Q1.md', ('missing',))(lambda root: [])

    assert phaseb.question_batch_size('Q1') == 48


def test_question_registered_with_a_size_reads_it_back(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    phaseb.register_question('Q1', tmp_path / 'Q1.md', ('missing',), batch_size=12)(lambda root: [])

    assert phaseb.question_batch_size('Q1') == 12


def test_question_batch_size_on_unregistered_question_raises(isolated_registry: None) -> None:
    with pytest.raises(phaseb.PhaseBError, match='Q9'):
        phaseb.question_batch_size('Q9')


def test_registering_a_question_stores_its_kinds_in_order(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    phaseb.register_question('Q1', tmp_path / 'Q1.md', ('stale', 'missing'))(lambda root: [])

    assert phaseb.question_kinds('Q1') == ('stale', 'missing')


def test_empty_kinds_raise_and_register_nothing(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    with pytest.raises(phaseb.PhaseBError, match='Q1'):
        phaseb.register_question('Q1', tmp_path / 'Q1.md', ())(lambda root: [])

    assert 'Q1' not in candidates.REGISTRY
    assert 'Q1' not in candidates.KINDS


def test_repeated_kind_raises_and_registers_nothing(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    with pytest.raises(phaseb.PhaseBError, match='Q1'):
        phaseb.register_question('Q1', tmp_path / 'Q1.md', ('missing', 'missing'))(lambda root: [])

    assert 'Q1' not in candidates.REGISTRY
    assert 'Q1' not in candidates.KINDS


def test_question_kinds_on_unregistered_question_raises(isolated_registry: None) -> None:
    with pytest.raises(phaseb.PhaseBError, match='Q9'):
        phaseb.question_kinds('Q9')


def test_every_registered_question_has_the_specified_kinds() -> None:
    expected = {
        'A1': ('call',),
        'A11': ('unexhausted',),
        'A17': ('surface',),
        'A19': ('handler',),
        'A4': ('missing', 'extra'),
        'Doc1': ('stale', 'missing'),
        'Doc2': ('stale', 'missing'),
        'Doc4': ('drift',),
        'Doc5': ('drift',),
        'T1': ('missing',),
        'T2': ('missing',),
    }

    assert {question: phaseb.question_kinds(question) for question in candidates.REGISTRY} == expected
