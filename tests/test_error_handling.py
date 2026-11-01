"""Tests for the exception-handling and error-reporting predicates.

`get-container-default-then-method-call` has its own module,
`test_get_container_default.py`.
"""

import ast
import collections.abc
import pathlib

import auditme.rules.error_handling
import pytest

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

SILENT_BROAD = auditme.rules.error_handling.check_silent_broad_except
INTERPOLATION = auditme.rules.error_handling.check_except_interpolation
WRONG_LEVEL = auditme.rules.error_handling.check_broad_except_wrong_level
MIXED_RAISE = auditme.rules.error_handling.check_mixed_raise_types
ASYMMETRIC = auditme.rules.error_handling.check_asymmetric_exception_translation
SIBLING_ERRORS = auditme.rules.error_handling.check_sibling_error_no_common_base
CLI_ENVELOPE = auditme.rules.error_handling.check_cli_entry_missing_error_envelope
TRY_WITH = auditme.rules.error_handling.check_try_wrapping_with_too_broad
STDLIB_RAISE = auditme.rules.error_handling.check_layer_has_domain_error_but_raises_stdlib
INCONSISTENT = auditme.rules.error_handling.check_inconsistent_error_translation
FS_ENVELOPE_GAP = auditme.rules.error_handling.check_filesystem_envelope_gap
FS_NO_ENVELOPE = auditme.rules.error_handling.check_filesystem_op_without_envelope
GRACEFUL = auditme.rules.error_handling.check_logger_exception_graceful_degradation
DOCSTRING_MISMATCH = auditme.rules.error_handling.check_docstring_raises_mismatch
MISSING_RAISES = auditme.rules.error_handling.check_missing_raises_section
RAISES_DRIFT = auditme.rules.error_handling.check_raises_section_drift
MIXED_EXCEPT = auditme.rules.error_handling.check_bare_except_in_module_with_narrow_errors
FAILURE_AS_ABSENCE = auditme.rules.error_handling.check_failure_as_absence
TRANSLATOR_GAP = auditme.rules.error_handling.check_translator_envelope_gap


# --------------------------------------------------------------------------
# check_silent_broad_except
# --------------------------------------------------------------------------


def test_a_broad_except_that_neither_logs_nor_raises_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def run() -> None:
                try:
                    probe.core.risky()
                except Exception:
                    pass
            """
        }
    )
    hits = run_check(SILENT_BROAD, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('silent-broad-except', 7)]


def test_a_broad_except_that_logs_is_not_silent(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import loguru
            import probe.core


            def run() -> None:
                try:
                    probe.core.risky()
                except Exception:
                    loguru.logger.exception('failed')
            """
        }
    )
    assert run_check(SILENT_BROAD, root) == []


def test_a_narrow_except_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def run() -> None:
                try:
                    probe.core.risky()
                except OSError:
                    pass
            """
        }
    )
    assert run_check(SILENT_BROAD, root) == []


# --------------------------------------------------------------------------
# check_except_interpolation
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# check_broad_except_wrong_level
# --------------------------------------------------------------------------


def test_a_broad_except_logging_at_warning_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import loguru
            import probe.core


            def run() -> None:
                try:
                    probe.core.risky()
                except Exception:
                    loguru.logger.warning('failed')
            """
        }
    )
    hits = run_check(WRONG_LEVEL, root)
    assert [hit['rule'] for hit in hits] == ['broad-except-wrong-level']


def test_a_broad_except_logging_at_exception_is_correct(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import loguru
            import probe.core


            def run() -> None:
                try:
                    probe.core.risky()
                except Exception:
                    loguru.logger.exception('failed')
            """
        }
    )
    assert run_check(WRONG_LEVEL, root) == []


# --------------------------------------------------------------------------
# check_mixed_raise_types
# --------------------------------------------------------------------------


def test_a_function_mixing_stdlib_and_project_errors_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def check(value: int) -> int:
                if value < 0:
                    raise ValueError('negative')
                if value > 10:
                    raise probe.errors.ProbeError('too large')
                return value
            """
        }
    )
    hits = run_check(MIXED_RAISE, root)
    assert [hit['rule'] for hit in hits] == ['mixed-raise-types']
    assert "['ValueError']" in hits[0]['variant']


def test_a_function_raising_only_project_errors_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def check(value: int) -> int:
                if value < 0:
                    raise probe.errors.RangeError('negative')
                if value > 10:
                    raise probe.errors.ProbeError('too large')
                return value
            """
        }
    )
    assert run_check(MIXED_RAISE, root) == []


# --------------------------------------------------------------------------
# check_asymmetric_exception_translation
# --------------------------------------------------------------------------


ASYMMETRIC_HELPER = 'def setup_experiment(name: str) -> int:\n    return len(name)\n'

WRAPPED_CALLER = """
import probe.errors
import probe.helper


def {name}(label: str) -> int:
    try:
        return probe.helper.setup_experiment(label)
    except Exception as exc:
        raise probe.errors.ProbeError('setup failed') from exc
"""


def test_a_helper_every_caller_wraps_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/helper.py': ASYMMETRIC_HELPER,
            'src/probe/a.py': WRAPPED_CALLER.format(name='run_a'),
            'src/probe/b.py': WRAPPED_CALLER.format(name='run_b'),
        }
    )
    hits = run_check(ASYMMETRIC, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('asymmetric-exception-translation', 'src/probe/helper.py')]
    assert 'all 2 callers wrap it' in hits[0]['variant']
    assert hits[0]['related'] == ['src/probe/a.py', 'src/probe/b.py']


def test_one_unwrapped_caller_makes_the_contract_symmetric_enough(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/helper.py': ASYMMETRIC_HELPER,
            'src/probe/a.py': WRAPPED_CALLER.format(name='run_a'),
            'src/probe/b.py': 'import probe.helper\n\n\ndef run_b(label: str) -> int:\n    return probe.helper.setup_experiment(label)\n',
        }
    )
    assert run_check(ASYMMETRIC, root) == []


def test_a_helper_that_holds_its_own_envelope_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/helper.py': """
            import probe.errors


            def setup_experiment(name: str) -> int:
                try:
                    return len(name)
                except Exception as exc:
                    raise probe.errors.ProbeError('setup failed') from exc
            """,
            'src/probe/a.py': WRAPPED_CALLER.format(name='run_a'),
            'src/probe/b.py': WRAPPED_CALLER.format(name='run_b'),
        }
    )
    assert run_check(ASYMMETRIC, root) == []


# --------------------------------------------------------------------------
# check_sibling_error_no_common_base
# --------------------------------------------------------------------------


def test_two_error_classes_with_no_shared_parent_are_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/errors.py': 'class AlphaError(Exception):\n    pass\n\n\nclass BetaError(Exception):\n    pass\n'})
    hits = run_check(SIBLING_ERRORS, root)
    assert [hit['rule'] for hit in hits] == ['sibling-errors-no-common-base']
    assert 'AlphaError' in hits[0]['evidence']


def test_a_real_hierarchy_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/errors.py': 'class ProbeError(Exception):\n    pass\n\n\nclass AlphaError(ProbeError):\n    pass\n'})
    assert run_check(SIBLING_ERRORS, root) == []


def test_a_module_that_is_not_errors_py_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'class AlphaError(Exception):\n    pass\n\n\nclass BetaError(Exception):\n    pass\n'})
    assert run_check(SIBLING_ERRORS, root) == []


# --------------------------------------------------------------------------
# check_cli_entry_missing_error_envelope
# --------------------------------------------------------------------------


def test_a_cli_entry_without_an_envelope_beside_one_with_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/cli/train.py': """
            import probe.core
            import probe.errors


            def run_train(label: str) -> int:
                try:
                    probe.core.train(label)
                except probe.errors.ProbeError:
                    return 1
                return 0
            """,
            'src/probe/cli/evaluate.py': """
            import probe.core


            def run_evaluate(label: str) -> int:
                probe.core.evaluate(label)
                return 0
            """,
        }
    )
    hits = run_check(CLI_ENVELOPE, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('cli-entry-missing-error-envelope', 'src/probe/cli/evaluate.py')]


def test_no_sibling_wraps_means_the_project_has_no_such_convention(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/cli/evaluate.py': 'import probe.core\n\n\ndef run_evaluate(label: str) -> int:\n    probe.core.evaluate(label)\n    return 0\n',
        }
    )
    assert run_check(CLI_ENVELOPE, root) == []


def test_a_project_with_no_cli_package_is_not_checked(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'def run_train(label: str) -> int:\n    return 0\n'})
    assert run_check(CLI_ENVELOPE, root) == []


# --------------------------------------------------------------------------
# check_try_wrapping_with_too_broad
# --------------------------------------------------------------------------


def test_a_handler_that_re_runs_the_wrapped_work_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import probe.errors


            def run_batch(config: dict) -> None:
                try:
                    with probe.core.open_batch_run(config):
                        probe.core.run_pipeline(config)
                except probe.errors.RegistryError:
                    probe.core.run_pipeline(config)
            """
        }
    )
    hits = run_check(TRY_WITH, root)
    assert [hit['rule'] for hit in hits] == ['try-wrapping-with-block-too-broad']
    assert 'run_pipeline' in hits[0]['variant']


def test_a_handler_that_only_reports_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import loguru
            import probe.core
            import probe.errors


            def run_batch(config: dict) -> None:
                try:
                    with probe.core.open_batch_run(config):
                        probe.core.run_pipeline(config)
                except probe.errors.RegistryError:
                    loguru.logger.exception('startup failed')
            """
        }
    )
    assert run_check(TRY_WITH, root) == []


# --------------------------------------------------------------------------
# check_layer_has_domain_error_but_raises_stdlib
# --------------------------------------------------------------------------


DOMAIN_ERRORS = 'class DataError(Exception):\n    pass\n'


def test_raising_stdlib_where_the_package_has_a_domain_error_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/data/errors.py': DOMAIN_ERRORS,
            'src/probe/data/loader.py': "def load(value: int) -> int:\n    if value < 0:\n        raise ValueError('negative')\n    return value\n",
        }
    )
    hits = run_check(STDLIB_RAISE, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('layer-has-domain-error-raises-stdlib', 3)]


def test_a_re_raise_inside_a_handler_is_the_narrowing_pattern(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/data/errors.py': DOMAIN_ERRORS,
            'src/probe/data/loader.py': """
            import probe.core


            def load(value: int) -> int:
                try:
                    return probe.core.parse(value)
                except TypeError:
                    raise ValueError('bad value')
            """,
        }
    )
    assert run_check(STDLIB_RAISE, root) == []


def test_a_package_with_no_errors_module_is_not_checked(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/data/loader.py': "def load(value: int) -> int:\n    raise ValueError('negative')\n"})
    assert run_check(STDLIB_RAISE, root) == []


# --------------------------------------------------------------------------
# check_inconsistent_error_translation
# --------------------------------------------------------------------------


TRANSLATING_CALLER = """
import probe.errors
import probe.helper


def {name}(label: str) -> int:
    try:
        return probe.helper.load(label)
    except LoadError:
        raise probe.errors.{target}('load failed')
"""


def test_a_domain_error_translated_two_ways_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/helper.py': "def load(label: str) -> int:\n    raise LoadError('nope')\n",
            'src/probe/a.py': TRANSLATING_CALLER.format(name='run_a', target='AlphaError'),
            'src/probe/b.py': TRANSLATING_CALLER.format(name='run_b', target='BetaError'),
        }
    )
    hits = run_check(INCONSISTENT, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('inconsistent-error-translation', 'src/probe/helper.py')]
    assert "['AlphaError', 'BetaError']" in hits[0]['variant']


def test_a_domain_error_translated_consistently_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/helper.py': "def load(label: str) -> int:\n    raise LoadError('nope')\n",
            'src/probe/a.py': TRANSLATING_CALLER.format(name='run_a', target='AlphaError'),
            'src/probe/b.py': TRANSLATING_CALLER.format(name='run_b', target='AlphaError'),
        }
    )
    assert run_check(INCONSISTENT, root) == []


# --------------------------------------------------------------------------
# check_filesystem_envelope_gap
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# check_filesystem_op_without_envelope
# --------------------------------------------------------------------------


def test_a_public_entry_point_writing_with_no_try_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/store/errors.py': 'class StoreError(Exception):\n    pass\n',
            'src/probe/store/writer.py': """
            import pathlib


            def save(path: pathlib.Path, text: str) -> None:
                \"\"\"Write the text.

                Raises:
                    StoreError: on failure.
                \"\"\"
                path.write_text(text)
            """,
        }
    )
    hits = run_check(FS_NO_ENVELOPE, root)
    assert [hit['rule'] for hit in hits] == ['filesystem-op-without-envelope']
    assert '`write_text`' in hits[0]['variant']


def test_the_same_write_inside_a_try_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/store/errors.py': 'class StoreError(Exception):\n    pass\n',
            'src/probe/store/writer.py': """
            import pathlib

            import probe.store.errors


            def save(path: pathlib.Path, text: str) -> None:
                \"\"\"Write the text.

                Raises:
                    StoreError: on failure.
                \"\"\"
                try:
                    path.write_text(text)
                except OSError as exc:
                    raise probe.store.errors.StoreError('save failed') from exc
            """,
        }
    )
    assert run_check(FS_NO_ENVELOPE, root) == []


def test_an_internal_helper_may_let_oserror_propagate(project: Builder, run_check: Runner) -> None:
    """Only functions on the package's public error contract are flagged."""
    root = project(
        {
            'src/probe/store/errors.py': 'class StoreError(Exception):\n    pass\n',
            'src/probe/store/writer.py': 'import pathlib\n\n\ndef save(path: pathlib.Path, text: str) -> None:\n    path.write_text(text)\n',
        }
    )
    assert run_check(FS_NO_ENVELOPE, root) == []


# --------------------------------------------------------------------------
# check_logger_exception_graceful_degradation
# --------------------------------------------------------------------------


def test_logging_at_exception_then_returning_a_default_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import loguru
            import probe.core


            def lookup(key: str) -> str | None:
                try:
                    return probe.core.fetch(key)
                except Exception:
                    loguru.logger.exception('lookup failed')
                    return None
            """
        }
    )
    hits = run_check(GRACEFUL, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('logger-exception-graceful-degradation', 10)]


def test_a_cli_exit_code_is_the_canonical_error_contract(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import loguru
            import probe.core


            def run_train(label: str) -> int:
                try:
                    probe.core.train(label)
                except Exception:
                    loguru.logger.exception('train failed')
                    return 2
                return 0
            """
        }
    )
    assert run_check(GRACEFUL, root) == []


def test_a_handler_that_re_raises_is_not_degradation(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import loguru
            import probe.core


            def lookup(key: str) -> str | None:
                try:
                    return probe.core.fetch(key)
                except Exception:
                    loguru.logger.exception('lookup failed')
                    raise
            """
        }
    )
    assert run_check(GRACEFUL, root) == []


# --------------------------------------------------------------------------
# check_docstring_raises_mismatch
# --------------------------------------------------------------------------


def test_a_docstring_naming_the_wrong_exception_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def load(label: str) -> int:
                \"\"\"Load the thing.

                Raises:
                    AlphaError: when the label is unknown.
                \"\"\"
                raise probe.errors.BetaError('unknown')
            """
        }
    )
    hits = run_check(DOCSTRING_MISMATCH, root)
    assert [hit['rule'] for hit in hits] == ['docstring-raises-mismatch']
    assert "['BetaError']" in hits[0]['variant']


def test_a_docstring_that_matches_the_body_is_not_a_hit(project: Builder, run_check: Runner) -> None:
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
    assert run_check(DOCSTRING_MISMATCH, root) == []


def test_a_raises_section_is_read_past_its_first_entry(project: Builder, run_check: Runner) -> None:
    """The raised class is documented second, after a wrapped first entry."""
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def load(label: str) -> int:
                \"\"\"Load the thing.

                Raises:
                    probe.errors.AlphaError: when the label is unknown, or
                        is empty.
                    probe.errors.BetaError: when the label repeats.
                \"\"\"
                raise probe.errors.BetaError('repeat')
            """
        }
    )
    assert run_check(DOCSTRING_MISMATCH, root) == []


def test_a_bulleted_raises_section_is_read_in_full(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def load(label: str) -> int:
                \"\"\"Load the thing.

                Raises:
                    - AlphaError: when the label is unknown.
                    - BetaError: when the label repeats.
                \"\"\"
                raise probe.errors.BetaError('repeat')
            """
        }
    )
    assert run_check(DOCSTRING_MISMATCH, root) == []


def test_a_class_named_after_the_raises_section_does_not_count(project: Builder, run_check: Runner) -> None:
    """The section ends at the first line back at its header's indent."""
    root = project(
        {
            'src/probe/mod.py': """
            import probe.errors


            def load(label: str) -> int:
                \"\"\"Load the thing.

                Raises:
                    AlphaError: when the label is unknown.

                Note:
                    BetaError: is someone else's problem.
                \"\"\"
                raise probe.errors.BetaError('repeat')
            """
        }
    )
    assert [hit['rule'] for hit in run_check(DOCSTRING_MISMATCH, root)] == ['docstring-raises-mismatch']


# --------------------------------------------------------------------------
# check_missing_raises_section
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# check_bare_except_in_module_with_narrow_errors
# --------------------------------------------------------------------------


def test_a_module_that_mixes_narrow_tuples_with_broad_catches_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core

            NETWORK_ERRORS = (OSError, TimeoutError)


            def fetch(url: str) -> str:
                try:
                    return probe.core.get(url)
                except NETWORK_ERRORS:
                    return ''


            def post(url: str) -> str:
                try:
                    return probe.core.post(url)
                except Exception:
                    return ''
            """
        }
    )
    hits = run_check(MIXED_EXCEPT, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('bare-except-in-module-with-narrow-errors', 16)]
    assert hits[0]['evidence'] == 'except Exception:'


def test_a_module_with_only_broad_catches_is_not_mid_sweep(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def post(url: str) -> str:
                try:
                    return probe.core.post(url)
                except Exception:
                    return ''
            """
        }
    )
    assert run_check(MIXED_EXCEPT, root) == []


# --------------------------------------------------------------------------
# check_failure_as_absence
# --------------------------------------------------------------------------


def test_an_adapter_returning_none_from_a_handler_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/sources/api.py': """
            import probe.core


            def fetch(url: str) -> dict | None:
                try:
                    return probe.core.get(url)
                except OSError:
                    return None
            """
        }
    )
    hits = run_check(FAILURE_AS_ABSENCE, root)
    assert [hit['rule'] for hit in hits] == ['failure-as-absence']
    assert 'caught exception returns empty' in hits[0]['variant']


def test_an_adapter_returning_none_on_a_non_200_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/sources/api.py': """
            import probe.core


            def fetch(url: str) -> dict | None:
                response = probe.core.get(url)
                if response.status != 200:
                    return None
                return response.body
            """
        }
    )
    hits = run_check(FAILURE_AS_ABSENCE, root)
    assert [hit['variant'] for hit in hits] == ['non-200 branch returns empty (return None)']


def test_a_handler_that_raises_records_the_failure(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/sources/api.py': """
            import probe.core
            import probe.errors


            def fetch(url: str) -> dict:
                try:
                    return probe.core.get(url)
                except OSError as exc:
                    raise probe.errors.SearchError('fetch failed') from exc
            """
        }
    )
    assert run_check(FAILURE_AS_ABSENCE, root) == []


def test_the_same_shape_outside_an_adapter_directory_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    """Outside an adapter a bare `return None` is often a legitimate cache miss."""
    root = project(
        {
            'src/probe/util/api.py': """
            import probe.core


            def fetch(url: str) -> dict | None:
                try:
                    return probe.core.get(url)
                except OSError:
                    return None
            """
        }
    )
    assert run_check(FAILURE_AS_ABSENCE, root) == []


# --------------------------------------------------------------------------
# check_translator_envelope_gap
# --------------------------------------------------------------------------


def translator(catches: str) -> str:
    """A contextmanager that translates `catches` into the package error.

    Written as `@contextlib.contextmanager`, which is the shape one project's store
    uses: it serves as a decorator over a whole function and as a `with` block
    over part of one, from a single definition.
    """
    return f"""
    import collections.abc
    import contextlib
    import json
    import sqlite3


    class ProbeError(Exception):
        pass


    @contextlib.contextmanager
    def translate_store_errors(context: str) -> collections.abc.Generator[None]:
        try:
            yield
        except {catches} as exc:
            raise ProbeError(context) from exc
    """


def test_a_decorator_envelope_omitting_the_parser_error_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.translate_store_errors('failed to query store')
            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])
            """,
        }
    )
    hits = run_check(TRANSLATOR_GAP, root)
    assert [(hit['rule'], hit['path'], hit['line']) for hit in hits] == [('translator-envelope-gap', 'src/probe/query.py', 10)]
    assert "omits ['json.JSONDecodeError']" in hits[0]['variant']


def test_a_decorator_envelope_covering_the_parser_error_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/errors.py': translator('(sqlite3.Error, json.JSONDecodeError)'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.translate_store_errors('failed to query store')
            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])
            """,
        }
    )
    assert run_check(TRANSLATOR_GAP, root) == []


def test_a_decorator_catching_bare_exception_satisfies_every_branch(project: Builder, run_check: Runner) -> None:
    """The carve-out: a broad decorator envelope is as complete as a broad lexical one."""
    root = project(
        {
            'src/probe/errors.py': translator('Exception'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.translate_store_errors('failed to query store')
            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])
            """,
        }
    )
    assert run_check(TRANSLATOR_GAP, root) == []


def test_a_call_inside_a_lexical_try_belongs_to_the_lexical_checks(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.translate_store_errors('failed to query store')
            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                try:
                    return json.loads(row[0])
                except ValueError as exc:
                    raise probe.errors.ProbeError('bad config') from exc
            """,
        }
    )
    assert run_check(TRANSLATOR_GAP, root) == []


def test_a_contextmanager_block_is_an_envelope_too(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            def load_config(conn: sqlite3.Connection) -> dict:
                with probe.errors.translate_store_errors('failed to query store'):
                    row = conn.execute('SELECT config FROM runs').fetchone()
                    return json.loads(row[0])
            """,
        }
    )
    hits = run_check(TRANSLATOR_GAP, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('translator-envelope-gap', 10)]
    assert 'with translate_store_errors' in hits[0]['variant']


def test_a_parse_outside_the_contextmanager_block_has_no_envelope(project: Builder, run_check: Runner) -> None:
    """No envelope at all is `filesystem-op-without-envelope`'s question, not this one."""
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            def load_config(conn: sqlite3.Connection) -> dict:
                with probe.errors.translate_store_errors('failed to query store'):
                    row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])
            """,
        }
    )
    assert run_check(TRANSLATOR_GAP, root) == []


def test_an_undecorated_function_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3


            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])
            """,
        }
    )
    assert run_check(TRANSLATOR_GAP, root) == []


def test_a_decorator_that_translates_nothing_is_not_an_envelope(project: Builder, run_check: Runner) -> None:
    """A decorator whose handler does not raise a `*Error` is not a translator."""
    root = project(
        {
            'src/probe/errors.py': """
            import collections.abc
            import contextlib
            import sqlite3


            @contextlib.contextmanager
            def timed(label: str) -> collections.abc.Generator[None]:
                try:
                    yield
                except sqlite3.Error:
                    return
            """,
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.timed('load')
            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])
            """,
        }
    )
    assert run_check(TRANSLATOR_GAP, root) == []


def test_a_filesystem_call_under_a_parser_only_envelope_is_a_hit(project: Builder, run_check: Runner) -> None:
    """The disk branch of the locked set, reached through the same envelope."""
    root = project(
        {
            'src/probe/errors.py': translator('json.JSONDecodeError'),
            'src/probe/query.py': """
            import pathlib

            import probe.errors


            @probe.errors.translate_store_errors('failed to write')
            def save(path: pathlib.Path, text: str) -> None:
                path.write_text(text)
            """,
        }
    )
    hits = run_check(TRANSLATOR_GAP, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('translator-envelope-gap', 8)]
    assert "omits ['OSError']" in hits[0]['variant']


def test_a_function_parsing_several_columns_reports_its_earliest_call(project: Builder, run_check: Runner) -> None:
    """One finding per function, anchored to the first parse rather than to
    whichever the AST walk happened to reach first."""
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.translate_store_errors('failed to query store')
            def load_pair(conn: sqlite3.Connection) -> tuple[dict, dict]:
                left, right = conn.execute('SELECT a, b FROM runs').fetchone()
                return (
                    json.loads(left),
                    json.loads(right),
                )
            """,
        }
    )
    assert [hit['line'] for hit in run_check(TRANSLATOR_GAP, root)] == [11]


def test_a_marker_scoped_to_this_rule_accepts_the_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.translate_store_errors('failed to query store')
            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])  # auditme: accept[translator-envelope-gap] the column is written by this package
            """,
        }
    )
    hits = run_check(TRANSLATOR_GAP, root)
    assert [(hit['accepted'], hit['accepted_reason']) for hit in hits] == [(True, 'the column is written by this package')]


def test_a_marker_scoped_to_another_rule_does_not_accept_the_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.translate_store_errors('failed to query store')
            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])  # auditme: accept[except-interpolation] unrelated decision
            """,
        }
    )
    assert [hit['accepted'] for hit in run_check(TRANSLATOR_GAP, root)] == [False]


# --- raises-section-drift ---------------------------------------------------

ERRORS = """class ProbeError(Exception):
    pass


class ParseError(ProbeError):
    pass


class FetchError(ProbeError):
    pass
"""

CALLEE = """import probe.errors


def parse(text: str) -> int:
    \"\"\"Parse it.

    Raises:
        ParseError: the text is not a number.
    \"\"\"
    if not text.isdigit():
        raise probe.errors.ParseError(text)
    return int(text)
"""


def drift(project: Builder, run_check: Runner, caller: str) -> list[tuple[str, str]]:
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/parse.py': CALLEE, 'src/probe/use.py': caller})
    return sorted((hit['path'], hit['variant']) for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift')


def test_a_callee_error_missing_from_raises_is_a_hit(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors
import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        FetchError: nothing to load.
    \"\"\"
    if not text:
        raise probe.errors.FetchError('empty')
    return probe.parse.parse(text)
"""
    assert drift(project, run_check, caller) == [('src/probe/use.py', 'load: Raises: omits ParseError, declared by probe.parse.parse')]


def test_a_callee_error_names_the_callee_file_as_related(project: Builder, run_check: Runner) -> None:
    caller = """import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ValueError: never.
    \"\"\"
    return probe.parse.parse(text)
"""
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/parse.py': CALLEE, 'src/probe/use.py': caller})
    hits = [hit for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift']
    assert [hit.get('related') for hit in hits] == [['src/probe/parse.py']]


def test_an_error_its_own_except_always_catches_is_an_extra(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors
import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ParseError: bad text.
    \"\"\"
    try:
        return probe.parse.parse(text)
    except probe.errors.ParseError:
        return 0
"""
    assert drift(project, run_check, caller) == [('src/probe/use.py', 'load: Raises: declares ParseError, which never reaches the caller')]


def test_a_handler_that_re_raises_does_not_catch(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors
import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ParseError: bad text.
    \"\"\"
    try:
        return probe.parse.parse(text)
    except probe.errors.ParseError:
        print('bad')
        raise
"""
    assert drift(project, run_check, caller) == []


@pytest.mark.parametrize('later', ['probe.errors.ProbeError', 'Exception'])
def test_a_re_raising_handler_wins_over_a_later_broader_one(project: Builder, run_check: Runner, later: str) -> None:
    caller = f"""import probe.errors
import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ParseError: bad text.
    \"\"\"
    try:
        return probe.parse.parse(text)
    except probe.errors.ParseError:
        raise
    except {later}:
        return 0
"""
    assert drift(project, run_check, caller) == []


def test_an_unresolved_call_under_a_re_raising_handler_is_not_an_extra(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors


def load(text: str, reader: object) -> int:
    \"\"\"Load it.

    Raises:
        ParseError: bad text.
    \"\"\"
    try:
        return reader(text)
    except probe.errors.ParseError:
        raise
    except Exception:
        return 0
"""
    assert drift(project, run_check, caller) == []


def test_catching_a_base_class_catches_its_subclasses(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors
import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        FetchError: nothing to load.
    \"\"\"
    if not text:
        raise probe.errors.FetchError('empty')
    try:
        return probe.parse.parse(text)
    except probe.errors.ProbeError:
        return 0
"""
    assert drift(project, run_check, caller) == []


def test_declaring_a_base_class_covers_its_subclasses(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors
import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ProbeError: anything the package raises.
    \"\"\"
    if not text:
        raise probe.errors.FetchError('empty')
    return probe.parse.parse(text)
"""
    assert drift(project, run_check, caller) == []


def test_a_method_call_on_self_follows_the_method(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors


class Loader:
    def check(self, text: str) -> None:
        \"\"\"Check it.

        Raises:
            FetchError: nothing to load.
        \"\"\"
        if not text:
            raise probe.errors.FetchError('empty')

    def load(self, text: str) -> str:
        \"\"\"Load it.

        Raises:
            ParseError: never raised here.
        \"\"\"
        self.check(text)
        return text
"""
    assert drift(project, run_check, caller) == [('src/probe/use.py', 'load: Raises: omits FetchError, declared by probe.use.Loader.check')]


def test_a_function_without_a_raises_section_is_not_this_check(project: Builder, run_check: Runner) -> None:
    caller = """import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.\"\"\"
    return probe.parse.parse(text)
"""
    assert drift(project, run_check, caller) == []


def test_a_callee_in_another_package_is_not_followed(project: Builder, run_check: Runner) -> None:
    caller = """import other.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ValueError: bad text.
    \"\"\"
    if not text:
        raise ValueError(text)
    return other.parse.parse(text)
"""
    assert drift(project, run_check, caller) == []


def test_a_scoped_marker_accepts_raises_drift(project: Builder, run_check: Runner) -> None:
    caller = """import probe.parse


def load(text: str) -> int:  # auditme: accept[raises-section-drift] callers never see a bad text
    \"\"\"Load it.

    Raises:
        ValueError: never.
    \"\"\"
    return probe.parse.parse(text)
"""
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/parse.py': CALLEE, 'src/probe/use.py': caller})
    hits = [hit for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift']
    assert [(hit['accepted'], hit['accepted_reason']) for hit in hits] == [(True, 'callers never see a bad text')]


def test_an_unreached_declared_error_with_no_handler_is_not_an_extra(project: Builder, run_check: Runner) -> None:
    """A declared error may reach through a call the check cannot resolve (an
    instance method, a callable passed in), so an extra needs positive evidence:
    a handler in the function that catches it."""
    caller = """import probe.errors


def load(reader, text: str) -> int:
    \"\"\"Load it.

    Raises:
        ParseError: the reader cannot parse the text.
    \"\"\"
    return reader.read(text)
"""
    assert drift(project, run_check, caller) == []


def test_a_function_re_exported_by_a_package_init_is_followed(project: Builder, run_check: Runner) -> None:
    caller = """import probe.tools


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ValueError: never.
    \"\"\"
    return probe.tools.parse(text)
"""
    root = project(
        {
            'src/probe/errors.py': ERRORS,
            'src/probe/tools/__init__.py': 'from probe.tools.parse import parse\n',
            'src/probe/tools/parse.py': CALLEE,
            'src/probe/use.py': caller,
        }
    )
    hits = [hit for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift']
    assert [hit['variant'] for hit in hits] == ['load: Raises: omits ParseError, declared by probe.tools.parse.parse']


def test_a_self_call_to_an_inherited_method_is_not_followed(project: Builder, run_check: Runner) -> None:
    """`self.load()` where the method is defined on a base class resolves to
    nothing in this class, and must not crash the sweep."""
    caller = """import base


class Loader(base.Base):
    def run(self) -> None:
        \"\"\"Run.

        Raises:
            ValueError: never.
        \"\"\"
        self.load()
"""
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/parse.py': CALLEE, 'src/probe/use.py': caller})
    assert run_check(RAISES_DRIFT, root) == []


def test_an_error_class_from_outside_the_package_is_not_a_domain_error(project: Builder, run_check: Runner) -> None:
    """A domain error is a class the package defines: `sqlite3.Error`, whose
    tail is just `Error`, and a third-party `*Error` are neither."""
    callee = """import sqlite3


def write(rows: list) -> None:
    \"\"\"Write them.

    Raises:
        sqlite3.Error: the database refused the rows.
        OtherLibError: the other library failed.
    \"\"\"
    del rows
"""
    caller = """import probe.write


def store(rows: list) -> None:
    \"\"\"Store them.

    Raises:
        ValueError: never.
    \"\"\"
    probe.write.write(rows)
"""
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/write.py': callee, 'src/probe/use.py': caller})
    assert run_check(RAISES_DRIFT, root) == []


# --- raises-section-drift: errors guarded by unset optional arguments -------

LOAD_CALLER = """import probe.errors
import probe.loader


def run(name: str, *args: str) -> int:
    \"\"\"Run it.

    Raises:
        FetchError: nothing to run.
    \"\"\"
    if not name:
        raise probe.errors.FetchError('empty')
    return {call}
"""

OPTIONAL_CALLEE = """import probe.errors

LIMIT = 3


def load({params}) -> int:
    \"\"\"Load it.

    Raises:
        ParseError: bad input.
    \"\"\"
{body}"""

GUARDED = '    if strict:\n        raise probe.errors.ParseError(name)\n    return 0\n'
OMITS_PARSE_ERROR = [('src/probe/use.py', 'run: Raises: omits ParseError, declared by probe.loader.load')]


def loader_drift(project: Builder, run_check: Runner, call: str, params: str = 'name: str, strict: bool = False', body: str = GUARDED) -> list[tuple[str, str]]:
    callee = OPTIONAL_CALLEE.format(params=params, body=body)
    caller = LOAD_CALLER.format(call=call)
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/loader.py': callee, 'src/probe/use.py': caller})
    return sorted((hit['path'], hit['variant']) for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift')


def test_a_call_leaving_the_guarding_optional_argument_unset_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    assert loader_drift(project, run_check, "probe.loader.load('x')") == []


def test_a_keyword_only_optional_guard_left_unset_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    assert loader_drift(project, run_check, "probe.loader.load('x')", params='name: str, *, strict: bool = False') == []


def test_a_self_call_leaving_the_optional_argument_unset_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors


class Runner:
    def load(self, name: str, strict: bool = False) -> int:
        \"\"\"Load it.

        Raises:
            ParseError: bad input.
        \"\"\"
        if strict:
            raise probe.errors.ParseError(name)
        return 0

    def run(self, name: str) -> int:
        \"\"\"Run it.

        Raises:
            FetchError: nothing to run.
        \"\"\"
        if not name:
            raise probe.errors.FetchError('empty')
        return self.load(name)
"""
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/use.py': caller})
    assert [hit for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift'] == []


def test_a_self_call_supplying_the_optional_argument_positionally_is_a_hit(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors


class Runner:
    def load(self, name: str, strict: bool = False) -> int:
        \"\"\"Load it.

        Raises:
            ParseError: bad input.
        \"\"\"
        if strict:
            raise probe.errors.ParseError(name)
        return 0

    def run(self, name: str) -> int:
        \"\"\"Run it.

        Raises:
            FetchError: nothing to run.
        \"\"\"
        if not name:
            raise probe.errors.FetchError('empty')
        return self.load(name, True)
"""
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/use.py': caller})
    hits = [hit['variant'] for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift']
    assert hits == ['run: Raises: omits ParseError, declared by probe.use.Runner.load']


@pytest.mark.parametrize('call', ["probe.loader.load('x', True)", "probe.loader.load('x', strict=True)", 'probe.loader.load(*args)'])
def test_a_call_supplying_the_optional_argument_is_still_a_hit(project: Builder, run_check: Runner, call: str) -> None:
    assert loader_drift(project, run_check, call) == OMITS_PARSE_ERROR


def test_a_guard_on_a_parameter_without_a_default_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    body = '    if not name.isdigit():\n        raise probe.errors.ParseError(name)\n    return 0\n'
    assert loader_drift(project, run_check, "probe.loader.load('x')", body=body) == OMITS_PARSE_ERROR


def test_a_guard_on_a_module_level_name_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    body = '    if LIMIT > 2:\n        raise probe.errors.ParseError(name)\n    return 0\n'
    assert loader_drift(project, run_check, "probe.loader.load('x')", body=body) == OMITS_PARSE_ERROR


def test_an_error_also_raised_outside_the_guard_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    body = GUARDED.replace('    return 0\n', '    raise probe.errors.ParseError(name)\n')
    assert loader_drift(project, run_check, "probe.loader.load('x')", body=body) == OMITS_PARSE_ERROR


def test_a_callee_only_documenting_the_error_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    body = '    return probe.parse.parse(name)\n'
    assert loader_drift(project, run_check, "probe.loader.load('x')", body=body) == OMITS_PARSE_ERROR


# --- raises-section-drift: called nested functions --------------------------

NESTED_CALLER = """import probe.errors
import probe.parse


def run(text: str, other: str, strict: bool) -> int:
    \"\"\"Run it.

    Raises:
        {declared}: the text is bad.
    \"\"\"
{body}"""

REPRODUCTION = """    def attempt() -> int:
        try:
            return probe.parse.parse(text)
        except probe.errors.ParseError:
            if strict:
                raise
            return 0

    try:
        probe.parse.parse(other)
    except probe.errors.ParseError:
        pass
    return attempt()
"""


def nested_drift(project: Builder, run_check: Runner, body: str, declared: str = 'ParseError') -> list[tuple[str, str]]:
    return drift(project, run_check, NESTED_CALLER.format(declared=declared, body=body))


def test_a_called_nested_def_that_re_raises_keeps_the_declaration_reaching(project: Builder, run_check: Runner) -> None:
    assert nested_drift(project, run_check, REPRODUCTION) == []


def test_a_nested_def_never_called_adds_nothing(project: Builder, run_check: Runner) -> None:
    body = """    def attempt() -> int:
        return probe.parse.parse(text)

    return 0
"""
    assert nested_drift(project, run_check, body, declared='FetchError') == []


def test_a_nested_def_called_outside_any_try_reaches_the_subject(project: Builder, run_check: Runner) -> None:
    body = """    def attempt() -> int:
        return probe.parse.parse(text)

    return attempt()
"""
    assert nested_drift(project, run_check, body, declared='FetchError') == [
        ('src/probe/use.py', 'run: Raises: omits ParseError, declared by probe.parse.parse')
    ]


def test_a_nested_def_called_inside_a_catching_try_does_not_reach(project: Builder, run_check: Runner) -> None:
    body = """    def attempt() -> int:
        return probe.parse.parse(text)

    try:
        return attempt()
    except probe.errors.ParseError:
        return 0
"""
    assert nested_drift(project, run_check, body) == [('src/probe/use.py', 'run: Raises: declares ParseError, which never reaches the caller')]


def test_a_bare_raise_in_a_def_inside_a_handler_does_not_make_it_re_raise(project: Builder, run_check: Runner) -> None:
    body = """    try:
        return probe.parse.parse(text)
    except probe.errors.ParseError:
        def again() -> None:
            raise

        return 0
"""
    assert nested_drift(project, run_check, body) == [('src/probe/use.py', 'run: Raises: declares ParseError, which never reaches the caller')]


# --------------------------------------------------------------------------
# package_class_parents and class_lineage
# --------------------------------------------------------------------------


def parse_modules(*sources: str) -> list[ast.Module]:
    return [ast.parse(source) for source in sources]


def test_package_class_parents_strips_module_prefix_from_bases() -> None:
    trees = parse_modules('class A(Base): pass\nclass B(mod.Base): pass\n')
    parents = auditme.rules.error_handling.package_class_parents(trees)
    assert parents['A'] == {'Base'}
    assert parents['B'] == {'Base'}


def test_package_class_parents_pools_modules() -> None:
    trees = parse_modules('class A(Base): pass\n', 'class B(A): pass\n')
    parents = auditme.rules.error_handling.package_class_parents(trees)
    assert set(parents) >= {'A', 'B'}
    assert parents['B'] == {'A'}


def test_class_lineage_is_transitive() -> None:
    parents = {'C': {'B'}, 'B': {'A'}, 'A': set()}
    assert auditme.rules.error_handling.class_lineage('C', parents) == {'A', 'B', 'C'}


def test_class_lineage_terminates_on_a_cycle() -> None:
    parents = {'A': {'B'}, 'B': {'A'}}
    assert auditme.rules.error_handling.class_lineage('A', parents) == {'A', 'B'}


def test_class_lineage_of_an_unknown_name_is_itself() -> None:
    assert auditme.rules.error_handling.class_lineage('Nope', {}) == {'Nope'}
