# Rules repository

**Version:** 1.0
**Status:** implemented
**Date:** 2026-11-25

Lets the runner read its rules from a separate repository named by
`$AUDITOR_RULES_PATH`, instead of a registry compiled into the package. Rules
can then grow, and differ between projects, without a runner release. This
spec defines:

- the format of a rules repository;
- the loader;
- the versioned helper API that rule code imports;
- the commands that report on a rules repository;
- how an audit records which rules it ran.

It is the second of four specs (see [Auditor CLI](../auditor-cli/spec.md)) and
requires that spec to be implemented. Until the
[Default rule catalogue](../default-rule-catalogue/spec.md) spec is
implemented, a run with `$AUDITOR_RULES_PATH` unset still uses the built-in
registry (`auditor.registry`). That spec removes the built-in registry.

Decided with the user on 2026-11-25:

- Every part of a rule moves out of the runner: its prose standard, its Python
  check and its Phase B question.
- Each rule is one directory.
- Helpers that more than one rule uses belong to the runner's versioned API,
  not to the rules repository.
- The prose standards reach Claude through a SessionStart hook that runs
  `auditor rules standards`.

## Module location

- `src/auditor/rulesrepo.py` (new) - loads and validates a rules repository.
- `src/auditor/api/` (new) - the helper API that rule code imports.
- `src/auditor/rulescli.py` (new) - the `auditor rules` subcommands.
- `src/auditor/sweep.py`, `src/auditor/phaseb/candidates.py` - run the loaded
  rules.
- `claude/hooks/auditme-standards.sh` (new) - the SessionStart hook.

## Repository format

```text
<rules-repo>/
  auditor-rules.toml        # api = "1.0", plus a source table (see Rules init)
  TODO.md                   # open rule work: change requests an audit raised
  DONE.md                   # finished and rejected rule work
  rules/<rule-dir>/
    rule.toml               # required
    rule.md                 # required: the standard or question, in prose
    check.py                # kind check or project-check
    brief.md                # kind question with a lister
    lister.py               # kind question with a lister
    tests/test_*.py         # optional; run by `auditor rules test`
```

`rule.toml` holds these keys:

| Key | Type | Required | Meaning |
|-----|------|----------|---------|
| `kind` | str | yes | `check` (one pass per root), `project-check` (once per project), `question` (Phase B) or `standard` (prose only) |
| `title` | str | yes | One line, shown by `auditor rules list` |
| `emits` | list of str | check kinds | Every rule id the check can emit; the directory name when it emits one id |
| `id` | str | question | The Phase B question id, e.g. `A4` |
| `category` | str | question | One of `A`, `S`, `P`, `Sec`, `T`, `D` or `Doc` |
| `kinds` | list of str | question with lister | The finding kinds of a result line |
| `batch-size` | int | no | Default 48, as today |
| `takes-depth` | bool | no | Default false, as today |
| `standards` | list of str | no | Directories of `standard` rules this rule enforces |

`check.py` defines `check(scope: pathlib.Path, src_root: pathlib.Path) -> None`,
which reports hits through `auditor.api.emit`. This is the signature every
entry of `CHECKS` and `PROJECT_CHECKS` has today. `lister.py` defines
`list_candidates(scope: pathlib.Path, depth: int) -> list[auditor.api.Candidate]`.
The `depth` argument is passed only when `takes-depth` is true.

The name of a rule directory is lowercase, with hyphens. A question's
directory is its id in lower case (`a4`). The rule ids across the whole
repository are unique.

## API

```python
# src/auditor/rulesrepo.py
API_VERSION = (1, 0)


@dataclasses.dataclass(frozen=True)
class Rule:
    """One rule directory, validated."""

    name: str
    kind: str
    path: pathlib.Path
    meta: collections.abc.Mapping[str, object]


@dataclasses.dataclass(frozen=True)
class RulesRepo:
    """A loaded rules repository and its identity."""

    root: pathlib.Path
    api: tuple[int, int]
    rules: tuple[Rule, ...]  # sorted by name

    def rule_ids(self) -> frozenset[str]:
        """Every rule id the repository's checks can emit, plus the runner's own ids."""


def rules_root() -> pathlib.Path:
    """Return the directory `$AUDITOR_RULES_PATH` names, resolved.

    Raises:
        RulesRepoError: the variable is unset or empty, or the directory does not exist.
    """


def load(root: pathlib.Path) -> RulesRepo:
    """Read and validate every rule directory under `root/rules/`; import no rule code.

    Raises:
        RulesRepoError: a malformed or missing file, an unknown key or kind,
            a duplicate rule id, or an API version this runner cannot serve.
    """


def import_entry(rule: Rule, filename: str) -> types.ModuleType:
    """Import `check.py` or `lister.py` of one rule, as module `auditor_rules.<name>.<stem>`.

    Raises:
        RulesRepoError: the file does not define the entry function its kind needs.
    """


@dataclasses.dataclass(frozen=True)
class Identity:
    """What shaped an audit's results."""

    runner: str  # auditor version
    api: str  # e.g. '1.0'
    rules_path: str
    rules_commit: str | None  # None when the repository is not a git work tree
    rules_dirty: bool
    rules_digest: str  # sha256 over every tracked file under rules/, in path order


def identity(repo: RulesRepo) -> Identity:
    """Return the identity of the runner and the rules repository it loaded."""
```

`auditor.api` re-exports the helpers that rule code may call:
`emit`, `Candidate`, every reader and resolver in `auditor.core`, and the
shared helpers that the catalogue spec promotes. Nothing outside
`auditor.api` is part of the contract. A rule that imports `auditor.core`
directly is reported by the loader's `rules check` (see Commands).

## Commands

```text
auditor rules list [--kind K]
    # one line per rule: name, kind, emits or id, title
auditor rules check
    # validate the repository: load, import every entry, no imports outside auditor.api
auditor rules test [pytest args]
    # run pytest over rules/*/tests with the auditor.testing plugin
auditor rules standards
    # print every standard rule's rule.md, in name order
auditor rules questions [--category C]
    # print the Phase B checklist: id, title, rule.md of each question
auditor rules identity [--expect <json-file>]
    # print Identity as JSON; with --expect, exit 1 when it differs
auditor rules pending
    # list each open item (a `## ` heading) in TODO.md; exit 1 when there is one
```

`auditor check` and `auditor phaseb` load the repository that
`$AUDITOR_RULES_PATH` names. `auditor check` runs every `project-check` once,
then every `check` once per root. Both run in rule-name order, which replaces
the hand-kept order of `CHECKS` and `tests/registry-order.txt`. Comparisons of
findings already treat the hits as a set, so the order changes no result.

## Implementation

**Loading.** `load` parses `auditor-rules.toml` and each `rule.toml` with
`tomllib`. It checks each key against the table above and the files each kind
needs, and imports nothing. Rule code is imported only when a command runs
it:

- `import_entry` builds the module with `importlib.util.spec_from_file_location`
  under the name `auditor_rules.<name>.<stem>`, using the directory name with
  hyphens replaced by underscores;
- it registers the module in `sys.modules` before running it, so that
  dataclasses and pickling inside rule code resolve;
- it puts nothing on `sys.path`. A rule therefore cannot import another rule,
  and a helper that two rules share belongs in `auditor.api`.

**Caching.** The repository is loaded once per process.
`auditor.core.clear_source_cache` also clears the loaded repository, so tests
can switch between fixture repositories.

**Import boundary.** `rules check` parses each rule file with `ast` and
reports every `import auditor.<x>` where `<x>` is not `api`. The rule is "use
the API only", so the check catches what a runtime import would let through.

**Phase B.** The registry in `auditor.phaseb.candidates` is built from the
loaded `question` rules that have a lister. `kinds`, `batch-size` and
`takes-depth` come from `rule.toml`, and the brief is the rule's `brief.md`.
The plan, check, merge and ledger code in `auditor.phaseb` is the runner's
and does not change.

## Error handling

`RulesRepoError(SettingsError)` is a new class. Every command reports it as
`ERROR: <message>` on stderr, with exit 2 and nothing on stdout, as an invalid
`[tool.auditme]` is reported today. Each message names the file and the fix:

- **Variable unset:** `AUDITOR_RULES_PATH is not set: create a rules repository with 'auditor rules init <dir>' and point the variable at it (docs/setup.md)`.
- **API mismatch:**
  `rules repository needs API 1.3; this auditor serves 1.0: upgrade auditor or use an older rules repository`.
  A different major version is refused, and so is a minor version above the
  runner's own.
- **Bad rule:** `rules/<dir>/rule.toml: <what is wrong>`.
- **A rule's code raises during the sweep:** this is reported as today's
  `auditme-check-crash` hit, naming the rule directory, and the sweep goes on.

## Trust

`auditor check` imports and runs Python from the rules repository. The rules
repository is therefore trusted code, in the same way as a project's own
`conftest.py`. The runner loads a rules repository only from
`$AUDITOR_RULES_PATH`, never from a path that the audited project names.
`docs/concepts.md` says this.

## Standards hook

`claude/hooks/auditme-standards.sh` is a SessionStart hook that
`bin/install-claude.sh` registers. Its rules:

- It runs only in a project that has opted in to the hooks, using the Stop
  hook's opt-in test.
- It prints `auditor rules standards` to stdout, which Claude Code adds to the
  session's context.
- When the variable is unset or the repository is invalid, it prints the
  `ERROR:` line instead, so that the session says why the standards are
  missing.
- It always exits 0.

## Recording identity

The review template in `claude/skills/auditme/SKILL.md` replaces its
`**Script version:**` line with an `**Auditor identity:**` line, holding
`auditor rules identity` as JSON. The skill:

- refuses to start an audit while `rules_dirty` is true. The convergence rule
  forbids rules changing during an audit, and a dirty tree is not a fixed
  version;
- compares the new identity with the previous review's identity. When they
  differ, the review says
  `Rules changed since review N: <the fields that changed>`, and it is not
  counted as a convergence measurement, because new findings may come from
  new rules rather than from the code.

The Phase B verdict ledger is unchanged. Its brief version and candidate hash
already catch a changed question.

## Change requests

Today, a pattern an audit finds that the sweep should check is written to
`claude/skills/auditme/requests.md`, and the next audit may not start until
that file's `## Open` section is empty. With the split, these requests become
items in the rules repository's own `TODO.md`. Decided with the user on
2026-11-25.

- **Filing.** After the review is written, the audit files each new request
  with the `todo-add` skill in `$AUDITOR_RULES_PATH/TODO.md`, in the usual
  item shape: dated, checked against the code, and merged into an existing
  item when the two share a cause. An audit still never changes a rule while
  it runs (failure mode 1 in the skill's convergence section).
- **The precondition.** Step 3 of the skill runs `auditor rules pending`
  before the sweep, and the audit does not start while it exits 1. A rules
  repository's `TODO.md` holds only rule work, so every open item blocks. The
  check is a command rather than a sentence in the skill, so it cannot be
  skipped by reading the skill from memory.
- **Shipping.** An item leaves `TODO.md` the way `todo-do` moves any item:
  implement the rule, run the sweep on a real project, land fixes or accept
  markers for what it newly finds, then move the item to `DONE.md` with its
  `Done:` line.
- **Rejecting.** The item moves to `DONE.md` with
  `Done: rejected on <date> - <reason>`. When it concerns one rule, the
  reason is also added under a `## Rejected widenings` heading in that rule's
  `rule.md`, so that anyone who edits the rule sees it. Before filing, the
  audit searches `DONE.md` and the relevant `rule.md`, so that an idea
  already rejected is not raised again.
- **Runner requests.** A request whose fix is in the runner or the skill,
  rather than in a rule, goes in the auditor repository's own `TODO.md`. It
  does not block audits, because a user of the runner cannot fix the runner.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `AUDITOR_RULES_PATH` | env, path | none (required once the catalogue spec lands) | The rules repository the runner loads; set per project with direnv |
| `api` in `auditor-rules.toml` | str `"M.m"` | none (required) | The helper API version the repository's code was written for |

## External dependencies

- **tomllib** (standard library) reads `rule.toml` and `auditor-rules.toml`.
- **pytest** is needed only by `auditor rules test`. It is the extra
  `auditor[test]`; without it, the command exits 2 and names the extra.
- **git** is used for `rules_commit` and `rules_dirty`.

## Tests

- Fixture rules repositories under `tests/rulesrepo/fixtures/`, covering:
  - one rule of each kind;
  - each error above;
  - an API minor version above the runner's;
  - a duplicate id.
- `auditor check` on a fixture project with a fixture rules repository emits
  exactly the fixture's hits.
- A rule whose `check` raises yields one `auditme-check-crash` hit, and the
  other rules still run.
- `rules identity --expect` exits 0 on the same identity and 1 after a commit
  to the rules repository.
- The standards hook prints the standards and exits 0 when the repository is
  valid, and prints the `ERROR:` line and exits 0 when it is not.
- `rules pending` exits 0 when there is no `TODO.md`, or when it has no
  `## ` heading. It exits 1 and lists each heading when there is one.
  Headings inside fenced code blocks are not counted.
