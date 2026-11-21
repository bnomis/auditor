---
paths:
  - "**/*.py"
---

# Imports

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

import loguru

import <project>.cli

p = pathlib.Path()
cpu = <project>.cli.detect_compute_resources()
loguru.logger.debug('message')
```

DO NOT do the below:

```python
# INCORRECT - avoid this pattern
from pathlib import Path
from <project>.cli import detect_compute_resources

from loguru import logger

p = Path()
cpu = detect_compute_resources()
logger.debug('message')
```

## imports in `__init__.py` files

from imports are allowed inside of `__init__.py` files as shown below:

```python
from .adjudicate import adjudicate

__all__ = [
    'Adjudication',
]
```

## No "as" imports

Do NOT use "as" imports. Do NOT do the following:

```python
# INCORRECT - avoid this pattern
import numpy as np
import pandas as pd
import multiprocessing as mp
import matplotlib.pyplot as plt
```
