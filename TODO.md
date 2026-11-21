# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged. See the shared `todo-add` and `todo-review` skills for
the shape of an item.

## The audit reads none of this repository's own Python

Found on 2026-11-21 when `/auditme` was run on this repository. `audit.py`
with no options printed `audit.py: no package under src/ and no extra root;
running the project-level checks only` and emitted no hits. All of this
repository's Python lives under `claude/skills/`: the checker's scripts and
its `auditme` package in `claude/skills/auditme/checks/`, and the tests in
`claude/skills/auditme/tests/`, `claude/skills/auditme-project-setup/tests/`
and `tests/`. Since the installer became `bin/install-claude.sh`, `bin/` holds
no Python. Run by hand with those four directories as `--extra-root`, the
sweep gave 659 hits on 2026-11-21, 654 of them unaccepted; the largest rules
were `literal-duplication` (153), `leading-underscore-def-class` (109),
`leading-underscore-attribute-access` (101), `from-import` (53),
`leading-underscore-const-upper` (49) and `silent-broad-except` (37).
`phaseb.py plan` found no candidates for A1, A4 or T1 the same day; the Doc
questions did have candidates. The commit and push hooks run the same default
sweep, so none of this code has been gated here. The operator chose on
2026-11-21 to stop review-1 of this repository until this is fixed.

Cause: the roots are fixed by layout. `_audit_roots()` in
`claude/skills/auditme/checks/auditme/core.py` takes each package under
`src/` and each `EXTRA_ROOT_NAMES` directory, which is `('bin',)`
(`core.py:146`); `audit.py --extra-root` replaces that set for one run only.
`sweep()` in `claude/skills/auditme/checks/changed.py` runs
`audit.py <repo-root>` with no options, and `phaseb.py`'s listers walk the
same roots, so neither the hooks nor Phase B can be pointed elsewhere. Passing
`claude/skills/auditme/checks` as a root would also name its modules
`checks.auditme.*`, while the checker imports them as `auditme.*`
(`module_dotted` in `core.py` builds names from the root's own name), so the
import-graph and public-surface checks may report false hits on it.

Fix direction: let a project declare its audit roots in one place that
`audit.py`, `changed.py` and `phaseb.py` all read, so the hooks cover the
same code as an audit, with each root's module-name base (here, the directory
the checker puts on `sys.path`). It changes the driver's contract and the
published hooks, so it goes through the project-setup spec
(`agents/specs/project-setup/spec.md`) first. Then land fixes or accept
markers for the catch-up surface before the first real audit of this
repository.

Spec: `agents/specs/project-setup/spec.md`, amendment 1.11; tasks: `agents/tasks/project-setup/tasks-4.md`, then `agents/tasks/project-setup/tasks-5.md`.
