"""Tests for the checks of the `silent-self-mutation` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

SELF_MUTATION = auditor.testing.load_check(__file__)


def test_a_stage_method_that_reassigns_owned_state_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Pipeline:
                def __init__(self, config: dict) -> None:
                    self.config = config

                def tokenize(self, patched: dict) -> None:
                    self.config = patched
            """
        }
    )
    hits = run_check(SELF_MUTATION, root)
    assert [(hit['rule'], hit['variant']) for hit in hits] == [('silent-self-mutation', 'Pipeline.tokenize reassigns self.config')]


def test_a_method_named_for_mutation_may_mutate(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Pipeline:
                def __init__(self, config: dict) -> None:
                    self.config = config

                def update_config(self, patched: dict) -> None:
                    self.config = patched

                def set_config(self, patched: dict) -> None:
                    self.config = patched
            """
        }
    )
    assert run_check(SELF_MUTATION, root) == []


def test_reassigning_an_attribute_the_caller_never_supplied_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """The rule is about the caller's view of their own object drifting."""
    root = project(
        {
            'src/probe/mod.py': """
            class Pipeline:
                def __init__(self, config: dict) -> None:
                    self.config = config
                    self.cache = {}

                def tokenize(self) -> None:
                    self.cache = {'a': 1}
            """
        }
    )
    assert run_check(SELF_MUTATION, root) == []
