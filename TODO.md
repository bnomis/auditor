# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

## The Stop hook passes silently when the installed checker is missing

Found on 2026-11-21 in the survey made before the checker moved out of the
agents repository, and confirmed the same day with a probe: in a git
repository whose `.pre-commit-config.yaml` lists `id: auditme-changed`, with
a `HOME` that has no `~/.claude/skills/auditme`, `claude/hooks/auditme-stop.sh`
exits 0 with no output, and `python3 -I` on the missing `changed.py` exits 2.
So a reinstall that leaves `~/.claude/skills/auditme` missing or dangling (a
link into a repository that no longer holds the skill, as the move did until
auditor's installer ran) turns the end-of-session audit off without a word.

Cause: `claude/hooks/auditme-stop.sh` runs
`python3 -I "$HOME/.claude/skills/auditme/checks/changed.py"` and blocks only
when its status is 1; any other status falls through to `exit 0`. `changed.py`
itself exits only 0 or 1 (an uncaught exception also exits 1, which blocks),
so the silent statuses are the ones where the checker never ran: 2 for a
missing file, 127 for no `python3`. The project-setup spec's Stop hook section
says only "on exit 1 it prints the Claude Code block decision", so nothing
specifies the other statuses.

Fix direction: small. Before running the checker, block once with a reason
naming the missing path and the install command (`bin/install-claude.py` in
this repository) when `changed.py` is not a file; and block, carrying the
output, on any status other than 0 and 1. Add cases to `tests/test_stop_hook.py`
beside the existing ones: a missing checker, a dangling link, and a stub
exiting 2, each giving one block decision; a stub exiting 0 still gives none.
Update the Stop hook bullet in `agents/specs/project-setup/spec.md` and the
Stop hook section of `docs/reference/cli.md` in the same change.

## The project-setup spec still names the agents repository's pin, deploy key and rule paths

Found on 2026-11-21 in a review of this file, checking the records the move
out of the agents repository brought here. `agents/specs/project-setup/spec.md`
(version 1.5, status implemented) still gives the hook block as
`repo: git@github.com:bnomis/agents.git` (line 366), the upgrade command as
`pre-commit autoupdate --repo git@github.com:bnomis/agents.git` (line 376), the
CI secret as `AGENTS_DEPLOY_KEY` with the `github-agents` host alias and its
`insteadOf` rewrite (lines 390-398), and the deploy-key steps against
`--repo bnomis/agents` (lines 459-461). It also cites
`claude/rules/git-conventions.md` (line 168) and `claude/rules/rule-scope.md`
(line 478) as paths in this repository; both are in the agents repository.

Cause: `5a8eb69` (pin auditor, not agents) moved
`claude/skills/project-setup/SKILL.md` and its templates to
`git@github.com:bnomis/auditor.git`, `{{AUDITOR_REV}}`, `AUDITOR_DEPLOY_KEY`
and `github-auditor`, and did not touch the spec. So the spec contradicts the
templates it specifies, and the spec-drift check and the Doc4 question read it
as implemented.

Fix direction: small. A version 1.6 amendment to
`agents/specs/project-setup/spec.md` that matches the hook block, upgrade
command, secret, alias and deploy-key steps to the templates, and names the
two rules as the agents repository's. If item 1 above lands first or at the
same time, its Stop hook bullet can go in the same amendment. Leave the dated
task lists (`agents/tasks/project-setup/`) unchanged: they are records.

## A project with no audit root skips the project-level checks

Found on 2026-10-31 in `agents/specs/project-setup/spec.md`, amendment 1.2,
which records it as a known limit not fixed there. When a project has no
package under `src/` and no extra root, `audit.py` runs no pass, so the
per-root project-level checks (the lockfile, `AGENTS.md`, spec drift) never
run, and a project with no Python passes them without being checked.

Cause: the project-level checks run inside the per-root loop in `main()` of
`claude/skills/auditme/checks/audit.py`, once per root with duplicates
suppressed. With no root, they never run.

Fix direction: deferred until a project without Python adopts the guards.
Then run the project-level checks once when no root exists, which changes the
driver's contract, so it goes through the spec first.
