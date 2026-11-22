# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

## The Phase B test index reads tests only from `src/tests/` and `tests/`

Found on 2026-11-21 by this repository's first full audit
(`agents/audit-reviews/review-1.md`) and filed as an open request in
`claude/skills/auditme/requests.md` ("The Phase B test index reads tests only
from `src/tests/` and `tests/`"), which holds the full finding.

Cause: `TEST_TREES` in `claude/skills/auditme/checks/auditme/phaseb/testmap.py`
fixes where the T1 and T2 listers look for tests, so a test tree declared as
an audit root in `[tool.auditme]` never reaches the index.

Fix direction: as the request asks - read tests from every audit root as well
as the default trees, deciding a test by `is_test_relpath`; amend
`agents/specs/listed-phase-b-test-questions/spec.md` first. Shipping it
deletes the request entry; review-2 cannot start until it is shipped or
rejected.

## A9 reads a registered check's `check_` name as a purity promise

Found on 2026-11-21 by `agents/audit-reviews/review-1.md` (decision D3) and
filed as an open request in `claude/skills/auditme/requests.md` ("A9 should
not read a registered check's `check_` name as a purity promise"), which holds
the full finding.

Cause: A9 lists `check_` among the pure prefixes, while the checker's own
registry (`claude/skills/auditme/checks/auditme/registry.py`) uses `check_`
for checks that read the tree and print hits.

Fix direction: as the request asks - a function registered as a check (by the
project's registry or a registering decorator) is not read as pure-named; the
narrowing names the registration as its positive evidence. Shipping it deletes
the request entry.

## Settle the thresholds review-1's reviewers left open

Found on 2026-11-21 by `agents/audit-reviews/review-1.md` (decision D1) and
filed as an open request in `claude/skills/auditme/requests.md` ("Settle the
thresholds review-1's reviewers left open"), which lists each threshold for
the A1, A4, T1, Doc4 and Doc5 briefs.

Cause: each brief tells its reviewer to report, not decide, a threshold it
does not settle, so the same case can be judged differently in another batch.

Fix direction: settle each threshold in its brief under
`claude/skills/auditme/phaseb/briefs/`, bumping that brief's
version and the expectation in `claude/skills/auditme/tests/phaseb/test_briefs.py`. Shipping it
deletes the request entry.
