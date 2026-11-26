# auditor

The auditme audit checker, the `auditme-changed` and `auditme-all` pre-commit
hooks that projects pin to run it, the `no-project-names` pre-commit hook
(published here, independent of the checker), the Claude Code Stop hook that
runs it before a turn ends, and the `/auditme-project-setup` skill that adopts the
hooks in a project, with the Python rules the checker enforces
(`claude/rules/auditme/`). `bin/install-claude.sh` links the skills, the rules
and the Stop hook into `~/.claude/`; the other shared rules and skills come
from the agents repository (`bnomis/agents`). The setup guide, from a new machine to a project
with working guards, is [docs/setup.md](docs/setup.md); the docs site is
<https://bnomis.github.io/auditor/>.

## Working on this repository

Run the tests:

```shell
uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider
```
