"""Shared fixtures for the auditme checker tests.

The checker is the installed `auditor` package, run as `auditor check <project-root>`.
These tests import it by its full path. The generic fixtures come from the
`auditor.testing` plugin; this file keeps what is specific to this suite.
"""

import auditor.api.candidates
import auditor.phaseb.candidates
import auditor.testing

# auditme: accept[reexport-in-non-init] the checker tests call `conftest.git`
git = auditor.testing.git


FUTURE_IMPORT = 'from __future__ import annotations\n'


def make_candidate(candidate_id: str, **overrides) -> auditor.api.candidates.Candidate:
    fields = {'question': 'Q1', 'id': candidate_id, 'path': 'src/pkg/mod.py', 'start': 1, 'end': 2, 'payload': {}, 'hash': 'h'}
    fields.update(overrides)
    return auditor.api.candidates.Candidate(**fields)


def make_verdict(candidate_id: str = 'src/pkg/mod.py::probe', **overrides) -> auditor.phaseb.candidates.Verdict:
    fields = {
        'question': 'Q1',
        'id': candidate_id,
        'hash': 'abc',
        'brief_version': 1,
        'findings': {'missing': [], 'extra': []},
        'reason': 'ok',
        'judged': '2026-01-01',
    }
    fields.update(overrides)
    return auditor.phaseb.candidates.Verdict(**fields)
