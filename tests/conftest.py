"""Shared fixtures for the auditme checker tests.

The checker is a stdlib-only script, run as
`python3 ~/.claude/skills/auditme/checks/audit.py <project-root>` with no venv
and no installation step. These tests therefore put `checks/` on `sys.path`
directly rather than importing an installed package, which keeps the suite
runnable wherever the skill is checked out.
"""

import collections.abc
import contextlib
import io
import json
import pathlib
import sys
import textwrap

import pytest

CHECKS_ROOT = pathlib.Path(__file__).resolve().parent.parent / 'checks'
if str(CHECKS_ROOT) not in sys.path:
    sys.path.insert(0, str(CHECKS_ROOT))

import auditme.core  # noqa: E402  sys.path is set up immediately above


@pytest.fixture(autouse=True)
def clean_emitted() -> collections.abc.Iterator[None]:
    """Clear the checker's duplicate suppressor around every test.

    `auditme.core._EMITTED` is process-lifetime module state: the driver relies
    on it to report a project-level hit once rather than once per package. In a
    test process it would also swallow the second test that produced an
    identical hit, making assertions depend on test order.
    """
    auditme.core._EMITTED.clear()
    yield
    auditme.core._EMITTED.clear()


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
def run_check() -> collections.abc.Callable[..., list[dict]]:
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
    ) -> list[dict]:
        auditme.core._EMITTED.clear()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            check(root, (root / src_root) if src_root else (root / 'src' / package))
        return [json.loads(line) for line in buffer.getvalue().splitlines()]

    return run
