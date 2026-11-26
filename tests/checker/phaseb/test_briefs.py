"""Tests for the briefs registered for Phase B questions."""

import pathlib
import re

import pytest

import auditor.phaseb
import auditor.phaseb.candidates

SKILL = pathlib.Path(__file__).resolve().parents[3] / 'claude' / 'skills' / 'auditme' / 'SKILL.md'


def test_every_registered_brief_exists_with_one_positive_version() -> None:
    assert auditor.phaseb.candidates.REGISTRY
    for question in auditor.phaseb.candidates.REGISTRY:
        brief = auditor.phaseb.question_brief(question)
        assert brief.is_file(), question
        assert len(re.findall(r'^\*\*Brief version:\*\*', brief.read_text(encoding='utf-8'), re.MULTILINE)) == 1
        assert auditor.phaseb.brief_version(brief) >= 1


def test_a4_brief_holds_the_a4_question_text_from_skill_md() -> None:
    skill = SKILL.read_text(encoding='utf-8')
    question = next(line for line in skill.splitlines() if line.startswith('- **A4.'))
    brief = auditor.phaseb.question_brief('A4').read_text(encoding='utf-8')
    assert question.removeprefix('- ') in brief


def test_a4_brief_settles_each_threshold_and_the_output() -> None:
    brief = auditor.phaseb.question_brief('A4').read_text(encoding='utf-8')
    for phrase in ('domain error', 'subclass', 'passed in', 'constant', 'unresolved', 'callees', 'missing', 'extra', 'reason', 'printenv'):
        assert phrase in brief, phrase


def test_brief_without_a_version_line_is_refused(tmp_path: pathlib.Path) -> None:
    brief = tmp_path / 'Q.md'
    brief.write_text('# Q brief\n\nNo version here.\n', encoding='utf-8')
    with pytest.raises(auditor.phaseb.PhaseBError):
        auditor.phaseb.brief_version(brief)


def test_brief_with_two_version_lines_is_refused(tmp_path: pathlib.Path) -> None:
    brief = tmp_path / 'Q.md'
    brief.write_text('**Brief version:** 1\n\n**Brief version:** 2\n', encoding='utf-8')
    with pytest.raises(auditor.phaseb.PhaseBError):
        auditor.phaseb.brief_version(brief)


def question_line(question: str) -> str:
    skill = SKILL.read_text(encoding='utf-8')
    return next(line for line in skill.splitlines() if line.startswith(f'- **{question}.')).removeprefix('- ')


DOC_BRIEF_VERSIONS = {'Doc1': 5, 'Doc2': 4, 'Doc4': 9, 'Doc5': 9}
DOC_BRIEF_PHRASES = {'Doc1': 'tracked', 'Doc2': 'declared', 'Doc4': 'unresolved', 'Doc5': 'unresolved'}


@pytest.mark.parametrize('question', sorted(DOC_BRIEF_VERSIONS))
def test_doc_brief_holds_question_keys_and_security_rule(question: str) -> None:
    brief = auditor.phaseb.question_brief(question)
    text = brief.read_text(encoding='utf-8')
    version = DOC_BRIEF_VERSIONS[question]
    assert len(re.findall(rf'^\*\*Brief version:\*\* {version}$', text, re.MULTILINE)) == 1
    assert auditor.phaseb.brief_version(brief) == version
    assert question_line(question) in text
    for key in auditor.phaseb.candidates.question_kinds(question):
        assert f'`{key}`' in text, key
    for phrase in ('printenv', 'reason', DOC_BRIEF_PHRASES[question]):
        assert phrase in text, phrase


def test_doc5_question_covers_readme() -> None:
    assert 'Drift between `docs/` or `README.md` and `src/`.' in question_line('Doc5')


@pytest.mark.parametrize(
    'question,keys',
    [
        ('T1', ('reasons', 'tests', 'callers', 'test_files', 'private', 'privacy', 'direct', 'caller', 'findings', 'missing', 'reason', 'xfail', '--rejudge')),
        ('T2', ('params', 'returns', 'types', 'pairs', 'tests', 'test_files', 'property', 'findings', 'missing', 'reason', 'hypothesis', '--rejudge')),
    ],
)
def test_test_brief_holds_question_keys_and_security_rule(question: str, keys: tuple[str, ...]) -> None:
    brief = auditor.phaseb.question_brief(question)
    text = brief.read_text(encoding='utf-8')
    version = {'T1': 7, 'T2': 3}[question]
    assert len(re.findall(rf'^\*\*Brief version:\*\* {version}$', text, re.MULTILINE)) == 1
    assert auditor.phaseb.brief_version(brief) == version
    assert question_line(question) in text
    assert 'printenv' in text
    assert '[ -n "${VAR:-}" ]' in text
    for key in keys:
        assert key in text, key


def output_section(question: str) -> str:
    text = auditor.phaseb.question_brief(question).read_text(encoding='utf-8')
    return text[text.index('## Output') :]


def test_every_brief_output_asks_for_findings_with_its_registered_kinds() -> None:
    for question in auditor.phaseb.candidates.REGISTRY:
        output = output_section(question)
        assert '- `findings`:' in output, question
        for kind in auditor.phaseb.candidates.question_kinds(question):
            assert f'`{kind}`' in output or f'"{kind}"' in output, (question, kind)
        for line in output.splitlines():
            if line.startswith('- `'):
                top = line.split('`')[1]
                assert top in ('id', 'findings', 'reason'), (question, top)


def test_every_brief_input_names_the_earlier_verdict() -> None:
    for question in auditor.phaseb.candidates.REGISTRY:
        text = auditor.phaseb.question_brief(question).read_text(encoding='utf-8')
        input_section = text[text.index('## Input') : text.index('## Thresholds')]
        assert '`earlier`' in input_section, question
        assert 'what changed your judgement' in input_section, question


def test_brief_versions_after_the_findings_shape() -> None:
    expected = {'A4': 8, 'Doc1': 5, 'Doc2': 4, 'Doc4': 9, 'Doc5': 9, 'T1': 7, 'T2': 3, 'A1': 6, 'A11': 3, 'A17': 6, 'A19': 3}
    assert set(expected) == set(auditor.phaseb.candidates.REGISTRY)
    for question, version in expected.items():
        assert auditor.phaseb.brief_version(auditor.phaseb.question_brief(question)) == version, question


# Doc4 and Doc5 carry the same rulings from agents/reviews/brief-thresholds-4-2026-11-23.md.
DOC_ROUND_4_PHRASES = ('API block is judged', 'Module location row', "component's input", 'example row of a file', 'table of kinds', 'undated `path:line`')


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
        # The rulings of agents/reviews/brief-thresholds-4-2026-11-23.md.
        ('Doc4', DOC_ROUND_4_PHRASES),
        ('Doc5', DOC_ROUND_4_PHRASES),
        ('T1', ('framework runs', 'build a module constant', 'reads a property', 'third-party library calls back', 'over a socket')),
        ('A17', ('own written exception',)),
        # The rulings of agents/reviews/brief-thresholds-3-2026-11-22.md.
        ('A1', ('defines itself counts as a domain error',)),
        ('T2', ('`given` test is a direct call',)),
        (
            'Doc4',
            (
                'marked "(new)"',
                'not their\n  conditions',
                'usage block',
                'says exactly what counts',
                'read as a whole',
                'catch-all',
                'Testing section',
                'within each batch',
                'run as written',
                'one fair reading',
            ),
        ),
        ('Doc5', ('"Stops for" list', 'pinned to a commit')),
        # The rulings of agents/reviews/brief-thresholds-2-2026-11-22.md.
        ('A1', ('only one `subprocess.SubprocessError`', 'registers as a check', 'Name it in the reason')),
        ('A4', ("decorator's own body",)),
        ('A17', ('non-empty',)),
        (
            'Doc4',
            (
                "bullet's lead",
                'draft\n  docstring',
                'reproduced file block',
                'presents an order',
                'Motivation is a record',
                'complete list of what the\n  function declares',
                'whose target the drift is about',
            ),
        ),
        ('Doc5', ('causes under a symptom', 'Inline JSON', 'Words before a list', 'narrower than the code', 'note or warning box', 'setup\n  skill')),
        # The rulings of agents/reviews/brief-thresholds-2026-11-22.md.
        ('A1', ('pass no `timeout`', 'says it returns failures')),
        ('A4', ('registry lookup',)),
        ('T1', ('as a subprocess', 'usefixtures', 'passes the candidate as an argument')),
        ('Doc4', ('header `**Date:**`', "what the spec's own change did", '`TODO.md` or `DONE.md`', 'opens with a date', 'names the change or amendment')),
        ('Doc5', ('A parenthetical list', 'A claim broader than the code')),
    ],
)
def test_brief_settles_its_thresholds(question: str, phrases: tuple[str, ...]) -> None:
    text = auditor.phaseb.question_brief(question).read_text(encoding='utf-8')
    thresholds = text.split('## Thresholds', 1)[1].split('## Output', 1)[0]
    for phrase in phrases:
        assert phrase in thresholds, (question, phrase)


def test_every_brief_gives_an_unsettled_case_the_default_verdict() -> None:
    # G1 of agents/reviews/brief-thresholds-3-2026-11-22.md.
    for question in auditor.phaseb.candidates.REGISTRY:
        text = auditor.phaseb.question_brief(question).read_text(encoding='utf-8')
        assert 'A case this brief does not settle is not a finding' in text, question
