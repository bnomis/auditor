import re
import subprocess
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib

HOOK_REPO_RE = re.compile(r'^\s*-\s*repo:\s*(\S+)')
HOOK_REV_RE = re.compile(r"""^\s*rev:\s*['"]?([^'"\s#]+)['"]?\s*(#.*)?$""")
PLAIN_VERSION_RE = re.compile(r'^v?(\d+\.\d+\.\d+)$')
FROZEN_RE = re.compile(r'#\s*frozen:\s*(v?\d+\.\d+\.\d+)\s*$')
RUFF_VERSION_OUTPUT_RE = re.compile(r'^ruff (\d+\.\d+\.\d+)')


def ruff_hook_pin(lines: list[str]) -> tuple[int, int | None, str | None] | None:
    """Return (repo line, rev line, pinned version text) for the first
    `ruff-pre-commit` repo entry, or None when the file has none. Line numbers
    are 1-based; the rev line and version are None when they cannot be read."""
    for index, text in enumerate(lines):
        repo = HOOK_REPO_RE.match(text)
        if not repo or not repo.group(1).rstrip('/').removesuffix('.git').rstrip('/').endswith('/ruff-pre-commit'):
            continue
        for rev_index in range(index + 1, len(lines)):
            if HOOK_REPO_RE.match(lines[rev_index]):
                break
            rev = HOOK_REV_RE.match(lines[rev_index])
            if not rev:
                continue
            if PLAIN_VERSION_RE.match(rev.group(1)):
                return index + 1, rev_index + 1, rev.group(1)
            frozen = FROZEN_RE.search(rev.group(2) or '')
            return index + 1, rev_index + 1, frozen.group(1) if frozen else None
        return index + 1, None, None
    return None


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Emit a `ruff-version-drift` hit when the ruff the audit runs (see
    `ruff_executable`) is not the version the project's `ruff-pre-commit` hook
    pins, or when the pin cannot be read.

    Project-level: reads `<scope>/.pre-commit-config.yaml` and runs
    `ruff --version` in `scope`; `src_root` is unused. Silent when the file is
    absent or holds no `ruff-pre-commit` repo. A ruff that cannot run is
    reported as a hit.
    """
    config = scope / '.pre-commit-config.yaml'
    if not config.is_file():
        return
    lines = auditor.api.source_lines(config)
    pin = ruff_hook_pin(lines)
    if pin is None:
        return
    repo_line, rev_line, pinned = pin
    anchor = rev_line or repo_line

    def emit(variant: str, evidence: str) -> None:
        auditor.api.emit(
            rule='ruff-version-drift',
            variant=variant,
            path='.pre-commit-config.yaml',
            line=anchor,
            evidence=evidence,
            accepted=(reason := auditor.api.accept_reason(lines, anchor, rule='ruff-version-drift')) is not None,
            accepted_reason=reason,
        )

    if pinned is None:
        emit('the ruff-pre-commit rev names no version', 'the rev is not a version and has no `# frozen: <version>` comment')
        return
    try:
        ruff, label = auditor.api.ruff_executable(scope)
        # auditme: accept[subprocess-without-memoisation] a PROJECT_CHECKS entry: the driver runs it once per sweep
        result = subprocess.run([ruff, '--version'], capture_output=True, text=True, cwd=scope)
    except OSError as error:
        emit('ruff could not run, so its version was not compared', error.strerror or type(error).__name__)
        return
    running = RUFF_VERSION_OUTPUT_RE.match(result.stdout.strip())
    if not running:
        emit('ruff --version printed no version', result.stdout.strip()[:200])
        return
    if running.group(1) != pinned.removeprefix('v'):
        emit('the ruff the audit runs differs from the ruff-pre-commit rev', f'{label} is {running.group(1)}; the hook pins {pinned}')
