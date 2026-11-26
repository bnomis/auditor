"""The `auditor rules` commands: report on the rules repository `$AUDITOR_RULES_PATH` names.

    auditor rules list [--kind K]
    auditor rules check
    auditor rules standards
    auditor rules questions [--category C]
    auditor rules pending

A `RulesRepoError` goes to stderr as `ERROR: <message>`, with exit status 2
and nothing on stdout.
"""

import argparse
import ast
import re
import sys
import typing

import auditor.core
import auditor.rulesrepo

if typing.TYPE_CHECKING:
    import collections.abc
    import pathlib

PENDING_HEADING = re.compile(r'##\s+\S')
FENCE = re.compile(r'\s*(```|~~~)')
RULE_FILES = ('check.py', 'lister.py')
HELPER_MODULE = 'api'
HELPER_PACKAGE = f'auditor.{HELPER_MODULE}'


def read_prose(rule: auditor.rulesrepo.Rule) -> str:
    return (rule.path / 'rule.md').read_text(encoding='utf-8').rstrip('\n')


def describe(rule: auditor.rulesrepo.Rule) -> str:
    emits = rule.meta.get('emits')
    label = ','.join(typing.cast('list[str]', emits)) if emits else str(rule.meta.get('id', rule.name))
    return f'{rule.name}\t{rule.kind}\t{label}\t{rule.meta["title"]}'


def run_list(repo: auditor.rulesrepo.RulesRepo, args: argparse.Namespace) -> int:
    for rule in repo.rules:
        if args.kind is None or rule.kind == args.kind:
            print(describe(rule))
    return 0


def foreign_imports(path: pathlib.Path) -> list[str]:
    """Return one problem line for each `auditor.<x>` import in `path` where `<x>` is not `api`."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except (OSError, SyntaxError, ValueError) as error:
        # auditme: accept[except-interpolation] the problem line carries the described error once
        return [f'{path}: cannot be parsed as Python: {auditor.core.describe_error(error)}']
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif node.level == 0 and node.module is not None:
            names = [f'{node.module}.{alias.name}' for alias in node.names] if node.module == 'auditor' else [node.module]
        for name in names:
            parts = name.split('.')
            if parts[0] == 'auditor' and (len(parts) < 2 or parts[1] != HELPER_MODULE):
                problems.append(f'{path}:{node.lineno}: imports {name}: import {HELPER_PACKAGE} only')
    return problems


def run_check(repo: auditor.rulesrepo.RulesRepo, args: argparse.Namespace) -> int:
    del args
    problems: list[str] = []
    for rule in repo.rules:
        for filename in RULE_FILES:
            path = rule.path / filename
            if not path.is_file():
                continue
            try:
                auditor.rulesrepo.import_entry(rule, filename)
            except auditor.rulesrepo.RulesRepoError as error:
                problems.append(auditor.core.describe_error(error))
            # auditme: accept[silent-broad-except] reporting a rule that raises on import as a problem is the handler's job
            except Exception as error:  # noqa: BLE001 - a rule's own code may raise anything
                # auditme: accept[except-interpolation] the problem line carries the described error once
                problems.append(f'rules/{rule.name}/{filename}: raises on import: {auditor.core.describe_error(error)}')
            problems.extend(foreign_imports(path))
    for problem in problems:
        print(problem)
    return 1 if problems else 0


def run_standards(repo: auditor.rulesrepo.RulesRepo, args: argparse.Namespace) -> int:
    del args
    print('\n\n'.join(read_prose(rule) for rule in repo.rules if rule.kind == 'standard'))
    return 0


def run_questions(repo: auditor.rulesrepo.RulesRepo, args: argparse.Namespace) -> int:
    questions = [rule for rule in repo.rules if rule.kind == 'question' and (args.category is None or rule.meta['category'] == args.category)]
    print('\n\n'.join(f'## {rule.meta["id"]}: {rule.meta["title"]}\n\n{read_prose(rule)}' for rule in questions))
    return 0


def pending_headings(text: str) -> list[str]:
    """Return each `## ` heading of `text` outside a fenced code block."""
    headings: list[str] = []
    fenced = False
    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced and PENDING_HEADING.match(line):
            headings.append(line.strip())
    return headings


def run_pending(repo: auditor.rulesrepo.RulesRepo, args: argparse.Namespace) -> int:
    del args
    todo = repo.root / 'TODO.md'
    if not todo.is_file():
        return 0
    headings = pending_headings(todo.read_text(encoding='utf-8'))
    for heading in headings:
        print(heading)
    return 1 if headings else 0


COMMANDS: dict[str, collections.abc.Callable[[auditor.rulesrepo.RulesRepo, argparse.Namespace], int]] = {
    'check': run_check,
    'list': run_list,
    'pending': run_pending,
    'questions': run_questions,
    'standards': run_standards,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='auditor rules',
        description='Report on the rules repository $AUDITOR_RULES_PATH names.',
    )
    commands = parser.add_subparsers(
        dest='command',
        required=True,
    )
    listing = commands.add_parser(
        'list',
        help='one line per rule: name, kind, emits or id, title',
    )
    listing.add_argument(
        '--kind',
        choices=auditor.rulesrepo.KINDS,
        help='list only rules of this kind',
    )
    commands.add_parser(
        'check',
        help='import every entry file and report imports outside the helper API package',
    )
    commands.add_parser(
        'standards',
        help="print every standard rule's rule.md, in name order",
    )
    questions = commands.add_parser(
        'questions',
        help='print the Phase B checklist',
    )
    questions.add_argument(
        '--category',
        choices=auditor.rulesrepo.CATEGORIES,
        help='print only questions of this category',
    )
    commands.add_parser(
        'pending',
        help='list the open items of TODO.md; exit 1 when there is one',
    )
    return parser


def main(argv: collections.abc.Sequence[str] | None = None) -> int:
    """Run one `rules` command; 2 for an invalid or missing rules repository."""
    args = build_parser().parse_args(argv)
    try:
        repo = auditor.rulesrepo.load(auditor.rulesrepo.rules_root())
    except auditor.rulesrepo.RulesRepoError as error:
        # auditme: accept[except-interpolation] the entry point prints the message and its chained cause once
        print(f'ERROR: {auditor.core.describe_error(error)}', file=sys.stderr)
        return 2
    return COMMANDS[args.command](repo, args)
