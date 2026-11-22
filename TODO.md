# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

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
