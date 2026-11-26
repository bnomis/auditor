# reexport-in-non-init

Flag module-level assignments `X = <dotted.path>.X` in files OTHER
than `__init__.py`. Re-exports belong in the package's `__init__.py`;
mid-tree re-export shims fragment the public surface and create
migration-shim-style consumer drift.
