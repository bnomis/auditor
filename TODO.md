# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

## Keep a dismissal across a re-judge while the code is unchanged

Found on 2026-11-22 by `agents/audit-reviews/review-4.md` (decision D2) and
filed in `claude/skills/auditme/requests.md` ("Keep a dismissal across a brief
bump while the code is unchanged"), which holds the full finding:
`core.py::cached_source` (A1) was dismissed on the pages of review-2, review-3
and review-4 for the same reason.

Cause: `merge_verdicts` in
`claude/skills/auditme/checks/auditme/phaseb/ledger.py` carries a dismissal to
the new verdict only when its `findings` text is identical to the old one. A
re-judge after a brief bump writes the findings afresh, so the text differs
and the dismissal is dropped.

Fix direction: keep the dismissal while the candidate's content hash is
unchanged, whatever the brief version or the wording of the findings; a
changed hash still drops it. Test both cases, and have `report` say a carried
dismissal was made under an earlier brief version. Shipping it deletes the
request entry.
