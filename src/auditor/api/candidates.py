"""Shared helpers of the Phase B listers: the candidate model, the site index and the hashing every lister uses."""

import ast
import collections
import collections.abc
import contextlib
import dataclasses
import hashlib
import io
import json
import pathlib
import typing

import auditor.api.base
import auditor.api.docrefs
import auditor.api.testmap
import auditor.core
import auditor.dispatch
import auditor.errorsites
import auditor.hygiene
import auditor.surface


@dataclasses.dataclass(frozen=True)
class Candidate:
    """One site a question applies to."""

    question: str  # e.g. 'A4'
    id: str  # '<repo-relative path>::<qualname>'; the A17 lister uses the path alone, one candidate per `__init__.py`
    path: str
    start: int
    end: int
    payload: dict[str, typing.Any]  # question-specific; A4: raises, callees, unresolved
    hash: str  # sha256 hex over the candidate's source and its callees' source


def read_test_files(scope: pathlib.Path, names: collections.abc.Iterable[str]) -> list[bytes]:
    """Read each named test file under `scope`, for hashing into a candidate.

    Raises:
        PhaseBError: a test file cannot be read.
    """
    try:
        return [auditor.core.cached_bytes(scope / name) for name in names]
    except OSError as error:
        raise auditor.api.base.PhaseBError(f'cannot read test file under {scope}') from error


DEFAULT_DEPTH = 3


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


def module_sites(module: str, tree: ast.Module, rel: str, lines: list[str]) -> list[Site]:
    """Every top-level function and class method a parsed module defines."""
    sites: list[Site] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sites.append(Site(module, f'{module}.{node.name}', None, node, rel, lines))
        elif isinstance(node, ast.ClassDef):
            sites.extend(
                Site(module, f'{module}.{node.name}.{member.name}', node.name, member, rel, lines)
                for member in node.body
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
    return sites


def site_candidate(question: str, site: Site, payload: dict[str, typing.Any], hash: str) -> Candidate:
    """The candidate for one function or method."""
    return Candidate(question=question, id=site.id, path=site.path, start=site.start, end=site.end, payload=payload, hash=hash)


def span_candidate(question: str, id: str, path: str, start: int, end: int, payload: dict[str, typing.Any], hash_parts: list[str]) -> Candidate:
    """The candidate for a line span of one file, hashed over `hash_parts`."""
    return Candidate(question=question, id=id, path=path, start=start, end=end, payload=payload, hash=digest([part.encode('utf-8') for part in hash_parts]))


def section_candidate(question: str, id: str, section: auditor.api.docrefs.DocSection, payload: dict[str, typing.Any], hash: str) -> Candidate:
    """The candidate for one document section."""
    return Candidate(question=question, id=id, path=section.doc, start=section.start, end=section.end, payload=payload, hash=hash)


DOC_BATCH_SIZE = 24


UNRESOLVED = '(unresolved)'


def read_text(path: pathlib.Path) -> str:
    """Return a listed document's text.

    Raises:
        PhaseBError: the file cannot be read or decoded as UTF-8.
    """
    try:
        return auditor.core.cached_bytes(path).decode('utf-8')
    except (OSError, UnicodeDecodeError) as error:
        raise auditor.api.base.PhaseBError(f'cannot read {path}') from error


def target_bytes(target: auditor.api.docrefs.DocTarget, index: auditor.api.docrefs.CorpusIndex) -> bytes:
    """The bytes a target's hash covers: its source lines, a file's content or a directory's sorted tracked entries.

    Raises:
        PhaseBError: the target's file cannot be read.
    """
    if target.kind == 'directory':
        return '\n'.join(sorted(name for name in index.files if name.startswith(f'{target.path}/'))).encode('utf-8', errors='surrogateescape')
    try:
        data = auditor.core.cached_bytes(index.scope / target.path)
    except OSError as error:
        raise auditor.api.base.PhaseBError(f'cannot read {target.path}') from error
    if target.kind == 'file':
        return data
    return b'\n'.join(data.splitlines()[target.start - 1 : target.end])


def digest(parts: list[bytes]) -> str:
    return hashlib.sha256(b'\0'.join(parts)).hexdigest()


def doc_candidates(question: str, scope: pathlib.Path, documents: list[pathlib.Path]) -> list[Candidate]:
    """One candidate per (section, target) pair and one `(unresolved)` candidate per section with unresolved names."""
    index = auditor.api.docrefs.CorpusIndex.build(scope)
    found: list[Candidate] = []
    for document in documents:
        lines = read_text(document).splitlines()
        for section in auditor.api.docrefs.read_sections(document, scope):
            text = '\n'.join(lines[section.start - 1 : section.end]).encode('utf-8')
            named: dict[str, tuple[auditor.api.docrefs.DocTarget, list[int]]] = {}
            unresolved: list[dict[str, typing.Any]] = []
            for number, token in section.names:
                targets = auditor.api.docrefs.read_name_targets(token, document, index)
                if len(targets) == 1:
                    named.setdefault(targets[0].id, (targets[0], []))[1].append(number)
                else:
                    unresolved.append({'name': token, 'line': number, 'definitions': [dataclasses.asdict(target) for target in targets]})
            prefix = f'{section.doc}::{section.heading_path}::'
            for target, numbers in named.values():
                found.append(
                    section_candidate(
                        question,
                        prefix + target.id,
                        section,
                        {
                            'target': dataclasses.asdict(target),
                            'lines': [{'line': number, 'text': lines[number - 1].strip()} for number in sorted(set(numbers))],
                        },
                        digest([text, target_bytes(target, index)]),
                    )
                )
            if unresolved:
                tokens = '\n'.join(sorted(entry['name'] for entry in unresolved)).encode('utf-8')
                found.append(section_candidate(question, prefix + UNRESOLVED, section, {'tokens': unresolved}, digest([text, tokens])))
    return found


AGENTS_BATCH_SIZE = 12


AGENTS_DOC = 'AGENTS.md'


def agents_document(scope: pathlib.Path) -> tuple[pathlib.Path, list[str]] | None:
    """The root `AGENTS.md` and its lines, or None when the project has none."""
    path = scope / AGENTS_DOC
    if not path.exists():
        return None
    return path, read_text(path).splitlines()


def is_overload(node: FunctionNode) -> bool:
    """True for a function decorated with `overload` or `typing.overload`."""
    return any(ast.unparse(decorator).rpartition('.')[2] == 'overload' for decorator in node.decorator_list)


T2_ENUM_BASES = frozenset({'Enum', 'Flag', 'IntEnum', 'IntFlag', 'StrEnum'})


def annotation_names(annotation: ast.expr) -> set[str]:
    """Every name an annotation mentions, parsing string annotations."""
    names: set[str] = set()
    for part in ast.walk(annotation):
        if isinstance(part, ast.Name):
            names.add(part.id)
        elif isinstance(part, ast.Attribute):
            names.add(part.attr)
        elif isinstance(part, ast.Constant) and isinstance(part.value, str):
            try:
                names |= annotation_names(ast.parse(part.value, mode='eval').body)
            except SyntaxError:
                continue
    return names


Check = collections.abc.Callable[[pathlib.Path, pathlib.Path], None]


MODULE_QUALNAME = '<module>'


def capture_hits(scope: pathlib.Path, checks: collections.abc.Sequence[Check]) -> set[tuple[str, str, int]]:
    """Run checks over every audit root and return each hit as (rule, path, line).

    Saves and restores `EMITTED` and captures stdout. Accepted hits are included.

    Raises:
        PhaseBError: a check raised; the message names the check.
    """
    saved = set(auditor.core.EMITTED)
    hits: set[tuple[str, str, int]] = set()
    try:
        for check in checks:
            auditor.core.EMITTED.clear()
            buffer = io.StringIO()
            try:
                with contextlib.redirect_stdout(buffer):
                    roots, _ = auditor.core.cached_roots(scope)
                    for src_root in roots:
                        check(scope, src_root)
            except Exception as error:  # a check's failure must stop the lister, whatever its type
                raise auditor.api.base.PhaseBError(f'check {getattr(check, "__name__", check)!r} failed') from error
            for line in buffer.getvalue().splitlines():
                record = json.loads(line)
                hits.add((record['rule'], record['path'], record['line']))
    finally:
        auditor.core.EMITTED.clear()
        auditor.core.EMITTED.update(saved)
    return hits


@dataclasses.dataclass(frozen=True)
class ParsedSource:
    """An audited file parsed once, with its repo-relative path and dotted module."""

    path: pathlib.Path
    rel: str
    module: str
    tree: ast.Module
    lines: list[str]


def read_audited_files(scope: pathlib.Path) -> list[ParsedSource]:
    """Every Python file under an audit root, parsed once, in path order.

    Raises:
        PhaseBError: a file does not parse; the rules skip it, but a skipped
            file would hide its candidates and let `merge` drop their ledger
            entries as vanished.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    files: list[ParsedSource] = []
    roots, _ = auditor.core.cached_roots(scope)
    for src_root in roots:
        for path in auditor.core.all_py_files(src_root):
            try:
                text = path.read_text(encoding='utf-8')
                tree = ast.parse(text)
            except (OSError, UnicodeDecodeError, SyntaxError) as error:
                raise auditor.api.base.PhaseBError(f'cannot parse {path}') from error
            files.append(ParsedSource(path, auditor.core.relpath(path, scope), auditor.core.module_dotted(path, src_root), tree, text.splitlines()))
    return files


class SiteCounter:
    """Numbers the sites of one qualname by order of appearance, from 1.

    An edit in another function does not change a site's number, so candidate
    ids stay stable.
    """

    def __init__(self) -> None:
        self.qualname_counts: collections.Counter[str] = collections.Counter()

    def next(self, qualname: str) -> int:
        """The number of the next site in this qualname."""
        self.qualname_counts[qualname] += 1
        return self.qualname_counts[qualname]


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


def dotted_name(node: ast.AST) -> str | None:
    """The text of a name or a dotted attribute made of names, else None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)
        return None if base is None else f'{base}.{node.attr}'
    return None


def scope_nodes(tree: ast.AST) -> dict[str, ast.AST]:
    """Every function and class below `tree`, by qualname."""
    scopes: dict[str, ast.AST] = {}
    for qualname, node in walk_with_qualname(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scopes[child_qualname(qualname, node.name)] = node
    return scopes


def emit_site(scope: pathlib.Path, path: pathlib.Path, rule: str, lineno: int) -> None:
    """Emit one site under the rule id, as the rule does, for `capture_hits`."""
    auditor.core.emit(rule=rule, variant='', path=auditor.core.relpath(path, scope), line=lineno, evidence='', accepted=False, accepted_reason=None)


__all__ = [
    'DEFAULT_DEPTH',
    'FunctionNode',
    'MODULE_QUALNAME',
    'ParsedSource',
    'Site',
    'SiteCounter',
    'T2_ENUM_BASES',
    'agents_document',
    'annotation_names',
    'capture_hits',
    'child_qualname',
    'digest',
    'doc_candidates',
    'dotted_name',
    'emit_site',
    'hit_on_anchor',
    'is_overload',
    'module_sites',
    'read_audited_files',
    'read_test_files',
    'read_text',
    'scope_nodes',
    'section_candidate',
    'site_candidate',
    'span_candidate',
    'walk_with_qualname',
]
