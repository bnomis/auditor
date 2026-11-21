# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

## A worktree's ruff-version-drift hit is hidden by an accept marker

Found on 2026-11-21 in a review of this file. `4641cca` (Task 1 of
`agents/tasks/project-setup/tasks-5.md`, run by a queue in a worktree) added
`# auditme: accept[ruff-version-drift] the ruff installed on PATH is newer
than the 14-day exclude-newer window lets uv.lock pin` above `rev: v0.17.2`
in `.pre-commit-config.yaml` (line 4), to get its commit past the
`auditme-changed` hook. In the main checkout the same day there was no drift
to accept: `.venv/bin/ruff` is 0.17.2, `uv.lock` locks ruff 0.17.2, and
`python3 claude/skills/auditme/checks/audit.py .` gave no
`ruff-version-drift` hit. The ruff on `PATH` was 0.17.6.

Cause: the worktree had no `.venv`, so `ruff_executable()` in
`claude/skills/auditme/checks/auditme/rules/project_hygiene.py` fell back to
the ruff on `PATH`, as it is specified to (amendment 1.5 of
`agents/specs/project-setup/spec.md`). The hit was real for that worktree
and not for the repository, and the marker now accepts any later drift on
that line, in every checkout.

Fix direction: small. Remove the marker. For a run in a worktree, make the
pinned ruff the one the audit finds - a `uv sync` in the worktree before its
first commit - rather than accepting the drift; where that is done (the queue
runner that creates the worktree) is another repository's change, so record
it there, not here.

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
