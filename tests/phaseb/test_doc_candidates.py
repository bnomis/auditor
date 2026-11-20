"""Tests for the Doc4 and Doc5 listers: documents, pairs, unresolved names and hashes."""

import pathlib
import subprocess
import textwrap

import pytest
from auditme import phaseb
from auditme.phaseb import candidates

MOD = """
    def run_it():
        return 1


    def dup_name():
        return 1


    class Probe:
        size: int = 3

        def load(self):
            return 2
"""

OTHER = """
    def dup_name():
        return 2
"""

SPEC = """
    # Probe

    **Status:** implemented

    ## Run

    The `run_it` function runs.

    Nothing else happens here.

    ## Other

    The `Probe.load` method loads.
"""

DRAFT = """
    # Draft

    **Status:** proposed

    ## Run

    The `run_it` function runs.
"""

GUIDE = """
    # Guide

    ## Usage

    Call `run_it` to start.

    See `docs/guide.md` too.
"""

FILES = {
    'src/pkg/__init__.py': '',
    'src/pkg/mod.py': MOD,
    'src/pkg/other.py': OTHER,
    'agents/specs/probe/spec.md': SPEC,
    'agents/specs/draft/spec.md': DRAFT,
    'docs/guide.md': GUIDE,
    'README.md': '# Probe\n\n## Start\n\nRun `run_it` first.\n',
    'AGENTS.md': '# Agents\n',
}


def write(root: pathlib.Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding='utf-8')


@pytest.fixture
def root(tmp_path: pathlib.Path) -> pathlib.Path:
    for name, text in FILES.items():
        write(tmp_path, name, text)
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'add', '-A'], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def listed(root: pathlib.Path, question: str) -> dict[str, phaseb.Candidate]:
    return {candidate.id: candidate for candidate in phaseb.list_candidates(question, root)}


def test_proposed_spec_is_not_listed_for_doc4(root: pathlib.Path) -> None:
    ids = listed(root, 'Doc4')
    assert any(name.startswith('agents/specs/probe/spec.md::') for name in ids)
    assert not any(name.startswith('agents/specs/draft/') for name in ids)


def test_doc4_does_not_list_docs_or_readme(root: pathlib.Path) -> None:
    assert not any(name.startswith(('docs/', 'README.md')) for name in listed(root, 'Doc4'))


def test_root_readme_and_docs_are_listed_for_doc5(root: pathlib.Path) -> None:
    ids = listed(root, 'Doc5')
    assert any(name.startswith('README.md::') for name in ids)
    assert any(name.startswith('docs/guide.md::') for name in ids)
    assert not any(name.startswith('agents/') for name in ids)


def test_pair_id_span_and_payload(root: pathlib.Path) -> None:
    candidate = listed(root, 'Doc5')['docs/guide.md::Guide > Usage::src/pkg/mod.py::run_it']
    assert candidate.question == 'Doc5'
    assert candidate.path == 'docs/guide.md'
    assert (candidate.start, candidate.end) == (4, 8)
    assert candidate.payload['target']['id'] == 'src/pkg/mod.py::run_it'
    assert candidate.payload['target']['kind'] == 'function'
    assert candidate.payload['lines'] == [{'line': 6, 'text': 'Call `run_it` to start.'}]


def test_file_target_is_a_pair_too(root: pathlib.Path) -> None:
    assert 'docs/guide.md::Guide > Usage::docs/guide.md' in listed(root, 'Doc5')


def test_target_source_edit_changes_its_pair_only(root: pathlib.Path) -> None:
    before = listed(root, 'Doc4')
    write(root, 'src/pkg/mod.py', MOD.replace('return 1\n\n\n    def dup', 'return 9\n\n\n    def dup', 1))
    after = listed(root, 'Doc4')
    run_pair = 'agents/specs/probe/spec.md::Probe > Run::src/pkg/mod.py::run_it'
    other_pair = 'agents/specs/probe/spec.md::Probe > Other::src/pkg/mod.py::Probe.load'
    assert before[run_pair].hash != after[run_pair].hash
    assert before[other_pair].hash == after[other_pair].hash


def test_block_naming_the_target_changes_the_hash(root: pathlib.Path) -> None:
    pair = 'agents/specs/probe/spec.md::Probe > Run::src/pkg/mod.py::run_it'
    before = listed(root, 'Doc4')[pair].hash
    write(root, 'agents/specs/probe/spec.md', SPEC.replace('function runs', 'function starts'))
    assert listed(root, 'Doc4')[pair].hash != before


def test_block_not_naming_the_target_leaves_the_hash(root: pathlib.Path) -> None:
    pair = 'agents/specs/probe/spec.md::Probe > Run::src/pkg/mod.py::run_it'
    before = listed(root, 'Doc4')[pair].hash
    write(root, 'agents/specs/probe/spec.md', SPEC.replace('Nothing else happens', 'Something else happens'))
    assert listed(root, 'Doc4')[pair].hash == before


def test_undefined_name_gets_an_unresolved_candidate_until_defined(root: pathlib.Path) -> None:
    write(root, 'docs/guide.md', textwrap.dedent(GUIDE) + '\nAlso `missing_fn` exists.\n')
    key = 'docs/guide.md::Guide > Usage::(unresolved)'
    candidate = listed(root, 'Doc5')[key]
    assert candidate.payload['tokens'] == [{'name': 'missing_fn', 'line': 10, 'definitions': []}]
    write(root, 'src/pkg/more.py', 'def missing_fn():\n    return 1\n')
    subprocess.run(['git', 'add', '-A'], cwd=root, check=True, capture_output=True)
    after = listed(root, 'Doc5')
    assert key not in after
    assert 'docs/guide.md::Guide > Usage::src/pkg/more.py::missing_fn' in after


def test_ambiguous_name_goes_to_unresolved_with_both_definitions(root: pathlib.Path) -> None:
    write(root, 'docs/guide.md', textwrap.dedent(GUIDE) + '\nAlso `dup_name` exists.\n')
    candidate = listed(root, 'Doc5')['docs/guide.md::Guide > Usage::(unresolved)']
    (entry,) = candidate.payload['tokens']
    assert entry['name'] == 'dup_name'
    assert sorted(found['id'] for found in entry['definitions']) == ['src/pkg/mod.py::dup_name', 'src/pkg/other.py::dup_name']
    assert not any(name.endswith('::src/pkg/mod.py::dup_name') for name in listed(root, 'Doc5'))


def test_unresolved_hash_follows_the_section_text_and_tokens(root: pathlib.Path) -> None:
    write(root, 'docs/guide.md', textwrap.dedent(GUIDE) + '\nAlso `missing_fn` exists.\n')
    key = 'docs/guide.md::Guide > Usage::(unresolved)'
    before = listed(root, 'Doc5')[key].hash
    write(root, 'docs/guide.md', textwrap.dedent(GUIDE) + '\nAlso `missing_fn` is gone.\n')
    assert listed(root, 'Doc5')[key].hash != before


def test_unreadable_document_raises(root: pathlib.Path) -> None:
    (root / 'docs' / 'bad.md').write_bytes(b'\xff\xfe\x00bad')
    with pytest.raises(phaseb.PhaseBError):
        phaseb.list_candidates('Doc5', root)


def test_unreadable_spec_raises(root: pathlib.Path) -> None:
    (root / 'agents' / 'specs' / 'bad.md').write_bytes(b'\xff\xfe\x00bad')
    with pytest.raises(phaseb.PhaseBError):
        phaseb.list_candidates('Doc4', root)


@pytest.mark.parametrize('question', ['Doc4', 'Doc5'])
def test_second_call_is_identical(root: pathlib.Path, question: str) -> None:
    assert phaseb.list_candidates(question, root) == phaseb.list_candidates(question, root)


@pytest.mark.parametrize('question', ['Doc4', 'Doc5'])
def test_registered_with_brief_and_batch_size(question: str) -> None:
    assert phaseb.question_batch_size(question) == 24
    assert phaseb.question_brief(question) == candidates.A4_BRIEF.parent / f'{question}.md'
