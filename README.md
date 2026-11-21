# auditor

The auditme audit checker, the `auditme-changed` and `auditme-all` pre-commit
hooks that projects pin to run it, the Claude Code Stop hook that runs it
before a turn ends, and the `/auditme-project-setup` skill that adopts the
hooks in a project. `bin/install-claude.py` links the skills and the Stop hook into
`~/.claude/`; the shared rules and other skills come from the agents
repository (`bnomis/agents`). The setup guide, from a new machine to a project
with working guards, is [docs/setup.md](docs/setup.md); the docs site is
<https://bnomis.github.io/auditor/>.

## Working on this repository

Run the tests:

```shell
uv run --no-project --with pytest pytest claude/skills/auditme/tests claude/skills/auditme-project-setup/tests tests -q -p no:cacheprovider
```
