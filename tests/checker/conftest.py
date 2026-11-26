"""Shared fixtures for the auditme checker tests.

The checker is the installed `auditor` package, run as `auditor check <project-root>`.
These tests import it by its full path. The generic fixtures come from the
`auditor.testing` plugin; this file keeps what is specific to this suite.
"""

import json
import os
import pathlib
import re
import typing

import pytest

if typing.TYPE_CHECKING:
    import collections.abc

import auditor.phaseb.candidates
import auditor.testing

# auditme: accept[reexport-in-non-init] the checker tests call `conftest.git`
git = auditor.testing.git


def pytest_configure(config: pytest.Config) -> None:
    """Load the `auditor.testing` plugin for this suite."""
    config.pluginmanager.register(auditor.testing, 'auditor-testing')


FUTURE_IMPORT = 'from __future__ import annotations\n'


def make_candidate(candidate_id: str, **overrides) -> auditor.phaseb.candidates.Candidate:
    fields = {'question': 'Q1', 'id': candidate_id, 'path': 'src/pkg/mod.py', 'start': 1, 'end': 2, 'payload': {}, 'hash': 'h'}
    fields.update(overrides)
    return auditor.phaseb.candidates.Candidate(**fields)


def make_verdict(candidate_id: str = 'src/pkg/mod.py::probe', **overrides) -> auditor.phaseb.candidates.Verdict:
    fields = {
        'question': 'Q1',
        'id': candidate_id,
        'hash': 'abc',
        'brief_version': 1,
        'findings': {'missing': [], 'extra': []},
        'reason': 'ok',
        'judged': '2026-01-01',
    }
    fields.update(overrides)
    return auditor.phaseb.candidates.Verdict(**fields)


@pytest.fixture
def run_check(
    request: pytest.FixtureRequest, run_check: collections.abc.Callable[..., list[dict[str, typing.Any]]]
) -> collections.abc.Callable[..., list[dict[str, typing.Any]]]:
    """Wrap the plugin's `run_check`; with `AUDITOR_DUMP_FIXTURES=<dir>` set, write each result to `<dir>/<test id>.jsonl`.

    The first call of a test writes `<test id>.jsonl`; later calls write `<test id>.<n>.jsonl`.
    """
    dump = os.environ.get('AUDITOR_DUMP_FIXTURES')
    if not dump:
        return run_check
    directory = pathlib.Path(dump)
    directory.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r'[^A-Za-z0-9_.-]+', '_', request.node.nodeid)
    calls = 0

    def run(*args: typing.Any, **kwargs: typing.Any) -> list[dict[str, typing.Any]]:
        nonlocal calls
        hits = run_check(*args, **kwargs)
        calls += 1
        name = f'{stem}.jsonl' if calls == 1 else f'{stem}.{calls}.jsonl'
        (directory / name).write_text(''.join(json.dumps(hit, sort_keys=True) + '\n' for hit in hits), encoding='utf-8')
        return hits

    return run
