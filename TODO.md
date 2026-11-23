# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

## A project with no audit root has its `.venv` swept

Found on 2026-11-23 running the sweep on another project with no `src/`
and no `.py` in `bin/`: it reported `unreadable-file` for a non-UTF-8 test
file inside `.venv/lib/.../site-packages/`. The sweep prints "running the
project-level checks only", yet `corpus_py_files` in
`claude/skills/auditme/checks/auditme/core.py` falls back to
`all_py_files(src_root)` when there are no roots, and that walks the whole
project, `.venv` and every hidden directory included.

Reproduce: a directory with a `pyproject.toml`, a `git init`, and
`.venv/lib/bad.py` holding bytes that are not UTF-8; `audit.py <dir>`
reports it. Declaring `[tool.auditme] roots = []` avoids it, which is the
workaround the affected project uses.

Fix: with no root, return no files instead of falling back to the swept
root, or skip the directories `SPEC_SKIP_PARTS` and the hidden-directory rule
already skip. Add the reproduction as a test. Small, no spec.

## `raises-section-drift` misreads three common shapes

Found on 2026-11-23 clearing the rule's first hits in other projects,
each checked by hand:

- **A combined entry is not read.** `Raises:` with `ErrorA, ErrorB: <when>`
  on one line counts as declaring neither, so the function is reported for
  an exception it names. Read each comma-separated name before the colon.
- **A tuple constant in a handler is not resolved.** `except
  pkg.errors.HANDLED_ERRORS:`, where `HANDLED_ERRORS` is a module-level tuple
  of exception classes, is treated as catching nothing, so every exception
  its members (or their subclasses) cover is reported as escaping. Resolve
  a name or attribute that refers to a module-level tuple of classes.
- **Exceptions declared by another first-party library are not followed.**
  A callee in a sibling package installed alongside (not under `src/`)
  whose `Raises:` names an exception is ignored, so a function that lets it
  escape is not reported. A false negative; lower priority than the two
  above.

Path-sensitive cases (a callee reached only under a condition that cannot
hold, or a call repeated after an earlier call on the same input was
validated) were accepted with markers: the rule cannot be expected to
follow them.
