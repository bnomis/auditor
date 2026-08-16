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

import auditme.core
import pytest

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]


def test_a_marker_on_the_hit_line_accepts_it() -> None:
    lines = ["usage = parsed.get('usage', {})  # auditme: accept schema forbids null"]
    assert auditme.core._accept_reason(lines, 1) == 'schema forbids null'


def test_a_marker_on_the_preceding_line_accepts_the_hit() -> None:
    lines = ['# auditme: accept schema forbids null', "usage = parsed.get('usage', {})"]
    assert auditme.core._accept_reason(lines, 2) == 'schema forbids null'


def test_a_marker_on_the_following_line_does_not_accept_the_hit() -> None:
    lines = ["usage = parsed.get('usage', {})", '# auditme: accept schema forbids null']
    assert auditme.core._accept_reason(lines, 1) is None


def test_a_marker_inside_a_multi_line_node_accepts_it() -> None:
    lines = [
        'result = call(',
        '    # auditme: accept deliberate',
        ')',
    ]
    assert auditme.core._accept_reason(lines, 1, end_lineno=3) == 'deliberate'
    assert auditme.core._accept_reason(lines, 1) is None


def test_a_marker_with_no_reason_still_accepts() -> None:
    lines = ['x = 1  # auditme: accept']
    assert auditme.core._accept_reason(lines, 1) == 'no reason given'


def test_a_scoped_marker_accepts_only_its_own_rule() -> None:
    lines = ['x = 1  # auditme: accept[failure-as-absence] the caller reads batch.error']
    assert auditme.core._accept_reason(lines, 1, rule='failure-as-absence') == 'the caller reads batch.error'
    assert auditme.core._accept_reason(lines, 1, rule='silent-broad-except') is None


def test_an_unscoped_marker_accepts_every_rule() -> None:
    """Retained so no marker written before scoping existed needs migrating."""
    lines = ['x = 1  # auditme: accept weighed and kept']
    assert auditme.core._accept_reason(lines, 1, rule='failure-as-absence') == 'weighed and kept'
    assert auditme.core._accept_reason(lines, 1, rule='silent-broad-except') == 'weighed and kept'


def test_a_caller_that_names_no_rule_matches_a_scoped_marker() -> None:
    lines = ['x = 1  # auditme: accept[failure-as-absence] the caller reads batch.error']
    assert auditme.core._accept_reason(lines, 1) == 'the caller reads batch.error'


def test_a_line_number_outside_the_file_is_not_an_error() -> None:
    assert auditme.core._accept_reason(['x = 1'], 99) is None


def test_an_identical_hit_is_emitted_once(capsys: pytest.CaptureFixture[str]) -> None:
    """The driver runs project-level checks once per package under `src/`."""
    for _ in range(3):
        auditme.core._emit(rule='lockfile-drift', variant='stale', path='uv.lock', line=None, evidence='x', accepted=False, accepted_reason=None)
    assert len(capsys.readouterr().out.splitlines()) == 1


def test_hits_differing_in_any_field_are_both_emitted(capsys: pytest.CaptureFixture[str]) -> None:
    auditme.core._emit(rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    auditme.core._emit(rule='r', variant='v', path='a.py', line=2, evidence='x', accepted=False, accepted_reason=None)
    assert len(capsys.readouterr().out.splitlines()) == 2


def test_an_emitted_hit_carries_the_documented_schema(capsys: pytest.CaptureFixture[str]) -> None:
    auditme.core._emit(rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    record = json.loads(capsys.readouterr().out)
    assert set(record) == {'accepted', 'accepted_reason', 'evidence', 'line', 'path', 'rule', 'variant'}


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
    assert auditme.core._accepted_lazy_imports(root) == {('probe.cli', 'probe.heavy')}


def test_a_project_with_no_agents_file_accepts_no_lazy_imports(tmp_path: pathlib.Path) -> None:
    assert auditme.core._accepted_lazy_imports(tmp_path) == set()


def test_type_checking_blocks_are_located_by_line() -> None:
    tree = ast.parse('import typing\n\nif typing.TYPE_CHECKING:\n    import probe.cli\n')
    assert 4 in auditme.core._type_checking_linenos(tree)


def test_source_lines_of_a_non_utf8_file_are_empty(tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'latin.py'
    path.write_bytes(b"x = '\xff\xfe'\n")
    assert auditme.core._source_lines(path) == []


def test_python_files_are_returned_sorted(project: Builder) -> None:
    """Emission order is part of the output, so file order cannot be arbitrary."""
    root = project({'src/probe/b.py': 'b = 1\n', 'src/probe/a.py': 'a = 1\n', 'src/probe/sub/c.py': 'c = 1\n'})
    found = auditme.core._all_py_files(root / 'src' / 'probe')
    assert [auditme.core._relpath(path, root) for path in found] == [
        'src/probe/a.py',
        'src/probe/b.py',
        'src/probe/sub/c.py',
    ]


def test_emit_writes_one_json_object_per_line(capsys: pytest.CaptureFixture[str]) -> None:
    auditme.core._emit(rule='r', variant='v', path='a.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    auditme.core._emit(rule='r', variant='v', path='b.py', line=1, evidence='x', accepted=False, accepted_reason=None)
    for line in io.StringIO(capsys.readouterr().out):
        assert json.loads(line)
