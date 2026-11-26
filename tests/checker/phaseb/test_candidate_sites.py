"""Tests for the helpers the listers share: capture_hits, the parsed-source index, qualnames and anchors."""

import ast
import collections.abc
import pathlib

import hypothesis
import hypothesis.strategies
import pytest

import auditor.api
import auditor.core
import auditor.phaseb
import auditor.phaseb.candidates

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


def silent_broad_except_hits(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """A check that reports each `silent-broad-except` site, as the A19 lister's helper does."""
    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in auditor.api.silent_broad_except_sites(tree):
            auditor.api.emit_site(scope, path, 'silent-broad-except', node.lineno)


def raise_boom(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    raise RuntimeError('boom')


def test_capture_hits_returns_rule_path_line_triples(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    hits = auditor.api.capture_hits(root, [silent_broad_except_hits])
    assert hits == {('silent-broad-except', 'src/pkg/mod.py', 4)}


def test_capture_hits_includes_accepted_hits(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': ACCEPTED})
    hits = auditor.api.capture_hits(root, [silent_broad_except_hits])
    assert hits == {('silent-broad-except', 'src/pkg/mod.py', 4)}


def test_capture_hits_restores_emitted_and_prints_nothing(project: Project, capsys: pytest.CaptureFixture[str]) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    auditor.core.EMITTED.clear()
    auditor.core.EMITTED.add('earlier')
    auditor.api.capture_hits(root, [silent_broad_except_hits])
    assert {'earlier'} == auditor.core.EMITTED
    assert capsys.readouterr().out == ''
    auditor.core.EMITTED.clear()


def test_capture_hits_names_a_check_that_raises(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    with pytest.raises(auditor.phaseb.PhaseBError, match='raise_boom'):
        auditor.api.capture_hits(root, [raise_boom])


def test_unparseable_file_raises_naming_it(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/bad.py': 'def (:\n'})
    with pytest.raises(auditor.phaseb.PhaseBError, match='bad.py'):
        auditor.api.read_audited_files(root)


def test_parse_audited_files_returns_each_file(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SILENT})
    assert {file.rel for file in auditor.api.read_audited_files(root)} == {'src/pkg/__init__.py', 'src/pkg/mod.py'}


def test_site_counter_numbers_sites_per_qualname() -> None:
    counter = auditor.api.SiteCounter()
    assert counter.next('pkg.mod.f') == 1
    assert counter.next('pkg.mod.f') == 2
    assert counter.next('pkg.mod.g') == 1
    assert counter.next('pkg.mod.f') == 3


def test_walk_with_qualname_names_functions_methods_and_module_level() -> None:
    tree = ast.parse('x = 1\n\n\ndef f():\n    y = 2\n\n\nclass C:\n    def m(self):\n        z = 3\n')
    found = {qualname for qualname, node in auditor.api.walk_with_qualname(tree) if isinstance(node, ast.Assign)}
    assert found == {'<module>', 'f', 'C.m'}


def test_hit_on_anchor_matches_rule_path_and_line() -> None:
    hits = {('silent-broad-except', 'src/pkg/mod.py', 4)}
    assert auditor.api.hit_on_anchor(hits, 'src/pkg/mod.py', [3, 4], ('silent-broad-except',))
    assert not auditor.api.hit_on_anchor(hits, 'src/pkg/mod.py', [3], ('silent-broad-except',))
    assert not auditor.api.hit_on_anchor(hits, 'src/pkg/other.py', [4], ('silent-broad-except',))
    assert not auditor.api.hit_on_anchor(hits, 'src/pkg/mod.py', [4], ('other-rule',))


DOTTED = hypothesis.strategies.from_regex(r'[a-z]{1,4}(\.[a-z]{1,4}){0,2}', fullmatch=True)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(qualname=DOTTED, name=hypothesis.strategies.from_regex(r'[A-Za-z_]{1,6}', fullmatch=True))
def test_child_qualname_ends_in_the_name_and_splits_back(qualname: str, name: str) -> None:
    child = auditor.api.child_qualname(qualname, name)
    assert child.rsplit('.', 1) == [qualname, name]
    assert auditor.api.child_qualname(auditor.api.MODULE_QUALNAME, name) == name


ANCHOR_HIT = hypothesis.strategies.tuples(
    hypothesis.strategies.sampled_from('abc'), hypothesis.strategies.sampled_from(['x.py', 'y.py']), hypothesis.strategies.integers(1, 5)
)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    hits=hypothesis.strategies.sets(ANCHOR_HIT, max_size=6),
    extra=hypothesis.strategies.sets(ANCHOR_HIT, max_size=3),
    lines=hypothesis.strategies.lists(hypothesis.strategies.integers(1, 5), max_size=3),
    rules=hypothesis.strategies.lists(hypothesis.strategies.sampled_from('abc'), max_size=3),
)
def test_hit_on_anchor_matches_the_cross_product_and_is_monotone(hits, extra, lines, rules) -> None:
    check = auditor.api.hit_on_anchor
    expected = any((rule, 'x.py', line) in hits for rule in rules for line in lines)
    assert check(hits, 'x.py', lines, rules) == expected
    if expected:
        assert check(hits | extra, 'x.py', lines, rules)


def test_capture_hits_resolves_the_audit_roots_once_for_all_its_checks(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': 'X = 1\n'})
    auditor.core.clear_source_cache()
    calls: list[pathlib.Path] = []
    real = auditor.core.audit_roots

    def counting(scope: pathlib.Path) -> list[pathlib.Path]:
        calls.append(scope)
        return real(scope)

    def first(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        pass

    def second(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        pass

    monkeypatch.setattr(auditor.core, 'audit_roots', counting)
    auditor.api.capture_hits(root, [first, second])
    assert len(calls) == 1
