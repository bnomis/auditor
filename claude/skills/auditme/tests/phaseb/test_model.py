"""Tests for the Phase B data model and question registry."""

import dataclasses
import typing

import auditme.phaseb
import auditme.phaseb.candidates
import conftest
import pytest

if typing.TYPE_CHECKING:
    import collections.abc
    import pathlib

# auditme: accept[non-alphabetical-literal] the order Doc1 and Doc2 register their kinds in
AGENTS_DOC_KINDS = ('stale', 'missing')


def make_model_verdict(**overrides) -> auditme.phaseb.Verdict:
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
    return auditme.phaseb.Verdict(**fields)


@pytest.fixture
def isolated_registry() -> collections.abc.Iterator[None]:
    """Run a test against an empty registry and restore the real one after."""
    saved = dict(auditme.phaseb.candidates.REGISTRY)
    saved_kinds = dict(auditme.phaseb.candidates.KINDS)
    auditme.phaseb.candidates.REGISTRY.clear()
    auditme.phaseb.candidates.KINDS.clear()
    yield
    auditme.phaseb.candidates.REGISTRY.clear()
    auditme.phaseb.candidates.REGISTRY.update(saved)
    auditme.phaseb.candidates.KINDS.clear()
    auditme.phaseb.candidates.KINDS.update(saved_kinds)


def test_flagged_when_any_findings_list_is_non_empty() -> None:
    assert make_model_verdict(findings={'missing': ['ProbeError'], 'extra': []}).flagged
    assert make_model_verdict(findings={'missing': [], 'extra': ['ProbeError']}).flagged


def test_not_flagged_when_all_findings_lists_are_empty() -> None:
    assert not make_model_verdict().flagged


def test_not_flagged_when_dismissed() -> None:
    assert not make_model_verdict(findings={'missing': ['ProbeError'], 'extra': []}, dismissed='2026-01-02: intended').flagged


def test_candidate_and_verdict_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        conftest.make_candidate('a').hash = 'x'  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        make_model_verdict().reason = 'x'  # type: ignore[misc]


def test_register_question_records_lister_and_brief(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    brief = tmp_path / 'Q1.md'

    @auditme.phaseb.register_question('Q1', brief, ('missing',))
    def lister(root: pathlib.Path) -> list[auditme.phaseb.Candidate]:
        return [conftest.make_candidate('b'), conftest.make_candidate('a')]

    assert auditme.phaseb.question_brief('Q1') == brief
    assert [c.id for c in auditme.phaseb.list_candidates('Q1', tmp_path)] == ['a', 'b']


def test_register_question_returns_the_lister(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    def lister(root: pathlib.Path) -> list[auditme.phaseb.Candidate]:
        return []

    assert auditme.phaseb.register_question('Q1', tmp_path / 'Q1.md', ('missing',))(lister) is lister


def test_list_candidates_on_unregistered_question_raises(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    with pytest.raises(auditme.phaseb.PhaseBError, match='Q9'):
        auditme.phaseb.list_candidates('Q9', tmp_path)


def test_question_brief_on_unregistered_question_raises(isolated_registry: None) -> None:
    with pytest.raises(auditme.phaseb.PhaseBError, match='Q9'):
        auditme.phaseb.question_brief('Q9')


def test_question_registered_without_a_size_reads_back_the_default(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    auditme.phaseb.register_question('Q1', tmp_path / 'Q1.md', ('missing',))(lambda root: [])

    assert auditme.phaseb.question_batch_size('Q1') == 48


def test_question_registered_with_a_size_reads_it_back(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    auditme.phaseb.register_question('Q1', tmp_path / 'Q1.md', ('missing',), batch_size=12)(lambda root: [])

    assert auditme.phaseb.question_batch_size('Q1') == 12


def test_question_batch_size_on_unregistered_question_raises(isolated_registry: None) -> None:
    with pytest.raises(auditme.phaseb.PhaseBError, match='Q9'):
        auditme.phaseb.question_batch_size('Q9')


def test_registering_a_question_stores_its_kinds_in_order(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    auditme.phaseb.register_question('Q1', tmp_path / 'Q1.md', ('second', 'first'))(lambda root: [])

    assert auditme.phaseb.question_kinds('Q1') == ('second', 'first')


def test_empty_kinds_raise_and_register_nothing(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    with pytest.raises(auditme.phaseb.PhaseBError, match='Q1'):
        auditme.phaseb.register_question('Q1', tmp_path / 'Q1.md', ())(lambda root: [])

    assert 'Q1' not in auditme.phaseb.candidates.REGISTRY
    assert 'Q1' not in auditme.phaseb.candidates.KINDS


def test_repeated_kind_raises_and_registers_nothing(isolated_registry: None, tmp_path: pathlib.Path) -> None:
    with pytest.raises(auditme.phaseb.PhaseBError, match='Q1'):
        auditme.phaseb.register_question('Q1', tmp_path / 'Q1.md', ('missing', 'missing'))(lambda root: [])

    assert 'Q1' not in auditme.phaseb.candidates.REGISTRY
    assert 'Q1' not in auditme.phaseb.candidates.KINDS


def test_question_kinds_on_unregistered_question_raises(isolated_registry: None) -> None:
    with pytest.raises(auditme.phaseb.PhaseBError, match='Q9'):
        auditme.phaseb.question_kinds('Q9')


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

    assert {question: auditme.phaseb.question_kinds(question) for question in auditme.phaseb.candidates.REGISTRY} == expected
