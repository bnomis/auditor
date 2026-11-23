# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

## Settle the brief cases reviewers left open

Found on 2026-11-23 by an audit on one project, run after the 2026-11-22
brief settlements, and filed as an open request in
`claude/skills/auditme/requests.md` ("Settle the brief cases reviewers left
open (filed 2026-11-23)"), which lists each case for the Doc4, Doc5, T1, A17
and A19 briefs.

Cause: the briefs leave these cases unsettled, so batch reviewers judged the
same shape differently (failure mode 2). For A19, the brief also flags a
handler that carries the scoped
`accept[logger-exception-graceful-degradation]` marker the 2026-10-14 ruling
prescribes, which records the user's decision to keep it.

Fix direction: put each case to the operator as a decision with a
recommendation on a review page, as the earlier threshold reviews in
`agents/reviews/` did; then settle each in its brief under
`claude/skills/auditme/phaseb/briefs/`, bumping that brief's version and the
expectation in `claude/skills/auditme/tests/phaseb/test_briefs.py`. For A19,
either have the brief read the marker as the user's decision or have the
lister leave such a site out, as it does for a sweep hit. Shipping it deletes
the request entry.
