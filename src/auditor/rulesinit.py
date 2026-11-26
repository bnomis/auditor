"""Create a new rules repository from the default rule catalogue.

`write_selection` writes the editable list of catalogue rules, grouped by pack.
"""

import importlib.resources
import pathlib
import tomllib
import typing

if typing.TYPE_CHECKING:
    import collections.abc

SELECTION = 'selection.txt'
REPOSITORY_ENTRIES = ('auditor-rules.toml', 'rules')


class RulesInitError(Exception):
    """A rules repository cannot be created; the message is the error text."""


def catalogue_root() -> pathlib.Path:
    """Return the directory that holds the catalogue's `packs.toml` and `rules/`."""
    return pathlib.Path(str(importlib.resources.files('auditor') / 'catalogue'))


def read_packs() -> dict[str, dict[str, typing.Any]]:
    """Return the pack table of the catalogue's `packs.toml`, keyed by pack name."""
    text = (catalogue_root() / 'packs.toml').read_text(encoding='utf-8')
    return dict(tomllib.loads(text)['packs'])


def rule_title(name: str) -> str:
    """Return the `title` of catalogue rule `name`."""
    meta = tomllib.loads((catalogue_root() / 'rules' / name / 'rule.toml').read_text(encoding='utf-8'))
    return str(meta['title'])


def write_selection(dest: pathlib.Path, packs: collections.abc.Sequence[str]) -> pathlib.Path:
    """Write `dest/selection.txt`: every catalogue rule under its pack heading.

    Rules of the chosen packs are written as bare lines. Rules of the other
    packs are written commented out (`# <rule-dir>`), so the user can add one
    by removing the `#`. With no packs given, every pack is chosen.

    Raises:
        RulesInitError: an unknown pack, or `dest` already holds `rules/` or `auditor-rules.toml`.
    """
    table = read_packs()
    unknown = [name for name in packs if name not in table]
    if unknown:
        raise RulesInitError(f"unknown pack '{unknown[0]}': known packs are {', '.join(sorted(table))}")
    for entry in REPOSITORY_ENTRIES:
        if (dest / entry).exists():
            raise RulesInitError(f'{dest / entry} already exists: rules init creates a new repository; edit the existing one by hand')
    chosen = set(packs) or set(table)
    lines = [
        '# One rule directory name per line. Comment a line out with # to leave that rule out.',
        '# Remove the # from a commented rule to add it.',
        '',
    ]
    for name in sorted(table):
        lines.append(f'## {name}: {table[name]["description"]}')
        prefix = '' if name in chosen else '# '
        lines.extend(f'{prefix}{rule}  # {rule_title(rule)}' for rule in table[name]['rules'])
        lines.append('')
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / SELECTION
    path.write_text('\n'.join(lines), encoding='utf-8')
    return path
