**A18. Hot-path setup.** For every callback method (`on_step`, `on_log`, `on_evaluate`, `on_batch_*`): does it perform setup (mkdir, file open) that should live in `__init__`? Flag per-event side effects.

## Documented conflicts

| Winner | Loser | Site pattern | Reason |
|--------|-------|--------------|--------|
| `A18` callbacks hot-path setup | `constructor-disk-io` | callback class `__init__` performing `mkdir` of a path that the callback writes to | one-time mkdir per Trainer instance is preferable to per-event mkdir; loser auto-accepted |
