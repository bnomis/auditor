"""The Doc2 lister: every site the Doc2 question applies to."""

import ast
import json
import re
import tomllib
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib

HOOK_FILE = '.pre-commit-config.yaml'


HOOK_ID_RE = re.compile(r'^\s*-\s+id:\s*[\'"]?([^\'"\s]+)')


REQUIREMENT_NAME_RE = re.compile(r'\s*([A-Za-z0-9][A-Za-z0-9._-]*)')


def normalise_name(name: str) -> str:
    """The PEP 503 form of a distribution name."""
    return re.sub(r'[-_.]+', '-', name).lower()


def requirement_names(requirements: object) -> set[str]:
    """Normalised names from a list of requirement strings; non-string entries (group includes) are skipped."""
    names: set[str] = set()
    if isinstance(requirements, list):
        for entry in requirements:
            match = REQUIREMENT_NAME_RE.match(entry) if isinstance(entry, str) else None
            if match:
                names.add(normalise_name(match.group(1)))
    return names


def read_pyproject(scope: pathlib.Path) -> dict[str, typing.Any]:
    """Parse `pyproject.toml`; empty when absent.

    Raises:
        PhaseBError: the file exists but cannot be read or parsed.
    """
    path = scope / 'pyproject.toml'
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_bytes().decode('utf-8'))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise auditor.api.PhaseBError(f'cannot read {path}') from error


def declared_tables(pyproject: dict[str, typing.Any]) -> dict[str, dict[str, set[str]] | set[str]]:
    """The four dependency tables as normalised names, keyed by their TOML location."""
    project = pyproject.get('project', {})
    optional = project.get('optional-dependencies', {})
    groups = pyproject.get('dependency-groups', {})
    return {
        'project.dependencies': requirement_names(project.get('dependencies')),
        'project.optional-dependencies': set().union(*(requirement_names(value) for value in optional.values())) if optional else set(),
        'dependency-groups': set().union(*(requirement_names(value) for value in groups.values())) if groups else set(),
        'build-system.requires': requirement_names(pyproject.get('build-system', {}).get('requires')),
    }


def read_hook_file(scope: pathlib.Path) -> bytes:
    """The bytes of `.pre-commit-config.yaml`; empty when absent.

    Raises:
        PhaseBError: the file exists but cannot be read.
    """
    path = scope / HOOK_FILE
    if not path.exists():
        return b''
    try:
        return auditor.api.cached_bytes(path)
    except OSError as error:
        raise auditor.api.PhaseBError(f'cannot read {path}') from error


def imported_modules(scope: pathlib.Path) -> set[str]:
    """The top-level module names the corpus imports; a file with a syntax error is skipped."""
    roots, _ = auditor.api.cached_roots(scope)
    src_root = roots[0] if roots else scope / 'src'
    modules: set[str] = set()
    for path in auditor.api.corpus_py_files(scope, src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module.split('.')[0])
    return modules


# auditme: accept[literal-duplication] each question declares its own kinds; equal values are coincidence
def list_candidates(scope: pathlib.Path) -> list[auditor.api.Candidate]:
    """List each `AGENTS.md` section holding a backticked token, matched against the declared tools.

    Raises:
        PhaseBError: `AGENTS.md`, `pyproject.toml` or `.pre-commit-config.yaml` exists but cannot be read
            or parsed, or `git ls-files` fails.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    document = auditor.api.agents_document(scope)
    if document is None:
        return []
    path, lines = document
    auditor.api.tracked_files(scope)
    tables = declared_tables(read_pyproject(scope))
    hook_bytes = read_hook_file(scope)
    hooks = {match.group(1) for line in hook_bytes.decode('utf-8', errors='replace').splitlines() if (match := HOOK_ID_RE.match(line))}
    modules = imported_modules(scope)
    canonical = json.dumps({key: sorted(value) for key, value in tables.items()}, sort_keys=True).encode('utf-8')
    found: list[auditor.api.Candidate] = []
    for section in auditor.api.read_sections(path, scope):
        tokens = auditor.api.backticked_tokens(lines, section.start, section.end)
        if not tokens:
            continue
        matched: list[dict[str, typing.Any]] = []
        unmatched: set[str] = set()
        for number, token in tokens:
            words = auditor.api.TRAILING_CALL_RE.sub('', token).split()
            name = words[0] if words else token
            source = next((key for key, names in tables.items() if normalise_name(name) in names), None)
            if source is None and name in hooks:
                source = 'pre-commit hook'
            if source is None and name.split('.')[0] in modules:
                source = 'import'
            if source is None:
                unmatched.add(token)
            else:
                matched.append({'token': token, 'line': number, 'source': source})
        found.append(
            auditor.api.section_candidate(
                'Doc2',
                f'{section.doc}::{section.heading_path}',
                section,
                {'matched': matched, 'unmatched': sorted(unmatched)},
                auditor.api.digest(['\n'.join(lines[section.start - 1 : section.end]).encode('utf-8'), canonical, hook_bytes]),
            )
        )
    return found
