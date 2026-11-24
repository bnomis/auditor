# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

## The sweep misses seven patterns one project's audits found by hand

Found on 2026-11-24 in `claude/skills/auditme/requests.md`, whose open entry
"Close the sweep gaps one project's audits carried as script candidates"
(filed on 2026-11-24, commit `9cd95f6`) has no `TODO.md` item. One project's
audits carried the patterns as script-coverage candidates across two cycles;
each was checked on 2026-11-24 against the checker at `3e23236`. The entry
lists every gap with its cause:

- `bare-parametric-annotation` misses bare inner generics (`list[dict]`).
- A discarded `-> tuple[...]` return (A23) has no rule and no lister.
- `layer-has-domain-error-raises-stdlib` misses `FileNotFoundError` and
  `TypeError`.
- `assert-never-missing` needs three `==` arms, and does not read a two-arm
  chain on a `Literal`-annotated name, dotted subjects, `in` or `match`.
- `build-name-has-side-effect` ignores `make_`; `pure-name-has-side-effect`
  matches only filesystem writes.
- `asymmetric-exception-translation` fires on callees with nothing to
  translate (a false positive).
- The A17 lister reads only an `__init__.py`'s `__all__`.

`agents/audit-reviews/summary.md` makes the next audit cycle wait until
`requests.md` is empty, so this item blocks it.

Fix direction: ship or reject each gap as `requests.md` describes, running
the sweep on a real project and landing fixes or accept markers for what each
change exposes, then delete the entry. The A23 rule is new and the
`assert-never-missing` change adds an inference path (the `Literal`
annotation as positive evidence), so start from a spec (`/todo-do`).

Spec: `agents/specs/sweep-coverage-gaps/spec.md` (approved 2026-11-24: `agents/reviews/sweep-coverage-gaps-spec-2026-11-24.md`); tasks: `agents/tasks/sweep-coverage-gaps/tasks-1.md`.

Note 2026-11-24: the checker work shipped; the item waits on the operator's
runs of the sweep on the projects that use the hooks and on the deletion of
the `requests.md` entry.
