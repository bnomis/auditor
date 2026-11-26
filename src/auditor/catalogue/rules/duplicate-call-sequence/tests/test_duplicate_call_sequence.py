"""Tests for the `duplicate-call-sequence` check."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

CALL_SEQUENCE = auditor.testing.load_check(__file__)


# --------------------------------------------------------------------------
# check_duplicate_call_sequence
# --------------------------------------------------------------------------


CALL_CHAIN = """
import probe.helper


def {name}(value: str) -> str:
    probe.helper.alpha(value)
    probe.helper.bravo(value)
    probe.helper.charlie(value)
    probe.helper.delta(value)
    probe.helper.echo(value)
    probe.helper.foxtrot(value)
    probe.helper.golf(value)
    return value
"""


def test_two_functions_with_the_same_call_skeleton_are_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': CALL_CHAIN.format(name='run_first'),
            'src/probe/b.py': CALL_CHAIN.format(name='run_second'),
        }
    )
    hits = run_check(CALL_SEQUENCE, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('duplicate-call-sequence', 'src/probe/a.py')]
    assert 'run_second' in hits[0]['variant']
    assert hits[0]['related'] == ['src/probe/b.py']


PLUMBING_CHAIN = """
import probe.helper
import sqlite3


def {name}(value: str) -> str:
    probe.helper.alpha(value)
    conn = sqlite3.connect(value)
    conn.execute(value)
    conn.fetchall(value)
    conn.close(value)
    probe.helper.{tail}(value)
    return value
"""


def test_a_sequence_that_is_mostly_connection_plumbing_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """connect/execute/close describe the framework, not the shape of the code.

    Two unrelated database tests both open a connection, run a statement and
    close it. Counting those made them look like copies of each other, which
    matters most in a codebase that forbids `from X import Y`: every call is
    dotted there, so nothing filtered them out.
    """
    root = project(
        {
            'src/probe/a.py': PLUMBING_CHAIN.format(name='run_first', tail='bravo'),
            'src/probe/b.py': PLUMBING_CHAIN.format(name='run_second', tail='charlie'),
        }
    )
    assert run_check(CALL_SEQUENCE, root) == []


def test_a_short_call_sequence_is_below_the_threshold(project: Builder, run_check: Runner) -> None:
    short = 'import probe.helper\n\n\ndef {name}(value: str) -> str:\n    probe.helper.alpha(value)\n    probe.helper.bravo(value)\n    return value\n'
    root = project({'src/probe/a.py': short.format(name='run_first'), 'src/probe/b.py': short.format(name='run_second')})
    assert run_check(CALL_SEQUENCE, root) == []


def test_two_copies_in_one_file_are_treated_as_a_family(project: Builder, run_check: Runner) -> None:
    """Within-file repetition is usually a deliberate family of similar
    functions; cross-file repetition is the architectural smell."""
    root = project({'src/probe/a.py': CALL_CHAIN.format(name='run_first') + CALL_CHAIN.format(name='run_second')})
    assert run_check(CALL_SEQUENCE, root) == []
