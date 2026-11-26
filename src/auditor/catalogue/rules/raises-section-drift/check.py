import ast
import collections
import collections.abc
import os.path
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


# A chain of one empty step: the error is raised in the function itself.
RAISED_HERE: tuple[str, ...] = ('',)


def unset_optional_guard(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    error: str,
    parents: collections.abc.Mapping[str, set[str]],
    call: ast.Call,
    bound: bool,
) -> bool:
    """Whether `call` leaves unset every optional argument guarding `error`.

    True when `func`'s own scope (nested defs, lambdas and classes excluded)
    holds at least one `raise X(...)` or `raise mod.X(...)` whose lineage
    contains `error`, and each such raise has an enclosing `If` (in its body
    or `orelse`) or `Match` inside `func` whose test or subject reads a Name
    that is a parameter with a default which `call` does not supply. A
    parameter is supplied when a keyword names it or a positional argument
    reaches its position; with `bound` (a call through `self.`), positional
    arguments start at the second parameter. A call with a `*` or `**`
    argument supplies every parameter. False otherwise, including when
    `func` raises `error` only through its own callees.
    """
    if any(isinstance(arg, ast.Starred) for arg in call.args) or any(kw.arg is None for kw in call.keywords):
        return False
    args = func.args
    positional = [*args.posonlyargs, *args.args]
    first_default = len(positional) - len(args.defaults)
    optional = {arg.arg: index for index, arg in enumerate(positional) if index >= first_default}
    optional.update({arg.arg: -1 for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True) if default is not None})
    reached = len(call.args) + (1 if bound else 0)
    named = {kw.arg for kw in call.keywords}
    unset = {name for name, index in optional.items() if name not in named and (index < 0 or index >= reached)}
    if not unset:
        return False

    def reads_unset(expr: ast.expr) -> bool:
        return any(isinstance(node, ast.Name) and node.id in unset for node in ast.walk(expr))

    found = False

    def visit(node: ast.AST, guarded: bool) -> bool:
        """Walk `node`; False when a matching raise sits outside an unset-argument guard."""
        nonlocal found
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return True
        if isinstance(node, ast.Raise):
            name = auditor.api.raised_name(node)
            if name and error in auditor.api.class_lineage(name, parents):
                found = True
                if not guarded:
                    return False
        tested = node.test if isinstance(node, ast.If) else node.subject if isinstance(node, ast.Match) else None
        inner = guarded or (tested is not None and reads_unset(tested))
        return all(visit(child, inner) for child in ast.iter_child_nodes(node))

    return all(visit(statement, False) for statement in func.body) and found


SECTIONLESS_DEPTH: typing.Final = 3
"""How many calls deep the rule follows from a subject; the A4 lister's `--depth` default."""


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a `Raises:` section that disagrees with the domain errors reaching
    the caller (A4).

    Signal:
      - A function or method whose docstring has a Google-style `Raises:`
        section (`auditor.api.raises_section_names`).
      - What reaches its caller: every domain error its body raises, plus every
        domain error a same-package callee's own `Raises:` section declares,
        minus each that an enclosing `except` catches without re-raising.
      - One hit per name the section omits, and one per domain error it
        declares that never reaches the caller although a handler in the
        function catches it - the positive evidence that it is caught there.

    A domain error is an exception class the swept package defines - positive
    evidence, so `sqlite3.Error` (tail `Error`) and a third-party `*Error` are
    not one - and never a builtin (`auditor.api.STDLIB_ERRORS`). Subclasses follow the package's own class tree: catching
    or declaring a base covers its subclasses. A callee with a `Raises:`
    section is followed through that declared section, not its body; a callee
    with no section is followed into its own raises and callees, up to
    `SECTIONLESS_DEPTH` calls deep. Only calls within the package being swept
    resolve: a module function called by its dotted path (or a name imported
    from a package module), a same-module function, a method called on
    `self`, or `<ClassName>.<method>(...)` for a class the package defines,
    following re-exports such as a package `__init__.py`'s
    `from pkg.mod import name`. A call the check cannot resolve contributes
    nothing, which is why an extra needs a catching handler: without one, the
    declared error may arrive through such a call.

    Raised by an audit whose Phase B A4 kept finding these by hand, cycle
    after cycle (shipped 2026-10-31).

    Refinement (2026-11-01): a callee's declared error does not reach the
    caller through a call that leaves unset every optional argument guarding
    it (`unset_optional_guard`): every raise of it in the callee's own body
    sits under an `if` or `match` testing a parameter with a default that the
    call does not supply, as `if strict: raise ParseError(...)` called as
    `load('x')`. Omissions only; a guard on a parameter without a default, a
    module-level name, a raise outside the guard, or a call passing the
    argument (or `*args`/`**kwargs`) keeps the hit. Other value-dependent
    cases (fixed names, pre-checked values, dispatch types) are left to the
    Phase B review (A4).

    Refinement (2026-11-01), nested functions: a def nested directly in the
    subject and called by bare name contributes its raises and calls under
    the call's handlers (`auditor.api.nested_call_sites`, one level deep), so an error it
    catches and re-raises on one branch still reaches the subject's callers;
    a def never called contributes nothing. A raise inside a def, lambda or
    class defined in a handler does not make that handler re-raise.

    Extension (2026-11-20): both resolution gaps in the request "`raises-section-drift`
    should follow pass-through callees and `Class.method()` calls" (a past
    change request) are closed. A `<ClassName>.<method>(...)`
    call resolves like a call on `self`, and a callee with no `Raises:` section
    is followed into its own raises and callees up to `SECTIONLESS_DEPTH`
    calls deep, with the chain named in the hit's variant. Omission hits grow;
    an extra declaration is reported only if it still never reaches the caller.

    Refinement (2026-11-24): a combined entry (`ParseError, FetchError:`)
    declares each name, and an `except` naming a module-level tuple of classes
    the package defines (`auditor.api.tuple_constants`) catches each member.

    Extension (2026-11-24): the modules under each directory `[tool.auditme]
    first-party` lists (`first_party_dirs`) join the tables, so a call into such
    a library resolves as a same-package call, its `Raises:` sections are
    followed and its error classes count as domain errors. Only the swept
    package's functions are subjects: no hit lands on a library file, which
    `related` names by its path relative to the project.

    Raises:
        RootsError: a `first-party` entry is invalid (`first_party_dirs`).
    """
    modules: dict[str, tuple[pathlib.Path, ast.Module, list[str]]] = {}
    for path in auditor.api.all_py_files(src_root):
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        modules[auditor.api.module_dotted(path, src_root)] = (path, tree, lines)
    swept = set(modules)
    for library in auditor.api.cached_first_party_dirs(scope):
        for path in auditor.api.all_py_files(library):
            tree = auditor.api.read_and_parse(path)
            if tree is None:
                continue
            modules.setdefault(auditor.api.module_dotted(path, library), (path, tree, auditor.api.source_lines(path)))

    parents = auditor.api.package_class_parents(tree for _, tree, _ in modules.values())
    package_classes = set(parents)
    constants = auditor.api.tuple_constants(tree for _, tree, _ in modules.values())
    declared_by: dict[str, set[str]] = {}
    path_of: dict[str, pathlib.Path] = {}
    functions: list[tuple[str, str, str | None, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for module, (_, tree, _) in modules.items():
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append((module, f'{module}.{node.name}', None, node))
            elif isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        functions.append((module, f'{module}.{node.name}.{member.name}', node.name, member))
    node_of: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for module, qualname, _, node in functions:
        declared_by[qualname] = auditor.api.raises_section_names(ast.get_docstring(node) or '')
        node_of[qualname] = node
        path_of[qualname] = modules[module][0]

    known = {qualname: cls for _, qualname, cls, _ in functions}
    bindings_of = {module: auditor.api.call_bindings(tree, module, path.name == '__init__.py') for module, (path, tree, _) in modules.items()}
    aliases = auditor.api.reexport_aliases(bindings_of, known)

    def ancestors(name: str) -> set[str]:
        return auditor.api.class_lineage(name, parents) - {name}

    def is_domain(name: str) -> bool:
        return name in package_classes and name not in auditor.api.STDLIB_ERRORS

    def caught(name: str, around: tuple[auditor.api.HandlerLevel, ...]) -> bool:
        lineage = {name} | ancestors(name)
        return any(auditor.api.level_catches(auditor.api.expand_level(level, constants), lineage) for level in around)

    module_of = {qualname: module for module, qualname, _, _ in functions}

    def is_bound(site: ast.Call, callee: str) -> bool:
        callee_node = node_of[callee]
        on_name = isinstance(site.func, ast.Attribute) and isinstance(site.func.value, ast.Name)
        return on_name and (
            site.func.value.id == 'self' or (known[callee] is not None and any(ast.unparse(d) == 'classmethod' for d in callee_node.decorator_list))
        )

    def declared_reach(site: ast.Call, callee: str, around: tuple[auditor.api.HandlerLevel, ...]) -> list[str]:
        """The domain errors a callee's section declares that reach past `around` and the call's unset guards."""
        bound = is_bound(site, callee)
        return [
            name
            for name in sorted(declared_by[callee])
            if is_domain(name) and not caught(name, around) and not unset_optional_guard(node_of[callee], name, parents, site, bound)
        ]

    def escapes(qualname: str, hop: int, chain: tuple[str, ...]) -> dict[str, set[tuple[str, ...]]]:
        """The domain errors leaving the section-less function `qualname`, each with the chains it leaves through.

        A chain lists the functions it passes through, outermost first, and ends with
        the function whose section declares the error, or with `''` after the function that raises it.
        """
        found: dict[str, set[tuple[str, ...]]] = collections.defaultdict(set)
        on_path = (*chain, qualname)
        module = module_of[qualname]
        for site, around in auditor.api.nested_call_sites(node_of[qualname]):
            if isinstance(site, ast.Raise):
                name = auditor.api.raised_name(site)
                if name and is_domain(name) and not caught(name, around):
                    found[name].add((qualname, ''))
                continue
            if hop >= SECTIONLESS_DEPTH:
                continue
            callee = auditor.api.resolve_call(site, module, known[qualname], bindings_of[module], known, aliases, class_methods=True)
            if callee is None or callee in on_path:
                continue
            if 'Raises:' in (ast.get_docstring(node_of[callee]) or ''):
                for name in declared_reach(site, callee, around):
                    found[name].add((qualname, callee))
                continue
            for name, chains in escapes(callee, hop + 1, on_path).items():
                if not caught(name, around):
                    found[name].update((qualname, *inner) for inner in chains)
        return found

    def describe(chain: tuple[str, ...]) -> str:
        if chain == RAISED_HERE:
            return 'raised here'
        *wrappers, last = chain
        if last == '':
            *wrappers, raiser = wrappers
            source = f'raised by {raiser}'
        else:
            source = f'declared by {last}'
        return f'{source} via {", ".join(wrappers)}' if wrappers else source

    for module, qualname, cls, node in functions:
        doc = ast.get_docstring(node) or ''
        if module not in swept or 'Raises:' not in doc:
            continue
        declared = {name for name in auditor.api.raises_section_names(doc) if is_domain(name)}
        path, tree, lines = modules[module]
        imported = bindings_of[module]

        reached: dict[str, set[tuple[str, ...]]] = collections.defaultdict(set)
        for site, around in auditor.api.nested_call_sites(node):
            if isinstance(site, ast.Raise):
                name = auditor.api.raised_name(site)
                if name and is_domain(name) and not caught(name, around):
                    reached[name].add(RAISED_HERE)
                continue
            callee = auditor.api.resolve_call(site, module, cls, imported, known, aliases, class_methods=True)
            if callee is None or callee == qualname:
                continue
            if 'Raises:' in (ast.get_docstring(node_of[callee]) or ''):
                for name in declared_reach(site, callee, around):
                    reached[name].add((callee,))
                continue
            for name, chains in escapes(callee, 1, (qualname,)).items():
                if not caught(name, around):
                    reached[name].update(chains)

        rel = auditor.api.relpath(path, scope)
        accept = auditor.api.accept_reason(lines, node.lineno, rule='raises-section-drift')
        evidence = lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else ''
        for name in sorted(reached):
            if name in declared or ancestors(name) & declared:
                continue
            chains = reached[name]
            on_chains = {function for chain in chains for function in chain if function}
            auditor.api.emit(
                related=sorted({os.path.relpath(path_of[function], scope) for function in on_chains if path_of[function] != path}),
                rule='raises-section-drift',
                variant=f'{node.name}: Raises: omits {name}, {describe(min(chains, key=lambda chain: (len(chain), chain)))}',
                path=rel,
                line=node.lineno,
                evidence=evidence,
                accepted=bool(accept),
                accepted_reason=accept,
            )
        levels = auditor.api.function_levels(node.body)
        for name in sorted(declared):
            if any(name == found or name in ancestors(found) for found in reached):
                continue
            lineage = {name} | ancestors(name)
            if not any(auditor.api.level_catches(auditor.api.expand_level(level, constants), lineage) for level in levels):
                continue
            auditor.api.emit(
                rule='raises-section-drift',
                variant=f'{node.name}: Raises: declares {name}, which never reaches the caller',
                path=rel,
                line=node.lineno,
                evidence=evidence,
                accepted=bool(accept),
                accepted_reason=accept,
            )
