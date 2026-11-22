# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

## The `ruff format` half of the `ruff` rule never reports a file

Found on 2026-11-22 by `agents/audit-reviews/review-3.md` (its Checker
request section), reproduced the same day on a scratch project, and filed in
`claude/skills/auditme/requests.md` ("The `ruff format` half of the `ruff`
rule never reports a file"), which holds the full finding.

Cause: `check_ruff` in `claude/skills/auditme/checks/auditme/rules/project_hygiene.py`
matches only output lines containing `Would reformat` or ending in `.py`;
ruff 0.17.4 prints `unformatted: File would be reformatted` and
` --> <path>:<line>:<col>`, so no `ruff-format` hit is ever emitted.

Fix direction: as the request asks - read a stable output form, set `path`
and `line` from it, and test against output captured from the pinned ruff.
Shipping it deletes the request entry; the first sweep after it reports any
unformatted file as catch-up.

## Settle the thresholds review-3's reviewers left open

Found on 2026-11-22 by `agents/audit-reviews/review-3.md` (decision D1) and
filed as an open request in `claude/skills/auditme/requests.md` ("Settle the
thresholds review-3's reviewers left open"), which lists each threshold for
the A1, T2, Doc4 and Doc5 briefs.

Cause: each brief tells its reviewer to report, not decide, a threshold it
does not settle, so the same case can be judged differently in another batch.

Fix direction: put each threshold to the operator as a decision with a
recommendation on a review page, as the two earlier threshold reviews in
`agents/reviews/` did, and consider the request's note on a general rule;
then settle each in its brief under `claude/skills/auditme/phaseb/briefs/`,
bumping that brief's version and the expectation in
`claude/skills/auditme/tests/phaseb/test_briefs.py`. Shipping it deletes the
request entry.
