"""A pytest plugin that records what every `run_check` call returns.

`test_equivalence.py` loads it into a run of the catalogue's rule tests with
`-p`. With `AUDITOR_RECORD_DIR=<dir>` set, each call writes its hits to
`<dir>/<test id>.jsonl`; the first call of a test writes `<test id>.jsonl`,
later calls `<test id>.<n>.jsonl`. It also registers the catalogue's Phase B
questions, as `tests/conftest.py` does, which `auditor rules test` does not.
"""

import json
import os
import pathlib
import re
import typing

import pytest

import auditor.phaseb.candidates

if typing.TYPE_CHECKING:
    import collections.abc


auditor.phaseb.candidates.use_rules_repository()


@pytest.fixture
def run_check(
    request: pytest.FixtureRequest, run_check: collections.abc.Callable[..., list[dict[str, typing.Any]]]
) -> collections.abc.Callable[..., list[dict[str, typing.Any]]]:
    """Wrap the plugin's `run_check` and write each result under `AUDITOR_RECORD_DIR`."""
    record = os.environ.get('AUDITOR_RECORD_DIR')
    if not record:
        return run_check
    directory = pathlib.Path(record)
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
