## Critical rules

- **Do not modify** these files without explicit instruction: `.envrc`, `uv.lock`, `.pre-commit-config.yaml`
- **Always use full import paths** - no `from X import Y` in internal code (see [Imports](#imports))
- **Never run the full test suite** - scope tests to changed files/modules (see Testing scope in `~/.claude/rules/python/testing.md`)
- **Use `loguru.logger`** - do not use stdlib `logging` (see [Logging](#logging))
- **No `pip install`** - use `uv add <package>` to add dependencies (see [Dependency management](dependencies.md))
- **Run checks before committing**: `ruff check && ruff format --check`, then `pre-commit run --all-files`
- **Code securely** - see `~/.claude/rules/security.md`
