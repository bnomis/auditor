# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

## Implemented specs and the spec index still name the old `claude/skills/auditme/checks/` paths

Found on 2026-11-26, after the runner-rules split order merged, by
`grep -rn 'claude/skills/auditme/checks' agents/specs`. These still point at
files under `claude/skills/auditme/checks/`, which no longer holds any
tracked file:

- `agents/specs/index.md`, in its Path column;
- the implemented specs `auditme-false-positives`, `listed-phase-b-test-questions`,
  `listed-phase-b-architecture-questions`,
  `listed-phase-b-documentation-questions`, `project-gate-settings`,
  `project-setup`, `raises-section-resolution` and `repeatable-phase-b`,
  each `agents/specs/<name>/spec.md`.

`agents/specs/auditor-cli/spec.md` names the old paths on purpose, to
describe the move, and stays as it is.

Cause: `9cc3b8d` ("move the checker into the auditor package", Task 2 of
`agents/tasks/auditor-cli/tasks-1.md`) and the later catalogue tasks moved
the files but updated only code, tests and user docs, not older specs.
`claude/skills/auditme/checks/audit.py` became `src/auditor/sweep.py`,
`checks/phaseb.py` became `src/auditor/phasebcli.py`, and `changed.py`,
`core.py` and `phaseb/` moved under `src/auditor/`. `registry.py` was
removed, and the rule modules under `checks/auditme/rules/` became rule
directories under `src/auditor/catalogue/rules/`. Some `phaseb/` modules
moved again later: `src/auditor/phaseb/` now holds only `batches.py`,
`candidates.py` and `ledger.py`.

Fix direction: in `agents/specs/index.md`, point each Path at the file's
current home. Find each one with
`git log --follow --name-status -- <old path>`, or name the rule directory in
`src/auditor/catalogue/rules/`. In each implemented spec, leave the body as
its record and add one line under the header: "Paths moved by the
runner-rules split (2026-11-26): see `agents/specs/index.md`". It does not
need a spec. The leftover untracked `__pycache__` directories under
`claude/skills/auditme/checks/` can be deleted at the same time.
