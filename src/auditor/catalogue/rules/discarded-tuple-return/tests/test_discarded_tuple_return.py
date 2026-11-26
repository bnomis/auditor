"""Tests for the checks of the `discarded-tuple-return` rule."""

import collections.abc
import pathlib

import pytest

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

DISCARDED_TUPLE = auditor.testing.load_check(__file__)


TUPLE_CALLEE = """
def f(x: int) -> tuple[int, str]:
    return x, 'a'


def h(x: int) -> tuple[int, ...]:
    return (x,)
"""


def test_a_discarded_tuple_return_from_another_module_is_a_hit_with_related(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/callee.py': TUPLE_CALLEE,
            'src/probe/caller.py': """
            import probe.callee


            def run(x: int) -> None:
                probe.callee.f(x)
            """,
        }
    )
    hits = run_check(DISCARDED_TUPLE, root)
    assert [(hit['rule'], hit['path'], hit['line']) for hit in hits] == [('discarded-tuple-return', 'src/probe/caller.py', 5)]
    assert hits[0]['variant'] == 'probe.callee.f returns tuple[...]; the result is discarded'
    assert hits[0]['related'] == ['src/probe/callee.py']


def test_a_discarded_awaited_tuple_return_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            async def g() -> tuple[int, str]:
                return 1, 'a'


            async def run() -> None:
                await g()
            """
        }
    )
    hits = run_check(DISCARDED_TUPLE, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('discarded-tuple-return', 6)]
    assert 'related' not in hits[0]


@pytest.mark.parametrize(
    'statement',
    ['_ = f(x)', 'a, _ = f(x)', 'h(x)', 'unknown(x)', 'value = f(x)'],
    ids=['named-discard', 'unpacked', 'variadic-tuple', 'unresolved', 'bound'],
)
def test_a_used_or_unprovable_tuple_call_is_not_a_hit(project: Builder, run_check: Runner, statement: str) -> None:
    source = TUPLE_CALLEE + f'\n\ndef run(x: int) -> None:\n    {statement}\n'
    root = project({'src/probe/mod.py': source})
    assert run_check(DISCARDED_TUPLE, root) == []
