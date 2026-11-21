# Skills

Each skill is a directory under `claude/skills/<name>/` holding a `SKILL.md`
and any scripts or templates it uses. `bin/install-claude.py` links
`claude/skills/` into `~/.claude/skills/`, so each skill is available in every
project as `~/.claude/skills/<name>/`. The other shared skills are in the
agents repository (`bnomis/agents`, <https://bnomis.github.io/agents/>).

Invoke a skill in Claude Code as `/<name> [args]`, or by asking for what it
does: the `when_to_use` list in each skill's frontmatter names the phrases
that trigger it ("audit the code", "set up a new project").

| Skill | Invocation | Purpose |
|---|---|---|
| [auditme](#auditme) | `/auditme [scope]` | Scripted and checklist audit of code, specs and docs |
| [project-setup](#project-setup) | `/project-setup new [path]`, `/project-setup adopt [path]` | Install the shared audit hooks, CI gate and project files |

## /auditme {#auditme}

```text
/auditme [scope] [--category <category>]
```

Scope is empty (specs, `src/`, `bin/`, `docs/`, `AGENTS.md`, `README.md`), a
file path, a spec slug, or the docs. `--category` (`standards`,
`architecture`, `performance`, `security`, `testing`, `dependencies`,
`documentation`) is a debugging aid; a normal audit runs every category.

- **Runs:** the scripted sweep
  `python3 ~/.claude/skills/auditme/checks/audit.py <project-root>`, then a
  fixed checklist applied by one subagent per question across every file in
  scope, then a spec review and re-verification of earlier findings.
- **Refuses to start** while `claude/skills/auditme/requests.md` has open
  checker change requests.
- **Writes:** `agents/audit-reviews/review-N.md`,
  `agents/audit-reviews/summary.md`, `agents/audit-reviews/index.md`, and
  marks shipped tasks done in `agents/tasks/audit-reviews/`.
- **Then:** runs `/taskdev agents/audit-reviews/review-N.md` if there are
  findings.
- **Stops for:** uncommitted changes; commit (`auditme: add review-N`).

The checker, its rules and accept markers are described in
[The checker](../guide/checker.md).

## /project-setup {#project-setup}

```text
/project-setup new [<path>]
/project-setup adopt [<path>]
```

Path defaults to the current repository root. Templates are in
`claude/skills/project-setup/templates/`.

- **`new`:** writes `.pre-commit-config.yaml` (ruff, shellcheck, and the
  `auditme-changed` and `auditme-all` hooks pinned to this repository's
  current `main` commit), `.github/workflows/ci.yml`, `AGENTS.md`,
  `CLAUDE.md`, `TODO.md`, `DONE.md` and `claude/rules/README.md`; installs the
  pre-commit and pre-push hooks; then runs the deploy-key steps. Asks before
  overwriting any existing file.
- **`adopt`:** adds the auditme hooks, offers to remove a project-local hook
  doing the same job, and counts unaccepted hits with
  `pre-commit run auditme-all --hook-stage manual --all-files`. At zero hits
  it enables the pre-push stage, adds the CI audit step and runs the
  deploy-key steps; otherwise it files a dated `TODO.md` item instead and
  enables neither gate.
- **Deploy-key steps:** generate an ed25519 key in a temporary directory, add
  the public key as a read-only deploy key on this repository, set it
  as the `AUDITOR_DEPLOY_KEY` secret on the project, then delete the files.
  The private key is never printed.
- **Stops for:** the project name and test command; each deploy-key and
  secret command; commit. Never pushes.

See [Setup](../setup.md) for the full walk-through.
