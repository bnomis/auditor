# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

## Settle the thresholds review-2's reviewers left open

Found on 2026-11-22 by `agents/audit-reviews/review-2.md` (decision D1) and
filed as an open request in `claude/skills/auditme/requests.md` ("Settle the
thresholds review-2's reviewers left open"), which lists each threshold for
the A1, A4, A17, Doc4 and Doc5 briefs.

Cause: each brief tells its reviewer to report, not decide, a threshold it
does not settle, so the same case can be judged differently in another batch.

Fix direction: put each threshold to the operator as a decision with a
recommendation on a review page, as `agents/reviews/brief-thresholds-2026-11-22.md`
did for review-1's; then settle each in its brief under
`claude/skills/auditme/phaseb/briefs/`, bumping that brief's version and the
expectation in `claude/skills/auditme/tests/phaseb/test_briefs.py`. The A1
emitted-hit case goes with review-2's D2. Shipping it deletes the request
entry; review-3 cannot start until it is shipped or rejected.
