"""Tests for the test tree index: test files, imports and direct tests."""

import collections.abc
import pathlib

import pytest
from auditme import phaseb
from auditme.phaseb import testmap

Project = collections.abc.Callable[[dict[str, str]], pathlib.Path]

MOD = """
    def load():
        return 1


    class Probe:
        def run(self):
            return 2
"""

BASE = {'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD, 'src/tests/__init__.py': ''}


def _map(root: pathlib.Path, depth: int = 3) -> dict[str, tuple[testmap.TestRef, ...]]:
    return testmap.build_test_map(root, depth)


def test_direct_call_after_import_gives_a_direct_ref(project: Project) -> None:
    root = project(
        {
            **BASE,
            'src/tests/test_mod.py': """
                from pkg.mod import load


                def test_load():
                    assert load() == 1
            """,
        }
    )
    (ref,) = _map(root)['src/pkg/mod.py::load']
    assert ref.id == 'src/tests/test_mod.py::test_load'
    assert ref.path == 'src/tests/test_mod.py'
    assert (ref.start, ref.end) == (4, 5)
    assert ref.route == 'direct'
    assert ref.via is None


def test_module_attribute_call_is_found(project: Project) -> None:
    root = project(
        {
            **BASE,
            'src/tests/test_mod.py': """
                import pkg.mod


                def test_load():
                    assert pkg.mod.load() == 1
            """,
        }
    )
    assert [ref.id for ref in _map(root)['src/pkg/mod.py::load']] == ['src/tests/test_mod.py::test_load']


def test_method_test_in_test_class_has_class_in_id(project: Project) -> None:
    root = project(
        {
            **BASE,
            'src/tests/test_mod.py': """
                from pkg.mod import load


                class TestProbe:
                    def test_load(self):
                        assert load() == 1

                    def helper(self):
                        load()
            """,
        }
    )
    assert [ref.id for ref in _map(root)['src/pkg/mod.py::load']] == ['src/tests/test_mod.py::TestProbe.test_load']


def test_fixture_in_same_file_gives_a_direct_ref(project: Project) -> None:
    root = project(
        {
            **BASE,
            'src/tests/test_mod.py': """
                import pytest
                from pkg.mod import load


                @pytest.fixture
                def loaded():
                    return load()


                def test_uses_fixture(loaded):
                    assert loaded == 1
            """,
        }
    )
    assert [ref.id for ref in _map(root)['src/pkg/mod.py::load']] == ['src/tests/test_mod.py::test_uses_fixture']


def test_fixture_in_conftest_above_gives_a_direct_ref(project: Project) -> None:
    root = project(
        {
            **BASE,
            'src/tests/conftest.py': """
                import pytest
                from pkg.mod import load


                @pytest.fixture()
                def loaded():
                    return load()
            """,
            'src/tests/sub/test_mod.py': """
                def test_uses_fixture(loaded):
                    assert loaded == 1
            """,
        }
    )
    assert [ref.id for ref in _map(root)['src/pkg/mod.py::load']] == ['src/tests/sub/test_mod.py::test_uses_fixture']


def test_hypothesis_given_marks_a_property_test(project: Project) -> None:
    root = project(
        {
            **BASE,
            'src/tests/test_mod.py': """
                from hypothesis import given
                from pkg.mod import load


                @given(x=1)
                def test_prop(x):
                    load()


                def test_plain():
                    load()
            """,
        }
    )
    flags = {ref.id: ref.property for ref in _map(root)['src/pkg/mod.py::load']}
    assert flags == {'src/tests/test_mod.py::test_plain': False, 'src/tests/test_mod.py::test_prop': True}


def test_hypothesis_module_attribute_given_is_recognised(project: Project) -> None:
    root = project(
        {
            **BASE,
            'src/tests/test_mod.py': """
                import hypothesis
                from pkg.mod import load


                @hypothesis.given(x=1)
                def test_prop(x):
                    load()
            """,
        }
    )
    assert _map(root)['src/pkg/mod.py::load'][0].property is True


def test_same_name_without_import_adds_no_ref(project: Project) -> None:
    root = project(
        {
            **BASE,
            'src/tests/test_other.py': """
                def load():
                    return 3


                def test_local():
                    assert load() == 3
            """,
        }
    )
    assert _map(root) == {}


def test_unresolvable_call_is_left_out(project: Project) -> None:
    root = project(
        {
            **BASE,
            'src/tests/test_mod.py': """
                import pkg.mod


                def test_dynamic():
                    getattr(pkg.mod, 'load')()
                    handlers = [pkg.mod.load]
                    handlers[0]()
            """,
        }
    )
    assert _map(root) == {}


@pytest.mark.parametrize('files', [{'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD}, {}])
def test_project_without_test_tree_gives_empty_map(project: Project, files: dict[str, str]) -> None:
    root = project({**files, 'README.md': 'x'})
    assert _map(root) == {}


def test_top_level_tests_directory_is_read(project: Project) -> None:
    root = project(
        {
            'src/pkg/__init__.py': '',
            'src/pkg/mod.py': MOD,
            'tests/test_mod.py': """
                from pkg.mod import load


                def test_load():
                    load()
            """,
        }
    )
    assert [ref.id for ref in _map(root)['src/pkg/mod.py::load']] == ['tests/test_mod.py::test_load']


def test_unparseable_test_file_raises_naming_the_file(project: Project) -> None:
    root = project({**BASE, 'src/tests/test_bad.py': 'def test_x(:\n'})
    with pytest.raises(phaseb.PhaseBError, match='test_bad.py'):
        _map(root)


def test_unparseable_source_file_raises_naming_the_file(project: Project) -> None:
    root = project({**BASE, 'src/pkg/broken.py': 'def f(:\n'})
    with pytest.raises(phaseb.PhaseBError, match='broken.py'):
        _map(root)


def test_refs_come_back_sorted_by_id(project: Project) -> None:
    root = project(
        {
            **BASE,
            'src/tests/test_b.py': """
                from pkg.mod import load


                def test_b():
                    load()
            """,
            'src/tests/test_a.py': """
                from pkg.mod import load


                def test_z():
                    load()


                def test_a():
                    load()
            """,
        }
    )
    ids = [ref.id for ref in _map(root)['src/pkg/mod.py::load']]
    assert ids == sorted(ids)
    assert len(ids) == 3


def test_each_test_file_is_parsed_once(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(
        {
            **BASE,
            'src/tests/test_mod.py': """
                from pkg.mod import load


                def test_load():
                    load()


                def test_again():
                    load()
            """,
        }
    )
    parsed: list[pathlib.Path] = []
    original = testmap.parse_file

    def counting(path: pathlib.Path, base: pathlib.Path, project_root: pathlib.Path) -> testmap.ParsedFile:
        parsed.append(path)
        return original(path, base, project_root)

    monkeypatch.setattr(testmap, 'parse_file', counting)
    _map(root)
    assert parsed.count(root / 'src/tests/test_mod.py') == 1
