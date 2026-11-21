# Review: specs for the raises resolution and listed Phase B run order

**Date:** 2026-11-20
**Review page:** https://claude.ai/artifact/LTLBJ7GShsiXTb3JMuP9vX

## What is being reviewed and how

`/todo-run-order 1,2` turns the first two `TODO.md` items into a run order
for `/rro`: item 1, "`raises-section-drift` misses errors reached through a
section-less wrapper or a `Class.method()` call", and item 2, "Put the Phase
B questions that find most onto the listed path". Four new specs were
written for them. Approve or flag each spec, approve or flag one small edit
to an existing task list, and pick an option for each decision below. No
task list is written until every item and decision has an answer: the
answers change the specs the lists are built from.

The order this review leads to, one task list per row:

| Row | Task list | Waits for | Stops for the operator |
|---|---|---|---|
| 1 | `repeatable-phase-b/tasks-1.md` (exists) | - | - |
| 2 | `raises-section-resolution/tasks-1.md` | 1 | - |
| 3 | `listed-phase-b-documentation-questions/tasks-1.md` | 1 | - |
| 4 | `listed-phase-b-test-questions/tasks-1.md` | 3 | - |
| 5 | `listed-phase-b-architecture-questions/tasks-1.md` | 4 | - |

Rows 3 to 5 edit the same lister registry and `SKILL.md` passages, so each
waits for the one before.

## Automatic checks

| Check | Result |
|---|---|
| Every spec is plain ASCII | pass |
| Every relative link in the specs resolves | pass |
| `pre-commit run --files` on the four specs | pass |
| Every function, constant and rule name the specs cite exists under `claude/skills/auditme/checks/` | pass |
| `docs/guide/checker.md`, which the raises spec edits, exists | pass |
| Spec length within `/specdev`'s guide of about 200 lines | fail: 239, 263, 255 and 270 lines (choice 4 below) |

## The items

**S1. Raises section resolution** - `agents/specs/raises-section-resolution/spec.md` (item 1).
The rule `raises-section-drift` passes `class_methods=True` to the shared
call resolver, so `Probe.load()` resolves, and follows a same-package callee
with no `Raises:` section into its own raises and callees, to a fixed depth,
with cycles cut and handlers netted out at every step. A hit names the
chain (`declared by pkg.inner.perform via pkg.wrap.wrapper`). Every
narrowing of the earlier false-positives spec is kept. Needs Task 1 of the
repeatable-phase-b list (the resolver moved into `core.py`). Widens the
rule's output, so every project using the shared hooks sees new hits; the
catch-up run there and deleting the `requests.md` entry are the operator's,
after the order.

**S2. Listed Phase B documentation questions** - `agents/specs/listed-phase-b-documentation-questions/spec.md` (item 2, first group).
Listers for Doc4 (specs against code) and Doc5 (`docs/` against code): one
candidate per document section and the code target a backticked name in it
resolves to, hashing both; unresolvable names go into one candidate per
section. Doc1 and Doc2: one candidate per `AGENTS.md` section, hashing the
tracked tree or the dependency and hook tables. Four briefs, version 1. Also
settles how questions that stay sampled run (decision 3) and adds a
`**Commit:**` line to the review template so the next audit knows its diff
base. Batch sizes are unmeasured; the operator's first real run is the
pilot.

**S3. Listed Phase B test questions** - `agents/specs/listed-phase-b-test-questions/spec.md` (item 2, second group).
T1 candidates: functions with an `if`, a `try` with a handler, a `match`, or
a state change another method tests. T2 candidates: pure functions over a
fixed set of types hypothesis can build. A new test-tree index finds the
tests that reach each candidate by resolved import, never by a bare name;
each candidate's hash covers its related test files, so a new test re-plans
it.

**S4. Listed Phase B architecture questions** - `agents/specs/listed-phase-b-architecture-questions/spec.md` (item 2, third group).
Listers for A11, A19, A1 and A17 that reuse the site-finding code of the
rules that already cover them (hoisted or made public, no rule's output
changing), and drop any site such a rule already reports, accepted or not,
so nothing is judged twice. Four briefs settle the thresholds the
questions' text leaves open.

**S5. Test-log save in `agents/tasks/repeatable-phase-b/tasks-1.md`.**
`/rro`'s merge gate reads a saved test log and does not rerun the tests.
That list predates the order, so its last task (Task 9) gains one subtask:
pipe its full test run through `tee` to the order's `test log` path. No
other change.

## Choices made (reversible, not decisions)

1. **New specs, not amendments.** Item 2 asked for an amendment of the
   repeatable-phase-b spec per group. That spec is already near 300 lines;
   each group is a separate spec that extends its API and links to it, and
   the repeatable-phase-b spec stays the record of version 1.
2. **Whole test files in the T1 and T2 hash** (S3 open decision 2), so no
   new test in a related file goes unseen. It follows from the reason the
   listed path exists: convergence over reviewer cost.
3. **A library's top-level `__all__` is judged like any other** (S4 open
   decision 3); the operator dismisses a finding once and the ledger keeps
   the dismissal while the code is unchanged. No configuration is added.
4. **The specs stay whole although each is over `/specdev`'s size guide.**
   Each is one cohesive lister group that becomes one task list; splitting
   S2 into Doc4 and Doc5 and Doc1 and Doc2 would add a row and a review
   without changing the work.
5. **The catch-up run for S1 is not a row.** It happens in other
   repositories, so it is the operator's step after the order, and
   `TODO.md` item 1 stays open until the `requests.md` entry is deleted.

## Decisions

**D1. How far `raises-section-drift` follows a callee with no `Raises:` section (S1).**
Background: the request (2026-11-20) proposes "one further level, or to a
fixed depth"; the A4 lister lists callees to `--depth` 3. Affects the
catch-up surface in every project using the hooks, and the rule's run time.
- (a) Fixed at three calls, the A4 lister's default, so the rule and Phase B
  see the same functions. **Recommended.**
- (b) One further level: the smallest catch-up surface; a wrapper of a
  wrapper stays hidden and Phase B keeps finding those by hand.
- (c) Unbounded, with the cycle guard: complete, with the largest catch-up
  surface and run time.

**D2. Whether a section-less wrapper's own `raise` statements reach its caller's verdict (S1).**
Background: the request names errors behind the wrapper; one the wrapper
raises itself is already a `missing-raises-section` hit on the wrapper.
- (a) Count them: the caller's section is judged on everything that reaches
  it; one root cause gives a second hit, on the caller. **Recommended.**
- (b) Callees only: a smaller catch-up surface; those stay with Phase B.

**D3. How often a question that stays sampled runs (S2).**
Background: repeatable-phase-b (2026-11-20) makes a sampled question's new
site coverage, not drift, but sets no cadence; `checks/changed.py` already
resolves a diff base. Affects every sampled question in every audit (A13,
A15 and every question without a lister).
- (a) Changed files since the previous review's commit, every audit:
  unchanged code converges by construction; a site missed before is never
  found.
- (b) The whole tree every third audit: old sites surface; new code waits up
  to two audits.
- (c) Both: changed files every audit, the whole tree every third, the span
  the 2026-11-20 measurement covers. **Recommended.**

**D4. What a backticked name that resolves to nothing becomes (S2).**
Background: no sweep rule flags a name in a spec or guide with no
definition today.
- (a) A candidate per section, judged against the brief: no new rule and no
  catch-up run. **Recommended.**
- (b) Also a new sweep rule for path-shaped names in implemented specs and
  `docs/`, with a catch-up run in every project with the hooks: mechanical,
  but noisy on run-time paths and paths in other repositories.

**D5. Which documents Doc5 reads (S2).**
Background: Doc5's text names `docs/`, and the spec lists `docs/` only. The
shared user-guides rule says a small project keeps its user guide in
`README.md`, so in such a project Doc5 would read nothing; Doc3 compares
`README.md` with `AGENTS.md`, not with the code.
- (a) `docs/` only, as the question's text says: a small project's guide
  goes unchecked against its code.
- (b) `docs/` and `README.md`: the predicate widens with this change, and
  the first audit's README findings are catch-up. **Recommended**, because
  the shared rule puts the guide there. (The spec recommended (a).)

**D6. How the listers tell a private function from a public one (S3, S4).**
Background: S3 lets a test of a caller cover a private T1 candidate, S4 lets
a caller's envelope cover an A1 call in a private helper, and S4's A17 brief
counts a reach into a private submodule as a bypass. All three specs judge
"private" by a leading underscore. The shared coding standard forbids
leading underscores and asks for `__all__`, so in a project that follows it
nothing would count as private.
- (a) Private means named in no `__all__` of its package, where the package
  has one; a leading underscore also counts, for projects without
  `__all__`. **Recommended.**
- (b) A leading underscore only, as the specs wrote: right for projects
  with underscores, wrong for every project that follows the shared
  standard.

**D7. Whether a test of a caller covers a public T1 candidate (S3).**
Background: T1 asks for "at least one test case"; the shared testing rule
says every public function must have tests.
- (a) A public candidate needs a direct test; a private one (as D6 defines
  it) may be covered through a caller. **Recommended**, matching the testing
  rule.
- (b) A caller's test covers any candidate: fewest findings.
- (c) Only direct tests count: most findings, many on helpers nobody tests
  alone.

**D8. Whether T2's well-defined types include `str` and `bytes` (S3).**
Background: most parsers and formatters take `str`.
- (a) Include them: parsers and formatters are judged; the brief flags only
  where the reviewer can state a property. **Recommended.**
- (b) Exclude them: a shorter list; parsers stay unjudged.

**D9. Whether a caller's envelope covers an A1 call in a private helper (S4).**
Background: A1 asks whether "the call" is inside a translating `try`; the
rule `filesystem-op-without-envelope` already passes a private helper whose
caller translates.
- (a) Yes, for a private (D6) or nested helper whose every resolved caller
  calls it inside an envelope; the callers go in the payload and the hash,
  so a new caller re-plans it. **Recommended**, consistent with the rule.
- (b) No, every call needs its own envelope: more findings, against the
  rule's existing reading.

**D10. Whether a read from the test tree counts as an A17 consumer (S4).**
Background: A20 counts test readers, since a mutation there is real; A17
asks whether a name belongs on the public surface.
- (a) No: a name only tests read is a finding. **Recommended.**
- (b) Yes: fewer findings, and test-only exports stay public.

## Answers

Answered on the review page on 2026-11-20, every answer with no comment
(read from the page's database at 19:10 UTC, when the answers were saved):

| Item or decision | Answer |
|---|---|
| S1. Raises section resolution | approved |
| S2. Listed Phase B documentation questions | approved |
| S3. Listed Phase B test questions | approved |
| S4. Listed Phase B architecture questions | approved |
| S5. Test-log save in the repeatable-phase-b task list | approved |
| D1. Follow depth for a section-less callee | (a) fixed at three calls |
| D2. A section-less wrapper's own raises | (a) counted |
| D3. Cadence for sampled questions | (c) changed files every audit, whole tree every third |
| D4. An unresolved backticked name | (a) a candidate per section, no new rule |
| D5. Doc5's documents | (b) `docs/` and `README.md` |
| D6. What is private | (a) not in its package's `__all__`; underscore only without `__all__` |
| D7. A caller's test and a public T1 candidate | (a) public needs a direct test |
| D8. `str` and `bytes` in T2's types | (a) included |
| D9. A caller's envelope and an A1 private helper | (a) covers it when every caller translates |
| D10. A test-tree read and A17 | (a) not a consumer |

Applied: each spec moved to version 1.1 and records its decisions in a
`## Decisions (operator, 2026-11-20)` section. S5 is applied when the task
lists are written.
