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


DOC_BRIEF_VERSIONS = {'Doc1': 3, 'Doc2': 2, 'Doc4': 4, 'Doc5': 4}


@pytest.mark.parametrize(
    ('question', 'keys'),
    [('Doc1', ('stale', 'missing')), ('Doc2', ('stale', 'missing')), ('Doc4', ('drift',)), ('Doc5', ('drift',))],
)
def test_doc_brief_holds_question_keys_and_security_rule(question: str, keys: tuple[str, ...]) -> None:
    brief = phaseb.question_brief(question)
    text = brief.read_text(encoding='utf-8')
    version = DOC_BRIEF_VERSIONS[question]
    assert len(re.findall(rf'^\*\*Brief version:\*\* {version}$', text, re.MULTILINE)) == 1
    assert phaseb.brief_version(brief) == version
    assert _question_line(question) in text
    for key in keys:
        assert f'`{key}`' in text, key
    for phrase in ('printenv', 'reason', 'unresolved' if question in ('Doc4', 'Doc5') else 'tracked' if question == 'Doc1' else 'declared'):
        assert phrase in text, phrase


def test_doc5_question_covers_readme() -> None:
    assert 'Drift between `docs/` or `README.md` and `src/`.' in _question_line('Doc5')


@pytest.mark.parametrize(
    ('question', 'keys'),
    [
        ('T1', ('reasons', 'tests', 'callers', 'test_files', 'private', 'direct', 'caller', 'findings', 'missing', 'reason', 'xfail', '--rejudge')),
        ('T2', ('params', 'returns', 'types', 'pairs', 'tests', 'test_files', 'property', 'findings', 'missing', 'reason', 'hypothesis', '--rejudge')),
    ],
)
def test_test_brief_holds_question_keys_and_security_rule(question: str, keys: tuple[str, ...]) -> None:
    brief = phaseb.question_brief(question)
    text = brief.read_text(encoding='utf-8')
    version = {'T1': 2, 'T2': 1}[question]
    assert len(re.findall(rf'^\*\*Brief version:\*\* {version}$', text, re.MULTILINE)) == 1
    assert phaseb.brief_version(brief) == version
    assert _question_line(question) in text
    assert 'printenv' in text
    assert '[ -n "${VAR:-}" ]' in text
    for key in keys:
        assert key in text, key


def _output_section(question: str) -> str:
    text = phaseb.question_brief(question).read_text(encoding='utf-8')
    return text[text.index('## Output') :]


def test_every_brief_output_asks_for_findings_with_its_registered_kinds() -> None:
    for question in phaseb.candidates.REGISTRY:
        output = _output_section(question)
        assert '- `findings`:' in output, question
        for kind in phaseb.candidates.question_kinds(question):
            assert f'`{kind}`' in output or f'"{kind}"' in output, (question, kind)
        for line in output.splitlines():
            if line.startswith('- `'):
                top = line.split('`')[1]
                assert top in ('id', 'findings', 'reason'), (question, top)


def test_brief_versions_after_the_findings_shape() -> None:
    expected = {'A4': 4, 'Doc1': 3, 'Doc2': 2, 'Doc4': 4, 'Doc5': 4, 'T1': 2, 'T2': 1, 'A1': 1, 'A11': 1, 'A17': 1, 'A19': 1}
    assert set(expected) == set(phaseb.candidates.REGISTRY)
    for question, version in expected.items():
        assert phaseb.brief_version(phaseb.question_brief(question)) == version, question


@pytest.mark.parametrize(
    ('question', 'phrases'),
    [
        ('Doc4', ('states its own date', 'other statements')),
        ('Doc5', ('states its own date', 'other statements', 'out a line the code prints', 'presents itself as complete')),
        ('Doc1', ('.gitignore',)),
        # The rulings of agents/reviews/checker-requests-2026-11-21.md.
        (
            'T1',
            (
                're-export of the candidate',
                'singledispatch',
                'A dunder the language runs',
                "A call made by a wrapper is the wrapper's",
                'helper defined in the test file',
            ),
        ),
        ('A4', ('registered implementations', 'invariant guard')),
        ('Doc4', ('A dated sentence inside an undated section', '"Today" in an implemented spec', 'reported\n  once')),
        ('Doc5', ('names more than one\n  keyword', 'A dated sentence inside an undated section', '"Today" in an implemented spec', 'reported\n  once')),
    ],
)
def test_brief_settles_its_thresholds(question: str, phrases: tuple[str, ...]) -> None:
    text = phaseb.question_brief(question).read_text(encoding='utf-8')
    thresholds = text.split('## Thresholds', 1)[1].split('## Output', 1)[0]
    for phrase in phrases:
        assert phrase in thresholds, (question, phrase)
