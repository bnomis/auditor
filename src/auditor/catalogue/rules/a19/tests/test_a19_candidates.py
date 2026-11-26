"""Tests for the A19 lister: its candidates, payloads and hashes."""

import collections.abc
import pathlib

import pytest

import auditor.api
import auditor.core
import auditor.phaseb
import auditor.phaseb.candidates
import auditor.testing

LISTER = auditor.testing.load_lister(__file__)

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


def run_a19(root: pathlib.Path) -> dict[str, auditor.api.Candidate]:
    return {candidate.id: candidate for candidate in auditor.phaseb.list_candidates('A19', root)}


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
