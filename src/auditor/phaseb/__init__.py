"""Phase B: listed questions, their candidates and their ledgers.

A listed question has a lister that names every site it applies to, so a
reviewer judges each site once and a ledger keeps the verdict until the code
or the brief changes. `candidates.py` holds the data model and the registry
of listers; `PhaseBError` is defined in `errors.py` and re-exported here.
"""

from auditor.api.base import PhaseBError
from auditor.api.candidates import DEFAULT_DEPTH

from . import batches
from .candidates import (
    brief_version,
    depth_questions,
    list_candidates,
    question_batch_size,
    question_brief,
    registered_questions,
)
from .ledger import dismiss_verdict, merge_verdicts, read_ledger

__all__ = [
    'DEFAULT_DEPTH',
    'PhaseBError',
    'batches',
    'brief_version',
    'depth_questions',
    'dismiss_verdict',
    'list_candidates',
    'merge_verdicts',
    'question_batch_size',
    'question_brief',
    'read_ledger',
    'registered_questions',
]
