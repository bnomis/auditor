import os
import re
import subprocess
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib

# `uv lock --check` exits non-zero both when the lockfile is genuinely stale
# and when it could not resolve at all. Only the first message is the drift.
LOCKFILE_DRIFT_MARKER = 'needs to be updated'
# uv's reason for re-resolving when the user's config adds an `exclude-newer` the lock lacks.
USER_EXCLUDE_NEWER_MARKER = 'due to addition of global exclude newer'
# auditme: accept[non-alphabetical-literal] a command line: the order is the argv
UV_LOCK_CHECK = ('uv', 'lock', '--check')
LOCKFILE_TIMESTAMP_RE = re.compile(r'\d{4}-\d{2}-\d{2}T[\d:.]+Z?')


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Emit a `lockfile-drift` hit when `uv lock --check` reports the lockfile
    out of date or cannot verify it; runs only when `pyproject.toml` and
    `uv.lock` both exist. A `uv` that cannot run is reported as a hit, since
    the question went unanswered."""
    pyproject = scope / 'pyproject.toml'
    uvlock = scope / 'uv.lock'
    if not pyproject.is_file() or not uvlock.is_file():
        return
    try:
        # auditme: accept[subprocess-without-memoisation] a PROJECT_CHECKS entry: the driver runs it once per sweep
        result = subprocess.run(UV_LOCK_CHECK, capture_output=True, text=True, cwd=scope)
        # A user-level `exclude-newer` that the lock was not made with re-resolves
        # it on this machine only; CI, without that config, sees no drift. Only
        # when uv names that setting as the reason is the check repeated without
        # the user's config. A lock made with the setting records it and passes
        # the first run, and dropping the config for it would report drift.
        if result.returncode != 0 and USER_EXCLUDE_NEWER_MARKER in (result.stderr or '') + (result.stdout or ''):
            env = {**os.environ, 'UV_NO_CONFIG': '1'}
            result = subprocess.run(UV_LOCK_CHECK, capture_output=True, text=True, cwd=scope, env=env)
    except OSError as error:
        auditor.api.emit(
            rule='lockfile-drift',
            variant='uv could not run, so the lockfile was not checked',
            path='uv.lock',
            line=None,
            evidence=error.strerror or type(error).__name__,
            accepted=False,
            accepted_reason=None,
        )
        return
    if result.returncode == 0:
        return

    output = (result.stderr or result.stdout).strip()
    # uv's progress chatter carries a resolution timestamp, and a network
    # failure carries whatever the transport said. Both change between runs, so
    # emitting the raw output made this check report a different evidence
    # string every time on an unchanged tree - see the convergence rules in
    # SKILL.md. Keep only the error lines, with any timestamp masked.
    error_lines = [line.strip() for line in output.splitlines() if line.strip().startswith('error:')]
    evidence = LOCKFILE_TIMESTAMP_RE.sub('<timestamp>', ' '.join(error_lines))[:200]

    # A lockfile that needs regenerating and a lockfile that could not be
    # checked are different facts: the first is drift, the second means the
    # question went unanswered. Reporting both as drift is the
    # failure-versus-absence defect, in the checker rather than in the code
    # under audit.
    if LOCKFILE_DRIFT_MARKER in output:
        variant = 'uv lock --check reports the lockfile is out of date'
        evidence = evidence or 'lockfile needs updating'
    else:
        variant = 'uv lock --check could not verify the lockfile'
        evidence = evidence or 'no error detail on stderr or stdout'

    auditor.api.emit(
        rule='lockfile-drift',
        variant=variant,
        path='uv.lock',
        line=None,
        evidence=evidence,
        accepted=False,
        accepted_reason=None,
    )
