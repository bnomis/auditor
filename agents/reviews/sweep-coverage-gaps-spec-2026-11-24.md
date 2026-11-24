# Review: sweep coverage gaps spec

**Review page:** https://claude.ai/artifact/8NLYMDA6qeA3XkpZPB6UCw
**Date:** 2026-11-24
**Spec:** `agents/specs/sweep-coverage-gaps/spec.md` (version 1.0, proposed)

## What is being reviewed and how

The spec closes the seven sweep gaps in the open `requests.md` entry "Close
the sweep gaps one project's audits carried as script candidates" (filed
2026-11-24), tracked by the `TODO.md` item "The sweep misses seven patterns
one project's audits found by hand". Each item below is one change the spec
makes. Approve it, or flag it with a comment saying what to change. No task
list is written until every item has an answer.

## Automatic checks

- Pass: every spec template section is present (Module location, API, Error
  handling, Implementation, Settings, External dependencies).
- Pass: no non-ASCII punctuation in the spec.
- Pass: every function and anchor the spec names exists at `8fd601d`:
  `bare_parametric_annotation_in_file`, `resolve_call`, `hit_on_anchor`,
  `translator_envelopes`, `FILESYSTEM_TOUCHING_CALLS`, `CROSS_FILE_RULES`,
  `SKILL.md` "Extending the script".
- Pass: all seven gaps re-checked against the code at `8fd601d` on
  2026-11-24; each is still open.
- Note: the spec runs to 206 lines, just over the ~200-line guide; it covers
  seven small changes, so it stays one spec.

## The items

Recommendation rule: approve where the change makes a rule read what its own
Phase B question in `SKILL.md` already asks, or what the request asks, with a
positive guard.

1. **Bare inner generics** (`bare-parametric-annotation`): the rule also reads
   inside a subscript, so `list[dict]` fires; `Literal[...]`, `Annotated`
   metadata and string forward references are not read. Recommend approve:
   the rule's own intent, no new judgement.
2. **Discarded tuple return** (new rule `discarded-tuple-return`, A23's
   mechanical part): a package function annotated `-> tuple[A, B, ...]`
   called as a bare statement. `tuple[X, ...]`, `_ = f()` and unresolved calls
   are not hits. Recommend approve: the annotation is the positive evidence,
   and the request asks for exactly this case.
3. **Two stdlib raises** (`layer-has-domain-error-raises-stdlib`): the set
   gains `TypeError` (already in A3's text and the rule's docstring) and
   `FileNotFoundError` (A3's text gains it). No new hit here (measured
   2026-11-24). Recommend approve.
4. **Wider `assert-never-missing`**: dotted subjects, `in` arms, a two-arm
   chain on a `Literal` of three or more members, and `match`. Unannotated
   two-arm chains stay exempt. Sites the rule newly hits leave A11's batches.
   Recommend approve: the `Literal` is positive evidence of a third value.
5. **Pure-name I/O** (`pure-name-has-side-effect`, `build-name-has-side-effect`):
   reads file reads, existence tests, subprocess and clock calls, as A9
   defines I/O; `make_` joins `build_` and `compute_`; registered `check_`
   functions are skipped as A9 decided (2026-11-21). No new hit here
   (measured 2026-11-24). Recommend approve: A9 already settles each point.
6. **Asymmetric translation needs something to translate**
   (`asymmetric-exception-translation`): a callee is a hit only when it makes
   a filesystem, subprocess or imported-module call, and not when it
   translates through a same-module translator. The shared test fixture
   changes from `len(name)` to a file read. Recommend approve: it adds the
   positive guard the rule lacked.
7. **A17 lists submodules**: a submodule's `__all__` is listed, its
   consumers being reads from any other file outside the test tree; the A17
   brief goes up one version. Recommend approve: the request asks for it,
   and existing candidates keep their ids.

Changes with no explanation: none.

## Decisions

None. Points that could have been decisions are settled by records the
project already holds, and the spec follows them:

- `TypeError` in the stdlib set: A3's text already lists it.
- How far `pure-name-has-side-effect` reads I/O, and the `check_` carve-out:
  A9's text (carve-out decided 2026-11-21, `agents/audit-reviews/review-1.md`).
- A23 as a sweep rule, not a Phase B lister: the request names only the
  bare-statement case.

## Answers

(empty until the review page is answered)
