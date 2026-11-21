# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

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
