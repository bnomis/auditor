"""The `auditor` command: dispatch to the checker's commands.

    auditor check <scope-root> ...    the mechanical sweep (`auditor.sweep`)
    auditor changed ...               the changed-files runner (`auditor.changed`)
    auditor phaseb <command> ...      the Phase B driver (`auditor.phasebcli`)
    auditor --version                 print the installed version

The remaining arguments go to the chosen command's `main` unchanged.
"""

import importlib.metadata
import sys
import typing

import auditor.changed
import auditor.phasebcli
import auditor.sweep

if typing.TYPE_CHECKING:
    import collections.abc

COMMANDS: dict[str, collections.abc.Callable[[collections.abc.Sequence[str]], int]] = {
    'changed': auditor.changed.main,
    'check': auditor.sweep.main,
    'phaseb': auditor.phasebcli.main,
}
USAGE = f'usage: auditor [--version] {{{",".join(sorted(COMMANDS))}}} ...'


def main(argv: collections.abc.Sequence[str] | None = None) -> int:
    """Run the command `argv` names; 2 for a missing or unknown command."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ['--version']:
        print(f'auditor {importlib.metadata.version("auditor")}')
        return 0
    if not args or args[0] not in COMMANDS:
        print(USAGE, file=sys.stderr)
        if args:
            print(f'auditor: unknown command {args[0]!r}', file=sys.stderr)
        return 2
    return COMMANDS[args[0]](args[1:])
