"""The A1 lister: every site the A1 question applies to."""

import ast
import builtins
import collections
import collections.abc
import dataclasses
import textwrap
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib

A1_RULES = ('filesystem-envelope-gap', 'filesystem-op-without-envelope', 'translator-envelope-gap')


def filesystem_envelope_gap_hits(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """The `filesystem-envelope-gap` sites, for `capture_hits`."""
    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for lineno, _ in auditor.api.filesystem_envelope_gap_sites(tree):
            auditor.api.emit_site(scope, path, 'filesystem-envelope-gap', lineno)


def filesystem_op_hits(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """The `filesystem-op-without-envelope` sites, for `capture_hits`."""
    for path, _, _, lineno in auditor.api.filesystem_op_sites(src_root):
        auditor.api.emit_site(scope, path, 'filesystem-op-without-envelope', lineno)


def translator_gap_hits(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """The `translator-envelope-gap` sites, for `capture_hits`."""
    envelopes = auditor.api.translator_envelopes(src_root)
    if not envelopes:
        return
    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for _, lineno, _, _, _, _ in auditor.api.translator_gap_sites(tree, envelopes):
            auditor.api.emit_site(scope, path, 'translator-envelope-gap', lineno)


A1_CHECKS = (filesystem_envelope_gap_hits, filesystem_op_hits, translator_gap_hits)


A1_CLIENT_MODULES = ('boto3', 'botocore', 'httpx', 'huggingface_hub', 'mlflow', 'requests', 'sqlalchemy', 'sqlite3', 'urllib.request')


A1_ROOTED_MODULES = ('subprocess', *A1_CLIENT_MODULES)


A1_CLIENT_METHODS = frozenset({'commit', 'download_file', 'execute', 'executemany', 'get_object', 'put_object', 'upload_file'})


A1_WRITE_METHODS = frozenset({'to_csv', 'to_excel', 'to_feather', 'to_hdf', 'to_json', 'to_parquet', 'to_pickle', 'to_sql'})


A1_TORCH_CALLS = frozenset({'torch.load', 'torch.save'})


@dataclasses.dataclass(frozen=True)
class Scope:
    """Where a call sits: its qualname, enclosing function and class, and innermost `try` body."""

    qualname: str
    function: auditor.api.FunctionNode | None
    nested: bool
    cls: str | None
    try_node: ast.Try | ast.TryStar | None


@dataclasses.dataclass(frozen=True)
class CallSite:
    """A call and the scope it sits in."""

    call: ast.Call
    scope: Scope


def call_sites(node: ast.AST, scope: Scope) -> collections.abc.Iterator[CallSite]:
    """Yield every call below `node` in source order, with its scope.

    A function body starts a new scope with no `try`: an enclosing `try` does
    not catch what a nested function raises when it is later called. Only the
    `try` body counts as inside the `try`, not its handlers or `finally`.
    """
    if isinstance(node, ast.Call):
        yield CallSite(node, scope)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        outer = [*node.decorator_list, *node.args.defaults, *(default for default in node.args.kw_defaults if default is not None)]
        for part in outer:
            yield from call_sites(part, scope)
        inner = Scope(auditor.api.child_qualname(scope.qualname, node.name), node, scope.function is not None, scope.cls, None)
        for statement in node.body:
            yield from call_sites(statement, inner)
    elif isinstance(node, ast.ClassDef):
        for part in [*node.decorator_list, *node.bases]:
            yield from call_sites(part, scope)
        inner = Scope(auditor.api.child_qualname(scope.qualname, node.name), None, scope.function is not None, node.name, None)
        for statement in node.body:
            yield from call_sites(statement, inner)
    elif isinstance(node, (ast.Try, ast.TryStar)):
        guarded = dataclasses.replace(scope, try_node=node)
        for statement in node.body:
            yield from call_sites(statement, guarded)
        for statement in [*node.handlers, *node.orelse, *node.finalbody]:
            yield from call_sites(statement, scope)
    else:
        for child in ast.iter_child_nodes(node):
            yield from call_sites(child, scope)


def import_targets(tree: ast.Module) -> dict[str, str]:
    """Each name an absolute import binds, mapped to the dotted module or object it names."""
    targets: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets[alias.asname or alias.name.partition('.')[0]] = alias.name if alias.asname else alias.name.partition('.')[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for alias in node.names:
                targets[alias.asname or alias.name] = f'{node.module}.{alias.name}'
    return targets


def is_under(dotted: str, modules: collections.abc.Iterable[str]) -> bool:
    """True when `dotted` is one of `modules` or lies below one."""
    return any(dotted == module or dotted.startswith(f'{module}.') for module in modules)


def is_external_call(call: ast.Call, imports: dict[str, str]) -> bool:
    """True for a call the A1 question covers: filesystem, subprocess, network, database and library I/O."""
    func = call.func
    short = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
    if short is None:
        return False
    if short in auditor.api.FILESYSTEM_TOUCHING_CALLS or (isinstance(func, ast.Name) and short == 'open'):
        return True
    if isinstance(func, ast.Attribute) and short in A1_WRITE_METHODS:
        return True
    text = auditor.api.dotted_name(func)
    if text is not None:
        head, _, rest = text.partition('.')
        target = imports.get(head)
        if target is not None:
            expanded = f'{target}.{rest}' if rest else target
            if is_under(expanded, A1_ROOTED_MODULES) or expanded in A1_TORCH_CALLS or expanded.startswith('pandas.read_'):
                return True
    return isinstance(func, ast.Attribute) and short in A1_CLIENT_METHODS and any(is_under(target, A1_CLIENT_MODULES) for target in imports.values())


def reaches_exception(lineage: collections.abc.Iterable[str]) -> bool:
    """True when a class lineage includes `Exception` or a builtin subclass of it."""
    for name in lineage:
        base = getattr(builtins, name, None)
        if isinstance(base, type) and issubclass(base, Exception):
            return True
    return False


def package_domain_errors(files: list[auditor.api.ParsedSource]) -> dict[str, list[str]]:
    """The domain errors each top-level package defines: classes named `*Error` that reach `Exception`."""
    by_package: dict[str, list[auditor.api.ParsedSource]] = collections.defaultdict(list)
    for file in files:
        by_package[file.module.partition('.')[0]].append(file)
    errors: dict[str, list[str]] = {}
    for package, members in by_package.items():
        parents = auditor.api.package_class_parents(member.tree for member in members)
        names = sorted(name for name in parents if name.endswith('Error') and reaches_exception(auditor.api.class_lineage(name, parents)))
        if names:
            errors[package] = names
    return errors


def known_functions(files: list[auditor.api.ParsedSource]) -> dict[str, str | None]:
    """Every module function and class method, by dotted name, mapped to its class (None for a function)."""
    known: dict[str, str | None] = {}
    for file in files:
        for node in file.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                known[f'{file.module}.{node.name}'] = None
            elif isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        known[f'{file.module}.{node.name}.{member.name}'] = node.name
    return known


def source_text(file: auditor.api.ParsedSource, node: ast.AST) -> str:
    """The dedented source lines of a statement or function, including its decorators."""
    first = min([node.lineno, *(decorator.lineno for decorator in getattr(node, 'decorator_list', []))])  # type: ignore[attr-defined]
    return textwrap.dedent('\n'.join(file.lines[first - 1 : node.end_lineno]))  # type: ignore[attr-defined]


def envelope_names(function: auditor.api.FunctionNode | None, catches: dict[str, frozenset[str]]) -> list[str]:
    """The translating decorators and `with` contextmanagers on a function, in source order, without repeats."""
    if function is None:
        return []
    names: list[str] = [auditor.api.callable_short_name(decorator) or '' for decorator in function.decorator_list]
    for node in ast.walk(function):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            names.extend(auditor.api.callable_short_name(item.context_expr) or '' for item in node.items)
    return list(dict.fromkeys(name for name in names if name in catches))


def site_envelope(site: CallSite, catches: dict[str, frozenset[str]], file: auditor.api.ParsedSource) -> dict[str, str | list[str] | None] | None:
    """The `try` and translating envelopes a call sits in, or None when it sits in neither."""
    names = envelope_names(site.scope.function, catches)
    if site.scope.try_node is None and not names:
        return None
    return {'try': source_text(file, site.scope.try_node) if site.scope.try_node is not None else None, 'envelopes': names}


def a1_anchor_lines(site: CallSite) -> list[int]:
    """The call's line, and the lines of the first handler of its enclosing `try`."""
    lines = [site.call.lineno]
    if site.scope.try_node is not None and site.scope.try_node.handlers:
        handler = site.scope.try_node.handlers[0]
        lines.extend(range(handler.lineno, (handler.end_lineno or handler.lineno) + 1))
    return lines


def a1_helper_privacy(helper: Scope, module: str, scope: pathlib.Path) -> str | None:
    """Why the function a call sits in is a helper: `nested`, or the `privacy` rule that marks it private.

    None when the call sits in no function, or in one that is public.
    """
    if helper.function is None:
        return None
    if helper.nested:
        return 'nested'
    private, rule = auditor.api.privacy(helper.qualname, module, scope)
    return rule if private else None


def list_candidates(scope: pathlib.Path) -> list[auditor.api.Candidate]:
    """Every external call in a package with a domain error that the sweep does not already report.

    A call in a private or nested helper lists its resolved callers, because
    whether the helper is covered depends on how each caller calls it, and
    `privacy`, the reason it counts as a helper (`a1_helper_privacy`). Test
    files are neither listed nor counted as callers.
    """
    files = auditor.api.read_audited_files(scope)
    hits = auditor.api.capture_hits(scope, A1_CHECKS)
    domain_errors = package_domain_errors(files)
    catches: dict[str, frozenset[str]] = {}
    roots, _ = auditor.api.cached_roots(scope)
    for src_root in roots:
        for name, caught in auditor.api.translator_envelopes(src_root).items():
            catches[name] = catches.get(name, frozenset()) | caught
    envelope_sources: dict[str, list[str]] = collections.defaultdict(list)
    for file in files:
        for node in ast.walk(file.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in catches:
                envelope_sources[node.name].append(source_text(file, node))
    known = known_functions(files)
    bindings = {file.module: auditor.api.call_bindings(file.tree, file.module, file.path.name == '__init__.py') for file in files}
    aliases = auditor.api.reexport_aliases(
        {file.module: auditor.api.from_import_bindings(file.tree, file.module, file.path.name == '__init__.py') for file in files},
        known,
    )
    sites: dict[str, list[CallSite]] = {}
    callers_of: dict[str, list[tuple[auditor.api.ParsedSource, CallSite]]] = collections.defaultdict(list)
    for file in files:
        if auditor.api.is_test_relpath(file.rel):
            continue
        sites[file.rel] = list(call_sites(file.tree, Scope(auditor.api.MODULE_QUALNAME, None, False, None, None)))
        for site in sites[file.rel]:
            target = auditor.api.resolve_call(site.call, file.module, site.scope.cls, bindings[file.module], known, aliases, class_methods=True)
            if target is not None:
                callers_of[target].append((file, site))

    def caller_entries(file: auditor.api.ParsedSource, site: CallSite) -> list[tuple[auditor.api.ParsedSource, CallSite]]:
        """The resolved call sites of the helper the candidate call sits in."""
        helper = site.scope
        if helper.nested:
            name = helper.qualname.rpartition('.')[2]
            parent = helper.qualname.rpartition('.')[0]
            return [
                (file, other)
                for other in sites[file.rel]
                if isinstance(other.call.func, ast.Name)
                and other.call.func.id == name
                and other.scope.qualname != helper.qualname
                and (other.scope.qualname == parent or other.scope.qualname.startswith(f'{parent}.'))
            ]
        return callers_of.get(f'{file.module}.{helper.qualname}', [])

    found: list[auditor.api.Candidate] = []
    for file in files:
        if auditor.api.is_test_relpath(file.rel) or file.module.partition('.')[0] not in domain_errors:
            continue
        errors = domain_errors[file.module.partition('.')[0]]
        imports = import_targets(file.tree)
        counter = auditor.api.SiteCounter()
        for site in sites[file.rel]:
            if not is_external_call(site.call, imports):
                continue
            callee = ast.unparse(site.call.func)
            number = counter.next(f'{site.scope.qualname}::call:{callee}')
            if auditor.api.hit_on_anchor(hits, file.rel, a1_anchor_lines(site), A1_RULES):
                continue
            names = envelope_names(site.scope.function, catches)
            enclosing = site.scope.function or site.scope.try_node or site.call
            parts = [source_text(file, enclosing) if enclosing is not site.call else '\n'.join(file.lines[site.call.lineno - 1 : site.call.end_lineno])]
            parts.extend(source for name in names for source in sorted(envelope_sources[name]))
            parts.extend(errors)
            payload: dict[str, object] = {
                'call': callee,
                'try': source_text(file, site.scope.try_node) if site.scope.try_node is not None else None,
                'envelopes': [{'name': name, 'catches': sorted(catches[name])} for name in names],
                'domain_errors': errors,
            }
            helper_privacy = a1_helper_privacy(site.scope, file.module, scope)
            helper_sites = caller_entries(file, site) if helper_privacy is not None else None
            if helper_sites is not None:
                payload['privacy'] = helper_privacy
                ordered = sorted(helper_sites, key=lambda entry: (entry[0].rel, entry[1].call.lineno))
                payload['callers'] = [
                    {'at': f'{caller_file.rel}:{caller.call.lineno}', 'caller': caller.scope.qualname, 'envelope': site_envelope(caller, catches, caller_file)}
                    for caller_file, caller in ordered
                ]
                parts.extend(
                    source_text(caller_file, caller.scope.function) if caller.scope.function is not None else caller_file.lines[caller.call.lineno - 1]
                    for caller_file, caller in ordered
                )
            found.append(
                auditor.api.span_candidate(
                    'A1',
                    f'{file.rel}::{site.scope.qualname}::call:{callee}#{number}',
                    file.rel,
                    site.call.lineno,
                    site.call.end_lineno or site.call.lineno,
                    payload,
                    parts,
                )
            )
    return found
