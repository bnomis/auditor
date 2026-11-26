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
