"""The A17 lister: every site the A17 question applies to."""

import ast
import collections
import pathlib
import tomllib
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import collections.abc

A17_SHIM_RULE = 'migration-shim-consumer'


def empty_init_hits(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Emit each `empty-init-while-siblings-export` site, as the rule does, for `capture_hits`."""
    for path, _ in auditor.api.empty_init_sites(src_root):
        auditor.api.emit(
            rule='empty-init-while-siblings-export',
            variant='',
            path=auditor.api.relpath(path, scope),
            line=1,
            evidence='',
            accepted=False,
            accepted_reason=None,
        )


def migration_shim_hits(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Emit each `migration-shim-consumer` site, as the rule does, for `capture_hits`."""
    for path, line, variant, evidence in auditor.api.migration_shim_sites(src_root):
        auditor.api.emit(
            rule=A17_SHIM_RULE, variant=variant, path=auditor.api.relpath(path, scope), line=line, evidence=evidence, accepted=False, accepted_reason=None
        )


A17_CHECKS = (empty_init_hits, migration_shim_hits)


def dunder_all_names(tree: ast.Module) -> list[str] | None:
    """The string members of the module's `__all__`, or None when it has none."""
    names: list[str] | None = None
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and auditor.api.is_dunder_all_assignment(node):
            names = []
            if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                names = [element.value for element in node.value.elts if isinstance(element, ast.Constant) and isinstance(element.value, str)]
    return names


def entry_point_targets(scope: pathlib.Path) -> list[tuple[str, str, str]]:
    """Each `[project.scripts]` and `[project.entry-points]` target of `pyproject.toml` as (module, name, text).

    Raises:
        PhaseBError: `pyproject.toml` cannot be read or parsed.
    """
    pyproject = scope / 'pyproject.toml'
    if not pyproject.is_file():
        return []
    try:
        project = tomllib.loads(pyproject.read_text(encoding='utf-8')).get('project', {})
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise auditor.api.PhaseBError(f'cannot parse {pyproject}') from error
    tables = [project.get('scripts', {})]
    tables.extend(project.get('entry-points', {}).values())
    targets: list[tuple[str, str, str]] = []
    for table in tables:
        for key, value in table.items():
            module, _, name = str(value).partition(':')
            targets.append((module.strip(), name.partition('[')[0].strip(), f'pyproject.toml: {key} = "{value}"'))
    return targets


def list_candidates(scope: pathlib.Path) -> list[auditor.api.Candidate]:
    """Every `__init__.py` with an `__all__` or no exports, and every submodule with an `__all__`, with who reads from it.

    A reader in the package's own directory or the test tree is not a
    consumer; for a submodule only the submodule itself and the test tree are
    left out, as its `__all__` declares its surface to its own package too. A consumer line a `migration-shim-consumer` hit names is left
    out, and an `__init__.py` with an `empty-init-while-siblings-export` hit
    is not listed.

    A candidate is one file, so its id is the file's repo-relative
    path, with no `::` qualname part as the other questions' ids have; the
    form is kept so ledger ids already written stay valid.

    Raises:
        PhaseBError: a file cannot be read or parsed.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    files = auditor.api.read_audited_files(scope)
    roots, _ = auditor.api.cached_roots(scope)
    if not roots:
        return []
    hits = auditor.api.capture_hits(scope, A17_CHECKS)
    reads = auditor.api.reads_by_module_and_name(scope, roots[0])
    entry_points = entry_point_targets(scope)
    line_cache: dict[pathlib.Path, list[str]] = {}

    def read_entries(module: str, names: collections.abc.Iterable[str] | None, own: collections.abc.Callable[[str], bool]) -> list[tuple[str, str]]:
        """Each outside read of `module` or its submodules, as (name, entry), by the read's name when `names` is None."""
        wanted = None if names is None else set(names)
        entries: list[tuple[str, str]] = []
        for (read_module, name), where in sorted(reads.items()):
            if not (read_module == module or read_module.startswith(f'{module}.')) or (wanted is not None and name not in wanted):
                continue
            if names is None and read_module == module:
                continue
            for path, line in where:
                rel = auditor.api.relpath(path, scope)
                if own(rel) or auditor.api.is_test_relpath(rel) or (A17_SHIM_RULE, rel, line) in hits:
                    continue
                # auditme: accept[filesystem-op-without-envelope] `candidates.read_text` translates the read's errors to PhaseBError
                text = line_cache.setdefault(path, auditor.api.read_text(path).splitlines())[line - 1].strip()
                entries.append((name, f'{rel}: {text}'))
        for entry_module, entry_name, text in entry_points:
            if (
                (entry_module == module or entry_module.startswith(f'{module}.'))
                and (wanted is None or entry_name in wanted)
                and not (names is None and entry_module == module)
            ):
                entries.append((entry_name, text))
        return entries

    found: list[auditor.api.Candidate] = []
    for file in files:
        is_init = file.path.name == '__init__.py'
        names = dunder_all_names(file.tree)
        if not is_init and names is None:
            continue
        exports_nothing = names is None and not any(isinstance(node, ast.ImportFrom) for node in file.tree.body)
        if names is None and not exports_nothing:
            continue
        if is_init and auditor.api.hit_on_anchor(hits, file.rel, [1], ('empty-init-while-siblings-export',)):
            continue
        directory = str(pathlib.PurePosixPath(file.rel).parent)
        own = (lambda rel, directory=directory: rel.startswith(f'{directory}/')) if is_init else (lambda rel, own_rel=file.rel: rel == own_rel)
        payload: dict[str, object] = {}
        keyed: list[tuple[str, str]]
        if names is not None:
            keyed = read_entries(file.module, names, own)
            payload['all'] = names
            payload['consumers'] = {name: sorted({entry for key, entry in keyed if key == name}) for name in names}
        else:
            keyed = read_entries(file.module, None, own)
            payload['all'] = []
            payload['consumers'] = {}
            payload['reach_ins'] = sorted({entry for _, entry in keyed})
        source = '\n'.join(file.lines)
        parts = [source, *(f'{name}\t{entry}' for name, entry in sorted(set(keyed)))]
        found.append(
            auditor.api.span_candidate(
                'A17',
                file.rel,
                file.rel,
                1,
                max(len(file.lines), 1),
                payload,
                parts,
            )
        )
    return found
