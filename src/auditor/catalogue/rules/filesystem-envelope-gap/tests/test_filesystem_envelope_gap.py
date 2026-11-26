"""Tests for the checks of the `filesystem-envelope-gap` rule."""

import collections.abc
import pathlib

import pytest

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

FS_ENVELOPE_GAP = auditor.testing.load_check(__file__)


def test_a_narrow_catch_around_a_filesystem_call_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib
            import probe.errors


            def save(path: pathlib.Path, text: str) -> None:
                try:
                    path.write_text(text)
                except ValueError as exc:
                    raise probe.errors.ProbeError('save failed') from exc
            """
        }
    )
    hits = run_check(FS_ENVELOPE_GAP, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('filesystem-envelope-gap', 8)]
    assert 'omits OSError' in hits[0]['variant']


def test_catching_oserror_closes_the_gap(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib
            import probe.errors


            def save(path: pathlib.Path, text: str) -> None:
                try:
                    path.write_text(text)
                except (OSError, ValueError) as exc:
                    raise probe.errors.ProbeError('save failed') from exc
            """
        }
    )
    assert run_check(FS_ENVELOPE_GAP, root) == []


def envelope_module(prelude: str, handler: str) -> dict[str, str]:
    prelude = prelude.replace('\n', '\n            ')
    body = f"""
            import pathlib
            import probe.errors
            import probe.other

            {prelude}


            def save(path: pathlib.Path, text: str) -> None:
                try:
                    path.write_text(text)
                except {handler} as exc:
                    raise probe.errors.ProbeError('save failed') from exc
            """
    return {'src/probe/mod.py': body}


@pytest.mark.parametrize('handler', ['READ_ERRORS', '(READ_ERRORS, KeyError)'])
def test_a_module_tuple_constant_holding_oserror_closes_the_gap(project: Builder, run_check: Runner, handler: str) -> None:
    """`except READ_ERRORS:` catches what the module-level tuple holds."""
    root = project(envelope_module('READ_ERRORS = (OSError, ValueError)', handler))
    assert run_check(FS_ENVELOPE_GAP, root) == []


@pytest.mark.parametrize(
    ('prelude', 'handler'),
    [
        ('READ_ERRORS = (KeyError, ValueError)', 'READ_ERRORS'),
        ('READ_ERRORS = (OSError, ValueError)', 'probe.other.READ_ERRORS'),
        ('READ_ERRORS = (OSError,)\nREAD_ERRORS = (ValueError,)', 'READ_ERRORS'),
        ('READ_ERRORS = make_errors()', 'READ_ERRORS'),
        ('INNER = (OSError,)\nREAD_ERRORS = (INNER, ValueError)', 'READ_ERRORS'),
    ],
    ids=['no-oserror-member', 'another-modules-name', 'assigned-twice', 'not-a-tuple-literal', 'two-levels-deep'],
)
def test_a_name_that_does_not_resolve_to_oserror_is_still_a_hit(project: Builder, run_check: Runner, prelude: str, handler: str) -> None:
    root = project(envelope_module(prelude, handler))
    assert [hit['rule'] for hit in run_check(FS_ENVELOPE_GAP, root)] == ['filesystem-envelope-gap']


def test_a_tuple_constant_inside_a_function_is_not_resolved(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib
            import probe.errors


            def save(path: pathlib.Path, text: str) -> None:
                READ_ERRORS = (OSError, ValueError)
                try:
                    path.write_text(text)
                except READ_ERRORS as exc:
                    raise probe.errors.ProbeError('save failed') from exc
            """
        }
    )
    assert [hit['rule'] for hit in run_check(FS_ENVELOPE_GAP, root)] == ['filesystem-envelope-gap']


def test_a_try_block_that_touches_no_filesystem_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def add(a: int, b: int) -> int:
                try:
                    return a + b
                except ValueError as exc:
                    raise probe.errors.ProbeError('add failed') from exc
            """
        }
    )
    assert run_check(FS_ENVELOPE_GAP, root) == []


def test_a_handler_that_skips_the_file_is_not_a_gap(project: Builder, run_check: Runner) -> None:
    """A handler that continues, returns or logs promises no translation."""
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib


            def scan(paths: list[pathlib.Path]) -> list[str]:
                found = []
                for path in paths:
                    try:
                        found.append(path.read_text())
                    except UnicodeDecodeError:
                        continue
                return found
            """
        }
    )
    assert run_check(FS_ENVELOPE_GAP, root) == []


def test_a_bare_reraise_is_not_a_translation(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib


            def save(path: pathlib.Path, text: str) -> None:
                try:
                    path.write_text(text)
                except ValueError:
                    raise
            """
        }
    )
    assert run_check(FS_ENVELOPE_GAP, root) == []
