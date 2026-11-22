# Setting up the shared guards

This guide takes you from nothing to a project whose commits and CI run the
shared audit checks. It covers a new machine, a new user, a new project and an
existing one.

## What you get

- **`auditme-changed`** - a pre-commit hook. It sweeps the whole tree with the
  auditme checker, then fails the commit on any unaccepted hit in a file the
  commit changes, or in a file a cross-file hit names as related to one.
- **`auditme-all`** - the same sweep reported over every file. It is published
  at the manual stage, and a project with no unaccepted hits also runs it on
  every push and in CI, so a hit in a file nobody touched still fails the push.
- **A Stop hook** - a Claude Code hook that blocks the end of a turn once while
  an opted-in project's changed files carry unaccepted hits.
- **`/auditme-project-setup`** - a skill that writes the config, CI workflow
  and project files for a new project, or adopts the hooks into an existing one.

The checker audits the packages under `src/<package>/` and the scripts in
`bin/`. `src/` is optional: a project with only `bin/` is audited over `bin/`,
and a project with no Python at all gets only the project-level checks: its
`uv.lock` against `pyproject.toml`, its `ruff-pre-commit` pin against the
ruff the audit runs, and its Markdown (`spec-api-signature-drift`). A `.py` file directly in `src/`
belongs to no package, so it is reported as a `src-loose-module` hit; move it
into a package, or accept it with a line-1 marker. No other directory's Python
is swept.

A project whose Python lives elsewhere declares its roots in `pyproject.toml`
instead, and the declared list replaces `src/` and `bin/`:

```toml
[tool.auditme]
roots = [
    { path = "tools/mypkg" },
    { path = "tools", modules = "top-level" },
    { path = "tests" },
]
```

A directory that is not declared is not swept. See
[`audit.py`](reference/cli.md#claudeskillsauditmechecksauditpy) for the
`modules` values and the errors.

The checker also reads files outside those passes:

- every `.md` file under the project, outside hidden directories and `.git`,
  `.venv`, `node_modules`, `__pycache__`, `audit-reviews` and `tasks`, for
  function signatures in a spec that no longer match the code
  (`spec-api-signature-drift`);
- `pyproject.toml` and `uv.lock` (`lockfile-drift`), `.pre-commit-config.yaml`
  (`ruff-version-drift`) and `AGENTS.md`, which declares project standards
  some rules enforce.

The checker's rules are described in [The audit checker](guide/checker.md) and
in `claude/skills/auditme/SKILL.md`.

### Why the scopes differ

The commit hook looks at changed files only, so a commit is never blocked by
someone else's old hit. CI looks at the whole tree, so a hit that appears
without touching its file (a cross-file duplicate, say) is still caught. A
cross-file hit counts as changed when either of its files changed.

### Why the checker is pinned

Projects pin the hooks to a revision of this repository (`rev:` in
`.pre-commit-config.yaml`). A new rule therefore never fails a build until you
choose to upgrade (see [Upgrading the checker](#upgrading-the-checker)).

### Why the Stop hook is global

The Stop hook is registered once, in `~/.claude/settings.json`, and does
nothing in a project whose `.pre-commit-config.yaml` lacks `id: auditme-changed`.
It runs the installed checker, not the project's pinned one, so it is an early
warning and the pinned hook stays the authority. In a worktree of the auditor
checkout the installed checker links into, it runs that worktree's own checker
instead, so a branch that changes the checker is judged by its own version. No
other repository's copy of the checker is ever run.

## A new machine

Prerequisites:

- `git`
- `gh`, authenticated: `gh auth login`
- an SSH key registered on GitHub with read access to this repository,
  `bnomis/auditor` (see
  [A new user](#a-new-user))
- `uv`, from <https://docs.astral.sh/uv/>
- `pre-commit`: `uv tool install pre-commit`
- Python meeting `requires-python` in `pyproject.toml`; the hooks run with the
  `python3` their shebang finds on `PATH`
- `jq`, used by the Stop hook
- `ruff`, which the checker runs: the project's own `.venv/bin/ruff` when it
  exists (after `uv sync`), whatever else is on `PATH`; otherwise `ruff` from
  `PATH`, such as `uv tool install ruff`. Without either, a sweep that audits a
  package or extra root reports `ruff not installed`; a project with no audit
  root runs only the project-level checks and does not. It must be the version the ruff hook's `rev`
  in `.pre-commit-config.yaml` pins; otherwise the sweep reports
  `ruff-version-drift`. Make them equal with `uv add --dev ruff==<version>`,
  or change the hook's `rev`

Install:

```shell
git clone git@github.com:bnomis/auditor.git <directory>
cd <directory>
bin/install-claude.sh
```

`<directory>` is wherever you keep your source. The script runs the shared
installer, `install-in-claude`, with `uvx` at a pinned commit, so it needs
`uv` and SSH access to `bnomis/install-in-claude`; add `--dry-run` to see what
it would change first. It links
`claude/` into `~/.claude/` one level down: each directory (`hooks/`, `rules/`,
`skills/`) becomes a real directory of symlinks to its entries. It renames
any existing file in a link's place to `.orig`. In `~/.claude/settings.json`
it adds the Stop hook once. It keeps every other setting, and saves the
original as `settings.json.orig`. It refuses to touch a settings file that is
not a valid JSON object.

The other shared rules and skills, and the status line, come from the agents
repository (`bnomis/agents`), installed the same way with its own
installer; see its docs at <https://bnomis.github.io/agents/>.

Check it:

```shell
ls ~/.claude/skills
grep -n 'auditme-stop.sh' ~/.claude/settings.json
```

## A new user

1. Ask the repository owner for read access to `bnomis/auditor`.
2. Create your own SSH key and add it to your GitHub account:
   `ssh-keygen -t ed25519`, then `gh ssh-key add ~/.ssh/id_ed25519.pub`.
3. Check access: `git ls-remote git@github.com:bnomis/auditor.git refs/heads/main`
   prints a commit and a ref.

The shared rules and skills in the agents repository hold nothing specific
to one project. A project's own rules and skills go in its `claude/` directory
(`claude/rules/`, `claude/skills/`); see the agents repository's
`claude/rules/rule-scope.md`.

## A new project

In an empty repository, in Claude Code:

```text
/auditme-project-setup new
```

It asks for the project's test command, then writes:

- `.pre-commit-config.yaml` - ruff, shellcheck and both audit hooks, pinned to
  the current `main` of this repository, with `auditme-all` also run on push
- `.github/workflows/ci.yml` - tests, the commit-time checks over the whole
  tree, and `auditme-all`
- `AGENTS.md`, `CLAUDE.md`, `TODO.md`, `DONE.md` and `claude/rules/README.md`

It installs the git hooks with `pre-commit install --hook-type pre-commit
--hook-type pre-push`, then offers to create the deploy key.

### The deploy key

CI clones this repository over SSH, so it needs a read-only deploy key. The
skill, asking before each step:

1. generates a key pair in a scratch directory,
2. adds the public half to `bnomis/auditor` with `gh repo deploy-key add`,
3. stores the private half in the project's `AUDITOR_DEPLOY_KEY` secret with
   `gh secret set`,
4. deletes both files.

GitHub accepts a deploy key on one repository only, so each project has its
own key.
The workflow installs it under the `github-auditor` host alias and rewrites the
clone URL to use it.

## An existing project

```text
/auditme-project-setup adopt
```

It adds the two hooks to `.pre-commit-config.yaml`, and shows you any
project-local runner or Stop hook doing the same job before asking to remove it.

Then it counts unaccepted hits by rule over the whole tree:

```shell
pre-commit run auditme-all --hook-stage manual --all-files
```

- **No hits:** it runs `auditme-all` on push as well, adds the CI step and
  offers the deploy key.
- **Hits:** it files one `TODO.md` item with the dated count by rule, and leaves
  the push stage and CI alone. Fix or accept every hit, then enable both.

A hit is accepted with a comment on its line or the line above:

```python
# auditme: accept[<rule>] <reason>
```

Why no gate over a backlog: a gate that fails every push gets switched off.

To enable the gates later, add `stages: [manual, pre-push]` under
`- id: auditme-all` in `.pre-commit-config.yaml`, paste
`claude/skills/auditme-project-setup/templates/ci-audit-step.yml` into the
workflow after the project's own setup, and run the deploy-key steps.

## Moving a project from agents

A project that adopted the hooks while the checker lived in the agents
repository pins `git@github.com:bnomis/agents.git`. That pin keeps working
until the project is moved: the agents commits it names still hold the
checker, so its hooks and CI run as before. They get no new rules or fixes,
which land only here.

To move it:

1. In `.pre-commit-config.yaml`, change the audit hooks' `repo:` from
   `git@github.com:bnomis/agents.git` to `git@github.com:bnomis/auditor.git`,
   and their `rev:` to a commit of this repository:
   `git ls-remote git@github.com:bnomis/auditor.git refs/heads/main`, first
   field. The hook ids are unchanged.
2. Add a deploy key for `bnomis/auditor` (see [The deploy key](#the-deploy-key)):
   a key on `bnomis/agents` does not open this repository, and GitHub accepts
   a deploy key on only one repository, so it is a new key. Store its private
   half in a new `AUDITOR_DEPLOY_KEY` secret on the project; the old
   `AGENTS_DEPLOY_KEY` secret can be deleted once CI passes.
3. In the CI workflow, replace the deploy-key steps with those in
   `claude/skills/auditme-project-setup/templates/ci-audit-step.yml`: they read
   `AUDITOR_DEPLOY_KEY`, install it under the `github-auditor` host alias, and
   rewrite `bnomis/auditor.git` rather than `bnomis/agents.git`.
4. Run `pre-commit run auditme-all --hook-stage manual --all-files`, and fix or
   accept any new hits in the same commit, as for an upgrade.
5. If the project also pins the `no-project-names` hook from
   `bnomis/agents`, move it into the auditor block beside the audit hooks,
   keeping its `args:`. It moved here too, and the agents repository no
   longer publishes it. A project that pinned only that hook from agents
   then needs no agents deploy key: remove the agents deploy-key steps from
   its CI workflow and delete its `AGENTS_DEPLOY_KEY` secret.

The old deploy key on `bnomis/agents` can then be removed.

## Upgrading the checker

```shell
pre-commit autoupdate --repo git@github.com:bnomis/auditor.git
pre-commit run auditme-all --hook-stage manual --all-files
```

A new rule can report hits in code that passed before. Fix or accept them in
the same commit as the upgrade, so `main` never carries a failing gate.

## Troubleshooting

**The hook cannot clone this repository.** Run
`git ls-remote git@github.com:bnomis/auditor.git refs/heads/main` on your
machine. If it fails, your SSH key lacks access. In CI, check that the
`AUDITOR_DEPLOY_KEY` secret exists, that the deploy key is on `bnomis/auditor`,
and that the `Install the audit deploy key` step ran before `pre-commit`.

**The Stop hook does not fire.**

- The project is not opted in: its `.pre-commit-config.yaml` must contain
  `id: auditme-changed`.
- `jq` is missing: `command -v jq`.
- The installer has not run: `grep -n 'auditme-stop.sh' ~/.claude/settings.json`.
- No diff base resolves (no upstream, `origin/main` or `main`): `changed.py` prints that and passes without sweeping. Check `git rev-parse --verify origin/main`.
- No reportable file changed, so `changed.py` skipped the sweep.
- The directory is not a git repository: the Stop hook finds no repository root and exits 0 itself, without running `changed.py`.

**Hits appear only after an upgrade.** Expected: the new checker has new rules.
See [Upgrading the checker](#upgrading-the-checker).

**One commit must go through.**

```shell
SKIP=auditme-changed git commit
```

The push and CI still sweep the whole tree, so the hit must be fixed or
accepted before they pass. For one push, `SKIP=auditme-all git push`.
