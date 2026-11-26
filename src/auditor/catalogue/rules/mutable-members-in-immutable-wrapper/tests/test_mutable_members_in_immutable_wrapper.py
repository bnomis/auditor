"""Tests for the checks of the `mutable-members-in-immutable-wrapper` rule."""

import collections.abc
import pathlib

import hypothesis
import hypothesis.strategies

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

WRAPPER_MEMBERS = auditor.testing.load_check(__file__)


def test_a_proxy_over_mutable_values_is_a_hit(project: Builder, run_check: Runner) -> None:
    """`MappingProxyType` freezes the mapping and nothing inside it."""
    root = project(
        {
            'src/probe/settings.py': "import types\n\nDEFAULTS = types.MappingProxyType({'a': [], 'b': 1})\n",
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    hits = run_check(WRAPPER_MEMBERS, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('mutable-members-in-immutable-wrapper', 3)]
    assert 'a list literal at line 3' in hits[0]['variant']


def test_a_proxy_over_a_non_frozen_dataclass_is_a_hit(project: Builder, run_check: Runner) -> None:
    """A dataclass states its own mutability, in this corpus, on its decorator."""
    root = project(
        {
            'src/probe/model.py': """
            import dataclasses


            @dataclasses.dataclass
            class Setting:
                default: list[str]
            """,
            'src/probe/settings.py': """
            import types

            import probe.model

            SETTINGS = types.MappingProxyType({'a': probe.model.Setting(default=[])})
            """,
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.SETTINGS\n',
        }
    )
    hits = run_check(WRAPPER_MEMBERS, root)
    assert len(hits) == 1
    assert 'non-frozen dataclass `Setting`' in hits[0]['variant']


def test_a_proxy_over_a_frozen_dataclass_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/model.py': """
            import dataclasses


            @dataclasses.dataclass(frozen=True)
            class Setting:
                default: str
            """,
            'src/probe/settings.py': """
            import types

            import probe.model

            SETTINGS = types.MappingProxyType({'a': probe.model.Setting(default='x')})
            """,
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.SETTINGS\n',
        }
    )
    assert run_check(WRAPPER_MEMBERS, root) == []


def test_a_tuple_of_lists_is_a_hit(project: Builder, run_check: Runner) -> None:
    """A tuple is immutable and holds whatever it is given."""
    root = project(
        {
            'src/probe/settings.py': 'ROWS = tuple([[1], [2]])\n',
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.ROWS\n',
        }
    )
    hits = run_check(WRAPPER_MEMBERS, root)
    assert len(hits) == 1
    assert 'wrapped in tuple' in hits[0]['variant']


def test_a_mutable_member_one_tuple_deep_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/settings.py': "import types\n\nDEFAULTS = types.MappingProxyType({'a': ('name', {})})\n",
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    hits = run_check(WRAPPER_MEMBERS, root)
    assert len(hits) == 1
    assert 'a dict literal' in hits[0]['variant']


def test_a_proxy_over_immutable_values_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/settings.py': "import types\n\nDEFAULTS = types.MappingProxyType({'a': 1, 'b': ('x',)})\n",
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    assert run_check(WRAPPER_MEMBERS, root) == []


def test_a_wrapped_member_whose_type_is_a_call_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """The same non-goal as A20's `Call` case: the assignment states no type."""
    root = project(
        {
            'src/probe/settings.py': "import types\n\nimport probe.factory\n\nDEFAULTS = types.MappingProxyType({'a': probe.factory.build()})\n",
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    assert run_check(WRAPPER_MEMBERS, root) == []


def test_a_shallow_wrapper_nobody_reads_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """The predicate is "read elsewhere", exactly as it is for A20."""
    root = project({'src/probe/settings.py': "import types\n\nDEFAULTS = types.MappingProxyType({'a': []})\n"})
    assert run_check(WRAPPER_MEMBERS, root) == []


def test_a_scoped_accept_marker_dismisses_the_shallow_wrapper(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/settings.py': (
                'import types\n\n'
                "DEFAULTS = types.MappingProxyType({'a': []})  "
                '# auditme: accept[mutable-members-in-immutable-wrapper] values are never handed out\n'
            ),
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    hits = run_check(WRAPPER_MEMBERS, root)
    assert [(hit['accepted'], hit['accepted_reason']) for hit in hits] == [(True, 'values are never handed out')]


def test_a_marker_scoped_to_the_container_rule_does_not_dismiss_the_member_rule(project: Builder, run_check: Runner) -> None:
    """The two rules ask different questions, so they are accepted separately."""
    root = project(
        {
            'src/probe/settings.py': (
                "import types\n\nDEFAULTS = types.MappingProxyType({'a': []})  # auditme: accept[mutable-module-level-exported] wrapped already\n"
            ),
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    hits = run_check(WRAPPER_MEMBERS, root)
    assert [hit['accepted'] for hit in hits] == [False]


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    hazards=hypothesis.strategies.lists(
        hypothesis.strategies.tuples(hypothesis.strategies.integers(1, 9999), hypothesis.strategies.from_regex(r'[a-z ]{1,12}', fullmatch=True)), max_size=6
    )
)
def test_hazard_summary_has_one_located_entry_per_hazard(hazards: list[tuple[int, str]]) -> None:
    summary = auditor.testing.load_check_module(__file__).hazard_summary(hazards)
    if not hazards:
        assert summary == ''
        return
    parts = summary.split(', ')
    assert len(parts) == len(hazards)
    for part, hazard in zip(parts, hazards, strict=True):
        assert part.endswith(f' at line {hazard[0]}')
