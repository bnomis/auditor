"""Tests for the A4 lister: candidates, callees, unresolved calls and the content hash."""

import collections.abc
import hashlib
import pathlib

import pytest

import auditor.api
import auditor.phaseb
import auditor.testing

LISTER = auditor.testing.load_lister(__file__)

Project = collections.abc.Callable[[dict[str, str]], pathlib.Path]

MOD = '''
    class ProbeError(Exception):
        pass


    def helper():
        raise ProbeError('x')


    def middle():
        helper()


    def top():
        """Do it.

        Raises:
            ProbeError: always.
        """
        middle()


    def plain():
        """No section here."""
        return 1


    class Probe:
        @classmethod
        def load(cls):
            raise ProbeError('x')

        def run(self):
            """Run.

            Raises:
                ProbeError: when loading fails.
            """
            Probe.load()
            local = Probe()
            local.other()

        def other(self):
            return 1
'''


# auditme: accept[paired-sibling-helpers] each question's tests sit in its own rule directory and cannot import a sibling's helper
def list_a4_candidates(root: pathlib.Path, depth: int | None = None) -> dict[str, auditor.api.Candidate]:
    found = LISTER.list_candidates(root) if depth is None else LISTER.list_candidates(root, depth=depth)
    return {candidate.id: candidate for candidate in found}


def test_function_with_raises_section_is_a_candidate(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD})
    candidate = list_a4_candidates(root)['src/pkg/mod.py::top']
    assert candidate.question == 'A4'
    assert candidate.path == 'src/pkg/mod.py'
    assert (candidate.start, candidate.end) == (13, 19)
    assert 'ProbeError: always.' in candidate.payload['raises']


def test_method_id_carries_the_class(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD})
    assert 'src/pkg/mod.py::Probe.run' in list_a4_candidates(root)


def test_function_without_raises_section_is_not_a_candidate(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD})
    found = list_a4_candidates(root)
    assert 'src/pkg/mod.py::plain' not in found
    assert 'src/pkg/mod.py::helper' not in found


@pytest.mark.parametrize(
    'body',
    [
        '...',
        'pass',
        'raise NotImplementedError',
        'raise NotImplementedError("later")',
    ],
)
def test_abstract_and_protocol_stubs_are_not_candidates(project: Project, body: str) -> None:
    source = f'''
        def stub():
            """Stub.

            Raises:
                ProbeError: by an implementation.
            """
            {body}
    '''
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': source})
    assert list_a4_candidates(root) == {}


def test_docstring_alone_is_a_stub(project: Project) -> None:
    source = '''
        def stub():
            """Stub.

            Raises:
                ProbeError: by an implementation.
            """
    '''
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': source})
    assert list_a4_candidates(root) == {}


def test_callees_follow_to_the_depth(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD})
    deep = {callee['id'] for callee in list_a4_candidates(root, depth=3)['src/pkg/mod.py::top'].payload['callees']}
    shallow = {callee['id'] for callee in list_a4_candidates(root, depth=1)['src/pkg/mod.py::top'].payload['callees']}
    assert deep == {'src/pkg/mod.py::middle', 'src/pkg/mod.py::helper'}
    assert shallow == {'src/pkg/mod.py::middle'}


def test_callee_entries_carry_path_and_lines(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD})
    callee = list_a4_candidates(root, depth=1)['src/pkg/mod.py::top'].payload['callees'][0]
    assert callee == {'id': 'src/pkg/mod.py::middle', 'path': 'src/pkg/mod.py', 'start': 9, 'end': 10}


def test_class_method_call_resolves_into_callees(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD})
    ids = {callee['id'] for callee in list_a4_candidates(root)['src/pkg/mod.py::Probe.run'].payload['callees']}
    assert 'src/pkg/mod.py::Probe.load' in ids


def test_imported_class_method_call_resolves(project: Project) -> None:
    caller = '''
        from pkg.mod import Probe


        def go():
            """Go.

            Raises:
                ProbeError: from load.
            """
            Probe.load()
    '''
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD, 'src/pkg/other.py': caller})
    ids = {callee['id'] for callee in list_a4_candidates(root)['src/pkg/other.py::go'].payload['callees']}
    assert 'src/pkg/mod.py::Probe.load' in ids


def test_call_on_local_instance_is_unresolved_with_location_and_text(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD})
    unresolved = list_a4_candidates(root)['src/pkg/mod.py::Probe.run'].payload['unresolved']
    assert {'at': 'src/pkg/mod.py:40', 'text': 'local.other()'} in unresolved


def test_editing_a_callee_changes_the_callers_hash_but_an_unrelated_edit_does_not(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD})
    before = list_a4_candidates(root)['src/pkg/mod.py::top'].hash
    mod = root / 'src/pkg/mod.py'
    text = mod.read_text(encoding='utf-8')
    mod.write_text(text.replace("raise ProbeError('x')\n\n\ndef middle", "raise ProbeError('changed')\n\n\ndef middle"), encoding='utf-8')
    assert list_a4_candidates(root)['src/pkg/mod.py::top'].hash != before
    mod.write_text(text.replace('return 1\n', 'return 2\n'), encoding='utf-8')
    assert list_a4_candidates(root)['src/pkg/mod.py::top'].hash == before


def test_hash_is_sha256_of_source_then_callee_sources_nul_separated(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD})
    lines = (root / 'src/pkg/mod.py').read_text(encoding='utf-8').splitlines()

    def source(start: int, end: int) -> str:
        return '\n'.join(lines[start - 1 : end])

    candidate = list_a4_candidates(root)['src/pkg/mod.py::top']
    parts = [source(13, 19), source(5, 6), source(9, 10)]  # top, then helper and middle in id order
    assert candidate.hash == hashlib.sha256('\0'.join(parts).encode('utf-8')).hexdigest()


def test_second_call_gives_the_same_candidates_and_hashes(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD})
    first = auditor.phaseb.list_candidates('A4', root)
    second = auditor.phaseb.list_candidates('A4', root)
    assert first == second
    assert [candidate.id for candidate in first] == sorted(candidate.id for candidate in first)


def test_a4_is_registered_with_its_brief_path() -> None:
    assert auditor.phaseb.question_brief('A4').as_posix().endswith('rules/a4/brief.md')
