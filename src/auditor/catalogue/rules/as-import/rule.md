# as-import

Flag `import X as Y` / `from M import X as Y` where the project bans it.

An alias is a second name for a module, so every reader has to hold the
mapping in their head, and the full-import-path codemods do not see it:
one project's AGENTS.md states the ban and names two enforcement mechanisms -
ruff's `ICN003`, which only sees the modules listed in `banned-from`, and
`bin/full-path-imports.sh --check`, which rewrites `from X import Y` and
leaves a bare `import gitutils as module` alone. Both reported clean over a
tree that carried one.

The signal is `ast.alias.asname` on any `ast.Import` or `ast.ImportFrom`.

Carve-out: a module-level `from ... import ... as ...` in an `__init__.py`.
That is a package's re-export list, the one place a from-import is
sanctioned, and renaming on the way out is how a surface is composed. A
plain `import x as y` in an `__init__.py` is not a re-export and still
fires.

Fires only where `project_bans_as_imports` finds the rule declared.
