# sibling-errors-no-common-base

Detect project error classes that sit side-by-side in a `*/errors.py`
module but have different base classes (one subclasses ProjectError,
another subclasses stdlib Exception). The mismatch is a smell:
existing `except ProjectError` catch sites will miss the sibling.

Signal:
  - A file named `errors.py` defines >= 2 classes whose names end in
    `Error`.
  - At least one of the classes subclasses a project-local error base
    (any name ending in 'Error' that is not stdlib Exception).
  - At least one of the classes subclasses stdlib `Exception`
    (or has no explicit base).
  - The two groups are not related by inheritance within the file.

A common mistake is defining `SignatureError(Exception)` next to
`RegistryError(Exception)` without making them share a hierarchy.
Call sites that catch `RegistryError` never catch `SignatureError`.
