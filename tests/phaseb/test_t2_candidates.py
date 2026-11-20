"""Tests for the T2 candidate rule."""

import ast
import textwrap

from auditme.phaseb import candidates

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
