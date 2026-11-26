"""Tests for the checks of the `parameter-mutation-in-pure-function` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

PARAM_MUTATION = auditor.testing.load_check(__file__)


def test_a_validator_that_writes_into_its_argument_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def validate_config(config: dict) -> bool:
                config['checked'] = True
                return True
            """
        }
    )
    hits = run_check(PARAM_MUTATION, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('parameter-mutation-in-pure-function', 2)]
    assert 'item assignment' in hits[0]['variant']


def test_a_validator_that_calls_a_mutating_method_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def check_config(config: dict, extra: dict) -> bool:
                config.update(extra)
                return True
            """
        }
    )
    hits = run_check(PARAM_MUTATION, root)
    assert len(hits) == 1
    assert '.update()' in hits[0]['variant']


def test_a_function_that_advertises_mutation_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def apply_config(config: dict) -> bool:
                config['checked'] = True
                return True
            """
        }
    )
    assert run_check(PARAM_MUTATION, root) == []


def test_a_validator_that_mutates_a_local_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def validate_config(config: dict) -> dict:
                copied = dict(config)
                copied['checked'] = True
                return copied
            """
        }
    )
    assert run_check(PARAM_MUTATION, root) == []
