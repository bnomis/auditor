# Runner and rules split: spec review

**Date:** 2026-11-25
**Review page:** https://claude.ai/artifact/TijAtYUsowpvG3zXatjy8x

## What is being reviewed and how

These four specs split the auditme runner from the rules it checks. After the
split:

- the runner is an installable `auditor` CLI;
- every rule (its Python check, its Phase B question and its prose standard)
  lives in a rules repository that `$AUDITOR_RULES_PATH` names;
- `auditor rules init` creates a new rules repository from chosen packs of
  the default catalogue.

The decisions made with you on 2026-11-25 are recorded in each spec. The
items below are the four specs and the choices I made that you did not decide
yourself. For each item, approve it, or flag it with a comment. No work starts
until every item has an answer.

- `/Users/simonb/src/auditor/agents/specs/auditor-cli/spec.md`
- `/Users/simonb/src/auditor/agents/specs/rules-repository/spec.md`
- `/Users/simonb/src/auditor/agents/specs/default-rule-catalogue/spec.md`
- `/Users/simonb/src/auditor/agents/specs/rules-init/spec.md`

## Automatic checks

- **Pass:** every template section (Module location, API, Error handling,
  Implementation, Settings, External dependencies) is present in each spec.
- **Pass:** the specs hold only ASCII punctuation
  (`LC_ALL=C grep -n '[^ -~]'` finds nothing).
- **Pass:** the build backend pin `uv_build>=0.13.0,<0.14` builds a wheel
  under `exclude-newer = "14 days"`, and data files under
  `src/auditor/catalogue/` are included in it (probe build, 2026-11-25).
- **Over the size guide:** `rules-repository/spec.md` is longer than the
  specdev skill's guide of about 200 lines (see the spec-size item below).

## The items

The recommendation for every item is to approve it. Each one either applies a
decision you made or follows an existing convention of this repository.

1. **The Auditor CLI spec.** Packages the checker as `auditor` with the
   `check`, `changed` and `phaseb` subcommands, with behaviour unchanged.
2. **The Rules repository spec.** Covers the rule directory format, the
   loader, the versioned `auditor.api`, the `auditor rules` commands, the
   standards SessionStart hook and the recorded identity.
3. **The Default rule catalogue spec.** Moves every rule into the
   `src/auditor/catalogue/` directory, proves it equivalent to today's rules
   as sets of hits and candidates, and removes the built-in registry.
4. **The Rules init spec.** Adds `init`, which writes `selection.txt`, and
   `apply`, which copies the selected rules, with packs by topic.
5. **The commands sit under `auditor rules`.** The commands are
   `auditor rules init`, `apply`, `list`, `check`, `test`, `standards`,
   `questions` and `identity`, rather than a top-level `init-rules`. This
   keeps every rules-repository command in one place.
6. **An unset `AUDITOR_RULES_PATH` is an error.** There is no silent fallback
   to the bundled catalogue, because a fallback would hide a project that is
   misconfigured. The error message names the init command.
7. **The catalogue ships inside the package** (`src/auditor/catalogue/`), so
   that `rules init` works from an installed wheel with no clone.
8. **Rules run in rule-name order.** This replaces the hand-kept `CHECKS`
   order and `registry-order.txt`, because findings are compared as sets.
9. **Identity and convergence.** An audit refuses to start on a rules
   repository with uncommitted changes. A review whose identity differs from
   the previous review's is marked "rules changed" and is not counted as a
   convergence measurement.
10. **Init has two steps and never prompts** (`init`, then `apply`), so that
    it works the same in a terminal, in a script and in Claude Code.
11. **Pack membership is decided later.** The task that writes `packs.toml`
    publishes its own review page with a recommendation for each rule.
12. **Version 0.3.0 is a breaking change.** Projects that pin the hooks need a
    rules repository from then on. `docs/setup.md` gives the upgrade steps.
13. **The runtime stays standard-library only.** pytest is needed only by
    `auditor rules test`, as the extra `auditor[test]`.
14. **A check that emits several ids from one table** (for example
    `check_text_patterns`) becomes one rule directory named after its family.
    It is not split into one directory per id, because the ids share one
    pattern table.
15. **The Rules repository spec is kept whole**, although it is past the size
    guide. Its loader, API, commands and identity are one cohesive unit; split
    up, each part would have to restate the others.
16. **This repository audits with your own rules repository.** The catalogue
    is only the default set that init copies from. Locally, this repository's
    `.envrc` names the rules repository you create, like any other project.
    Only the tests and CI point at the catalogue. (Changed on 2026-11-25 at
    your request: an earlier draft asked you to point `.envrc` at the
    catalogue.)

17. **Change requests become TODO items in the rules repository** (your
    request, 2026-11-25). An audit files each new request with `todo-add` in
    `$AUDITOR_RULES_PATH/TODO.md`. The next audit cannot start while
    `auditor rules pending` lists an open item.

    A rejected request moves to `DONE.md` as `Done: rejected on <date> - <reason>`,
    and also into the rule's `rule.md` under `## Rejected widenings` when it
    concerns one rule. `claude/skills/auditme/requests.md` is retired, and its
    one rejected entry moves into the `rule.md` of
    `mutable-module-level-exported`.

    Requests whose fix is in the runner or the skill go in the auditor
    repository's `TODO.md` and do not block audits, because a user of the
    runner cannot fix it. Specs changed: Rules repository (a new Change
    requests section and the `rules pending` command), Default rule catalogue
    (step 5) and Rules init (the files `apply` writes).

## Decisions

None. Every open question was answered on 2026-11-25.

## Answers

- **2026-11-25 (read from the review page at 20:53 UTC):** items 1 to 16 are
  approved, with no comments.
- **2026-11-25 (read from the review page at 21:01 UTC):** item 17 is
  approved, with no comment.
