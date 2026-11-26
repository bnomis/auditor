"""The catalogue's rule tests give the hits that the built-in checks gave.

`baseline/fixtures.jsonl` records what each `run_check` call returned in the
test suite that ran the built-in checks. The rule tests were moved into the
catalogue with their bodies unchanged, so a run of them over the catalogue
must return the same hits for the same test and call.

Each line of the baseline is one call: the test's name with its parameters
(its node id without the file), the call's number within the test, and its
hits as `[accepted, evidence, line, path, rule, variant]`.
"""

import json
import os
import pathlib
import re
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
CATALOGUE = HERE.parents[1] / 'src' / 'auditor' / 'catalogue'
BASELINE = HERE / 'baseline' / 'fixtures.jsonl'
FIELDS = ('accepted', 'evidence', 'line', 'path', 'rule', 'variant')
RECORDED_NAME_RE = re.compile(r'^.*?\.py_(.*?)(?:\.(\d+))?\.jsonl$')
RUN_RULE_TESTS = 'import sys, auditor.rulescli; sys.exit(auditor.rulescli.main(sys.argv[1:]))'


def baseline_calls() -> list[str]:
    return sorted(BASELINE.read_text(encoding='utf-8').splitlines())


def recorded_calls(directory: pathlib.Path) -> list[str]:
    calls = []
    for path in directory.iterdir():
        match = RECORDED_NAME_RE.match(path.name)
        assert match, path.name
        hits = sorted([hit.get(field) for field in FIELDS] for hit in map(json.loads, path.read_text(encoding='utf-8').splitlines()))
        calls.append(json.dumps({'call': int(match.group(2) or 1), 'hits': hits, 'test': match.group(1)}, sort_keys=True))
    return sorted(calls)


@pytest.fixture(scope='module')
def recorded(tmp_path_factory: pytest.TempPathFactory) -> list[str]:
    directory = tmp_path_factory.mktemp('recorded')
    env = {
        **os.environ,
        'AUDITOR_RECORD_DIR': str(directory),
        'AUDITOR_RULES_PATH': str(CATALOGUE),
        'PYTHONPATH': os.pathsep.join([str(HERE), os.environ.get('PYTHONPATH', '')]),
    }
    result = subprocess.run(
        [sys.executable, '-c', RUN_RULE_TESTS, 'test', '-p', 'recorder', '-q', '-p', 'no:cacheprovider'],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stdout[-2000:]
    return recorded_calls(directory)


def test_every_rule_test_call_gives_the_baseline_hits(recorded: list[str]) -> None:
    baseline = baseline_calls()
    missing = [call for call in baseline if call not in recorded]
    extra = [call for call in recorded if call not in baseline]
    assert not missing, f'calls whose hits changed or that no test makes now: {[json.loads(call)["test"] for call in missing][:10]}'
    assert not extra, f'calls with no baseline: {[json.loads(call)["test"] for call in extra][:10]}'
