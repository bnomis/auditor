"""Tests for the declared audit roots: `[tool.auditme]` in `pyproject.toml`."""

import collections.abc
import pathlib

import auditme.core
import pytest

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]

LAYOUT = {
    'bin/tool.py': 'x = 1\n',
    'checks/audit.py': 'x = 1\n',
    'checks/pkg/mod.py': 'x = 1\n',
    'checks/pkg/sub/deep.py': 'x = 1\n',
    'src/lib/core.py': 'x = 1\n',
    'tests/test_a.py': 'x = 1\n',
}


def declare(project: Builder, table: str, files: dict[str, str] | None = None) -> pathlib.Path:
    return project({**(LAYOUT if files is None else files), 'pyproject.toml': table})


def test_declared_list_is_returned_in_order_and_replaces_defaults(project: Builder) -> None:
    root = declare(project, '[tool.auditme]\nroots = [{ path = "tests" }, { path = "checks/pkg" }]\n')
    assert auditme.core.audit_roots(root) == [root / 'tests', root / 'checks/pkg']


def test_top_level_root_sweeps_only_its_own_files_named_by_stem(project: Builder) -> None:
    root = declare(project, '[tool.auditme]\nroots = [{ path = "checks", modules = "top-level" }, { path = "checks/pkg" }]\n')
    top, pkg = auditme.core.audit_roots(root)
    assert auditme.core.all_py_files(top) == [root / 'checks/audit.py']
    assert auditme.core.module_dotted(root / 'checks/audit.py', top) == 'audit'
    assert auditme.core.all_py_files(pkg) == [root / 'checks/pkg/mod.py', root / 'checks/pkg/sub/deep.py']


def test_package_root_names_modules_after_the_root(project: Builder) -> None:
    root = declare(project, '[tool.auditme]\nroots = [{ path = "checks/pkg" }]\n')
    (pkg,) = auditme.core.audit_roots(root)
    assert auditme.core.module_dotted(root / 'checks/pkg/sub/deep.py', pkg) == 'pkg.sub.deep'


def test_no_table_gives_the_default_roots(project: Builder) -> None:
    root = declare(project, '[project]\nname = "probe"\n')
    assert auditme.core.audit_roots(root) == [root / 'src/lib', root / 'bin']


def test_no_pyproject_gives_the_default_roots(project: Builder) -> None:
    root = project(LAYOUT)
    assert auditme.core.declared_roots(root) is None
    assert auditme.core.audit_roots(root) == [root / 'src/lib', root / 'bin']


def test_defaults_reset_the_modes_of_an_earlier_declaration(project: Builder, tmp_path_factory: pytest.TempPathFactory) -> None:
    root = declare(project, '[tool.auditme]\nroots = [{ path = "checks", modules = "top-level" }]\n')
    auditme.core.audit_roots(root)
    assert auditme.core.ROOT_MODULES
    other = tmp_path_factory.mktemp('other')
    (other / 'bin').mkdir()
    (other / 'bin/x.py').write_text('x = 1\n')
    auditme.core.audit_roots(other)
    assert not auditme.core.ROOT_MODULES


@pytest.mark.parametrize(
    ('table', 'message'),
    [
        ('[tool]\nauditme = 3\n', r'pyproject.toml \[tool.auditme\]: must be a table'),
        ('[tool.auditme]\nroots = 3\n', 'roots must be a list of tables'),
        ('[tool.auditme]\nroots = ["tests"]\n', 'roots must be a list of tables'),
        ('[tool.auditme]\nroots = [{ modules = "package" }]\n', 'has no path'),
        ('[tool.auditme]\nroots = [{ path = "tests", colour = "red" }]\n', "unknown key 'colour'"),
        ('[tool.auditme]\nroots = [{ path = "tests", modules = "flat" }]\n', "modules must be 'package' or 'top-level'"),
        ('[tool.auditme]\nroots = [{ path = "nowhere" }]\n', 'declared root nowhere not found'),
        ('[tool.auditme]\nroots = [{ path = "empty" }]\n', r'declared root empty holds no \.py file'),
        ('[tool.auditme]\nroots = [{ path = "checks" }, { path = "checks/pkg" }]\n', 'declared roots checks and checks/pkg overlap'),
        ('[tool.auditme]\nroots = [{ path = "checks/pkg" }, { path = "checks" }]\n', 'declared roots checks/pkg and checks overlap'),
        ('[tool.auditme]\nroots = [{ path = "checks" }, { path = "checks", modules = "top-level" }]\n', 'overlap'),
        ('[tool.auditme]\nroots = [{ path = "checks/pkg" }, { path = "checks/pkg/sub", modules = "top-level" }]\n', 'overlap'),
        ('[tool.auditme\nroots = [\n', 'pyproject.toml: '),
    ],
)
def test_invalid_declarations_raise_roots_error(project: Builder, table: str, message: str) -> None:
    root = declare(project, table, {**LAYOUT, 'empty/data.txt': 'x\n'})
    with pytest.raises(auditme.core.RootsError, match=message):
        auditme.core.audit_roots(root)


def test_a_top_level_root_with_only_subdirectory_files_holds_no_py_file(project: Builder) -> None:
    root = declare(project, '[tool.auditme]\nroots = [{ path = "src", modules = "top-level" }]\n')
    with pytest.raises(auditme.core.RootsError, match=r'holds no \.py file'):
        auditme.core.audit_roots(root)


def test_a_package_inside_a_top_level_root_is_not_an_overlap(project: Builder) -> None:
    root = declare(project, '[tool.auditme]\nroots = [{ path = "checks", modules = "top-level" }, { path = "checks/pkg" }]\n')
    assert len(auditme.core.audit_roots(root)) == 2


def test_invalid_toml_without_the_table_gives_the_defaults(project: Builder) -> None:
    root = declare(project, 'this is = not [valid\n')
    assert auditme.core.declared_roots(root) is None
    assert auditme.core.audit_roots(root) == [root / 'src/lib', root / 'bin']


def test_corpus_py_files_spans_the_declared_roots(project: Builder) -> None:
    root = declare(project, '[tool.auditme]\nroots = [{ path = "checks", modules = "top-level" }, { path = "tests" }]\n')
    assert auditme.core.corpus_py_files(root, root / 'tests') == [root / 'checks/audit.py', root / 'tests/test_a.py']
