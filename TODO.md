# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

## Ship or reject the three open checker requests

Found on 2026-11-21 in a review of this file. `dfc34b2` filed three entries
under `## Open` in `claude/skills/auditme/requests.md`, each raised by an
audit the same day: "A user guide's parameter list is checked by nothing",
"Listed briefs leave thresholds open that reviewers settle differently" and
"D2 has no carve-out for type-stub packages and notebook kernels".

Cause: the auditme skill (step 3, Mechanical sweep) lets no audit start while
`## Open` has an entry, so these stand between the backlog item below and
the first audit of this repository, and no item recorded them.

Fix direction: for each entry, ship it (the check, brief threshold or
predicate text, its tests, and the catch-up it exposes) or move it to
`## Rejected` with the reason. The first entry adds or widens a check, so it
goes through a spec first; the other two change brief and predicate text,
each with a brief version bump where a brief changes. Do this before the
backlog below, so the backlog's catch-up includes any new check's hits.

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
