"""Phase B: listed questions, their candidates and their ledgers.

A listed question has a lister that names every site it applies to, so a
reviewer judges each site once and a ledger keeps the verdict until the code
or the brief changes. `candidates.py` holds the data model and the registry
of listers; `PhaseBError` is defined in `errors.py` and re-exported here.
"""

import auditme.phaseb.architecture  # noqa: F401  registers the architecture listers
from auditme.phaseb import batches
from auditme.phaseb.candidates import (
    brief_version,
    list_candidates,
    question_batch_size,
    question_brief,
)
from auditme.phaseb.errors import PhaseBError
from auditme.phaseb.ledger import dismiss_verdict, merge_verdicts, read_ledger

__all__ = [
    'PhaseBError',
    'batches',
    'brief_version',
    'dismiss_verdict',
    'list_candidates',
    'merge_verdicts',
    'question_batch_size',
    'question_brief',
    'read_ledger',
]
