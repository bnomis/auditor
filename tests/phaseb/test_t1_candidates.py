"""Tests for the T1 lister: reasons, candidates, tests and the content hash."""

import ast
import collections.abc
import hashlib
import pathlib
import textwrap

from auditme import phaseb
from auditme.phaseb import candidates

Project = collections.abc.Callable[[dict[str, str]], pathlib.Path]


def _reasons(source: str, name: str = 'target') -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    for parent in ast.walk(tree):
        cls = parent if isinstance(parent, ast.ClassDef) else None
        body = parent.body if isinstance(parent, (ast.Module, ast.ClassDef)) else []
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                return candidates.t1_reasons(node, cls)
    raise AssertionError(name)


def test_if_gives_if() -> None:
    assert _reasons('def target(x):\n    if x:\n        return 1\n') == ['if']


def test_elif_gives_if() -> None:
    source = 'def target(x):\n    if x:\n        pass\n    elif x > 1:\n        pass\n'
    assert _reasons(source) == ['if']


def test_try_with_except_gives_try() -> None:
    assert _reasons('def target():\n    try:\n        pass\n    except ValueError:\n        pass\n') == ['try']


def test_try_star_with_handler_gives_try() -> None:
    assert _reasons('def target():\n    try:\n        pass\n    except* ValueError:\n        pass\n') == ['try']


def test_try_finally_alone_gives_nothing() -> None:
    assert _reasons('def target():\n    try:\n        pass\n    finally:\n        pass\n') == []


def test_match_gives_match() -> None:
    assert _reasons('def target(x):\n    match x:\n        case 1:\n            pass\n') == ['match']


STATE = """
    class Probe:
        def target(self):
            self.state = 1

        def other(self):
            if self.state == 2:
                pass
"""


def test_assignment_to_tested_attribute_gives_state() -> None:
    assert _reasons(STATE) == ['state']


def test_state_by_match_subject_and_comparison() -> None:
    match = 'class Probe:\n    def target(self):\n        self.mode = 1\n\n    def other(self):\n        match self.mode:\n            case 1:\n                pass\n'
    compare = 'class Probe:\n    def target(self):\n        self.mode = 1\n\n    def other(self):\n        return self.mode == 1\n'
    assert _reasons(match) == ['state']
    assert _reasons(compare) == ['state']


def test_attribute_no_other_method_tests_gives_nothing() -> None:
    source = 'class Probe:\n    def target(self):\n        self.count = 1\n\n    def other(self):\n        return self.count\n'
    assert _reasons(source) == []


def test_own_test_of_attribute_is_not_evidence() -> None:
    source = 'class Probe:\n    def target(self):\n        self.mode = 1\n        return self.mode == 1\n'
    assert _reasons(source) == []


def test_non_branching_constructs_give_nothing() -> None:
    source = 'def target(xs, x):\n    y = 1 if x else 2\n    zs = [z for z in xs if z]\n    assert x\n    return y, zs\n'
    assert _reasons(source) == []


def test_if_in_nested_def_gives_nothing() -> None:
    source = 'def target():\n    def inner(x):\n        if x:\n            pass\n    return inner\n'
    assert _reasons(source) == []


def test_reasons_in_fixed_order_without_repeats() -> None:
    source = """
        class Probe:
            def target(self, x):
                self.state = 1
                match x:
                    case 1:
                        pass
                try:
                    pass
                except ValueError:
                    pass
                if x:
                    pass
                if x > 1:
                    pass

            def other(self):
                if self.state:
                    pass
    """
    assert _reasons(source) == ['if', 'try', 'match', 'state']


MOD = """
    import typing

    if typing.TYPE_CHECKING:
        def hidden(x):
            if x:
                pass


    def load(x):
        if x:
            return 1
        return 0


    def run(x):
        return load(x)


    def plain():
        return 1


    @typing.overload
    def over(x):
        if x:
            pass


    def _inner(x):
        if x:
            return 1
        return 0
"""

BASE = {
    'src/pkg/__init__.py': '',
    'src/pkg/mod.py': MOD,
    'src/tests/__init__.py': '',
    'src/tests/pkg/test_mod.py': """
        from pkg.mod import run


        def test_run():
            assert run(1) == 1
    """,
    'src/tests/test_other.py': """
        def test_other():
            assert 1
    """,
}


def _t1(root: pathlib.Path, depth: int | None = None) -> dict[str, phaseb.Candidate]:
    found = candidates.list_t1_candidates(root) if depth is None else candidates.list_t1_candidates(root, depth=depth)
    return {candidate.id: candidate for candidate in found}


def test_branchy_function_is_a_candidate_with_its_payload(project: Project) -> None:
    root = project(BASE)
    found = _t1(root)
    candidate = found['src/pkg/mod.py::load']
    assert candidate.question == 'T1'
    assert candidate.path == 'src/pkg/mod.py'
    assert candidate.payload['reasons'] == ['if']
    assert candidate.payload['tests'] == [
        {
            'id': 'src/tests/pkg/test_mod.py::test_run',
            'path': 'src/tests/pkg/test_mod.py',
            'start': 4,
            'end': 5,
            'route': 'caller',
            'via': 'src/pkg/mod.py::run',
            'property': False,
        }
    ]
    assert [caller['id'] for caller in candidate.payload['callers']] == ['src/pkg/mod.py::run']
    assert candidate.payload['test_files'] == ['src/tests/pkg/test_mod.py']
    assert 'src/pkg/mod.py::plain' not in found
    assert 'src/pkg/mod.py::run' not in found


def test_overload_stub_and_type_checking_def_are_not_candidates(project: Project) -> None:
    found = _t1(project(BASE))
    assert 'src/pkg/mod.py::over' not in found
    assert 'src/pkg/mod.py::hidden' not in found


def test_test_files_are_never_candidates(project: Project) -> None:
    root = project(
        {
            **BASE,
            'src/pkg/test_thing.py': 'def f(x):\n    if x:\n        pass\n',
            'src/pkg/thing_test.py': 'def f(x):\n    if x:\n        pass\n',
            'src/pkg/conftest.py': 'def f(x):\n    if x:\n        pass\n',
            'src/pkg/tests/helper.py': 'def f(x):\n    if x:\n        pass\n',
        }
    )
    assert {candidate.path for candidate in _t1(root).values()} == {'src/pkg/mod.py'}


def test_private_is_the_answer_of_is_private(project: Project) -> None:
    found = _t1(project(BASE))
    assert found['src/pkg/mod.py::_inner'].payload['private'] is True
    assert found['src/pkg/mod.py::load'].payload['private'] is False


def test_no_test_tree_lists_candidates_with_no_tests(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD})
    candidate = _t1(root)['src/pkg/mod.py::load']
    assert candidate.payload['tests'] == []
    assert candidate.payload['test_files'] == []


def test_hash_is_sha256_of_source_then_test_files_nul_separated(project: Project) -> None:
    root = project(BASE)
    lines = (root / 'src/pkg/mod.py').read_text(encoding='utf-8').splitlines()
    source = '\n'.join(lines[8:12])
    test_text = (root / 'src/tests/pkg/test_mod.py').read_text(encoding='utf-8')
    expected = hashlib.sha256('\0'.join([source, test_text]).encode('utf-8')).hexdigest()
    assert _t1(root)['src/pkg/mod.py::load'].hash == expected


def test_editing_a_relevant_test_file_changes_the_hash_but_an_unrelated_one_does_not(project: Project) -> None:
    root = project(BASE)
    before = _t1(root)['src/pkg/mod.py::load'].hash
    (root / 'src/tests/test_other.py').write_text('def test_other():\n    assert 2\n', encoding='utf-8')
    assert _t1(root)['src/pkg/mod.py::load'].hash == before
    mirrored = root / 'src/tests/pkg/test_mod.py'
    mirrored.write_text(mirrored.read_text(encoding='utf-8') + '\n\ndef test_more():\n    assert run(0) == 0\n', encoding='utf-8')
    assert _t1(root)['src/pkg/mod.py::load'].hash != before


def test_second_call_gives_the_same_candidates_and_hashes(project: Project) -> None:
    root = project(BASE)
    first = phaseb.list_candidates('T1', root)
    assert first == phaseb.list_candidates('T1', root)
    assert [candidate.id for candidate in first] == sorted(candidate.id for candidate in first)


def test_depth_reaches_the_lister(project: Project) -> None:
    root = project(BASE)
    assert _t1(root, depth=1)['src/pkg/mod.py::load'].payload['callers']
    assert not _t1(root, depth=0)['src/pkg/mod.py::load'].payload['callers']


def test_t1_is_registered_with_its_brief_path() -> None:
    assert phaseb.question_brief('T1').as_posix().endswith('claude/skills/auditme/phaseb/briefs/T1.md')
