"""Tests for the checks of the `except-interpolation` rule."""

import collections.abc
import pathlib

import hypothesis
import hypothesis.strategies

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

INTERPOLATION = auditor.testing.load_check(__file__)
CHECK_MODULE = auditor.testing.load_check_module(__file__)
IDENTIFIER = hypothesis.strategies.from_regex(r'[A-Za-z_][A-Za-z0-9_]{0,8}', fullmatch=True)
SPACES = hypothesis.strategies.text(alphabet=' \t', max_size=3)


def test_interpolating_the_caught_exception_into_a_message_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def run() -> None:
                try:
                    probe.core.risky()
                except ValueError as exc:
                    raise probe.core.ProbeError(f'could not run: {exc}') from exc
            """
        }
    )
    hits = run_check(INTERPOLATION, root)
    assert [(hit['rule'], hit['variant']) for hit in hits] == [('except-interpolation', 'f-string interpolates caught exception')]


def test_passing_the_exception_as_a_logger_positional_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import loguru
            import probe.core


            def run() -> None:
                try:
                    probe.core.risky()
                except ValueError as exc:
                    loguru.logger.error(exc)
            """
        }
    )
    hits = run_check(INTERPOLATION, root)
    assert [hit['variant'] for hit in hits] == ['logger positional arg is caught exception']


def test_the_class_name_of_the_exception_is_a_categorical_hint(project: Builder, run_check: Runner) -> None:
    """Documented refinement: `type(exc).__name__` exposes the class
    string, not a lossy copy of the message body."""
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def run() -> None:
                try:
                    probe.core.risky()
                except ValueError as exc:
                    raise probe.core.ProbeError(f'could not run: {type(exc).__name__}') from exc
            """
        }
    )
    assert run_check(INTERPOLATION, root) == []


def test_the_dunder_class_qualname_form_is_also_categorical(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def run() -> None:
                try:
                    probe.core.risky()
                except ValueError as exc:
                    raise probe.core.ProbeError(f'could not run: {exc.__class__.__qualname__}') from exc
            """
        }
    )
    assert run_check(INTERPOLATION, root) == []


def test_an_unbound_handler_has_nothing_to_interpolate(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def run() -> None:
                try:
                    probe.core.risky()
                except ValueError:
                    raise probe.core.ProbeError('could not run')
            """
        }
    )
    assert run_check(INTERPOLATION, root) == []


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    bound=IDENTIFIER,
    pad=SPACES,
    attr=hypothesis.strategies.sampled_from(CHECK_MODULE.SAFE_ATTRS),
    suffix=hypothesis.strategies.text(min_size=1, max_size=5),
)
def test_categorical_class_name_expr_accepts_the_class_name_forms_only(bound: str, pad: str, attr: str, suffix: str) -> None:
    check = CHECK_MODULE.is_categorical_class_name_expr
    forms = [f'type({pad}{bound}{pad}).{attr}', f'{bound}.__class__.{attr}']
    for form in forms:
        assert check(f'{pad}{form}{pad}', bound)
        assert not check(form + suffix.strip() + 'x', bound)
