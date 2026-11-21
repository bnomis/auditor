"""Tests for the T2 candidate rule."""

import ast
import collections.abc
import hashlib
import pathlib
import textwrap

from auditme import phaseb
from auditme.phaseb import candidates

Project = collections.abc.Callable[[dict[str, str]], pathlib.Path]

PACKAGE = """
import dataclasses
import decimal
import enum
import pathlib
import typing


@dataclasses.dataclass(frozen=True)
class Probe:
    x: int
    y: str


@dataclasses.dataclass
class Loose:
    x: int


@dataclasses.dataclass(frozen=True)
class WithPath:
    where: pathlib.Path


@dataclasses.dataclass(frozen=True)
class Node:
    value: int
    child: 'Node | None'


class Colour(enum.Enum):
    RED = 1


class Pair(typing.NamedTuple):
    a: int
    b: float


class Row(typing.TypedDict):
    key: str
    probe: Probe
"""


def _types() -> dict[str, ast.ClassDef]:
    return {node.name: node for node in ast.parse(PACKAGE).body if isinstance(node, ast.ClassDef)}


def _is_candidate(source: str, name: str = 'target') -> bool:
    tree = ast.parse(textwrap.dedent(source))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return candidates.is_t2_candidate(node, _types())
    raise AssertionError(name)


def test_int_function_with_branch_is_a_candidate() -> None:
    assert _is_candidate('def target(x: int) -> int:\n    if x:\n        return 1\n    return 2\n')


def test_frozen_package_dataclass_is_a_candidate() -> None:
    assert _is_candidate('def target(p: Probe) -> int:\n    if p.x:\n        return 1\n    return 2\n')


def test_str_and_bytes_are_a_candidate() -> None:
    assert _is_candidate('def target(s: str) -> bytes:\n    if s:\n        return b"a"\n    return b""\n')


def test_optional_list_is_a_candidate() -> None:
    assert _is_candidate('def target(xs: list[int] | None) -> int:\n    return sum(x for x in xs or [])\n')


def test_literal_is_a_candidate() -> None:
    assert _is_candidate('def target(m: typing.Literal["a", "b"]) -> int:\n    if m == "a":\n        return 1\n    return 2\n')


def test_package_enum_namedtuple_and_typeddict_are_candidates() -> None:
    for annotation in ('Colour', 'Pair', 'Row'):
        assert _is_candidate(f'def target(v: {annotation}) -> int:\n    if v:\n        return 1\n    return 2\n')


def test_staticmethod_is_a_candidate() -> None:
    source = 'class K:\n    @staticmethod\n    def target(x: int) -> int:\n        if x:\n            return 1\n        return 2\n'
    assert _is_candidate(source)


def test_recursive_package_type_terminates() -> None:
    assert _is_candidate('def target(n: Node) -> int:\n    if n:\n        return 1\n    return 2\n')


def test_path_parameter_is_not_a_candidate() -> None:
    assert not _is_candidate('def target(p: pathlib.Path) -> int:\n    if p:\n        return 1\n    return 2\n')


def test_non_frozen_dataclass_is_not_a_candidate() -> None:
    assert not _is_candidate('def target(p: Loose) -> int:\n    if p:\n        return 1\n    return 2\n')


def test_frozen_dataclass_with_path_field_is_not_a_candidate() -> None:
    assert not _is_candidate('def target(p: WithPath) -> int:\n    if p:\n        return 1\n    return 2\n')


def test_unannotated_parameter_is_not_a_candidate() -> None:
    assert not _is_candidate('def target(x) -> int:\n    if x:\n        return 1\n    return 2\n')


def test_unknown_class_is_not_a_candidate() -> None:
    assert not _is_candidate('def target(x: Mystery) -> int:\n    if x:\n        return 1\n    return 2\n')


def test_none_return_is_not_a_candidate() -> None:
    assert not _is_candidate('def target(x: int) -> None:\n    if x:\n        return\n')


def test_missing_return_annotation_is_not_a_candidate() -> None:
    assert not _is_candidate('def target(x: int):\n    if x:\n        return 1\n    return 2\n')


def test_no_parameters_is_not_a_candidate() -> None:
    assert not _is_candidate('def target() -> int:\n    if True:\n        return 1\n    return 2\n')


def test_async_is_not_a_candidate() -> None:
    tree = ast.parse('async def target(x: int) -> int:\n    if x:\n        return 1\n    return 2\n')
    node = tree.body[0]
    assert isinstance(node, ast.AsyncFunctionDef)
    assert not candidates.is_t2_candidate(node, _types())  # type: ignore[arg-type]


def test_generator_is_not_a_candidate() -> None:
    assert not _is_candidate('def target(x: int) -> int:\n    if x:\n        yield 1\n')


def test_plain_method_is_not_a_candidate() -> None:
    source = 'class K:\n    def target(self, x: int) -> int:\n        if x:\n            return 1\n        return 2\n'
    assert not _is_candidate(source)


def test_classmethod_is_not_a_candidate() -> None:
    source = 'class K:\n    @classmethod\n    def target(cls, x: int) -> int:\n        if x:\n            return 1\n        return 2\n'
    assert not _is_candidate(source)


def test_side_effect_calls_are_not_candidates() -> None:
    for call in ('write_text(x)', 'open(x)', 'print(x)', 'now()', 'random.random()', 'subprocess.run(x)', 'p.unlink()'):
        source = f'def target(x: int) -> int:\n    {call}\n    if x:\n        return 1\n    return 2\n'
        assert not _is_candidate(source), call


def test_global_and_nonlocal_are_not_candidates() -> None:
    assert not _is_candidate('def target(x: int) -> int:\n    global G\n    if x:\n        return 1\n    return 2\n')
    source = 'def outer():\n    n = 0\n    def target(x: int) -> int:\n        nonlocal n\n        if x:\n            return 1\n        return 2\n'
    assert not _is_candidate(source)


def test_assignment_to_parameter_attribute_or_subscript_is_not_a_candidate() -> None:
    assert not _is_candidate('def target(p: Probe) -> int:\n    p.x = 1\n    if p:\n        return 1\n    return 2\n')
    assert not _is_candidate('def target(d: dict[str, int]) -> int:\n    d["a"] = 1\n    if d:\n        return 1\n    return 2\n')


def test_assignment_to_a_local_is_allowed() -> None:
    assert _is_candidate('def target(x: int) -> int:\n    total = 0\n    for i in range(x):\n        total += i\n    return total\n')


def test_no_branch_loop_or_comprehension_is_not_a_candidate() -> None:
    assert not _is_candidate('def target(x: int) -> int:\n    return x + 1\n')


def test_branch_in_nested_def_does_not_count() -> None:
    source = 'def target(x: int) -> int:\n    def inner(y):\n        if y:\n            return 1\n        return 2\n    return x\n'
    assert not _is_candidate(source)


def test_comprehension_counts() -> None:
    assert _is_candidate('def target(xs: list[int]) -> list[int]:\n    return [x for x in xs]\n')


MOD = """
    import dataclasses


    @dataclasses.dataclass(frozen=True)
    class Probe:
        x: int


    @dataclasses.dataclass(frozen=True)
    class Wrapper:
        probe: Probe


    def parse_probe(s: str) -> Probe:
        if s:
            return Probe(int(s))
        return Probe(0)


    def format_probe(p: Probe) -> str:
        if p.x:
            return str(p.x)
        return ''


    def encode(s: str) -> bytes:
        return bytes(c for c in s.encode() if c)


    def decode(b: bytes) -> str:
        return ''.join(chr(c) for c in b)


    def to_x(n: int) -> str:
        return ''.join(str(d) for d in range(n))


    def from_x(s: str) -> int:
        return len([c for c in s])


    def dumps(n: int) -> str:
        if n:
            return str(n)
        return ''


    def loads(s: str) -> int:
        if s:
            return int(s)
        return 0


    def unwrap(w: Wrapper) -> int:
        if w.probe.x:
            return 1
        return 0


    def plain(n: int) -> int:
        return n


    def untyped(n):
        if n:
            return 1
        return 0
"""

BASE = {
    'src/pkg/__init__.py': '',
    'src/pkg/mod.py': MOD,
    'src/tests/__init__.py': '',
    'src/tests/pkg/test_mod.py': """
        from hypothesis import given, strategies

        from pkg.mod import parse_probe, unwrap


        @given(strategies.text())
        def test_parse(s):
            parse_probe(s)


        def test_unwrap():
            assert unwrap(None) == 0
    """,
    'src/tests/test_other.py': """
        def test_other():
            assert 1
    """,
}


def _t2(root: pathlib.Path) -> dict[str, phaseb.Candidate]:
    return {candidate.id: candidate for candidate in candidates.list_t2_candidates(root)}


def test_candidates_are_the_functions_the_rule_accepts(project: Project) -> None:
    found = _t2(project(BASE))
    assert set(found) == {
        f'src/pkg/mod.py::{name}' for name in ('parse_probe', 'format_probe', 'encode', 'decode', 'to_x', 'from_x', 'dumps', 'loads', 'unwrap')
    }


def test_params_returns_and_types(project: Project) -> None:
    found = _t2(project(BASE))
    candidate = found['src/pkg/mod.py::parse_probe']
    assert candidate.question == 'T2'
    assert candidate.payload['params'] == [{'name': 's', 'annotation': 'str'}]
    assert candidate.payload['returns'] == 'Probe'
    assert candidate.payload['types'] == [{'id': 'src/pkg/mod.py::Probe', 'path': 'src/pkg/mod.py', 'start': 4, 'end': 6}]


def test_types_include_classes_named_through_a_field(project: Project) -> None:
    found = _t2(project(BASE))
    ids = [entry['id'] for entry in found['src/pkg/mod.py::unwrap'].payload['types']]
    assert ids == ['src/pkg/mod.py::Probe', 'src/pkg/mod.py::Wrapper']
    assert found['src/pkg/mod.py::dumps'].payload['types'] == []


def test_inverse_names_list_each_other_in_pairs(project: Project) -> None:
    found = _t2(project(BASE))
    for first, second in (('parse_probe', 'format_probe'), ('encode', 'decode'), ('to_x', 'from_x'), ('dumps', 'loads')):
        assert found[f'src/pkg/mod.py::{first}'].payload['pairs'] == [f'src/pkg/mod.py::{second}']
        assert found[f'src/pkg/mod.py::{second}'].payload['pairs'] == [f'src/pkg/mod.py::{first}']
    assert found['src/pkg/mod.py::unwrap'].payload['pairs'] == []


def test_test_files_are_never_candidates(project: Project) -> None:
    body = 'def f(x: int) -> int:\n    if x:\n        return 1\n    return 0\n'
    root = project({**BASE, 'src/pkg/test_thing.py': body, 'src/pkg/thing_test.py': body, 'src/pkg/conftest.py': body, 'src/pkg/tests/helper.py': body})
    assert {candidate.path for candidate in _t2(root).values()} == {'src/pkg/mod.py'}


def test_property_test_calling_the_candidate_is_marked(project: Project) -> None:
    found = _t2(project(BASE))
    parse = found['src/pkg/mod.py::parse_probe'].payload
    assert [(ref['id'], ref['route'], ref['property']) for ref in parse['tests']] == [('src/tests/pkg/test_mod.py::test_parse', 'direct', True)]
    unwrap = found['src/pkg/mod.py::unwrap'].payload
    assert [(ref['id'], ref['property']) for ref in unwrap['tests']] == [('src/tests/pkg/test_mod.py::test_unwrap', False)]
    assert parse['test_files'] == ['src/tests/pkg/test_mod.py']


def test_hash_is_sha256_of_source_types_then_test_files_nul_separated(project: Project) -> None:
    root = project(BASE)
    lines = (root / 'src/pkg/mod.py').read_text(encoding='utf-8').splitlines()
    parts = [
        '\n'.join(lines[13:17]),
        '\n'.join(lines[3:6]),
        (root / 'src/tests/pkg/test_mod.py').read_text(encoding='utf-8'),
    ]
    expected = hashlib.sha256('\0'.join(parts).encode('utf-8')).hexdigest()
    assert _t2(root)['src/pkg/mod.py::parse_probe'].hash == expected


def test_adding_a_field_to_a_type_changes_the_hash(project: Project) -> None:
    root = project(BASE)
    before = _t2(root)
    path = root / 'src/pkg/mod.py'
    path.write_text(path.read_text(encoding='utf-8').replace('    x: int\n', '    x: int\n    y: int = 0\n', 1), encoding='utf-8')
    after = _t2(root)
    assert after['src/pkg/mod.py::parse_probe'].hash != before['src/pkg/mod.py::parse_probe'].hash
    assert after['src/pkg/mod.py::dumps'].hash == before['src/pkg/mod.py::dumps'].hash


def test_adding_a_test_to_the_mirrored_file_changes_the_hash(project: Project) -> None:
    root = project(BASE)
    before = _t2(root)['src/pkg/mod.py::parse_probe'].hash
    mirrored = root / 'src/tests/pkg/test_mod.py'
    mirrored.write_text(mirrored.read_text(encoding='utf-8') + '\n\ndef test_more():\n    assert parse_probe("")\n', encoding='utf-8')
    assert _t2(root)['src/pkg/mod.py::parse_probe'].hash != before


def test_second_call_gives_the_same_candidates_and_hashes(project: Project) -> None:
    root = project(BASE)
    first = phaseb.list_candidates('T2', root)
    assert first == phaseb.list_candidates('T2', root)
    assert [candidate.id for candidate in first] == sorted(candidate.id for candidate in first)


def test_t2_is_registered_with_its_brief_path() -> None:
    assert phaseb.question_brief('T2').as_posix().endswith('claude/skills/auditme/phaseb/briefs/T2.md')
