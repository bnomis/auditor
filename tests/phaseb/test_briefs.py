"""Tests for the briefs registered for Phase B questions."""

import pathlib
import re

import pytest
from auditme import phaseb

SKILL = pathlib.Path(__file__).resolve().parents[2] / 'SKILL.md'


def test_every_registered_brief_exists_with_one_positive_version() -> None:
    assert phaseb.candidates.REGISTRY
    for question in phaseb.candidates.REGISTRY:
        brief = phaseb.question_brief(question)
        assert brief.is_file(), question
        assert len(re.findall(r'^\*\*Brief version:\*\*', brief.read_text(encoding='utf-8'), re.MULTILINE)) == 1
        assert phaseb.brief_version(brief) >= 1


def test_a4_brief_holds_the_a4_question_text_from_skill_md() -> None:
    skill = SKILL.read_text(encoding='utf-8')
    question = next(line for line in skill.splitlines() if line.startswith('- **A4.'))
    brief = phaseb.question_brief('A4').read_text(encoding='utf-8')
    assert question.removeprefix('- ') in brief


def test_a4_brief_settles_each_threshold_and_the_output() -> None:
    brief = phaseb.question_brief('A4').read_text(encoding='utf-8')
    for phrase in ('domain error', 'subclass', 'passed in', 'constant', 'unresolved', 'callees', 'missing', 'extra', 'reason', 'printenv'):
        assert phrase in brief, phrase


def test_brief_without_a_version_line_is_refused(tmp_path: pathlib.Path) -> None:
    brief = tmp_path / 'Q.md'
    brief.write_text('# Q brief\n\nNo version here.\n', encoding='utf-8')
    with pytest.raises(phaseb.PhaseBError):
        phaseb.brief_version(brief)


def test_brief_with_two_version_lines_is_refused(tmp_path: pathlib.Path) -> None:
    brief = tmp_path / 'Q.md'
    brief.write_text('**Brief version:** 1\n\n**Brief version:** 2\n', encoding='utf-8')
    with pytest.raises(phaseb.PhaseBError):
        phaseb.brief_version(brief)


def _question_line(question: str) -> str:
    skill = SKILL.read_text(encoding='utf-8')
    return next(line for line in skill.splitlines() if line.startswith(f'- **{question}.')).removeprefix('- ')


@pytest.mark.parametrize(
    ('question', 'keys'),
    [('Doc1', ('stale', 'missing')), ('Doc2', ('stale', 'missing')), ('Doc4', ('drift',)), ('Doc5', ('drift',))],
)
def test_doc_brief_holds_question_keys_and_security_rule(question: str, keys: tuple[str, ...]) -> None:
    brief = phaseb.question_brief(question)
    text = brief.read_text(encoding='utf-8')
    assert len(re.findall(r'^\*\*Brief version:\*\* 1$', text, re.MULTILINE)) == 1
    assert phaseb.brief_version(brief) == 1
    assert _question_line(question) in text
    for key in keys:
        assert f'`{key}`' in text, key
    for phrase in ('printenv', 'reason', 'unresolved' if question in ('Doc4', 'Doc5') else 'tracked' if question == 'Doc1' else 'declared'):
        assert phrase in text, phrase


def test_doc5_question_covers_readme() -> None:
    assert 'Drift between `docs/` or `README.md` and `src/`.' in _question_line('Doc5')
