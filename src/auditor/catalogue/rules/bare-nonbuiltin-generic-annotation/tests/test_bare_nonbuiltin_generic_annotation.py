"""Tests for the checks of the `bare-nonbuiltin-generic-annotation` rule."""

import collections.abc
import pathlib
import typing

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

BARE_NONBUILTIN = auditor.testing.load_check(__file__)


def rules_found(hits: list[dict[str, typing.Any]]) -> set[str]:
    return {hit['rule'] for hit in hits}


# --------------------------------------------------------------------------
# check_bare_nonbuiltin_generic_annotation
# --------------------------------------------------------------------------


def test_a_bare_dotted_generic_annotation_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import multiprocessing\n\n\ndef f(q: multiprocessing.Queue) -> None:\n    return None\n'})
    hits = run_check(BARE_NONBUILTIN, root)
    assert [hit['rule'] for hit in hits] == ['bare-nonbuiltin-generic-annotation']
    assert 'multiprocessing.Queue' in hits[0]['variant']


def test_an_imported_alias_resolves_to_its_full_name(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'from queue import Queue\n\n\ndef f(q: Queue) -> None:\n    return None\n'})
    hits = run_check(BARE_NONBUILTIN, root)
    assert len(hits) == 1
    assert 'queue.Queue' in hits[0]['variant']


def test_a_parametric_non_builtin_annotation_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import multiprocessing\n\n\ndef f(q: multiprocessing.Queue[int]) -> None:\n    return None\n'})
    assert run_check(BARE_NONBUILTIN, root) == []


def test_a_builtin_generic_is_left_to_the_other_check(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'def f(values: dict) -> None:\n    return None\n'})
    assert run_check(BARE_NONBUILTIN, root) == []
