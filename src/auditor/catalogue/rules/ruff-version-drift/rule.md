# ruff-version-drift

Report a ruff that the audit runs which is not the version the project's `ruff-pre-commit` hook pins, or a pin that cannot be read.

Project-level: reads `.pre-commit-config.yaml` in the project directory and runs `ruff --version` there; the source root is unused. Silent when the file is absent or holds no `ruff-pre-commit` repo. A ruff that cannot run is a hit.

The pin is a plain version `rev`, or a SHA `rev` with a `# frozen: <version>` comment. A repo URL with a `.git` or `/` suffix is still found. The ruff compared is the one `auditor.api.ruff_executable` finds, and the evidence names it. A scoped `# auditme: accept[ruff-version-drift] <reason>` marker on the `rev` line, or the line above, accepts the hit.
