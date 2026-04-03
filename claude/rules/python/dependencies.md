---
paths:
  - "**/*.py"
  - "**/pyproject.toml"
  - "**/uv.lock"
  - "**/requirements.txt"
---

# Python Dependency management

- All dependencies are declared in `pyproject.toml` and managed via `uv`
- Do not run `pip install` directly - use `uv add <package>` to add dependencies
- The lockfile `uv.lock` is committed to the repository
