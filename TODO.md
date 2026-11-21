# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

## Fix or accept this repository's audit backlog

Found on 2026-11-21 when `pyproject.toml` first declared this repository's
audit roots (amendment 1.11 of `agents/specs/project-setup/spec.md`).
`python3 claude/skills/auditme/checks/audit.py .` gave 691 hits, 686 of them
unaccepted. By rule: `literal-duplication` (155),
`leading-underscore-attribute-access` (116), `leading-underscore-def-class`
(111), `from-import` (53), `leading-underscore-const-upper` (49),
`silent-broad-except` (37), `except-interpolation` (30),
`filesystem-envelope-gap` (23), `non-alphabetical-literal` (18),
`leading-underscore-binding` (15), and the remaining rules, each with 8 hits or fewer.
`phaseb.py plan . --question A4` plans 37 candidates in one batch.

Cause: the checker's own code was never swept; the roots were fixed by layout
until the declaration landed, so the hooks gated none of it. Until the
backlog is cleared, `auditme-all` in `.pre-commit-config.yaml` runs at the
`manual` stage only, so a push is not blocked by it; `auditme-changed` still
gates every commit's changed files.

Fix direction: fix or accept every hit, then put `pre-push` back on
`auditme-all` (`stages: [manual, pre-push]`) and run the first audit of this
repository.

Note 2026-11-21: until this is done, every commit that changes a checker file
is blocked by `auditme-changed` on the backlog hits already in that file (and
in files a `literal-duplication` hit relates to it), whether or not the
commit adds any. The commit that shipped the three checker requests added no
hit (685 unaccepted before and after) and was made with
`SKIP=auditme-changed`, as the operator chose; the next checker change meets
the same block.

Review: `agents/reviews/audit-backlog-2026-11-21.md` (answered 2026-11-21); tasks: `agents/tasks/reviews/tasks-1.md`.
