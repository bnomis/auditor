"""The helper API: the one module a rules repository's code may import.

Nothing outside this package is part of the contract between the runner and
rule code.
"""

from auditor.api.base import API_VERSION
from auditor.api.calls import SINK_TOKENS
from auditor.api.flow import (  # auditme: accept[migration-shim-consumer] the API's home for two core helpers
    BARE_GENERIC_NAMES,
    is_dunder_all_assignment,
    leading_underscore_names,
)
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
    'BARE_GENERIC_NAMES',
    'Candidate',
    'SINK_TOKENS',
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
    'is_dunder_all_assignment',
    'is_test_relpath',
    'leading_underscore_names',
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
