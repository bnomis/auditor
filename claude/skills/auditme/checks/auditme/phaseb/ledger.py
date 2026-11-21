"""Reading, merging and dismissing the verdicts of a question's ledger.

A ledger is a JSON-lines file, one verdict per line sorted by candidate id, so
a diff shows only the verdicts that changed. A ledger that exists but cannot
be read is an error, never an empty ledger: an empty one would re-judge
everything and a later merge would overwrite the real one.
"""

import dataclasses
import datetime
import json
import os
import pathlib
import tempfile

from auditme.phaseb.candidates import Candidate, Verdict
from auditme.phaseb.errors import PhaseBError

REQUIRED = tuple(field.name for field in dataclasses.fields(Verdict) if field.default is dataclasses.MISSING)


@dataclasses.dataclass(frozen=True)
class MergeResult:
    """What a merge did: verdicts written, current ones kept, entries dropped."""

    written: int
    kept: int
    dropped: int


def parse_verdict(record: object, where: str) -> Verdict:
    if not isinstance(record, dict):
        raise PhaseBError(f'{where}: a verdict must be a JSON object')
    missing = [name for name in REQUIRED if name not in record]
    if missing:
        raise PhaseBError(f'{where}: verdict is missing {", ".join(missing)}')
    findings = record['findings']
    if not isinstance(findings, dict) or not all(isinstance(names, list) for names in findings.values()):
        raise PhaseBError(f'{where}: findings must map each kind to a list')
    if not isinstance(record['brief_version'], int) or isinstance(record['brief_version'], bool):
        raise PhaseBError(f'{where}: brief_version must be an integer')
    dismissed = record.get('dismissed')
    if dismissed is not None and not isinstance(dismissed, str):
        raise PhaseBError(f'{where}: dismissed must be a string or null')
    try:
        return Verdict(**{field.name: record[field.name] for field in dataclasses.fields(Verdict) if field.name in record})
    except TypeError as error:
        raise PhaseBError(f'{where}: not a valid verdict') from error


def read_ledger(path: pathlib.Path) -> dict[str, Verdict]:
    """Read a question's ledger, keyed by candidate id; empty if the file is absent.

    Raises:
        PhaseBError: the file exists but cannot be read, or a line is not a valid verdict.
    """
    if not path.exists() and not path.is_symlink():
        return {}
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as error:
        raise PhaseBError(f'cannot read ledger {path}') from error
    verdicts: dict[str, Verdict] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        where = f'{path}:{number}'
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise PhaseBError(f'{where}: not valid JSON') from error
        verdict = parse_verdict(record, where)
        verdicts[verdict.id] = verdict
    return verdicts


def discard_temporary(temporary: str) -> None:
    """Remove a temporary file left by a failed ledger write.

    Raises:
        PhaseBError: the file cannot be removed.
    """
    try:
        pathlib.Path(temporary).unlink(missing_ok=True)
    except OSError as error:
        raise PhaseBError(f'cannot remove temporary file {temporary}') from error


def write_ledger(path: pathlib.Path, verdicts: dict[str, Verdict]) -> None:
    """Write verdicts to path through a temporary file and a rename, so a failure keeps the old file.

    Raises:
        PhaseBError: the ledger cannot be written.
    """
    body = ''.join(json.dumps(dataclasses.asdict(verdicts[key]), sort_keys=True) + '\n' for key in sorted(verdicts))
    temporary: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.', suffix='.tmp')
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            stream.write(body)
        os.replace(temporary, path)
        temporary = None
    except OSError as error:
        raise PhaseBError(f'cannot write ledger {path}') from error
    finally:
        if temporary is not None:
            discard_temporary(temporary)


def merge_verdicts(ledger_path: pathlib.Path, candidates: list[Candidate], verdicts: list[Verdict]) -> MergeResult:
    """Write the new verdicts into the ledger and drop entries whose id is no longer a candidate.

    A new verdict for a dismissed candidate keeps the dismissal only if its
    findings are unchanged. Writes atomically (temporary file, then rename).

    Raises:
        PhaseBError: the ledger cannot be read or written.
    """
    current = read_ledger(ledger_path)
    live = {candidate.id for candidate in candidates}
    merged = {key: verdict for key, verdict in current.items() if key in live}
    dropped = len(current) - len(merged)
    for verdict in verdicts:
        if verdict.id not in live:
            continue
        earlier = current.get(verdict.id)
        if earlier is not None and earlier.dismissed is not None and earlier.findings == verdict.findings:
            verdict = dataclasses.replace(verdict, dismissed=earlier.dismissed)
        merged[verdict.id] = verdict
    new_ids = {verdict.id for verdict in verdicts if verdict.id in live}
    written = len(new_ids)
    kept = len(set(merged) & set(current) - new_ids)
    write_ledger(ledger_path, merged)
    return MergeResult(written=written, kept=kept, dropped=dropped)


def dismiss_verdict(ledger_path: pathlib.Path, candidate_id: str, reason: str, today: str | None = None) -> Verdict:
    """Record that the operator dismissed a candidate's finding, as 'YYYY-MM-DD: reason'.

    Raises:
        PhaseBError: the ledger cannot be read or written, or holds no verdict for candidate_id.
    """
    current = read_ledger(ledger_path)
    if candidate_id not in current:
        raise PhaseBError(f'ledger {ledger_path} holds no verdict for {candidate_id!r}')
    stamp = today or datetime.date.today().isoformat()
    dismissed = dataclasses.replace(current[candidate_id], dismissed=f'{stamp}: {reason}')
    write_ledger(ledger_path, {**current, candidate_id: dismissed})
    return dismissed


__all__ = ['MergeResult', 'dismiss_verdict', 'merge_verdicts', 'read_ledger']
