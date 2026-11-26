# Order: runner and rules split

Written on 2026-11-25 for the four task lists that split the auditme runner
from the rules it checks. The specs were approved on 2026-11-25, with every
item answered, in `agents/specs/runner-rules-split-review.md`. No `TODO.md`
item covers this work, so no row moves an item to `DONE.md`.

Run it from the main checkout, on `main`, with a clean tree level with
`origin/main`:

```text
/rro agents/tasks/order-runner-rules-split.md
```

The rows run strictly in sequence, each needing the one before it merged:

1. The checker becomes the installable `auditor` CLI, with behaviour
   unchanged.
2. Rules can be loaded from `$AUDITOR_RULES_PATH`, while the built-in rules
   still run when the variable is unset.
3. Every built-in rule moves into the default catalogue at
   `src/auditor/catalogue/`, and the built-ins are removed. From this row's
   merge on, `AUDITOR_RULES_PATH` is required. The tests, CI and this
   repository's local hooks set it to the catalogue themselves.
4. `auditor rules init` and `apply` are added.

One row stops for the operator. Row 4's Task 1 publishes a review page
recommending a pack for each catalogue rule, then stops. Once every item has
an answer, an operator session copies the answers into
`agents/reviews/rules-init-packs.md`, commits that, and restarts the order.

There are no prerequisites outside this repository. After the order, two
steps are the operator's own:

- Create your own rules repository with `auditor rules init <dir>` and
  `auditor rules apply <dir>`, and point this repository's `.envrc`
  (`export AUDITOR_RULES_PATH=<dir>`) and every other project's at it.
  Agents never edit `.envrc`.
- Every project that pins the audit hooks needs a rules repository before it
  moves its hooks to a revision at or after row 3, version 0.3.0.
  `docs/setup.md` gives the upgrade steps.

| Setting | Value |
|---|---|
| checkpoint command | `pre-commit run --all-files && pre-commit run auditme-all --hook-stage manual --all-files && uv run pytest tests claude/skills/auditme-project-setup/tests -q -p no:cacheprovider && uv run --group docs mkdocs build --strict` |
| checkpoint every | 3 |
| test log | `logs/rro/{spec}/tasks-{index}/final-tests.log` |
| test pass line | `all selected test directories passed` |
| test fail pattern | `FAILED` |
| always wait for | |
| progress page | |

| # | Task list | Waits for | Stops for you | Status |
|---|---|---|---|---|
| 1 | `auditor-cli/tasks-1.md` | - | - | running |
| 2 | `rules-repository/tasks-1.md` | 1 | - | todo |
| 3 | `default-rule-catalogue/tasks-1.md` | 2 | - | todo |
| 4 | `rules-init/tasks-1.md` | 3 | Task 1: answer the pack-membership review page, then an operator session copies the answers into `agents/reviews/rules-init-packs.md` | todo |
