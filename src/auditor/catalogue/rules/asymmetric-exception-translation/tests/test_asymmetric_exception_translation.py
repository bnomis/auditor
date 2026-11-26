"""Tests for the checks of the `asymmetric-exception-translation` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

ASYMMETRIC = auditor.testing.load_check(__file__)


ASYMMETRIC_HELPER = 'import pathlib\n\n\ndef setup_experiment(name: str) -> int:\n    return len(pathlib.Path(name).read_text())\n'

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


def test_a_helper_of_pure_string_work_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/helper.py': 'def setup_experiment(name: str) -> int:\n    return len(name)\n',
            'src/probe/a.py': WRAPPED_CALLER.format(name='run_a'),
            'src/probe/b.py': WRAPPED_CALLER.format(name='run_b'),
        }
    )
    assert run_check(ASYMMETRIC, root) == []


def test_a_helper_that_translates_through_a_same_module_function_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/helper.py': """
            import pathlib

            import probe.errors


            def read_guarded(name: str) -> str:
                try:
                    return pathlib.Path(name).read_text()
                except OSError as exc:
                    raise probe.errors.ProbeError('read failed') from exc


            def setup_experiment(name: str) -> int:
                return len(read_guarded(name))
            """,
            'src/probe/a.py': WRAPPED_CALLER.format(name='run_a'),
            'src/probe/b.py': WRAPPED_CALLER.format(name='run_b'),
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
