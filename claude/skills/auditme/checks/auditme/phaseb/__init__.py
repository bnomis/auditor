"""Phase B: listed questions, their candidates and their ledgers.

A listed question has a lister that names every site it applies to, so a
reviewer judges each site once and a ledger keeps the verdict until the code
or the brief changes. `candidates.py` holds the data model and the registry
of listers; `PhaseBError` is defined in `errors.py` and re-exported here.
"""

from auditme.phaseb import architecture, batches
from auditme.phaseb.candidates import (
    Candidate,
    Lister,
    Verdict,
    brief_version,
    list_candidates,
    question_batch_size,
    question_brief,
    question_kinds,
    register_question,
)
from auditme.phaseb.errors import PhaseBError
from auditme.phaseb.ledger import MergeResult, dismiss_verdict, merge_verdicts, read_ledger
from auditme.phaseb.testmap import TestRef, build_test_map

__all__ = [
    'Candidate',
    'Lister',
    'MergeResult',
    'PhaseBError',
    'TestRef',
    'Verdict',
    'architecture',
    'batches',
    'brief_version',
    'build_test_map',
    'dismiss_verdict',
    'list_candidates',
    'merge_verdicts',
    'question_batch_size',
    'question_brief',
    'question_kinds',
    'read_ledger',
    'register_question',
]
