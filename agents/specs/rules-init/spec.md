# Rules init

**Version:** 1.0
**Status:** approved
**Date:** 2026-11-25

`auditor rules init` creates a new rules repository from the
[Default rule catalogue](../default-rule-catalogue/spec.md). The user chooses
packs, edits a plain list of the rules those packs hold, and init copies the
rules that are left. The copy is plain: the new repository keeps no link to
the catalogue, its rules are the user's to edit, and later fixes to the
catalogue reach it only when they are copied by hand.

It is the last of four specs and requires the other three to be implemented.

Decided with the user on 2026-11-25:

- **Selection is by pack.** The user chooses packs, then deletes lines from an
  editable list of the rules those packs hold.
- **The copy is plain.** There is no upstream link and no update command.

## Module location

- `src/auditor/rulesinit.py` (new).
- `src/auditor/catalogue/packs.toml` (new).
- `src/auditor/rulescli.py` - gains `init` and `apply`.
- `claude/skills/auditme-project-setup/SKILL.md` - offers to create a rules
  repository when `AUDITOR_RULES_PATH` is unset.

## Packs

A pack is a named group of catalogue rules on one topic. It holds that topic's
checks, questions and standards together, so choosing a topic brings
everything that enforces it. `src/auditor/catalogue/packs.toml` defines the packs:

```toml
[packs.error-handling]
description = "Exception envelopes, domain errors, Raises sections, logging of failures"
rules = ["silent-broad-except", "raises-section-drift", "a1", "a4", "std-error-handling"]
```

The proposed packs are:

- `error-handling`
- `imports`
- `module-surfaces`
- `state-and-effects`
- `duplication`
- `style-and-naming`
- `project-hygiene`
- `testing`
- `documentation`
- `security`
- `performance`

The membership of each rule is decided in the task that writes the file. That
task publishes the proposed membership as a review page, with one
recommendation per rule, and stops until the user has answered every item.
Every catalogue rule is in exactly one pack, which a test checks.

## API

```text
auditor rules init <dest> [--pack <name> ...]
    # writes <dest>/selection.txt and stops
auditor rules apply <dest>
    # copies the rules selection.txt lists into <dest>
auditor rules packs
    # one line per pack: name, rule count, description
```

```python
# src/auditor/rulesinit.py
def write_selection(dest: pathlib.Path, packs: collections.abc.Sequence[str]) -> pathlib.Path:
    """Write `dest/selection.txt`: every catalogue rule under its pack heading.

    Rules of the chosen packs are written as bare lines. Rules of the other
    packs are written commented out (`# <rule-dir>`), so the user can add one
    by removing the `#`. With no packs given, every pack is chosen.

    Raises:
        RulesInitError: an unknown pack, or `dest` already holds `rules/` or `auditor-rules.toml`.
    """


def apply_selection(dest: pathlib.Path) -> list[str]:
    """Copy each rule `dest/selection.txt` names into `dest/rules/` and write the repository files.

    Returns the rule directory names copied, sorted.

    Raises:
        RulesInitError: no selection file, an unknown rule name, a standard
            rule that a selected rule names in `standards` is missing from the
            selection, or `dest/rules/` already exists.
    """
```

## Implementation

**The selection file** holds one rule directory name per line. A line starting
with `#` is a comment, and a line `## <pack>: <description>` is a pack
heading. Blank lines are ignored. Each rule line is followed by its title as a
comment (`raises-section-drift  # Raises: section omits an error the body raises`),
so the user does not need the catalogue open to decide.

**`init`** writes `selection.txt`, creating `<dest>` if it is missing. It
prints the path, then says to edit the file and run `auditor rules apply <dest>`.
It is never interactive, so it works the same from a terminal, from a script
and from Claude Code.

**`apply`** reads the file and validates every name against the catalogue
(`importlib.resources.files('auditor')`, which holds `src/auditor/catalogue/` in the
wheel). It then writes:

- `rules/<dir>/` - each listed directory, copied with its `tests/`;
- `auditor-rules.toml` - `api` set to the runner's `API_VERSION`, and a
  `[source]` table holding `auditor` (version), `commit` (the catalogue's git
  commit, when the package was built from a work tree) and `date`. The table
  is a record of where the rules came from; nothing reads it back;
- `TODO.md` and `DONE.md` - the standard headers of each file, with no items.
  An audit files its change requests in `TODO.md`, and
  `auditor rules pending` blocks the next audit while any item is open (see
  the Rules repository spec, Change requests);
- `README.md` - how to point `AUDITOR_RULES_PATH` at the repository, add a
  rule, and run `auditor rules check` and `auditor rules test`;
- `.gitignore` - `__pycache__/`.

`apply` then runs `git init` when `<dest>` is not already inside a work tree,
and makes no commit. It leaves `selection.txt` in place as the record of the
choice, and runs `auditor rules check` on the result before it returns.

A project is pointed at the new repository by its `.envrc`
(`export AUDITOR_RULES_PATH=<dest>`). Nothing in a rules repository says which
projects use it.

## Error handling

`RulesInitError(Exception)` is a new class. It is reported as
`ERROR: <message>` on stderr with exit 2, and nothing is written. `apply`
validates the whole selection before it copies anything, so a failure leaves
`<dest>` as it was. The messages are:

- `unknown pack 'x': known packs are a, b, c`;
- `selection.txt line 12: no catalogue rule 'raise-drift'`;
- `rule 'silent-broad-except' needs standard 'std-error-handling', which is not selected`;
- `<dest>/rules already exists: rules init creates a new repository; edit the existing one by hand`.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `--pack` | repeatable str | every pack | The packs whose rules start uncommented in `selection.txt` |

## External dependencies

- **git** is used for `git init` and for the catalogue commit at build time.

## Tests

- `init` with one pack writes that pack's rules uncommented and every other
  rule commented out.
- `apply` copies exactly the uncommented names, and its result passes
  `auditor rules check` and `auditor rules test`.
- Each error above, with `<dest>` unchanged afterwards.
- A sweep with `AUDITOR_RULES_PATH` set to a repository made from every pack
  gives the same hits as one with `src/auditor/catalogue/`.
- The wheel built by `uv build` contains `auditor/catalogue/` (checked for data files with a probe build on 2026-11-25).
