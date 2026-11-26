## Clean `__init__.py` files

Avoid defining functions, constants and global variables in `__init__.py` files. Instead define these things in a file named `base.py` and import the required symbols into `__init__.py` and expose in the `__all__` list.

Example:

```python
# __init__.py
from .base import Foo, Bar

__all__ = ['Bar', 'Foo']
```
