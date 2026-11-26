import json
import pathlib
import subprocess

import auditor.api


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Emit a `ruff` hit for each `ruff check` finding and each file `ruff format
    --check` would reformat under `src_root`.

    Runs the ruff `ruff_executable` finds, in `scope`. A ruff that cannot run
    is a hit (`ruff not installed`), as is output from either command that is
    not JSON (`ruff-check-parse-error`, `ruff-format-parse-error`). Both commands
    report in ruff's JSON output format, so a file `ruff format` would rewrite
    is a `ruff-format` hit at the path and line ruff names. No accept marker
    applies: fix the code, or silence a `ruff check` line with `# noqa: <code>`.
    """
    ruff, _ = auditor.api.ruff_executable(scope)
    for cmd, variant in (
        ([ruff, 'check', '--output-format=json', str(src_root)], 'ruff-check'),
        ([ruff, 'format', '--check', '--output-format=json', str(src_root)], 'ruff-format'),
    ):
        try:
            # auditme: accept[subprocess-without-memoisation] its arguments differ per root
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=scope)
        except OSError:
            auditor.api.emit(
                rule='ruff',
                variant=variant,
                path=None,
                line=None,
                evidence='ruff not installed',
                accepted=False,
                accepted_reason=None,
            )
            continue
        if not result.stdout.strip():
            continue
        try:
            found = json.loads(result.stdout)
        except json.JSONDecodeError:
            auditor.api.emit(
                rule='ruff', variant=f'{variant}-parse-error', path=None, line=None, evidence=result.stdout[:200], accepted=False, accepted_reason=None
            )
            continue
        for hit in found:
            auditor.api.emit(
                rule='ruff',
                variant=hit.get('code', 'ruff-check') if variant == 'ruff-check' else 'ruff-format',
                path=auditor.api.relpath(pathlib.Path(hit['filename']), scope),
                line=hit['location']['row'],
                evidence=hit.get('message', ''),
                accepted=False,
                accepted_reason=None,
            )
