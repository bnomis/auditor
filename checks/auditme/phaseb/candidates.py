"""The Phase B data model and the registry of per-question candidate listers."""

import ast
import builtins
import collections.abc
import dataclasses
import hashlib
import pathlib
import re
import typing

import auditme.core
import auditme.rules.error_handling
from auditme.phaseb.errors import PhaseBError


@dataclasses.dataclass(frozen=True)
class Candidate:
    """One site a question applies to."""

    question: str  # e.g. 'A4'
    id: str  # '<repo-relative path>::<qualname>'
    path: str
    start: int
    end: int
    payload: dict[str, typing.Any]  # question-specific; A4: raises, callees, unresolved
    hash: str  # sha256 hex over the candidate's source and its callees' source


@dataclasses.dataclass(frozen=True)
class Verdict:
    """One reviewer's ruling on one candidate."""

    question: str
    id: str
    hash: str  # the candidate hash it was judged against
    brief_version: int
    findings: dict[str, list[str]]  # A4: {'missing': [...], 'extra': [...]}
    reason: str
    judged: str  # ISO date
    dismissed: str | None = None  # 'YYYY-MM-DD: <reason>' once the operator dismisses it

    @property
    def flagged(self) -> bool:
        """True when any findings list is non-empty and the verdict is not dismissed."""
        return self.dismissed is None and any(self.findings.values())


Lister = collections.abc.Callable[[pathlib.Path], list[Candidate]]

DEFAULT_BATCH_SIZE = 48

REGISTRY: dict[str, tuple[Lister, pathlib.Path, int]] = {}


def register_question(question: str, brief: pathlib.Path, batch_size: int = DEFAULT_BATCH_SIZE) -> collections.abc.Callable[[Lister], Lister]:
    """Register a candidate lister for a Phase B question, with its brief and batch size.

    The batch size is how many candidates one reviewer judges when `phaseb.py
    plan` is not given `--batch-size`; a question whose candidates are costly
    to judge registers a smaller one.
    """

    def decorate(lister: Lister) -> Lister:
        REGISTRY[question] = (lister, brief, batch_size)
        return lister

    return decorate


def registered(question: str) -> tuple[Lister, pathlib.Path, int]:
    """Return a question's lister, brief path and batch size.

    Raises:
        PhaseBError: question has no registered lister.
    """
    try:
        return REGISTRY[question]
    except KeyError:
        raise PhaseBError(f'no Phase B lister is registered for question {question!r}; known: {sorted(REGISTRY)}') from None


def question_brief(question: str) -> pathlib.Path:
    """Return the path of a question's brief.

    Raises:
        PhaseBError: question has no registered lister.
    """
    return registered(question)[1]


def question_batch_size(question: str) -> int:
    """Return the number of candidates one reviewer judges for a question.

    Raises:
        PhaseBError: question has no registered lister.
    """
    return registered(question)[2]


def list_candidates(question: str, root: pathlib.Path, depth: int | None = None) -> list[Candidate]:
    """List every candidate for question under root, sorted by id.

    A depth is handed to the lister, which follows callees that far; without
    one the lister uses its own default.

    Raises:
        PhaseBError: question has no registered lister.
    """
    lister, _, _ = registered(question)
    found = lister(root) if depth is None else lister(root, depth)  # type: ignore[call-arg]
    return sorted(found, key=lambda candidate: candidate.id)


BRIEF_VERSION_LINE = re.compile(r'^\*\*Brief version:\*\*\s*(\d+)\s*$', re.MULTILINE)


def brief_version(brief: pathlib.Path) -> int:
    """Return the version a brief declares on its `**Brief version:** N` line.

    Raises:
        PhaseBError: the brief cannot be read or has not exactly one version line.
    """
    try:
        text = brief.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as error:
        raise PhaseBError(f'cannot read brief {brief}: {error}') from error
    found = BRIEF_VERSION_LINE.findall(text)
    if len(found) != 1 or int(found[0]) < 1:
        raise PhaseBError(f'brief {brief} must have exactly one `**Brief version:** N` line with N a positive integer')
    return int(found[0])


DEFAULT_DEPTH = 3
A4_BRIEF = pathlib.Path(__file__).resolve().parents[3] / 'phaseb' / 'briefs' / 'A4.md'

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclasses.dataclass(frozen=True)
class Site:
    """One function or method a root defines, with where it lives."""

    module: str
    qualname: str  # dotted, as the resolver knows it
    cls: str | None
    node: FunctionNode
    path: str  # repo-relative
    lines: list[str]

    @property
    def id(self) -> str:
        return f'{self.path}::{self.qualname.removeprefix(self.module + ".")}'

    @property
    def start(self) -> int:
        return min([self.node.lineno, *(decorator.lineno for decorator in self.node.decorator_list)])

    @property
    def end(self) -> int:
        return self.node.end_lineno or self.node.lineno

    @property
    def source(self) -> str:
        return '\n'.join(self.lines[self.start - 1 : self.end])


def is_stub(node: FunctionNode) -> bool:
    """True for an abstract or protocol body (D2): `...`, `pass`, a docstring alone or `raise NotImplementedError`."""
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    if not body:
        return True
    if len(body) != 1:
        return False
    only = body[0]
    if isinstance(only, ast.Pass):
        return True
    if isinstance(only, ast.Expr) and isinstance(only.value, ast.Constant) and only.value.value is Ellipsis:
        return True
    if isinstance(only, ast.Raise) and only.exc is not None:
        raised = only.exc.func if isinstance(only.exc, ast.Call) else only.exc
        return isinstance(raised, ast.Name) and raised.id == 'NotImplementedError'
    return False


def is_builtin_call(call: ast.Call, site: Site, imported: collections.abc.Mapping[str, str], known: collections.abc.Mapping[str, str | None]) -> bool:
    """True for a bare-name call to a builtin that the module neither imports nor defines."""
    func = call.func
    return isinstance(func, ast.Name) and hasattr(builtins, func.id) and func.id not in imported and f'{site.module}.{func.id}' not in known


def root_sites(scope: pathlib.Path, src_root: pathlib.Path) -> tuple[list[Site], dict[str, ast.Module], dict[str, bool]]:
    """Every top-level function and class method under one audited root, with each module's tree and package flag."""
    sites: list[Site] = []
    trees: dict[str, ast.Module] = {}
    is_package: dict[str, bool] = {}
    for path in auditme.core._all_py_files(src_root):
        lines = auditme.core._source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        module = auditme.core.module_dotted(path, src_root)
        trees[module] = tree
        is_package[module] = path.name == '__init__.py'
        rel = auditme.core._relpath(path, scope)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sites.append(Site(module, f'{module}.{node.name}', None, node, rel, lines))
            elif isinstance(node, ast.ClassDef):
                sites.extend(
                    Site(module, f'{module}.{node.name}.{member.name}', node.name, member, rel, lines)
                    for member in node.body
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
    return sites, trees, is_package


def root_candidates(scope: pathlib.Path, src_root: pathlib.Path, depth: int) -> list[Candidate]:
    """The A4 candidates of one audited root."""
    sites, trees, is_package = root_sites(scope, src_root)
    by_name = {site.qualname: site for site in sites}
    known = {site.qualname: site.cls for site in sites}
    bindings = {module: auditme.core.call_bindings(tree, module, is_package[module]) for module, tree in trees.items()}
    aliases = auditme.core.reexport_aliases(
        {module: auditme.core.from_import_bindings(tree, module, is_package[module]) for module, tree in trees.items()},
        known,
    )

    def calls_of(site: Site) -> list[tuple[ast.Call, str | None]]:
        return [
            (call, auditme.core.resolve_call(call, site.module, site.cls, bindings[site.module], known, aliases, class_methods=True))
            for call in ast.walk(site.node)
            if isinstance(call, ast.Call)
        ]

    direct = {site.qualname: sorted({callee for _, callee in calls_of(site) if callee and callee != site.qualname}) for site in sites}

    def reach(site: Site) -> list[Site]:
        seen = {site.qualname}
        frontier = [site.qualname]
        for _ in range(depth):
            frontier = [callee for name in frontier for callee in direct[name] if callee not in seen]
            seen.update(frontier)
        return sorted((by_name[name] for name in seen - {site.qualname}), key=lambda callee: callee.id)

    found: list[Candidate] = []
    for site in sites:
        doc = ast.get_docstring(site.node) or ''
        if 'Raises:' not in doc or is_stub(site.node) or not auditme.rules.error_handling.raises_section_names(doc):
            continue
        callees = reach(site)
        unresolved = [
            {'at': f'{site.path}:{call.lineno}', 'text': ast.unparse(call)}
            for call, callee in calls_of(site)
            if callee is None and not is_builtin_call(call, site, bindings[site.module], known)
        ]
        digest = hashlib.sha256('\0'.join([site.source, *(callee.source for callee in callees)]).encode('utf-8')).hexdigest()
        found.append(
            Candidate(
                question='A4',
                id=site.id,
                path=site.path,
                start=site.start,
                end=site.end,
                payload={
                    'raises': doc[doc.index('Raises:') :],
                    'callees': [{'id': callee.id, 'path': callee.path, 'start': callee.start, 'end': callee.end} for callee in callees],
                    'unresolved': unresolved,
                },
                hash=digest,
            )
        )
    return found


@register_question('A4', A4_BRIEF)
def list_a4_candidates(scope: pathlib.Path, depth: int = DEFAULT_DEPTH) -> list[Candidate]:
    """List every function or method with a `Raises:` section under the audited roots, minus D2's stubs.

    Each carries its section, its resolved callees to `depth` (resolving
    `<ClassName>.<method>(...)` too), its unresolved calls, and a sha256 over
    its source then its callees' source in id order, NUL-separated.
    """
    return [candidate for src_root in auditme.core._audit_roots(scope) for candidate in root_candidates(scope, src_root, depth)]
