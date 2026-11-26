"""String-dispatch site finders.

The `assert-never-missing` rule reports what `assert_never_findings` yields,
and the Phase B A11 lister reads the same chain walker without running the
rule. Both read them from here, so that the lister needs no check function.
The rule reaches them through the helper API.
"""

import ast
import dataclasses
import typing

if typing.TYPE_CHECKING:
    import collections.abc


@dataclasses.dataclass(frozen=True)
class IfChain:
    """An `if/elif/...` chain whose every test names the same subject."""

    subject: str
    tests: list[ast.expr]
    orelse: list[ast.stmt] | None


def if_chain(node: ast.If, subject_of: collections.abc.Callable[[ast.expr], str | None]) -> IfChain | None:
    """Walk the `elif` chain starting at `node`.

    Return None when a test has no subject (`subject_of` returns None) or two
    tests name different subjects. `orelse` is the body of a final plain
    `else`, or None when the chain has none."""
    subject: str | None = None
    tests: list[ast.expr] = []
    orelse: list[ast.stmt] | None = None
    cursor: ast.If | None = node
    while cursor is not None:
        name = subject_of(cursor.test)
        if name is None or (subject is not None and name != subject):
            return None
        subject = name
        tests.append(cursor.test)
        rest = cursor.orelse
        if not rest:
            cursor = None
        elif len(rest) == 1 and isinstance(rest[0], ast.If):
            cursor = rest[0]
        else:
            orelse = rest
            cursor = None
    if subject is None:
        return None
    return IfChain(subject=subject, tests=tests, orelse=orelse)


def ends_in_assert_never(body: list[ast.stmt] | None) -> bool:
    """True when a statement list calls a function whose name contains `assert_never`."""
    return any(isinstance(sub, ast.Call) and 'assert_never' in ast.unparse(sub.func) for stmt in body or [] for sub in ast.walk(stmt))


def literal_member_count(function: ast.FunctionDef | ast.AsyncFunctionDef | None, subject: str) -> int:
    """String members of the `Literal[...]` the function annotates `subject` with, as a parameter or a local; else 0."""
    if function is None:
        return 0
    arguments = function.args
    annotations = [
        argument.annotation
        for argument in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs, arguments.vararg, arguments.kwarg]
        if argument is not None and argument.arg == subject and argument.annotation is not None
    ]
    annotations += [node.annotation for node in ast.walk(function) if isinstance(node, ast.AnnAssign) and ast.unparse(node.target) == subject]
    for annotation in annotations:
        if isinstance(annotation, ast.Subscript) and ast.unparse(annotation.value).rpartition('.')[2] == 'Literal':
            members = annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
            return sum(isinstance(member, ast.Constant) and isinstance(member.value, str) for member in members)
    return 0


def match_string_cases(node: ast.Match) -> int:
    """How many `case` patterns are a string constant or a `|` of them."""

    def is_string_pattern(pattern: ast.pattern) -> bool:
        if isinstance(pattern, ast.MatchValue):
            return isinstance(pattern.value, ast.Constant) and isinstance(pattern.value.value, str)
        return isinstance(pattern, ast.MatchOr) and all(is_string_pattern(sub) for sub in pattern.patterns)

    return sum(is_string_pattern(case.pattern) for case in node.cases)


def assert_never_sites(
    tree: ast.AST,
) -> collections.abc.Iterator[tuple[ast.If | ast.Match, str, int, list[ast.stmt] | None, bool]]:
    """Each chain head or `match` as (node, subject, arm count, final else body, a third value is known).

    A `match` reports its last case body as the else body; a two-arm chain is "known" three-valued
    when its subject is annotated `Literal[...]` with three or more string members."""
    else_ifs = {id(node.orelse[0]) for node in ast.walk(tree) if isinstance(node, ast.If) and len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)}
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    owner: dict[int, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for function in functions:
        owner.update({id(inner): function for inner in ast.walk(function)})
    for node in ast.walk(tree):
        function = owner.get(id(node))
        if isinstance(node, ast.If) and id(node) not in else_ifs:
            chain = if_chain(node, extract_string_eq_var)
            if chain is not None:
                known = literal_member_count(function, chain.subject) >= 3
                yield node, chain.subject, len(chain.tests), chain.orelse, known
        elif isinstance(node, ast.Match):
            last = node.cases[-1] if node.cases else None
            wildcard = last is not None and isinstance(last.pattern, ast.MatchAs) and last.pattern.pattern is None
            yield node, ast.unparse(node.subject), match_string_cases(node), last.body if wildcard and last else None, False


def string_constants(node: ast.expr) -> bool:
    """True for a non-empty tuple, list or set of string constants."""
    return (
        isinstance(node, (ast.Tuple, ast.List, ast.Set))
        and bool(node.elts)
        and all(isinstance(element, ast.Constant) and isinstance(element.value, str) for element in node.elts)
    )


def extract_string_eq_var(test: ast.expr) -> str | None:
    """Return the subject's source text (a name or dotted name) if `test` is
    `subject == "literal"`, `"literal" == subject` or `subject in ("a", "b")`,
    otherwise None."""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return None
    left, right = test.left, test.comparators[0]

    def is_subject(node: ast.expr) -> bool:
        while isinstance(node, ast.Attribute):
            node = node.value
        return isinstance(node, ast.Name)

    def is_string(node: ast.expr) -> bool:
        return isinstance(node, ast.Constant) and isinstance(node.value, str)

    if isinstance(test.ops[0], ast.Eq):
        if is_subject(left) and is_string(right):
            return ast.unparse(left)
        if is_subject(right) and is_string(left):
            return ast.unparse(right)
    elif isinstance(test.ops[0], ast.In) and is_subject(left) and string_constants(right):
        return ast.unparse(left)
    return None


def assert_never_findings(tree: ast.AST) -> collections.abc.Iterator[tuple[ast.If | ast.Match, str, int, list[ast.stmt] | None]]:
    """Each dispatch site that should end in `assert_never` and does not, as (node, subject, arm count, final else body)."""
    for node, subject, arms, terminal_else, known in assert_never_sites(tree):
        if arms < (2 if known else 3) or ends_in_assert_never(terminal_else):
            continue
        yield node, subject, arms, terminal_else
