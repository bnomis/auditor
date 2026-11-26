"""Helpers that read the shape of an AST node, for rules to share."""

import ast

import auditor.core

BARE_GENERIC_NAMES = auditor.core.BARE_GENERIC_NAMES  # auditme: accept[reexport-in-non-init] the API publishes the core helper under this name
is_dunder_all_assignment = auditor.core.is_dunder_all_assignment  # auditme: accept[reexport-in-non-init] the API publishes the core helper under this name


def leading_underscore_names(target: ast.AST) -> list[tuple[str, int]]:
    """Return `(name, lineno)` for every `_foo` Store-name inside a
    tuple-unpack target (or a bare `_foo`). Skips bare `_`."""
    out: list[tuple[str, int]] = []

    def walk(n: ast.AST) -> None:
        if isinstance(n, ast.Name):
            if n.id.startswith('_') and n.id != '_' and not n.id.startswith('__'):
                out.append((n.id, n.lineno))
        elif isinstance(n, (ast.Tuple, ast.List)):
            for elt in n.elts:
                walk(elt)
        elif isinstance(n, ast.Starred):
            walk(n.value)

    walk(target)
    return out


__all__ = ['BARE_GENERIC_NAMES', 'is_dunder_all_assignment', 'leading_underscore_names']
