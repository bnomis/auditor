"""Planning a question's batches and checking a reviewer run's output.

`plan_batches` picks the candidates that need a verdict; `write_plan` writes
them as `batch-NN.jsonl` beside a `plan.json`. A reviewer writes one
`result-NN.jsonl` per batch, one JSON line per candidate with `id`, `missing`,
`extra` and `reason`. `check_run` reports each problem in those results
instead of raising, so the orchestrator can retry the batch.
"""

import dataclasses
import datetime
import json
import pathlib
import typing

from auditme.phaseb.candidates import Candidate, Verdict
from auditme.phaseb.errors import PhaseBError

PLAN_NAME = 'plan.json'


@dataclasses.dataclass(frozen=True)
class RunCheck:
    """The problems found in a run, per batch number, and the batches to retry."""

    problems: dict[int, list[str]]

    @property
    def retry(self) -> list[int]:
        """Batch numbers with at least one problem, in order."""
        return sorted(self.problems)


@dataclasses.dataclass(frozen=True)
class Plan:
    """A written plan: the question, its brief and the candidate ids of each batch."""

    question: str
    brief: str
    brief_version: int
    batches: list[list[str]]


def batch_path(run_dir: pathlib.Path, number: int) -> pathlib.Path:
    return run_dir / f'batch-{number:02d}.jsonl'


def result_path(run_dir: pathlib.Path, number: int) -> pathlib.Path:
    return run_dir / f'result-{number:02d}.jsonl'


def plan_batches(
    candidates: list[Candidate],
    ledger: dict[str, Verdict],
    brief_version: int,
    size: int,
    rejudge: bool = False,
) -> list[list[Candidate]]:
    """Return the candidates needing a verdict, in batches of size, in id order.

    A candidate needs one when the ledger has no verdict for its id, or the
    verdict's hash or brief_version differs from the current one, or rejudge
    is set.

    Raises:
        PhaseBError: size is not a positive number.
    """
    if size < 1:
        raise PhaseBError(f'batch size must be at least 1, not {size}')
    needed = []
    for candidate in sorted(candidates, key=lambda item: item.id):
        verdict = ledger.get(candidate.id)
        current = verdict is not None and verdict.hash == candidate.hash and verdict.brief_version == brief_version
        if rejudge or not current:
            needed.append(candidate)
    return [needed[start : start + size] for start in range(0, len(needed), size)]


def write_plan(question: str, brief: pathlib.Path, brief_version: int, planned: list[list[Candidate]], run_dir: pathlib.Path) -> None:
    """Write each batch as batch-NN.jsonl and the plan as plan.json in run_dir.

    Raises:
        PhaseBError: a file cannot be written.
    """
    document = {
        'question': question,
        'brief': str(brief),
        'brief_version': brief_version,
        'batches': [[candidate.id for candidate in batch] for batch in planned],
    }
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        for number, batch in enumerate(planned, start=1):
            body = ''.join(json.dumps(dataclasses.asdict(candidate), sort_keys=True) + '\n' for candidate in batch)
            batch_path(run_dir, number).write_text(body, encoding='utf-8')
        (run_dir / PLAN_NAME).write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8')
    except OSError as error:
        raise PhaseBError(f'cannot write plan in {run_dir}: {error}') from error


def read_plan(run_dir: pathlib.Path) -> Plan:
    """Read run_dir's plan.json.

    Raises:
        PhaseBError: the plan is absent, cannot be read or is not a valid plan.
    """
    path = run_dir / PLAN_NAME
    try:
        document = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError) as error:
        raise PhaseBError(f'cannot read plan {path}: {error}') from error
    except json.JSONDecodeError as error:
        raise PhaseBError(f'{path}: not valid JSON: {error}') from error
    try:
        planned = document['batches']
        valid = (
            isinstance(document['question'], str)
            and isinstance(document['brief'], str)
            and isinstance(document['brief_version'], int)
            and isinstance(planned, list)
            and all(isinstance(batch, list) and all(isinstance(item, str) for item in batch) for batch in planned)
        )
    except (KeyError, TypeError) as error:
        raise PhaseBError(f'{path}: not a valid plan: {error!r}') from error
    if not valid:
        raise PhaseBError(f'{path}: not a valid plan')
    return Plan(document['question'], document['brief'], document['brief_version'], planned)


def parse_result(line: str) -> dict[str, typing.Any]:
    """Parse one result line, returning the record.

    Raises:
        ValueError: the line is not a JSON object with the expected fields.
    """
    record = json.loads(line)
    if not isinstance(record, dict):
        raise ValueError('not a JSON object')
    if not isinstance(record.get('id'), str):
        raise ValueError('id must be a string')
    for key in ('missing', 'extra'):
        names = record.get(key)
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            raise ValueError(f'{key} must be a list of strings')
    if not isinstance(record.get('reason'), str):
        raise ValueError('reason must be a string')
    return record


def check_batch(run_dir: pathlib.Path, number: int, ids: list[str]) -> tuple[list[str], list[dict[str, typing.Any]]]:
    """Return a batch's problems and its valid result records."""
    path = result_path(run_dir, number)
    if not path.is_file():
        return [f'no output file {path.name}'], []
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as error:
        return [f'unreadable output {path.name}: {error}'], []
    problems: list[str] = []
    records: list[dict[str, typing.Any]] = []
    seen: set[str] = set()
    expected = set(ids)
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = parse_result(line)
        except ValueError as error:
            problems.append(f'unparseable line {line_number} in {path.name}: {error}')
            continue
        found = str(record['id'])
        if found not in expected:
            problems.append(f'unexpected id {found} in {path.name}')
        elif found in seen:
            problems.append(f'duplicate id {found} in {path.name}')
        else:
            seen.add(found)
            records.append(record)
    problems.extend(f'missing id {found} in {path.name}' for found in ids if found not in seen)
    return problems, records


def check_run(run_dir: pathlib.Path) -> RunCheck:
    """Check every planned batch has exactly one valid verdict per candidate.

    Returns the problems per batch (no output, unparseable line, missing,
    duplicate or unexpected id) and the batches to retry; a reviewer's
    malformed output is reported, not raised.

    Raises:
        PhaseBError: the plan cannot be read.
    """
    plan = read_plan(run_dir)
    problems: dict[int, list[str]] = {}
    for number, ids in enumerate(plan.batches, start=1):
        found, _ = check_batch(run_dir, number, ids)
        if found:
            problems[number] = found
    return RunCheck(problems=problems)


def read_run_verdicts(run_dir: pathlib.Path, candidates: list[Candidate], today: str | None = None) -> list[Verdict]:
    """Turn a checked run's results into verdicts, sorted by id.

    Each verdict carries its candidate's current hash, the plan's brief
    version and today's date.

    Raises:
        PhaseBError: the plan cannot be read, the run has problems, or a
            planned id is not among candidates.
    """
    plan = read_plan(run_dir)
    problems = check_run(run_dir).problems
    if problems:
        raise PhaseBError(f'run in {run_dir} has problems in batches {sorted(problems)}; run check and retry them')
    by_id = {candidate.id: candidate for candidate in candidates}
    stamp = today or datetime.date.today().isoformat()
    verdicts: list[Verdict] = []
    for number, ids in enumerate(plan.batches, start=1):
        _, records = check_batch(run_dir, number, ids)
        for record in records:
            candidate = by_id.get(str(record['id']))
            if candidate is None:
                raise PhaseBError(f'planned id {record["id"]} is no longer a candidate; plan again')
            verdicts.append(
                Verdict(
                    question=plan.question,
                    id=candidate.id,
                    hash=candidate.hash,
                    brief_version=plan.brief_version,
                    findings={'missing': sorted(record['missing']), 'extra': sorted(record['extra'])},
                    reason=str(record['reason']),
                    judged=stamp,
                )
            )
    return sorted(verdicts, key=lambda verdict: verdict.id)


__all__ = ['Plan', 'RunCheck', 'check_run', 'plan_batches', 'read_plan', 'read_run_verdicts', 'write_plan']
