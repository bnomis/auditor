"""Tests for the checks of the `callback-hotpath-io` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

CALLBACK_IO = auditor.testing.load_check(__file__)


def test_a_callback_that_opens_a_file_per_event_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib


            class Reporter(TrainerCallback):
                def __init__(self, root: pathlib.Path) -> None:
                    self.root = root

                def on_log(self, args: object, state: object, control: object) -> None:
                    self.root.mkdir(parents=True, exist_ok=True)
            """
        }
    )
    hits = run_check(CALLBACK_IO, root)
    assert [hit['rule'] for hit in hits] == ['callback-hotpath-io']
    assert 'Reporter.on_log' in hits[0]['variant']


def test_the_same_setup_in_the_constructor_is_not_a_callback_hit(project: Builder, run_check: Runner) -> None:
    """This is the documented winner of the A18 / constructor-disk-io conflict."""
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib


            class Reporter(TrainerCallback):
                def __init__(self, root: pathlib.Path) -> None:
                    root.mkdir(parents=True, exist_ok=True)
                    self.root = root

                def on_log(self, args: object, state: object, control: object) -> None:
                    return None
            """
        }
    )
    assert run_check(CALLBACK_IO, root) == []
