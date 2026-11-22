# Repeatable Phase B

**Version:** 1.6
**Status:** implemented
**Date:** 2026-11-20
**Review page:** https://claude.ai/artifact/2L2gApX1M8DNzL5ivQF3D7

Makes an auditme Phase B question give the same answer twice on unchanged
code. A program lists every site the question applies to; reviewer agents
judge every listed site in fixed batches against a versioned brief; the
orchestrator checks each batch is complete and retries one that is not; and
each verdict is stored in a ledger keyed by a hash of what it judged, so an
unchanged site keeps its verdict instead of being judged again. Version 1
covers question A4 (docstring `Raises` accuracy). Further questions join one
at a time; a question that cannot be listed stays sampled and the review says
so.

## Motivation

`SKILL.md` requires two audits of unchanged code to produce the same findings.
The mechanical sweep meets that; Phase B does not. On one project, three full
audits in a row ran from an unchanged checker with a clean sweep, and the
last two marked 21 and 23 sites "missed by" the review before - sites in code
nobody had changed. The cause is structural: a reviewer applying one question
to a whole tree cannot read the whole tree, so it greps, opens some candidates
and reports those. Which candidates it opens varies from run to run, and each
brief steers it away from the last review's sites. The per-question fan-out
keeps the judgement steady; it does not fix what gets looked at.

Pilot, 2026-11-20, on that project, question A4 only:

- a script listed 575 functions with a `Raises:` section, split into 12
  batches of 48;
- two independent runs of 12 reviewers each, same brief, same batches;
- every batch of the first run returned a verdict for every candidate; one
  batch of the second run was stopped by an API safeguard error and returned
  nothing;
- on the 527 candidates both runs judged, 523 verdicts were identical
  (99.2%); per (candidate, error name) claim, agreement was 0.95; every site
  the first run flagged, the second flagged too;
- the four disagreements had two causes: a threshold the brief left open (an
  error that cannot fire for a constant the candidate passes), and one run
  stopping its trace before a callee that raised.

Decisions (operator, 2026-11-20):

- **D1.** An error a candidate can reach only through a constant it passes
  itself, where that constant rules the error out, is not owed in its
  `Raises:` section.
- **D2.** An abstract or protocol method - body `...`, `pass`, a docstring
  alone, or `raise NotImplementedError` - is not an A4 candidate. Its section
  is a contract; each implementation is judged on its own code.
- **D3.** The ledger lives in the audited project at
  `agents/audit-reviews/ledger/<question>.jsonl` and is committed.

Review (operator, 2026-11-20): every section of version 1.0 approved on
the review page, S1 to S9, with no comments.

Amendment 1.1 (operator, 2026-11-20): `Class.method()` resolution is turned
on for the A4 lister only. The `raises-section-drift` rule keeps its current
resolution, so this spec changes no rule's output and leaves no catch-up
surface in any project; giving the rule the same resolution is the separate
open request in `claude/skills/auditme/requests.md`.

Amendment 1.2 (operator, 2026-11-21): one result shape for every listed
question. Found on 2026-11-21 in the Doc batch-size pilot (two runs of 13
batches on one project): `phaseb.py check` exits 1 on every Doc1, Doc2,
Doc4 and Doc5 run, reporting every line `unparseable ... extra must be a
list of strings` and every batch for retry, though every reviewer returned a
well-formed line in its brief's shape. `parse_result` and
`read_run_verdicts` in `phaseb/batches.py` read A4's `missing` and `extra`
keys from every line, while the briefs that shipped after version 1 ask for
`drift` (Doc4, Doc5), `stale` and `missing` (Doc1, Doc2), or a `findings`
object (T1, T2, A1, A11, A17, A19). So only A4 could reach a ledger. The
operator chose one wire shape for every question - `id`, a `findings` object
mapping each of the question's kinds to a list, and `reason` - over reading
two shapes; no project had a ledger yet, so no stored verdict is re-judged.

## Module location

The checker is not under `src/`; this repository keeps it with its skill.

- `claude/skills/auditme/checks/auditme/phaseb/__init__.py` - the package
- `claude/skills/auditme/checks/auditme/phaseb/candidates.py` - the
  per-question candidate listers and their registry
- `claude/skills/auditme/checks/auditme/phaseb/ledger.py` - reading, merging
  and reporting verdicts
- `claude/skills/auditme/checks/auditme/phaseb/batches.py` - planning batches
  and checking a run's output
- `claude/skills/auditme/checks/phaseb.py` - the command-line entry point,
  beside `audit.py`
- `claude/skills/auditme/phaseb/briefs/A4.md` - the versioned A4 brief
- `claude/skills/auditme/tests/phaseb/` - tests
- `claude/skills/auditme/SKILL.md` - Phase B and the completion gate

The call resolution `check_raises_section_drift` uses (its inner `resolve`
and the alias table) moves to a shared helper in `checks/auditme/core.py`, so
the rule and the A4 lister resolve calls the same way. The helper takes a
`class_methods: bool = False` flag: the lister passes `True` to resolve
`<ClassName>.<method>(...)`; the rule kept the default when this was written, so its output did
not change (amendment 2026-11-21: the rule now passes `class_methods=True`).

## API

```python
@dataclasses.dataclass(frozen=True)
class Candidate:
    """One site a question applies to."""

    question: str  # 'A4'
    id: str  # '<repo-relative path>::<qualname>'
    path: str
    start: int
    end: int
    payload: dict[str, typing.Any]  # question-specific; A4: raises, callees, unresolved
    hash: str  # sha256 hex, see Content hash


@dataclasses.dataclass(frozen=True)
class Verdict:
    """One reviewer's ruling on one candidate."""

    question: str
    id: str
    hash: str  # the candidate hash it was judged against
    brief_version: int
    findings: dict[str, list[str]]  # one list per registered kind; A4: {'missing': [...], 'extra': [...]}
    reason: str
    judged: str  # ISO date
    dismissed: str | None = None  # 'YYYY-MM-DD: <reason>' once the operator dismisses it

    @property
    def flagged(self) -> bool:
        """True when any findings list is non-empty and the verdict is not dismissed."""


def register_question(question: str, brief: pathlib.Path, kinds: tuple[str, ...], batch_size: int = DEFAULT_BATCH_SIZE) -> typing.Callable[[Lister], Lister]:
    """Register a candidate lister for a Phase B question, with its brief, the
    finding kinds its reviewers report (1.2) and its default batch size.

    Raises:
        PhaseBError: kinds is empty or repeats a kind.
    """


def question_kinds(question: str) -> tuple[str, ...]:
    """The finding kinds registered for question (1.2).

    Raises:
        PhaseBError: question has no registered lister.
    """


def list_candidates(question: str, root: pathlib.Path, depth: int | None = None) -> list[Candidate]:
    """List every candidate for question under root, sorted by id.

    Raises:
        PhaseBError: question has no registered lister.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """


def read_ledger(path: pathlib.Path) -> dict[str, Verdict]:
    """Read a question's ledger, keyed by candidate id; empty if the file is absent.

    Raises:
        PhaseBError: the file exists but cannot be read, or a line is not a valid verdict.
    """


def plan_batches(candidates: list[Candidate], ledger: dict[str, Verdict], brief_version: int, size: int, rejudge: bool = False) -> list[list[Candidate]]:
    """Return the candidates needing a verdict, in batches of size, in id order.

    A candidate needs one when the ledger has no verdict for its id, or the
    verdict's hash or brief_version differs from the current one, or rejudge
    is set.

    Raises:
        PhaseBError: size is not a positive number.
    """


def read_run_check(run_dir: pathlib.Path) -> RunCheck:
    """Check every planned batch has exactly one valid verdict per candidate.

    Returns the problems per batch (no output, unparseable line, missing,
    duplicate or unexpected id) and the batches to retry.

    Raises:
        PhaseBError: the plan cannot be read or names an unregistered
            question (amendment 2026-11-21: 1.2 said it raised nothing).
    """


def merge_verdicts(ledger_path: pathlib.Path, candidates: list[Candidate], verdicts: list[Verdict]) -> MergeResult:
    """Write the new verdicts into the ledger and drop entries whose id is no longer a candidate.

    A new verdict for a dismissed candidate keeps the dismissal while the
    candidate's content hash is unchanged, or while its findings are
    unchanged (amendment 1.6). Writes atomically (temporary file, then rename).

    Raises:
        PhaseBError: the ledger cannot be read or written.
    """
```

Signatures updated 2026-11-21 to match the code: `list_candidates` takes an
optional `depth` (how far the lister follows callees), and `read_run_check` names
its parameter `run_dir`.

Command line, run from the project root:

```text
phaseb.py candidates <root> --question A4 [--depth N]   # JSONL to stdout
phaseb.py plan <root> --question A4 --out <dir> [--batch-size 48] [--depth N] [--rejudge]
phaseb.py check <dir>                                  # exit 1 on any problem; lists batches to retry
phaseb.py merge <root> --question A4 <dir> [--depth N]   # into the project's ledger
phaseb.py report <root> --question A4 [--depth N]    # open findings, new and carried
phaseb.py dismiss <root> --question A4 <id> --reason <text>
```

`plan` writes `batch-NN.jsonl` files and a `plan.json` holding the question,
brief path, brief version, the callee `depth` it listed at and each batch's
ids, which `check` and `merge` read. `merge` refuses a `--depth` that differs
from the plan's, naming both; a plan without a `depth` is read as the default,
3.

Amendment 2026-11-22 (review-5, decision D3): a candidate the ledger already
holds a verdict for, and which `plan` plans again (its hash changed, its
brief version is older, or `--rejudge` is set), has an `earlier` object in its
batch line: the ledger verdict's `findings`, `reason`, `brief_version` and
`judged`. A candidate new to the ledger has none. `check` and `merge` ignore
`earlier`. Every brief's Input section says a reviewer whose verdict differs
from `earlier` gives what changed its judgement in `reason`; that bumped every
brief's version by one.

## Error handling

- `PhaseBError` (defined in `phaseb/errors.py`, re-exported by
  `phaseb/__init__.py`) for an unknown question, a ledger
  or plan that exists but cannot be read or parsed, or a write that fails. A
  ledger that cannot be read is never treated as empty: an empty ledger
  re-judges everything, and a later merge would overwrite the real one.
- A missing ledger file is a clean absence: every candidate is planned.
- A reviewer's malformed output is not an exception. `read_run_check` reports it,
  and the batch is retried.
- A batch with problems after two retries, each by a fresh reviewer, is
  recorded in the review as not judged, naming its ids. The question then
  fails the completion gate (see Skill changes).
- The command line prints `PhaseBError` messages to stderr and exits 2; a
  `check` with problems exits 1.

## Implementation

### A4 candidates

Every function or method under the audited roots (the same roots `audit.py`
audits) whose docstring has a Google-style `Raises:` section, except those D2
excludes. The payload holds:

- `raises`: the section's text;
- `callees`: the package functions the candidate's calls resolve to, followed
  transitively to `--depth` (default 3), each as `{id, path, start, end}`,
  using the shared resolver with `class_methods=True`, which also resolves
  `<ClassName>.<method>(...)` for a class the package defines;
- `unresolved`: each call the resolver could not follow, as `path:line` and
  its source text, so the reviewer knows where to trace by hand.

### Content hash

sha256 over the candidate's source, then each listed callee's source in id
order, separated by NUL bytes. A change to the candidate or to any listed
callee changes the hash and re-plans the candidate. A change behind an
unresolved call does not, which is why `unresolved` is listed and why
`--rejudge` exists. A brief version bump re-plans every candidate of that
question, since the brief's version is compared beside the hash.

### Briefs

`phaseb/briefs/<question>.md` holds the question verbatim from `SKILL.md`,
every threshold settled for it, the output format, and a
`**Brief version:** N` line. A change to any threshold increments N. The A4
brief, version 1, settles:

- a domain error is a class the audited package defines, never a builtin or
  a third-party class;
- each class counts separately: declaring a base does not cover a subclass
  that reaches the caller;
- an error reachable only through a callable passed in as an argument is not
  owed;
- D1: an error ruled out by a constant the candidate passes is not owed, and
  the reason names the constant;
- the reviewer reads every listed callee and every unresolved call.

A threshold a reviewer raises in its reply that the brief does not settle is
reported to the operator, never settled by the orchestrator mid-run, and the
answer lands as a brief version bump.

Amendment 1.5 (operator, 2026-11-22, `agents/reviews/brief-thresholds-3-2026-11-22.md`, decision G1; every
brief up one version): a case the brief does not settle is judged not a
finding, and the reviewer names it in its reply. Every batch gives such a case
the same verdict, so settling a reported case is needed only when it should
count, not for the verdicts to agree. The A4 brief is at version 7.

Amendment 1.3 (operator, 2026-11-22, `agents/reviews/brief-thresholds-2026-11-22.md`;
A4 brief version 5): a call dispatched through a registry lookup owes the
domain errors of the functions the registry holds when the registry is a
module-level literal mapping, or one a registering decorator fills, of the
package's own functions; a mapping built at run time or passed in counts as a
callable passed in.

Amendment 1.4 (operator, 2026-11-22, `agents/reviews/brief-thresholds-2-2026-11-22.md`;
A4 brief version 6): a raise in a decorator's own body, which runs when the
function is defined, is not owed by the decorated function; one in the wrapper
it returns is.

### The result line (1.2)

Every brief's Output section asks for one JSON line per candidate with
exactly the keys `id` (a string), `findings` (an object mapping each of the
question's registered kinds to a list of strings, empty when nothing is
wrong) and `reason` (a string). `parse_result` checks a line against
`question_kinds(plan.question)`: a key outside the three, a missing or extra
kind, or a value that is not a list of strings makes the line unparseable,
which `read_run_check` reports against its batch, as today. `read_run_verdicts`
stores `findings` as the line gives it, each list sorted. The kinds each
question registers:

Brief versions below are those 1.2 set; amendment 2026-11-21: the briefs have
since moved on (run `grep -n 'Brief version' claude/skills/auditme/phaseb/briefs/*.md`).

| Question | Kinds | Brief version |
|---|---|---|
| A4 | `missing`, `extra` | 3 (output moves under `findings`) |
| Doc4, Doc5 | `drift` | 2 (the same) |
| Doc1, Doc2 | `stale`, `missing` | 2 (the same) |
| T1, T2 | `missing` | unchanged |
| A1 | `call` | unchanged |
| A11 | `unexhausted` | unchanged |
| A17 | `surface` | unchanged |
| A19 | `handler` | unchanged |

Only the Output sections of the A4 and Doc briefs change, but a version bump
is how a brief change re-plans its candidates, so each still moves up one.
`Verdict`, the ledger format and `flagged` are unchanged: the ledger already
holds `findings` as a map of lists.

### A review's findings

For a listed question, the review's findings are the flagged verdicts in the
ledger for current candidates: those judged in this run as new, those reused
as carried. A carried finding is not a regression and is not "missed by" any
review. When the operator dismisses one on the review page, the orchestrator
runs `dismiss`, and the verdict stays dismissed while its hash is unchanged.
Amendment 1.6 (2026-11-22, from review-4's decision D2 in
`agents/audit-reviews/review-4.md`): `merge_verdicts` now does what this says.
Before, it kept a dismissal only when the new findings text matched the old
one, so a re-judge under a bumped brief, which writes the findings afresh,
dropped it. It keeps a dismissal while the hash is unchanged, and still keeps
one whose findings are unchanged after the code changed.

### Skill changes

- **Phase B** gains a listed-question path: `plan`, one reviewer per batch
  with the question's brief, `check`, up to two retries, `merge`, `report`.
  Questions with a registered lister take it; the rest keep the per-question
  fan-out and are marked `(sampled)` in the review.
- **Convergence** applies in full to listed questions. A new site in a
  sampled question is coverage, not drift, and the review says so.
- **Completion gate** adds: every listed question has a current verdict for
  every candidate, or the review names each not-judged id.
- **Extending** a question to the listed path is a skill change between
  audits, with its lister, brief and tests, never mid-audit.

### Tests

In `claude/skills/auditme/tests/phaseb/`, on neutral fixtures (`pkg`,
`ProbeError`): the lister finds a `Raises:` function, skips a protocol stub
(D2), resolves a `Class.method()` callee, and lists an unresolvable call;
changing a callee changes the hash; `plan_batches` skips a current verdict
and re-plans a changed hash and a bumped brief version; `read_run_check` reports
each problem kind; `merge_verdicts` drops vanished ids, keeps an unchanged
dismissal, keeps one whose hash is unchanged under a bumped brief and reworded
findings (1.6), and drops one whose hash and findings both changed; a malformed ledger raises `PhaseBError`.
For 1.2: for every registered question, a line in its brief's shape passes
`read_run_check` and `read_run_verdicts` stores its kinds; a line with an
unregistered kind, a missing kind, or A4's old top-level `missing` and
`extra` is reported unparseable; every brief's Output section names exactly
its question's registered kinds; and `register_question` rejects empty or
repeated kinds.

## Settings

Command-line options only; the skill has no configuration file.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--question` | `str` | none, required | The Phase B question, e.g. `A4` |
| `--batch-size` | `int` | the question's registered size | Candidates per reviewer; 48 for A4 (the pilot's size), smaller for the documentation and AGENTS.md questions |
| `--depth` | `int` | `3` | How far callees are followed for the callee list and the hash |
| `--rejudge` | flag | off | Plan every candidate, ignoring the ledger |

## External dependencies

Standard library only (`ast`, `hashlib`, `json`, `dataclasses`). Tests run
with `uv run --no-project --with pytest pytest ~/.claude/skills/auditme/tests`.
