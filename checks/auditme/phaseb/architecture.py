"""Architecture questions: the listers for A11, A19, A1 and A17 and their shared helpers.

`capture_hits` runs sweep rules and returns where they hit, so a lister can
drop a site the sweep already reports. The other helpers parse every audited
file, number the sites in a qualname and walk a tree with qualified names.
"""

import ast
import builtins
import collections
import collections.abc
import contextlib
import dataclasses
import io
import json
import pathlib
import textwrap
import tomllib

import auditme.core
import auditme.rules.error_handling
import auditme.rules.imports_and_surfaces
import auditme.rules.state_and_effects
from auditme.phaseb import candidates, testmap
from auditme.phaseb.errors import PhaseBError

Check = collections.abc.Callable[[pathlib.Path, pathlib.Path], None]

MODULE_QUALNAME = '<module>'


def capture_hits(scope: pathlib.Path, checks: collections.abc.Sequence[Check]) -> set[tuple[str, str, int]]:
    """Run checks over every audit root and return each hit as (rule, path, line).

    Saves and restores `_EMITTED` and captures stdout. Accepted hits are included.

    Raises:
        PhaseBError: a check raised; the message names the check.
    """
    saved = set(auditme.core._EMITTED)
    hits: set[tuple[str, str, int]] = set()
    try:
        for check in checks:
            auditme.core._EMITTED.clear()
            buffer = io.StringIO()
            try:
                with contextlib.redirect_stdout(buffer):
                    for src_root in auditme.core._audit_roots(scope):
                        check(scope, src_root)
            except Exception as error:  # a check's failure must stop the lister, whatever its type
                raise PhaseBError(f'check {getattr(check, "__name__", check)!r} failed: {error}') from error
            for line in buffer.getvalue().splitlines():
                record = json.loads(line)
                hits.add((record['rule'], record['path'], record['line']))
    finally:
        auditme.core._EMITTED.clear()
        auditme.core._EMITTED.update(saved)
    return hits


@dataclasses.dataclass(frozen=True)
class ParsedSource:
    """An audited file parsed once, with its repo-relative path and dotted module."""

    path: pathlib.Path
    rel: str
    module: str
    tree: ast.Module
    lines: list[str]


def parse_audited_files(scope: pathlib.Path) -> list[ParsedSource]:
    """Every Python file under an audit root, parsed once, in path order.

    Raises:
        PhaseBError: a file does not parse; the rules skip it, but a skipped
            file would hide its candidates and let `merge` drop their ledger
            entries as vanished.
    """
    files: list[ParsedSource] = []
    for src_root in auditme.core._audit_roots(scope):
        for path in auditme.core._all_py_files(src_root):
            try:
                text = path.read_text(encoding='utf-8')
                tree = ast.parse(text)
            except (OSError, UnicodeDecodeError, SyntaxError) as error:
                raise PhaseBError(f'cannot parse {path}: {error}') from error
            files.append(ParsedSource(path, auditme.core._relpath(path, scope), auditme.core.module_dotted(path, src_root), tree, text.splitlines()))
    return files


class SiteCounter:
    """Numbers the sites of one qualname by order of appearance, from 1.

    An edit in another function does not change a site's number, so candidate
    ids stay stable.
    """

    def __init__(self) -> None:
        self._counts: collections.Counter[str] = collections.Counter()

    def next(self, qualname: str) -> int:
        """The number of the next site in this qualname."""
        self._counts[qualname] += 1
        return self._counts[qualname]


def child_qualname(qualname: str, name: str) -> str:
    """The qualname of a function or class `name` defined directly in `qualname`."""
    return name if qualname == MODULE_QUALNAME else f'{qualname}.{name}'


def walk_with_qualname(tree: ast.AST, qualname: str = MODULE_QUALNAME) -> collections.abc.Iterator[tuple[str, ast.AST]]:
    """Yield (enclosing qualname, node) for every node below `tree`, in source order.

    Module-level code has the qualname `<module>`; a function or class body
    extends the qualname with its name.
    """
    for node in ast.iter_child_nodes(tree):
        yield qualname, node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield from walk_with_qualname(node, child_qualname(qualname, node.name))
        else:
            yield from walk_with_qualname(node, qualname)


def hit_on_anchor(hits: set[tuple[str, str, int]], path: str, lines: collections.abc.Iterable[int], rules: collections.abc.Iterable[str]) -> bool:
    """True when a hit of one of `rules` falls on `path` at one of the anchor `lines`."""
    wanted = set(rules)
    anchors = set(lines)
    return any(rule in wanted and hit_path == path and line in anchors for rule, hit_path, line in hits)


FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef

A11_BRIEF = candidates.DOC_BRIEFS / 'A11.md'
A11_RULES = ('assert-never-missing',)


def dotted_name(node: ast.AST) -> str | None:
    """The text of a name or a dotted attribute made of names, else None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)
        return None if base is None else f'{base}.{node.attr}'
    return None


def is_constant_operand(node: ast.expr) -> bool:
    """A string constant, an attribute constant (`Mode.FAST`) or a tuple, list or set of them."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.Attribute):
        return dotted_name(node) is not None
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(is_constant_operand(element) for element in node.elts)
    return False


def comparison_subject(test: ast.expr) -> str | None:
    """The name or dotted attribute a single `==`, `is` or `in` comparison tests against constants."""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return None
    operator, right = test.ops[0], test.comparators[0]
    if not isinstance(operator, (ast.Eq, ast.Is, ast.In)):
        return None
    left_name = dotted_name(test.left)
    if left_name is not None and is_constant_operand(right):
        return left_name
    if isinstance(operator, ast.Eq) and isinstance(test.left, ast.Constant) and isinstance(test.left.value, str):
        return dotted_name(right)
    return None


def flag_subjects(function: ast.AST) -> dict[str, str]:
    """Each name the function assigns from a comparison, mapped to the compared subject."""
    flags: dict[str, str] = {}
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            subject = comparison_subject(node.value)
            if subject is not None:
                flags[node.targets[0].id] = subject
    return flags


def else_if_nodes(tree: ast.AST) -> set[int]:
    """The id of every `If` that is the sole `orelse` of another, so is not a chain head."""
    return {id(node.orelse[0]) for node in ast.walk(tree) if isinstance(node, ast.If) and len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)}


def scope_nodes(tree: ast.AST) -> dict[str, ast.AST]:
    """Every function and class below `tree`, by qualname."""
    scopes: dict[str, ast.AST] = {}
    for qualname, node in walk_with_qualname(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scopes[child_qualname(qualname, node.name)] = node
    return scopes


def annotation_of(subject: str, function: FunctionNode | None, owner: ast.AST | None) -> str | None:
    """The subject's annotation: a parameter, a local annotation or a class field, else None."""
    if function is not None:
        arguments = function.args
        for argument in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs, arguments.vararg, arguments.kwarg]:
            if argument is not None and argument.arg == subject and argument.annotation is not None:
                return ast.unparse(argument.annotation)
        for node in ast.walk(function):
            if isinstance(node, ast.AnnAssign) and dotted_name(node.target) == subject:
                return ast.unparse(node.annotation)
    if isinstance(owner, ast.ClassDef) and subject.startswith('self.'):
        field = subject.removeprefix('self.')
        for node in owner.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == field:
                return ast.unparse(node.annotation)
    return None


def is_enum_class(node: ast.ClassDef) -> bool:
    """True when a base is one of the standard enum classes, named or dotted."""
    return any((dotted_name(base) or '').rpartition('.')[2] in candidates.T2_ENUM_BASES for base in node.bases)


def literal_alias(node: ast.AST) -> str | None:
    """The alias name when the statement binds a name to a `Literal[...]` type, else None."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        name, value = dotted_name(node.targets[0]), node.value
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        name, value = dotted_name(node.target), node.value
    elif isinstance(node, ast.TypeAlias):
        name, value = dotted_name(node.name), node.value
    else:
        return None
    if name is None or not isinstance(value, ast.Subscript):
        return None
    return name if (dotted_name(value.value) or '').rpartition('.')[2] == 'Literal' else None


def typing_aliases(files: list[ParsedSource]) -> dict[str, str]:
    """Each `Literal` alias and `Enum` class the package defines, by name, as `path:line name`."""
    found: dict[str, str] = {}
    for file in files:
        for node in ast.walk(file.tree):
            if not isinstance(node, ast.stmt):
                continue
            name = node.name if isinstance(node, ast.ClassDef) and is_enum_class(node) else literal_alias(node)
            if name is not None:
                found.setdefault(name, f'{file.rel}:{node.lineno} {name}')
    return found


def a11_site(node: ast.AST, flags: dict[str, str]) -> tuple[str, str] | None:
    """(kind, subject) when the node is an A11 site: a chain head, a two-way split or a `match`."""
    if isinstance(node, ast.Match):
        return 'match', ast.unparse(node.subject)
    if not isinstance(node, ast.If):
        return None
    chain = auditme.rules.state_and_effects.if_chain(node, comparison_subject)
    if chain is not None:
        if len(chain.tests) >= 2 or chain.orelse is not None:
            return 'if', chain.subject
        return None
    if isinstance(node.test, ast.Name) and node.orelse and node.test.id in flags:
        return 'if', flags[node.test.id]
    return None


def type_source_of(annotation: str | None, aliases: dict[str, str]) -> str | None:
    """The alias or enum an annotation names, if the package defines one."""
    if annotation is None:
        return None
    names = candidates.annotation_names(ast.parse(annotation, mode='eval').body)
    return next((aliases[name] for name in sorted(names) if name in aliases), None)


@candidates.register_question('A11', A11_BRIEF)
def list_a11_candidates(scope: pathlib.Path) -> list[candidates.Candidate]:
    """Every if chain, two-way split on a comparison flag and `match` the sweep does not already report."""
    files = parse_audited_files(scope)
    hits = capture_hits(scope, [auditme.rules.state_and_effects.check_assert_never_missing])
    aliases = typing_aliases(files)
    found: list[candidates.Candidate] = []
    for file in files:
        scopes = scope_nodes(file.tree)
        else_ifs = else_if_nodes(file.tree)
        counter = SiteCounter()
        for qualname, node in walk_with_qualname(file.tree):
            if id(node) in else_ifs or not isinstance(node, ast.stmt):
                continue
            function = scopes.get(qualname)
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function = None
            site = a11_site(node, flag_subjects(function) if function is not None else {})
            if site is None or hit_on_anchor(hits, file.rel, [node.lineno], A11_RULES):
                continue
            kind, subject = site
            number = counter.next(f'{qualname}::{kind}:{subject}')
            owner = scopes.get(qualname.rpartition('.')[0]) if function is not None else None
            annotation = annotation_of(subject, function, owner)
            type_source = type_source_of(annotation, aliases)
            source = textwrap.dedent('\n'.join(file.lines[node.lineno - 1 : node.end_lineno]))
            found.append(
                candidates.Candidate(
                    question='A11',
                    id=f'{file.rel}::{qualname}::{kind}:{subject}#{number}',
                    path=file.rel,
                    start=node.lineno,
                    end=node.end_lineno or node.lineno,
                    payload={'source': source, 'subject': subject, 'annotation': annotation, 'type_source': type_source},
                    hash=candidates.digest([part.encode('utf-8') for part in (source, subject, annotation or '', type_source or '')]),
                )
            )
    return found


A19_BRIEF = candidates.DOC_BRIEFS / 'A19.md'
A19_RULES = ('silent-broad-except', 'broad-except-wrong-level', 'logger-exception-graceful-degradation')
A19_CHECKS = (
    auditme.rules.error_handling.check_silent_broad_except,
    auditme.rules.error_handling.check_broad_except_wrong_level,
    auditme.rules.error_handling.check_logger_exception_graceful_degradation,
)
LOGGER_NAMES = frozenset({'logger', 'log', '_logger', 'LOGGER', 'logging', 'loguru.logger'})
LOG_LEVELS = frozenset({'debug', 'info', 'warning', 'warn', 'error', 'critical', 'exception'})
LEAVING_STATEMENTS = (ast.Return, ast.Raise, ast.Continue, ast.Break)


def logger_call_level(node: ast.AST) -> str | None:
    """The level when the node is a call to a logging method on a logger name, else None."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr not in LOG_LEVELS:
        return None
    receiver = dotted_name(node.func.value)
    if receiver is None:
        return None
    return node.func.attr if receiver.removeprefix('self.') in LOGGER_NAMES else None


def log_calls_of(handler: ast.ExceptHandler) -> list[str]:
    """Each logger call in the handler body as `level: text`, text being its first argument."""
    calls: list[str] = []
    for statement in handler.body:
        for node in ast.walk(statement):
            level = logger_call_level(node)
            if level is not None and isinstance(node, ast.Call):
                calls.append(f'{level}: {ast.unparse(node.args[0]) if node.args else ""}')
    return calls


def function_summary(function: FunctionNode) -> dict[str, str | None]:
    """Name, signature, return annotation and last statement of a function."""
    return {
        'name': function.name,
        'signature': ast.unparse(function.args),
        'returns': ast.unparse(function.returns) if function.returns is not None else None,
        'last_statement': ast.unparse(function.body[-1]) if function.body else None,
    }


def handler_anchor_lines(handler: ast.ExceptHandler, function: FunctionNode | None) -> list[int]:
    """The handler's lines, plus the function's last `return` when the handler falls through."""
    lines = list(range(handler.lineno, (handler.end_lineno or handler.lineno) + 1))
    falls_through = not handler.body or not isinstance(handler.body[-1], LEAVING_STATEMENTS)
    if falls_through and function is not None and function.body and isinstance(function.body[-1], ast.Return):
        lines.append(function.body[-1].lineno)
    return lines


@candidates.register_question('A19', A19_BRIEF)
def list_a19_candidates(scope: pathlib.Path) -> list[candidates.Candidate]:
    """Every broad handler and every handler logging `.exception(` that the sweep does not already report."""
    files = parse_audited_files(scope)
    hits = capture_hits(scope, A19_CHECKS)
    found: list[candidates.Candidate] = []
    for file in files:
        scopes = scope_nodes(file.tree)
        counter = SiteCounter()
        for qualname, node in walk_with_qualname(file.tree):
            if not isinstance(node, (ast.Try, ast.TryStar)):
                continue
            function = scopes.get(qualname)
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function = None
            try_source = textwrap.dedent('\n'.join(file.lines[node.lineno - 1 : node.end_lineno]))
            for handler in node.handlers:
                log_calls = log_calls_of(handler)
                logs_exception = any(call.startswith('exception: ') for call in log_calls)
                if not (auditme.rules.error_handling.is_broad_handler(handler) or logs_exception):
                    continue
                number = counter.next(f'{qualname}::except')
                if hit_on_anchor(hits, file.rel, handler_anchor_lines(handler, function), A19_RULES):
                    continue
                function_source = textwrap.dedent('\n'.join(file.lines[function.lineno - 1 : function.end_lineno])) if function is not None else try_source
                handler_source = textwrap.dedent('\n'.join(file.lines[handler.lineno - 1 : handler.end_lineno]))
                found.append(
                    candidates.Candidate(
                        question='A19',
                        id=f'{file.rel}::{qualname}::except#{number}',
                        path=file.rel,
                        start=handler.lineno,
                        end=handler.end_lineno or handler.lineno,
                        payload={
                            'handler': handler_source,
                            'try': try_source,
                            'function': function_summary(function) if function is not None else None,
                            'log_calls': log_calls,
                        },
                        hash=candidates.digest([function_source.encode('utf-8')]),
                    )
                )
    return found


A1_BRIEF = candidates.DOC_BRIEFS / 'A1.md'
A1_RULES = ('filesystem-envelope-gap', 'filesystem-op-without-envelope', 'translator-envelope-gap')
A1_CHECKS = (
    auditme.rules.error_handling.check_filesystem_envelope_gap,
    auditme.rules.error_handling.check_filesystem_op_without_envelope,
    auditme.rules.error_handling.check_translator_envelope_gap,
)
A1_CLIENT_MODULES = ('boto3', 'botocore', 'httpx', 'huggingface_hub', 'mlflow', 'requests', 'sqlalchemy', 'sqlite3', 'urllib.request')
A1_ROOTED_MODULES = ('subprocess', *A1_CLIENT_MODULES)
A1_CLIENT_METHODS = frozenset({'commit', 'download_file', 'execute', 'executemany', 'get_object', 'put_object', 'upload_file'})
A1_WRITE_METHODS = frozenset({'to_csv', 'to_excel', 'to_feather', 'to_hdf', 'to_json', 'to_parquet', 'to_pickle', 'to_sql'})
A1_TORCH_CALLS = frozenset({'torch.load', 'torch.save'})


@dataclasses.dataclass(frozen=True)
class Scope:
    """Where a call sits: its qualname, enclosing function and class, and innermost `try` body."""

    qualname: str
    function: FunctionNode | None
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
        inner = Scope(child_qualname(scope.qualname, node.name), node, scope.function is not None, scope.cls, None)
        for statement in node.body:
            yield from call_sites(statement, inner)
    elif isinstance(node, ast.ClassDef):
        for part in [*node.decorator_list, *node.bases]:
            yield from call_sites(part, scope)
        inner = Scope(child_qualname(scope.qualname, node.name), None, scope.function is not None, node.name, None)
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
    if short in auditme.rules.error_handling.FILESYSTEM_TOUCHING_CALLS or (isinstance(func, ast.Name) and short == 'open'):
        return True
    if isinstance(func, ast.Attribute) and short in A1_WRITE_METHODS:
        return True
    text = dotted_name(func)
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


def package_domain_errors(files: list[ParsedSource]) -> dict[str, list[str]]:
    """The domain errors each top-level package defines: classes named `*Error` that reach `Exception`."""
    by_package: dict[str, list[ParsedSource]] = collections.defaultdict(list)
    for file in files:
        by_package[file.module.partition('.')[0]].append(file)
    errors: dict[str, list[str]] = {}
    for package, members in by_package.items():
        parents = auditme.rules.error_handling.package_class_parents(member.tree for member in members)
        names = sorted(name for name in parents if name.endswith('Error') and reaches_exception(auditme.rules.error_handling.class_lineage(name, parents)))
        if names:
            errors[package] = names
    return errors


def known_functions(files: list[ParsedSource]) -> dict[str, str | None]:
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


def source_text(file: ParsedSource, node: ast.AST) -> str:
    """The dedented source lines of a statement or function, including its decorators."""
    first = min([node.lineno, *(decorator.lineno for decorator in getattr(node, 'decorator_list', []))])  # type: ignore[attr-defined]
    return textwrap.dedent('\n'.join(file.lines[first - 1 : node.end_lineno]))  # type: ignore[attr-defined]


def envelope_names(function: FunctionNode | None, catches: dict[str, frozenset[str]]) -> list[str]:
    """The translating decorators and `with` contextmanagers on a function, in source order, without repeats."""
    if function is None:
        return []
    names: list[str] = [auditme.rules.error_handling.callable_short_name(decorator) or '' for decorator in function.decorator_list]
    for node in ast.walk(function):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            names.extend(auditme.rules.error_handling.callable_short_name(item.context_expr) or '' for item in node.items)
    return list(dict.fromkeys(name for name in names if name in catches))


def site_envelope(site: CallSite, catches: dict[str, frozenset[str]], file: ParsedSource) -> dict[str, str | list[str] | None] | None:
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


@candidates.register_question('A1', A1_BRIEF)
def list_a1_candidates(scope: pathlib.Path) -> list[candidates.Candidate]:
    """Every external call in a package with a domain error that the sweep does not already report.

    A call in a private or nested helper lists its resolved callers, because
    whether the helper is covered depends on how each caller calls it. Test
    files are neither listed nor counted as callers.
    """
    files = parse_audited_files(scope)
    hits = capture_hits(scope, A1_CHECKS)
    domain_errors = package_domain_errors(files)
    catches: dict[str, frozenset[str]] = {}
    for src_root in auditme.core._audit_roots(scope):
        for name, caught in auditme.rules.error_handling.translator_envelopes(src_root).items():
            catches[name] = catches.get(name, frozenset()) | caught
    envelope_sources: dict[str, list[str]] = collections.defaultdict(list)
    for file in files:
        for node in ast.walk(file.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in catches:
                envelope_sources[node.name].append(source_text(file, node))
    known = known_functions(files)
    bindings = {file.module: auditme.core.call_bindings(file.tree, file.module, file.path.name == '__init__.py') for file in files}
    aliases = auditme.core.reexport_aliases(
        {file.module: auditme.core.from_import_bindings(file.tree, file.module, file.path.name == '__init__.py') for file in files},
        known,
    )
    sites: dict[str, list[CallSite]] = {}
    callers_of: dict[str, list[tuple[ParsedSource, CallSite]]] = collections.defaultdict(list)
    for file in files:
        if testmap.is_test_relpath(file.rel):
            continue
        sites[file.rel] = list(call_sites(file.tree, Scope(MODULE_QUALNAME, None, False, None, None)))
        for site in sites[file.rel]:
            target = auditme.core.resolve_call(site.call, file.module, site.scope.cls, bindings[file.module], known, aliases, class_methods=True)
            if target is not None:
                callers_of[target].append((file, site))

    def caller_entries(file: ParsedSource, site: CallSite) -> list[tuple[ParsedSource, CallSite]]:
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
        return callers_of.get(f'{file.module}.{helper.qualname}', []) if auditme.core.is_private(helper.qualname, file.module, scope) else []

    found: list[candidates.Candidate] = []
    for file in files:
        if testmap.is_test_relpath(file.rel) or file.module.partition('.')[0] not in domain_errors:
            continue
        errors = domain_errors[file.module.partition('.')[0]]
        imports = import_targets(file.tree)
        counter = SiteCounter()
        for site in sites[file.rel]:
            if not is_external_call(site.call, imports):
                continue
            callee = ast.unparse(site.call.func)
            number = counter.next(f'{site.scope.qualname}::call:{callee}')
            if hit_on_anchor(hits, file.rel, a1_anchor_lines(site), A1_RULES):
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
            helper_sites = (
                caller_entries(file, site)
                if site.scope.function is not None and (site.scope.nested or auditme.core.is_private(site.scope.qualname, file.module, scope))
                else None
            )
            if helper_sites is not None:
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
                candidates.Candidate(
                    question='A1',
                    id=f'{file.rel}::{site.scope.qualname}::call:{callee}#{number}',
                    path=file.rel,
                    start=site.call.lineno,
                    end=site.call.end_lineno or site.call.lineno,
                    payload=payload,
                    hash=candidates.digest([part.encode('utf-8') for part in parts]),
                )
            )
    return found


A17_BRIEF = candidates.DOC_BRIEFS / 'A17.md'
A17_SHIM_RULE = 'migration-shim-consumer'
A17_CHECKS = (
    auditme.rules.imports_and_surfaces.check_empty_init_with_exporting_siblings,
    auditme.rules.imports_and_surfaces.check_migration_shim_consumers,
)


def dunder_all_names(tree: ast.Module) -> list[str] | None:
    """The string members of the module's `__all__`, or None when it has none."""
    names: list[str] | None = None
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and auditme.core.is_dunder_all_assignment(node):
            names = []
            if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                names = [element.value for element in node.value.elts if isinstance(element, ast.Constant) and isinstance(element.value, str)]
    return names


def entry_point_targets(scope: pathlib.Path) -> list[tuple[str, str, str]]:
    """Each `[project.scripts]` and `[project.entry-points]` target of `pyproject.toml` as (module, name, text)."""
    pyproject = scope / 'pyproject.toml'
    if not pyproject.is_file():
        return []
    try:
        project = tomllib.loads(pyproject.read_text(encoding='utf-8')).get('project', {})
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise PhaseBError(f'cannot parse {pyproject}: {error}') from error
    tables = [project.get('scripts', {})]
    tables.extend(project.get('entry-points', {}).values())
    targets: list[tuple[str, str, str]] = []
    for table in tables:
        for key, value in table.items():
            module, _, name = str(value).partition(':')
            targets.append((module.strip(), name.partition('[')[0].strip(), f'pyproject.toml: {key} = "{value}"'))
    return targets


@candidates.register_question('A17', A17_BRIEF)
def list_a17_candidates(scope: pathlib.Path) -> list[candidates.Candidate]:
    """Every `__init__.py` with an `__all__` or no exports, with who reads from it.

    A reader in the package's own directory or the test tree is not a
    consumer. A consumer line a `migration-shim-consumer` hit names is left
    out, and an `__init__.py` with an `empty-init-while-siblings-export` hit
    is not listed.
    """
    files = parse_audited_files(scope)
    roots = auditme.core._audit_roots(scope)
    if not roots:
        return []
    hits = capture_hits(scope, A17_CHECKS)
    reads = auditme.core.reads_by_module_and_name(scope, roots[0])
    entry_points = entry_point_targets(scope)
    line_cache: dict[pathlib.Path, list[str]] = {}

    def read_entries(module: str, names: collections.abc.Iterable[str] | None, directory: str) -> list[tuple[str, str]]:
        """Each outside read of `module` or its submodules, as (name, entry), by the read's name when `names` is None."""
        wanted = None if names is None else set(names)
        entries: list[tuple[str, str]] = []
        for (read_module, name), where in sorted(reads.items()):
            if not (read_module == module or read_module.startswith(f'{module}.')) or (wanted is not None and name not in wanted):
                continue
            if names is None and read_module == module:
                continue
            for path, line in where:
                rel = auditme.core._relpath(path, scope)
                if rel.startswith(f'{directory}/') or testmap.is_test_relpath(rel) or (A17_SHIM_RULE, rel, line) in hits:
                    continue
                text = line_cache.setdefault(path, path.read_text(encoding='utf-8').splitlines())[line - 1].strip()
                entries.append((name, f'{rel}: {text}'))
        for entry_module, entry_name, text in entry_points:
            if (
                (entry_module == module or entry_module.startswith(f'{module}.'))
                and (wanted is None or entry_name in wanted)
                and not (names is None and entry_module == module)
            ):
                entries.append((entry_name, text))
        return entries

    found: list[candidates.Candidate] = []
    for file in files:
        if file.path.name != '__init__.py':
            continue
        names = dunder_all_names(file.tree)
        exports_nothing = names is None and not any(isinstance(node, ast.ImportFrom) for node in file.tree.body)
        if names is None and not exports_nothing:
            continue
        if hit_on_anchor(hits, file.rel, [1], ('empty-init-while-siblings-export',)):
            continue
        directory = str(pathlib.PurePosixPath(file.rel).parent)
        payload: dict[str, object] = {}
        keyed: list[tuple[str, str]]
        if names is not None:
            keyed = read_entries(file.module, names, directory)
            payload['all'] = names
            payload['consumers'] = {name: sorted({entry for key, entry in keyed if key == name}) for name in names}
        else:
            keyed = read_entries(file.module, None, directory)
            payload['all'] = []
            payload['consumers'] = {}
            payload['reach_ins'] = sorted({entry for _, entry in keyed})
        source = '\n'.join(file.lines)
        parts = [source, *(f'{name}\t{entry}' for name, entry in sorted(set(keyed)))]
        found.append(
            candidates.Candidate(
                question='A17',
                id=file.rel,
                path=file.rel,
                start=1,
                end=max(len(file.lines), 1),
                payload=payload,
                hash=candidates.digest([part.encode('utf-8') for part in parts]),
            )
        )
    return found
