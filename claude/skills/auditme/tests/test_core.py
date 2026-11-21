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
import typing

import auditme.core
import hypothesis
import hypothesis.strategies

if typing.TYPE_CHECKING:
    import pytest

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]


def test_a_marker_on_the_hit_line_accepts_it() -> None:
    lines = ["usage = parsed.get('usage', {})  # auditme: accept schema forbids null"]
    assert auditme.core.accept_reason(lines, 1) == 'schema forbids null'


def test_a_marker_on_the_preceding_line_accepts_the_hit() -> None:
    lines = ['# auditme: accept schema forbids null', "usage = parsed.get('usage', {})"]
    assert auditme.core.accept_reason(lines, 2) == 'schema forbids null'


def test_a_marker_on_the_following_line_does_not_accept_the_hit() -> None:
    lines = ["usage = parsed.get('usage', {})", '# auditme: accept schema forbids null']
    assert auditme.core.accept_reason(lines, 1) is None


def test_a_marker_inside_a_multi_line_node_accepts_it() -> None:
    lines = [
        'result = call(',
        '    # auditme: accept deliberate',
        ')',
    ]
    assert auditme.core.accept_reason(lines, 1, end_lineno=3) == 'deliberate'
    assert auditme.core.accept_reason(lines, 1) is None


TWO_MARKERS = ['x = obj.attr  # auditme: accept[rule-a] reason a  # auditme: accept[rule-b] reason b']


def test_each_of_two_markers_on_one_line_answers_for_its_rule() -> None:
    assert auditme.core.accept_reason(TWO_MARKERS, 1, rule='rule-a') == 'reason a'
    assert auditme.core.accept_reason(TWO_MARKERS, 1, rule='rule-b') == 'reason b'


def test_two_markers_on_one_line_do_not_accept_a_third_rule() -> None:
    assert auditme.core.accept_reason(TWO_MARKERS, 1, rule='rule-c') is None


def test_a_marker_with_no_reason_still_accepts() -> None:
    lines = ['x = 1  # auditme: accept']
    assert auditme.core.accept_reason(lines, 1) == 'no reason given'


def test_a_scoped_marker_accepts_only_its_own_rule() -> None:
    lines = ['x = 1  # auditme: accept[failure-as-absence] the caller reads batch.error']
    assert auditme.core.accept_reason(lines, 1, rule='failure-as-absence') == 'the caller reads batch.error'
    assert auditme.core.accept_reason(lines, 1, rule='silent-broad-except') is None


def test_an_unscoped_marker_accepts_every_rule() -> None:
    """Retained so no marker written before scoping existed needs migrating."""
    lines = ['x = 1  # auditme: accept weighed and kept']
    assert auditme.core.accept_reason(lines, 1, rule='failure-as-absence') == 'weighed and kept'
    assert auditme.core.accept_reason(lines, 1, rule='silent-broad-except') == 'weighed and kept'


def test_a_caller_that_names_no_rule_matches_a_scoped_marker() -> None:
    lines = ['x = 1  # auditme: accept[failure-as-absence] the caller reads batch.error']
    assert auditme.core.accept_reason(lines, 1) == 'the caller reads batch.error'


def test_a_line_number_outside_the_file_is_not_an_error() -> None:
    assert auditme.core.accept_reason(['x = 1'], 99) is None


def test_an_identical_hit_is_emitted_once(capsys: pytest.CaptureFixture[str]) -> None:
    """The driver runs project-level checks once per package under `src/`."""
    for _ in range(3):
        auditme.core.emit(rule='lockfile-drift', variant='stale', path='uv.lock', line=None, evidence='x', accepted=False, accepted_reason=None)
    assert len(capsys.readouterr().out.splitlines()) == 1


def test_hits_differing_in_any_field_are_both_emitted(capsys: pytest.CaptureFixture[str]) -> None:
    auditme.core.emit(rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    auditme.core.emit(rule='r', variant='v', path='a.py', line=2, evidence='x', accepted=False, accepted_reason=None)
    assert len(capsys.readouterr().out.splitlines()) == 2


def test_an_emitted_hit_carries_the_documented_schema(capsys: pytest.CaptureFixture[str]) -> None:
    auditme.core.emit(rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    record = json.loads(capsys.readouterr().out)
    assert set(record) == {'accepted', 'accepted_reason', 'evidence', 'line', 'path', 'rule', 'variant'}


def test_a_hit_with_no_related_serialises_without_the_key(capsys: pytest.CaptureFixture[str]) -> None:
    auditme.core.emit(rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    auditme.core.emit(related=[], rule='r', variant='v', path='a.py', line=2, evidence='x', accepted=False, accepted_reason=None)
    first, second = capsys.readouterr().out.splitlines()
    assert first == '{"accepted": false, "accepted_reason": null, "evidence": "x", "line": 1, "path": "a.py", "rule": "r", "variant": "v"}'
    assert 'related' not in second


def test_related_is_sorted_deduplicated_and_never_names_the_hit_s_own_path(capsys: pytest.CaptureFixture[str]) -> None:
    auditme.core.emit(related=['c.py', 'b.py', 'b.py', 'a.py'], rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    auditme.core.emit(related=['a.py'], rule='r', variant='v', path='a.py', line=2, evidence='x', accepted=False, accepted_reason=None)
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
    assert auditme.core.accepted_lazy_imports(root) == {('probe.cli', 'probe.heavy')}


def test_a_project_with_no_agents_file_accepts_no_lazy_imports(tmp_path: pathlib.Path) -> None:
    assert auditme.core.accepted_lazy_imports(tmp_path) == set()


def test_type_checking_blocks_are_located_by_line() -> None:
    tree = ast.parse('import typing\n\nif typing.TYPE_CHECKING:\n    import probe.cli\n')
    assert 4 in auditme.core.type_checking_linenos(tree)


def test_source_lines_of_a_non_utf8_file_are_empty(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'latin.py'
    path.write_bytes(b"x = '\xff\xfe'\n")
    assert auditme.core.source_lines(path) == []


def test_python_files_are_returned_sorted(project: Builder) -> None:
    """Emission order is part of the output, so file order cannot be arbitrary."""
    root = project({'src/probe/b.py': 'b = 1\n', 'src/probe/a.py': 'a = 1\n', 'src/probe/sub/c.py': 'c = 1\n'})
    found = auditme.core.all_py_files(root / 'src' / 'probe')
    assert [auditme.core.relpath(path, root) for path in found] == [
        'src/probe/a.py',
        'src/probe/b.py',
        'src/probe/sub/c.py',
    ]


def test_emit_writes_one_json_object_per_line(capsys: pytest.CaptureFixture[str]) -> None:
    auditme.core.emit(rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    auditme.core.emit(rule='r', variant='v', path='b.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    for line in io.StringIO(capsys.readouterr().out):
        assert json.loads(line)


# corpus definitions

DEFINITIONS_SOURCE = 'def run() -> None:\n    pass\n\n\nclass Probe:\n    def load(self) -> None:\n        pass\n'


def test_corpus_definitions_default_keys_module_level_functions_only(project: Builder) -> None:
    root = project({'src/pkg/mod.py': DEFINITIONS_SOURCE})
    found = auditme.core.corpus_definitions(root, root / 'src' / 'pkg')
    assert list(found) == ['run']
    node, path = found['run'][0]
    assert isinstance(node, ast.FunctionDef)
    assert auditme.core.relpath(path, root) == 'src/pkg/mod.py'


def test_corpus_definitions_skips_a_file_with_a_syntax_error(project: Builder) -> None:
    root = project({'src/pkg/good.py': DEFINITIONS_SOURCE, 'src/pkg/bad.py': 'def broken(:\n'})
    assert list(auditme.core.corpus_definitions(root, root / 'src' / 'pkg')) == ['run']


def test_corpus_definitions_with_classes_adds_classes_and_methods(project: Builder) -> None:
    root = project({'src/pkg/mod.py': DEFINITIONS_SOURCE})
    found = auditme.core.corpus_definitions(root, root / 'src' / 'pkg', classes=True)
    assert sorted(found) == ['Probe', 'load', 'run']
    assert isinstance(found['Probe'][0][0], ast.ClassDef)
    assert isinstance(found['load'][0][0], ast.FunctionDef)
    assert auditme.core.relpath(found['load'][0][1], root) == 'src/pkg/mod.py'


def test_corpus_definitions_keeps_a_name_defined_in_two_modules_twice(project: Builder) -> None:
    root = project({'src/pkg/a.py': 'def run() -> None:\n    pass\n', 'src/pkg/b.py': 'def run() -> None:\n    pass\n'})
    found = auditme.core.corpus_definitions(root, root / 'src' / 'pkg')
    assert [auditme.core.relpath(path, root) for _, path in found['run']] == ['src/pkg/a.py', 'src/pkg/b.py']


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
    tests = [ast.unparse(n.test) for n in auditme.core.walk_within_scope(func) if isinstance(n, ast.If)]
    assert tests == ['a']


def test_walk_within_scope_does_not_enter_nested_scopes() -> None:
    func = ast.parse(SCOPE_SOURCE).body[0]
    nodes = list(auditme.core.walk_within_scope(func))
    assert not any(isinstance(n, ast.IfExp) for n in nodes)
    assert any(isinstance(n, ast.FunctionDef) and n.name == 'inner' for n in nodes)


# is_private

INIT_ALL = "__all__ = ['load', 'Probe']\n"
NO_ALL = 'def load() -> None:\n    pass\n'


def test_is_private_a_name_in_the_package_all_is_public(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': INIT_ALL, 'src/pkg/mod.py': NO_ALL})
    assert not auditme.core.is_private('load', 'pkg.mod', root)


def test_is_private_a_name_left_out_of_the_package_all_is_private(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': INIT_ALL, 'src/pkg/mod.py': NO_ALL})
    assert auditme.core.is_private('helper', 'pkg.mod', root)


def test_is_private_a_name_in_its_modules_own_all_is_public(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': INIT_ALL, 'src/pkg/mod.py': "__all__ = ['helper']\n"})
    assert not auditme.core.is_private('helper', 'pkg.mod', root)


def test_is_private_a_method_follows_its_class(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': INIT_ALL, 'src/pkg/mod.py': NO_ALL})
    assert not auditme.core.is_private('Probe.load', 'pkg.mod', root)
    assert auditme.core.is_private('Other.load', 'pkg.mod', root)


def test_is_private_without_an_all_only_an_underscore_makes_private(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': NO_ALL, 'src/pkg/_mod.py': NO_ALL})
    assert not auditme.core.is_private('load', 'pkg.mod', root)
    assert auditme.core.is_private('_load', 'pkg.mod', root)
    assert auditme.core.is_private('load', 'pkg._mod', root)
    assert auditme.core.is_private('Probe._load', 'pkg.mod', root)


def test_is_private_an_underscore_name_in_an_all_is_public(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': "__all__ = ['_load']\n", 'src/pkg/mod.py': NO_ALL})
    assert not auditme.core.is_private('_load', 'pkg.mod', root)


def test_is_private_reads_an_annotated_all(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': "__all__: list[str] = ['load']\n", 'src/pkg/mod.py': NO_ALL})
    assert not auditme.core.is_private('load', 'pkg.mod', root)
    assert auditme.core.is_private('other', 'pkg.mod', root)


SCRIPT = (
    "import sys\n\n\ndef helper() -> int:\n    return 0\n\n\ndef main() -> int:\n    return helper()\n\n\nif __name__ == '__main__':\n    sys.exit(main())\n"
)


def test_privacy_names_the_all_rule(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': INIT_ALL, 'src/pkg/mod.py': NO_ALL})
    assert auditme.core.privacy('load', 'pkg.mod', root) == (False, auditme.core.PRIVACY_ALL)
    assert auditme.core.privacy('helper', 'pkg.mod', root) == (True, auditme.core.PRIVACY_ALL)


def test_privacy_a_script_is_public_only_through_its_main_guard(project: Builder) -> None:
    root = project({'bin/probe-run.py': SCRIPT})
    assert auditme.core.privacy('main', 'bin.probe-run', root) == (False, auditme.core.PRIVACY_SCRIPT)
    assert auditme.core.privacy('helper', 'bin.probe-run', root) == (True, auditme.core.PRIVACY_SCRIPT)


def test_privacy_reads_the_guard_either_way_round(project: Builder) -> None:
    root = project({'bin/probe.py': SCRIPT.replace("__name__ == '__main__'", "'__main__' == __name__")})
    assert auditme.core.privacy('helper', 'bin.probe', root) == (True, auditme.core.PRIVACY_SCRIPT)


def test_privacy_a_scripts_own_all_wins_over_its_guard(project: Builder) -> None:
    root = project({'bin/probe.py': "__all__ = ['helper']\n" + SCRIPT})
    assert auditme.core.privacy('helper', 'bin.probe', root) == (False, auditme.core.PRIVACY_ALL)
    assert auditme.core.privacy('main', 'bin.probe', root) == (True, auditme.core.PRIVACY_ALL)


def test_privacy_a_module_without_a_guard_falls_back_to_underscores(project: Builder) -> None:
    root = project({'bin/probe.py': 'def helper() -> int:\n    return 0\n'})
    assert auditme.core.privacy('helper', 'bin.probe', root) == (False, auditme.core.PRIVACY_UNDERSCORE)


def test_privacy_a_guarded_module_inside_a_package_is_no_script(project: Builder) -> None:
    root = project({'src/pkg/__init__.py': '', 'src/pkg/mod.py': SCRIPT})
    assert auditme.core.privacy('helper', 'pkg.mod', root) == (False, auditme.core.PRIVACY_UNDERSCORE)


def test_privacy_reads_a_script_in_a_top_level_root(project: Builder) -> None:
    root = project(
        {
            'pyproject.toml': "[tool.auditme]\nroots = [{path = 'scripts', modules = 'top-level'}]\n",
            'scripts/probe.py': SCRIPT,
        }
    )
    assert auditme.core.privacy('helper', 'probe', root) == (True, auditme.core.PRIVACY_SCRIPT)
    assert auditme.core.privacy('main', 'probe', root) == (False, auditme.core.PRIVACY_SCRIPT)


def test_privacy_reads_the_all_of_a_module_in_a_top_level_root(project: Builder) -> None:
    root = project(
        {
            'pyproject.toml': "[tool.auditme]\nroots = [{path = 'lib', modules = 'top-level'}]\n",
            'lib/probe.py': "__all__ = ['load']\n" + NO_ALL,
        }
    )
    assert auditme.core.privacy('other', 'probe', root) == (True, auditme.core.PRIVACY_ALL)


def test_describe_error_appends_the_chained_cause() -> None:
    try:
        try:
            raise OSError('disk on fire')
        except OSError as error:
            raise auditme.core.RootsError('cannot read x') from error
    except auditme.core.RootsError as caught:
        assert auditme.core.describe_error(caught) == 'cannot read x (disk on fire)'


def test_describe_error_is_the_bare_message_without_a_cause() -> None:
    assert auditme.core.describe_error(auditme.core.RootsError('plain')) == 'plain'


def test_from_import_bindings_resolve_absolute_and_relative_imports() -> None:
    tree = ast.parse('from a.b import c\nfrom .d import e as f\nfrom ..g import h\nfrom . import i\nimport j\n')
    assert auditme.core.from_import_bindings(tree, 'pkg.sub.mod', False) == {
        'c': 'a.b.c',
        'f': 'pkg.sub.d.e',
        'h': 'pkg.g.h',
        'i': 'pkg.sub.i',
    }


def test_from_import_bindings_resolve_a_package_init_against_itself() -> None:
    tree = ast.parse('from .base import Foo\n')
    assert auditme.core.from_import_bindings(tree, 'pkg.sub', True) == {'Foo': 'pkg.sub.base.Foo'}


def test_call_bindings_add_aliased_plain_imports() -> None:
    tree = ast.parse('from a import b\nimport c.d as e\nimport f.g\n')
    assert auditme.core.call_bindings(tree, 'pkg.mod', False) == {'b': 'a.b', 'e': 'c.d'}


def test_reexport_aliases_follow_a_re_export_of_a_re_export() -> None:
    from_bindings = {
        'pkg': {'run': 'pkg.base.run'},
        'top': {'run': 'pkg.run'},
        'other': {'unrelated': 'elsewhere.thing'},
    }
    assert auditme.core.reexport_aliases(from_bindings, {'pkg.base.run'}) == {
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
    assert auditme.core.resolve_call(parse_call('local()'), 'pkg.mod', None, imported, known, aliases) == 'pkg.mod.local'
    assert auditme.core.resolve_call(parse_call('func()'), 'pkg.mod', None, imported, known, aliases) == 'pkg.other.func'
    assert auditme.core.resolve_call(parse_call('other.func()'), 'pkg.mod', None, imported, known, aliases) == 'pkg.other.func'
    assert auditme.core.resolve_call(parse_call('pkg.reexport.func()'), 'pkg.mod', None, imported, known, aliases) == 'pkg.other.func'
    assert auditme.core.resolve_call(parse_call('self.method()'), 'pkg.mod', 'Cls', imported, known, aliases) == 'pkg.mod.Cls.method'
    assert auditme.core.resolve_call(parse_call('unknown()'), 'pkg.mod', None, imported, known, aliases) is None


def test_resolve_call_resolves_a_class_method_only_when_asked() -> None:
    known: dict[str, str | None] = {'pkg.mod.Cls.build': 'Cls'}
    call = parse_call('Cls.build()')
    assert auditme.core.resolve_call(call, 'pkg.mod', None, {}, known, {}) is None
    assert auditme.core.resolve_call(call, 'pkg.mod', None, {}, known, {}, class_methods=True) == 'pkg.mod.Cls.build'


def test_reads_by_module_and_name_counts_both_import_spellings(project: Builder) -> None:
    root = project(
        {
            'src/pkg/__init__.py': '',
            'src/pkg/a.py': 'from pkg.b import NAME\n',
            'src/pkg/c.py': 'import pkg.b\n\nvalue = pkg.b.OTHER\n',
        }
    )
    reads = auditme.core.reads_by_module_and_name(root, root / 'src')
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
    assert auditme.core.accept_reason(lines, lineno, end) is None


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    reason=hypothesis.strategies.text(alphabet='abc xyz', min_size=0, max_size=12),
    rule=hypothesis.strategies.from_regex(r'[a-z][a-z0-9]{0,8}', fullmatch=True),
    other=hypothesis.strategies.from_regex(r'[a-z][a-z0-9]{0,8}', fullmatch=True),
)
def test_accept_reason_answers_with_a_string_and_ignores_another_rules_marker(reason: str, rule: str, other: str) -> None:
    hypothesis.assume(rule != other)
    lines = [f'x = 1  # auditme: accept[{other}] {reason}']
    assert auditme.core.accept_reason(lines, 1, None, rule=rule) is None
    answer = auditme.core.accept_reason(lines, 1, None, rule=other)
    assert isinstance(answer, str)
    assert answer
    assert auditme.core.accept_reason(lines, 1, None) == answer
