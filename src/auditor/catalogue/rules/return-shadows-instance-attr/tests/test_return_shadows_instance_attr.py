"""Tests for the checks of the `return-shadows-instance-attr` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

RETURN_SHADOWS = auditor.testing.load_check(__file__)


def test_returning_a_divergent_copy_of_owned_state_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Pipeline:
                def __init__(self, config: dict) -> None:
                    self.config = config

                def tokenize(self) -> dict:
                    patched_config = self.config.copy()
                    patched_config['tokenized'] = True
                    return patched_config
            """
        }
    )
    hits = run_check(RETURN_SHADOWS, root)
    assert [hit['rule'] for hit in hits] == ['return-shadows-instance-attr']
    assert 'callers must reassign' in hits[0]['variant']


def test_a_local_that_is_not_derived_from_the_attribute_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Pipeline:
                def __init__(self, config: dict) -> None:
                    self.config = config

                def tokenize(self) -> dict:
                    patched_config = {'fresh': True}
                    return patched_config
            """
        }
    )
    assert run_check(RETURN_SHADOWS, root) == []
