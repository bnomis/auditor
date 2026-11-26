"""Tests for the shared helpers every check depends on.

These are the pieces whose failure is silent: an acceptance rule that matches
too widely turns real findings into dismissed ones, and a duplicate suppressor
that matches too widely drops findings outright.
"""

import ast
import collections.abc
import io
import json
import pathlib

import hypothesis
import hypothesis.strategies
import pytest

import auditor.core

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]


def test_a_marker_on_the_hit_line_accepts_it() -> None:
    lines = ["usage = parsed.get('usage', {})  # auditme: accept schema forbids null"]
    assert auditor.core.accept_reason(lines, 1) == 'schema forbids null'


def test_a_marker_on_the_preceding_line_accepts_the_hit() -> None:
    lines = ['# auditme: accept schema forbids null', "usage = parsed.get('usage', {})"]
    assert auditor.core.accept_reason(lines, 2) == 'schema forbids null'


def test_a_marker_on_the_following_line_does_not_accept_the_hit() -> None:
    lines = ["usage = parsed.get('usage', {})", '# auditme: accept schema forbids null']
    assert auditor.core.accept_reason(lines, 1) is None


def test_a_marker_inside_a_multi_line_node_accepts_it() -> None:
    lines = [
        'result = call(',
        '    # auditme: accept deliberate',
        ')',
    ]
    assert auditor.core.accept_reason(lines, 1, end_lineno=3) == 'deliberate'
    assert auditor.core.accept_reason(lines, 1) is None


TWO_MARKERS = ['x = obj.attr  # auditme: accept[rule-a] reason a  # auditme: accept[rule-b] reason b']


def test_each_of_two_markers_on_one_line_answers_for_its_rule() -> None:
    assert auditor.core.accept_reason(TWO_MARKERS, 1, rule='rule-a') == 'reason a'
    assert auditor.core.accept_reason(TWO_MARKERS, 1, rule='rule-b') == 'reason b'


def test_two_markers_on_one_line_do_not_accept_a_third_rule() -> None:
    assert auditor.core.accept_reason(TWO_MARKERS, 1, rule='rule-c') is None


def test_a_marker_with_no_reason_still_accepts() -> None:
    lines = ['x = 1  # auditme: accept']
    assert auditor.core.accept_reason(lines, 1) == 'no reason given'


def test_a_scoped_marker_accepts_only_its_own_rule() -> None:
    lines = ['x = 1  # auditme: accept[failure-as-absence] the caller reads batch.error']
    assert auditor.core.accept_reason(lines, 1, rule='failure-as-absence') == 'the caller reads batch.error'
    assert auditor.core.accept_reason(lines, 1, rule='silent-broad-except') is None


def test_an_unscoped_marker_accepts_every_rule() -> None:
    """Retained so no marker written before scoping existed needs migrating."""
    lines = ['x = 1  # auditme: accept weighed and kept']
    assert auditor.core.accept_reason(lines, 1, rule='failure-as-absence') == 'weighed and kept'
    assert auditor.core.accept_reason(lines, 1, rule='silent-broad-except') == 'weighed and kept'


def test_a_caller_that_names_no_rule_matches_a_scoped_marker() -> None:
    lines = ['x = 1  # auditme: accept[failure-as-absence] the caller reads batch.error']
    assert auditor.core.accept_reason(lines, 1) == 'the caller reads batch.error'


def test_a_line_number_outside_the_file_is_not_an_error() -> None:
    assert auditor.core.accept_reason(['x = 1'], 99) is None


def test_an_identical_hit_is_emitted_once(capsys: pytest.CaptureFixture[str]) -> None:
    """The driver runs project-level checks once per package under `src/`."""
    for _ in range(3):
        auditor.core.emit(rule='lockfile-drift', variant='stale', path='uv.lock', line=None, evidence='x', accepted=False, accepted_reason=None)
    assert len(capsys.readouterr().out.splitlines()) == 1


def test_hits_differing_in_any_field_are_both_emitted(capsys: pytest.CaptureFixture[str]) -> None:
    auditor.core.emit(rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    auditor.core.emit(rule='r', variant='v', path='a.py', line=2, evidence='x', accepted=False, accepted_reason=None)
    assert len(capsys.readouterr().out.splitlines()) == 2


def test_an_emitted_hit_carries_the_documented_schema(capsys: pytest.CaptureFixture[str]) -> None:
    auditor.core.emit(rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    record = json.loads(capsys.readouterr().out)
    assert set(record) == {'accepted', 'accepted_reason', 'evidence', 'line', 'path', 'rule', 'variant'}


def test_a_hit_with_no_related_serialises_without_the_key(capsys: pytest.CaptureFixture[str]) -> None:
    auditor.core.emit(rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    auditor.core.emit(related=[], rule='r', variant='v', path='a.py', line=2, evidence='x', accepted=False, accepted_reason=None)
    first, second = capsys.readouterr().out.splitlines()
    assert first == '{"accepted": false, "accepted_reason": null, "evidence": "x", "line": 1, "path": "a.py", "rule": "r", "variant": "v"}'
    assert 'related' not in second


def test_related_is_sorted_deduplicated_and_never_names_the_hit_s_own_path(capsys: pytest.CaptureFixture[str]) -> None:
    auditor.core.emit(related=['c.py', 'b.py', 'b.py', 'a.py'], rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    auditor.core.emit(related=['a.py'], rule='r', variant='v', path='a.py', line=2, evidence='x', accepted=False, accepted_reason=None)
    first, second = (json.loads(line) for line in capsys.readouterr().out.splitlines())
    assert first['related'] == ['b.py', 'c.py']
    assert 'related' not in second


def test_lazy_import_pairs_are_read_from_the_agents_table(project: Builder) -> None:
    root = project(
        {
            'AGENTS.md': """
            ## Accepted lazy imports

            | Importer | Imported | Reason |
            |----------|----------|--------|
            | `probe.cli` | `probe.heavy` | startup cost |
            """
        }
    )
    assert auditor.core.accepted_lazy_imports(root) == {('probe.cli', 'probe.heavy')}


def test_a_project_with_no_agents_file_accepts_no_lazy_imports(tmp_path: pathlib.Path) -> None:
    assert auditor.core.accepted_lazy_imports(tmp_path) == set()


def test_accepted_lazy_imports_reads_the_file_once_per_run(tmp_path: pathlib.Path) -> None:
    auditor.core.clear_source_cache()
    agents = tmp_path / 'AGENTS.md'
    agents.write_text('| `a.b` | `c.d` |\n', encoding='utf-8')
    assert auditor.core.accepted_lazy_imports(tmp_path) == {('a.b', 'c.d')}
    agents.write_text('| `x.y` | `z.w` |\n', encoding='utf-8')
    assert auditor.core.accepted_lazy_imports(tmp_path) == {('a.b', 'c.d')}


def test_cached_per_run_computes_once_per_name_and_scope(tmp_path: pathlib.Path) -> None:
    auditor.core.clear_source_cache()
    calls: list[pathlib.Path] = []

    def compute(scope: pathlib.Path) -> object:
        calls.append(scope)
        return len(calls)

    first = auditor.core.cached_per_run('probe', tmp_path, compute)
    second = auditor.core.cached_per_run('probe', tmp_path, compute)
    assert first == second == 1
    assert calls == [tmp_path]


def test_cached_per_run_computes_again_after_the_cache_is_cleared(tmp_path: pathlib.Path) -> None:
    auditor.core.clear_source_cache()
    counter = iter(range(1, 10))
    assert auditor.core.cached_per_run('probe', tmp_path, lambda scope: next(counter)) == 1
    auditor.core.clear_source_cache()
    assert auditor.core.cached_per_run('probe', tmp_path, lambda scope: next(counter)) == 2


def test_cached_per_run_keeps_two_names_and_two_scopes_apart(tmp_path: pathlib.Path) -> None:
    auditor.core.clear_source_cache()
    other = tmp_path / 'other'
    assert auditor.core.cached_per_run('a', tmp_path, lambda scope: 'a') == 'a'
    assert auditor.core.cached_per_run('b', tmp_path, lambda scope: 'b') == 'b'
    assert auditor.core.cached_per_run('a', other, lambda scope: 'other') == 'other'


CHECKS_DIR = pathlib.Path(__file__).resolve().parents[2] / 'src' / 'auditor'


def is_cached_roots_call(node: ast.expr) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', None)
    return name == 'cached_roots'


def test_no_check_subscripts_the_result_of_cached_roots() -> None:
    offenders = []
    for path in sorted(CHECKS_DIR.rglob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        offenders.extend(
            f'{path.relative_to(CHECKS_DIR)}:{node.lineno}' for node in ast.walk(tree) if isinstance(node, ast.Subscript) and is_cached_roots_call(node.value)
        )
    assert offenders == []


def test_type_checking_blocks_are_located_by_line() -> None:
    tree = ast.parse('import typing\n\nif typing.TYPE_CHECKING:\n    import probe.cli\n')
    assert 4 in auditor.core.type_checking_linenos(tree)


def test_source_lines_of_a_non_utf8_file_are_empty(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'latin.py'
    path.write_bytes(b"x = '\xff\xfe'\n")
    assert auditor.core.source_lines(path) == []


def test_python_files_are_returned_sorted(project: Builder) -> None:
    """Emission order is part of the output, so file order cannot be arbitrary."""
    root = project({'src/probe/b.py': 'b = 1\n', 'src/probe/a.py': 'a = 1\n', 'src/probe/sub/c.py': 'c = 1\n'})
    found = auditor.core.all_py_files(root / 'src' / 'probe')
    assert [auditor.core.relpath(path, root) for path in found] == [
        'src/probe/a.py',
        'src/probe/b.py',
        'src/probe/sub/c.py',
    ]


def test_emit_writes_one_json_object_per_line(capsys: pytest.CaptureFixture[str]) -> None:
    auditor.core.emit(rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    auditor.core.emit(rule='r', variant='v', path='b.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    for line in io.StringIO(capsys.readouterr().out):
        assert json.loads(line)


# corpus definitions

DEFINITIONS_SOURCE = 'def run() -> None:\n    pass\n\n\nclass Probe:\n    def load(self) -> None:\n        pass\n'


def test_corpus_definitions_default_keys_module_level_functions_only(project: Builder) -> None:
    root = project({'src/pkg/mod.py': DEFINITIONS_SOURCE})
    found = auditor.core.corpus_definitions(root, root / 'src' / 'pkg')
    assert list(found) == ['run']
    node, path = found['run'][0]
    assert isinstance(node, ast.FunctionDef)
    assert auditor.core.relpath(path, root) == 'src/pkg/mod.py'


def test_a_corpus_index_lookup_does_not_list_the_corpus_again_within_a_run(project: Builder, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'src/pkg/mod.py': DEFINITIONS_SOURCE})
    src_root = root / 'src' / 'pkg'
    auditor.core.clear_source_cache()
    listings: list[pathlib.Path] = []
    real = auditor.core.corpus_py_files

    def counting(scope: pathlib.Path, source_root: pathlib.Path) -> list[pathlib.Path]:
        listings.append(source_root)
        return real(scope, source_root)

    monkeypatch.setattr(auditor.core, 'corpus_py_files', counting)
    auditor.core.corpus_index('probe-a', root, src_root, lambda: 1)
    auditor.core.corpus_index('probe-b', root, src_root, lambda: 2)
    assert len(listings) == 1
    auditor.core.clear_source_cache()


def test_a_corpus_index_is_built_once_per_kind_within_a_run(project: Builder) -> None:
    root = project({'src/pkg/mod.py': DEFINITIONS_SOURCE})
    src_root = root / 'src' / 'pkg'
    auditor.core.clear_source_cache()
    builds: list[str] = []

    def build(kind: str) -> collections.abc.Callable[[], str]:
        def run() -> str:
            builds.append(kind)
            return kind

        return run

    assert auditor.core.corpus_index('kind-a', root, src_root, build('kind-a')) == 'kind-a'
    assert auditor.core.corpus_index('kind-a', root, src_root, build('kind-a')) == 'kind-a'
    assert auditor.core.corpus_index('kind-b', root, src_root, build('kind-b')) == 'kind-b'
    assert builds == ['kind-a', 'kind-b']
    auditor.core.clear_source_cache()


def test_a_corpus_index_is_rebuilt_after_a_corpus_file_changes(project: Builder) -> None:
    root = project({'src/pkg/mod.py': DEFINITIONS_SOURCE})
    src_root = root / 'src' / 'pkg'
    auditor.core.clear_source_cache()
    builds: list[int] = []

    def build() -> int:
        builds.append(1)
        return len(builds)

    assert auditor.core.corpus_index('probe', root, src_root, build) == 1
    (src_root / 'mod.py').write_text(DEFINITIONS_SOURCE + '\n\ndef extra() -> None:\n    pass\n', encoding='utf-8')
    assert auditor.core.corpus_index('probe', root, src_root, build) == 2
    auditor.core.clear_source_cache()


def test_a_corpus_index_is_rebuilt_once_a_file_is_added_in_a_later_run(project: Builder) -> None:
    root = project({'src/pkg/mod.py': DEFINITIONS_SOURCE})
    src_root = root / 'src' / 'pkg'
    auditor.core.clear_source_cache()
    builds: list[int] = []

    def build() -> int:
        builds.append(1)
        return len(builds)

    assert auditor.core.corpus_index('probe', root, src_root, build) == 1
    (src_root / 'added.py').write_text(DEFINITIONS_SOURCE, encoding='utf-8')
    auditor.core.clear_source_cache()
    assert auditor.core.corpus_index('probe', root, src_root, build) == 2
    auditor.core.clear_source_cache()


def test_corpus_definitions_skips_a_file_with_a_syntax_error(project: Builder) -> None:
    root = project({'src/pkg/good.py': DEFINITIONS_SOURCE, 'src/pkg/bad.py': 'def broken(:\n'})
    assert list(auditor.core.corpus_definitions(root, root / 'src' / 'pkg')) == ['run']


def test_corpus_definitions_with_classes_adds_classes_and_methods(project: Builder) -> None:
    root = project({'src/pkg/mod.py': DEFINITIONS_SOURCE})
    found = auditor.core.corpus_definitions(root, root / 'src' / 'pkg', classes=True)
    assert sorted(found) == ['Probe', 'load', 'run']
    assert isinstance(found['Probe'][0][0], ast.ClassDef)
    assert isinstance(found['load'][0][0], ast.FunctionDef)
    assert auditor.core.relpath(found['load'][0][1], root) == 'src/pkg/mod.py'


def test_corpus_definitions_keeps_a_name_defined_in_two_modules_twice(project: Builder) -> None:
    root = project({'src/pkg/a.py': 'def run() -> None:\n    pass\n', 'src/pkg/b.py': 'def run() -> None:\n    pass\n'})
    found = auditor.core.corpus_definitions(root, root / 'src' / 'pkg')
    assert [auditor.core.relpath(path, root) for _, path in found['run']] == ['src/pkg/a.py', 'src/pkg/b.py']


# scope walk

SCOPE_SOURCE = (
    'def outer():\n'
    '    if a:\n'
    '        pass\n'
    '    def inner():\n'
    '        if b:\n'
    '            pass\n'
    '    f = lambda: (1 if c else 2)\n'
    '    class Probe:\n'
    '        if d:\n'
    '            pass\n'
)


def test_walk_within_scope_yields_an_if_in_the_body() -> None:
    func = ast.parse(SCOPE_SOURCE).body[0]
    tests = [ast.unparse(n.test) for n in auditor.core.walk_within_scope(func) if isinstance(n, ast.If)]
    assert tests == ['a']


def test_walk_within_scope_does_not_enter_nested_scopes() -> None:
    func = ast.parse(SCOPE_SOURCE).body[0]
    nodes = list(auditor.core.walk_within_scope(func))
    assert not any(isinstance(n, ast.IfExp) for n in nodes)
    assert any(isinstance(n, ast.FunctionDef) and n.name == 'inner' for n in nodes)


# read_is_private

INIT_ALL = "__all__ = ['load', 'Probe']\n"
NO_ALL = 'def load() -> None:\n    pass\n'


def test_is_private_a_name_in_the_package_all_is_public(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': INIT_ALL, 'src/pkg/mod.py': NO_ALL})
    assert not auditor.core.read_is_private('load', 'pkg.mod', root)


def test_is_private_a_name_left_out_of_the_package_all_is_private(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': INIT_ALL, 'src/pkg/mod.py': NO_ALL})
    assert auditor.core.read_is_private('helper', 'pkg.mod', root)


def test_is_private_a_name_in_its_modules_own_all_is_public(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': INIT_ALL, 'src/pkg/mod.py': "__all__ = ['helper']\n"})
    assert not auditor.core.read_is_private('helper', 'pkg.mod', root)


def test_is_private_a_method_follows_its_class(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': INIT_ALL, 'src/pkg/mod.py': NO_ALL})
    assert not auditor.core.read_is_private('Probe.load', 'pkg.mod', root)
    assert auditor.core.read_is_private('Other.load', 'pkg.mod', root)


def test_is_private_without_an_all_only_an_underscore_makes_private(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': NO_ALL, 'src/pkg/_mod.py': NO_ALL})
    assert not auditor.core.read_is_private('load', 'pkg.mod', root)
    assert auditor.core.read_is_private('_load', 'pkg.mod', root)
    assert auditor.core.read_is_private('load', 'pkg._mod', root)
    assert auditor.core.read_is_private('Probe._load', 'pkg.mod', root)


def test_is_private_an_underscore_name_in_an_all_is_public(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': "__all__ = ['_load']\n", 'src/pkg/mod.py': NO_ALL})
    assert not auditor.core.read_is_private('_load', 'pkg.mod', root)


def test_is_private_reads_an_annotated_all(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': "__all__: list[str] = ['load']\n", 'src/pkg/mod.py': NO_ALL})
    assert not auditor.core.read_is_private('load', 'pkg.mod', root)
    assert auditor.core.read_is_private('other', 'pkg.mod', root)


SCRIPT = (
    "import sys\n\n\ndef helper() -> int:\n    return 0\n\n\ndef main() -> int:\n    return helper()\n\n\nif __name__ == '__main__':\n    sys.exit(main())\n"
)


def test_privacy_names_the_all_rule(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': INIT_ALL, 'src/pkg/mod.py': NO_ALL})
    assert auditor.core.privacy('load', 'pkg.mod', root) == (False, auditor.core.PRIVACY_ALL)
    assert auditor.core.privacy('helper', 'pkg.mod', root) == (True, auditor.core.PRIVACY_ALL)


def test_privacy_resolves_the_audit_roots_once_across_many_functions(project: Builder, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'src/pkg/__init__.py': INIT_ALL, 'src/pkg/mod.py': NO_ALL})
    auditor.core.clear_source_cache()
    calls: list[pathlib.Path] = []
    real = auditor.core.audit_roots

    def counting(scope: pathlib.Path) -> list[pathlib.Path]:
        calls.append(scope)
        return real(scope)

    monkeypatch.setattr(auditor.core, 'audit_roots', counting)
    for name in ('load', 'helper', 'other', 'more', 'extra'):
        auditor.core.privacy(name, 'pkg.mod', root)
    assert len(calls) <= 1
    auditor.core.clear_source_cache()


def test_privacy_a_script_is_public_only_through_its_main_guard(project: Builder) -> None:
    root = project({'bin/probe-run.py': SCRIPT})
    assert auditor.core.privacy('main', 'bin.probe-run', root) == (False, auditor.core.PRIVACY_SCRIPT)
    assert auditor.core.privacy('helper', 'bin.probe-run', root) == (True, auditor.core.PRIVACY_SCRIPT)


def test_privacy_reads_the_guard_either_way_round(project: Builder) -> None:
    root = project({'bin/probe.py': SCRIPT.replace("__name__ == '__main__'", "'__main__' == __name__")})
    assert auditor.core.privacy('helper', 'bin.probe', root) == (True, auditor.core.PRIVACY_SCRIPT)


def test_privacy_a_scripts_own_all_wins_over_its_guard(project: Builder) -> None:
    root = project({'bin/probe.py': "__all__ = ['helper']\n" + SCRIPT})
    assert auditor.core.privacy('helper', 'bin.probe', root) == (False, auditor.core.PRIVACY_ALL)
    assert auditor.core.privacy('main', 'bin.probe', root) == (True, auditor.core.PRIVACY_ALL)


def test_privacy_a_module_without_a_guard_falls_back_to_underscores(project: Builder) -> None:
    root = project({'bin/probe.py': 'def helper() -> int:\n    return 0\n'})
    assert auditor.core.privacy('helper', 'bin.probe', root) == (False, auditor.core.PRIVACY_UNDERSCORE)


def test_privacy_a_guarded_module_inside_a_package_is_no_script(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SCRIPT})
    assert auditor.core.privacy('helper', 'pkg.mod', root) == (False, auditor.core.PRIVACY_UNDERSCORE)


def test_privacy_reads_a_script_in_a_top_level_root(project: Builder) -> None:
    root = project(
        {
            'pyproject.toml': "[tool.auditme]\nroots = [{path = 'scripts', modules = 'top-level'}]\n",
            'scripts/probe.py': SCRIPT,
        }
    )
    assert auditor.core.privacy('helper', 'probe', root) == (True, auditor.core.PRIVACY_SCRIPT)
    assert auditor.core.privacy('main', 'probe', root) == (False, auditor.core.PRIVACY_SCRIPT)


def test_privacy_reads_the_all_of_a_module_in_a_top_level_root(project: Builder) -> None:
    root = project(
        {
            'pyproject.toml': "[tool.auditme]\nroots = [{path = 'lib', modules = 'top-level'}]\n",
            'lib/probe.py': "__all__ = ['load']\n" + NO_ALL,
        }
    )
    assert auditor.core.privacy('other', 'probe', root) == (True, auditor.core.PRIVACY_ALL)


def test_describe_error_appends_the_chained_cause() -> None:
    try:
        try:
            raise OSError('disk on fire')
        except OSError as error:
            raise auditor.core.RootsError('cannot read x') from error
    except auditor.core.RootsError as caught:
        assert auditor.core.describe_error(caught) == 'cannot read x (disk on fire)'


def test_describe_error_is_the_bare_message_without_a_cause() -> None:
    assert auditor.core.describe_error(auditor.core.RootsError('plain')) == 'plain'


def test_from_import_bindings_resolve_absolute_and_relative_imports() -> None:
    tree = ast.parse('from a.b import c\nfrom .d import e as f\nfrom ..g import h\nfrom . import i\nimport j\n')
    assert auditor.core.from_import_bindings(tree, 'pkg.sub.mod', False) == {
        'c': 'a.b.c',
        'f': 'pkg.sub.d.e',
        'h': 'pkg.g.h',
        'i': 'pkg.sub.i',
    }


def test_from_import_bindings_resolve_a_package_init_against_itself() -> None:
    tree = ast.parse('from .base import Foo\n')
    assert auditor.core.from_import_bindings(tree, 'pkg.sub', True) == {'Foo': 'pkg.sub.base.Foo'}


def test_call_bindings_add_aliased_plain_imports() -> None:
    tree = ast.parse('from a import b\nimport c.d as e\nimport f.g\n')
    assert auditor.core.call_bindings(tree, 'pkg.mod', False) == {'b': 'a.b', 'e': 'c.d'}


def test_reexport_aliases_follow_a_re_export_of_a_re_export() -> None:
    from_bindings = {
        'pkg': {'run': 'pkg.base.run'},
        'top': {'run': 'pkg.run'},
        'other': {'unrelated': 'elsewhere.thing'},
    }
    assert auditor.core.reexport_aliases(from_bindings, {'pkg.base.run'}) == {
        'pkg.run': 'pkg.base.run',
        'top.run': 'pkg.base.run',
    }


def parse_call(source: str) -> ast.Call:
    node = ast.parse(source, mode='eval').body
    assert isinstance(node, ast.Call)
    return node


def test_resolve_call_reaches_a_same_module_name_an_import_and_an_alias() -> None:
    known: dict[str, str | None] = {'pkg.mod.local': None, 'pkg.other.func': None, 'pkg.mod.Cls.method': 'Cls'}
    imported = {'func': 'pkg.other.func', 'other': 'pkg.other'}
    aliases = {'pkg.reexport.func': 'pkg.other.func'}
    assert auditor.core.resolve_call(parse_call('local()'), 'pkg.mod', None, imported, known, aliases) == 'pkg.mod.local'
    assert auditor.core.resolve_call(parse_call('func()'), 'pkg.mod', None, imported, known, aliases) == 'pkg.other.func'
    assert auditor.core.resolve_call(parse_call('other.func()'), 'pkg.mod', None, imported, known, aliases) == 'pkg.other.func'
    assert auditor.core.resolve_call(parse_call('pkg.reexport.func()'), 'pkg.mod', None, imported, known, aliases) == 'pkg.other.func'
    assert auditor.core.resolve_call(parse_call('self.method()'), 'pkg.mod', 'Cls', imported, known, aliases) == 'pkg.mod.Cls.method'
    assert auditor.core.resolve_call(parse_call('unknown()'), 'pkg.mod', None, imported, known, aliases) is None


def test_resolve_call_resolves_a_class_method_only_when_asked() -> None:
    known: dict[str, str | None] = {'pkg.mod.Cls.build': 'Cls'}
    call = parse_call('Cls.build()')
    assert auditor.core.resolve_call(call, 'pkg.mod', None, {}, known, {}) is None
    assert auditor.core.resolve_call(call, 'pkg.mod', None, {}, known, {}, class_methods=True) == 'pkg.mod.Cls.build'


def test_resolve_call_with_class_methods_resolves_a_plainly_imported_top_level_module() -> None:
    known: dict[str, str | None] = {'script.run': None}
    call = parse_call('script.run()')
    assert auditor.core.resolve_call(call, 'tests.test_script', None, {}, known, {}, class_methods=True) == 'script.run'


def test_reads_by_module_and_name_counts_both_import_spellings(project: Builder) -> None:
    root = project(
        {
            'src/pkg/__init__.py': '',
            'src/pkg/a.py': 'from pkg.b import NAME\n',
            'src/pkg/c.py': 'import pkg.b\n\nvalue = pkg.b.OTHER\n',
        }
    )
    reads = auditor.core.reads_by_module_and_name(root, root / 'src')
    assert [(path.name, line) for path, line in reads[('pkg.b', 'NAME')]] == [('a.py', 1)]
    assert [(path.name, line) for path, line in reads[('pkg.b', 'OTHER')]] == [('c.py', 3)]


PLAIN_LINE = hypothesis.strategies.text(alphabet=hypothesis.strategies.characters(blacklist_characters='#\n\r', blacklist_categories=['Cs']), max_size=30)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    lines=hypothesis.strategies.lists(PLAIN_LINE, max_size=6),
    lineno=hypothesis.strategies.integers(-2, 9),
    end=hypothesis.strategies.none() | hypothesis.strategies.integers(-2, 9),
)
def test_accept_reason_is_none_without_a_marker(lines: list[str], lineno: int, end: int | None) -> None:
    assert auditor.core.accept_reason(lines, lineno, end) is None


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    reason=hypothesis.strategies.text(alphabet='abc xyz', min_size=0, max_size=12),
    rule=hypothesis.strategies.from_regex(r'[a-z][a-z0-9]{0,8}', fullmatch=True),
    other=hypothesis.strategies.from_regex(r'[a-z][a-z0-9]{0,8}', fullmatch=True),
)
def test_accept_reason_answers_with_a_string_and_ignores_another_rules_marker(reason: str, rule: str, other: str) -> None:
    hypothesis.assume(rule != other)
    lines = [f'x = 1  # auditme: accept[{other}] {reason}']
    assert auditor.core.accept_reason(lines, 1, None, rule=rule) is None
    answer = auditor.core.accept_reason(lines, 1, None, rule=other)
    assert isinstance(answer, str)
    assert answer
    assert auditor.core.accept_reason(lines, 1, None) == answer


def test_a_cached_scope_restores_its_own_root_modes(project: Builder) -> None:
    root = project(
        {
            'a/pyproject.toml': "[tool.auditme]\nroots = [{path = 'lib', modules = 'top-level'}]\n",
            'a/lib/mod.py': 'X = 1\n',
            'b/src/pkg/mod.py': 'X = 1\n',
        }
    )
    scope_a = root / 'a'
    scope_b = root / 'b'
    auditor.core.clear_source_cache()
    roots_a, _ = auditor.core.cached_roots(scope_a)
    auditor.core.cached_roots(scope_b)
    auditor.core.cached_roots(scope_a)
    assert auditor.core.ROOT_MODULES.get(roots_a[0]) == auditor.core.TOP_LEVEL
    auditor.core.clear_source_cache()


# cached_bytes


def test_cached_bytes_reads_a_file_once_per_run(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / 'a.txt'
    path.write_bytes(b'one')
    auditor.core.clear_source_cache()
    reads: list[pathlib.Path] = []
    real = pathlib.Path.read_bytes

    def counting(self: pathlib.Path) -> bytes:
        reads.append(self)
        return real(self)

    monkeypatch.setattr(pathlib.Path, 'read_bytes', counting)
    assert auditor.core.cached_bytes(path) == b'one'
    assert auditor.core.cached_bytes(path) == b'one'
    assert reads == [path]


def test_cached_bytes_reads_again_after_the_file_changes_size(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'a.txt'
    path.write_bytes(b'one')
    auditor.core.clear_source_cache()
    assert auditor.core.cached_bytes(path) == b'one'
    path.write_bytes(b'three')
    assert auditor.core.cached_bytes(path) == b'three'


def test_cached_bytes_of_a_missing_path_raises_cached_read_error(tmp_path: pathlib.Path) -> None:
    auditor.core.clear_source_cache()
    with pytest.raises(auditor.core.CachedReadError, match='missing.txt'):
        auditor.core.cached_bytes(tmp_path / 'missing.txt')


def test_is_never_accepted_matches_an_exact_id() -> None:
    assert auditor.core.is_never_accepted('literal-duplication', ('literal-duplication',))
    assert not auditor.core.is_never_accepted('literal-duplication', ('other',))


def test_is_never_accepted_matches_a_family() -> None:
    assert auditor.core.is_never_accepted('leading-underscore-parameter', ('leading-underscore-*',))


def test_is_never_accepted_does_not_match_the_bare_family_prefix() -> None:
    assert not auditor.core.is_never_accepted('leading-underscore', ('leading-underscore-*',))


def test_emit_refuses_an_accepted_hit_of_a_listed_rule(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(auditor.core, 'NEVER_ACCEPTED', ('r',))
    auditor.core.emit(rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=True, accepted_reason='why')
    hit = json.loads(capsys.readouterr().out)
    assert hit['accepted'] is False
    assert hit['accepted_reason'] is None
    assert hit['refused_reason'] == 'why'


def test_emit_leaves_an_accepted_hit_of_an_unlisted_rule(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(auditor.core, 'NEVER_ACCEPTED', ('other',))
    auditor.core.emit(rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=True, accepted_reason='why')
    hit = json.loads(capsys.readouterr().out)
    assert hit['accepted'] is True
    assert hit['accepted_reason'] == 'why'
    assert 'refused_reason' not in hit
