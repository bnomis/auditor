"""The helper API: the one module a rules repository's code may import.

Nothing outside this package is part of the contract between the runner and
rule code.
"""

from auditor.api.base import API_VERSION
from auditor.core import (
    accept_reason,
    all_py_files,
    audit_roots,
    cached_bytes,
    cached_source,
    call_bindings,
    corpus_definitions,
    corpus_index,
    corpus_py_files,
    describe_error,
    emit,
    first_party_dirs,
    from_import_bindings,
    is_test_relpath,
    module_dotted,
    path_inside,
    py_files,
    read_and_parse,
    read_source,
    reexport_aliases,
    relpath,
    resolve_call,
    source_lines,
    type_checking_linenos,
    walk_within_scope,
)
from auditor.phaseb.candidates import Candidate

__all__ = [
    'API_VERSION',
    'Candidate',
    'accept_reason',
    'all_py_files',
    'audit_roots',
    'cached_bytes',
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
