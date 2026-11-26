"""Tests for the A17 lister: its candidates, payloads and hashes."""

import collections.abc
import pathlib

import pytest

import auditor.api
import auditor.core
import auditor.phaseb
import auditor.phaseb.candidates
import auditor.testing

LISTER = auditor.testing.load_lister(__file__)

Project = collections.abc.Callable[[dict[str, str]], pathlib.Path]

A17_INIT = "from .base import Probe\n\n__all__ = ['Probe']\n"


A17_BASE = 'class Probe:\n    pass\n'


A17_READER = 'import pkg.sub\n\n\ndef use():\n    return pkg.sub.Probe\n'


A17_KEY = 'src/pkg/sub/__init__.py'


def run_a17(root: pathlib.Path) -> dict[str, auditor.api.Candidate]:
    return {candidate.id: candidate for candidate in auditor.phaseb.list_candidates('A17', root)}


def write_a17_project(project: Project, extra: dict[str, str] | None = None, init: str = A17_INIT) -> pathlib.Path:
    files = {'src/pkg/__init__.py': '', A17_KEY: init, 'src/pkg/sub/base.py': A17_BASE}
    files.update(extra or {})
    return project(files)


def test_a17_lists_an_all_init_with_its_consumers(project: Project) -> None:
    candidate = run_a17(write_a17_project(project, {'src/pkg/user.py': A17_READER}))[A17_KEY]
    assert candidate.payload['all'] == ['Probe']
    assert candidate.payload['consumers'] == {'Probe': ['src/pkg/user.py: return pkg.sub.Probe']}


def test_a17_leaves_out_a_test_tree_reader_and_its_hash(project: Project) -> None:
    first = run_a17(write_a17_project(project))[A17_KEY]
    with_test = run_a17(write_a17_project(project, {'src/tests/test_sub.py': A17_READER}))[A17_KEY]
    assert with_test.payload['consumers'] == {'Probe': []}
    assert with_test.hash == first.hash


A17_SUBMODULE_KEY = 'src/pkg/mod.py'


A17_SUBMODULE = "__all__ = ['f']\n\n\ndef f():\n    return 1\n"


def test_a17_lists_a_submodule_all_with_a_consumer_in_another_module(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', A17_SUBMODULE_KEY: A17_SUBMODULE, 'src/pkg/user.py': 'from pkg.mod import f\n'})
    candidate = run_a17(root)[A17_SUBMODULE_KEY]
    assert candidate.payload['all'] == ['f']
    assert candidate.payload['consumers'] == {'f': ['src/pkg/user.py: from pkg.mod import f']}


def test_a17_lists_a_submodule_all_read_only_by_a_test_with_no_consumer(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', A17_SUBMODULE_KEY: A17_SUBMODULE, 'src/tests/test_mod.py': 'from pkg.mod import f\n'})
    assert run_a17(root)[A17_SUBMODULE_KEY].payload['consumers'] == {'f': []}


def test_a17_leaves_out_a_submodule_without_all(project: Project) -> None:
    root = project({'src/pkg/__init__.py': '', A17_SUBMODULE_KEY: 'def f():\n    return 1\n'})
    assert A17_SUBMODULE_KEY not in run_a17(root)


def test_a17_keeps_an_init_candidate_when_a_submodule_is_listed(project: Project) -> None:
    plain = run_a17(write_a17_project(project))[A17_KEY]
    both = run_a17(write_a17_project(project, {'src/pkg/mod.py': A17_SUBMODULE}))
    assert both[A17_KEY].hash == plain.hash
    assert 'src/pkg/mod.py' in both


def test_a17_counts_a_project_script_target_as_a_consumer(project: Project) -> None:
    root = write_a17_project(project, {'pyproject.toml': '[project.scripts]\nprobe = "pkg.sub:Probe"\n'})
    assert run_a17(root)[A17_KEY].payload['consumers'] == {'Probe': ['pyproject.toml: probe = "pkg.sub:Probe"']}


def test_a17_reports_an_unreadable_reader_as_a_phaseb_error(project: Project, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    root = write_a17_project(project)
    reader = tmp_path / 'user.py'
    reader.write_bytes(b'\xff\xfe not utf-8')
    monkeypatch.setattr(auditor.api, 'reads_by_module_and_name', lambda scope, src_root: {('pkg.sub', 'Probe'): [(reader, 1)]})
    with pytest.raises(auditor.phaseb.PhaseBError, match='user.py'):
        run_a17(root)


def test_a17_lists_reach_ins_for_an_empty_init(project: Project) -> None:
    root = write_a17_project(project, {'src/pkg/user.py': 'from pkg.sub.base import Probe\n'}, init='')
    assert run_a17(root)[A17_KEY].payload['reach_ins'] == ['src/pkg/user.py: from pkg.sub.base import Probe']


def test_a17_drops_an_init_on_an_empty_init_hit(project: Project) -> None:
    root = project(
        {
            'src/pkg/__init__.py': '',
            'src/pkg/sub/__init__.py': '',
            'src/pkg/big/__init__.py': "__all__ = ['a', 'b', 'c', 'd', 'e']\n",
        }
    )
    found = run_a17(root)
    assert A17_KEY not in found
    assert 'src/pkg/big/__init__.py' in found


def test_a17_removes_a_consumer_a_shim_hit_names(project: Project) -> None:
    files = {'src/pkg/canon.py': A17_BASE, 'src/pkg/user.py': 'from pkg.sub import Probe\n'}
    root = write_a17_project(project, files, init="import pkg.canon\n\n__all__ = ['Probe']\n\nProbe = pkg.canon.Probe\n")
    hits = auditor.api.capture_hits(root, (LISTER.migration_shim_hits,))
    assert ('migration-shim-consumer', 'src/pkg/user.py', 1) in hits
    assert run_a17(root)[A17_KEY].payload['consumers'] == {'Probe': []}


def test_a17_hash_ignores_a_moved_consumer_line_and_tracks_an_init_edit(project: Project) -> None:
    first = run_a17(write_a17_project(project, {'src/pkg/user.py': A17_READER}))[A17_KEY]
    moved = run_a17(write_a17_project(project, {'src/pkg/user.py': 'X = 1\n' + A17_READER}))[A17_KEY]
    assert moved.hash == first.hash
    edited = run_a17(write_a17_project(project, {'src/pkg/user.py': A17_READER}, init=A17_INIT + '# edit\n'))[A17_KEY]
    assert edited.hash != first.hash
