"""Tests for the test tree index: test files, imports and direct tests."""

import collections.abc
import pathlib

import auditme.core
import auditme.phaseb
import auditme.phaseb.testmap
import hypothesis
import hypothesis.strategies
import pytest

Project = collections.abc.Callable[[dict[str, str]], pathlib.Path]

MOD = """
    def load():
        return 1


    class Probe:
        def run(self):
            return 2
"""

BASE = {'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD, 'src/tests/__init__.py': ''}


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
    (ref,) = auditme.phaseb.testmap.load_test_map(root, 3)['src/pkg/mod.py::load']
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
    assert [ref.id for ref in auditme.phaseb.testmap.load_test_map(root, 3)['src/pkg/mod.py::load']] == ['src/tests/test_mod.py::test_load']


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
    assert [ref.id for ref in auditme.phaseb.testmap.load_test_map(root, 3)['src/pkg/mod.py::load']] == ['src/tests/test_mod.py::TestProbe.test_load']


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
    assert [ref.id for ref in auditme.phaseb.testmap.load_test_map(root, 3)['src/pkg/mod.py::load']] == ['src/tests/test_mod.py::test_uses_fixture']


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
    assert [ref.id for ref in auditme.phaseb.testmap.load_test_map(root, 3)['src/pkg/mod.py::load']] == ['src/tests/sub/test_mod.py::test_uses_fixture']


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
    flags = {ref.id: ref.property for ref in auditme.phaseb.testmap.load_test_map(root, 3)['src/pkg/mod.py::load']}
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
    assert auditme.phaseb.testmap.load_test_map(root, 3)['src/pkg/mod.py::load'][0].property is True


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
    assert auditme.phaseb.testmap.load_test_map(root, 3) == {}


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
    assert auditme.phaseb.testmap.load_test_map(root, 3) == {}


@pytest.mark.parametrize('files', [{'src/pkg/__init__.py': '', 'src/pkg/mod.py': MOD}, {}])
def test_project_without_test_tree_gives_empty_map(project: Project, files: dict[str, str]) -> None:
    root = project({**files, 'README.md': 'x'})
    assert auditme.phaseb.testmap.load_test_map(root, 3) == {}


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
    assert [ref.id for ref in auditme.phaseb.testmap.load_test_map(root, 3)['src/pkg/mod.py::load']] == ['tests/test_mod.py::test_load']


PKG_ROOTS = '[tool.auditme]\nroots = [{path = "pkg"}, {path = "checks/tests"}]\n'
LOAD_TEST = """
    from pkg.mod import load


    def test_load():
        load()
"""


def test_declared_root_holding_tests_is_read(project: Project) -> None:
    root = project(
        {
            'pyproject.toml': PKG_ROOTS,
            'pkg/__init__.py': '',
            'pkg/mod.py': MOD,
            'checks/tests/__init__.py': '',
            'checks/tests/test_mod.py': """
                import pkg.mod


                def test_load():
                    pkg.mod.load()
            """,
        }
    )
    index = auditme.phaseb.testmap.load_test_index(root)
    (ref,) = index.refs(3)['pkg/mod.py::load']
    assert ref.path == 'checks/tests/test_mod.py'
    assert 'checks/tests/test_mod.py' in index.test_files('pkg/mod.py::load', 3)


def test_top_level_declared_root_names_test_module_without_root_name(project: Project) -> None:
    root = project(
        {
            'pyproject.toml': '[tool.auditme]\nroots = [{path = "scripts", modules = "top-level"}]\n',
            'scripts/test_x.py': 'def test_x():\n    pass\n',
        }
    )
    (file,) = auditme.phaseb.testmap.read_test_tree(root, auditme.core.audit_roots(root))[0]
    assert file.module == 'test_x'


def test_file_under_two_roots_gives_one_ref(project: Project) -> None:
    root = project(
        {
            'pyproject.toml': '[tool.auditme]\nroots = [{path = "pkg"}, {path = "tests"}]\n',
            'pkg/__init__.py': '',
            'pkg/mod.py': MOD,
            'tests/test_mod.py': LOAD_TEST,
        }
    )
    assert [ref.id for ref in auditme.phaseb.testmap.load_test_map(root, 3)['pkg/mod.py::load']] == ['tests/test_mod.py::test_load']


def test_conftest_chain_stops_at_the_declared_test_root(project: Project) -> None:
    root = project(
        {
            'pyproject.toml': PKG_ROOTS,
            'pkg/__init__.py': '',
            'pkg/mod.py': MOD,
            'pkg/other.py': 'def other():\n    return 3\n',
            'checks/conftest.py': """
                import pytest
                from pkg.other import other


                @pytest.fixture()
                def above():
                    return other()
            """,
            'checks/tests/conftest.py': """
                import pytest
                from pkg.mod import load


                @pytest.fixture()
                def inside():
                    return load()
            """,
            'checks/tests/test_a.py': 'def test_a(inside):\n    pass\n',
            'checks/tests/test_b.py': 'def test_b(above):\n    pass\n',
        }
    )
    found = auditme.phaseb.testmap.load_test_map(root, 3)
    assert [ref.id for ref in found['pkg/mod.py::load']] == ['checks/tests/test_a.py::test_a']
    assert 'pkg/other.py::other' not in found


def test_undeclared_project_reads_package_tests_and_src_tests(project: Project) -> None:
    root = project(
        {
            'src/pkg/__init__.py': '',
            'src/pkg/mod.py': MOD,
            'src/pkg/tests/test_mod.py': LOAD_TEST,
            'src/tests/test_other.py': LOAD_TEST,
        }
    )
    ids = [ref.id for ref in auditme.phaseb.testmap.load_test_map(root, 3)['src/pkg/mod.py::load']]
    assert ids == ['src/pkg/tests/test_mod.py::test_load', 'src/tests/test_other.py::test_load']


def test_unparseable_test_file_raises_naming_the_file(project: Project) -> None:
    root = project({**BASE, 'src/tests/test_bad.py': 'def test_x(:\n'})
    with pytest.raises(auditme.phaseb.PhaseBError, match='test_bad.py'):
        auditme.phaseb.testmap.load_test_map(root, 3)


def test_unparseable_source_file_raises_naming_the_file(project: Project) -> None:
    root = project({**BASE, 'src/pkg/broken.py': 'def f(:\n'})
    with pytest.raises(auditme.phaseb.PhaseBError, match='broken.py'):
        auditme.phaseb.testmap.load_test_map(root, 3)


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
    ids = [ref.id for ref in auditme.phaseb.testmap.load_test_map(root, 3)['src/pkg/mod.py::load']]
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
    original = auditme.phaseb.testmap.read_test_file

    def counting(path: pathlib.Path, base: pathlib.Path, project_root: pathlib.Path) -> auditme.phaseb.testmap.ParsedFile:
        parsed.append(path)
        return original(path, base, project_root)

    monkeypatch.setattr(auditme.phaseb.testmap, 'read_test_file', counting)
    auditme.phaseb.testmap.load_test_map(root, 3)
    assert parsed.count(root / 'src/tests/test_mod.py') == 1


CHAIN = {
    'src/pkg/__init__.py': '',
    'src/pkg/mid.py': """
        from pkg.mod import load


        def run():
            return load()
    """,
    'src/pkg/mod.py': """
        def load():
            return 1
    """,
    'src/pkg/top.py': """
        from pkg.mid import run


        def start():
            return run()


        def deep():
            return start()
    """,
    'src/tests/__init__.py': '',
}


def test_caller_route_gives_a_caller_ref_with_via(project: Project) -> None:
    root = project(
        {
            **CHAIN,
            'src/tests/test_mid.py': """
                from pkg.mid import run


                def test_run():
                    run()
            """,
        }
    )
    (ref,) = auditme.phaseb.testmap.load_test_map(root, 3)['src/pkg/mod.py::load']
    assert ref.route == 'caller'
    assert ref.via == 'src/pkg/mid.py::run'
    assert ref.id == 'src/tests/test_mid.py::test_run'


def test_caller_route_is_bounded_by_depth(project: Project) -> None:
    root = project(
        {
            **CHAIN,
            'src/tests/test_top.py': """
                from pkg.top import deep


                def test_deep():
                    deep()
            """,
        }
    )
    assert 'src/pkg/mod.py::load' in auditme.phaseb.testmap.load_test_map(root, 3)
    assert 'src/pkg/mod.py::load' not in auditme.phaseb.testmap.load_test_map(root, 2)
    assert 'src/pkg/mid.py::run' in auditme.phaseb.testmap.load_test_map(root, 2)


def test_direct_and_caller_refs_are_both_kept(project: Project) -> None:
    root = project(
        {
            **CHAIN,
            'src/tests/test_both.py': """
                from pkg.mid import run
                from pkg.mod import load


                def test_load():
                    load()


                def test_run():
                    run()
            """,
        }
    )
    refs = auditme.phaseb.testmap.load_test_map(root, 3)['src/pkg/mod.py::load']
    assert [(ref.id.split('::')[1], ref.route) for ref in refs] == [('test_load', 'direct'), ('test_run', 'caller')]


def test_a_call_cycle_terminates(project: Project) -> None:
    root = project(
        {
            'src/pkg/__init__.py': '',
            'src/pkg/cyc.py': """
                def ping():
                    return pong()


                def pong():
                    return ping()
            """,
            'src/tests/__init__.py': '',
            'src/tests/test_cyc.py': """
                from pkg.cyc import ping


                def test_ping():
                    ping()
            """,
        }
    )
    refs = auditme.phaseb.testmap.load_test_map(root, 10)
    assert refs['src/pkg/cyc.py::ping'][0].route == 'direct'
    assert refs['src/pkg/cyc.py::pong'][0].route == 'caller'


def test_callers_lists_functions_reaching_the_target_within_depth(project: Project) -> None:
    root = project(CHAIN)
    index = auditme.phaseb.testmap.load_test_index(root)
    found = index.callers('src/pkg/mod.py::load', 2)
    assert [caller['id'] for caller in found] == ['src/pkg/mid.py::run', 'src/pkg/top.py::start']
    assert found[0] == {'id': 'src/pkg/mid.py::run', 'path': 'src/pkg/mid.py', 'start': 4, 'end': 5}
    assert [caller['id'] for caller in index.callers('src/pkg/mod.py::load', 1)] == ['src/pkg/mid.py::run']


def test_test_files_holds_mirror_importers_and_caller_importers(project: Project) -> None:
    root = project(
        {
            **CHAIN,
            'src/tests/pkg/__init__.py': '',
            'src/tests/pkg/test_mod.py': 'def test_nothing():\n    pass\n',
            'src/tests/test_importer.py': 'import pkg.mod\n\n\ndef test_x():\n    pass\n',
            'src/tests/test_caller.py': 'from pkg import mid\n\n\ndef test_y():\n    pass\n',
            'src/tests/test_other.py': 'from pkg import top\n\n\ndef test_z():\n    pass\n',
        }
    )
    index = auditme.phaseb.testmap.load_test_index(root)
    assert index.test_files('src/pkg/mod.py::load', 1) == [
        'src/tests/pkg/test_mod.py',
        'src/tests/test_caller.py',
        'src/tests/test_importer.py',
    ]
    assert 'src/tests/test_other.py' in index.test_files('src/pkg/mod.py::load', 2)


def test_test_files_hold_a_file_importing_only_the_package_re_export(project: Project) -> None:
    """A test reaching the candidate through the package's re-export is listed (review of 2026-11-21, D7)."""
    root = project(
        {
            'src/pkg/__init__.py': 'from pkg.mod import load\n\n__all__ = ["load"]\n',
            'src/pkg/mod.py': 'def load(path):\n    return path\n',
            'src/pkg/other.py': 'def other():\n    return 1\n',
            'src/tests/test_from_package.py': 'from pkg import load\n\n\ndef test_load():\n    assert load("x") == "x"\n',
            'src/tests/test_import_package.py': 'import pkg\n\n\ndef test_load():\n    assert pkg.load("x") == "x"\n',
            'src/tests/test_unrelated.py': 'from pkg import other\n\n\ndef test_other():\n    assert other.other() == 1\n',
        }
    )
    index = auditme.phaseb.testmap.load_test_index(root)
    assert index.test_files('src/pkg/mod.py::load', 1) == [
        'src/tests/test_from_package.py',
        'src/tests/test_import_package.py',
    ]


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    edges=hypothesis.strategies.dictionaries(
        hypothesis.strategies.sampled_from('abcde'), hypothesis.strategies.lists(hypothesis.strategies.sampled_from('abcde'), max_size=3), max_size=5
    ),
    start=hypothesis.strategies.lists(hypothesis.strategies.sampled_from('abcde'), min_size=1, max_size=2, unique=True),
    depth=hypothesis.strategies.integers(0, 4),
)
def test_reach_matches_a_breadth_first_search_and_grows_with_depth(edges: dict[str, list[str]], start: list[str], depth: int) -> None:
    reached = auditme.phaseb.testmap.reach(edges, start, depth)
    expected = dict.fromkeys(start, 0)
    queue = list(start)
    while queue:
        name = queue.pop(0)
        for callee in edges.get(name, []):
            if callee not in expected and expected[name] < depth:
                expected[callee] = expected[name] + 1
                queue.append(callee)
    assert reached == expected
    assert all(0 <= distance <= depth for distance in reached.values())
    deeper = auditme.phaseb.testmap.reach(edges, start, depth + 1)
    assert all(deeper[name] == distance for name, distance in reached.items())
