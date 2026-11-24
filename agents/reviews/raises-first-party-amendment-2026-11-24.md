# Review: raises-section-drift first-party libraries (amendment 1.3)

**Review page:** https://claude.ai/artifact/3WXNFD43SB4nv8PnBzoPxA
**Date:** 2026-11-24
**Spec:** `agents/specs/raises-section-resolution/spec.md`, amendment 1.3 (proposed)

## What is being reviewed and how

Amendment 1.3 lets `raises-section-drift` follow a callee into a sibling
first-party library the project lists, closing the `TODO.md` item
"`raises-section-drift` does not follow `Raises:` sections of first-party
libraries outside the sweep" (finding dated 2026-11-23). Each item below is
one part of the amendment. Approve it, or flag it with a comment saying what
to change. No task list is written until every item has an answer.

## Automatic checks

- Pass: no drift between version 1.2 and the code; the names the spec uses
  (`SECTIONLESS_DEPTH`, `escapes`, `class_methods`, `unset_optional_guard`,
  `nested_call_sites`) are all in it.
- Pass: no non-ASCII punctuation in the spec.
- Pass: every name the amendment builds on exists: `declared_roots`,
  `RootsError`, `module_dotted`, `core.relpath` in
  `claude/skills/auditme/checks/auditme/core.py`; `audit.py` catches
  `SettingsError` where it reads the roots; `changed.py` runs `audit.py`.
- Note: the spec now runs to about 340 lines, over the ~200-line guide; the
  amendment is one section, kept beside the design it extends.

## The items

Recommendation rule: approve where the part follows from the decision below,
or keeps today's behaviour where the finding asks for no change.

1. **The `first-party` setting**: package directories relative to the
   project, which may lie outside it, read but never swept. Recommend
   approve: the chosen option, written as a setting.
2. **A bad or missing entry stops the sweep**, with the roots' error and exit
   status; a listed directory must exist wherever the sweep runs, CI
   included. Recommend approve: a silent skip would hide hits.
3. **Library errors count as domain errors.** Recommend approve: stated with
   the decision.
4. **Calls into the library are followed as in-package calls**; subjects stay
   the swept package's; no hit on a library file. Recommend approve: the
   rule's existing resolution.
5. **`related` names library files relative to the project**
   (`os.path.relpath`). Recommend approve: keeps `related` complete.
6. **The A4 lister stays as it is.** Recommend approve: no record asks to
   widen it; reviewers keep judging such calls by hand.

Changes with no explanation: none.

## Decisions

Decided on 2026-11-24 by the operator, through the question tool: first-party
libraries are named by declared paths in a new `[tool.auditme] first-party`
key, not inferred from `[tool.uv.sources]`, and the finding is not rejected.

## Answers

Answered on the review page on 2026-11-24 (read back at 12:38 UTC):

1. The `first-party` setting - approved.
2. A bad or missing entry stops the sweep - approved.
3. Library errors count as domain errors - approved.
4. Calls into the library are followed as in-package calls - approved.
5. `related` names library files relative to the project - approved.
6. The A4 lister stays as it is - approved.

No item was flagged and no comment was left. Amendment 1.3 stands as
written; the next step is its task list.
