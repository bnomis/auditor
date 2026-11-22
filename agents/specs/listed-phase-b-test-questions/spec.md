# Listed Phase B test questions

**Version:** 1.7
**Status:** implemented
**Date:** 2026-11-20
**Review page:** https://claude.ai/artifact/A2jYW6bvHGhR3JxqhppKuW (amendment 1.5)

Puts the auditme Phase B test questions T1 and T2 on the listed path of
[Repeatable Phase B](../repeatable-phase-b/spec.md). A lister finds each
branchy function and each function a property test would suit from the AST,
finds the tests that reach it, and hashes those test files with it, so an
unchanged function with unchanged tests keeps its verdict and a new test
re-plans it. Each question gets a versioned brief that settles its thresholds.

## Motivation

When this spec was written (2026-11-20), only A4 was listed; every other question was sampled and kept finding sites
earlier audits missed in unchanged code. Measured on 2026-11-20 on one
project's last three full audits, by the question each finding names: the
documentation questions 13, T1 and T2 7, A1, A11, A17 and A19 9, A13 and A15
5, A4 3, the rest 5. T1 and T2 are the second group of the `TODO.md` item
"Put the Phase B questions that find most onto the listed path", whose fix
direction is: branchy functions and the functions a property test would
suit, from the AST, with their test files in the hash. The questions,
verbatim from `claude/skills/auditme/SKILL.md`:

- **T1.** Every function with `if`/`try`/`except`/state transitions has at
  least one test case.
- **T2.** Domains that are well-defined (data shapes, config combinations)
  have hypothesis tests.

## Prerequisites

Both merged to `main` before Task 1; the task list checks each:

1. [Repeatable Phase B](../repeatable-phase-b/spec.md): `**Status:**` reads
   `implemented`, and `python3 claude/skills/auditme/checks/phaseb.py
   candidates . --question A4` exits 0. Its `Candidate`, `Verdict`,
   `register_question`, ledger, batches, command line and shared call
   resolver (`core.py`, `class_methods=True`) are used unchanged.
2. [The documentation-questions spec](../listed-phase-b-documentation-questions/spec.md),
   the first group: `**Status:**` reads `implemented`. It edits the same
   registry and `SKILL.md` passages, so this spec follows the module layout
   it leaves and the rule it settles for questions that stay sampled.

## Module location

The checker is not under `src/`; this repository keeps it with its skill.

- `claude/skills/auditme/checks/auditme/phaseb/testmap.py` (new): the test
  tree index
- `claude/skills/auditme/checks/auditme/phaseb/candidates.py`: the T1 and T2
  listers beside A4's (or the group module the documentation-questions spec
  introduces)
- `claude/skills/auditme/phaseb/briefs/T1.md` and `T2.md`: the briefs
- `claude/skills/auditme/tests/phaseb/test_testmap.py`,
  `test_t1_candidates.py`, `test_t2_candidates.py`: tests
- `claude/skills/auditme/SKILL.md`: T1 and T2 named as listed

`claude/skills/auditme/checks/auditme/core.py` gains `read_is_private` (see
API), which [the architecture-questions spec](../listed-phase-b-architecture-questions/spec.md) reuses.

Reused, not copied: `audit_roots` and `module_dotted` (`core.py`), the
shared resolver, `walk_within_scope` (`rules/error_handling.py`) and
`SIDE_EFFECT_CALL_NAMES` (`rules/state_and_effects.py`). A helper `phaseb/`
uses from a rule module moves to `core.py`, the rule importing it from there.

## API

```python
@dataclasses.dataclass(frozen=True)
class TestRef:
    """One test function that reaches a package function."""

    id: str  # 'src/tests/test_mod.py::test_load'
    path: str
    start: int
    end: int
    route: typing.Literal['direct', 'caller']
    via: str | None  # 'caller' only: id of the package function the test calls
    property: bool  # decorated with hypothesis `given`


def load_test_map(root: pathlib.Path, depth: int) -> dict[str, tuple[TestRef, ...]]:
    """Map each package function id to the tests that reach it, sorted by id.

    Raises:
        PhaseBError: a test file or audited source file does not parse.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """


def privacy(qualname: str, module: str, root: pathlib.Path) -> tuple[bool, str]:
    """Whether the function or class qualname in module is private, and the rule that decided.

    The rules, first that applies (decision 1, amended in 1.4):

    - `all`: module's own `__all__` and the `__all__` of every package
      `__init__.py` above it. Public when any of them names qualname's first
      segment; private when at least one has an `__all__` and none names it.
    - `script`: a standalone script with no `__all__`. Public only when
      qualname's first segment is a name its `__main__` guard calls.
    - `underscore`: where nothing is declared, private when a segment of
      qualname or module starts with an underscore (clarified in 1.2).
    """


def read_is_private(qualname: str, module: str, root: pathlib.Path) -> bool:
    """`privacy(...)[0]`."""


def t1_reasons(node: ast.FunctionDef | ast.AsyncFunctionDef, cls: ast.ClassDef | None) -> list[str]:
    """Why node is a T1 candidate: any of 'if', 'try', 'match', 'state'; empty if not."""


def is_t2_candidate(node: ast.FunctionDef, package_types: collections.abc.Mapping[str, ast.ClassDef]) -> bool:
    """True when node is pure over well-defined types and has logic a property can test."""
```

Listers register as `T1` and `T2` with `register_question` and take the A4
lister's arguments, `--depth` included. Payloads: T1 has `reasons`, `tests`
(each `TestRef` as a dict), `callers` (package functions reaching it within
`--depth`, as `{id, path, start, end}`), `test_files`, `private` and
`privacy` (whether the function is private and the rule that says so); T2 has `params`
(`[{name, annotation}]`), `returns`, `types` (package classes the
annotations name, as `{id, path, start, end}`), `pairs`, `tests` and
`test_files`.

## Error handling

- `PhaseBError`, naming the file, when a test file or audited source file
  does not parse. Skipping a test file would mark what it tests as untested;
  skipping a source file would drop its ledger entries at the next merge.
- No test file under any test root (amendment 1.5): not an error. T1
  candidates are listed with empty `tests`; the review says none was found.
- A test call the resolver cannot follow is left out of the map, never
  raised or guessed; the reviewer reads `test_files`.
- All else (unknown question, ledger, reviewer output, retries, exit codes)
  is Repeatable Phase B's handling.

## Implementation

### Scope

Candidates come from `audit_roots` minus the test tree: a path with a
`tests` part, `test_*.py`, `*_test.py` and `conftest.py` are never
candidates. The test tree is every `test_*.py` and `*_test.py` under
`src/tests/` (the layout of `claude/rules/python/testing.md`) and `tests/`.

Amendment 1.5 (2026-11-22, from a request in
`claude/skills/auditme/requests.md` raised on 2026-11-21 by this repository's
first full audit): a project whose tests sit outside `src/tests/` and
`tests/`, under a root declared in `[tool.auditme]`, got an empty test map,
so every T1 and T2 candidate had empty `tests` and `test_files`; in that audit
every candidate of the first T1 batch had both empty, though the tests under
the declared root import those modules. The test roots are now every root
`audit_roots` returns, in its order, then `src/tests/` and `tests/` where they
exist; a project that declares nothing keeps the default trees, which are the
only roots outside its packages and `bin/`. Under a test root, a test file is
a `test_*.py` or `*_test.py` that `is_test_relpath` marks a test, and a
`conftest.py` is read as before. A file met under two roots is read once,
under the first, so its module name follows that root's `modules` mode
(`module_dotted`). `test_tree_roots(root)` returns this list, so the
`conftest.py` chain stops at the nearest test root and the mirrored test file
is looked for under each. In a project that declares nothing, the change reads
test files inside its packages and `bin/` (a `src/<pkg>/tests/` directory)
that it did not read before; the sweep already treats them as tests, so they
were neither candidates nor tests. The briefs do not change; the hash of each
candidate whose `test_files` grows changes, so the next audit re-judges it.
Both parts (the change, and reading test files inside a non-declaring
project's packages and `bin/`) were approved by the operator on 2026-11-22 on
the review page named in the header.

### T1 candidates

A function or method whose own body (by `walk_within_scope`: a nested def
does not count for its parent) holds at least one of: `if`, an `ast.If`
(an `elif` too; a conditional expression, comprehension filter or `assert`
is not); `try`, an `ast.Try` or `ast.TryStar` with an `except` handler
(`try`/`finally` alone does not branch); `match`, an `ast.Match`; `state`, an
assignment to `self.<attr>` where another method of the class tests
`self.<attr>` in an `if`, a `match` subject or a comparison. That test is the
positive evidence the attribute is state; an assignment alone is not. The
minimum is one, as T1's text names any such function. `@typing.overload`
stubs and defs under `if TYPE_CHECKING:` are excluded.

### T2 candidates

A positive rule. All of:

1. a module-level function or `staticmethod`, not `async`, not a generator,
   with at least one parameter;
2. every parameter and the return annotated, the return not `None`, each
   annotation built only from `int`, `float`, `bool`, `str`, `bytes`, `None`,
   `Decimal`, `Fraction`, `date`, `datetime`, `timedelta`, `Literal[...]`, a
   package-defined `Enum`, frozen dataclass, `NamedTuple` or `TypedDict`
   whose fields are themselves such types, and `list`, `tuple`, `dict`,
   `set`, `frozenset`, `Sequence`, `Mapping`, `Iterable`, `|` or `Optional`
   over them;
3. no call in its own body whose short name is in `SIDE_EFFECT_CALL_NAMES`
   or is `open`, `print`, `input`, `now`, `time`, a `random` or `subprocess`
   function; no `global` or `nonlocal`; no assignment to an attribute or
   subscript of a parameter;
4. a branch, loop or comprehension in its own body.

Rule 2 is the evidence of a well-defined domain: hypothesis can build every
type it allows. Rule 4 keeps out accessors with nothing to state. `pairs`
lists another candidate whose name is the inverse (`parse_x`/`format_x`,
`encode`/`decode`, `to_x`/`from_x`, `dumps`/`loads`), as a round-trip hint.

### Finding the tests

Each test file is parsed once. A test function (`test_*` at module level or
in a `Test*` class) reaches a package function **directly** when a call in
its body, or in a fixture it requests from the same file or a `conftest.py`
above it, resolves to it; **through a caller** when it directly reaches a
function whose resolved callees reach the target within `--depth`, `via`
naming that function. Resolution starts from the test file's imports, so a
bare name match without an import of the module or name is never evidence.

`test_files` is, sorted: the mirrored test file (`src/<project>/<pkg>/<f>.py`
-> `src/tests/<pkg>/test_<f>.py`) if it exists, every test file importing the
candidate's module, and every test file importing a listed caller's module.
Amendment 1.3 (decided by the operator on 2026-11-21, D7 of
`agents/reviews/checker-requests-2026-11-21.md`): also every test file that
imports a package re-export of the candidate by its own name
(`from pkg import load`) or imports the module that re-exports it
(`import pkg`). A file importing some other name from that package is not
added. The T1 brief (version 2) counts a call through such a re-export as a
call of the candidate, so a reviewer must see those files.

Amendment 1.4 (2026-11-21, from a request in
`claude/skills/auditme/requests.md` raised by one project's full audit): a
project that bans leading underscores and has no `__all__` in its `bin/`
scripts had no private names there, so every helper of a script was a public
function its tests reached only through `main()`. `privacy` now reads a
standalone script's surface: a file outside any package (no `__init__.py`
beside it) with a top-level `if __name__ == '__main__':` is a script, and only
the bare names that guard calls are public. The guard is the positive
evidence; a loose module without one, such as a helper module the scripts
import, stays under the underscore rule. A script's own `__all__` still wins.
A module in a root declared `top-level` is now found at `<root>/<module>.py`,
so its `__all__` and guard are read too. The T1 brief (version 3) lets a test
that loads a script by path and runs an entry point that reaches a `script`
candidate count as its caller test.

### Content hash

sha256 over, NUL-separated: the candidate's source; for T2 each `types`
class's source in id order; then each `test_files` file's full text in path
order. A new or edited test in any of those files re-plans the candidate. A
test in a file importing neither the module nor a caller's does not; the
brief says so, and `--rejudge` covers it.

### Briefs

Each has the question verbatim, its thresholds, the input format, the output
(one JSON line per candidate with `id`, `findings`, `reason`, none left out)
and `**Brief version:** N` (1 when written; T1 is at 5 and T2 at 2, amendment 1.7: the default verdict of `agents/specs/repeatable-phase-b/spec.md` amendment 1.5, and in T2 a call through a name assigned from the candidate is a direct call), plus the rule that an unsettled threshold is
reported, not decided, and the security rule every subagent brief carries.

- `T1.md`: findings `{"missing": ["test case"]}` or `{"missing": []}`.
  Covered when a listed `direct` test calls it, or, for a function
  `read_is_private` marks private, a `caller` test reaches it (decisions 1 and
  2). The payload carries `private: bool` and `privacy`, the rule that
  decided it; the reason names the rule whenever it decides the verdict
  (brief version 3, amendment 1.4). An
  unconditionally skipped or `xfail` test does not count. The reason names
  the covering test's id. Amendment 1.6 (operator, 2026-11-22,
  `agents/reviews/brief-thresholds-2026-11-22.md`; brief version 4): a test
  that runs a script's path as a subprocess is a caller test like a `runpy`
  load; a fixture the test requests, names in `usefixtures` or gets as
  `autouse` is part of the test; passing the candidate as an argument covers
  it when the receiving package function calls that argument.
- `T2.md`: findings `{"missing": ["property test"]}` or `{"missing": []}`.
  Covered when a test with `property: true` calls it directly. Flagged only
  when the reason states a property the domain supports (a round trip with
  a `pairs` entry, idempotence, an output invariant, a simpler oracle, a
  bound); with none statable, not flagged, and the reason says why. Whether
  the project declares hypothesis does not change the verdict.

### Skill changes

`SKILL.md` section 4 names T1 and T2 as listed, so they lose `(sampled)`. A
dated entry under "Refining a predicate" records T2's candidate rule as the
predicate's reading of "well-defined domains". As `SKILL.md` requires, this
is a skill change between audits; the first audit after it judges every T1
and T2 candidate as new, and its findings are coverage, not drift.

### Tests

On a fixture project with `src/pkg/` and `src/tests/`: each T1 reason fires,
and a conditional expression, `try`/`finally` alone, an unread attribute
assignment and a nested def's `if` do not; a T2 function over `int` and a
frozen `Probe` dataclass is listed, and ones taking `pathlib.Path`, calling
`write_text`, mutating a parameter or without a branch or loop are not; a
test file is never a candidate; direct, fixture-routed and caller tests are
found with their route; `read_is_private` is false for a name in its package's
`__all__`, true for one left out of it, and falls back to a leading
underscore only in a package with no `__all__`; a test file under a
declared root outside `src/tests/` and `tests/` is read, reaches what it
calls and names its module by that root's mode, a file under two roots is
read once, and a project that declares nothing reads the default trees; a same-named function in a test file that does not
import the module adds no ref; a test added to the mirrored file, or a field
added to `Probe`, changes the hash; an unparseable test file raises
`PhaseBError`; both briefs have a version line and their question verbatim.

## Settings

No new options: Repeatable Phase B's `--question` (`str`, required, no
default; `T1` or `T2` here),
`--batch-size` (`int`, `48`), `--depth` (`int`, `3`; here also how far up
callers are followed) and `--rejudge` (flag, off). The type set of T2 rule 2
and the call names of rule 3 are lister constants, changed only with a brief
version bump.

## External dependencies

Standard library only (`ast`, `hashlib`, `dataclasses`). Hypothesis is
recognised by name (`given` imported from `hypothesis`), never imported.
Tests run with `uv run --no-project --with pytest pytest ~/.claude/skills/auditme/tests`.

## Decisions (operator, 2026-11-20)

Answered on the review page of
`agents/reviews/order-raises-resolution-and-listed-phase-b-specs.md`; version
1.1 applies them:

1. **What is private (D6 in that review):** named in no `__all__` of its
   package where the package has one; a leading underscore counts only for
   a package without `__all__`. The shared coding standard forbids leading
   underscores and asks for `__all__`, so an underscore test alone would
   find nothing private in a project that follows it. `read_is_private` in
   `core.py` holds the rule, for this spec and the [architecture-questions](../listed-phase-b-architecture-questions/spec.md)
   spec.
2. **A caller's test and a public T1 candidate (D7):** a public candidate
   needs a `direct` test; a private one may be covered through a caller,
   matching the testing rule that every public function has tests.
3. **`str` and `bytes` in T2's types (D8):** included, as rule 2 lists them.

Settled in the same review without a question: whole test files go into the
hash (formerly open decision 2), so no new test in a related file is missed.
