# Listed Phase B documentation questions

**Version:** 1.5
**Status:** implemented
**Date:** 2026-11-20

Puts the auditme Phase B questions Doc4 (specs match implementation), Doc5
(user docs match implementation), Doc1 (`AGENTS.md` project structure
matches the layout) and Doc2 (`AGENTS.md` tools and libraries list is
current) on the listed path of [Repeatable Phase B](../repeatable-phase-b/spec.md):
a lister names every site, reviewers judge each against a versioned brief,
and a ledger reuses each verdict while its hash is unchanged. It also
settles how the questions that stay sampled run.

## Motivation

Measured on 2026-11-20 on one project's last three full audits, counting
the Phase B question each finding names (a finding may name more than one):
Doc1, Doc2, Doc4 and Doc5 13; T1 and T2 7; A1, A11, A17 and A19 9; A13 and
A15 5; A4 3; the rest 5. Listing A4 alone covers the smallest group. This
spec is the first group of the `TODO.md` item "Put the Phase B questions
that find most onto the listed path"; it extends the repeatable-phase-b API
and leaves that spec as the record of version 1.

## Module location

The checker is not under `src/`; this repository keeps it with its skill.

- `claude/skills/auditme/checks/auditme/phaseb/docrefs.py` - new: sections,
  code-shaped names, resolution
- `claude/skills/auditme/checks/auditme/phaseb/candidates.py` - the four
  listers, registered beside A4
- `claude/skills/auditme/checks/auditme/core.py` - gains
  `corpus_definitions`, hoisted from `_source_definitions` in
  `rules/project_hygiene.py`
- `claude/skills/auditme/phaseb/briefs/{Doc1,Doc2,Doc4,Doc5}.md` - version 1 when written
- `claude/skills/auditme/tests/phaseb/` and `claude/skills/auditme/SKILL.md`

**Prerequisite:** `agents/tasks/repeatable-phase-b/tasks-1.md` has merged
to `main`. Check: `grep -c '^\*\*Status:\*\* implemented'
agents/specs/repeatable-phase-b/spec.md` prints `1` and `python3
claude/skills/auditme/checks/phaseb.py candidates . --question A4` exits 0.
Otherwise stop: this spec needs its `Candidate`, registry, ledger and the
shared call resolver its Task 1 puts in `core.py`.

## API

```python
@dataclasses.dataclass(frozen=True)
class DocSection:
    """A markdown section: a heading to the next heading of any level, outside fences."""

    doc: str  # repo-relative path
    heading_path: str  # enclosing headings' titles joined by ' > ', '#2' on a repeat
    start: int
    end: int
    names: list[tuple[int, str]]  # (line, token) per code-shaped name, in line order


@dataclasses.dataclass(frozen=True)
class DocTarget:
    """What a name resolves to; kind is function, class, method, setting, option, field, file or directory."""

    kind: str
    id: str  # 'path::qualname', or 'path' for a file or directory
    path: str
    start: int
    end: int


def read_sections(path: pathlib.Path, root: pathlib.Path) -> list[DocSection]:
    """Split a markdown file into sections with their code-shaped names.

    Raises:
        PhaseBError: the file cannot be read or decoded as UTF-8.
    """


def read_name_targets(token: str, doc: pathlib.Path, index: CorpusIndex) -> list[DocTarget]:
    """Resolve one token: [] for nothing, one target, or several when ambiguous.

    Reads a matching file's bytes, through the per-run cache, for its line count.

    Raises:
        PhaseBError: a matching file cannot be read for its line count.
    """


def corpus_definitions(scope: pathlib.Path, src_root: pathlib.Path, *, classes: bool = False) -> dict[str, list[tuple[ast.AST, pathlib.Path]]]:
    """Module-level defs across the corpus by bare name; with classes, classes and methods too."""


def register_question(
    question: str, brief: pathlib.Path, kinds: tuple[str, ...], batch_size: int = DEFAULT_BATCH_SIZE
) -> collections.abc.Callable[[Lister], Lister]:
    """Register a lister with its brief and default batch size (extends repeatable-phase-b).

    Raises:
        PhaseBError: kinds is empty or names a kind twice.
    """
```

Signature updated 2026-11-21 to match the code: `kinds` (the keys of the
`findings` object in the question's result line) is a required parameter, and
the default batch size is `DEFAULT_BATCH_SIZE`.

`CorpusIndex` is built once per lister call from `corpus_definitions(...,
classes=True)`, the shared resolver's re-export alias table, settings
fields, command-line options and the tracked file list. `phaseb.py plan`
uses the registered batch size when `--batch-size` is not given.

## Error handling

- `PhaseBError` when a listed document, `pyproject.toml` or
  `.pre-commit-config.yaml` exists but cannot be read (`pyproject.toml` is
  parsed as TOML; `.pre-commit-config.yaml` is read as text and its hook ids
  found by regex, so it is never parsed), and when
  `git ls-files` fails (Doc1 and Doc2 need a work tree). A lister never
  skips an unreadable file: a vanished candidate is dropped from the ledger
  at the next merge, so a silent skip would delete verdicts.
- A Python file with a syntax error is skipped by the index, as
  `corpus_definitions` in `core.py` does (amendment 2026-11-21: hoisted from `_source_definitions`); the sweep's ruff hit reports it.
- A token resolving to nothing or to several definitions is not an error;
  it goes into its section's `(unresolved)` candidate.
- No sweep rule is added: `CHECKS` and `registry-order.txt` are unchanged,
  and `check_spec_api_signature_drift` calls `corpus_definitions` at its
  default, so its output does not change.

## Implementation

### Documents and names

Doc4 lists `agents/specs/**/*.md` whose `**Status:**` is `implemented`: a
proposed spec describes code not yet written. Doc5 lists `docs/**/*.md` and
the root `README.md` (decision 3 below), since the shared user-guides rule
lets a small project keep its guide there; Doc3 still compares `README.md`
with `AGENTS.md`. Doc1 and Doc2 list the root
`AGENTS.md`. Discovery reuses `spec_markdown_files`. A code-shaped name is
a backticked token with no space and no `<`, after dropping a trailing
`(...)`, that is path-shaped (holds `/`, or ends in `.py`, `.md`, `.toml`,
`.yaml`, `.yml`, `.json`, `.sh`, `.txt` or `.lock`, not starting `/` or
`~`), option-shaped (`--name`), or an identifier holding `_`, `.` or an
inner capital. A `def` or `class` line in a fence under an `API` heading
counts too (`DEF_LINE_RE`, `CLASS_LINE_RE`).

### Resolution

`read_name_targets` tries, in order: a tracked path relative to the repository
root, then to the document's directory; a dotted name through the alias
table, so a re-export resolves to its definition; a bare name in
`corpus_definitions(..., classes=True)`, unique or ambiguous as there;
`Class.method` and `Class.field`; a setting, a dotted key whose first
segment is a field of a class deriving by name from `BaseSettings` in the
package's class tree and each later segment a field of the previous field's
class; an option, a `--name` literal passed to a call named `add_argument`,
`option` or `Option`. Each is positive evidence; nothing resolves by
resemblance.

### Doc4 and Doc5 candidates

One candidate per (section, target) pair, id `<doc>::<heading
path>::<target id>`, span the section's, payload the target and each line
naming it. Hash: sha256, NUL-separated, over the whole section's text
(amendment 2026-11-22, review-5: not only the blocks naming the target, so an
edit to any statement a reviewer can report under the candidate re-plans it);
then the target's source - the whole source lines from the first decorator's line to the end line
for a def or class (amendment 2026-11-21: not `ast.get_source_segment`), the statement for a field or option call, a file's
bytes, a directory's sorted tracked entries. A section with unresolved or
ambiguous tokens also gets `<doc>::<heading path>::(unresolved)`: payload
each token with its line and any definitions found, hash the section's text
and the sorted tokens. Neither is a sweep finding now:
`spec-api-signature-drift` is silent on a name with no definition.

### Doc1 and Doc2 candidates

Doc1: one candidate per `AGENTS.md` section that names a path or holds a
fence, id `AGENTS.md::<heading path>`; payload its paths with their
resolution and the tracked directory tree to depth 3 from `git ls-files
-z`, so an untracked directory never changes it; hash the section's text,
then the tree. Doc2: one per section holding a backticked token; payload
each token matched against the declared distributions (PEP 503 names from
`project.dependencies`, `project.optional-dependencies`,
`dependency-groups` and `build-system.requires`, via `tomllib`), the `- id:`
lines of `.pre-commit-config.yaml` and the top-level modules the corpus
imports, plus the tokens matching none; hash the section's text, the
canonical JSON of those tables, then the hook file's bytes.

### Briefs

Each follows the A4 brief's form: the question verbatim from `SKILL.md`,
thresholds, input and output format, the env-variable security rule, and
`**Brief version:** 1` when written (the current versions are in
`grep -n 'Brief version' claude/skills/auditme/phaseb/briefs/*.md`). Findings: `{'drift': [...]}` for Doc4 and Doc5,
`{'stale': [...], 'missing': [...]}` for Doc1 and Doc2. Thresholds:

- Doc4, Doc5: drift is a statement the target's code contradicts - name,
  parameters, defaults, return, errors, a setting's type or default, an
  option's default, a file's existence or role. Not drift: an omission,
  unless the section presents a list as complete; a dated record or
  decision; a shorter type spelling; a parameter-list difference, which
  `spec-api-signature-drift` reports. For an unresolved token, drift is a
  name the code once had or plainly means; a stdlib or third-party name, a
  command, a value, an environment variable, a path outside the repository
  or one created at run time is not. Doc5 also: an example that would fail
  against the code is drift.
- Doc1: stale is a named path that is absent or does not hold what the
  section says; missing is a tracked directory absent from a section that
  presents itself as the layout (a tree fence, or a heading naming
  structure or layout).
- Doc2: stale is a named tool or library no longer declared, imported or
  run (D2's sense of run), or a version differing from its pin; missing is
  a declared dependency or hook absent from a section that presents itself
  as the tools or libraries list.

Settled after the pilot (operator, 2026-11-21; briefs Doc4, Doc5 and Doc1 at
version 3): a section or table that states its own date is a record of that
day and is not checked against today's code; an `(unresolved)` candidate's
section is judged on its other statements too; in Doc5 an example of
printed output that leaves out a line the code prints is drift, and a list of
a field's values written without "for example", "such as" or "including"
presents itself as complete; in Doc1 a named path the section calls ignored,
and that `.gitignore` ignores, is not stale.

Amendment 1.3 (operator, 2026-11-22, `agents/reviews/brief-thresholds-2026-11-22.md`;
briefs Doc4 and Doc5 at version 5): a spec's header date does not date its
sections; a statement worded as what the spec's own change did is a record,
one worded as the current state is judged; a `TODO.md` reference holds while
its heading is in `TODO.md` or `DONE.md`; a bullet that opens with a date is a
record of that day; a table naming the change it records is a record of that
change. In Doc5 a parenthetical list and a list of failure or exit conditions
present themselves as complete unless marked "for example", "such as",
"including" or "e.g.", and a claim broader than the code is drift.

Amendment 1.4 (operator, 2026-11-22, `agents/reviews/brief-thresholds-2-2026-11-22.md`;
briefs Doc4 and Doc5 at version 6): in Doc4 a date in a bullet's lead dates it;
an implementer's instruction or draft docstring for the spec's own change, a
Motivation, and a criterion tagged with an amendment are records; a reproduced
file block or "X has a, b and c" is complete unless marked; a numbered or
"then" list presents an order; an API block's `Raises:` is complete; a shared-span
drift goes under the candidate naming its target. In Doc5 a list of causes
under a symptom, a list inside a note, and a list after "any failure:" are
complete unless marked; inline JSON is judged on content, not layout; a
narrower claim is drift only when it states its scope as the whole or the
rest is undescribed; a row about a set-up project is judged against the setup
skill's template.

Amendment 1.5 (operator, 2026-11-22, `agents/reviews/brief-thresholds-3-2026-11-22.md`; briefs Doc1 4, Doc2 3,
Doc4 7, Doc5 7): every brief carries the default verdict of
[Repeatable Phase B](../repeatable-phase-b/spec.md) amendment 1.5. Doc4 adds rulings on
"(new)" Module location rows, `Raises:` conditions, usage blocks, definitions,
sections read as a whole, catch-all lists, Testing sections, drifts in split
sections, commands and ambiguous sentences; Doc5 on "Stops for" lists and
tools pinned in another repository.

Registered batch sizes, unmeasured: 24 for Doc4 and Doc5 (a section and its
code per candidate), 12 for Doc1 and Doc2 (the tree or the inventories).
The operator's first run on a real project is the pilot, run twice as A4's
was; a threshold it exposes lands as a brief version bump.

### Skill changes

- **Phase B**: the listed questions become A4, Doc1, Doc2, Doc4 and Doc5;
  every other question is sampled (decision 1): every audit runs it on the
  files changed since the previous review's `**Commit:**`, using the diff
  base `checks/changed.py` resolves, and every third audit (counted from the
  first audit after this change ships, and on any audit with no previous
  `**Commit:**`) runs it on the whole tree.
- **Doc5's predicate** in the Phase B checklist reads "Drift between `docs/`
  or `README.md` and `src/`" (decision 3), a widening shipped with this
  change; the first audit's README findings are catch-up.
- **Convergence**: a sampled question's new site goes under "Coverage
  (sampled)" and is never marked "missed by" a review; the rule applies in
  full to listed questions.
- **Review template**: a `**Commit:**` line (the audited `HEAD`) and, beside
  each sampled question, its mode (changed files since a named commit, or
  full).
- **Completion gate**: every listed question has a current verdict per
  candidate, and every sampled question ran in its cadence's mode.
- This change ships between audits, never mid-audit, as `SKILL.md`'s
  extension rule requires. The next audit judges every Doc candidate; its
  findings in unchanged code are the catch-up surface, and its Convergence
  note names the newly listed questions.

### Tests

In `claude/skills/auditme/tests/phaseb/`, on fixtures with `src/pkg/`,
`agents/specs/probe/spec.md`, `docs/guide.md` and an `AGENTS.md`: sections
and repeated headings; a root `README.md` listed for Doc5; each name shape
kept or dropped; each resolution
kind, a re-export and an ambiguous name; a proposed spec not listed; a
target edit changes its pair's hash and not an unrelated section's; an
unresolved candidate vanishes once the name is defined; Doc1's hash changes
for a new tracked directory, not an untracked one; Doc2 matches a declared
distribution and a hook id; an unreadable document raises `PhaseBError`;
each Doc brief has one version line; `check_spec_api_signature_drift`'s
existing tests pass unchanged.

## Settings

No new option. Command-line options of `phaseb.py` that the documentation
questions use:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--batch-size` | `int` | the question's registered size (24 for Doc4 and Doc5, 12 for Doc1 and Doc2) | Candidates per reviewer |
| `--depth` | `int` | `3` | How far callees are followed; read by the code-reading listers, not the documentation ones (amendment 2026-11-21: 1.0 said it stays A4's) |

The Doc1 tree depth (`TREE_DEPTH` in `docrefs.py`) and the path-shaped
extensions are constants there, changed only by a skill change with a brief
version bump.

## External dependencies

None beyond the standard library (`ast`, `hashlib`, `json`, `re`, `tomllib`, and `subprocess` for `git ls-files`) and `git`.

## Decisions (operator, 2026-11-20)

Answered on the review page of
`agents/reviews/order-raises-resolution-and-listed-phase-b-specs.md`; version
1.1 applies them:

1. **Cadence for sampled questions (D3 in that review):** both - changed
   files every audit, the whole tree every third audit, the span the
   2026-11-20 measurement covers.
2. **An unresolved name (D4):** an `(unresolved)` candidate per section,
   judged against the brief; no new sweep rule and no catch-up run.
3. **Doc5's documents (D5):** `docs/` and the root `README.md`, because the
   shared user-guides rule puts a small project's guide there.
