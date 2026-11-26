"""Helpers that read the project's declared configuration, for rules to share."""

import typing

import auditor.core

accepted_lazy_imports = auditor.core.accepted_lazy_imports  # auditme: accept[reexport-in-non-init] the API publishes the core helper under this name
cached_per_run = auditor.core.cached_per_run  # auditme: accept[reexport-in-non-init] the API publishes the core helper under this name


def declared_root_modules() -> frozenset[str]:
    """The top-level module names the declared roots (`[tool.auditme]`) provide.

    A `package` root provides its own directory name; a `top-level` root
    provides each module and package directly inside it. Empty when no root is
    declared.
    """
    key = ('declared-root-modules', tuple(auditor.core.ROOT_MODULES.items()))
    if key in auditor.core.INDEX_CACHE:
        return typing.cast('frozenset[str]', auditor.core.INDEX_CACHE[key])
    names: set[str] = set()
    for root, mode in auditor.core.ROOT_MODULES.items():
        if mode == auditor.core.TOP_LEVEL:
            names.update(p.stem for p in root.glob('*.py'))
            names.update(p.name for p in root.iterdir() if p.is_dir() and (p / '__init__.py').is_file())
        else:
            names.add(root.name)
    declared = frozenset(names)
    auditor.core.INDEX_CACHE[key] = declared
    return declared


__all__ = ['accepted_lazy_imports', 'cached_per_run', 'declared_root_modules']
