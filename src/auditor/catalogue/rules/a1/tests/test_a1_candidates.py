"""Tests for the A1 lister: its candidates, payloads and hashes."""

import builtins
import collections.abc
import pathlib

import hypothesis
import hypothesis.strategies
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


DOTTED = hypothesis.strategies.from_regex(r'[a-z]{1,4}(\.[a-z]{1,4}){0,2}', fullmatch=True)


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


def run_a1(root: pathlib.Path) -> dict[str, auditor.api.Candidate]:
    return {candidate.id: candidate for candidate in auditor.phaseb.list_candidates('A1', root)}


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


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    module=DOTTED, suffix=DOTTED, ident=hypothesis.strategies.from_regex(r'[a-z]{1,4}', fullmatch=True), others=hypothesis.strategies.lists(DOTTED, max_size=3)
)
def test_is_under_accepts_the_module_and_its_children_only(module: str, suffix: str, ident: str, others: list[str]) -> None:
    check = LISTER.is_under
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
    assert LISTER.reaches_exception(lineage) == expected
    if expected:
        assert LISTER.reaches_exception([*lineage, *more])


def test_a1_listing_resolves_the_audit_roots_once(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    auditor.core.clear_source_cache()
    calls: list[pathlib.Path] = []
    original = auditor.core.audit_roots

    def counting(scope: pathlib.Path) -> list[pathlib.Path]:
        calls.append(scope)
        return original(scope)

    monkeypatch.setattr(auditor.core, 'audit_roots', counting)
    auditor.phaseb.list_candidates('A1', root)
    assert len(calls) == 1
