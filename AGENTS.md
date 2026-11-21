# auditor

The `auditme` audit checker (`claude/skills/auditme/`), the pre-commit hooks
that run it (`.pre-commit-hooks.yaml`), the Claude Code Stop hook that runs it
at the end of a session (`claude/hooks/auditme-stop.sh`) and the
`/auditme-project-setup` skill that adopts the hooks in a project
(`claude/skills/auditme-project-setup/`).

## Installing

`bin/install-claude.sh` links `claude/skills/auditme`,
`claude/skills/auditme-project-setup`, `claude/rules/auditme` and
`claude/hooks/auditme-stop.sh` into `~/.claude` and registers the Stop hook in
`~/.claude/settings.json`. The other shared rules and skills come from the
agents repository's own installer.

## Tests

From the repository root:

```shell
uv run pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider
```

## No project names

This repository serves many projects. Its code, tests, fixtures, specs, task
lists, records and commit messages name no project it has been run on: a run
that found something is "one project". The `no-project-names` hook
(`bin/check-foreign-names.sh`), published here and run on this repository too,
enforces it at commit and commit-msg time; install
both hook types with
`pre-commit install --hook-type pre-commit --hook-type pre-push --hook-type commit-msg`.
