"""Tests for the checks of the `cli-entry-missing-error-envelope` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

CLI_ENVELOPE = auditor.testing.load_check(__file__)


def test_a_cli_entry_without_an_envelope_beside_one_with_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/cli/train.py': """
            import probe.core
            import probe.errors


            def run_train(label: str) -> int:
                try:
                    probe.core.train(label)
                except probe.errors.ProbeError:
                    return 1
                return 0
            """,
            'src/probe/cli/evaluate.py': """
            import probe.core


            def run_evaluate(label: str) -> int:
                probe.core.evaluate(label)
                return 0
            """,
        }
    )
    hits = run_check(CLI_ENVELOPE, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('cli-entry-missing-error-envelope', 'src/probe/cli/evaluate.py')]


def test_no_sibling_wraps_means_the_project_has_no_such_convention(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/cli/evaluate.py': 'import probe.core\n\n\ndef run_evaluate(label: str) -> int:\n    probe.core.evaluate(label)\n    return 0\n',
        }
    )
    assert run_check(CLI_ENVELOPE, root) == []


def test_a_project_with_no_cli_package_is_not_checked(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'def run_train(label: str) -> int:\n    return 0\n'})
    assert run_check(CLI_ENVELOPE, root) == []
