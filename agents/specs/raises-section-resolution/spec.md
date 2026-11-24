# Raises section resolution

**Version:** 1.3
**Status:** implemented
**Date:** 2026-11-20

Widens the auditme rule `raises-section-drift` so it sees the domain errors
that reach a caller through a same-package function with no `Raises:`
section, and through a call written `<ClassName>.<method>(...)`. Both are
resolution gaps, not judgement calls: once closed, Phase B question A4 stops
finding these omissions by hand.

## Motivation

The `TODO.md` item "`raises-section-drift` misses errors reached through a
section-less wrapper or a `Class.method()` call" (found 2026-11-20) tracks
the open request in `claude/skills/auditme/requests.md`,
"`raises-section-drift` should follow pass-through callees and
`Class.method()` calls", raised 2026-11-20 by an audit whose Phase B A4 found
by hand `Raises:` omissions this rule exists to catch. Each traced to one of
two gaps in `check_raises_section_drift` (last changed 2026-11-01):

1. **Section-less callee.** A callee is followed one level, through its
   declared section. A thin wrapper whose docstring defers to another
   function in prose has none, so every domain error behind it is invisible.
2. **`Class.method()` calls.** `Probe.load(path)` resolves to nothing, though
   `self.load(path)` would.

While the request is open the next audit cannot start (`SKILL.md`: the sweep
checks that `requests.md`'s `## Open` section is empty). This is an extension
in the sense of `SKILL.md` "Extending the script": omission hits grow. Every
narrowing made by [Auditme false positives](../auditme-false-positives/spec.md)
(unset optional argument guards, called nested functions, handler scope) is
kept and applies at every hop this spec adds.

## Prerequisite

Task 1 of `agents/tasks/repeatable-phase-b/tasks-1.md`
([Repeatable Phase B](../repeatable-phase-b/spec.md), version 1.1) has
merged: the rule's call resolution (inner `resolve`, the re-export alias
table, the import bindings) is a shared helper in
`claude/skills/auditme/checks/auditme/core.py` taking
`class_methods: bool = False`, called by the rule (amendment 2026-11-21: with `class_methods=True`, as the A4 lister does). Check:
`grep -n 'class_methods' claude/skills/auditme/checks/auditme/core.py` prints
the helper's signature (at the time of writing the same grep on
`claude/skills/auditme/checks/auditme/rules/error_handling.py` printed
nothing; it now prints the rule's calls with `class_methods=True`). Otherwise the first task stops as `blocked`. Below, "the resolver"
means that helper, under whatever name Task 1 gave it.

## Module location

The checker is not under `src/`; this repository keeps it with its skill.

- `claude/skills/auditme/checks/auditme/rules/error_handling.py` - the rule
- `claude/skills/auditme/tests/test_error_handling.py` - tests, under the
  existing `# --- raises-section-drift` headings
- `claude/skills/auditme/SKILL.md` - A4 in the Phase B checklist
- `docs/guide/checker.md` - the `raises-section-drift` row

`CHECKS` in `claude/skills/auditme/checks/auditme/registry.py` does not
change: it already holds `check_raises_section_drift` and its position stays.
`claude/skills/auditme/tests/registry-order.txt` does not list the check and
needs no edit.

## API

The rule's signature is unchanged; a module constant and an inner function
are added.

```python
SECTIONLESS_DEPTH: typing.Final = 3
"""How many calls deep the rule follows from a subject; the A4 lister's `--depth` default."""


def check_raises_section_drift(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a `Raises:` section that disagrees with the domain errors reaching the caller (A4)."""


# inner to check_raises_section_drift, beside `caught` and `is_domain`:
def escapes(qualname: str, hop: int, chain: tuple[str, ...]) -> dict[str, set[tuple[str, ...]]]:
    """The domain errors leaving the section-less function qualname, each with
    the chains (qualnames, outermost first, qualname included) it leaves
    through. hop is qualname's call distance from the subject (1 for a direct
    callee); chain holds the functions already on the path, subject first.
    """
```

## Implementation

**Resolution.** The rule calls the resolver with `class_methods=True`, so
`<ClassName>.<method>(...)` resolves for a class the package defines, in the
same module or imported by name or dotted path. For such a call, `bound` (the
argument `unset_optional_guard` uses to skip the first parameter) is true
when the method is decorated `@classmethod`, false for a `@staticmethod` or
an undecorated method called through its class. A `self.` call keeps `bound`
true. `cls.<method>()` and inherited methods stay unresolved; Phase B keeps
them.

**Following a section-less callee.** For each call site of the subject (from
`nested_call_sites`, as today) whose callee resolves:

- a callee with a `Raises:` section (`'Raises:'` in its docstring, the test
  the rule applies to subjects) is handled as today: its declared domain
  errors reach the subject unless a handler around the call catches them or
  `unset_optional_guard` skips them. It is not followed: its section is its
  contract, judged when the rule reaches it as a subject;
- a callee with no section contributes `escapes(callee, 1, (subject,))`,
  minus what the handlers around the call catch.

`escapes(f, hop, chain)` walks `nested_call_sites(f)`:

- a `raise` of a domain error that `f`'s handlers at that site do not catch
  escapes, with chain `(f, '')`, the trailing `''` marking the raiser (amendment 2026-11-21: 1.0 gave `(f,)`);
- only while `hop < SECTIONLESS_DEPTH`, each call resolving to a function
  not in `chain` and not `f` adds, minus what `f`'s handlers at that site
  catch: for a callee with a section, its declared domain errors not skipped
  by `unset_optional_guard(callee, name, parents, call, bound)`, chain
  `(f, callee)`; for a section-less callee `g`,
  `escapes(g, hop + 1, (*chain, f))` with each chain prefixed by `f`;
- anything else (an unresolved call, a call back onto the chain, any call
  at `hop == SECTIONLESS_DEPTH`) adds nothing.

So the rule reaches exactly the functions the A4 lister lists at its default
depth: `subject -> wrapper -> wrapper -> perform` is followed to `perform`,
one wrapper more is not. Cycles end because nothing on the chain is entered
again. No memoisation (the chain changes what a call may enter; the depth
bound keeps the walk small). Every set is iterated sorted, so output is
deterministic.

**What is reported.** One omission hit per name in `reached` that the
section does not cover by itself or an ancestor, as today. The variant names
the shortest chain, ties broken by sorting the chain tuples:

- `f: Raises: omits ProbeError, raised here` and
  `f: Raises: omits ProbeError, declared by probe.inner.perform` (unchanged);
- `f: Raises: omits ProbeError, declared by probe.inner.perform via probe.wrap.wrapper`,
  or `..., raised by probe.wrap.wrapper` when the wrapper raises it; a longer
  chain lists its wrappers in call order, comma-separated after `via`.

`related` lists the path of every function, outside the subject's file, on
any chain by which a reported name reaches the subject - not only the
shortest chain the message names - sorted and de-duplicated. This keeps
today's behaviour, where `related` names the file of every direct callee
that reaches the error, and adds the wrappers' files (clarified in 1.2). The extra-declaration branch
("declares X, which never reaches the caller") is unchanged in logic; as
`reached` grows it can only lose hits. Accept markers on the `def` line work
as today.

**Documentation.** The rule's docstring: the "Callees are followed one
level" sentence states the new resolution, and an `Extension (<ship date>):`
paragraph names both gaps, `SECTIONLESS_DEPTH` and the request. `SKILL.md`
A4: "it follows each same-package callee one level through its declared
`Raises:`" becomes "it follows each same-package callee, including
`<ClassName>.<method>(...)` for a class the package defines, through its
declared `Raises:`, and follows a callee with no section into its own raises
and callees, up to three calls deep"; the list of what Phase B reviews by
hand gains `cls.<method>()` calls and inherited methods. No "Documented
refinements" entry: this is an extension. `docs/guide/checker.md`: the row
adds that errors are followed through wrappers with no section and through
`Class.method()` calls.

## Error handling

The rule raises nothing, as today; a module that does not parse is skipped.
An unresolved call contributes nothing, which is why an extra still needs a
catching handler. Recursion is bounded by `SECTIONLESS_DEPTH` and the
on-chain test, so no package shape can raise `RecursionError`. A missing
prerequisite stops the first task as `blocked`. An existing test in
`claude/skills/auditme/tests/test_error_handling.py` whose expected hits
change stops the task for the operator; it is never edited to pass.

## Testing

In `claude/skills/auditme/tests/test_error_handling.py`, on the existing
`probe` fixtures (`ProbeError` and subclasses in `errors.py`), each written
first and seen to fail:

- **Wrapper (request fixture):** `perform()` declares and raises
  `ProbeError`; section-less `wrapper()` calls it; a caller whose section
  omits `ProbeError` gets one hit, variant `... declared by probe.inner.perform via probe.wrap.wrapper`,
  `related` naming both files; the caller declaring `ProbeError` or its
  base gets none.
- **Handlers at every hop:** no hit when the caller catches `ProbeError`
  around `wrapper()`, or `wrapper()` catches it around `perform()`; a hit
  when `wrapper()` catches and re-raises it.
- **Raise in the wrapper:** gives `raised by probe.wrap.wrapper`.
- **Depth:** `perform()` behind two section-less wrappers is a hit; behind
  three, none.
- **Cycle:** section-less `a()` and `b()` call each other, `b()` calls
  `perform()`; the caller of `a()` gets one hit and the check ends.
- **Kept narrowing:** `wrapper()` calling `load('x')`, whose only raise is
  under `if strict:`, gives none; `load('x', strict=True)` gives a hit.
- **Extras only shrink:** a subject declaring `ProbeError`, catching it from
  another call and reaching it through `wrapper()`, gets no "never reaches"
  hit.
- **`Probe.load()` (request fixture):** a classmethod declaring
  `ProbeError`; a caller without handler or entry gets
  `declared by probe.conf.Probe.load`, with `Probe` in the same module and
  imported by name; a catching handler gives none; a classmethod raising only
  under an unset optional argument, called `Probe.load(path)`, gives none
  (`bound` true); a `@staticmethod` with that guard, called with an argument
  in the guarded position, gives a hit (`bound` false).
- **Accept marker** on the caller's `def` line marks the new hit accepted.

Every existing test passes unchanged:
`uv run --no-project --with pytest pytest claude/skills/auditme/tests -q -p no:cacheprovider`.

## Settings

None. `SECTIONLESS_DEPTH` is a module constant: the sweep takes no per-rule
settings, and a depth varying between projects would give the same code
different hits.

## External dependencies

Standard library only (`ast`).

## After this ships (operator, outside the task list)

Every project using the shared hooks sees new `raises-section-drift` hits at
its next hook update. In each such repository the operator runs the sweep,
lands a fix or accept marker for each new hit (`SKILL.md` "Extending the
script" step 4) and notes the change in that project's
`agents/audit-reviews/summary.md`; then deletes the request entry from
`claude/skills/auditme/requests.md` here. None of this is a task: a task
list runs in this repository only. The `TODO.md` item stays open until that
entry is deleted, then moves to `DONE.md`.

## Decisions (operator, 2026-11-20)

Answered on the review page of
`agents/reviews/order-raises-resolution-and-listed-phase-b-specs.md`
(version 1.1 records them; the design above already followed both):

1. **Follow depth (D1 in that review):** fixed at three calls,
   `SECTIONLESS_DEPTH = 3`, the A4 lister's `--depth` default, so the rule
   and the Phase B callee list see the same functions.
2. **A section-less callee's own raises (D2):** counted. A `raise` in a
   wrapper with no section reaches its caller's verdict, as `escapes`
   describes; the second hit, on the caller, for one root cause is accepted.

## Amendment 1.3: first-party libraries outside the project (proposed 2026-11-24)

**Motivation.** The `TODO.md` item "`raises-section-drift` does not follow
`Raises:` sections of first-party libraries outside the sweep" (finding
dated 2026-11-23, split on 2026-11-24 from an item whose other two findings
shipped in `8fd601d`): a callee in a sibling first-party package installed
alongside the project, not under `src/`, whose `Raises:` names an exception
is ignored, so a function that lets it escape is not reported. A false
negative. Declared roots cannot reach such a package: a root must resolve
inside the project (`docs/reference/cli.md`, "Declared roots").

**Decision (operator, 2026-11-24).** The project names its first-party
libraries' source directories in a new `[tool.auditme]` key; nothing is
inferred (not from `[tool.uv.sources]`, not from the environment). An error
class such a library defines counts as a domain error, as the swept
package's own do.

**Setting.**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `[tool.auditme] first-party` | `list[str]` | absent (no library is followed) | Package directories, relative to the project, that `raises-section-drift` reads for `Raises:` sections and error classes but never sweeps. Each is a directory named as its import name (`../lib/src/lib` for `import lib`); it may lie outside the project. |

**API**, in `claude/skills/auditme/checks/auditme/core.py`, beside
`declared_roots`:

```python
def first_party_dirs(scope: pathlib.Path) -> list[pathlib.Path]:
    """The package directories `[tool.auditme] first-party` names, in order, resolved.

    Empty when `pyproject.toml`, the table or the key is absent.

    Raises:
        RootsError: the key is not a list of non-empty strings, or an entry
            is missing, not a directory, holds no `.py` file, or lies inside
            a root the sweep audits.
    """
```

with `cached_first_party_dirs(scope)` reading it once per run, as
`cached_declared_roots` does. `declared_roots`' unknown-key check admits
`first-party`.

**Implementation.**

- `audit.py` reads `first_party_dirs` where it reads the roots (`changed.py`
  runs `audit.py`, so it inherits this), before any check runs, so an invalid entry stops the sweep with
  the roots' error and exit status, naming the entry: `first-party path
  ../lib/src/lib not found`. A missing directory is an error, never a skip:
  a sweep that silently drops a library reports fewer hits than the same
  code gives with it. `--package` and `--extra-root` do not change it.
- `check_raises_section_drift` adds every module under each first-party
  directory to its module table, named by `module_dotted(path, dir)` (so
  `lib.errors` under `../lib/src/lib`). Their functions join `known`,
  `declared_by` and `node_of`; their classes join `parents`, so
  `package_classes`, and with it `is_domain`, include them. Subjects stay
  the swept package's functions only: no hit is ever emitted on a
  first-party file.
- A call into a first-party module resolves as a same-package call does
  (`resolve_call` over the joined table, `class_methods=True`), and is then
  followed exactly as today: through its declared `Raises:` section, or,
  section-less, into its raises and callees up to `SECTIONLESS_DEPTH`.
- `related` names a first-party file by its path relative to the project
  (`os.path.relpath`, so `../lib/src/lib/errors.py`); `core.relpath` is not
  used for it, as it fails outside the project.
- The A4 lister (`claude/skills/auditme/checks/auditme/phaseb/`) is
  unchanged: a call into a first-party library stays unresolved there, and
  Phase B keeps judging such calls by hand.

**Error handling.** `RootsError` as the API says; a first-party module that
does not parse is skipped, as a swept one is. An existing test whose
expected hits change stops the task for the operator.

**Testing**, in `claude/skills/auditme/tests/test_error_handling.py` and
the settings tests beside the roots tests, each written first and seen to
fail; the first-party library lives in a sibling directory of the project
fixture:

- a subject calling `lib.load()`, whose section declares `LibError`
  (defined in `lib/errors.py`), with a section omitting it: one hit,
  `declared by lib.load`, `related` naming `../lib/src/lib/...`; declaring
  it gives none; a catching handler gives none;
- a section-less wrapper in the library calling a declaring function: the
  hit names the chain, as for an in-package wrapper;
- without the key, the same subject gives no hit (today's behaviour);
- no hit is emitted on a file under a first-party directory;
- a missing entry, a file entry, an entry holding no `.py` file, a
  non-list value and an entry inside a swept root each stop the sweep with
  `RootsError` naming the entry; `first-party` beside `roots` and
  `never-accepted` is accepted.

**Documentation.** `docs/reference/cli.md`: the setting, beside "Declared
roots", with the CI consequence (a listed directory must exist wherever the
sweep runs). `docs/guide/checker.md`: the rule's row adds that callees in
listed first-party libraries are followed. `SKILL.md` A4: the rule also
follows callees into the libraries `first-party` lists. The rule's
docstring gains an `Extension (<ship date>):` paragraph.

