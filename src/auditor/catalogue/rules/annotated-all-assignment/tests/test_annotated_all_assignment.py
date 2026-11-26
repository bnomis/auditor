"""Tests for `annotated-all-assignment`.

The defect: `__all__: list[str] = [...]` is an `ast.AnnAssign`, not an
`ast.Assign`, so a public-surface guard written to match `ast.Assign` skips the
module entirely - reporting green while checking nothing.
"""

import collections.abc
import pathlib
import typing

import auditor.core
import auditor.testing

if typing.TYPE_CHECKING:
    import pytest

RULE = 'annotated-all-assignment'

CHECK = auditor.testing.load_check(__file__)
MODULE = auditor.testing.load_check_module(__file__)

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

# A guard of the shape the rule is about: it walks other modules' ASTs looking
# for an `__all__` declaration, and the string literal is what marks the file
# as reading `__all__` as data rather than declaring one.
AST_GUARD = """
import ast


def declares_all(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == '__all__':
                    return True
    return False
"""

ATTRIBUTE_GUARD = """
import types


def exported_names(module: types.ModuleType) -> list[str]:
    return list(module.__all__)
"""


def test_annotated_all_is_a_hit_when_the_project_guards_all(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/__init__.py': """
            __all__: list[str] = [
                'COMMANDS',
            ]
            """,
            'src/tests/test_package_surfaces.py': AST_GUARD,
        }
    )
    hits = run_check(CHECK, root)
    assert [(hit['rule'], hit['path'], hit['line']) for hit in hits] == [(RULE, 'src/probe/__init__.py', 1)]
    assert not hits[0]['accepted']
    assert hits[0]['evidence'] == '__all__: list[str] = ['


def test_a_guard_that_reads_the_attribute_also_counts(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/__init__.py': "__all__: list[str] = ['thing']\n",
            'src/tests/test_surface.py': ATTRIBUTE_GUARD,
        }
    )
    assert len(run_check(CHECK, root)) == 1


def test_a_project_with_no_guard_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """Nothing to switch off, so the annotated form costs the project nothing."""
    root = project({'src/probe/__init__.py': "__all__: list[str] = ['thing']\n"})
    assert run_check(CHECK, root) == []


def test_the_plain_assignment_form_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/__init__.py': "__all__ = ['thing']\n",
            'src/tests/test_package_surfaces.py': AST_GUARD,
        }
    )
    assert run_check(CHECK, root) == []


def test_an_annotation_on_another_name_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/__init__.py': "EXPORTS: list[str] = ['thing']\n",
            'src/tests/test_package_surfaces.py': AST_GUARD,
        }
    )
    assert run_check(CHECK, root) == []


def test_a_scoped_accept_marker_accepts_the_hit(project: Builder, run_check: Runner) -> None:
    """The sanctioned answer when the guard was taught both assignment forms."""
    root = project(
        {
            'src/probe/__init__.py': """
            # auditme: accept[annotated-all-assignment] declares_all matches AnnAssign too
            __all__: list[str] = [
                'COMMANDS',
            ]
            """,
            'src/tests/test_package_surfaces.py': AST_GUARD,
        }
    )
    hits = run_check(CHECK, root)
    assert len(hits) == 1
    assert hits[0]['accepted']
    assert hits[0]['accepted_reason'] == 'declares_all matches AnnAssign too'


def test_a_marker_scoped_to_another_rule_does_not_accept_the_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/__init__.py': """
            # auditme: accept[def-class-in-init] unrelated decision
            __all__: list[str] = ['thing']
            """,
            'src/tests/test_package_surfaces.py': AST_GUARD,
        }
    )
    hits = run_check(CHECK, root)
    assert len(hits) == 1
    assert not hits[0]['accepted']


def test_the_guard_is_found_in_any_package_not_just_the_audited_one(project: Builder, run_check: Runner) -> None:
    """The declaration and the guard live in different packages under `src/`.

    The check runs once per package, so it has to look project-wide for the
    guard or it would report a hit on the library pass and nothing on the test
    pass, depending on which package it happened to be handed.
    """
    root = project(
        {
            'src/probe/__init__.py': "__all__: list[str] = ['thing']\n",
            'src/othertests/test_surface.py': AST_GUARD,
        }
    )
    assert len(run_check(CHECK, root)) == 1


def test_an_unparseable_file_is_skipped_rather_than_crashing(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/broken.py': 'def parse(:\n',
            'src/probe/__init__.py': "__all__: list[str] = ['thing']\n",
            'src/tests/test_package_surfaces.py': AST_GUARD,
        }
    )
    hits = run_check(CHECK, root)
    assert [hit['path'] for hit in hits] == ['src/probe/__init__.py']


def test_the_all_guard_scan_runs_once_per_sweep_over_two_roots(project: Builder, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'src/probe/a.py': 'x = 1\n', 'src/probe/b.py': "y = getattr(m, '__all__')\n"})
    auditor.core.clear_source_cache()
    calls: list[pathlib.Path] = []
    real = MODULE.scan_has_all_guard

    def counting(scope: pathlib.Path) -> bool:
        calls.append(scope)
        return real(scope)

    monkeypatch.setattr(MODULE, 'scan_has_all_guard', counting)
    answers = [MODULE.project_has_all_guard(root) for _ in range(2)]
    assert answers == [True, True]
    assert calls == [root]
