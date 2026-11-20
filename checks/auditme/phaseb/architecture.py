"""Architecture questions: the listers for A11, A19, A1 and A17 and their shared helpers.

`capture_hits` runs sweep rules and returns where they hit, so a lister can
drop a site the sweep already reports. The other helpers parse every audited
file, number the sites in a qualname and walk a tree with qualified names.
"""

import ast
import collections
import collections.abc
import contextlib
import dataclasses
import io
import json
import pathlib
import textwrap

import auditme.core
import auditme.rules.error_handling
import auditme.rules.state_and_effects
from auditme.phaseb import candidates
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
