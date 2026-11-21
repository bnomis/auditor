# Raises section resolution

**Version:** 1.2
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
`class_methods: bool = False`, called by the rule at the default. Check:
`grep -n 'class_methods' claude/skills/auditme/checks/auditme/core.py` prints
the helper's signature, and the same grep on
`claude/skills/auditme/checks/auditme/rules/error_handling.py` prints
nothing. Otherwise the first task stops as `blocked`. Below, "the resolver"
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
  escapes, with chain `(f,)`;
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
