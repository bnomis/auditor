"""Tests for the architecture listers and their shared helpers."""

import ast
import collections.abc
import pathlib

import auditme.core
import auditme.rules.error_handling
import pytest
from auditme import phaseb
from auditme.phaseb import architecture

Project = collections.abc.Callable[[dict[str, str]], pathlib.Path]

SILENT = """
def load():
    try:
        return 1
    except Exception:
        pass
"""

ACCEPTED = """
def load():
    try:
        return 1
    except Exception:  # auditme: accept[silent-broad-except] probe
        pass
"""


def _boom(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    raise RuntimeError('boom')


# capture_hits


def test_capture_hits_returns_rule_path_line_triples(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    hits = architecture.capture_hits(root, [auditme.rules.error_handling.check_silent_broad_except])
    assert hits == {('silent-broad-except', 'src/pkg/mod.py', 4)}


def test_capture_hits_includes_accepted_hits(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': ACCEPTED})
    hits = architecture.capture_hits(root, [auditme.rules.error_handling.check_silent_broad_except])
    assert hits == {('silent-broad-except', 'src/pkg/mod.py', 4)}


def test_capture_hits_restores_emitted_and_prints_nothing(project: Project, capsys: pytest.CaptureFixture[str]) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    auditme.core._EMITTED.clear()
    auditme.core._EMITTED.add('earlier')
    architecture.capture_hits(root, [auditme.rules.error_handling.check_silent_broad_except])
    assert {'earlier'} == auditme.core._EMITTED
    assert capsys.readouterr().out == ''
    auditme.core._EMITTED.clear()


def test_capture_hits_names_a_check_that_raises(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    with pytest.raises(phaseb.PhaseBError, match='_boom'):
        architecture.capture_hits(root, [_boom])


# shared


def test_unparseable_file_raises_naming_it(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/bad.py': 'def (:\n'})
    with pytest.raises(phaseb.PhaseBError, match='bad.py'):
        architecture.parse_audited_files(root)


def test_parse_audited_files_returns_each_file(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    assert {file.rel for file in architecture.parse_audited_files(root)} == {'src/pkg/__init__.py', 'src/pkg/mod.py'}


def test_site_counter_numbers_sites_per_qualname() -> None:
    counter = architecture.SiteCounter()
    assert counter.next('pkg.mod.f') == 1
    assert counter.next('pkg.mod.f') == 2
    assert counter.next('pkg.mod.g') == 1
    assert counter.next('pkg.mod.f') == 3


def test_walk_with_qualname_names_functions_methods_and_module_level() -> None:
    tree = ast.parse('x = 1\n\n\ndef f():\n    y = 2\n\n\nclass C:\n    def m(self):\n        z = 3\n')
    found = {qualname for qualname, node in architecture.walk_with_qualname(tree) if isinstance(node, ast.Assign)}
    assert found == {'<module>', 'f', 'C.m'}


def test_hit_on_anchor_matches_rule_path_and_line() -> None:
    hits = {('silent-broad-except', 'src/pkg/mod.py', 4)}
    assert architecture.hit_on_anchor(hits, 'src/pkg/mod.py', [3, 4], ('silent-broad-except',))
    assert not architecture.hit_on_anchor(hits, 'src/pkg/mod.py', [3], ('silent-broad-except',))
    assert not architecture.hit_on_anchor(hits, 'src/pkg/other.py', [4], ('silent-broad-except',))
    assert not architecture.hit_on_anchor(hits, 'src/pkg/mod.py', [4], ('other-rule',))
