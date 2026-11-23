# Project gate settings

**Version:** 1.0
**Status:** approved (review 1, 2026-11-23)
**Date:** 2026-11-23

Two settings that let a project run the published `auditme-all` hook as its
only push gate, without a wrapper script of its own:

- **Never-accepted rules.** `[tool.auditme] never-accepted` names rules (or
  rule families) whose `# auditme: accept` markers do not count in this
  project: a hit of such a rule is always unaccepted, so every hook and
  every report treats it as a finding to fix in the code.
- **The ruff to run.** The `AUDITME_RUFF` environment variable names the
  ruff executable the sweep runs, for a project whose ruff lives in a shared
  virtual environment rather than in its own `.venv`.

## Motivation

One project ran its push gate through its own wrapper around `audit.py`
for two reasons, both measured on 2026-11-23:

- **It refused markers for some rules.** The project fixes every
  `literal-duplication` and `leading-underscore-*` hit and never accepts
  one, and its wrapper failed on those hits whether a marker was present or
  not. The checker already has this idea for two rules (`ruff` and
  `lockfile-drift` hits are never accepted by a marker); a project could
  not extend it.
- **Its ruff was not where the checker looks.** Its projects share one
  virtual environment outside each repository. The checker looks for the
  project's own `.venv/bin/ruff`, then `ruff` on PATH, and found neither in
  a plain shell, so every sweep reported `ruff not installed` and a
  `ruff-version-drift` hit. The wrapper activated the shared environment
  first.

Because the wrapper ran whatever checker was installed, not a pinned
revision, a new rule failed every push the day it was released. Replacing
it with the pinned `auditme-all` hook needs both settings.

## Module location

- `claude/skills/auditme/checks/auditme/core.py`: reading `never-accepted`,
  and refusing markers in `emit`
- `claude/skills/auditme/checks/auditme/registry.py`: `RULE_IDS`
- `claude/skills/auditme/checks/auditme/rules/project_hygiene.py`:
  `ruff_executable`
- `claude/skills/auditme/checks/audit.py`: validating both settings before
  the sweep
- `claude/skills/auditme/checks/changed.py`: the advice printed for a
  refused marker

## API

```python
# auditme/registry.py
RULE_IDS: frozenset[str]
"""Every rule id the checker can emit, `ruff` and `lockfile-drift` included."""


# auditme/core.py
class SettingsError(Exception):
    """A project setting is invalid; the message is the error text."""


class RootsError(SettingsError):
    """`[tool.auditme]` declares an invalid root (unchanged, now a SettingsError)."""


NEVER_ACCEPTED: tuple[str, ...] = ()
"""The current run's `never-accepted` patterns; the driver sets it."""


def never_accepted(scope: pathlib.Path) -> tuple[str, ...]:
    """The `never-accepted` patterns `[tool.auditme]` declares, in order; () when none.

    Raises:
        SettingsError: the value is not a list of strings, or a pattern
            matches no id in `auditme.registry.RULE_IDS`.
    """


def is_never_accepted(rule: str, patterns: tuple[str, ...]) -> bool:
    """True when `rule` equals a pattern, or a pattern ends in `*` and `rule` starts with the text before it."""


# auditme/rules/project_hygiene.py
def ruff_executable(scope: pathlib.Path) -> tuple[str, str]:
    """(command, label) for the ruff the audit runs: `$AUDITME_RUFF` when set
    and not empty, else the project's `.venv/bin/ruff` when executable, else
    `ruff` on PATH. The label for the first is `AUDITME_RUFF`."""
```

A hit whose marker was refused carries one new key:

```json
{"rule": "literal-duplication", "accepted": false, "accepted_reason": null,
 "refused_reason": "<the marker's reason>", "...": "..."}
```

`refused_reason` is present only on such a hit, so every other hit
serialises as before.

## Settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `[tool.auditme] never-accepted` | list of strings | `[]` | Rule ids whose markers never count. An entry ending in `*` matches every id that starts with the text before it (`leading-underscore-*`). |
| `AUDITME_RUFF` (environment) | path | unset | The ruff executable the sweep runs, ahead of `.venv/bin/ruff` and PATH. |

`never-accepted` sits beside `roots` in the same table, which already
refuses unknown keys; `never-accepted` becomes a known one.

## Implementation

**Reading `never-accepted`.** `never_accepted` reads the table the same
way `declared_roots` does (same TOML errors, same "only when the text
mentions `[tool.auditme`" rule) and checks each pattern against `RULE_IDS`:
an exact pattern must be an id, and a `*` pattern must match at least one.
A pattern that matches nothing is an error, not a silent no-op: a misspelt
rule name would otherwise let every marker for that rule count. `*`
anywhere but the end is an error. `ruff` and `lockfile-drift` may be named
but change nothing, since no marker answers for them already.

**Refusing markers.** `audit.py` reads the patterns before the sweep, with
the roots, and sets `auditme.core.NEVER_ACCEPTED`. `emit` is the one place
every hit passes through: when the hit's `rule` is never-accepted and its
`accepted` is true, it sets `accepted` to false, moves `accepted_reason`
to `refused_reason` and sets `accepted_reason` to null, before
de-duplication and printing. No rule changes; every caller (`changed.py`,
the Stop hook, an audit) sees the refusal because it reads `audit.py`'s
output. `--package` and `--extra-root` runs read `never-accepted` too:
it is a property of the project, not of the roots.

**`RULE_IDS`.** A literal `frozenset` in `registry.py`, sorted in the
source. Five call sites pass `rule=rule` rather than a literal, so the set
cannot be derived from the source and is maintained by hand, checked by
the tests below.

**`changed.py`'s advice.** When any reported hit has `refused_reason`, it
prints, after the hit list: `<rule>: this project does not accept markers
for this rule ([tool.auditme] never-accepted); fix the code.` once per
such rule, in place of the generic accept-marker advice for that rule.

**`AUDITME_RUFF`.** `ruff_executable` checks it first. `audit.py` checks
it before the sweep: when set and not empty, it must name an executable
file, and the run exits 2 otherwise (below). The variable is read from the
environment the hook runs in; the project sets it where it sets the rest of
its environment.

**Documentation.** `docs/guide/checker.md` (a "Never-accepted rules"
section beside declared roots, and `AUDITME_RUFF` where ruff is
described), `docs/reference/cli.md` (both settings and the new exit-2
cases), `docs/setup.md` (the ruff prerequisite names `AUDITME_RUFF`), and
the acceptance mechanism in `claude/skills/auditme/SKILL.md` and
`audit.py`'s docstring (a project can refuse markers for named rules).

## Error handling

| Failure | Where | Result |
|---|---|---|
| `never-accepted` is not a list of strings, or has a pattern matching no rule id, or a `*` not at the end | `audit.py`, before anything is emitted | `ERROR: pyproject.toml [tool.auditme]: <detail>` on stderr, exit 2; `changed.py` then fails as for any sweep that exits non-zero |
| `AUDITME_RUFF` is set but names no executable file | `audit.py`, before anything is emitted | `ERROR: AUDITME_RUFF=<value> is not an executable file` on stderr, exit 2. The value is a path, not a secret. |
| Both drivers catch `SettingsError` | `audit.py` | `RootsError` is now a `SettingsError`, so one handler covers both |

## Testing

In `claude/skills/auditme/tests/`:

- `test_roots.py` (or a new `test_settings.py`): `never-accepted` read,
  ordered and validated; an unknown id, a `*` matching nothing and a
  misplaced `*` each exit 2 with the message above; a non-list exits 2;
  absent means `()`.
- `test_core.py`: `is_never_accepted` for an exact id, a family, and a
  near miss (`leading-underscore` against `leading-underscore-*`); `emit`
  refuses a marked hit of a listed rule and leaves an unlisted rule's
  marked hit accepted (a positive and a negative case).
- `test_driver.py`: a fixture project with a `literal-duplication` hit
  carrying a scoped marker reports `accepted: false` with `refused_reason`
  when the rule is listed, and `accepted: true` when it is not.
- `test_changed.py`: `--all` fails on the refused hit and prints the
  never-accepted advice.
- `test_project_hygiene.py`: `AUDITME_RUFF` wins over `.venv/bin/ruff`;
  an unset or empty value falls through; a value naming no executable
  exits 2.
- `test_registry.py`: every `rule='<literal>'` in `auditme/` is in
  `RULE_IDS`, and `RULE_IDS` equals the first-column ids of every `Rule id`
  table under "The rules" in `docs/guide/checker.md`; a rule added without
  both fails.

## External dependencies

None. The checker stays standard-library only (`tomllib`, `os`).

## Compatibility

A project with neither setting sees no change: no `refused_reason` key, the
same ruff lookup. A project that pins a revision before this one and adds
`never-accepted` gets the existing "unknown key" error, which names the key.
