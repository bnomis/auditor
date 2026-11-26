# from-import

Flag `from X import Y` in any file other than an `__init__.py`.

The shared import rule asks for full import paths - `import pathlib` then
`pathlib.Path` - and names one exception: an `__init__.py`'s re-export
list. Until 2026-10-14 nothing mechanical read that rule, so audits found
its sites by hand under S4, a judgement question answering
what a parser can.

The signal is any `ast.ImportFrom` in a non-`__init__.py` file, at any
depth: a function-local or `TYPE_CHECKING` from-import is still one. Each
statement is one hit, however many names it imports.

Not this rule's: `from __future__ import ...` (`future-annotations`) and
`from X import *` (`wildcard-imports`), which already report the same line
for a sharper reason. A relative import outside an `__init__.py` is also
`relative-import-nonpackage`'s, and is reported by both, the way
`import X as Y` is by both `aliased-imports` and `as-import`.

Ungated, unlike `as-import`: the rule is a shared standard, as
`stdlib-logging` and `legacy-typing` are, and no project restates it in
its AGENTS.md - a gate there would silence the check on every project the
rule governs.
