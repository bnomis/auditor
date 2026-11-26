"""Tests for the checks of the `assert-never-missing` rule."""

import collections.abc
import pathlib
import typing

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

ASSERT_NEVER = auditor.testing.load_check(__file__)


def test_a_three_arm_string_dispatch_without_an_else_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def score(kind: str) -> int:
                if kind == 'alpha':
                    return 1
                elif kind == 'beta':
                    return 2
                elif kind == 'gamma':
                    return 3
                return 0
            """
        }
    )
    hits = run_check(ASSERT_NEVER, root)
    assert [hit['rule'] for hit in hits] == ['assert-never-missing']
    assert 'has no else' in hits[0]['variant']


def test_a_chain_that_ends_in_assert_never_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import typing


            def score(kind: str) -> int:
                if kind == 'alpha':
                    return 1
                elif kind == 'beta':
                    return 2
                elif kind == 'gamma':
                    return 3
                else:
                    typing.assert_never(kind)
            """
        }
    )
    assert run_check(ASSERT_NEVER, root) == []


def test_a_two_arm_chain_is_legitimately_bi_valued(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def score(kind: str) -> int:
                if kind == 'alpha':
                    return 1
                elif kind == 'beta':
                    return 2
                return 0
            """
        }
    )
    assert run_check(ASSERT_NEVER, root) == []


def assert_never_hits(project: Builder, run_check: Runner, body: str) -> list[dict[str, typing.Any]]:
    return run_check(ASSERT_NEVER, project({'src/probe/mod.py': body}))


def test_a_three_arm_chain_on_a_dotted_subject_is_a_hit(project: Builder, run_check: Runner) -> None:
    hits = assert_never_hits(
        project,
        run_check,
        """
        class Probe:
            def score(self) -> int:
                if self.kind == 'alpha':
                    return 1
                elif self.kind == 'beta':
                    return 2
                elif self.kind == 'gamma':
                    return 3
                return 0
        """,
    )
    assert [hit['rule'] for hit in hits] == ['assert-never-missing']
    assert 'self.kind' in hits[0]['variant']


def test_an_in_arm_counts_as_an_arm(project: Builder, run_check: Runner) -> None:
    hits = assert_never_hits(
        project,
        run_check,
        """
        def score(kind: str) -> int:
            if kind in ('alpha', 'beta'):
                return 1
            elif kind == 'gamma':
                return 2
            elif 'delta' == kind:
                return 3
            return 0
        """,
    )
    assert [hit['rule'] for hit in hits] == ['assert-never-missing']


def test_a_two_arm_chain_on_a_three_member_literal_is_a_hit(project: Builder, run_check: Runner) -> None:
    hits = assert_never_hits(
        project,
        run_check,
        """
        import typing


        def score(kind: typing.Literal['a', 'b', 'c']) -> int:
            if kind == 'a':
                return 1
            elif kind == 'b':
                return 2
            return 0
        """,
    )
    assert [hit['rule'] for hit in hits] == ['assert-never-missing']


def test_a_two_arm_chain_on_a_two_member_literal_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    hits = assert_never_hits(
        project,
        run_check,
        """
        import typing


        def score(kind: typing.Literal['a', 'b']) -> int:
            if kind == 'a':
                return 1
            elif kind == 'b':
                return 2
            return 0
        """,
    )
    assert hits == []


def test_a_two_arm_chain_on_a_local_literal_annotation_is_a_hit(project: Builder, run_check: Runner) -> None:
    hits = assert_never_hits(
        project,
        run_check,
        """
        import typing


        def score(raw: str) -> int:
            kind: typing.Literal['a', 'b', 'c'] = raw
            if kind == 'a':
                return 1
            elif kind == 'b':
                return 2
            return 0
        """,
    )
    assert [hit['rule'] for hit in hits] == ['assert-never-missing']


MATCH_BODY = """
import typing


def score(kind: str) -> int:
    match kind:
        case 'a':
            return 1
        case 'b' | 'c':
            return 2
        case 'd':
            return 3
        {tail}
"""


def test_a_three_case_match_is_a_hit(project: Builder, run_check: Runner) -> None:
    hits = assert_never_hits(project, run_check, MATCH_BODY.format(tail='case _:\n            return 0'))
    assert [hit['rule'] for hit in hits] == ['assert-never-missing']


def test_a_match_ending_in_assert_never_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    hits = assert_never_hits(project, run_check, MATCH_BODY.format(tail='case _:\n            typing.assert_never(kind)'))
    assert hits == []
