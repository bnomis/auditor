## imports in `__init__.py` files

from imports are allowed inside of `__init__.py` files as shown below:

```python
from .adjudicate import adjudicate

__all__ = [
    'Adjudication',
]
```
