"""A pytest plugin of the generic helpers a rule's own tests use.

`auditor rules test` loads it with `-p auditor.testing`. It provides the
`git` helper and the `project` and `run_check` fixtures, and restores the
checker's module-level state around every test.
"""

import contextlib
import io
import json
import pathlib
import subprocess
import textwrap
import typing

import pytest

import auditor.core
import auditor.rulesrepo

if typing.TYPE_CHECKING:
    import collections.abc

# auditme: accept[non-alphabetical-literal] `-c` flag and value pairs, in order
GIT_ENV_ARGS = ['-c', 'user.email=test@example.com', '-c', 'user.name=Test']


def git(repo: pathlib.Path, *args: str) -> None:
    subprocess.run(['git', *GIT_ENV_ARGS, *args], cwd=repo, check=True, capture_output=True)


def load_check(test_file: str) -> collections.abc.Callable[[pathlib.Path, pathlib.Path], None]:
    """Return the `check` function of the rule directory that owns a test file.

    A rule's tests sit in `<repo>/rules/<rule-dir>/tests/`, and the rule
    directory name has hyphens, so a test cannot import `check.py` by name.
    Pass `__file__`.
    """
    tests_dir = pathlib.Path(test_file).resolve().parent
    rule_dir = tests_dir.parent
    repo = auditor.rulesrepo.load(rule_dir.parent.parent)
    rule = next(rule for rule in repo.rules if rule.name == rule_dir.name)
    return auditor.rulesrepo.import_entry(rule, 'check.py').check


@pytest.fixture(autouse=True)
def clean_emitted() -> collections.abc.Iterator[None]:
    """Clear the checker's duplicate suppressor around every test.

    `auditor.core.EMITTED` is process-lifetime module state: the driver relies
    on it to report a project-level hit once rather than once per package. In a
    test process it would also swallow the second test that produced an
    identical hit, making assertions depend on test order.
    """
    auditor.core.EMITTED.clear()
    auditor.core.UNREADABLE.clear()
    yield
    auditor.core.EMITTED.clear()
    auditor.core.UNREADABLE.clear()


@pytest.fixture(autouse=True)
def restore_extra_roots() -> collections.abc.Iterator[None]:
    """Put `EXTRA_ROOT_NAMES` back after every test.

    `--extra-root` is configuration a check has to see, and a check receives
    only a scope and a root, so the driver rebinds the module-level default.
    In a test process that rebinding would outlive the test that caused it.
    """
    original = auditor.core.EXTRA_ROOT_NAMES
    yield
    auditor.core.EXTRA_ROOT_NAMES = original


@pytest.fixture(autouse=True)
def restore_never_accepted() -> collections.abc.Iterator[None]:
    """Put `NEVER_ACCEPTED` back after every test: the driver rebinds it for each run."""
    original = auditor.core.NEVER_ACCEPTED
    yield
    auditor.core.NEVER_ACCEPTED = original


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
        auditor.core.EMITTED.clear()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            check(root, (root / src_root) if src_root else (root / 'src' / package))
        return [json.loads(line) for line in buffer.getvalue().splitlines()]

    return run
