# Order: raises resolution and listed Phase B

Written on 2026-11-20 by `/todo-run-order 1,2`, for two `TODO.md` items:
"`raises-section-drift` misses errors reached through a section-less
wrapper or a `Class.method()` call" (item 1) and "Put the Phase B questions
that find most onto the listed path" (item 2). It follows the specs' review,
`agents/reviews/order-raises-resolution-and-listed-phase-b-specs.md`,
answered on 2026-11-20.

Run it from the main checkout, on `main`, with a clean tree level with
`origin/main`:

```text
/rro agents/tasks/order-raises-resolution-and-listed-phase-b.md
```

Row 1 builds version 1 of the listed Phase B path (A4 only) and the shared
call resolver; every other row needs it. Row 2 widens `raises-section-drift`
on that resolver. Rows 3 to 5 put the documentation, test and architecture
questions on the listed path, each after the one before, since they edit the
same lister registry and `SKILL.md` passages. Row 5's last task moves item 2
to `DONE.md`.

No row stops for the operator, and nothing has to be provided before the
start. After the order, two steps are the operator's, outside this
repository:

- the catch-up run for row 2: in every project using the shared hooks, run
  the sweep at the new hook revision, land a fix or an accept marker for
  each new `raises-section-drift` hit and note it in that project's
  `agents/audit-reviews/summary.md`; then delete the request entry in
  `claude/skills/auditme/requests.md` here and move item 1 to `DONE.md`;
- the pilot of the documentation listers' batch sizes: the first real audit
  runs each Doc question twice, as A4's pilot was run, and a threshold it
  exposes lands as a brief version bump.

| Setting | Value |
|---|---|
| checkpoint command | `pre-commit run --all-files && pre-commit run auditme-all --hook-stage manual --all-files && uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests claude/skills/project-setup/tests tests -q -p no:cacheprovider && uv run --group docs mkdocs build --strict` |
| checkpoint every | 3 |
| test log | `logs/rro/{spec}/tasks-{index}/final-tests.log` |
| test pass line | `all selected test directories passed` |
| test fail pattern | `FAILED` |
| always wait for | |
| progress page | https://claude.ai/artifact/XeWk6GJbeU68NwiXZFMxyP |

| # | Task list | Waits for | Stops for you | Status |
|---|---|---|---|---|
| 1 | `repeatable-phase-b/tasks-1.md` | - | - | merged 8548019 |
| 2 | `raises-section-resolution/tasks-1.md` | 1 | - | merged f1a24f4, after serial rerun |
| 3 | `listed-phase-b-documentation-questions/tasks-1.md` | 1 | - | merged c10a5cc |
| 4 | `listed-phase-b-test-questions/tasks-1.md` | 3 | - | merged 9da7cc3 |
| 5 | `listed-phase-b-architecture-questions/tasks-1.md` | 4 | - | merged 73df3f4 |

Checkpoint after 5: passed 991 passed
