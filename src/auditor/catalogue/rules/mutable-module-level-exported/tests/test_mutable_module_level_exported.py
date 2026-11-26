"""Tests for the checks of the `mutable-module-level-exported` rule."""

import collections.abc
import pathlib

import pytest

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

MUTABLE_EXPORT = auditor.testing.load_check(__file__)


def test_a_mutable_global_imported_elsewhere_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/settings.py': "DEFAULTS = {'a': 1}\n",
            'src/probe/user.py': 'from probe.settings import DEFAULTS\n\nVALUE = DEFAULTS\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('mutable-module-level-exported', 'src/probe/settings.py')]
    assert 'types.MappingProxyType(...)' in hits[0]['variant']
    assert hits[0]['related'] == ['src/probe/user.py']


def test_a_mutable_global_read_by_attribute_access_is_a_hit(project: Builder, run_check: Runner) -> None:
    """The project standard is dotted access, so both forms must count."""
    root = project(
        {
            'src/probe/settings.py': 'DEFAULTS = [1, 2]\n',
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert len(hits) == 1
    assert 'tuple(...)' in hits[0]['variant']


def test_a_mutable_global_nobody_imports_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/settings.py': "DEFAULTS = {'a': 1}\n"})
    assert run_check(MUTABLE_EXPORT, root) == []


def test_an_immutably_wrapped_global_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/settings.py': "import types\n\nDEFAULTS = types.MappingProxyType({'a': 1})\n",
            'src/probe/user.py': 'from probe.settings import DEFAULTS\n\nVALUE = DEFAULTS\n',
        }
    )
    assert run_check(MUTABLE_EXPORT, root) == []


def test_a_reader_in_a_sibling_package_still_counts(project: Builder, run_check: Runner) -> None:
    """The driver sweeps one package per pass; readers live in all of them.

    A project whose `src/` holds the library and the test tree keeps its
    cross-module readers in the sibling package, so a reader scan rooted at the
    package under audit sees none of them and the export reads as private.
    """
    root = project(
        {
            'src/probe/settings.py': "DEFAULTS = {'a': 1}\n",
            'src/tests/test_settings.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('mutable-module-level-exported', 'src/probe/settings.py')]


def test_a_mutable_global_built_by_a_comprehension_is_a_hit(project: Builder, run_check: Runner) -> None:
    """`{k: f(k) for k in ...}` is the same mutable dict `{...}` is."""
    root = project(
        {
            'src/probe/settings.py': 'MODES = {name: name.upper() for name in ("a", "b")}\n',
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.MODES\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert len(hits) == 1
    assert 'dict comprehension' in hits[0]['variant']
    assert 'types.MappingProxyType(...)' in hits[0]['variant']


def test_an_annotated_mutable_global_is_a_hit(project: Builder, run_check: Runner) -> None:
    """An annotation is not a wrapper: `typing.Mapping` over a dict still mutates."""
    root = project(
        {
            'src/probe/settings.py': 'import typing\n\nDEFAULTS: typing.Mapping[str, int] = {"a": 1}\n',
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('mutable-module-level-exported', 3)]


def test_a_global_built_by_a_call_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """A `Call` value's type is not knowable from the assignment; see the
    rejected widening in the rule's `rule.md`."""
    root = project(
        {
            'src/probe/settings.py': 'import probe.factory\n\nDEFAULTS = probe.factory.build()\n',
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    assert run_check(MUTABLE_EXPORT, root) == []


@pytest.mark.parametrize(
    ('value', 'shape', 'wrap'),
    [
        ("list(('a', 'b'))", 'list constructor call', 'tuple(...)'),
        ('dict(a=1)', 'dict constructor call', 'types.MappingProxyType(...)'),
        ("set(('a', 'b'))", 'set constructor call', 'frozenset(...)'),
    ],
)
def test_a_global_built_by_a_builtin_constructor_is_a_hit(project: Builder, run_check: Runner, value: str, shape: str, wrap: str) -> None:
    """`list(...)`, `dict(...)` and `set(...)` state their type in the
    assignment, as a literal does (ruled 2026-10-31, on an audit's request)."""
    root = project(
        {
            'src/probe/settings.py': f'NAMES = {value}\n',
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.NAMES\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert len(hits) == 1
    assert shape in hits[0]['variant']
    assert wrap in hits[0]['variant']


@pytest.mark.parametrize('value', ["tuple(['a'])", "frozenset({'a'})", 'probe.factory.list()', "sorted(['a'])"])
def test_an_immutable_or_untyped_call_is_not_a_hit(project: Builder, run_check: Runner, value: str) -> None:
    """Only the three mutable builtin constructors join the literals: an
    immutable builtin, a method named like one, and any other call stay out."""
    root = project(
        {
            'src/probe/settings.py': f'import probe.factory\n\nNAMES = {value}\n',
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.NAMES\n',
        }
    )
    assert run_check(MUTABLE_EXPORT, root) == []


def test_a_scoped_accept_marker_dismisses_the_mutable_export(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/settings.py': "DEFAULTS = {'a': 1}  # auditme: accept[mutable-module-level-exported] callers copy\n",
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert [(hit['accepted'], hit['accepted_reason']) for hit in hits] == [(True, 'callers copy')]


def test_a_reader_that_goes_through_sys_modules_still_counts(project: Builder, run_check: Runner) -> None:
    """`sys.modules['pkg.mod'].NAME` reads what `pkg.mod.NAME` reads.

    It is the documented way to reach a module without importing it, used to
    break a package-initialisation ordering cycle - so the projects most
    careful about import cycles were the ones this scan could not see.
    """
    root = project(
        {
            'src/probe/search.py': 'SOURCE_MAX_BATCH_SIZE = {"pubmed": 200}\n',
            'src/tests/test_search.py': "import sys\n\nVALUE = sys.modules['probe.search'].SOURCE_MAX_BATCH_SIZE\n",
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('mutable-module-level-exported', 'src/probe/search.py')]


def test_a_reader_under_a_computed_sys_modules_key_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """A computed key names no module the scan can know."""
    root = project(
        {
            'src/probe/search.py': 'SOURCE_MAX_BATCH_SIZE = {"pubmed": 200}\n',
            'src/tests/test_search.py': "import sys\n\nNAME = 'probe.search'\nVALUE = sys.modules[NAME].SOURCE_MAX_BATCH_SIZE\n",
        }
    )
    assert run_check(MUTABLE_EXPORT, root) == []


def test_a_reader_in_a_script_root_still_counts(project: Builder, run_check: Runner) -> None:
    """A script in `bin/` is a reader on the same argument a sibling package is."""
    root = project(
        {
            'src/probe/settings.py': "DEFAULTS = {'a': 1}\n",
            'bin/probe-report.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('mutable-module-level-exported', 'src/probe/settings.py')]


def test_a_mutable_global_in_a_script_root_is_a_hit(project: Builder, run_check: Runner) -> None:
    """`bin/` is swept as its own root, so its own exports are candidates."""
    root = project(
        {
            'bin/shared.py': "DEFAULTS = {'a': 1}\n",
            'bin/report.py': 'import bin.shared\n\nVALUE = bin.shared.DEFAULTS\n',
            'src/probe/mod.py': 'x = 1\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root, src_root='bin')
    assert [(hit['rule'], hit['path']) for hit in hits] == [('mutable-module-level-exported', 'bin/shared.py')]
