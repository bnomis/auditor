# lockfile-drift

Report a lockfile that `uv lock --check` finds out of date, or cannot verify.

The check runs only when `pyproject.toml` and `uv.lock` both exist. A `uv` that cannot run is a hit, since the question went unanswered.

Refinements:

- A lockfile that needs regenerating and a lockfile that could not be checked are different facts, and carry different variants. Reporting both as drift is the failure-as-absence defect, in the checker rather than in the code under audit.
- A user-level `exclude-newer` that the lock was not made with re-resolves it on this machine only, and CI, without that config, sees no drift. Only when uv names that setting as the reason is the check repeated without the user's config (`UV_NO_CONFIG=1`).
- The evidence keeps only uv's `error:` lines, with any resolution timestamp masked, so an unchanged tree gives the same evidence on every run (the convergence rules in the auditme skill).

It is a project check: the driver runs it once per sweep, so a project with no Python root still has its lockfile checked.
