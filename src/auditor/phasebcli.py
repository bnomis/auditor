"""Phase B driver: list, plan, check, merge, report and dismiss a listed question.

Usage (run from anywhere; <root> is the project root):
    auditor phaseb candidates <root> --question A4 [--depth 3]
    auditor phaseb plan <root> --question A4 --out <dir> [--batch-size N] [--depth 3] [--rejudge]
    auditor phaseb check <dir>
    auditor phaseb merge <root> --question A4 <dir> [--depth 3]
    auditor phaseb report <root> --question A4 [--depth 3]
    auditor phaseb dismiss <root> --question A4 <id> --reason <text>

`candidates` prints one JSON line per candidate. `plan` writes the batches the
ledger does not already answer, and `plan.json`. `check` exits 1 when any batch
has a problem, naming it. `merge` writes the verified results into
`<root>/agents/audit-reviews/ledger/<question>.jsonl`. `report` prints the
open findings, new (judged in the latest merge) and carried. A `PhaseBError`
message goes to stderr and the exit status is 2, as it is for a `<root>` that is
not a directory.
"""

import argparse
import dataclasses
import json
import pathlib
import sys
import typing

import auditor.core
import auditor.phaseb
import auditor.phaseb.batches
import auditor.phaseb.candidates
import auditor.rulesrepo

if typing.TYPE_CHECKING:
    import collections.abc

LEDGER_PARTS = ('agents', 'audit-reviews', 'ledger')


def ledger_path(root: pathlib.Path, question: str) -> pathlib.Path:
    return root.joinpath(*LEDGER_PARTS, f'{question}.jsonl')


def project_root(value: str) -> pathlib.Path:
    """Return `value` as a path if it is a directory.

    Raises:
        argparse.ArgumentTypeError: the path does not exist or is not a directory.
    """
    path = pathlib.Path(value)
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f'{path} is not a directory')
    return path


def registered_question(value: str) -> str:
    """Return `value` if a lister is registered for it, so it can build a ledger path.

    Raises:
        argparse.ArgumentTypeError: no lister is registered for the question.
    """
    known = auditor.phaseb.registered_questions()
    if value not in known:
        raise argparse.ArgumentTypeError(f'not a registered question: {value!r}; known: {known}')
    return value


def add_question(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        '--question',
        required=True,
        type=registered_question,
        help='The Phase B question, e.g. A4',
    )


def positive_int(value: str) -> int:
    """Return `value` as an integer of at least 1.

    Raises:
        argparse.ArgumentTypeError: value is not an integer, or is below 1.
    """
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f'not an integer: {value!r}') from None
    if number < 1:
        raise argparse.ArgumentTypeError(f'must be at least 1: {value!r}')
    return number


def add_depth(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        '--depth',
        type=positive_int,
        default=None,
        help='How far callees are followed, at least 1; only for the questions that follow callees (default 3)',
    )


# auditme: accept[duplicate-call-sequence] both parsers are argparse builders that add subcommands and arguments
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Phase B driver for listed audit questions.',
    )
    commands = parser.add_subparsers(
        dest='command',
        required=True,
    )

    candidates = commands.add_parser(
        'candidates',
        help='Print every candidate as a JSON line',
    )
    candidates.add_argument(
        'root',
        type=project_root,
    )
    add_question(candidates)
    add_depth(candidates)

    plan = commands.add_parser(
        'plan',
        help='Write the batches that need a verdict',
    )
    plan.add_argument(
        'root',
        type=project_root,
    )
    add_question(plan)
    add_depth(plan)
    plan.add_argument(
        '--out',
        type=pathlib.Path,
        required=True,
        help='Directory to write batch-NN.jsonl and plan.json into',
    )
    plan.add_argument(
        '--batch-size',
        type=int,
        default=None,
        help="Candidates per reviewer (default: the question's registered batch size)",
    )
    plan.add_argument(
        '--rejudge',
        action='store_true',
        help='Plan every candidate, ignoring the ledger',
    )

    check = commands.add_parser(
        'check',
        help='Check a run; exit 1 on any problem',
    )
    check.add_argument(
        'run_dir',
        type=pathlib.Path,
        metavar='dir',
    )

    merge = commands.add_parser(
        'merge',
        help="Merge a checked run into the project's ledger",
    )
    merge.add_argument(
        'root',
        type=project_root,
    )
    add_question(merge)
    add_depth(merge)
    merge.add_argument(
        'run_dir',
        type=pathlib.Path,
        metavar='dir',
    )

    report = commands.add_parser(
        'report',
        help='Print the open findings, new and carried',
    )
    report.add_argument(
        'root',
        type=project_root,
    )
    add_question(report)
    add_depth(report)

    dismiss = commands.add_parser(
        'dismiss',
        help="Record the operator's dismissal of a finding",
    )
    dismiss.add_argument(
        'root',
        type=project_root,
    )
    add_question(dismiss)
    dismiss.add_argument(
        'candidate_id',
        metavar='id',
    )
    dismiss.add_argument(
        '--reason',
        required=True,
        help='Why the finding is dismissed',
    )
    return parser


def run_candidates(args: argparse.Namespace) -> int:
    for candidate in auditor.phaseb.list_candidates(args.question, args.root, args.depth):
        print(json.dumps(dataclasses.asdict(candidate), sort_keys=True))
    return 0


def depth_of(args: argparse.Namespace) -> int:
    """The callee depth the command runs at: its `--depth`, else the default."""
    return auditor.phaseb.DEFAULT_DEPTH if args.depth is None else args.depth


def run_plan(args: argparse.Namespace) -> int:
    brief = auditor.phaseb.question_brief(args.question)
    version = auditor.phaseb.brief_version(brief)
    found = auditor.phaseb.list_candidates(args.question, args.root, args.depth)
    ledger = auditor.phaseb.read_ledger(ledger_path(args.root, args.question))
    size = auditor.phaseb.question_batch_size(args.question) if args.batch_size is None else args.batch_size
    planned = auditor.phaseb.batches.plan_batches(found, ledger, version, size, args.rejudge)
    count = sum(len(batch) for batch in planned)
    auditor.phaseb.batches.write_plan(args.question, brief, version, planned, args.out, depth_of(args), ledger)
    print(f'{count} planned in {len(planned)} batches, {len(found) - count} reused (brief version {version}) in {args.out}')
    return 0


def run_check(args: argparse.Namespace) -> int:
    result = auditor.phaseb.batches.read_run_check(args.run_dir)
    for number in result.retry:
        for problem in result.problems[number]:
            print(f'batch {number}: {problem}')
    if result.retry:
        print(f'retry batches: {", ".join(str(number) for number in result.retry)}')
        return 1
    print('all batches complete')
    return 0


def run_merge(args: argparse.Namespace) -> int:
    plan = auditor.phaseb.batches.read_plan(args.run_dir)
    if plan.question != args.question:
        raise auditor.phaseb.PhaseBError(f'the run in {args.run_dir} is for question {plan.question!r}, not {args.question!r}')
    if depth_of(args) != plan.depth:
        raise auditor.phaseb.PhaseBError(
            f'the run in {args.run_dir} was planned at depth {plan.depth}, not {depth_of(args)}: merge with --depth {plan.depth}, or plan again at depth {depth_of(args)}'
        )
    found = auditor.phaseb.list_candidates(args.question, args.root, args.depth)
    verdicts = auditor.phaseb.batches.read_run_verdicts(args.run_dir, found)
    path = ledger_path(args.root, args.question)
    result = auditor.phaseb.merge_verdicts(path, found, verdicts)
    print(f'{result.written} written, {result.kept} kept, {result.dropped} dropped in {path}')
    return 0


def run_report(args: argparse.Namespace) -> int:
    found = {candidate.id for candidate in auditor.phaseb.list_candidates(args.question, args.root, args.depth)}
    ledger = auditor.phaseb.read_ledger(ledger_path(args.root, args.question))
    latest = max((verdict.judged for verdict in ledger.values()), default='')
    open_findings = [verdict for key, verdict in sorted(ledger.items()) if key in found and verdict.flagged]
    for verdict in open_findings:
        label = 'new' if verdict.judged == latest else 'carried'
        names = '; '.join(f'{kind} {", ".join(names)}' for kind, names in sorted(verdict.findings.items()) if names)
        print(f'{label} {verdict.id}: {names} - {verdict.reason}')
    print(f'{len(open_findings)} open findings')
    return 0


def run_dismiss(args: argparse.Namespace) -> int:
    verdict = auditor.phaseb.dismiss_verdict(ledger_path(args.root, args.question), args.candidate_id, args.reason)
    print(f'dismissed {verdict.id}: {verdict.dismissed}')
    return 0


COMMANDS = {
    'candidates': run_candidates,
    'check': run_check,
    'dismiss': run_dismiss,
    'merge': run_merge,
    'plan': run_plan,
    'report': run_report,
}


def main(argv: collections.abc.Sequence[str] | None = None) -> int:
    try:
        auditor.phaseb.candidates.use_rules_repository()
    except (auditor.rulesrepo.RulesRepoError, auditor.phaseb.PhaseBError) as error:
        # auditme: accept[except-interpolation] the entry point prints the message and its chained cause once
        print(f'phaseb.py: {auditor.core.describe_error(error)}', file=sys.stderr)
        return 2
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, 'depth', None) is not None and args.question not in auditor.phaseb.depth_questions():
        parser.error(f'--depth is only for the questions {auditor.phaseb.depth_questions()}, not {args.question}')
    try:
        return COMMANDS[args.command](args)
    except auditor.phaseb.PhaseBError as error:
        # auditme: accept[except-interpolation] the entry point prints the message and its chained cause once
        print(f'phaseb.py: {auditor.core.describe_error(error)}', file=sys.stderr)
        return 2
    except auditor.core.RootsError as error:
        # auditme: accept[except-interpolation] the entry point prints the message and its chained cause once
        print(f'ERROR: {auditor.core.describe_error(error)}', file=sys.stderr)
        return 2
