"""Tests for the architecture listers and their shared helpers."""

import ast
import collections.abc
import pathlib

import auditme.core
import auditme.rules.error_handling
import auditme.rules.imports_and_surfaces
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
    auditme.core.EMITTED.clear()
    auditme.core.EMITTED.add('earlier')
    architecture.capture_hits(root, [auditme.rules.error_handling.check_silent_broad_except])
    assert {'earlier'} == auditme.core.EMITTED
    assert capsys.readouterr().out == ''
    auditme.core.EMITTED.clear()


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


def _a19(root: pathlib.Path) -> dict[str, phaseb.Candidate]:
    return {candidate.id: candidate for candidate in phaseb.list_candidates('A19', root)}


def _a19_project(project: Project, body: str) -> pathlib.Path:
    return project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': body})


def _handler(exception: str, call: str) -> str:
    return f"""
def load(logger, path):
    try:
        return open(path).read()
    except {exception}:
        {call}
        raise
"""


def test_a19_lists_a_broad_handler_with_its_payload(project: Project) -> None:
    found = _a19(_a19_project(project, A19_WARNING))
    assert list(found) == ['src/pkg/mod.py::load::except#1']
    payload = found['src/pkg/mod.py::load::except#1'].payload
    assert payload['log_calls'] == ["critical: f'bad {error}'"]
    assert payload['handler'].startswith('except Exception as error:')
    assert payload['try'].startswith('try:')
    function = payload['function']
    assert (function['name'], function['signature'], function['returns']) == ('load', 'path', None)
    assert function['last_statement'].startswith('try:')


def test_a19_lists_a_bare_except(project: Project) -> None:
    found = _a19(_a19_project(project, _handler('', 'pass').replace('except :', 'except:')))
    assert list(found) == ['src/pkg/mod.py::load::except#1']


@pytest.mark.parametrize('receiver', ['logger', 'log', '_logger', 'LOGGER', 'logging', 'loguru.logger', 'self.logger'])
def test_a19_lists_a_narrow_handler_that_logs_exception(project: Project, receiver: str) -> None:
    found = _a19(_a19_project(project, _handler('ValueError', f"{receiver}.exception('x')")))
    assert list(found) == ['src/pkg/mod.py::load::except#1']
    assert found['src/pkg/mod.py::load::except#1'].payload['log_calls'] == ["exception: 'x'"]


def test_a19_ignores_a_narrow_handler_that_logs_at_error(project: Project) -> None:
    assert _a19(_a19_project(project, _handler('ValueError', "logger.error('x')"))) == {}


def test_a19_drops_a_handler_on_a_silent_broad_except_hit(project: Project) -> None:
    assert _a19(_a19_project(project, SILENT)) == {}


def test_a19_drops_a_handler_on_a_wrong_level_hit(project: Project) -> None:
    assert _a19(_a19_project(project, _handler('Exception', "logger.warning('x')"))) == {}


def test_a19_drops_a_handler_on_a_graceful_degradation_hit_on_the_last_return(project: Project) -> None:
    assert _a19(_a19_project(project, A19_FALLTHROUGH)) == {}


def test_a19_drops_a_handler_whose_hit_is_accepted(project: Project) -> None:
    assert _a19(_a19_project(project, ACCEPTED)) == {}


def test_a19_numbers_two_handlers_in_one_function_in_order(project: Project) -> None:
    assert list(_a19(_a19_project(project, A19_TWO_HANDLERS))) == ['src/pkg/mod.py::load::except#1', 'src/pkg/mod.py::load::except#2']


def test_a19_module_level_handler_hashes_the_try_statement(project: Project) -> None:
    found = _a19(_a19_project(project, A19_MODULE_LEVEL))
    key = 'src/pkg/mod.py::<module>::except#1'
    assert list(found) == [key]
    assert found[key].payload['function'] is None
    edited = _a19(_a19_project(project, A19_MODULE_LEVEL.replace('json = None', 'json = 1')))[key]
    assert edited.hash != found[key].hash
    outside = _a19(_a19_project(project, A19_MODULE_LEVEL + '\nY = 2\n'))[key]
    assert outside.hash == found[key].hash


def test_a19_hash_tracks_the_enclosing_function_only(project: Project) -> None:
    key = 'src/pkg/mod.py::load::except#1'
    first = _a19(_a19_project(project, A19_WARNING + A19_OTHER))[key]
    inside = _a19(_a19_project(project, (A19_WARNING + A19_OTHER).replace("return ''", 'return None')))[key]
    assert inside.hash != first.hash
    elsewhere = _a19(_a19_project(project, A19_WARNING + A19_OTHER.replace('return 1', 'return 2')))[key]
    assert elsewhere.hash == first.hash
    above = _a19(_a19_project(project, 'X = 1\n' + A19_WARNING + A19_OTHER))[key]
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


def _a1(root: pathlib.Path) -> dict[str, phaseb.Candidate]:
    return {candidate.id: candidate for candidate in phaseb.list_candidates('A1', root)}


def _a1_project(project: Project, body: str, **extra: str) -> pathlib.Path:
    files = {'src/pkg/__init__.py': '', 'src/pkg/base.py': A1_BASE, 'src/pkg/mod.py': body}
    files.update({f'src/pkg/{name}.py': text for name, text in extra.items()})
    return project(files)


def test_a1_lists_an_open_call_with_its_payload(project: Project) -> None:
    found = _a1(_a1_project(project, A1_OPEN))
    assert list(found) == ['src/pkg/mod.py::load::call:open#1']
    payload = found['src/pkg/mod.py::load::call:open#1'].payload
    assert payload['call'] == 'open'
    assert payload['try'] is None
    assert payload['envelopes'] == []
    assert payload['domain_errors'] == ['ProbeError']
    assert 'callers' not in payload


def test_a1_gives_the_enclosing_try(project: Project) -> None:
    payload = _a1(_a1_project(project, A1_TRY))['src/pkg/mod.py::load::call:open#1'].payload
    assert payload['try'].startswith('try:')


def test_a1_gives_a_translating_with_envelope(project: Project) -> None:
    found = _a1(_a1_project(project, A1_WITH_ENVELOPE, guard=A1_GUARD))
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
    assert list(_a1(_a1_project(project, body))) == [f'src/pkg/mod.py::load::call:{callee}#1']


def test_a1_lists_a_client_method_only_in_a_module_importing_a_client(project: Project) -> None:
    with_client = 'import sqlite3\n\n\ndef load(conn):\n    return conn.execute("x")\n'
    without = 'def load(conn):\n    return conn.execute("x")\n'
    assert list(_a1(_a1_project(project, with_client))) == ['src/pkg/mod.py::load::call:conn.execute#1']
    assert _a1(_a1_project(project, without)) == {}


def test_a1_ignores_a_package_without_a_domain_error(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': A1_OPEN})
    assert _a1(root) == {}


@pytest.mark.parametrize('name', ['test_probe.py', 'probe_test.py', 'conftest.py', 'tests/helpers.py'])
def test_a1_ignores_test_files(project: Project, name: str) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/base.py': A1_BASE, f'src/pkg/{name}': A1_OPEN})
    assert _a1(root) == {}


def test_a1_drops_a_call_on_a_filesystem_envelope_gap_hit(project: Project) -> None:
    assert _a1(_a1_project(project, A1_NARROW)) == {}


def test_a1_drops_a_call_whose_hit_is_accepted(project: Project) -> None:
    assert _a1(_a1_project(project, A1_NARROW_ACCEPTED)) == {}


def test_a1_drops_a_call_on_a_filesystem_op_without_envelope_hit(project: Project) -> None:
    root = project({'src/pkg/__init__.py': A1_PUBLIC_INIT, 'src/pkg/errors.py': A1_BASE, 'src/pkg/mod.py': A1_UNGUARDED})
    assert _a1(root) == {}


def test_a1_drops_a_call_on_a_translator_envelope_gap_hit(project: Project) -> None:
    assert _a1(_a1_project(project, A1_NARROW_DECORATED, guard=A1_NARROW_GUARD)) == {}


def test_a1_lists_the_callers_of_a_private_helper(project: Project) -> None:
    found = _a1(_a1_project(project, A1_HELPER + A1_HELPER_OTHER))
    callers = found['src/pkg/mod.py::_read::call:open#1'].payload['callers']
    assert [(caller['at'], caller['caller']) for caller in callers] == [('src/pkg/mod.py:10', 'load'), ('src/pkg/mod.py:17', 'other')]
    assert callers[0]['envelope']['try'].startswith('try:')
    assert callers[1]['envelope'] is None


def test_a1_lists_the_callers_of_a_nested_helper(project: Project) -> None:
    found = _a1(_a1_project(project, A1_NESTED))
    payload = found['src/pkg/mod.py::load.read::call:open#1'].payload
    assert [caller['caller'] for caller in payload['callers']] == ['load']


def test_a1_public_helper_has_no_callers_key(project: Project) -> None:
    found = _a1(_a1_project(project, A1_HELPER.replace('_read', 'read_it')))
    assert 'callers' not in found['src/pkg/mod.py::read_it::call:open#1'].payload


def test_a1_hash_tracks_the_callers_of_a_helper(project: Project) -> None:
    key = 'src/pkg/mod.py::_read::call:open#1'
    first = _a1(_a1_project(project, A1_HELPER))[key]
    with_new_caller = _a1(_a1_project(project, A1_HELPER + A1_HELPER_OTHER))[key]
    assert with_new_caller.hash != first.hash
    unlisted_edit = _a1(_a1_project(project, A1_HELPER + A1_UNRELATED))[key]
    assert unlisted_edit.hash == first.hash
    edited_caller = _a1(_a1_project(project, A1_HELPER.replace('return _read(path)', 'return _read(path).strip()')))[key]
    assert edited_caller.hash != first.hash


def test_a1_id_survives_an_edit_above_and_hash_tracks_the_function(project: Project) -> None:
    key = 'src/pkg/mod.py::load::call:open#1'
    first = _a1(_a1_project(project, A1_OPEN + A1_UNRELATED))[key]
    above = _a1(_a1_project(project, 'X = 1\n' + A1_OPEN + A1_UNRELATED))[key]
    assert above.hash == first.hash
    outside = _a1(_a1_project(project, A1_OPEN + A1_UNRELATED.replace('return 1', 'return 2')))[key]
    assert outside.hash == first.hash
    inside = _a1(_a1_project(project, (A1_OPEN + A1_UNRELATED).replace('.read()', '.read(1)')))[key]
    assert inside.hash != first.hash


def test_a1_hash_tracks_the_domain_errors(project: Project) -> None:
    key = 'src/pkg/mod.py::load::call:open#1'
    first = _a1(_a1_project(project, A1_OPEN))[key]
    root = project({'src/pkg/__init__.py': '', 'src/pkg/base.py': A1_BASE + '\n\nclass OtherError(ProbeError):\n    pass\n', 'src/pkg/mod.py': A1_OPEN})
    assert _a1(root)[key].hash != first.hash


def test_a1_numbers_repeated_calls_in_order(project: Project) -> None:
    body = 'def load(a, b):\n    return open(a).read() + open(b).read()\n'
    assert list(_a1(_a1_project(project, body))) == ['src/pkg/mod.py::load::call:open#1', 'src/pkg/mod.py::load::call:open#2']


# A17

A17_INIT = "from .base import Probe\n\n__all__ = ['Probe']\n"
A17_BASE = 'class Probe:\n    pass\n'
A17_READER = 'import pkg.sub\n\n\ndef use():\n    return pkg.sub.Probe\n'
A17_KEY = 'src/pkg/sub/__init__.py'


def _a17(root: pathlib.Path) -> dict[str, phaseb.Candidate]:
    return {candidate.id: candidate for candidate in phaseb.list_candidates('A17', root)}


def _a17_project(project: Project, extra: dict[str, str] | None = None, init: str = A17_INIT) -> pathlib.Path:
    files = {'src/pkg/__init__.py': '', A17_KEY: init, 'src/pkg/sub/base.py': A17_BASE}
    files.update(extra or {})
    return project(files)


def test_a17_lists_an_all_init_with_its_consumers(project: Project) -> None:
    candidate = _a17(_a17_project(project, {'src/pkg/user.py': A17_READER}))[A17_KEY]
    assert candidate.payload['all'] == ['Probe']
    assert candidate.payload['consumers'] == {'Probe': ['src/pkg/user.py: return pkg.sub.Probe']}


def test_a17_leaves_out_a_test_tree_reader_and_its_hash(project: Project) -> None:
    first = _a17(_a17_project(project))[A17_KEY]
    with_test = _a17(_a17_project(project, {'src/tests/test_sub.py': A17_READER}))[A17_KEY]
    assert with_test.payload['consumers'] == {'Probe': []}
    assert with_test.hash == first.hash


def test_a17_counts_a_project_script_target_as_a_consumer(project: Project) -> None:
    root = _a17_project(project, {'pyproject.toml': '[project.scripts]\nprobe = "pkg.sub:Probe"\n'})
    assert _a17(root)[A17_KEY].payload['consumers'] == {'Probe': ['pyproject.toml: probe = "pkg.sub:Probe"']}


def test_a17_lists_reach_ins_for_an_empty_init(project: Project) -> None:
    root = _a17_project(project, {'src/pkg/user.py': 'from pkg.sub.base import Probe\n'}, init='')
    assert _a17(root)[A17_KEY].payload['reach_ins'] == ['src/pkg/user.py: from pkg.sub.base import Probe']


def test_a17_drops_an_init_on_an_empty_init_hit(project: Project) -> None:
    root = project(
        {
            'src/pkg/__init__.py': '',
            'src/pkg/sub/__init__.py': '',
            'src/pkg/big/__init__.py': "__all__ = ['a', 'b', 'c', 'd', 'e']\n",
        }
    )
    found = _a17(root)
    assert A17_KEY not in found
    assert 'src/pkg/big/__init__.py' in found


def test_a17_removes_a_consumer_a_shim_hit_names(project: Project) -> None:
    files = {'src/pkg/canon.py': A17_BASE, 'src/pkg/user.py': 'from pkg.sub import Probe\n'}
    root = _a17_project(project, files, init="import pkg.canon\n\n__all__ = ['Probe']\n\nProbe = pkg.canon.Probe\n")
    hits = architecture.capture_hits(root, (auditme.rules.imports_and_surfaces.check_migration_shim_consumers,))
    assert ('migration-shim-consumer', 'src/pkg/user.py', 1) in hits
    assert _a17(root)[A17_KEY].payload['consumers'] == {'Probe': []}


def test_a17_hash_ignores_a_moved_consumer_line_and_tracks_an_init_edit(project: Project) -> None:
    first = _a17(_a17_project(project, {'src/pkg/user.py': A17_READER}))[A17_KEY]
    moved = _a17(_a17_project(project, {'src/pkg/user.py': 'X = 1\n' + A17_READER}))[A17_KEY]
    assert moved.hash == first.hash
    edited = _a17(_a17_project(project, {'src/pkg/user.py': A17_READER}, init=A17_INIT + '# edit\n'))[A17_KEY]
    assert edited.hash != first.hash
