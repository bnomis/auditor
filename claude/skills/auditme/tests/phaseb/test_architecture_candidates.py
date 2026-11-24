"""Tests for the architecture listers and their shared helpers."""

import ast
import builtins
import collections.abc
import pathlib

import auditme.core
import auditme.phaseb
import auditme.phaseb.architecture
import auditme.phaseb.candidates
import auditme.rules.error_handling
import auditme.rules.imports_and_surfaces
import hypothesis
import hypothesis.strategies
import pytest

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


def raise_boom(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    raise RuntimeError('boom')


# capture_hits


def test_capture_hits_returns_rule_path_line_triples(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    hits = auditme.phaseb.architecture.capture_hits(root, [auditme.rules.error_handling.check_silent_broad_except])
    assert hits == {('silent-broad-except', 'src/pkg/mod.py', 4)}


def test_capture_hits_includes_accepted_hits(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': ACCEPTED})
    hits = auditme.phaseb.architecture.capture_hits(root, [auditme.rules.error_handling.check_silent_broad_except])
    assert hits == {('silent-broad-except', 'src/pkg/mod.py', 4)}


def test_capture_hits_restores_emitted_and_prints_nothing(project: Project, capsys: pytest.CaptureFixture[str]) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    auditme.core.EMITTED.clear()
    auditme.core.EMITTED.add('earlier')
    auditme.phaseb.architecture.capture_hits(root, [auditme.rules.error_handling.check_silent_broad_except])
    assert {'earlier'} == auditme.core.EMITTED
    assert capsys.readouterr().out == ''
    auditme.core.EMITTED.clear()


def test_capture_hits_names_a_check_that_raises(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    with pytest.raises(auditme.phaseb.PhaseBError, match='raise_boom'):
        auditme.phaseb.architecture.capture_hits(root, [raise_boom])


# shared


def test_unparseable_file_raises_naming_it(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/bad.py': 'def (:\n'})
    with pytest.raises(auditme.phaseb.PhaseBError, match='bad.py'):
        auditme.phaseb.architecture.read_audited_files(root)


def test_parse_audited_files_returns_each_file(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    assert {file.rel for file in auditme.phaseb.architecture.read_audited_files(root)} == {'src/pkg/__init__.py', 'src/pkg/mod.py'}


def test_site_counter_numbers_sites_per_qualname() -> None:
    counter = auditme.phaseb.architecture.SiteCounter()
    assert counter.next('pkg.mod.f') == 1
    assert counter.next('pkg.mod.f') == 2
    assert counter.next('pkg.mod.g') == 1
    assert counter.next('pkg.mod.f') == 3


def test_walk_with_qualname_names_functions_methods_and_module_level() -> None:
    tree = ast.parse('x = 1\n\n\ndef f():\n    y = 2\n\n\nclass C:\n    def m(self):\n        z = 3\n')
    found = {qualname for qualname, node in auditme.phaseb.architecture.walk_with_qualname(tree) if isinstance(node, ast.Assign)}
    assert found == {'<module>', 'f', 'C.m'}


def test_hit_on_anchor_matches_rule_path_and_line() -> None:
    hits = {('silent-broad-except', 'src/pkg/mod.py', 4)}
    assert auditme.phaseb.architecture.hit_on_anchor(hits, 'src/pkg/mod.py', [3, 4], ('silent-broad-except',))
    assert not auditme.phaseb.architecture.hit_on_anchor(hits, 'src/pkg/mod.py', [3], ('silent-broad-except',))
    assert not auditme.phaseb.architecture.hit_on_anchor(hits, 'src/pkg/other.py', [4], ('silent-broad-except',))
    assert not auditme.phaseb.architecture.hit_on_anchor(hits, 'src/pkg/mod.py', [4], ('other-rule',))


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


def run_a11(root: pathlib.Path) -> dict[str, auditme.phaseb.candidates.Candidate]:
    return {candidate.id: candidate for candidate in auditme.phaseb.list_candidates('A11', root)}


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


# A19

A19_WARNING = """
import loguru


def load(path):
    try:
        return open(path).read()
    except Exception as error:
        loguru.logger.critical(f'bad {error}')
        return ''
"""

A19_OTHER = """
def other():
    return 1
"""

A19_TWO_HANDLERS = """
import loguru


def load(path):
    try:
        return open(path).read()
    except Exception as error:
        loguru.logger.critical(f'bad {error}')
        return ''
    try:
        return 2
    except BaseException as other:
        loguru.logger.critical(str(other))
        return ''
"""

A19_MODULE_LEVEL = """
import loguru

try:
    import json
except Exception:
    loguru.logger.critical('x')
    json = None
"""

A19_FALLTHROUGH = """
def load(logger, path):
    try:
        return open(path).read()
    except ValueError:
        logger.exception('x')
    return ''
"""


def run_a19(root: pathlib.Path) -> dict[str, auditme.phaseb.candidates.Candidate]:
    return {candidate.id: candidate for candidate in auditme.phaseb.list_candidates('A19', root)}


def write_a19_project(project: Project, body: str) -> pathlib.Path:
    return project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': body})


def handler_source(exception: str, call: str) -> str:
    return f"""
def load(logger, path):
    try:
        return open(path).read()
    except {exception}:
        {call}
        raise
"""


def test_a19_lists_a_broad_handler_with_its_payload(project: Project) -> None:
    found = run_a19(write_a19_project(project, A19_WARNING))
    assert list(found) == ['src/pkg/mod.py::load::except#1']
    payload = found['src/pkg/mod.py::load::except#1'].payload
    assert payload['log_calls'] == ["critical: f'bad {error}'"]
    assert payload['handler'].startswith('except Exception as error:')
    assert payload['try'].startswith('try:')
    function = payload['function']
    assert (function['name'], function['signature'], function['returns']) == ('load', 'path', None)
    assert function['last_statement'].startswith('try:')


def test_a19_lists_a_bare_except(project: Project) -> None:
    found = run_a19(write_a19_project(project, handler_source('', 'pass').replace('except :', 'except:')))
    assert list(found) == ['src/pkg/mod.py::load::except#1']


@pytest.mark.parametrize('receiver', ['logger', 'log', '_logger', 'LOGGER', 'logging', 'loguru.logger', 'self.logger'])
def test_a19_lists_a_narrow_handler_that_logs_exception(project: Project, receiver: str) -> None:
    found = run_a19(write_a19_project(project, handler_source('ValueError', f"{receiver}.exception('x')")))
    assert list(found) == ['src/pkg/mod.py::load::except#1']
    assert found['src/pkg/mod.py::load::except#1'].payload['log_calls'] == ["exception: 'x'"]


def test_a19_ignores_a_narrow_handler_that_logs_at_error(project: Project) -> None:
    assert run_a19(write_a19_project(project, handler_source('ValueError', "logger.error('x')"))) == {}


def test_a19_drops_a_handler_on_a_silent_broad_except_hit(project: Project) -> None:
    assert run_a19(write_a19_project(project, SILENT)) == {}


def test_a19_drops_a_handler_on_a_wrong_level_hit(project: Project) -> None:
    assert run_a19(write_a19_project(project, handler_source('Exception', "logger.warning('x')"))) == {}


def test_a19_drops_a_handler_on_a_graceful_degradation_hit_on_the_last_return(project: Project) -> None:
    assert run_a19(write_a19_project(project, A19_FALLTHROUGH)) == {}


def test_a19_drops_a_handler_whose_hit_is_accepted(project: Project) -> None:
    assert run_a19(write_a19_project(project, ACCEPTED)) == {}


A19_MARKED = """
def load(logger, paths):
    for path in paths:
        try:
            open(path).read()
        except Exception:  # auditme: accept[RULE] the user keeps this handler
            logger.exception('x')
            continue
"""


def test_a19_lists_a_kept_handler_the_sweep_does_not_report(project: Project) -> None:
    # A handler that `continue`s gets no sweep hit, so without a marker it is listed.
    assert list(run_a19(write_a19_project(project, A19_MARKED.replace('  # auditme: accept[RULE] the user keeps this handler', '')))) == [
        'src/pkg/mod.py::load::except#1'
    ]


@pytest.mark.parametrize('rule', ['logger-exception-graceful-degradation', 'broad-except-wrong-level', 'silent-broad-except'])
def test_a19_drops_a_handler_carrying_an_a19_marker(project: Project, rule: str) -> None:
    # A19-1 of agents/reviews/brief-thresholds-4-2026-11-23.md: the marker records the user's decision.
    assert run_a19(write_a19_project(project, A19_MARKED.replace('RULE', rule))) == {}


def test_a19_drops_a_handler_with_the_marker_on_the_line_above(project: Project) -> None:
    body = A19_MARKED.replace('  # auditme: accept[RULE] the user keeps this handler', '').replace(
        '        except Exception:', '        # auditme: accept[logger-exception-graceful-degradation] kept\n        except Exception:'
    )
    assert run_a19(write_a19_project(project, body)) == {}


def test_a19_keeps_a_handler_whose_marker_names_another_rule(project: Project) -> None:
    assert list(run_a19(write_a19_project(project, A19_MARKED.replace('RULE', 'failure-as-absence')))) == ['src/pkg/mod.py::load::except#1']


def test_a19_numbers_two_handlers_in_one_function_in_order(project: Project) -> None:
    assert list(run_a19(write_a19_project(project, A19_TWO_HANDLERS))) == ['src/pkg/mod.py::load::except#1', 'src/pkg/mod.py::load::except#2']


def test_a19_module_level_handler_hashes_the_try_statement(project: Project) -> None:
    found = run_a19(write_a19_project(project, A19_MODULE_LEVEL))
    key = 'src/pkg/mod.py::<module>::except#1'
    assert list(found) == [key]
    assert found[key].payload['function'] is None
    edited = run_a19(write_a19_project(project, A19_MODULE_LEVEL.replace('json = None', 'json = 1')))[key]
    assert edited.hash != found[key].hash
    outside = run_a19(write_a19_project(project, A19_MODULE_LEVEL + '\nY = 2\n'))[key]
    assert outside.hash == found[key].hash


def test_a19_hash_tracks_the_enclosing_function_only(project: Project) -> None:
    key = 'src/pkg/mod.py::load::except#1'
    first = run_a19(write_a19_project(project, A19_WARNING + A19_OTHER))[key]
    inside = run_a19(write_a19_project(project, (A19_WARNING + A19_OTHER).replace("return ''", 'return None')))[key]
    assert inside.hash != first.hash
    elsewhere = run_a19(write_a19_project(project, A19_WARNING + A19_OTHER.replace('return 1', 'return 2')))[key]
    assert elsewhere.hash == first.hash
    above = run_a19(write_a19_project(project, 'X = 1\n' + A19_WARNING + A19_OTHER))[key]
    assert above.hash == first.hash


# A1

A1_BASE = """
class ProbeError(Exception):
    pass
"""

A1_OPEN = """
def load(path):
    return open(path).read()
"""

A1_TRY = """
import pkg.base


def load(path):
    try:
        return open(path).read()
    except OSError as error:
        raise pkg.base.ProbeError(str(error)) from error
"""

A1_GUARD = """
import contextlib

import pkg.base


@contextlib.contextmanager
def translate():
    try:
        yield
    except OSError as error:
        raise pkg.base.ProbeError(str(error)) from error
"""

A1_WITH_ENVELOPE = """
import pkg.guard


def load(path):
    with pkg.guard.translate():
        return open(path).read()
"""

A1_NARROW = """
import pkg.base


def load(path):
    try:
        return path.read_text()
    except ValueError as error:
        raise pkg.base.ProbeError(str(error)) from error
"""

A1_NARROW_ACCEPTED = A1_NARROW.replace('except ValueError as error:', 'except ValueError as error:  # auditme: accept[filesystem-envelope-gap] probe')

A1_PUBLIC_INIT = """
from .mod import load

__all__ = ['load']
"""

A1_UNGUARDED = """
def load(path):
    path.write_text('x')
"""

A1_NARROW_GUARD = """
import contextlib

import pkg.base


@contextlib.contextmanager
def translate():
    try:
        yield
    except ValueError as error:
        raise pkg.base.ProbeError(str(error)) from error
"""

A1_NARROW_DECORATED = """
import pkg.guard


@pkg.guard.translate()
def load(path):
    return path.read_text()
"""

A1_HELPER = """
import pkg.base


def _read(path):
    return open(path).read()


def load(path):
    try:
        return _read(path)
    except OSError as error:
        raise pkg.base.ProbeError(str(error)) from error
"""

A1_HELPER_OTHER = """


def other(path):
    return _read(path)
"""

A1_NESTED = """
import pkg.base


def load(path):
    def read():
        return open(path).read()

    try:
        return read()
    except OSError as error:
        raise pkg.base.ProbeError(str(error)) from error
"""

A1_UNRELATED = """


def unrelated():
    return 1
"""


def run_a1(root: pathlib.Path) -> dict[str, auditme.phaseb.candidates.Candidate]:
    return {candidate.id: candidate for candidate in auditme.phaseb.list_candidates('A1', root)}


def write_a1_project(project: Project, body: str, **extra: str) -> pathlib.Path:
    files = {'src/pkg/__init__.py': '', 'src/pkg/base.py': A1_BASE, 'src/pkg/mod.py': body}
    files.update({f'src/pkg/{name}.py': text for name, text in extra.items()})
    return project(files)


def test_a1_lists_an_open_call_with_its_payload(project: Project) -> None:
    found = run_a1(write_a1_project(project, A1_OPEN))
    assert list(found) == ['src/pkg/mod.py::load::call:open#1']
    payload = found['src/pkg/mod.py::load::call:open#1'].payload
    assert payload['call'] == 'open'
    assert payload['try'] is None
    assert payload['envelopes'] == []
    assert payload['domain_errors'] == ['ProbeError']
    assert 'callers' not in payload


def test_a1_gives_the_enclosing_try(project: Project) -> None:
    payload = run_a1(write_a1_project(project, A1_TRY))['src/pkg/mod.py::load::call:open#1'].payload
    assert payload['try'].startswith('try:')


def test_a1_gives_a_translating_with_envelope(project: Project) -> None:
    found = run_a1(write_a1_project(project, A1_WITH_ENVELOPE, guard=A1_GUARD))
    payload = found['src/pkg/mod.py::load::call:open#1'].payload
    assert payload['envelopes'] == [{'name': 'translate', 'catches': ['OSError']}]


@pytest.mark.parametrize(
    ('imports', 'call', 'callee'),
    [
        ('', "path.write_text('x')", 'path.write_text'),
        ('import subprocess', "subprocess.run(['x'])", 'subprocess.run'),
        ('import torch', 'torch.load(path)', 'torch.load'),
        ('import pandas', 'pandas.read_csv(path)', 'pandas.read_csv'),
        ('', "df.to_parquet('x')", 'df.to_parquet'),
        ('import requests', "requests.get('x')", 'requests.get'),
        ('import pandas as pd', 'pd.read_json(path)', 'pd.read_json'),
        ('from requests import get', "get('x')", 'get'),
    ],
)
def test_a1_lists_each_external_call_shape(project: Project, imports: str, call: str, callee: str) -> None:
    body = f'{imports}\n\n\ndef load(path, df):\n    return {call}\n'
    assert list(run_a1(write_a1_project(project, body))) == [f'src/pkg/mod.py::load::call:{callee}#1']


def test_a1_lists_a_client_method_only_in_a_module_importing_a_client(project: Project) -> None:
    with_client = 'import sqlite3\n\n\ndef load(conn):\n    return conn.execute("x")\n'
    without = 'def load(conn):\n    return conn.execute("x")\n'
    assert list(run_a1(write_a1_project(project, with_client))) == ['src/pkg/mod.py::load::call:conn.execute#1']
    assert run_a1(write_a1_project(project, without)) == {}


def test_a1_ignores_a_package_without_a_domain_error(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': A1_OPEN})
    assert run_a1(root) == {}


@pytest.mark.parametrize('name', ['test_probe.py', 'probe_test.py', 'conftest.py', 'tests/helpers.py'])
def test_a1_ignores_test_files(project: Project, name: str) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/base.py': A1_BASE, f'src/pkg/{name}': A1_OPEN})
    assert run_a1(root) == {}


def test_a1_drops_a_call_on_a_filesystem_envelope_gap_hit(project: Project) -> None:
    assert run_a1(write_a1_project(project, A1_NARROW)) == {}


def test_a1_drops_a_call_whose_hit_is_accepted(project: Project) -> None:
    assert run_a1(write_a1_project(project, A1_NARROW_ACCEPTED)) == {}


def test_a1_drops_a_call_on_a_filesystem_op_without_envelope_hit(project: Project) -> None:
    root = project({'src/pkg/__init__.py': A1_PUBLIC_INIT, 'src/pkg/errors.py': A1_BASE, 'src/pkg/mod.py': A1_UNGUARDED})
    assert run_a1(root) == {}


def test_a1_drops_a_call_on_a_translator_envelope_gap_hit(project: Project) -> None:
    assert run_a1(write_a1_project(project, A1_NARROW_DECORATED, guard=A1_NARROW_GUARD)) == {}


def test_a1_lists_the_callers_of_a_private_helper(project: Project) -> None:
    found = run_a1(write_a1_project(project, A1_HELPER + A1_HELPER_OTHER))
    callers = found['src/pkg/mod.py::_read::call:open#1'].payload['callers']
    assert [(caller['at'], caller['caller']) for caller in callers] == [('src/pkg/mod.py:10', 'load'), ('src/pkg/mod.py:17', 'other')]
    assert callers[0]['envelope']['try'].startswith('try:')
    assert callers[1]['envelope'] is None


def test_a1_lists_the_callers_of_a_nested_helper(project: Project) -> None:
    found = run_a1(write_a1_project(project, A1_NESTED))
    payload = found['src/pkg/mod.py::load.read::call:open#1'].payload
    assert [caller['caller'] for caller in payload['callers']] == ['load']


def test_a1_names_why_a_helper_is_a_helper(project: Project) -> None:
    assert run_a1(write_a1_project(project, A1_HELPER))['src/pkg/mod.py::_read::call:open#1'].payload['privacy'] == 'underscore'
    assert run_a1(write_a1_project(project, A1_NESTED))['src/pkg/mod.py::load.read::call:open#1'].payload['privacy'] == 'nested'


def test_a1_lists_the_callers_of_a_script_helper(project: Project) -> None:
    script = (
        'import sys\n\n\nclass ProbeError(Exception):\n    pass\n\n\ndef read(path):\n    return open(path).read()\n\n\n'
        'def main():\n    try:\n        return read(sys.argv[1])\n    except OSError as error:\n        raise ProbeError(str(error)) from error\n\n\n'
        "if __name__ == '__main__':\n    main()\n"
    )
    payload = run_a1(project({'bin/probe.py': script}))['bin/probe.py::read::call:open#1'].payload
    assert payload['privacy'] == 'script'
    assert [caller['caller'] for caller in payload['callers']] == ['main']


def test_a1_public_helper_has_no_callers_key(project: Project) -> None:
    found = run_a1(write_a1_project(project, A1_HELPER.replace('_read', 'read_it')))
    assert 'callers' not in found['src/pkg/mod.py::read_it::call:open#1'].payload


def test_a1_hash_tracks_the_callers_of_a_helper(project: Project) -> None:
    key = 'src/pkg/mod.py::_read::call:open#1'
    first = run_a1(write_a1_project(project, A1_HELPER))[key]
    with_new_caller = run_a1(write_a1_project(project, A1_HELPER + A1_HELPER_OTHER))[key]
    assert with_new_caller.hash != first.hash
    unlisted_edit = run_a1(write_a1_project(project, A1_HELPER + A1_UNRELATED))[key]
    assert unlisted_edit.hash == first.hash
    edited_caller = run_a1(write_a1_project(project, A1_HELPER.replace('return _read(path)', 'return _read(path).strip()')))[key]
    assert edited_caller.hash != first.hash


def test_a1_id_survives_an_edit_above_and_hash_tracks_the_function(project: Project) -> None:
    key = 'src/pkg/mod.py::load::call:open#1'
    first = run_a1(write_a1_project(project, A1_OPEN + A1_UNRELATED))[key]
    above = run_a1(write_a1_project(project, 'X = 1\n' + A1_OPEN + A1_UNRELATED))[key]
    assert above.hash == first.hash
    outside = run_a1(write_a1_project(project, A1_OPEN + A1_UNRELATED.replace('return 1', 'return 2')))[key]
    assert outside.hash == first.hash
    inside = run_a1(write_a1_project(project, (A1_OPEN + A1_UNRELATED).replace('.read()', '.read(1)')))[key]
    assert inside.hash != first.hash


def test_a1_hash_tracks_the_domain_errors(project: Project) -> None:
    key = 'src/pkg/mod.py::load::call:open#1'
    first = run_a1(write_a1_project(project, A1_OPEN))[key]
    root = project({'src/pkg/__init__.py': '', 'src/pkg/base.py': A1_BASE + '\n\nclass OtherError(ProbeError):\n    pass\n', 'src/pkg/mod.py': A1_OPEN})
    assert run_a1(root)[key].hash != first.hash


def test_a1_numbers_repeated_calls_in_order(project: Project) -> None:
    body = 'def load(a, b):\n    return open(a).read() + open(b).read()\n'
    assert list(run_a1(write_a1_project(project, body))) == ['src/pkg/mod.py::load::call:open#1', 'src/pkg/mod.py::load::call:open#2']


# A17

A17_INIT = "from .base import Probe\n\n__all__ = ['Probe']\n"
A17_BASE = 'class Probe:\n    pass\n'
A17_READER = 'import pkg.sub\n\n\ndef use():\n    return pkg.sub.Probe\n'
A17_KEY = 'src/pkg/sub/__init__.py'


def run_a17(root: pathlib.Path) -> dict[str, auditme.phaseb.candidates.Candidate]:
    return {candidate.id: candidate for candidate in auditme.phaseb.list_candidates('A17', root)}


def write_a17_project(project: Project, extra: dict[str, str] | None = None, init: str = A17_INIT) -> pathlib.Path:
    files = {'src/pkg/__init__.py': '', A17_KEY: init, 'src/pkg/sub/base.py': A17_BASE}
    files.update(extra or {})
    return project(files)


def test_a17_lists_an_all_init_with_its_consumers(project: Project) -> None:
    candidate = run_a17(write_a17_project(project, {'src/pkg/user.py': A17_READER}))[A17_KEY]
    assert candidate.payload['all'] == ['Probe']
    assert candidate.payload['consumers'] == {'Probe': ['src/pkg/user.py: return pkg.sub.Probe']}


def test_a17_leaves_out_a_test_tree_reader_and_its_hash(project: Project) -> None:
    first = run_a17(write_a17_project(project))[A17_KEY]
    with_test = run_a17(write_a17_project(project, {'src/tests/test_sub.py': A17_READER}))[A17_KEY]
    assert with_test.payload['consumers'] == {'Probe': []}
    assert with_test.hash == first.hash


A17_SUBMODULE_KEY = 'src/pkg/mod.py'
A17_SUBMODULE = "__all__ = ['f']\n\n\ndef f():\n    return 1\n"


def test_a17_lists_a_submodule_all_with_a_consumer_in_another_module(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', A17_SUBMODULE_KEY: A17_SUBMODULE, 'src/pkg/user.py': 'from pkg.mod import f\n'})
    candidate = run_a17(root)[A17_SUBMODULE_KEY]
    assert candidate.payload['all'] == ['f']
    assert candidate.payload['consumers'] == {'f': ['src/pkg/user.py: from pkg.mod import f']}


def test_a17_lists_a_submodule_all_read_only_by_a_test_with_no_consumer(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', A17_SUBMODULE_KEY: A17_SUBMODULE, 'src/tests/test_mod.py': 'from pkg.mod import f\n'})
    assert run_a17(root)[A17_SUBMODULE_KEY].payload['consumers'] == {'f': []}


def test_a17_leaves_out_a_submodule_without_all(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', A17_SUBMODULE_KEY: 'def f():\n    return 1\n'})
    assert A17_SUBMODULE_KEY not in run_a17(root)


def test_a17_keeps_an_init_candidate_when_a_submodule_is_listed(project: Project) -> None:
    plain = run_a17(write_a17_project(project))[A17_KEY]
    both = run_a17(write_a17_project(project, {'src/pkg/mod.py': A17_SUBMODULE}))
    assert both[A17_KEY].hash == plain.hash
    assert 'src/pkg/mod.py' in both


def test_a17_counts_a_project_script_target_as_a_consumer(project: Project) -> None:
    root = write_a17_project(project, {'pyproject.toml': '[project.scripts]\nprobe = "pkg.sub:Probe"\n'})
    assert run_a17(root)[A17_KEY].payload['consumers'] == {'Probe': ['pyproject.toml: probe = "pkg.sub:Probe"']}


def test_a17_reports_an_unreadable_reader_as_a_phaseb_error(project: Project, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    root = write_a17_project(project)
    reader = tmp_path / 'user.py'
    reader.write_bytes(b'\xff\xfe not utf-8')
    monkeypatch.setattr(auditme.core, 'reads_by_module_and_name', lambda scope, src_root: {('pkg.sub', 'Probe'): [(reader, 1)]})
    with pytest.raises(auditme.phaseb.PhaseBError, match='user.py'):
        run_a17(root)


def test_a17_lists_reach_ins_for_an_empty_init(project: Project) -> None:
    root = write_a17_project(project, {'src/pkg/user.py': 'from pkg.sub.base import Probe\n'}, init='')
    assert run_a17(root)[A17_KEY].payload['reach_ins'] == ['src/pkg/user.py: from pkg.sub.base import Probe']


def test_a17_drops_an_init_on_an_empty_init_hit(project: Project) -> None:
    root = project(
        {
            'src/pkg/__init__.py': '',
            'src/pkg/sub/__init__.py': '',
            'src/pkg/big/__init__.py': "__all__ = ['a', 'b', 'c', 'd', 'e']\n",
        }
    )
    found = run_a17(root)
    assert A17_KEY not in found
    assert 'src/pkg/big/__init__.py' in found


def test_a17_removes_a_consumer_a_shim_hit_names(project: Project) -> None:
    files = {'src/pkg/canon.py': A17_BASE, 'src/pkg/user.py': 'from pkg.sub import Probe\n'}
    root = write_a17_project(project, files, init="import pkg.canon\n\n__all__ = ['Probe']\n\nProbe = pkg.canon.Probe\n")
    hits = auditme.phaseb.architecture.capture_hits(root, (auditme.rules.imports_and_surfaces.check_migration_shim_consumers,))
    assert ('migration-shim-consumer', 'src/pkg/user.py', 1) in hits
    assert run_a17(root)[A17_KEY].payload['consumers'] == {'Probe': []}


def test_a17_hash_ignores_a_moved_consumer_line_and_tracks_an_init_edit(project: Project) -> None:
    first = run_a17(write_a17_project(project, {'src/pkg/user.py': A17_READER}))[A17_KEY]
    moved = run_a17(write_a17_project(project, {'src/pkg/user.py': 'X = 1\n' + A17_READER}))[A17_KEY]
    assert moved.hash == first.hash
    edited = run_a17(write_a17_project(project, {'src/pkg/user.py': A17_READER}, init=A17_INIT + '# edit\n'))[A17_KEY]
    assert edited.hash != first.hash


DOTTED = hypothesis.strategies.from_regex(r'[a-z]{1,4}(\.[a-z]{1,4}){0,2}', fullmatch=True)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(qualname=DOTTED, name=hypothesis.strategies.from_regex(r'[A-Za-z_]{1,6}', fullmatch=True))
def test_child_qualname_ends_in_the_name_and_splits_back(qualname: str, name: str) -> None:
    child = auditme.phaseb.architecture.child_qualname(qualname, name)
    assert child.rsplit('.', 1) == [qualname, name]
    assert auditme.phaseb.architecture.child_qualname(auditme.phaseb.architecture.MODULE_QUALNAME, name) == name


ANCHOR_HIT = hypothesis.strategies.tuples(
    hypothesis.strategies.sampled_from('abc'), hypothesis.strategies.sampled_from(['x.py', 'y.py']), hypothesis.strategies.integers(1, 5)
)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    hits=hypothesis.strategies.sets(ANCHOR_HIT, max_size=6),
    extra=hypothesis.strategies.sets(ANCHOR_HIT, max_size=3),
    lines=hypothesis.strategies.lists(hypothesis.strategies.integers(1, 5), max_size=3),
    rules=hypothesis.strategies.lists(hypothesis.strategies.sampled_from('abc'), max_size=3),
)
def test_hit_on_anchor_matches_the_cross_product_and_is_monotone(hits, extra, lines, rules) -> None:
    check = auditme.phaseb.architecture.hit_on_anchor
    expected = any((rule, 'x.py', line) in hits for rule in rules for line in lines)
    assert check(hits, 'x.py', lines, rules) == expected
    if expected:
        assert check(hits | extra, 'x.py', lines, rules)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    module=DOTTED, suffix=DOTTED, ident=hypothesis.strategies.from_regex(r'[a-z]{1,4}', fullmatch=True), others=hypothesis.strategies.lists(DOTTED, max_size=3)
)
def test_is_under_accepts_the_module_and_its_children_only(module: str, suffix: str, ident: str, others: list[str]) -> None:
    check = auditme.phaseb.architecture.is_under
    assert check(module, [module])
    assert check(f'{module}.{suffix}', [module])
    assert not check(module + ident, [module])
    assert check(module, [*others, module])


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    lineage=hypothesis.strategies.lists(
        hypothesis.strategies.sampled_from(['Exception', 'ValueError', 'OSError', 'object', 'int', 'dict', 'Nope', 'KeyboardInterrupt']), max_size=5
    ),
    more=hypothesis.strategies.lists(hypothesis.strategies.sampled_from(['Exception', 'int']), max_size=2),
)
def test_reaches_exception_matches_issubclass_and_is_monotone(lineage: list[str], more: list[str]) -> None:
    expected = any(isinstance(getattr(builtins, name, None), type) and issubclass(getattr(builtins, name), Exception) for name in lineage)
    assert auditme.phaseb.architecture.reaches_exception(lineage) == expected
    if expected:
        assert auditme.phaseb.architecture.reaches_exception([*lineage, *more])


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    aliases=hypothesis.strategies.dictionaries(
        hypothesis.strategies.sampled_from(['Alpha', 'Beta', 'Gamma']), hypothesis.strategies.sampled_from(['src.one', 'src.two']), max_size=3
    ),
    names=hypothesis.strategies.lists(hypothesis.strategies.sampled_from(['Alpha', 'Beta', 'Delta', 'int']), min_size=1, max_size=3),
)
def test_type_source_of_is_none_or_an_alias_value(aliases: dict[str, str], names: list[str]) -> None:
    annotation = ' | '.join(names)
    result = auditme.phaseb.architecture.type_source_of(annotation, aliases)
    assert auditme.phaseb.architecture.type_source_of(None, aliases) is None
    if not any(name in aliases for name in names):
        assert result is None
    else:
        assert result in aliases.values()


def test_capture_hits_resolves_the_audit_roots_once_for_all_its_checks(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': 'X = 1\n'})
    auditme.core.clear_source_cache()
    calls: list[pathlib.Path] = []
    real = auditme.core.audit_roots

    def counting(scope: pathlib.Path) -> list[pathlib.Path]:
        calls.append(scope)
        return real(scope)

    def first(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        pass

    def second(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        pass

    monkeypatch.setattr(auditme.core, 'audit_roots', counting)
    auditme.phaseb.architecture.capture_hits(root, [first, second])
    assert len(calls) == 1


def test_a1_listing_resolves_the_audit_roots_once(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    auditme.core.clear_source_cache()
    calls: list[pathlib.Path] = []
    original = auditme.core.audit_roots

    def counting(scope: pathlib.Path) -> list[pathlib.Path]:
        calls.append(scope)
        return original(scope)

    monkeypatch.setattr(auditme.core, 'audit_roots', counting)
    auditme.phaseb.list_candidates('A1', root)
    assert len(calls) == 1


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
    original = auditme.phaseb.architecture.flag_subjects

    def counting(function: ast.AST) -> dict[str, str]:
        calls.append(function)
        return original(function)

    monkeypatch.setattr(auditme.phaseb.architecture, 'flag_subjects', counting)
    run_a11(write_a11_project(project, body))
    assert len(calls) == 1
