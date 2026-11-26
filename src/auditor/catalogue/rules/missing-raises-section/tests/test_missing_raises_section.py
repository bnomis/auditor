"""Tests for the checks of the `missing-raises-section` rule."""

import collections.abc
import pathlib

import pytest

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

CATCHING_HANDLERS = ['except Exception:', 'except probe.errors.ParseError:', 'except probe.errors.ProbeError:', 'except:']
MISSING_RAISES = auditor.testing.load_check(__file__)


def test_raising_a_project_error_with_no_raises_section_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def load(label: str) -> int:
                \"\"\"Load the thing.\"\"\"
                raise probe.errors.AlphaError('unknown')
            """
        }
    )
    hits = run_check(MISSING_RAISES, root)
    assert [hit['rule'] for hit in hits] == ['missing-raises-section']


def test_a_documented_raises_section_satisfies_the_rule(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def load(label: str) -> int:
                \"\"\"Load the thing.

                Raises:
                    AlphaError: when the label is unknown.
                \"\"\"
                raise probe.errors.AlphaError('unknown')
            """
        }
    )
    assert run_check(MISSING_RAISES, root) == []


def test_a_stdlib_raise_is_the_other_check_s_business(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'def load(label: str) -> int:\n    """Load the thing."""\n    raise ValueError(\'unknown\')\n'})
    assert run_check(MISSING_RAISES, root) == []


def test_an_undocumented_function_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    """The rule is about docstrings that are incomplete, not absent."""
    root = project({'src/probe/mod.py': "import probe.errors\n\n\ndef load(label: str) -> int:\n    raise probe.errors.AlphaError('unknown')\n"})
    assert run_check(MISSING_RAISES, root) == []


CAUGHT_ERRORS = 'class ProbeError(Exception):\n    pass\n\n\nclass ParseError(ProbeError):\n    pass\n\n\nclass FetchError(ProbeError):\n    pass\n'


def make_caught_module(body: str) -> dict[str, str]:
    return {'src/probe/errors.py': CAUGHT_ERRORS, 'src/probe/mod.py': 'import probe.errors\n\n\n' + body}


@pytest.mark.parametrize('handler', CATCHING_HANDLERS)
def test_a_raise_caught_by_a_handler_around_it_is_not_a_hit(project: Builder, run_check: Runner, handler: str) -> None:
    root = project(
        make_caught_module(
            f'def load(label: str) -> int:\n    """Load the thing."""\n    try:\n        raise probe.errors.ParseError(label)\n    {handler}\n        return 0\n'
        )
    )
    assert run_check(MISSING_RAISES, root) == []


@pytest.mark.parametrize('handler', CATCHING_HANDLERS)
def test_a_nested_raise_called_inside_a_catching_try_is_not_a_hit(project: Builder, run_check: Runner, handler: str) -> None:
    root = project(
        make_caught_module(
            'def load(label: str) -> int:\n'
            '    """Load the thing."""\n'
            '    def inner() -> int:\n'
            '        raise probe.errors.ParseError(label)\n'
            '    try:\n'
            '        return inner()\n'
            f'    {handler}\n'
            '        return 0\n'
        )
    )
    assert run_check(MISSING_RAISES, root) == []


def test_a_nested_raise_never_called_in_the_subject_is_not_the_subjects_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        make_caught_module(
            'def load(label: str):\n    """Load the thing."""\n    def inner() -> int:\n        raise probe.errors.ParseError(label)\n    return inner\n'
        )
    )
    assert run_check(MISSING_RAISES, root) == []


def test_a_documented_nested_def_is_still_its_own_subject(project: Builder, run_check: Runner) -> None:
    root = project(
        make_caught_module(
            'def load(label: str):\n'
            '    """Load the thing."""\n'
            '    def inner() -> int:\n'
            '        """Inner."""\n'
            '        raise probe.errors.ParseError(label)\n'
            '    return inner\n'
        )
    )
    assert [(hit['rule'], hit['line']) for hit in run_check(MISSING_RAISES, root)] == [('missing-raises-section', 6)]


@pytest.mark.parametrize(
    'handler',
    ['except probe.errors.ParseError:\n        raise', 'except probe.errors.FetchError:\n        return 0'],
    ids=['re-raises', 'unrelated-class'],
)
def test_a_raise_a_handler_does_not_stop_is_still_a_hit(project: Builder, run_check: Runner, handler: str) -> None:
    root = project(
        make_caught_module(f'def load(label: str) -> int:\n    """Load the thing."""\n    try:\n        raise probe.errors.ParseError(label)\n    {handler}\n')
    )
    assert [hit['rule'] for hit in run_check(MISSING_RAISES, root)] == ['missing-raises-section']


def test_a_nested_raise_called_outside_any_try_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        make_caught_module(
            'def load(label: str) -> int:\n'
            '    """Load the thing."""\n'
            '    def inner() -> int:\n'
            '        raise probe.errors.ParseError(label)\n'
            '    return inner()\n'
        )
    )
    assert [hit['rule'] for hit in run_check(MISSING_RAISES, root)] == ['missing-raises-section']
