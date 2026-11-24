"""Shared fixtures for the auditme checker tests.

The checker is a stdlib-only script, run as
`python3 ~/.claude/skills/auditme/checks/audit.py <project-root>` with no venv
and no installation step. These tests therefore put `checks/` on `sys.path`
directly rather than importing an installed package, which keeps the suite
runnable wherever the skill is checked out.
"""

import contextlib
import io
import json
import pathlib
import subprocess
import sys
import textwrap
import typing

import pytest

# auditme: accept[non-alphabetical-literal] `-c` flag and value pairs, in order
GIT_ENV_ARGS = ['-c', 'user.email=test@example.com', '-c', 'user.name=Test']
FUTURE_IMPORT = 'from __future__ import annotations\n'
CHECKS_ROOT = pathlib.Path(__file__).resolve().parent.parent / 'checks'


def git(repo: pathlib.Path, *args: str) -> None:
    subprocess.run(['git', *GIT_ENV_ARGS, *args], cwd=repo, check=True, capture_output=True)


if str(CHECKS_ROOT) not in sys.path:
    sys.path.insert(0, str(CHECKS_ROOT))

import auditme.core  # noqa: E402  sys.path is set up immediately above
import auditme.phaseb.candidates  # noqa: E402  sys.path is set up above

if typing.TYPE_CHECKING:
    import collections.abc


def make_candidate(candidate_id: str, **overrides) -> auditme.phaseb.candidates.Candidate:
    fields = {'question': 'Q1', 'id': candidate_id, 'path': 'src/pkg/mod.py', 'start': 1, 'end': 2, 'payload': {}, 'hash': 'h'}
    fields.update(overrides)
    return auditme.phaseb.candidates.Candidate(**fields)


def make_verdict(candidate_id: str = 'src/pkg/mod.py::probe', **overrides) -> auditme.phaseb.candidates.Verdict:
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
    return auditme.phaseb.candidates.Verdict(**fields)


@pytest.fixture(autouse=True)
def clean_emitted() -> collections.abc.Iterator[None]:
    """Clear the checker's duplicate suppressor around every test.

    `auditme.core.EMITTED` is process-lifetime module state: the driver relies
    on it to report a project-level hit once rather than once per package. In a
    test process it would also swallow the second test that produced an
    identical hit, making assertions depend on test order.
    """
    auditme.core.EMITTED.clear()
    auditme.core.UNREADABLE.clear()
    yield
    auditme.core.EMITTED.clear()
    auditme.core.UNREADABLE.clear()


@pytest.fixture(autouse=True)
def restore_extra_roots() -> collections.abc.Iterator[None]:
    """Put `EXTRA_ROOT_NAMES` back after every test.

    `--extra-root` is configuration a check has to see, and a check receives
    only a scope and a root, so the driver rebinds the module-level default.
    In a test process that rebinding would outlive the test that caused it.
    """
    original = auditme.core.EXTRA_ROOT_NAMES
    yield
    auditme.core.EXTRA_ROOT_NAMES = original


@pytest.fixture(autouse=True)
def restore_never_accepted() -> collections.abc.Iterator[None]:
    """Put `NEVER_ACCEPTED` back after every test: the driver rebinds it for each run."""
    original = auditme.core.NEVER_ACCEPTED
    yield
    auditme.core.NEVER_ACCEPTED = original


@pytest.fixture
def project(tmp_path: pathlib.Path) -> collections.abc.Callable[[dict[str, str]], pathlib.Path]:
    """Return a builder that writes a throwaway project tree and returns its root.

    Keys are paths relative to the project root; values are file contents,
    dedented and stripped of a leading blank line so a test can write them as
    indented triple-quoted strings.
    """

    def build(files: dict[str, str]) -> pathlib.Path:
        for relative, content in files.items():
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(content).lstrip('\n'), encoding='utf-8')
        return tmp_path

    return build


@pytest.fixture
def run_check() -> collections.abc.Callable[..., list[dict[str, typing.Any]]]:
    """Return a runner that executes one check over one root and parses its hits.

    The root is `src/<package>/` unless `src_root` names another one relative
    to the project, which is how a case covers a root outside `src/` - the
    driver sweeps `bin/` as its own pass exactly as it sweeps a package.

    Checks report by printing one JSON object per line, so the runner captures
    stdout rather than inspecting a return value - there is none.
    """

    def run(
        check: collections.abc.Callable[[pathlib.Path, pathlib.Path], None],
        root: pathlib.Path,
        package: str = 'probe',
        src_root: str | None = None,
    ) -> list[dict[str, typing.Any]]:
        auditme.core.EMITTED.clear()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            check(root, (root / src_root) if src_root else (root / 'src' / package))
        return [json.loads(line) for line in buffer.getvalue().splitlines()]

    return run
