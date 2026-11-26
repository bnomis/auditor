"""Tests for the checks of the `docstring-raises-mismatch` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

DOCSTRING_MISMATCH = auditor.testing.load_check(__file__)


def test_a_docstring_naming_the_wrong_exception_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def load(label: str) -> int:
                \"\"\"Load the thing.

                Raises:
                    AlphaError: when the label is unknown.
                \"\"\"
                raise probe.errors.BetaError('unknown')
            """
        }
    )
    hits = run_check(DOCSTRING_MISMATCH, root)
    assert [hit['rule'] for hit in hits] == ['docstring-raises-mismatch']
    assert "['BetaError']" in hits[0]['variant']


def test_a_docstring_that_matches_the_body_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def load(label: str) -> int:
                \"\"\"Load the thing.

                Raises:
                    AlphaError: when the label is unknown.
                \"\"\"
                raise probe.errors.AlphaError('unknown')
            """
        }
    )
    assert run_check(DOCSTRING_MISMATCH, root) == []


def test_a_raises_section_is_read_past_its_first_entry(project: Builder, run_check: Runner) -> None:
    """The raised class is documented second, after a wrapped first entry."""
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def load(label: str) -> int:
                \"\"\"Load the thing.

                Raises:
                    probe.errors.AlphaError: when the label is unknown, or
                        is empty.
                    probe.errors.BetaError: when the label repeats.
                \"\"\"
                raise probe.errors.BetaError('repeat')
            """
        }
    )
    assert run_check(DOCSTRING_MISMATCH, root) == []


def test_a_bulleted_raises_section_is_read_in_full(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def load(label: str) -> int:
                \"\"\"Load the thing.

                Raises:
                    - AlphaError: when the label is unknown.
                    - BetaError: when the label repeats.
                \"\"\"
                raise probe.errors.BetaError('repeat')
            """
        }
    )
    assert run_check(DOCSTRING_MISMATCH, root) == []


def test_a_class_named_after_the_raises_section_does_not_count(project: Builder, run_check: Runner) -> None:
    """The section ends at the first line back at its header's indent."""
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def load(label: str) -> int:
                \"\"\"Load the thing.

                Raises:
                    AlphaError: when the label is unknown.

                Note:
                    BetaError: is someone else's problem.
                \"\"\"
                raise probe.errors.BetaError('repeat')
            """
        }
    )
    assert [hit['rule'] for hit in run_check(DOCSTRING_MISMATCH, root)] == ['docstring-raises-mismatch']
