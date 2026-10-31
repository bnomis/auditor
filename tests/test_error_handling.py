"""Tests for the exception-handling and error-reporting predicates.

`get-container-default-then-method-call` has its own module,
`test_get_container_default.py`.
"""

import collections.abc
import pathlib

import auditme.rules.error_handling

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
    """Documented refinement (review-36): `type(exc).__name__` exposes the class
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

    Written as `@contextlib.contextmanager`, which is the shape litrev's store
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
