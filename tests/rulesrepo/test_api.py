import importlib
import pathlib
import pkgutil

import pytest

import auditor
import auditor.api
import auditor.core
import auditor.phaseb.candidates

CORE_NAMES = [
    'accept_reason',
    'all_py_files',
    'audit_roots',
    'cached_bytes',
    'cached_first_party_dirs',
    'cached_roots',
    'cached_source',
    'call_bindings',
    'corpus_definitions',
    'corpus_index',
    'corpus_py_files',
    'describe_error',
    'emit',
    'first_party_dirs',
    'from_import_bindings',
    'is_test_relpath',
    'module_dotted',
    'path_inside',
    'privacy',
    'py_files',
    'read_and_parse',
    'read_source',
    'reexport_aliases',
    'relpath',
    'resolve_call',
    'source_lines',
    'type_checking_linenos',
    'walk_within_scope',
]


@pytest.mark.parametrize('name', CORE_NAMES)
def test_core_helper_is_the_same_object(name: str) -> None:
    assert getattr(auditor.api, name) is getattr(auditor.core, name)


def test_candidate_is_the_phaseb_class() -> None:
    assert auditor.api.Candidate is auditor.api.candidates.Candidate


def test_api_version() -> None:
    assert auditor.api.API_VERSION == (1, 0)


def submodule_exports() -> list[str]:
    """Every name that an `auditor.api` submodule lists in its own `__all__`."""
    names: list[str] = []
    for info in pkgutil.iter_modules(auditor.api.__path__):
        names.extend(getattr(importlib.import_module(f'auditor.api.{info.name}'), '__all__', []))
    return names


def test_all_lists_exactly_the_exports() -> None:
    assert sorted(auditor.api.__all__) == sorted([*CORE_NAMES, 'API_VERSION', 'Candidate', *submodule_exports()])


def test_no_existing_module_imports_the_api() -> None:
    root = pathlib.Path(auditor.__file__).parent
    users = [p for p in root.rglob('*.py') if p.relative_to(root).parts[0] not in {'api', 'catalogue', 'phaseb'} and 'auditor.api' in p.read_text()]
    assert users == []
