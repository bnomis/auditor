"""The A11 lister: every site the A11 question applies to."""

import ast
import textwrap
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib

A11_RULES = ('assert-never-missing',)


def is_constant_operand(node: ast.expr) -> bool:
    """A string constant, an attribute constant (`Mode.FAST`) or a tuple, list or set of them."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.Attribute):
        return auditor.api.dotted_name(node) is not None
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
    left_name = auditor.api.dotted_name(test.left)
    if left_name is not None and is_constant_operand(right):
        return left_name
    if isinstance(operator, ast.Eq) and isinstance(test.left, ast.Constant) and isinstance(test.left.value, str):
        return auditor.api.dotted_name(right)
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


def annotation_of(subject: str, function: auditor.api.FunctionNode | None, owner: ast.AST | None) -> str | None:
    """The subject's annotation: a parameter, a local annotation or a class field, else None."""
    if function is not None:
        arguments = function.args
        for argument in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs, arguments.vararg, arguments.kwarg]:
            if argument is not None and argument.arg == subject and argument.annotation is not None:
                return ast.unparse(argument.annotation)
        for node in ast.walk(function):
            if isinstance(node, ast.AnnAssign) and auditor.api.dotted_name(node.target) == subject:
                return ast.unparse(node.annotation)
    if isinstance(owner, ast.ClassDef) and subject.startswith('self.'):
        field = subject.removeprefix('self.')
        for node in owner.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == field:
                return ast.unparse(node.annotation)
    return None


def is_enum_class(node: ast.ClassDef) -> bool:
    """True when a base is one of the standard enum classes, named or dotted."""
    return any((auditor.api.dotted_name(base) or '').rpartition('.')[2] in auditor.api.T2_ENUM_BASES for base in node.bases)


def literal_alias(node: ast.AST) -> str | None:
    """The alias name when the statement binds a name to a `Literal[...]` type, else None."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        name, value = auditor.api.dotted_name(node.targets[0]), node.value
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        name, value = auditor.api.dotted_name(node.target), node.value
    elif isinstance(node, ast.TypeAlias):
        name, value = auditor.api.dotted_name(node.name), node.value
    else:
        return None
    if name is None or not isinstance(value, ast.Subscript):
        return None
    return name if (auditor.api.dotted_name(value.value) or '').rpartition('.')[2] == 'Literal' else None


def typing_aliases(files: list[auditor.api.ParsedSource]) -> dict[str, str]:
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


def assert_never_hits(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Emit each `assert-never-missing` site, as the rule does, for `capture_hits`."""
    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node, _, _, _ in auditor.api.assert_never_findings(tree):
            auditor.api.emit(
                rule='assert-never-missing',
                variant='',
                path=auditor.api.relpath(path, scope),
                line=node.lineno,
                evidence='',
                accepted=False,
                accepted_reason=None,
            )


def a11_site(node: ast.AST, flags: dict[str, str]) -> tuple[str, str] | None:
    """(kind, subject) when the node is an A11 site: a chain head, a two-way split or a `match`."""
    if isinstance(node, ast.Match):
        return 'match', ast.unparse(node.subject)
    if not isinstance(node, ast.If):
        return None
    chain = auditor.api.if_chain(node, comparison_subject)
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
    names = auditor.api.annotation_names(ast.parse(annotation, mode='eval').body)
    return next((aliases[name] for name in sorted(names) if name in aliases), None)


# auditme: accept[duplicate-call-sequence] each question lists its own sites; the shared opening is the API call that reads the audited files
def list_candidates(scope: pathlib.Path) -> list[auditor.api.Candidate]:
    """Every if chain, two-way split on a comparison flag and `match` the sweep does not already report."""
    files = auditor.api.read_audited_files(scope)
    hits = auditor.api.capture_hits(scope, [assert_never_hits])
    aliases = typing_aliases(files)
    found: list[auditor.api.Candidate] = []
    for file in files:
        scopes = auditor.api.scope_nodes(file.tree)
        else_ifs = else_if_nodes(file.tree)
        counter = auditor.api.SiteCounter()
        flags_by_scope: dict[str, dict[str, str]] = {}
        for qualname, node in auditor.api.walk_with_qualname(file.tree):
            if id(node) in else_ifs or not isinstance(node, ast.stmt):
                continue
            function = scopes.get(qualname)
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function = None
            if function is not None and qualname not in flags_by_scope:
                flags_by_scope[qualname] = flag_subjects(function)
            site = a11_site(node, flags_by_scope.get(qualname, {}))
            if site is None or auditor.api.hit_on_anchor(hits, file.rel, [node.lineno], A11_RULES):
                continue
            kind, subject = site
            number = counter.next(f'{qualname}::{kind}:{subject}')
            owner = scopes.get(qualname.rpartition('.')[0]) if function is not None else None
            annotation = annotation_of(subject, function, owner)
            type_source = type_source_of(annotation, aliases)
            source = textwrap.dedent('\n'.join(file.lines[node.lineno - 1 : node.end_lineno]))
            found.append(
                auditor.api.span_candidate(
                    'A11',
                    f'{file.rel}::{qualname}::{kind}:{subject}#{number}',
                    file.rel,
                    node.lineno,
                    node.end_lineno or node.lineno,
                    {'source': source, 'subject': subject, 'annotation': annotation, 'type_source': type_source},
                    [source, subject, annotation or '', type_source or ''],
                )
            )
    return found
