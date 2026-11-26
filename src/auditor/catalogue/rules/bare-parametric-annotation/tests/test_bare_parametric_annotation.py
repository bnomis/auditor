"""Tests for the checks of the `bare-parametric-annotation` rule."""

import collections.abc
import pathlib
import typing

import pytest

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

BARE_PARAMETRIC = auditor.testing.load_check(__file__)


def rules_found(hits: list[dict[str, typing.Any]]) -> set[str]:
    return {hit['rule'] for hit in hits}


# --------------------------------------------------------------------------
# check_bare_parametric_annotation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    'source',
    [
        pytest.param('def f(values: dict) -> None:\n    return None\n', id='parameter'),
        pytest.param('def f() -> list:\n    return []\n', id='return'),
        pytest.param('VALUES: dict = {}\n', id='module-level'),
        pytest.param('def f(values: dict | None) -> None:\n    return None\n', id='union-member'),
    ],
)
def test_a_bare_builtin_generic_annotation_is_a_hit(source: str, project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': source})
    hits = run_check(BARE_PARAMETRIC, root)
    assert [hit['rule'] for hit in hits] == ['bare-parametric-annotation']


def test_a_parametric_annotation_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'def f(values: dict[str, int]) -> list[str]:\n    return []\n'})
    assert run_check(BARE_PARAMETRIC, root) == []


@pytest.mark.parametrize(
    'source',
    [
        pytest.param('def f(values: list[dict]) -> None:\n    return None\n', id='list-of-dict'),
        pytest.param('def f(values: dict[str, dict]) -> None:\n    return None\n', id='dict-value'),
        pytest.param('def f(values: list[list]) -> None:\n    return None\n', id='list-of-list'),
        pytest.param(
            'import typing\n\n\ndef f(values: typing.Annotated[list, "meta"]) -> None:\n    return None\n',
            id='annotated-first-argument',
        ),
    ],
)
def test_a_bare_generic_inside_a_subscript_is_a_hit(source: str, project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': source})
    hits = run_check(BARE_PARAMETRIC, root)
    assert [hit['rule'] for hit in hits] == ['bare-parametric-annotation']


@pytest.mark.parametrize(
    'source',
    [
        pytest.param('import typing\n\n\ndef f(mode: typing.Literal["dict"]) -> None:\n    return None\n', id='literal'),
        pytest.param('def f(values: "list[dict]") -> None:\n    return None\n', id='string-forward-reference'),
        pytest.param(
            'import typing\n\n\ndef f(values: typing.Annotated[int, dict]) -> None:\n    return None\n',
            id='annotated-metadata',
        ),
    ],
)
def test_a_name_that_is_not_a_type_inside_a_subscript_is_not_a_hit(source: str, project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': source})
    assert run_check(BARE_PARAMETRIC, root) == []


def test_one_line_with_two_bare_annotations_reports_once(project: Builder, run_check: Runner) -> None:
    """`reported` is keyed by line, so a signature cannot report twice."""
    root = project({'src/probe/mod.py': 'def f(a: dict, b: list) -> None:\n    return None\n'})
    assert len(run_check(BARE_PARAMETRIC, root)) == 1
