"""Tests for the Doc4 and Doc5 listers: documents, pairs, unresolved names and hashes."""

import textwrap
import typing

import auditme.core
import auditme.phaseb
import auditme.phaseb.candidates
import conftest
import pytest

if typing.TYPE_CHECKING:
    import pathlib

AGENTS_QUESTIONS = ['Doc1', 'Doc2']
DRIFT_QUESTIONS = ['Doc4', 'Doc5']
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
    'AGENTS.md': '# Agents\n',
    'README.md': '# Probe\n\n## Start\n\nRun `run_it` first.\n',
    'agents/specs/draft/spec.md': DRAFT,
    'agents/specs/probe/spec.md': SPEC,
    'docs/guide.md': GUIDE,
    'src/pkg/__init__.py': '',
    'src/pkg/mod.py': MOD,
    'src/pkg/other.py': OTHER,
}


def write(root: pathlib.Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding='utf-8')


@pytest.fixture
def root(tmp_path: pathlib.Path) -> pathlib.Path:
    for name, text in FILES.items():
        write(tmp_path, name, text)
    conftest.git(tmp_path, 'init', '-q')
    conftest.git(tmp_path, 'add', '-A')
    return tmp_path


def listed(root: pathlib.Path, question: str) -> dict[str, auditme.phaseb.candidates.Candidate]:
    auditme.core.clear_source_cache()
    return {candidate.id: candidate for candidate in auditme.phaseb.list_candidates(question, root)}


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
    conftest.git(root, 'add', '-A')
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
    with pytest.raises(auditme.phaseb.PhaseBError):
        auditme.phaseb.list_candidates('Doc5', root)


def test_unreadable_spec_raises(root: pathlib.Path) -> None:
    (root / 'agents' / 'specs' / 'bad.md').write_bytes(b'\xff\xfe\x00bad')
    with pytest.raises(auditme.phaseb.PhaseBError):
        auditme.phaseb.list_candidates('Doc4', root)


@pytest.mark.parametrize('question', DRIFT_QUESTIONS)
def test_second_call_is_identical(root: pathlib.Path, question: str) -> None:
    assert auditme.phaseb.list_candidates(question, root) == auditme.phaseb.list_candidates(question, root)


@pytest.mark.parametrize('question', DRIFT_QUESTIONS)
def test_registered_with_brief_and_batch_size(question: str) -> None:
    assert auditme.phaseb.question_batch_size(question) == 24
    assert auditme.phaseb.question_brief(question) == auditme.phaseb.candidates.A4_BRIEF.parent / f'{question}.md'


# Doc1 and Doc2

AGENTS = """
    # Agents

    ## Layout

    ```text
    src/pkg/
    docs/
    ```

    The code is in `src/pkg/mod.py` and the old `src/gone/` tree.

    ## Tools

    Use `ruff` and `Requests` for checks; `mypy`, `pytest`, `hatchling`, `lintme`, `black` and `uv sync`.
    The `numpy` module is imported and `nothing_here` is not.

    ## Prose

    Plain words only.
"""

PYPROJECT = """
    [project]
    name = "pkg"
    dependencies = ["requests>=2"]

    [project.optional-dependencies]
    extra = ["mypy"]

    [dependency-groups]
    dev = ["pytest", {include-group = "other"}]

    [build-system]
    requires = ["hatchling"]
"""

HOOKS = """
    repos:
      - repo: local
        hooks:
          - id: lintme
"""


@pytest.fixture
def agents_root(root: pathlib.Path) -> pathlib.Path:
    write(root, 'AGENTS.md', AGENTS)
    write(root, 'pyproject.toml', PYPROJECT)
    write(root, '.pre-commit-config.yaml', HOOKS)
    write(root, 'src/pkg/uses.py', 'import numpy\nfrom os import path\n')
    conftest.git(root, 'add', '-A')
    return root


def test_doc1_id_and_payload(agents_root: pathlib.Path) -> None:
    candidate = listed(agents_root, 'Doc1')['AGENTS.md::Agents > Layout']
    assert candidate.question == 'Doc1'
    paths = {entry['path']: entry['resolved'] for entry in candidate.payload['paths']}
    assert paths['src/pkg/mod.py'] == ['src/pkg/mod.py']
    assert paths['src/gone/'] == []
    assert 'src/pkg' in candidate.payload['tree']
    assert all(name.count('/') < 3 for name in candidate.payload['tree'])


def test_doc1_skips_section_without_path_or_fence(agents_root: pathlib.Path) -> None:
    ids = listed(agents_root, 'Doc1')
    assert 'AGENTS.md::Agents > Prose' not in ids
    assert 'AGENTS.md::Agents > Tools' not in ids


def test_doc1_hash_follows_tracked_directories_only(agents_root: pathlib.Path) -> None:
    key = 'AGENTS.md::Agents > Layout'
    before = listed(agents_root, 'Doc1')[key].hash
    write(agents_root, 'untracked/file.py', 'x = 1\n')
    assert listed(agents_root, 'Doc1')[key].hash == before
    conftest.git(agents_root, 'add', '-A')
    assert listed(agents_root, 'Doc1')[key].hash != before


def test_doc2_matches_each_inventory(agents_root: pathlib.Path) -> None:
    candidate = listed(agents_root, 'Doc2')['AGENTS.md::Agents > Tools']
    matched = {entry['token']: entry['source'] for entry in candidate.payload['matched']}
    assert matched['Requests'] == 'project.dependencies'
    assert matched['mypy'] == 'project.optional-dependencies'
    assert matched['pytest'] == 'dependency-groups'
    assert matched['hatchling'] == 'build-system.requires'
    assert matched['lintme'] == 'pre-commit hook'
    assert matched['numpy'] == 'import'
    assert 'ruff' in candidate.payload['unmatched']
    assert 'nothing_here' in candidate.payload['unmatched']


def test_doc2_skips_section_without_a_token(agents_root: pathlib.Path) -> None:
    assert 'AGENTS.md::Agents > Prose' not in listed(agents_root, 'Doc2')


def test_doc2_hash_follows_hook_file_and_tables(agents_root: pathlib.Path) -> None:
    key = 'AGENTS.md::Agents > Tools'
    before = listed(agents_root, 'Doc2')[key].hash
    write(agents_root, '.pre-commit-config.yaml', HOOKS + '      - id: other\n')
    assert listed(agents_root, 'Doc2')[key].hash != before


def test_missing_pyproject_and_hook_file_are_not_errors(root: pathlib.Path) -> None:
    write(root, 'AGENTS.md', AGENTS)
    candidate = listed(root, 'Doc2')['AGENTS.md::Agents > Tools']
    assert [entry['token'] for entry in candidate.payload['matched']] == []


def test_missing_agents_md_lists_nothing(root: pathlib.Path) -> None:
    (root / 'AGENTS.md').unlink()
    assert auditme.phaseb.list_candidates('Doc1', root) == []
    assert auditme.phaseb.list_candidates('Doc2', root) == []


def test_unparseable_pyproject_raises(agents_root: pathlib.Path) -> None:
    write(agents_root, 'pyproject.toml', 'not [valid')
    with pytest.raises(auditme.phaseb.PhaseBError):
        auditme.phaseb.list_candidates('Doc2', agents_root)


def test_unreadable_hook_file_raises(agents_root: pathlib.Path) -> None:
    (agents_root / '.pre-commit-config.yaml').unlink()
    (agents_root / '.pre-commit-config.yaml').mkdir()
    with pytest.raises(auditme.phaseb.PhaseBError):
        auditme.phaseb.list_candidates('Doc2', agents_root)


@pytest.mark.parametrize('question', AGENTS_QUESTIONS)
def test_failing_git_ls_files_raises(tmp_path: pathlib.Path, question: str) -> None:
    write(tmp_path, 'AGENTS.md', AGENTS)
    with pytest.raises(auditme.phaseb.PhaseBError):
        auditme.phaseb.list_candidates(question, tmp_path)


@pytest.mark.parametrize('question', AGENTS_QUESTIONS)
def test_agents_listers_are_registered_and_stable(agents_root: pathlib.Path, question: str) -> None:
    assert auditme.phaseb.question_batch_size(question) == 12
    assert auditme.phaseb.question_brief(question) == auditme.phaseb.candidates.A4_BRIEF.parent / f'{question}.md'
    assert auditme.phaseb.list_candidates(question, agents_root) == auditme.phaseb.list_candidates(question, agents_root)
