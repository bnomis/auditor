# Sweep coverage gaps

**Version:** 1.0
**Status:** implemented
**Date:** 2026-11-24

Closes seven gaps in the auditme sweep that one project's audits found by
hand: five rules that miss a shape their own question describes, one rule
that fires where there is nothing to report, and one question (A23) with
no mechanical check at all. Each change below makes a rule read what its
Phase B question in `claude/skills/auditme/SKILL.md` already asks for.

## Motivation

The `TODO.md` item "The sweep misses seven patterns one project's audits
found by hand" (found 2026-11-24) tracks the open entry in
`claude/skills/auditme/requests.md`, "Close the sweep gaps one project's
audits carried as script candidates" (filed 2026-11-24). That project's
audits carried the patterns as script-coverage candidates across two
cycles; each was checked on 2026-11-24 against the checker at `3e23236`,
and again on 2026-11-24 against `8fd601d`: all seven are still open.

While the entry is open the next audit cannot start (`SKILL.md`, step 3:
the sweep checks that `requests.md`'s `## Open` section is empty). Five
changes are extensions in the sense of `SKILL.md` "Extending the script"
(hits grow); the asymmetric-translation change is a refinement (hits
shrink).

## Module location

The checker is not under `src/`; this repository keeps it with its skill.
Paths below are under `claude/skills/auditme/`.

- `checks/auditme/rules/style_and_naming.py` - `bare-parametric-annotation`
- `checks/auditme/rules/error_handling.py` - `layer-has-domain-error-raises-stdlib`, `asymmetric-exception-translation`
- `checks/auditme/rules/state_and_effects.py` - `assert-never-missing`, `pure-name-has-side-effect`, `build-name-has-side-effect`, and the new `discarded-tuple-return`
- `checks/auditme/registry.py` - `CHECKS` and `RULE_IDS` gain the new rule
- `checks/auditme/phaseb/architecture.py` and `phaseb/briefs/A17.md` - the A17 lister and brief
- `SKILL.md` (A3, A9, A17, A23 and "Documented refinements"), `docs/guide/checker.md` (the rule table)
- tests beside each: `tests/test_style_and_naming.py`, `tests/test_error_handling.py`, `tests/test_state_and_effects.py`, `tests/test_registry.py`, `tests/phaseb/test_architecture_candidates.py`, `tests/phaseb/test_briefs.py`

## API

One new check; every other change is inside an existing function.

```python
def check_discarded_tuple_return(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a call whose tuple result is thrown away (A23, mechanical part).

    Signal: an expression statement (`ast.Expr`) whose value is a call, or
    an `await` of one, that `auditme.core.resolve_call` resolves to a
    function of the swept package annotated `-> tuple[A, B, ...]` with two
    or more element types (`typing.Tuple[...]` too). `tuple[X, ...]` is a
    sequence, not a multi-return, and does not count. `_ = f()` and
    `a, _ = f()` name the discard and are not hits.
    """
```

Rule id `discarded-tuple-return`, variant
`<callee qualname> returns tuple[...]; the result is discarded`, with
`related` naming the callee's file when it differs (so the rule joins
`CROSS_FILE_RULES` in `tests/test_registry.py`).

## Implementation

**1. `bare-parametric-annotation` reads inside a subscript.** The visitor in
`bare_parametric_annotation_in_file` stops at any `Subscript`. It descends
into the slice instead (each element of a `Tuple` slice, or the slice
itself), so `list[dict]`, `dict[str, dict]` and `list[list]` fire. It does
not descend into `Literal[...]`, and reads only the first argument of
`Annotated[...]` (by tail name). A string constant (a forward reference)
is not read. One hit per line, as now.

**2. `discarded-tuple-return` (new).** As the API docstring says. Calls
resolve exactly as `raises-section-drift` resolves them (`resolve_call`
with `class_methods=True`, the import bindings and re-export aliases), so
only package functions count; an unresolved call is not a hit. The
annotation is the positive evidence; a function returning a tuple without
saying so is left to Phase B. `SKILL.md` A23 gains a sentence naming the
rule as its mechanical part; the dataclass and partial-use cases stay
Phase B.

**3. `layer-has-domain-error-raises-stdlib` set.** `STDLIB_EXCS` becomes
`{'FileNotFoundError', 'KeyError', 'RuntimeError', 'TypeError', 'ValueError'}`.
`TypeError` is already in A3's text and the rule's docstring; A3's text
gains `FileNotFoundError`. Measured on this repository on 2026-11-24: no
raise of either name in a package with an `errors.py`.

**4. `assert-never-missing` reads more chains.** Today each test must be
`<bare name> == '<str>'` and a chain needs three. After the change:

- the subject may be a dotted name (`self.kind`), compared by its source text;
- an arm may be `subject in ('a', 'b')` (a tuple, list or set of string
  constants) as well as `==` in either order;
- a two-arm chain counts when the subject is a parameter, or a name with an
  `AnnAssign`, annotated `Literal[...]` with three or more string members.
  The annotation is the positive evidence that a third value exists; an
  unannotated two-arm chain stays exempt as bi-valued;
- a `match` on such a subject with three or more `case` patterns of string
  constants (or `|` of them) is a hit unless its last case is `case _:`
  calling `assert_never`.

A chain or `match` already ending in `assert_never` is never a hit. The A11
lister drops any site the rule hits (`hit_on_anchor`), so the sites that
move become sweep hits and leave A11's batches; nothing else in A11 changes.

**5. The pure-name rules.** `build-name-has-side-effect` reads the prefix
`make_` as well as `build_` and `compute_`; A9's prefix list in `SKILL.md`
gains `make_`. `pure-name-has-side-effect` reads, beside its filesystem
writes, what A9 already calls I/O: opening or reading a file (`open`,
`.read_text`, `.read_bytes`), testing for existence (`.exists`, `.is_file`,
`.is_dir`, `os.path.exists`, `os.path.isfile`, `os.path.isdir`), running a
subprocess (the `subprocess` calls the build rule reads, and `os.system`),
and reading the clock (`datetime.now`, `datetime.utcnow`, `time.time`).
These go in a new constant beside the rule; `SIDE_EFFECT_CALL_NAMES` is not
changed, because the build rule and the T2 lister share it. A9's carve-out
for registered checks applies: a `check_` function whose name is a member
of a module-level tuple, list, set or dict-value literal in the corpus, or
which is decorated by a function the package defines, is not read as
pure-named. Path normalisation (`.resolve`, `.absolute`, `.expanduser`,
`os.path.realpath`) is not read. The rule's stale docstring (it names
prefixes and calls the rule does not read) is corrected. Measured on this
repository on 2026-11-24: three `check_` functions run a subprocess, all
registered in `checks/auditme/registry.py`, so no new hit.

**6. `asymmetric-exception-translation` needs something to translate.** A
callee is a hit only when its own body (nested defs skipped) makes a call
that can raise an error the callers translate: a name in
`FILESYSTEM_TOUCHING_CALLS`, a subprocess call, or a call rooted at a
module imported from outside the swept package. A body of pure string or
arithmetic work is not a hit. A callee that calls a same-module function
`translator_envelopes` lists translates through it and is not a hit. The
shared fixture `ASYMMETRIC_HELPER` in `tests/test_error_handling.py` does
pure string work (`len(name)`); it changes to read a file, so the tests
built on it keep their meaning. This is the one existing test change the
spec allows.

**7. The A17 lister reads submodules.** `list_a17_candidates` skips every
file but `__init__.py`. It also lists a submodule with a module-level
`__all__`: id and `path` the submodule's path, `all` its names, and
`consumers` each read of a name from any other file outside the test tree
(a submodule's `__all__` declares its surface to its own package too).
Existing candidates keep their ids and hashes. `A17.md` gains the
submodule case in its question and input text, and its brief version goes
up by one.

## Error handling

The rules raise nothing, as today; a module that does not parse is
skipped, and an unresolved call contributes nothing. An existing test
whose expected hits change, other than those built on `ASYMMETRIC_HELPER`,
stops the task for the operator; it is never edited to pass.

## Testing

Each case written first and seen to fail, on the files' existing fixtures:

- **1:** `list[dict]`, `dict[str, dict]` and `list[list]` are hits;
  `Literal['dict']`, `'list[dict]'` (a string) and `dict[str, int]` are not;
  `Annotated[list, meta]` is a hit.
- **2:** `f(x)` as a statement, `f` annotated `-> tuple[int, str]` in
  another module, is one hit with `related`; `await g()` likewise;
  `_ = f(x)`, `a, _ = f(x)`, `h()` with `-> tuple[int, ...]` and a call to
  an unresolved function are not.
- **3:** `raise TypeError(...)` and `raise FileNotFoundError(...)` in a
  package with `errors.py` are hits; inside an `except` block they are not.
- **4:** a three-arm chain on `self.kind` is a hit; `kind in ('a', 'b')`
  counts as an arm; a two-arm chain on a parameter annotated
  `Literal['a', 'b', 'c']` is a hit, and on `kind: str` is not
  (`test_a_two_arm_chain_is_legitimately_bi_valued` unchanged); a
  three-case `match` is a hit, and with `case _: assert_never(kind)` is not;
  the A11 lister no longer lists a chain the rule now hits.
- **5:** `make_x` reading the clock is a hit; `get_x` calling `.read_text()`,
  `subprocess.run` or `.exists()` is a hit; `get_x` calling `.resolve()` is
  not; a `check_x` named in a module-level tuple, or decorated by a package
  function, is not; an unregistered `check_x` reading a file is.
- **6:** a helper every caller wraps that reads a file is a hit (the existing
  tests, on the changed fixture); one doing only string work is not; one
  calling a same-module translator is not.
- **7:** a submodule with `__all__ = ['f']` read by another module is listed
  with that consumer; read only by a test file, listed with none; an
  `__init__.py` candidate's id and hash are unchanged; the brief tests in
  `tests/phaseb/test_briefs.py` pass on the new version.

`tests/test_registry.py` keeps `RULE_IDS` equal to the emitted ids and the
guide's rule table. Every task ends with the whole-tree sweep of this
repository (`pre-commit run auditme-all --hook-stage pre-push --all-files`)
clean: a new hit here is fixed or accepted with a reason in the same task.

## Settings

None. The sweep takes no per-rule settings.

## External dependencies

Standard library only (`ast`).

## After this ships (operator, outside the task list)

In the project that raised the request, and every other project using the
shared hooks at its next hook update, the operator runs the sweep, lands a
fix or accept marker for each new hit and notes the change in that
project's `agents/audit-reviews/summary.md` (`SKILL.md` "Extending the
script" step 4); then deletes the entry from
`claude/skills/auditme/requests.md` here. The `TODO.md` item moves to
`DONE.md` when the entry is deleted.
