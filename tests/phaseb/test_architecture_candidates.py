"""Tests for the architecture listers and their shared helpers."""

import ast
import collections.abc
import pathlib

import auditme.core
import auditme.rules.error_handling
import pytest
from auditme import phaseb
from auditme.phaseb import architecture

Project = collections.abc.Callable[[dict[str, str]], pathlib.Path]

SILENT = """
def load():
    try:
        return 1
    except Exception:
        pass
"""

ACCEPTED = """
def load():
    try:
        return 1
    except Exception:  # auditme: accept[silent-broad-except] probe
        pass
"""


def _boom(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    raise RuntimeError('boom')


# capture_hits


def test_capture_hits_returns_rule_path_line_triples(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    hits = architecture.capture_hits(root, [auditme.rules.error_handling.check_silent_broad_except])
    assert hits == {('silent-broad-except', 'src/pkg/mod.py', 4)}


def test_capture_hits_includes_accepted_hits(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': ACCEPTED})
    hits = architecture.capture_hits(root, [auditme.rules.error_handling.check_silent_broad_except])
    assert hits == {('silent-broad-except', 'src/pkg/mod.py', 4)}


def test_capture_hits_restores_emitted_and_prints_nothing(project: Project, capsys: pytest.CaptureFixture[str]) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    auditme.core._EMITTED.clear()
    auditme.core._EMITTED.add('earlier')
    architecture.capture_hits(root, [auditme.rules.error_handling.check_silent_broad_except])
    assert {'earlier'} == auditme.core._EMITTED
    assert capsys.readouterr().out == ''
    auditme.core._EMITTED.clear()


def test_capture_hits_names_a_check_that_raises(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    with pytest.raises(phaseb.PhaseBError, match='_boom'):
        architecture.capture_hits(root, [_boom])


# shared


def test_unparseable_file_raises_naming_it(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/bad.py': 'def (:\n'})
    with pytest.raises(phaseb.PhaseBError, match='bad.py'):
        architecture.parse_audited_files(root)


def test_parse_audited_files_returns_each_file(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    assert {file.rel for file in architecture.parse_audited_files(root)} == {'src/pkg/__init__.py', 'src/pkg/mod.py'}


def test_site_counter_numbers_sites_per_qualname() -> None:
    counter = architecture.SiteCounter()
    assert counter.next('pkg.mod.f') == 1
    assert counter.next('pkg.mod.f') == 2
    assert counter.next('pkg.mod.g') == 1
    assert counter.next('pkg.mod.f') == 3


def test_walk_with_qualname_names_functions_methods_and_module_level() -> None:
    tree = ast.parse('x = 1\n\n\ndef f():\n    y = 2\n\n\nclass C:\n    def m(self):\n        z = 3\n')
    found = {qualname for qualname, node in architecture.walk_with_qualname(tree) if isinstance(node, ast.Assign)}
    assert found == {'<module>', 'f', 'C.m'}


def test_hit_on_anchor_matches_rule_path_and_line() -> None:
    hits = {('silent-broad-except', 'src/pkg/mod.py', 4)}
    assert architecture.hit_on_anchor(hits, 'src/pkg/mod.py', [3, 4], ('silent-broad-except',))
    assert not architecture.hit_on_anchor(hits, 'src/pkg/mod.py', [3], ('silent-broad-except',))
    assert not architecture.hit_on_anchor(hits, 'src/pkg/other.py', [4], ('silent-broad-except',))
    assert not architecture.hit_on_anchor(hits, 'src/pkg/mod.py', [4], ('other-rule',))


# A11

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


def _a11(root: pathlib.Path) -> dict[str, phaseb.Candidate]:
    return {candidate.id: candidate for candidate in phaseb.list_candidates('A11', root)}


def _a11_project(project: Project, body: str) -> pathlib.Path:
    return project({'src/pkg/__init__.py': '', 'src/pkg/types.py': A11_TYPES, 'src/pkg/mod.py': body})


def test_a11_lists_an_enum_chain_with_annotation_and_type_source(project: Project) -> None:
    found = _a11(_a11_project(project, A11_CHAIN))
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
    payload = _a11(_a11_project(project, body))['src/pkg/mod.py::run::if:level#1'].payload
    assert payload['annotation'] == 'pkg.types.Level'
    assert payload['type_source'] == 'src/pkg/types.py:4 Level'


def test_a11_unannotated_subject_has_null_annotation(project: Project) -> None:
    payload = _a11(_a11_project(project, A11_TWO_ARM))['src/pkg/mod.py::run::if:mode#1'].payload
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
    assert list(_a11(_a11_project(project, body))) == ['src/pkg/mod.py::run::if:mode#1']


def test_a11_ignores_a_single_if_without_else(project: Project) -> None:
    body = """
    def run(mode):
        if mode == 'a':
            return 1
        return 0
    """
    assert _a11(_a11_project(project, body)) == {}


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
    assert len(_a11(_a11_project(project, body))) == 1


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
    assert _a11(_a11_project(project, body)) == {}


def test_a11_lists_a_two_way_split_on_a_comparison_flag(project: Project) -> None:
    body = """
    def run(mode):
        flag = mode == 'a'
        if flag:
            return 1
        else:
            return 2
    """
    assert list(_a11(_a11_project(project, body))) == ['src/pkg/mod.py::run::if:mode#1']


def test_a11_ignores_a_flag_not_assigned_from_a_comparison(project: Project) -> None:
    body = """
    def run(flag):
        if flag:
            return 1
        else:
            return 2
    """
    assert _a11(_a11_project(project, body)) == {}


def test_a11_lists_a_match_statement(project: Project) -> None:
    body = """
    def run(mode):
        match mode:
            case 'a':
                return 1
            case _:
                raise ValueError(mode)
    """
    assert list(_a11(_a11_project(project, body))) == ['src/pkg/mod.py::run::match:mode#1']


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
    assert list(_a11(_a11_project(project, body))) == ['src/pkg/mod.py::run::if:mode#1', 'src/pkg/mod.py::run::if:mode#2']


def test_a11_drops_a_chain_the_assert_never_rule_flags(project: Project) -> None:
    assert _a11(_a11_project(project, A11_STRING_CHAIN)) == {}


def test_a11_drops_a_chain_whose_hit_is_accepted(project: Project) -> None:
    accepted = A11_STRING_CHAIN.replace("if mode == 'a':", "if mode == 'a':  # auditme: accept[assert-never-missing] probe", 1)
    assert _a11(_a11_project(project, accepted)) == {}


def test_a11_id_survives_an_edit_above_and_hash_tracks_the_chain(project: Project) -> None:
    key = 'src/pkg/mod.py::run::if:mode#1'
    first = _a11(_a11_project(project, A11_TWO_ARM))[key]
    above = _a11(_a11_project(project, 'X = 1\n\n\n' + A11_TWO_ARM.lstrip('\n')))[key]
    assert above.hash == first.hash
    inside = _a11(_a11_project(project, A11_TWO_ARM.replace('return 2', 'return 3')))[key]
    assert inside.hash != first.hash
    outside = _a11(_a11_project(project, A11_TWO_ARM.replace('def run(mode):', 'def run(mode):\n    x = 1')))[key]
    assert outside.hash == first.hash
