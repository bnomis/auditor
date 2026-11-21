# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

## The Stop hook checks an auditor worktree with the main checkout's checker

Found on 2026-11-21 during the `agents/tasks/reviews/tasks-1.md` queue, which
ran in the worktree `.claude/worktrees/reviews-tasks-1`. After Tasks 4 to 9
changed the checker on that branch, the Stop hook kept blocking every turn
with hits the branch's own checker no longer reported: for example
`literal-duplication` on expected values inside `assert` (cleared by R2 of
`agents/reviews/audit-backlog-2026-11-21.md`). At 17:35 UTC
`python3 claude/skills/auditme/checks/audit.py .` in the worktree reported 0
unaccepted hits while the hook still listed well over a hundred. The hook
stopped only once the branch merged into `main` (`52b4813`).

Cause: `claude/hooks/auditme-stop.sh:22` always runs
`$HOME/.claude/skills/auditme/checks/changed.py`, which
`bin/install-claude.sh` links into the main checkout. Its comment gives the
reason ("the installed checker, not the project's pinned one: this is the
early warning"), which holds for a project that only uses the checker. In
this repository the checker under change is the project's own code, so a
branch is judged by the checker it is replacing.

Fix direction: small. When the project root holds its own
`claude/skills/auditme/checks/changed.py` (this repository, or a worktree of
it), the hook runs that one instead; other projects keep the installed
checker. Add a test to `tests/test_stop_hook.py` for both cases.

## A second accept marker on one line is silently ignored

Found on 2026-11-21 by Task 14 of `agents/tasks/reviews/tasks-1.md`: the
docstring line `claude/skills/auditme/checks/auditme/rules/state_and_effects.py:1029`
carried `# auditme: accept[leading-underscore-self] ...` followed by
`# auditme: accept[leading-underscore-attribute-access] ...`, and the sweep
still reported `leading-underscore-attribute-access` there as unaccepted
(recorded in that task's Notes; the line was later reworded and both markers
dropped in `57b7a4a`).

Cause: `ACCEPT_COMMENT_RE` in `claude/skills/auditme/checks/auditme/core.py:20`
is `#\s*auditme:\s*accept\b(?:\[([a-z0-9-]+)\])?\s*(.*)$`, matched once per
line. The reason group `(.*)$` swallows any later marker, so only the first
rule named on a line is accepted. Checked the same day:
`accept[rule-a] reason a  # auditme: accept[rule-b] reason b` parses as rule
`rule-a` with reason `reason a  # auditme: accept[rule-b] reason b`.

Fix direction: small, a skill change made between audits. Either parse every
marker on a line (the reason ends at the next `# auditme:`), or report a
second marker on one line as its own hit so it cannot pass unnoticed;
document the choice in `SKILL.md`'s acceptance mechanism, with a test in
`claude/skills/auditme/tests/test_core.py`.
