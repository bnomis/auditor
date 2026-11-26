"""Load and validate a rules repository: the directory `$AUDITOR_RULES_PATH` names.

`load` reads `auditor-rules.toml` and every `rules/<dir>/rule.toml` and imports
no rule code.
"""

import dataclasses
import os
import pathlib
import re
import tomllib
import types
import typing

import auditor.core

if typing.TYPE_CHECKING:
    import collections.abc

API_VERSION = (1, 0)  # the helper API version this runner serves; a test holds it equal to the helper package's own
RULES_PATH_VARIABLE = 'AUDITOR_RULES_PATH'
MANIFEST = 'auditor-rules.toml'

# The ids the runner itself can emit, whatever the rules repository holds.
RUNNER_RULE_IDS = frozenset(
    {
        'auditme-check-crash',
        'lockfile-drift',
        'ruff',
        'src-loose-module',
        'unreadable-file',
    }
)

KINDS = ('check', 'project-check', 'question', 'standard')
CHECK_KINDS = ('check', 'project-check')
CATEGORIES = ('A', 'D', 'Doc', 'P', 'S', 'Sec', 'T')
DEFAULT_BATCH_SIZE = 48
KEYS = frozenset({'batch-size', 'category', 'emits', 'id', 'kind', 'kinds', 'standards', 'takes-depth', 'title'})

DIRECTORY_NAME = re.compile(r'[a-z0-9]+(-[a-z0-9]+)*')
API_TEXT = re.compile(r'(\d+)\.(\d+)')


class RulesRepoError(auditor.core.SettingsError):
    """A rules repository is missing or invalid; the message is the error text and names the file."""


@dataclasses.dataclass(frozen=True)
class Rule:
    """One rule directory, validated."""

    name: str
    kind: str
    path: pathlib.Path
    meta: collections.abc.Mapping[str, object]


@dataclasses.dataclass(frozen=True)
class RulesRepo:
    """A loaded rules repository."""

    root: pathlib.Path
    api: tuple[int, int]
    rules: tuple[Rule, ...]  # sorted by name

    def rule_ids(self) -> frozenset[str]:
        """Every rule id the repository's checks can emit, plus the runner's own ids."""
        emitted = {rule_id for rule in self.rules for rule_id in typing.cast('list[str]', rule.meta.get('emits', []))}
        return frozenset(emitted) | RUNNER_RULE_IDS


def rules_root() -> pathlib.Path:
    """Return the directory `$AUDITOR_RULES_PATH` names, resolved.

    Raises:
        RulesRepoError: the variable is unset or empty, or the directory does not exist.
    """
    value = os.environ.get(RULES_PATH_VARIABLE, '')
    if not value:
        raise RulesRepoError(
            f"{RULES_PATH_VARIABLE} is not set: create a rules repository with 'auditor rules init <dir>' and point the variable at it (docs/setup.md)"
        )
    root = pathlib.Path(value).expanduser().resolve()
    if not root.is_dir():
        raise RulesRepoError(f'{RULES_PATH_VARIABLE} names {root}, which is not a directory: point it at a rules repository (docs/setup.md)')
    return root


def load(root: pathlib.Path) -> RulesRepo:
    """Read and validate every rule directory under `root/rules/`; import no rule code.

    The result is cached for the process, in the cache `auditor.core.clear_source_cache` clears.

    Raises:
        RulesRepoError: a malformed or missing file, an unknown key or kind,
            a duplicate rule id, or an API version this runner cannot serve.
    """
    root = root.resolve()
    key = ('rulesrepo', root)
    if key not in auditor.core.INDEX_CACHE:
        auditor.core.INDEX_CACHE[key] = load_uncached(root)
    return typing.cast('RulesRepo', auditor.core.INDEX_CACHE[key])


def read_toml(path: pathlib.Path, label: str) -> dict[str, object]:
    """Parse one TOML file.

    Raises:
        RulesRepoError: the file is missing or malformed; the message starts with `label`.
    """
    try:
        with path.open('rb') as handle:
            return tomllib.load(handle)
    except FileNotFoundError:
        raise RulesRepoError(f'{label}: file not found: create it (docs/setup.md)') from None
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise RulesRepoError(f'{label}: cannot read it as TOML: fix the file') from error


def read_api(root: pathlib.Path) -> tuple[int, int]:
    """Return the API version `auditor-rules.toml` declares.

    Raises:
        RulesRepoError: the manifest is missing or malformed, or declares a version the runner cannot serve.
    """
    manifest = read_toml(root / MANIFEST, MANIFEST)
    text = manifest.get('api')
    match = API_TEXT.fullmatch(text) if isinstance(text, str) else None
    if match is None:
        raise RulesRepoError(f'{MANIFEST}: api must be a string "M.m", for example "1.0": set it to the API version the rules were written for')
    api = (int(match[1]), int(match[2]))
    if api[0] != API_VERSION[0] or api[1] > API_VERSION[1]:
        raise RulesRepoError(
            f'rules repository needs API {api[0]}.{api[1]}; this auditor serves {API_VERSION[0]}.{API_VERSION[1]}: '
            'upgrade auditor or use an older rules repository'
        )
    return api


def load_uncached(root: pathlib.Path) -> RulesRepo:
    api = read_api(root)
    rules_dir = root / 'rules'
    directories = sorted(entry for entry in rules_dir.iterdir() if entry.is_dir() and not entry.name.startswith('.')) if rules_dir.is_dir() else []
    rules = tuple(load_rule(directory) for directory in directories)
    check_unique_ids(rules)
    check_standards(rules)
    return RulesRepo(root=root, api=api, rules=rules)


def bad_rule(directory: pathlib.Path, problem: str) -> RulesRepoError:
    return RulesRepoError(f'rules/{directory.name}/rule.toml: {problem}')


def is_str_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item for item in value)


def load_rule(directory: pathlib.Path) -> Rule:
    name = directory.name
    if not DIRECTORY_NAME.fullmatch(name):
        raise RulesRepoError(f'rules/{name}: the directory name must be lowercase with hyphens: rename it')
    meta = read_toml(directory / 'rule.toml', f'rules/{name}/rule.toml')
    unknown = sorted(set(meta) - KEYS)
    if unknown:
        raise bad_rule(directory, f'unknown key {unknown[0]!r}: remove it (the keys are {", ".join(sorted(KEYS))})')
    kind = meta.get('kind')
    if kind not in KINDS:
        raise bad_rule(directory, f'kind must be one of {", ".join(KINDS)}, not {kind!r}: set it')
    title = meta.get('title')
    if not isinstance(title, str) or not title:
        raise bad_rule(directory, 'title must be a non-empty string: add a one-line title')
    if not (directory / 'rule.md').is_file():
        raise RulesRepoError(f'rules/{name}/rule.md: file not found: write the rule in prose')
    if 'standards' in meta and not is_str_list(meta['standards']):
        raise bad_rule(directory, 'standards must be a list of directory names: fix it')
    if kind in CHECK_KINDS:
        reject_bad_check(directory, meta)
    elif kind == 'question':
        reject_bad_question(directory, meta)
    return Rule(name=name, kind=typing.cast('str', kind), path=directory, meta=types.MappingProxyType(meta))


def reject_bad_check(directory: pathlib.Path, meta: dict[str, object]) -> None:
    if not is_str_list(meta.get('emits')):
        raise bad_rule(directory, f'kind {meta["kind"]!r} needs emits, a list of the rule ids the check can emit: add it')
    if not (directory / 'check.py').is_file():
        raise RulesRepoError(f'rules/{directory.name}/check.py: file not found: a {meta["kind"]} rule needs it')


def reject_bad_question(directory: pathlib.Path, meta: dict[str, object]) -> None:
    question_id = meta.get('id')
    if not isinstance(question_id, str) or not question_id:
        raise bad_rule(directory, 'a question needs id, its Phase B id such as "A4": add it')
    if directory.name != question_id.lower():
        raise bad_rule(directory, f'a question directory is its id in lower case: rename it to {question_id.lower()!r}')
    if meta.get('category') not in CATEGORIES:
        raise bad_rule(directory, f'category must be one of {", ".join(CATEGORIES)}, not {meta.get("category")!r}: set it')
    batch_size = meta.get('batch-size', DEFAULT_BATCH_SIZE)
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise bad_rule(directory, 'batch-size must be a positive integer: fix it')
    if not isinstance(meta.get('takes-depth', False), bool):
        raise bad_rule(directory, 'takes-depth must be true or false: fix it')
    if (directory / 'lister.py').is_file():
        if not is_str_list(meta.get('kinds')):
            raise bad_rule(directory, 'a question with lister.py needs kinds, the finding kinds of a result line: add it')
        if not (directory / 'brief.md').is_file():
            raise RulesRepoError(f'rules/{directory.name}/brief.md: file not found: a question with lister.py needs it')


def check_unique_ids(rules: tuple[Rule, ...]) -> None:
    owner: dict[str, str] = {}
    for rule in rules:
        ids = list(typing.cast('list[str]', rule.meta.get('emits', [])))
        if 'id' in rule.meta:
            ids.append(typing.cast('str', rule.meta['id']))
        for rule_id in ids:
            if rule_id in owner and owner[rule_id] != rule.name:
                raise RulesRepoError(
                    f'rules/{rule.name}/rule.toml: rule id {rule_id!r} is also used by rules/{owner[rule_id]}/rule.toml: give each rule id to one directory'
                )
            owner[rule_id] = rule.name


def check_standards(rules: tuple[Rule, ...]) -> None:
    standards = {rule.name for rule in rules if rule.kind == 'standard'}
    for rule in rules:
        for name in typing.cast('list[str]', rule.meta.get('standards', [])):
            if name not in standards:
                raise RulesRepoError(f'rules/{rule.name}/rule.toml: standards names {name!r}, which is not a standard rule directory: fix the name')


__all__ = [
    'API_VERSION',
    'CATEGORIES',
    'CHECK_KINDS',
    'KINDS',
    'RUNNER_RULE_IDS',
    'Rule',
    'RulesRepo',
    'RulesRepoError',
    'load',
    'rules_root',
]
