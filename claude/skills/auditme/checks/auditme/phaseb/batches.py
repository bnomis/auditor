"""Planning a question's batches and checking a reviewer run's output.

`plan_batches` picks the candidates that need a verdict; `write_plan` writes
them as `batch-NN.jsonl` beside a `plan.json`. A reviewer writes one
`result-NN.jsonl` per batch, one JSON line per candidate with `id`,
`findings` (one list of strings per kind registered for the question) and
`reason`. `read_run_check` reports each problem in those results
instead of raising, so the orchestrator can retry the batch.
"""

import dataclasses
import datetime
import json
import typing

import auditme.phaseb.errors
from auditme.phaseb.candidates import (
    DEFAULT_DEPTH,
    Candidate,
    Verdict,
    question_kinds,
)  # auditme: accept[from-import] the package init imports this module while `auditme.phaseb` is not yet bound on `auditme`, so a qualified path fails at import

if typing.TYPE_CHECKING:
    import pathlib

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
    depth: int = DEFAULT_DEPTH


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
        raise auditme.phaseb.errors.PhaseBError(f'batch size must be at least 1, not {size}')
    needed = []
    for candidate in sorted(candidates, key=lambda item: item.id):
        verdict = ledger.get(candidate.id)
        current = verdict is not None and verdict.hash == candidate.hash and verdict.brief_version == brief_version
        if rejudge or not current:
            needed.append(candidate)
    return [needed[start : start + size] for start in range(0, len(needed), size)]


def batch_line(candidate: Candidate, ledger: dict[str, Verdict]) -> dict[str, typing.Any]:
    """Return a candidate's batch line: its fields, and `earlier` when the ledger holds a verdict for it."""
    line: dict[str, typing.Any] = dataclasses.asdict(candidate)
    verdict = ledger.get(candidate.id)
    if verdict is not None:
        line['earlier'] = {
            'findings': verdict.findings,
            'reason': verdict.reason,
            'brief_version': verdict.brief_version,
            'judged': verdict.judged,
        }
    return line


def write_plan(
    question: str,
    brief: pathlib.Path,
    brief_version: int,
    planned: list[list[Candidate]],
    run_dir: pathlib.Path,
    depth: int = DEFAULT_DEPTH,
    ledger: dict[str, Verdict] | None = None,
) -> None:
    """Write each batch as batch-NN.jsonl and the plan as plan.json in run_dir.

    The plan records the callee `depth` the candidates were listed at, so a
    merge can refuse to re-list at another. A candidate the `ledger` already
    holds a verdict for carries it as `earlier` (`findings`, `reason`,
    `brief_version`, `judged`) so its reviewer sees what it last was judged;
    `check` and `merge` ignore the field.

    Raises:
        PhaseBError: a file cannot be written.
    """
    document = {
        'question': question,
        'brief': str(brief),
        'brief_version': brief_version,
        'depth': depth,
        'batches': [[candidate.id for candidate in batch] for batch in planned],
    }
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        for number, batch in enumerate(planned, start=1):
            body = ''.join(json.dumps(batch_line(candidate, ledger or {}), sort_keys=True) + '\n' for candidate in batch)
            batch_path(run_dir, number).write_text(body, encoding='utf-8')
        (run_dir / PLAN_NAME).write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8')
    except OSError as error:
        raise auditme.phaseb.errors.PhaseBError(f'cannot write plan in {run_dir}') from error


def read_plan(run_dir: pathlib.Path) -> Plan:
    """Read run_dir's plan.json.

    A plan written before it recorded its depth is read as the default depth, 3.

    Raises:
        PhaseBError: the plan is absent, cannot be read or is not a valid plan.
    """
    path = run_dir / PLAN_NAME
    try:
        document = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError) as error:
        raise auditme.phaseb.errors.PhaseBError(f'cannot read plan {path}') from error
    except json.JSONDecodeError as error:
        raise auditme.phaseb.errors.PhaseBError(f'{path}: not valid JSON') from error
    try:
        planned = document['batches']
        valid = (
            isinstance(document['question'], str)
            and isinstance(document['brief'], str)
            and isinstance(document['brief_version'], int)
            and isinstance(document.get('depth', DEFAULT_DEPTH), int)
            and isinstance(planned, list)
            and all(isinstance(batch, list) and all(isinstance(item, str) for item in batch) for batch in planned)
        )
    except (KeyError, TypeError) as error:
        raise auditme.phaseb.errors.PhaseBError(f'{path}: not a valid plan') from error
    if not valid:
        raise auditme.phaseb.errors.PhaseBError(f'{path}: not a valid plan')
    return Plan(document['question'], document['brief'], document['brief_version'], planned, document.get('depth', DEFAULT_DEPTH))


def parse_result(line: str, kinds: tuple[str, ...]) -> dict[str, typing.Any]:
    """Parse one result line against a question's finding kinds, returning the record.

    Raises:
        ValueError: the line is not a JSON object of exactly `id`, `findings`
            and `reason`, or `findings` is not one list of strings per kind.
    """
    record = json.loads(line)
    if not isinstance(record, dict):
        # auditme: accept[layer-has-domain-error-raises-stdlib] it validates one result line as `json.loads` does; both land in one `except ValueError` that records a problem
        raise ValueError('not a JSON object')
    if set(record) != {'id', 'findings', 'reason'}:
        # auditme: accept[layer-has-domain-error-raises-stdlib] it validates one result line as `json.loads` does; both land in one `except ValueError` that records a problem
        raise ValueError('keys must be exactly id, findings and reason')
    if not isinstance(record['id'], str):
        # auditme: accept[layer-has-domain-error-raises-stdlib] it validates one result line as `json.loads` does; both land in one `except ValueError` that records a problem
        raise ValueError('id must be a string')
    findings = record['findings']
    if not isinstance(findings, dict) or set(findings) != set(kinds):
        # auditme: accept[layer-has-domain-error-raises-stdlib] it validates one result line as `json.loads` does; both land in one `except ValueError` that records a problem
        raise ValueError(f'findings must have exactly the kinds {list(kinds)}')
    for kind, names in findings.items():
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            # auditme: accept[layer-has-domain-error-raises-stdlib] it validates one result line as `json.loads` does; both land in one `except ValueError` that records a problem
            raise ValueError(f'findings {kind} must be a list of strings')
    if not isinstance(record['reason'], str):
        # auditme: accept[layer-has-domain-error-raises-stdlib] it validates one result line as `json.loads` does; both land in one `except ValueError` that records a problem
        raise ValueError('reason must be a string')
    return record


def read_batch_check(run_dir: pathlib.Path, number: int, ids: list[str], kinds: tuple[str, ...]) -> tuple[list[str], list[dict[str, typing.Any]]]:
    """Return a batch's problems and its valid result records."""
    path = result_path(run_dir, number)
    if not path.is_file():
        return [f'no output file {path.name}'], []
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as error:
        # auditme: accept[except-interpolation] the text is a problem reported to the user, not a raised exception
        return [f'unreadable output {path.name}: {error}'], []
    problems: list[str] = []
    records: list[dict[str, typing.Any]] = []
    seen: set[str] = set()
    expected = set(ids)
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = parse_result(line, kinds)
        except ValueError as error:
            # auditme: accept[except-interpolation] the text is a problem reported to the user, not a raised exception
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


def read_run_check(run_dir: pathlib.Path) -> RunCheck:
    """Check every planned batch has exactly one valid verdict per candidate.

    Returns the problems per batch (no output, unparseable line, missing,
    duplicate or unexpected id) and the batches to retry; a reviewer's
    malformed output is reported, not raised.

    Raises:
        PhaseBError: the plan cannot be read or names an unregistered question.
    """
    plan = read_plan(run_dir)
    kinds = question_kinds(plan.question)
    problems: dict[int, list[str]] = {}
    for number, ids in enumerate(plan.batches, start=1):
        found, _ = read_batch_check(run_dir, number, ids, kinds)
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
    problems = read_run_check(run_dir).problems
    if problems:
        raise auditme.phaseb.errors.PhaseBError(f'run in {run_dir} has problems in batches {sorted(problems)}; run check and retry them')
    kinds = question_kinds(plan.question)
    by_id = {candidate.id: candidate for candidate in candidates}
    stamp = today or datetime.date.today().isoformat()
    verdicts: list[Verdict] = []
    for number, ids in enumerate(plan.batches, start=1):
        _, records = read_batch_check(run_dir, number, ids, kinds)
        for record in records:
            candidate = by_id.get(str(record['id']))
            if candidate is None:
                raise auditme.phaseb.errors.PhaseBError(f'planned id {record["id"]} is no longer a candidate; plan again')
            verdicts.append(
                Verdict(
                    question=plan.question,
                    id=candidate.id,
                    hash=candidate.hash,
                    brief_version=plan.brief_version,
                    findings={kind: sorted(record['findings'][kind]) for kind in kinds},
                    reason=str(record['reason']),
                    judged=stamp,
                )
            )
    return sorted(verdicts, key=lambda verdict: verdict.id)


__all__ = ['Plan', 'RunCheck', 'plan_batches', 'read_plan', 'read_run_check', 'read_run_verdicts', 'write_plan']
