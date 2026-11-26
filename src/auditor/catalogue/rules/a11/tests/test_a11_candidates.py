"""Tests for the A11 lister: its candidates, payloads and hashes."""

import collections.abc
import pathlib
import typing

import hypothesis
import hypothesis.strategies

import auditor.api
import auditor.core
import auditor.phaseb
import auditor.phaseb.candidates
import auditor.testing

if typing.TYPE_CHECKING:
    import ast

    import pytest

LISTER = auditor.testing.load_lister(__file__)

Project = collections.abc.Callable[[dict[str, str]], pathlib.Path]

A11_TYPES = """
import enum
import typing

Level = typing.Literal['low', 'high']


class Mode(enum.Enum):
    FAST = 'fast'
    SLOW = 'slow'
"""


A11_CHAIN = """
import pkg.types


def run(mode: pkg.types.Mode) -> int:
    if mode == pkg.types.Mode.FAST:
        return 1
    elif mode == pkg.types.Mode.SLOW:
        return 2
    return 0
"""


A11_STRING_CHAIN = """
def run(mode):
    if mode == 'a':
        return 1
    elif mode == 'b':
        return 2
    elif mode == 'c':
        return 3
    return 0
"""


A11_TWO_ARM = """
def run(mode):
    if mode == 'a':
        return 1
    else:
        return 2
"""


def run_a11(root: pathlib.Path) -> dict[str, auditor.api.Candidate]:
    return {candidate.id: candidate for candidate in auditor.phaseb.list_candidates('A11', root)}


def write_a11_project(project: Project, body: str) -> pathlib.Path:
    return project({'src/pkg/__init__.py': '', 'src/pkg/types.py': A11_TYPES, 'src/pkg/mod.py': body})


def test_a11_lists_an_enum_chain_with_annotation_and_type_source(project: Project) -> None:
    found = run_a11(write_a11_project(project, A11_CHAIN))
    assert list(found) == ['src/pkg/mod.py::run::if:mode#1']
    payload = found['src/pkg/mod.py::run::if:mode#1'].payload
    assert payload['subject'] == 'mode'
    assert payload['annotation'] == 'pkg.types.Mode'
    assert payload['type_source'] == 'src/pkg/types.py:7 Mode'
    assert payload['source'].startswith('if mode ==')


def test_a11_names_a_literal_alias_as_type_source(project: Project) -> None:
    body = """
    import pkg.types


    def run(level: pkg.types.Level) -> int:
        if level == 'low':
            return 1
        else:
            return 2
    """
    payload = run_a11(write_a11_project(project, body))['src/pkg/mod.py::run::if:level#1'].payload
    assert payload['annotation'] == 'pkg.types.Level'
    assert payload['type_source'] == 'src/pkg/types.py:4 Level'


def test_a11_unannotated_subject_has_null_annotation(project: Project) -> None:
    payload = run_a11(write_a11_project(project, A11_TWO_ARM))['src/pkg/mod.py::run::if:mode#1'].payload
    assert payload['annotation'] is None
    assert payload['type_source'] is None


def test_a11_lists_is_in_and_tuple_chains(project: Project) -> None:
    body = """
    def run(mode):
        if mode is Mode.FAST:
            return 1
        elif mode in (Mode.SLOW, 'x'):
            return 2
        return 0
    """
    assert list(run_a11(write_a11_project(project, body))) == ['src/pkg/mod.py::run::if:mode#1']


def test_a11_ignores_a_single_if_without_else(project: Project) -> None:
    body = """
    def run(mode):
        if mode == 'a':
            return 1
        return 0
    """
    assert run_a11(write_a11_project(project, body)) == {}


def test_a11_lists_the_chain_once_not_each_elif(project: Project) -> None:
    body = """
    def run(mode):
        if mode == 'a':
            return 1
        elif mode == 'b':
            return 2
        else:
            return 4
    """
    assert len(run_a11(write_a11_project(project, body))) == 1


def test_a11_ignores_a_chain_over_two_subjects(project: Project) -> None:
    body = """
    def run(mode, other):
        if mode == 'a':
            return 1
        elif other == 'b':
            return 2
        else:
            return 3
    """
    assert run_a11(write_a11_project(project, body)) == {}


def test_a11_lists_a_two_way_split_on_a_comparison_flag(project: Project) -> None:
    body = """
    def run(mode):
        flag = mode == 'a'
        if flag:
            return 1
        else:
            return 2
    """
    assert list(run_a11(write_a11_project(project, body))) == ['src/pkg/mod.py::run::if:mode#1']


def test_a11_ignores_a_flag_not_assigned_from_a_comparison(project: Project) -> None:
    body = """
    def run(flag):
        if flag:
            return 1
        else:
            return 2
    """
    assert run_a11(write_a11_project(project, body)) == {}


def test_a11_lists_a_match_statement(project: Project) -> None:
    body = """
    def run(mode):
        match mode:
            case 'a':
                return 1
            case _:
                raise ValueError(mode)
    """
    assert list(run_a11(write_a11_project(project, body))) == ['src/pkg/mod.py::run::match:mode#1']


def test_a11_numbers_two_chains_on_one_subject_in_order(project: Project) -> None:
    body = """
    def run(mode):
        if mode == 'a':
            return 1
        else:
            return 2
        if mode == 'b':
            return 3
        else:
            return 4
    """
    assert list(run_a11(write_a11_project(project, body))) == ['src/pkg/mod.py::run::if:mode#1', 'src/pkg/mod.py::run::if:mode#2']


def test_a11_drops_a_chain_the_assert_never_rule_flags(project: Project) -> None:
    assert run_a11(write_a11_project(project, A11_STRING_CHAIN)) == {}


def test_a11_drops_a_dotted_in_chain_the_assert_never_rule_flags(project: Project) -> None:
    body = """
class Probe:
    def run(self):
        if self.mode in ('a', 'b'):
            return 1
        elif self.mode == 'c':
            return 2
        elif self.mode == 'd':
            return 3
        return 0
"""
    assert run_a11(write_a11_project(project, body)) == {}


def test_a11_drops_a_chain_whose_hit_is_accepted(project: Project) -> None:
    accepted = A11_STRING_CHAIN.replace("if mode == 'a':", "if mode == 'a':  # auditme: accept[assert-never-missing] probe", 1)
    assert run_a11(write_a11_project(project, accepted)) == {}


def test_a11_id_survives_an_edit_above_and_hash_tracks_the_chain(project: Project) -> None:
    key = 'src/pkg/mod.py::run::if:mode#1'
    first = run_a11(write_a11_project(project, A11_TWO_ARM))[key]
    above = run_a11(write_a11_project(project, 'X = 1\n\n\n' + A11_TWO_ARM.lstrip('\n')))[key]
    assert above.hash == first.hash
    inside = run_a11(write_a11_project(project, A11_TWO_ARM.replace('return 2', 'return 3')))[key]
    assert inside.hash != first.hash
    outside = run_a11(write_a11_project(project, A11_TWO_ARM.replace('def run(mode):', 'def run(mode):\n    x = 1')))[key]
    assert outside.hash == first.hash


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    aliases=hypothesis.strategies.dictionaries(
        hypothesis.strategies.sampled_from(['Alpha', 'Beta', 'Gamma']), hypothesis.strategies.sampled_from(['src.one', 'src.two']), max_size=3
    ),
    names=hypothesis.strategies.lists(hypothesis.strategies.sampled_from(['Alpha', 'Beta', 'Delta', 'int']), min_size=1, max_size=3),
)
def test_type_source_of_is_none_or_an_alias_value(aliases: dict[str, str], names: list[str]) -> None:
    annotation = ' | '.join(names)
    result = LISTER.type_source_of(annotation, aliases)
    assert LISTER.type_source_of(None, aliases) is None
    if not any(name in aliases for name in names):
        assert result is None
    else:
        assert result in aliases.values()


def test_a11_computes_flag_subjects_once_per_function(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    body = """
    def run(mode):
        if mode == 'a':
            return 1
        else:
            return 2
        if mode == 'b':
            return 3
        else:
            return 4
    """
    calls: list[ast.AST] = []
    lister = auditor.testing.load_lister(__file__)
    original = lister.flag_subjects

    def counting(function: ast.AST) -> dict[str, str]:
        calls.append(function)
        return original(function)

    monkeypatch.setattr(lister, 'flag_subjects', counting)
    run_a11(write_a11_project(project, body))
    assert len(calls) == 1
