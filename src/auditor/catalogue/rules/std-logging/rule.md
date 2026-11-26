## Logging

- Use `loguru.logger`  - do not use stdlib `logging`
- Use appropriate levels:
  - `debug` for internals
  - `info` for progress
  - `warning` for recoverable issues
  - `error` for failures
  - `exception` to log exceptions in `except` blocks
- CLI entry points (`cli.py`, `<package>/cli.py`) may use `print()` for
  machine-consumable stdout (config dumps via `--dump-config`, result
  summaries written to stdout). This output is typically piped into files
  or other tools, so `loguru` would add unwanted structured log overhead.
