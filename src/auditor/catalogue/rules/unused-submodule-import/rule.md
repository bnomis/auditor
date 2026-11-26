# unused-submodule-import

Flag a top-level `import a.b.c` whose name the file never uses.

Signal: a module-level `import X.Y` with no `as` alias, where neither the
dotted name nor its root followed by a dot appears in the rest of the
file. Carve-outs: an `as` alias, an undotted import, an import not at
module level, and a file that does not parse.
