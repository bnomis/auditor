"""Tests for the checks of the `pure-name-has-side-effect` rule."""

import collections.abc
import pathlib
import typing

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

PURE_NAME = auditor.testing.load_check(__file__)


def test_a_get_function_that_writes_to_disk_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib


            def get_run_dir(root: pathlib.Path) -> pathlib.Path:
                root.mkdir(parents=True, exist_ok=True)
                return root
            """
        }
    )
    hits = run_check(PURE_NAME, root)
    assert [hit['rule'] for hit in hits] == ['pure-name-has-side-effect']
    assert '`mkdir`' in hits[0]['variant']


def test_a_load_function_may_do_io(project: Builder, run_check: Runner) -> None:
    """`load_*` names promise IO; the rule is about names that do not."""
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib


            def load_run_dir(root: pathlib.Path) -> pathlib.Path:
                root.mkdir(parents=True, exist_ok=True)
                return root
            """
        }
    )
    assert run_check(PURE_NAME, root) == []


def test_a_side_effect_inside_a_returned_closure_is_not_the_function_s_own(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import collections.abc
            import pathlib


            def get_preparer(root: pathlib.Path) -> collections.abc.Callable[[], None]:
                def prepare() -> None:
                    root.mkdir(parents=True, exist_ok=True)

                return prepare
            """
        }
    )
    assert run_check(PURE_NAME, root) == []


def pure_name_hits(project: Builder, run_check: Runner, files: dict[str, str]) -> list[dict[str, typing.Any]]:
    return run_check(PURE_NAME, project(files))


def test_a_get_function_that_reads_a_file_is_a_hit(project: Builder, run_check: Runner) -> None:
    hits = pure_name_hits(
        project,
        run_check,
        {
            'src/probe/mod.py': """
            import pathlib


            def get_text(path: pathlib.Path) -> str:
                return path.read_text()
            """
        },
    )
    assert [hit['rule'] for hit in hits] == ['pure-name-has-side-effect']
    assert '`read_text`' in hits[0]['variant']


def test_a_get_function_that_runs_a_subprocess_is_a_hit(project: Builder, run_check: Runner) -> None:
    hits = pure_name_hits(
        project,
        run_check,
        {
            'src/probe/mod.py': """
            import subprocess


            def get_version() -> str:
                return subprocess.run(['probe', '--version'], check=True).stdout
            """
        },
    )
    assert [hit['rule'] for hit in hits] == ['pure-name-has-side-effect']


def test_a_get_function_that_tests_existence_is_a_hit(project: Builder, run_check: Runner) -> None:
    hits = pure_name_hits(
        project,
        run_check,
        {
            'src/probe/mod.py': """
            import pathlib


            def get_found(path: pathlib.Path) -> bool:
                return path.exists()
            """
        },
    )
    assert [hit['rule'] for hit in hits] == ['pure-name-has-side-effect']


def test_a_get_function_that_only_normalises_a_path_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    hits = pure_name_hits(
        project,
        run_check,
        {
            'src/probe/mod.py': """
            import pathlib


            def get_full(path: pathlib.Path) -> pathlib.Path:
                return path.resolve()
            """
        },
    )
    assert hits == []


def test_a_run_method_that_is_not_a_subprocess_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    hits = pure_name_hits(
        project,
        run_check,
        {
            'src/probe/mod.py': """
            def get_result(job: object) -> object:
                return job.run()
            """
        },
    )
    assert hits == []


CHECK_READING_A_FILE = """
import pathlib


def check_x(path: pathlib.Path) -> str:
    return path.read_text()
"""


def test_a_check_named_in_a_module_level_tuple_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    hits = pure_name_hits(
        project,
        run_check,
        {
            'src/probe/checks.py': CHECK_READING_A_FILE,
            'src/probe/registry.py': """
            import probe.checks

            CHECKS = (probe.checks.check_x,)
            """,
        },
    )
    assert hits == []


def test_a_check_named_in_a_dict_value_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    hits = pure_name_hits(
        project,
        run_check,
        {
            'src/probe/checks.py': CHECK_READING_A_FILE,
            'src/probe/registry.py': """
            from probe.checks import check_x

            CHECKS = {'x': check_x}
            """,
        },
    )
    assert hits == []


def test_a_check_decorated_by_a_package_function_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    hits = pure_name_hits(
        project,
        run_check,
        {
            'src/probe/registry.py': """
            import collections.abc


            def register(func: collections.abc.Callable[..., str]) -> collections.abc.Callable[..., str]:
                return func
            """,
            'src/probe/checks.py': """
            import pathlib

            import probe.registry


            @probe.registry.register
            def check_x(path: pathlib.Path) -> str:
                return path.read_text()
            """,
        },
    )
    assert hits == []


def test_an_unregistered_check_that_reads_a_file_is_a_hit(project: Builder, run_check: Runner) -> None:
    hits = pure_name_hits(project, run_check, {'src/probe/checks.py': CHECK_READING_A_FILE})
    assert [hit['rule'] for hit in hits] == ['pure-name-has-side-effect']
