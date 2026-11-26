"""Tests for the checks of the `in-function-import` rule."""

import collections.abc
import pathlib
import types
import typing

import auditor.api
import auditor.core
import auditor.testing

if typing.TYPE_CHECKING:
    import pytest

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

IN_FUNCTION_IMPORTS = auditor.testing.load_check(__file__)


def test_an_import_inside_a_function_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def parse(text: str) -> object:
                import json
                return json.loads(text)
            """
        }
    )
    hits = run_check(IN_FUNCTION_IMPORTS, root)
    assert [(hit['rule'], hit['variant'], hit['line']) for hit in hits] == [('in-function-import', 'stdlib', 2)]


def test_a_first_party_in_function_import_is_labelled_as_such(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def parse(text: str) -> object:
                import probe.heavy
                return probe.heavy.run(text)
            """
        }
    )
    assert [hit['variant'] for hit in run_check(IN_FUNCTION_IMPORTS, root)] == ['first-party']


def test_a_module_under_a_declared_root_is_labelled_first_party(project: Builder, run_check: Runner, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def parse(text: str) -> object:
                import gitutils
                import auditme.core
                return gitutils, auditme.core
            """,
            'bin/gitutils.py': 'VALUE = 1\n',
            'lib/auditme/__init__.py': '',
        }
    )
    monkeypatch.setattr(
        auditor.core,
        'ROOT_MODULES',
        types.MappingProxyType({root / 'bin': auditor.core.TOP_LEVEL, root / 'lib' / 'auditme': auditor.core.PACKAGE}),
    )
    assert [hit['variant'] for hit in run_check(IN_FUNCTION_IMPORTS, root)] == ['first-party', 'first-party']


def test_a_module_outside_every_declared_root_stays_third_party(project: Builder, run_check: Runner, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def parse(text: str) -> object:
                import requests
                return requests
            """,
            'bin/gitutils.py': 'VALUE = 1\n',
        }
    )
    monkeypatch.setattr(auditor.core, 'ROOT_MODULES', types.MappingProxyType({root / 'bin': auditor.core.TOP_LEVEL}))
    assert [hit['variant'] for hit in run_check(IN_FUNCTION_IMPORTS, root)] == ['third-party']


def test_an_import_under_type_checking_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """The `TYPE_CHECKING` guard has to be tested inside a function.

    A module-level guard is never reached: the check only walks function
    scopes, so a module-level fixture would pass whether or not the
    `TYPE_CHECKING` exemption existed.
    """
    root = project(
        {
            'src/probe/mod.py': """
            import typing


            def parse(text: str) -> object:
                if typing.TYPE_CHECKING:
                    import json
                return text
            """
        }
    )
    assert run_check(IN_FUNCTION_IMPORTS, root) == []


def test_the_same_import_without_the_guard_is_a_hit(project: Builder, run_check: Runner) -> None:
    """The counterpart to the test above: the guard is what makes the difference."""
    root = project(
        {
            'src/probe/mod.py': """
            def parse(text: str) -> object:
                if text:
                    import json
                    return json.loads(text)
                return text
            """
        }
    )
    assert len(run_check(IN_FUNCTION_IMPORTS, root)) == 1


def test_an_optional_dependency_probe_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """`try: import x / except ImportError` is how an optional dependency is
    detected, not a lazy import hiding a startup cost."""
    root = project(
        {
            'src/probe/mod.py': """
            def has_orjson() -> bool:
                try:
                    import orjson
                except ImportError:
                    return False
                return bool(orjson)
            """
        }
    )
    assert run_check(IN_FUNCTION_IMPORTS, root) == []


def test_an_init_file_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/__init__.py': """
            def build() -> object:
                import json
                return json
            """
        }
    )
    assert run_check(IN_FUNCTION_IMPORTS, root) == []


def test_an_agents_table_row_accepts_the_pair(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'AGENTS.md': """
            ## Accepted lazy imports

            | Importer | Imported | Reason |
            |----------|----------|--------|
            | `probe.mod` | `json` | startup cost |
            """,
            'src/probe/mod.py': """
            def parse(text: str) -> object:
                import json
                return json.loads(text)
            """,
        }
    )
    hits = run_check(IN_FUNCTION_IMPORTS, root)
    assert len(hits) == 1
    assert hits[0]['accepted']
    assert 'probe.mod -> json' in hits[0]['accepted_reason']


def test_declared_root_modules_are_listed_once_per_run(project: Builder, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'bin/tool.py': '', 'bin/pkg/__init__.py': ''})
    monkeypatch.setattr(auditor.core, 'ROOT_MODULES', types.MappingProxyType({root / 'bin': auditor.core.TOP_LEVEL}))
    auditor.core.clear_source_cache()
    calls: list[pathlib.Path] = []
    real = pathlib.Path.glob

    def counting(self: pathlib.Path, pattern: str, **kwargs: typing.Any) -> typing.Any:
        calls.append(self)
        return real(self, pattern, **kwargs)

    monkeypatch.setattr(pathlib.Path, 'glob', counting)
    first = auditor.api.declared_root_modules()
    second = auditor.api.declared_root_modules()
    assert first == second == {'tool', 'pkg'}
    assert len(calls) == 1
