"""Create a new rules repository from the default rule catalogue.

`write_selection` writes the editable list of catalogue rules, grouped by pack.
"""

import datetime
import importlib.metadata
import importlib.resources
import pathlib
import shutil
import subprocess
import tomllib
import typing

import auditor.rulesrepo

if typing.TYPE_CHECKING:
    import collections.abc

SELECTION = 'selection.txt'
TODO_HEADER = """# TODO

Open work only, in implementation order, nearest first. Finished items move to
`DONE.md` unchanged.
"""
DONE_HEADER = """# DONE

Finished work, chronological, newest last. An item moves here from `TODO.md`
unchanged, followed by a `Done:` line. Never file a new item here.
"""
README = """# Rules repository

The rules `auditor` applies. Each directory under `rules/` is one rule: a
`rule.toml`, a `rule.md` and, for a check, a `check.py` with its `tests/`.
`selection.txt` records which catalogue rules this repository started from.

## Use it

Point a project at this repository in its `.envrc`:

```shell
export AUDITOR_RULES_PATH=<path to this directory>
```

## Add or change a rule

Add a directory under `rules/` holding `rule.toml`, `rule.md` and, for a check,
`check.py`. Then run:

```shell
auditor rules check
auditor rules test
```

`auditor rules pending` exits 1 while `TODO.md` holds an open item.
"""
GITIGNORE = '__pycache__/\n'
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


def read_selection(path: pathlib.Path) -> list[str]:
    """Return the rule names `path` lists, each validated against the catalogue.

    Raises:
        RulesInitError: a line names a rule the catalogue does not hold.
    """
    rules_dir = catalogue_root() / 'rules'
    names: list[str] = []
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        name = line.split('#', 1)[0].strip()
        if not name:
            continue
        if not (rules_dir / name / 'rule.toml').is_file():
            raise RulesInitError(f"{SELECTION} line {number}: no catalogue rule '{name}'")
        if name not in names:
            names.append(name)
    return names


def require_standards(names: collections.abc.Sequence[str]) -> None:
    """Refuse a selected rule whose `standards` name a standard that is not selected.

    Raises:
        RulesInitError: a standard that a selected rule names is not in `names`.
    """
    for name in names:
        meta = tomllib.loads((catalogue_root() / 'rules' / name / 'rule.toml').read_text(encoding='utf-8'))
        for standard in meta.get('standards', []):
            if standard not in names:
                raise RulesInitError(f"rule '{name}' needs standard '{standard}', which is not selected")


def catalogue_commit() -> str | None:
    """Return the git commit of the catalogue when this package runs from the auditor work tree, else None."""
    root = catalogue_root().resolve()
    top = auditor.rulesrepo.run_git(root, 'rev-parse', '--show-toplevel')
    if top is None or (pathlib.Path(top.strip()) / 'src' / 'auditor' / 'catalogue').resolve() != root:
        return None
    commit = auditor.rulesrepo.run_git(root, 'rev-parse', 'HEAD')
    return commit.strip() if commit else None


def manifest_text() -> str:
    """Return the text of `auditor-rules.toml`: the API version and where the rules came from."""
    api = auditor.rulesrepo.API_VERSION
    lines = [f'api = "{api[0]}.{api[1]}"', '', '[source]', f'auditor = "{importlib.metadata.version("auditor")}"']
    commit = catalogue_commit()
    if commit:
        lines.append(f'commit = "{commit}"')
    lines.append(f'date = "{datetime.datetime.now(tz=datetime.UTC).date().isoformat()}"')
    return '\n'.join(lines) + '\n'


def apply_selection(dest: pathlib.Path) -> list[str]:
    """Copy each rule `dest/selection.txt` names into `dest/rules/` and write the repository files.

    Returns the rule directory names copied, sorted.

    Raises:
        RulesInitError: no selection file, an unknown rule name, a standard
            rule that a selected rule names in `standards` is missing from the
            selection, or `dest/rules/` already exists.
    """
    selection = dest / SELECTION
    if not selection.is_file():
        raise RulesInitError(f'{selection}: file not found: run auditor rules init {dest} first')
    names = read_selection(selection)
    require_standards(names)
    for entry in REPOSITORY_ENTRIES:
        if (dest / entry).exists():
            raise RulesInitError(f'{dest / entry} already exists: rules init creates a new repository; edit the existing one by hand')
    rules_dir = catalogue_root() / 'rules'
    for name in names:
        shutil.copytree(rules_dir / name, dest / 'rules' / name, ignore=shutil.ignore_patterns('__pycache__'))
    (dest / 'auditor-rules.toml').write_text(manifest_text(), encoding='utf-8')
    (dest / 'TODO.md').write_text(TODO_HEADER, encoding='utf-8')
    (dest / 'DONE.md').write_text(DONE_HEADER, encoding='utf-8')
    (dest / 'README.md').write_text(README, encoding='utf-8')
    (dest / '.gitignore').write_text(GITIGNORE, encoding='utf-8')
    if auditor.rulesrepo.run_git(dest, 'rev-parse', '--is-inside-work-tree') is None:
        subprocess.run(['git', 'init', '--quiet'], cwd=dest, check=True)
    return sorted(names)
