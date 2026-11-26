# ruff

Report each `ruff check` finding and each file `ruff format --check` would reformat under the root.

The check runs the ruff that `auditor.api.ruff_executable` finds, in the project directory: `$AUDITME_RUFF` when set and not empty, else the project's `.venv/bin/ruff` when it is an executable file, else `ruff` from PATH. A ruff that cannot run is a hit (`ruff not installed`), as is output from either command that is not JSON (`ruff-check-parse-error`, `ruff-format-parse-error`).

Both commands report in ruff's JSON output format, so a file `ruff format` would rewrite is a `ruff-format` hit at the path and line ruff names.

No accept marker applies: fix the code, or silence a `ruff check` line with `# noqa: <code>`.
