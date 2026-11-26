"""Tests for the Phase B data model and question registry."""

import dataclasses
import typing

import conftest
import pytest

import auditor.phaseb
import auditor.phaseb.candidates

if typing.TYPE_CHECKING:
    import collections.abc
    import pathlib

# auditme: accept[non-alphabetical-literal] the order Doc1 and Doc2 register their kinds in
AGENTS_DOC_KINDS = ('stale', 'missing')


@pytest.fixture
def isolated_registry() -> collections.abc.Iterator[None]:
    """Run a test against an empty registry and restore the real one after."""
    saved = dict(auditor.phaseb.candidates.REGISTRY)
    saved_kinds = dict(auditor.phaseb.candidates.KINDS)
    auditor.phaseb.candidates.REGISTRY.clear()
    auditor.phaseb.candidates.KINDS.clear()
    yield
    auditor.phaseb.candidates.REGISTRY.clear()
    auditor.phaseb.candidates.REGISTRY.update(saved)
    auditor.phaseb.candidates.KINDS.clear()
    auditor.phaseb.candidates.KINDS.update(saved_kinds)


def test_flagged_when_any_findings_list_is_non_empty() -> None:
    assert conftest.make_verdict(findings={'missing': ['ProbeError'], 'extra': []}).flagged
    assert conftest.make_verdict(findings={'missing': [], 'extra': ['ProbeError']}).flagged


def test_not_flagged_when_all_findings_lists_are_empty() -> None:
    assert not conftest.make_verdict().flagged


def test_not_flagged_when_dismissed() -> None:
    assert not conftest.make_verdict(findings={'missing': ['ProbeError'], 'extra': []}, dismissed='2026-01-02: intended').flagged


def test_candidate_and_verdict_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        conftest.make_candidate('a').hash = 'x'  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        conftest.make_verdict().reason = 'x'  # type: ignore[misc]


def test_register_question_records_lister_and_brief(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    brief = tmp_path / 'Q1.md'

    @auditor.phaseb.candidates.register_question('Q1', brief, ('missing',))
    def lister(root: pathlib.Path) -> list[auditor.api.candidates.Candidate]:
        return [conftest.make_candidate('b'), conftest.make_candidate('a')]

    assert auditor.phaseb.question_brief('Q1') == brief
    assert [c.id for c in auditor.phaseb.list_candidates('Q1', tmp_path)] == ['a', 'b']


def test_register_question_returns_the_lister(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    def lister(root: pathlib.Path) -> list[auditor.api.candidates.Candidate]:
        return []

    assert auditor.phaseb.candidates.register_question('Q1', tmp_path / 'Q1.md', ('missing',))(lister) is lister


def test_list_candidates_on_unregistered_question_raises(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    with pytest.raises(auditor.phaseb.PhaseBError, match='Q9'):
        auditor.phaseb.list_candidates('Q9', tmp_path)


def test_question_brief_on_unregistered_question_raises(isolated_registry: None) -> None:
    with pytest.raises(auditor.phaseb.PhaseBError, match='Q9'):
        auditor.phaseb.question_brief('Q9')


def test_question_registered_without_a_size_reads_back_the_default(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    auditor.phaseb.candidates.register_question('Q1', tmp_path / 'Q1.md', ('missing',))(lambda root: [])

    assert auditor.phaseb.question_batch_size('Q1') == 48


def test_question_registered_with_a_size_reads_it_back(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    auditor.phaseb.candidates.register_question('Q1', tmp_path / 'Q1.md', ('missing',), batch_size=12)(lambda root: [])

    assert auditor.phaseb.question_batch_size('Q1') == 12


def test_question_batch_size_on_unregistered_question_raises(isolated_registry: None) -> None:
    with pytest.raises(auditor.phaseb.PhaseBError, match='Q9'):
        auditor.phaseb.question_batch_size('Q9')


def test_registering_a_question_stores_its_kinds_in_order(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    auditor.phaseb.candidates.register_question('Q1', tmp_path / 'Q1.md', ('second', 'first'))(lambda root: [])

    assert auditor.phaseb.candidates.question_kinds('Q1') == ('second', 'first')


def test_empty_kinds_raise_and_register_nothing(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    with pytest.raises(auditor.phaseb.PhaseBError, match='Q1'):
        auditor.phaseb.candidates.register_question('Q1', tmp_path / 'Q1.md', ())(lambda root: [])

    assert 'Q1' not in auditor.phaseb.candidates.REGISTRY
    assert 'Q1' not in auditor.phaseb.candidates.KINDS


def test_repeated_kind_raises_and_registers_nothing(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    with pytest.raises(auditor.phaseb.PhaseBError, match='Q1'):
        auditor.phaseb.candidates.register_question('Q1', tmp_path / 'Q1.md', ('missing', 'missing'))(lambda root: [])

    assert 'Q1' not in auditor.phaseb.candidates.REGISTRY
    assert 'Q1' not in auditor.phaseb.candidates.KINDS


def test_question_kinds_on_unregistered_question_raises(isolated_registry: None) -> None:
    with pytest.raises(auditor.phaseb.PhaseBError, match='Q9'):
        auditor.phaseb.candidates.question_kinds('Q9')


def test_every_registered_question_has_the_specified_kinds() -> None:
    expected = {
        'A1': ('call',),
        'A11': ('unexhausted',),
        'A17': ('surface',),
        'A19': ('handler',),
        'A4': ('missing', 'extra'),
        'Doc1': AGENTS_DOC_KINDS,
        'Doc2': AGENTS_DOC_KINDS,
        'Doc4': ('drift',),
        'Doc5': ('drift',),
        'T1': ('missing',),
        'T2': ('missing',),
    }

    assert {question: auditor.phaseb.candidates.question_kinds(question) for question in auditor.phaseb.candidates.REGISTRY} == expected
