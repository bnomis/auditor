---
paths:
  - "**/*.py"
---

# Python Coding standards

Follow the ruff rules defined in `pyproject.toml`, see `[tool.ruff]` in `pyproject.toml`.

Below `<project>` is the current project's top level module name.

## Python version

- Minimum supported version: Python 3.14 <https://docs.python.org/3.14/>

## Critical rules

- **Do not modify** these files without explicit instruction: `.envrc`, `uv.lock`, `.pre-commit-config.yaml`
- **Always use full import paths** - no `from X import Y` in internal code (see [Imports](#imports))
- **Never run the full test suite** - scope tests to changed files/modules (see [Testing scope](testing.md#testing-scope))
- **Use `loguru.logger`** - do not use stdlib `logging` (see [Logging](#logging))
- **No `pip install`** - use `uv add <package>` to add dependencies (see [Dependency management](dependencies.md))
- **Run checks before committing**: `ruff check && ruff format --check`, then `pre-commit run --all-files`
- **Code securely** - see [security](../security.md)

## Project structure

- `src/<project>/__init__.py` - public api
- `src/tests/` - tests mirror source structure
- `bin/` - entry point scripts, bin-scripts
- `bin/activate.sh` - activate the Python virtual environment

## Before committing and pushing

1. `ruff check && ruff format --check`
2. `pre-commit run --all-files` (checks more than ruff)
3. Run tests for changed modules (see [Testing scope](testing.md#testing-scope))

## Clean `__init__.py` files

Avoid defining functions, constants and global variables in `__init__.py` files. Instead define these things in a file named `base.py` and import the required symbols into `__init__.py` and expose in the `__all__` list.

Example:

```python
# __init__.py
from .base import Foo, Bar
__all__ = ['Bar', 'Foo']
```

## Imports

- Follow ruff's isort-compatible import ordering (stdlib, third-party, local)
- First-party packages: `<project>`
- No wildcard imports (`from module import *`)
- If you come across `from __future__ import annotations` in a file, remove it

Do not include unnecessary imports. If an import exists but is not used, remove it.

**Exception: `__init__.py` re-export lists** - relative imports (`from .module import Symbol`) are permitted inside `__init__.py` files for re-exporting symbols from sub-modules into the package's public API. This is the only permitted use of `from X import Y` in internal code.

**Always use full import paths** - do not use `from X import Y` pattern:

```python
# CORRECT - full import path
import pathlib

import <project>.cli

p = pathlib.Path()
cpu = <project>.cli.detect_compute_resources()
```

```python
# INCORRECT - avoid this pattern
from pathlib import Path
from <project>.cli import detect_compute_resources

p = Path()
cpu = detect_compute_resources()
```

### No "as" imports

Do NOT use "as" imports. Do NOT do the following:

```python
# INCORRECT - avoid this pattern
import numpy as np
import pandas as pd
import multiprocessing as mp
import matplotlib.pyplot as plt
```

## Type annotations

- All function signatures must have parameter and return type annotations
- Use `None` return type explicitly for functions that return nothing
- Prefer built-in generics (`list[str]`, `dict[str, int]`) over `typing` equivalents
- Use `|` union syntax instead of `Union` or `Optional`
- Use deferred evaluation of annotations (native in 3.14)
- Do not use `from __future__ import annotations` - it is unnecessary on Python 3.14
- If you see `from __future__ import annotations` in a file, remove it

If an import is needed **only** for type annotation, import inside of a TYPE_CHECKING block. For example, like this:

```python
import typing

if typing.TYPE_CHECKING:
    import <project>.cli
```

## Naming

- `snake_case` for functions, methods, variables, modules
- `PascalCase` for classes
- `UPPER_SNAKE_CASE` for constants
- Prefer `__all__` to define the public API of packages imported by external consumers.

## No leading underscores

- DO NOT use leading underscores.
- Leading underscores (`_name`, `_NAME`) are NOT an accepted secondary privacy convention for marking implementation details within a module.
- Single throwaway underscores `_` (e.g. for unused variables in loops) are acceptable

## String formatting

- **Always use f-strings** instead of `%` formatting or `.format()`
- Convert existing `%` patterns to f-strings when editing
- Example: `f'Exception: {e}'` instead of `'Exception: %s' % e`
- Use single quotes for strings whenever possible (enforced by ruff format config)
- Exception: use double quotes when the string itself contains a single quote

## Alphabetical ordering

Configuration lists, enum-like collections, and import groups should be in **alphabetical** order. For example:

```python
names = [
    'aardvark',
    'bird',
    'cat',
]
```

Do **not** alphabetise lists where order is semantically meaningful (e.g., processing pipelines, priority ordering, function call sequences).

## Data structures

- Prefer `dataclasses` for structured data
- Use `cappa` dataclass conventions for CLI argument definitions

## Exception syntax

We're using at least Python version 3.14.

The following:

```python
except ValueError, RuntimeError:
```

Without parentheses, is valid Python 3.14 syntax per PEP 758, see <https://docs.python.org/3/reference/compound_stmts.html#try>

Do not flag or "fix" it.

The only caveat: parentheses are still required when using as — e.g.

```python
except (ValueError, RuntimeError) as e:
```

## Error handling

- Let unexpected exceptions propagate rather than silently catching them

## Comments

Do not add obvious comments.
Only add comments if they add a lot of value that is not obvious from reading the code.

Function docstrings are not required for all functions but you may add them to describe the purpose and input/output of a function if it helps for understanding.

## Logging

- Use `loguru.logger`  - do not use stdlib `logging`
- Use appropriate levels:
  - `debug` for internals
  - `info` for progress
  - `warning` for recoverable issues
  - `error` for failures
  - `exception` to log exceptions in `except` blocks
- CLI entry points (`cli.py`, `ensemble/cli.py`) may use `print()` for
  machine-consumable stdout (config dumps via `--dump-config`, result
  summaries written to stdout). This output is typically piped into files
  or other tools, so `loguru` would add unwanted structured log overhead.

## Logging exceptions

Always use `loguru.logger.exception` to log exceptions. For example:

```python
  try:
      if df.shape[1] < 2:
          loguru.logger.warning('Cannot compute correlation with fewer than 2 features')
          return None
      return df.corr(method='pearson')
  except Exception as e:
      loguru.logger.exception(f'Failed to compute correlation matrix: {e}')
      raise
```
