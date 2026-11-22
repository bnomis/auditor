# Listed Phase B architecture questions

**Version:** 1.6
**Status:** implemented
**Date:** 2026-11-20

Puts the auditme Phase B questions A11 (exhaustion via `assert_never`), A19
(logger level in broad excepts), A1 (external call envelope) and A17
(public-surface drift) on the listed path that
[Repeatable Phase B](../repeatable-phase-b/spec.md) defines. Each lister finds
its sites with the site-finding code the sweep's rules already use, drops any
site a sweep rule for the same question already reports, and hashes what the
verdict depends on. Each question gets a versioned brief that settles the
thresholds the question's text in
[`SKILL.md`](../../../claude/skills/auditme/SKILL.md) leaves open.

## Motivation

When this spec was written (2026-11-20), every question but A4 was still sampled, so it still turned up sites earlier
audits missed in code nobody changed. Measured on 2026-11-20 on one project's
last three full audits, counting the Phase B question each finding names: the
documentation questions 13, T1 and T2 7, A1, A11, A17 and A19 9, A13 and A15
5, A4 3, the rest 5. These four are the third group of the
[`TODO.md`](../../../TODO.md) item "Put the Phase B questions that find most
onto the listed path", whose fix direction is "the match statements, broad
handlers, external calls and public surfaces the AST already finds". The full
text of each question is in `SKILL.md`, Architecture (A).

## Prerequisites

Built after all three of these have merged to `main`; check each before
Task 1 with `grep -n '^\*\*Status:\*\*' <spec>`, which must print
`implemented`:

1. [Repeatable Phase B](../repeatable-phase-b/spec.md), task list
   [tasks-1](../../tasks/repeatable-phase-b/tasks-1.md); also
   `python3 claude/skills/auditme/checks/phaseb.py candidates . --question A4`
   exits 0. This spec uses its `Candidate`, `Verdict`, `register_question`,
   ledger, batches, `read_run_check` and command line unchanged.
2. [Listed Phase B documentation questions](../listed-phase-b-documentation-questions/spec.md).
3. [Listed Phase B test questions](../listed-phase-b-test-questions/spec.md).

The second and third edit the same lister registry and the same `SKILL.md`
passages. This spec follows the layout they leave (one module per question
group, if they split `candidates.py`) and the rule they settle for questions
that stay sampled; it settles no such rule itself.

## Module location

The checker is not under `src/`; this repository keeps it with its skill.

- `claude/skills/auditme/checks/auditme/phaseb/architecture.py` (new) - the
  A11, A19, A1 and A17 listers, registered with `register_question`, and
  `capture_hits` (in `phaseb/`, not `core.py`, since it raises `PhaseBError`
  and `phaseb` imports `core.py`; clarified in 1.2)
- `claude/skills/auditme/checks/auditme/core.py` - the corpus read index moved from `rules/state_and_effects.py` (see Hoists)
- `checks/auditme/rules/error_handling.py`, `rules/state_and_effects.py` -
  site finders made public (see Hoists)
- `claude/skills/auditme/phaseb/briefs/{A11,A19,A1,A17}.md` - briefs, version 1 when written; the A1 brief is at version 5, the A17 brief at version 3, and the A11 and A19 briefs at version 2 (amendment 1.6: every brief carries the default verdict of [Repeatable Phase B](../repeatable-phase-b/spec.md) amendment 1.5; A1 also counts a standalone script's own `*Error` class as a domain error)
- `claude/skills/auditme/tests/phaseb/test_architecture_candidates.py` - tests
- `claude/skills/auditme/SKILL.md` - names the new listed questions

## API

```python
def capture_hits(scope: pathlib.Path, checks: collections.abc.Sequence[Check]) -> set[tuple[str, str, int]]:
    """Run checks over every audit root and return each hit as (rule, path, line).

    Saves and restores `EMITTED` and captures stdout. Accepted hits are included.

    Raises:
        PhaseBError: a check raised; the message names the check.
    """


def if_chain(node: ast.If, subject_of: collections.abc.Callable[[ast.expr], str | None]) -> IfChain | None:
    """The chain's subject, arm tests and terminal else, or None if a test names another subject."""


def is_broad_handler(handler: ast.ExceptHandler) -> bool:
    """True for a bare except, or one naming Exception or BaseException, alone or in a tuple."""
```

`Check` is `Callable[[pathlib.Path, pathlib.Path], None]`, every rule's
signature. `IfChain` is a frozen dataclass (`subject: str`, `tests: list[ast.expr]`,
`orelse: list[ast.stmt] | None`). Candidate ids extend A4's
`<path>::<qualname>` with a site part, numbered by order of appearance within
the qualname so an edit elsewhere in the file does not change them:
`::if:<subject>#k` or `::match:<subject>#k` (A11), `::except#k` (A19),
`::call:<callee text>#k` (A1). An A17 id is the `__init__.py` path alone.
Module-level code has the qualname `<module>`.

## Error handling

- A file under an audit root that does not parse raises `PhaseBError` naming
  it; the rules skip it, but a skipped file would hide its candidates and let
  `merge` drop their ledger entries as vanished.
- `capture_hits` turns an exception from a check into `PhaseBError` naming the
  check, so no lister runs on a partial set of sweep hits.
- The rest is as the repeatable-phase-b spec says (exit 2; malformed reviewer
  output reported by `check` and retried).

## Implementation

### Hoists

A finder that reads the whole corpus, or serves more than one rule module,
moves to `core.py` beside `audit_roots`; any other becomes public in its rule
module. No rule's output and no existing test changes.

- `if_chain` is the chain walk inside `check_assert_never_missing`
  (`rules/state_and_effects.py`), with the subject test as a parameter; the
  rule passes `extract_string_eq_var`.
- `is_broad_handler` replaces the copied handler-type test in
  `check_silent_broad_except` and `check_broad_except_wrong_level`
  (`rules/error_handling.py`).
- `_FILESYSTEM_TOUCHING_CALLS`, `_translator_envelopes`, `_handler_translates`
  and `_callable_short_name` (`rules/error_handling.py`) drop the underscore.
- `_corpus_py_files`, `_dotted_read`, `_sys_modules_key` and
  `_reads_by_module_and_name` move from `rules/state_and_effects.py` to
  `core.py` without the underscore; the A20 rule imports them from there.
- Used as they are: `package_class_parents`, `class_lineage`,
  `is_dunder_all_assignment`, and `read_is_private` from `core.py`, which the
  test-questions spec adds (decision 1). `capture_hits`, in
  `phaseb/architecture.py`, generalises the capture in the runner in
  `tests/conftest.py`.

### Sites the sweep already reports

A site the sweep flags is not judged twice. Each lister runs its owning
rules through `capture_hits` and drops a candidate when a hit, accepted or
not, falls on an anchor line: an unaccepted hit is already in the review, an
accepted one is the operator's ruling. Once the hit is fixed the site lists
again and is judged as new.

| Question | Owning rules | Anchor lines |
|----------|--------------|--------------|
| A11 | `assert-never-missing` | the chain's first `if` |
| A19 | `silent-broad-except`, `broad-except-wrong-level`, `logger-exception-graceful-degradation` | the handler's lines, and the function's last `return` when the handler falls through |
| A1 | `filesystem-envelope-gap`, `filesystem-op-without-envelope`, `translator-envelope-gap` | the call's line, and the first handler of its enclosing `try` |
| A17 | `empty-init-while-siblings-export`; `migration-shim-consumer` per consumer | line 1 of the `__init__.py`; a consumer line a hit names is removed from `consumers` |

### A11 candidates

Every head of an `if` chain (an `If` that is not the sole `orelse` of
another) for which `if_chain` finds one subject - a name or dotted attribute
compared by `==`, `is` or `in` with string constants, attribute constants
(`Mode.FAST`) or tuples, lists or sets of them - with two or more arms, or one arm and an
`else`; every `if <name>:` with an `else` where `<name>` is assigned in the
same function from such a comparison (the two-way split); and every `match`
statement. Payload: `source` (the chain or `match`), `subject`, `annotation`
(the subject's annotation from a parameter, a local annotation or a class
field, else null) and `type_source` (the `Literal` alias or `Enum` class the
annotation names, if the package defines it). Hash: those texts.

### A19 candidates

Every handler `is_broad_handler` accepts, and every handler of any type whose
body calls `.exception(` on a logger name (`logger`, `log`, `_logger`,
`LOGGER`, `logging`, `loguru.logger`, or a `self.` attribute of one). Payload:
`handler`, `try` (the whole statement), `function` (name, signature, return
annotation, last statement), `log_calls` (each as `level: text`). Hash: the
enclosing function's source, or the `try` statement's at module level.

### A1 candidates

Every call in a non-test file under a package that defines a domain error (a
class whose name ends in `Error` and whose `class_lineage` reaches
`Exception`), to: a name in `FILESYSTEM_TOUCHING_CALLS`; `open`;
`subprocess.*`; `torch.load` and `torch.save`; `pandas` `read_*`; a `.to_*`
method that writes (`to_csv`, `to_json`, `to_parquet`, `to_pickle`,
`to_excel`, `to_feather`, `to_hdf`, `to_sql`); any call rooted at an imported
`requests`, `httpx`, `urllib.request`, `mlflow`, `boto3`, `botocore`,
`sqlite3`, `sqlalchemy` or `huggingface_hub`; and `execute`, `executemany`,
`commit`, `get_object`, `put_object`, `upload_file` or `download_file` in a
module that imports one of those clients. A test file is `test_*.py`,
`*_test.py`, `conftest.py` or anything under a `tests` directory. Payload:
`call`, `try` (the innermost enclosing statement, or null), `envelopes` (each
translating decorator or `with` contextmanager on the function, from
`translator_envelopes`, with what it catches), `domain_errors` (sorted
names), and for a call in a private or nested helper `callers` (each
resolved call site of the helper with its enclosing envelope, or null) and
`privacy`, why the function counts as a helper: `nested`, or the rule of the
test-questions spec's `privacy` that marks it private (`all`, `script` or
`underscore`; amendment 1.3, 2026-11-21, A1 brief version 2). Amendment 1.4
(operator, 2026-11-22, `agents/reviews/brief-thresholds-2026-11-22.md`; A1
brief version 3): a `subprocess` call with `check` false or unset and no
`timeout` can raise only `OSError`, so a handler for it alone covers the
call; a handler that returns the error is translation when the function's
return annotation or docstring says it returns failures.
Hash: the enclosing function's source, each envelope's source, the domain
error names, and each listed caller's source.

### A17 candidates

Every `__init__.py` under an audit root that has an `__all__`
(`is_dunder_all_assignment`) or is empty of exports. Payload: `all` (the
names), `consumers` (for each name, every read from outside the package's
directory and outside the test tree found by `reads_by_module_and_name`,
plus `[project.scripts]` and `[project.entry-points]` targets in
`pyproject.toml`, as `path: line text`),
and for an empty one `reach_ins` (each outside read of a submodule). Hash:
the `__init__.py` source and the sorted, de-duplicated consumer and reach-in
entries without line numbers, so an edit that moves a reading line does not
re-plan it.

### Briefs

Each brief holds its question verbatim from `SKILL.md`, the input format,
the output (one JSON line per candidate: `id`, `findings`, `reason`), the
rules every brief carries (report an unsettled threshold, never decide it;
never list environment variables or print an env file) and
`**Brief version:** 1` when written (the current versions are in
`grep -n 'Brief version' claude/skills/auditme/phaseb/briefs/*.md`; amendment 1.5
(operator, 2026-11-22, `agents/reviews/brief-thresholds-2-2026-11-22.md`) added to A1 that a handler for the
only `SubprocessError` subclass a call can raise covers it, that a registered
check emitting a hit translates, and that a call to the package's own
translating function is covered; and to A17 that a read past a non-empty
`__all__` is a bypass reported on that package). Thresholds:

- **A11.** A hit when the subject is a `Literal` or `Enum` and the chain ends
  in `raise`, has no `else` and falls through, or ends in an `else` that
  silently handles the remaining values; the fix is an explicit arm per value
  and `assert_never`. A `match` whose `case _:` raises is a hit; one on class
  or structural patterns is not A11's. A subject with no `Literal` or `Enum`
  type is not a hit, and the reason says what its type is.
- **A19.** A handler that raises passes the first half if it logs only at
  `exception` or not at all. A handler that does not raise and carries on
  (returns any value, `continue`, `pass`, or falls through to a default) is
  graceful degradation. A broad graceful-degradation handler is a hit at any
  level, with the fix "remove or narrow" from `SKILL.md`'s conflicts with no
  winner. A function returning `int` is a command exit path, not degradation.
- **A1.** The envelope translates when a handler covers the call's failure
  class (`OSError` for the filesystem and `open`, `OSError` and
  `subprocess.SubprocessError` for `subprocess`, the library's error or a
  broad handler otherwise) and raises one of `domain_errors`. Logging,
  returning a default or a bare re-raise is not translation. A lexical `try`
  in the function or a listed envelope counts. A call in a helper that
  `read_is_private` marks private, or in a nested function, is also covered when
  every resolved caller calls the helper inside a translating envelope
  (decision 2); the payload's `callers` lists those call sites, and the hash
  adds each caller's source, so a new caller re-plans the helper.
- **A17.** A name with no consumer is a hit unless a dynamic use (a literal
  `getattr`, `importlib.import_module`, an entry point) reads it. A consumer
  reading a name from a submodule when the `__init__.py` exports it is a
  bypass; for an empty `__init__.py`, a reach-in to a submodule `read_is_private`
  marks private is a bypass, and any other submodule is the owning module.
  A read from the test tree is not a consumer (decision 3): a name only
  tests read is a finding.

### Skill changes

`SKILL.md` names A11, A19, A1 and A17 as listed, and section 4 says a site a
sweep rule for the same question reports is not judged in Phase B. This is a
skill change, made between audits, never during one.

### Tests

On neutral fixtures (`pkg`, `probe`, `ProbeError`, `Mode`): each lister lists
its positive shapes and skips its carve-outs; a site on an owning rule's hit,
accepted or not, is dropped; ids survive an unrelated edit above the site; an
edit inside the hashed text changes the hash and one outside does not; the
A17 hash ignores a moved consumer line and leaves out a test-tree reader; an
A1 call in a private helper whose every caller translates is covered, and a
new caller without an envelope re-plans it; an unparseable file raises
`PhaseBError`; each brief has one version line and its `SKILL.md` text.

## Settings

None new. Command-line options of `phaseb.py`; the lister of each question takes the
ones that apply to it.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--question` | `str` | none, required | `A11`, `A19`, `A1` or `A17` here, as well as the questions of the other specs |
| `--batch-size` | `int` | the question's registered size (48 for A4) | Candidates per reviewer |
| `--depth` | `int` | `3` | How far callees are followed; `list_candidates` hands it to any lister that takes a depth (A4, T1, T2) |

## External dependencies

Standard library only (`ast`, `hashlib`, `tomllib`, `contextlib`, `io`).

## Decisions (operator, 2026-11-20)

Answered on the review page of
`agents/reviews/order-raises-resolution-and-listed-phase-b-specs.md`; version
1.1 applies them:

1. **What is private (D6 in that review):** `read_is_private` from the
   test-questions spec: named in no `__all__` of its package where the
   package has one, a leading underscore only where it has none. Used for
   A1 helpers and A17 reach-ins.
2. **A caller's envelope and an A1 call in a private helper (D9):** covers
   it when every resolved caller calls the helper inside an envelope,
   consistent with `filesystem-op-without-envelope`.
3. **A test-tree read and A17 (D10):** not a consumer; a name only tests
   read is a finding.

Settled in the same review without a question: a library's top-level
`__all__` is judged like any other, and the operator dismisses a finding
once; the ledger keeps the dismissal while the code is unchanged.
