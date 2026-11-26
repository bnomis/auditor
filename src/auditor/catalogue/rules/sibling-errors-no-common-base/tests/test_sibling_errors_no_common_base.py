"""Tests for the checks of the `sibling-errors-no-common-base` rule."""

import collections.abc
import pathlib
import typing

import auditor.api
import auditor.core
import auditor.testing

if typing.TYPE_CHECKING:
    import pytest

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

SIBLING_ERRORS = auditor.testing.load_check(__file__)


def test_two_error_classes_with_no_shared_parent_are_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/errors.py': 'class AlphaError(Exception):\n    pass\n\n\nclass BetaError(Exception):\n    pass\n'})
    hits = run_check(SIBLING_ERRORS, root)
    assert [hit['rule'] for hit in hits] == ['sibling-errors-no-common-base']
    assert 'AlphaError' in hits[0]['evidence']


def test_attribute_call_and_subscript_bases_are_read_without_error(project: Builder, run_check: Runner) -> None:
    source = 'import lib\n\n\nclass AlphaError(lib.Base):\n    pass\n\n\nclass BetaError(make_base()):\n    pass\n\n\nclass GammaError(bases[0]):\n    pass\n'
    root = project({'src/probe/errors.py': source})
    hits = run_check(SIBLING_ERRORS, root)
    assert [hit['rule'] for hit in hits] == ['sibling-errors-no-common-base']
    assert 'AlphaError' in hits[0]['evidence']


def test_a_real_hierarchy_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/errors.py': 'class ProbeError(Exception):\n    pass\n\n\nclass AlphaError(ProbeError):\n    pass\n'})
    assert run_check(SIBLING_ERRORS, root) == []


def test_a_module_that_is_not_errors_py_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'class AlphaError(Exception):\n    pass\n\n\nclass BetaError(Exception):\n    pass\n'})
    assert run_check(SIBLING_ERRORS, root) == []


def test_sibling_error_check_walks_the_root_once_however_many_errors_files_it_holds(
    project: Builder, run_check: Runner, monkeypatch: pytest.MonkeyPatch
) -> None:
    errors = 'class AlphaError(Exception):\n    pass\n\n\nclass BetaError(Exception):\n    pass\n'
    root = project({'src/probe/errors.py': errors, 'src/probe/sub/errors.py': errors})
    auditor.core.clear_source_cache()
    calls: list[pathlib.Path] = []
    real = auditor.api.all_py_files

    def counting(src_root: pathlib.Path) -> list[pathlib.Path]:
        calls.append(src_root)
        return real(src_root)

    monkeypatch.setattr(auditor.api, 'all_py_files', counting)
    hits = run_check(SIBLING_ERRORS, root)
    assert len(hits) == 2
    assert len(calls) == 1
