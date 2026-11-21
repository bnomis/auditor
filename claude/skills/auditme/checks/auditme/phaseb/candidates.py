"""The Phase B data model and the registry of per-question candidate listers."""

import ast
import builtins
import collections.abc
import dataclasses
import hashlib
import json
import pathlib
import re
import tomllib
import typing

import auditme.core
import auditme.phaseb.docrefs
import auditme.phaseb.errors
import auditme.phaseb.testmap
import auditme.rules.error_handling
import auditme.rules.project_hygiene


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
    findings: dict[str, list[str]]  # one list per registered kind
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
KINDS: dict[str, tuple[str, ...]] = {}


def read_test_files(scope: pathlib.Path, names: collections.abc.Iterable[str]) -> list[bytes]:
    """Read each named test file under `scope`, for hashing into a candidate.

    Raises:
        PhaseBError: a test file cannot be read.
    """
    try:
        return [(scope / name).read_bytes() for name in names]
    except OSError as error:
        raise auditme.phaseb.errors.PhaseBError(f'cannot read test file under {scope}: {error}') from error


def register_question(
    question: str, brief: pathlib.Path, kinds: tuple[str, ...], batch_size: int = DEFAULT_BATCH_SIZE
) -> collections.abc.Callable[[Lister], Lister]:
    """Register a candidate lister for a Phase B question, with its brief, finding kinds and batch size.

    The kinds are the keys of the `findings` object in the question's result
    line, in the order the brief names them. The batch size is how many
    candidates one reviewer judges when `phaseb.py plan` is not given
    `--batch-size`; a question whose candidates are costly to judge registers
    a smaller one.

    Raises:
        PhaseBError: kinds is empty or names a kind twice.
    """
    if not kinds:
        raise auditme.phaseb.errors.PhaseBError(f'question {question!r} registers no finding kinds')
    if len(set(kinds)) != len(kinds):
        raise auditme.phaseb.errors.PhaseBError(f'question {question!r} registers a finding kind twice: {list(kinds)}')

    def decorate(lister: Lister) -> Lister:
        REGISTRY[question] = (lister, brief, batch_size)
        KINDS[question] = tuple(kinds)
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
        raise auditme.phaseb.errors.PhaseBError(f'no Phase B lister is registered for question {question!r}; known: {sorted(REGISTRY)}') from None


def question_brief(question: str) -> pathlib.Path:
    """Return the path of a question's brief.

    Raises:
        PhaseBError: question has no registered lister.
    """
    return registered(question)[1]


def question_kinds(question: str) -> tuple[str, ...]:
    """Return the finding kinds registered for a question.

    Raises:
        PhaseBError: question has no registered lister.
    """
    registered(question)
    return KINDS[question]


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
        raise auditme.phaseb.errors.PhaseBError(f'cannot read brief {brief}') from error
    found = BRIEF_VERSION_LINE.findall(text)
    if len(found) != 1 or int(found[0]) < 1:
        raise auditme.phaseb.errors.PhaseBError(f'brief {brief} must have exactly one `**Brief version:** N` line with N a positive integer')
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
    for path in auditme.core.all_py_files(src_root):
        lines = auditme.core.source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        module = auditme.core.module_dotted(path, src_root)
        trees[module] = tree
        is_package[module] = path.name == '__init__.py'
        rel = auditme.core.relpath(path, scope)
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


@register_question('A4', A4_BRIEF, ('missing', 'extra'))
def list_a4_candidates(scope: pathlib.Path, depth: int = DEFAULT_DEPTH) -> list[Candidate]:
    """List every function or method with a `Raises:` section under the audited roots, minus D2's stubs.

    Each carries its section, its resolved callees to `depth` (resolving
    `<ClassName>.<method>(...)` too), its unresolved calls, and a sha256 over
    its source then its callees' source in id order, NUL-separated.

    Raises:
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    return [candidate for src_root in auditme.core.audit_roots(scope) for candidate in root_candidates(scope, src_root, depth)]


DOC_BATCH_SIZE = 24
DOC_BRIEFS = A4_BRIEF.parent
UNRESOLVED = '(unresolved)'
IMPLEMENTED_RE = re.compile(r'^\*\*Status:\*\*\s*implemented\s*$', re.MULTILINE)
LIST_ITEM_RE = re.compile(r'^\s*(?:[-*+]|\d+[.)])\s')
TABLE_ROW_RE = re.compile(r'^\s*\|')


def read_text(path: pathlib.Path) -> str:
    """Return a listed document's text.

    Raises:
        PhaseBError: the file cannot be read or decoded as UTF-8.
    """
    try:
        return path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as error:
        raise auditme.phaseb.errors.PhaseBError(f'cannot read {path}') from error


def section_blocks(lines: list[str], start: int, end: int) -> list[tuple[int, int]]:
    """The (first, last) lines of each paragraph, list item, table row and fence between a heading and the section's end."""
    blocks: list[tuple[int, int]] = []
    first: int | None = None
    in_fence = False
    for number in range(start + 1, end + 1):
        line = lines[number - 1]
        if auditme.phaseb.docrefs.FENCE_RE.match(line):
            if in_fence:
                blocks.append((first or number, number))
                first = None
            else:
                if first is not None:
                    blocks.append((first, number - 1))
                first = number
            in_fence = not in_fence
        elif in_fence:
            continue
        elif not line.strip():
            if first is not None:
                blocks.append((first, number - 1))
                first = None
        elif TABLE_ROW_RE.match(line):
            if first is not None:
                blocks.append((first, number - 1))
            blocks.append((number, number))
            first = None
        elif LIST_ITEM_RE.match(line):
            if first is not None:
                blocks.append((first, number - 1))
            first = number
        elif first is None:
            first = number
    if first is not None:
        blocks.append((first, end))
    return blocks


def target_bytes(target: auditme.phaseb.docrefs.DocTarget, index: auditme.phaseb.docrefs.CorpusIndex) -> bytes:
    """The bytes a target's hash covers: its source lines, a file's content or a directory's sorted tracked entries.

    Raises:
        PhaseBError: the target's file cannot be read.
    """
    if target.kind == 'directory':
        return '\n'.join(sorted(name for name in index.files if name.startswith(f'{target.path}/'))).encode('utf-8', errors='surrogateescape')
    try:
        data = (index.scope / target.path).read_bytes()
    except OSError as error:
        raise auditme.phaseb.errors.PhaseBError(f'cannot read {target.path}') from error
    if target.kind == 'file':
        return data
    return b'\n'.join(data.splitlines()[target.start - 1 : target.end])


def digest(parts: list[bytes]) -> str:
    return hashlib.sha256(b'\0'.join(parts)).hexdigest()


def doc_candidates(question: str, scope: pathlib.Path, documents: list[pathlib.Path]) -> list[Candidate]:
    """One candidate per (section, target) pair and one `(unresolved)` candidate per section with unresolved names."""
    index = auditme.phaseb.docrefs.CorpusIndex.build(scope)
    found: list[Candidate] = []
    for document in documents:
        lines = read_text(document).splitlines()
        for section in auditme.phaseb.docrefs.read_sections(document, scope):
            blocks = section_blocks(lines, section.start, section.end)
            named: dict[str, tuple[auditme.phaseb.docrefs.DocTarget, list[int]]] = {}
            unresolved: list[dict[str, typing.Any]] = []
            for number, token in section.names:
                targets = auditme.phaseb.docrefs.resolve_name(token, document, index)
                if len(targets) == 1:
                    named.setdefault(targets[0].id, (targets[0], []))[1].append(number)
                else:
                    unresolved.append({'name': token, 'line': number, 'definitions': [dataclasses.asdict(target) for target in targets]})
            prefix = f'{section.doc}::{section.heading_path}::'
            for target, numbers in named.values():
                covering = sorted({block for block in blocks for number in numbers if block[0] <= number <= block[1]})
                parts = ['\n'.join(lines[first - 1 : last]).encode('utf-8') for first, last in covering]
                found.append(
                    Candidate(
                        question=question,
                        id=prefix + target.id,
                        path=section.doc,
                        start=section.start,
                        end=section.end,
                        payload={
                            'target': dataclasses.asdict(target),
                            'lines': [{'line': number, 'text': lines[number - 1].strip()} for number in sorted(set(numbers))],
                        },
                        hash=digest([*parts, target_bytes(target, index)]),
                    )
                )
            if unresolved:
                text = '\n'.join(lines[section.start - 1 : section.end]).encode('utf-8')
                tokens = '\n'.join(sorted(entry['name'] for entry in unresolved)).encode('utf-8')
                found.append(
                    Candidate(
                        question=question,
                        id=prefix + UNRESOLVED,
                        path=section.doc,
                        start=section.start,
                        end=section.end,
                        payload={'tokens': unresolved},
                        hash=digest([text, tokens]),
                    )
                )
    return found


@register_question('Doc4', DOC_BRIEFS / 'Doc4.md', ('drift',), batch_size=DOC_BATCH_SIZE)
def list_doc4_candidates(scope: pathlib.Path) -> list[Candidate]:
    """List the (section, target) pairs of every implemented spec under `agents/specs/`.

    A proposed spec describes code not yet written, so it is not listed.

    Raises:
        PhaseBError: a spec cannot be read.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    specs = [
        path
        for path in auditme.rules.project_hygiene.spec_markdown_files(scope)
        if path.relative_to(scope).as_posix().startswith('agents/specs/') and IMPLEMENTED_RE.search(read_text(path))
    ]
    return doc_candidates('Doc4', scope, specs)


@register_question('Doc5', DOC_BRIEFS / 'Doc5.md', ('drift',), batch_size=DOC_BATCH_SIZE)
def list_doc5_candidates(scope: pathlib.Path) -> list[Candidate]:
    """List the (section, target) pairs of every `docs/**/*.md` and the root `README.md`.

    Raises:
        PhaseBError: a document cannot be read.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    documents = [
        path
        for path in auditme.rules.project_hygiene.spec_markdown_files(scope)
        if (rel := path.relative_to(scope).as_posix()).startswith('docs/') or rel == 'README.md'
    ]
    return doc_candidates('Doc5', scope, documents)


AGENTS_BATCH_SIZE = 12
AGENTS_DOC = 'AGENTS.md'
HOOK_FILE = '.pre-commit-config.yaml'
HOOK_ID_RE = re.compile(r'^\s*-\s+id:\s*[\'"]?([^\'"\s]+)')
REQUIREMENT_NAME_RE = re.compile(r'\s*([A-Za-z0-9][A-Za-z0-9._-]*)')


def agents_document(scope: pathlib.Path) -> tuple[pathlib.Path, list[str]] | None:
    """The root `AGENTS.md` and its lines, or None when the project has none."""
    path = scope / AGENTS_DOC
    if not path.exists():
        return None
    return path, read_text(path).splitlines()


def tracked_directories(index: auditme.phaseb.docrefs.CorpusIndex) -> list[str]:
    """The tracked directories down to the tree depth, sorted."""
    return sorted(name for name in index.directories if name.count('/') < auditme.phaseb.docrefs.TREE_DEPTH)


@register_question('Doc1', DOC_BRIEFS / 'Doc1.md', ('stale', 'missing'), batch_size=AGENTS_BATCH_SIZE)
def list_doc1_candidates(scope: pathlib.Path) -> list[Candidate]:
    """List each `AGENTS.md` section that names a path or holds a fence, with the tracked directory tree.

    Raises:
        PhaseBError: `AGENTS.md` cannot be read, or `git ls-files` fails.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    document = agents_document(scope)
    if document is None:
        return []
    path, lines = document
    index = auditme.phaseb.docrefs.CorpusIndex.build(scope)
    tree = tracked_directories(index)
    tree_bytes = '\n'.join(tree).encode('utf-8', errors='surrogateescape')
    found: list[Candidate] = []
    for section in auditme.phaseb.docrefs.read_sections(path, scope):
        text = lines[section.start - 1 : section.end]
        named = [(number, token) for number, token in section.names if auditme.phaseb.docrefs.is_path_shaped(token)]
        if not named and not any(auditme.phaseb.docrefs.FENCE_RE.match(line) for line in text):
            continue
        paths = [
            {'path': token, 'line': number, 'resolved': [target.id for target in auditme.phaseb.docrefs.resolve_path(token, path, index)]}
            for number, token in named
        ]
        found.append(
            Candidate(
                question='Doc1',
                id=f'{section.doc}::{section.heading_path}',
                path=section.doc,
                start=section.start,
                end=section.end,
                payload={'paths': paths, 'tree': tree},
                hash=digest(['\n'.join(text).encode('utf-8'), tree_bytes]),
            )
        )
    return found


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
        raise auditme.phaseb.errors.PhaseBError(f'cannot read {path}') from error


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
        return path.read_bytes()
    except OSError as error:
        raise auditme.phaseb.errors.PhaseBError(f'cannot read {path}') from error


def imported_modules(scope: pathlib.Path) -> set[str]:
    """The top-level module names the corpus imports; a file with a syntax error is skipped."""
    roots = auditme.core.audit_roots(scope)
    src_root = roots[0] if roots else scope / 'src'
    modules: set[str] = set()
    for path in auditme.core.corpus_py_files(scope, src_root):
        try:
            tree = ast.parse('\n'.join(auditme.core.source_lines(path)))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module.split('.')[0])
    return modules


@register_question('Doc2', DOC_BRIEFS / 'Doc2.md', ('stale', 'missing'), batch_size=AGENTS_BATCH_SIZE)
def list_doc2_candidates(scope: pathlib.Path) -> list[Candidate]:
    """List each `AGENTS.md` section holding a backticked token, matched against the declared tools.

    Raises:
        PhaseBError: `AGENTS.md`, `pyproject.toml` or `.pre-commit-config.yaml` exists but cannot be read
            or parsed, or `git ls-files` fails.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    document = agents_document(scope)
    if document is None:
        return []
    path, lines = document
    auditme.phaseb.docrefs.tracked_files(scope)
    tables = declared_tables(read_pyproject(scope))
    hook_bytes = read_hook_file(scope)
    hooks = {match.group(1) for line in hook_bytes.decode('utf-8', errors='replace').splitlines() if (match := HOOK_ID_RE.match(line))}
    modules = imported_modules(scope)
    canonical = json.dumps({key: sorted(value) for key, value in tables.items()}, sort_keys=True).encode('utf-8')
    found: list[Candidate] = []
    for section in auditme.phaseb.docrefs.read_sections(path, scope):
        tokens = auditme.phaseb.docrefs.backticked_tokens(lines, section.start, section.end)
        if not tokens:
            continue
        matched: list[dict[str, typing.Any]] = []
        unmatched: set[str] = set()
        for number, token in tokens:
            words = auditme.phaseb.docrefs.TRAILING_CALL_RE.sub('', token).split()
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
            Candidate(
                question='Doc2',
                id=f'{section.doc}::{section.heading_path}',
                path=section.doc,
                start=section.start,
                end=section.end,
                payload={'matched': matched, 'unmatched': sorted(unmatched)},
                hash=digest(['\n'.join(lines[section.start - 1 : section.end]).encode('utf-8'), canonical, hook_bytes]),
            )
        )
    return found


def _self_attribute(node: ast.AST) -> str | None:
    """The attribute name when node is `self.<attr>`, else None."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'self':
        return node.attr
    return None


def _tested_attributes(method: FunctionNode) -> set[str]:
    """The `self.<attr>` names method tests in an `if`, a `match` subject or a comparison."""
    tested: set[str] = set()
    for node in auditme.core.walk_within_scope(method):
        if isinstance(node, ast.If):
            expressions: list[ast.AST] = [node.test]
        elif isinstance(node, ast.Match):
            expressions = [node.subject]
        elif isinstance(node, ast.Compare):
            expressions = [node]
        else:
            continue
        for expression in expressions:
            for inner in ast.walk(expression):
                name = _self_attribute(inner)
                if name is not None:
                    tested.add(name)
    return tested


def _assigned_attributes(node: FunctionNode) -> set[str]:
    """The `self.<attr>` names node assigns in its own body."""
    assigned: set[str] = set()
    for inner in auditme.core.walk_within_scope(node):
        targets: list[ast.expr] = []
        if isinstance(inner, ast.Assign):
            targets = inner.targets
        elif isinstance(inner, (ast.AugAssign, ast.AnnAssign)):
            targets = [inner.target]
        for target in targets:
            for part in ast.walk(target):
                name = _self_attribute(part)
                if name is not None:
                    assigned.add(name)
    return assigned


def t1_reasons(node: ast.FunctionDef | ast.AsyncFunctionDef, cls: ast.ClassDef | None) -> list[str]:
    """Why node is a T1 candidate: any of 'if', 'try', 'match', 'state'; empty if not."""
    own = list(auditme.core.walk_within_scope(node))
    reasons: list[str] = []
    if any(isinstance(inner, ast.If) for inner in own):
        reasons.append('if')
    if any(isinstance(inner, (ast.Try, ast.TryStar)) and inner.handlers for inner in own):
        reasons.append('try')
    if any(isinstance(inner, ast.Match) for inner in own):
        reasons.append('match')
    if cls is not None:
        assigned = _assigned_attributes(node)
        if assigned:
            others = (method for method in cls.body if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method is not node)
            if any(assigned & _tested_attributes(method) for method in others):
                reasons.append('state')
    return reasons


T1_BRIEF = DOC_BRIEFS / 'T1.md'


def is_overload(node: FunctionNode) -> bool:
    """True for a function decorated with `overload` or `typing.overload`."""
    return any(ast.unparse(decorator).rpartition('.')[2] == 'overload' for decorator in node.decorator_list)


@register_question('T1', T1_BRIEF, ('missing',))
def list_t1_candidates(scope: pathlib.Path, depth: int = DEFAULT_DEPTH) -> list[Candidate]:
    """List every function or method whose own body branches, with the tests that reach it.

    Each carries its reasons, its direct and caller tests, its callers to
    `depth`, its `test_files` and whether it is private. The hash is a sha256
    over its source then each `test_files` file's text in path order,
    NUL-separated. `@typing.overload` stubs and defs under `if TYPE_CHECKING:`
    are left out.

    Raises:
        PhaseBError: a test file or audited source file does not parse.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    index = auditme.phaseb.testmap.build_index(scope)
    refs = index.refs(depth)
    hidden = {module: auditme.core.type_checking_linenos(file.tree) for module, file in index.sources.items()}
    classes = {(module, node.name): node for module, file in index.sources.items() for node in file.tree.body if isinstance(node, ast.ClassDef)}
    found: list[Candidate] = []
    for site in index.sites.values():
        if is_overload(site.node) or site.node.lineno in hidden[site.module]:
            continue
        reasons = t1_reasons(site.node, classes.get((site.module, site.cls)) if site.cls else None)
        if not reasons:
            continue
        test_files = index.test_files(site.id, depth)
        parts = [site.source.encode('utf-8'), *read_test_files(scope, test_files)]
        found.append(
            Candidate(
                question='T1',
                id=site.id,
                path=site.path,
                start=site.start,
                end=site.end,
                payload={
                    'reasons': reasons,
                    'tests': [dataclasses.asdict(ref) for ref in refs.get(site.id, ())],
                    'callers': index.callers(site.id, depth),
                    'test_files': test_files,
                    'private': auditme.core.is_private(site.qualname.removeprefix(f'{site.module}.'), site.module, scope),
                },
                hash=digest(parts),
            )
        )
    return found


# The type set and the extra call names below change only with a bump of the
# T2 brief version: a change re-plans every candidate through its hash.
T2_SCALAR_TYPES = frozenset({'Decimal', 'Fraction', 'bool', 'bytes', 'date', 'datetime', 'float', 'int', 'str', 'timedelta'})
T2_CONTAINER_TYPES = frozenset({'Iterable', 'Mapping', 'Optional', 'Sequence', 'Union', 'dict', 'frozenset', 'list', 'set', 'tuple'})
T2_ENUM_BASES = frozenset({'Enum', 'Flag', 'IntEnum', 'IntFlag', 'StrEnum'})
T2_EXTRA_CALL_NAMES = frozenset(
    {'Popen', 'check_call', 'check_output', 'choice', 'input', 'now', 'open', 'print', 'randint', 'randrange', 'shuffle', 'time', 'uniform'}
)
T2_EFFECT_MODULES = frozenset({'random', 'subprocess'})
T2_BRANCHES = (ast.If, ast.IfExp, ast.Match, ast.For, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def short_name(node: ast.AST) -> str | None:
    """The last dotted component of a name or attribute, else None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def root_name(node: ast.AST) -> str | None:
    """The leftmost name of an attribute, subscript or call chain, else None."""
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def is_frozen_dataclass(cls: ast.ClassDef) -> bool:
    """True for a class decorated `dataclass(frozen=True)`."""
    for decorator in cls.decorator_list:
        if isinstance(decorator, ast.Call) and short_name(decorator.func) == 'dataclass':
            if any(keyword.arg == 'frozen' and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in decorator.keywords):
                return True
    return False


def is_well_defined_class(cls: ast.ClassDef, package_types: collections.abc.Mapping[str, ast.ClassDef], checking: set[str]) -> bool:
    """True when cls is an Enum, or a frozen dataclass, NamedTuple or TypedDict of well-defined fields."""
    bases = {short_name(base) for base in cls.bases}
    if bases & T2_ENUM_BASES:
        return True
    if not (bases & {'NamedTuple', 'TypedDict'} or is_frozen_dataclass(cls)):
        return False
    checking = checking | {cls.name}
    for field in cls.body:
        if isinstance(field, ast.AnnAssign) and short_name(field.annotation) != 'ClassVar':
            if not is_well_defined_type(field.annotation, package_types, checking):
                return False
    return True


def is_well_defined_type(annotation: ast.expr, package_types: collections.abc.Mapping[str, ast.ClassDef], checking: set[str]) -> bool:
    """True when annotation is built only from the T2 type set."""
    if isinstance(annotation, ast.Constant):
        if annotation.value is None or annotation.value is Ellipsis:
            return True
        if isinstance(annotation.value, str):
            try:
                inner = ast.parse(annotation.value, mode='eval').body
            except SyntaxError:
                return False
            return is_well_defined_type(inner, package_types, checking)
        return False
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return is_well_defined_type(annotation.left, package_types, checking) and is_well_defined_type(annotation.right, package_types, checking)
    if isinstance(annotation, ast.Subscript):
        head = short_name(annotation.value)
        if head == 'Literal':
            return True
        if head not in T2_CONTAINER_TYPES:
            return False
        arguments = annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
        return all(is_well_defined_type(argument, package_types, checking) for argument in arguments)
    name = short_name(annotation)
    if name is None:
        return False
    if name in T2_SCALAR_TYPES:
        return True
    cls = package_types.get(name)
    if cls is None:
        return False
    if name in checking:
        return True
    return is_well_defined_class(cls, package_types, checking)


def is_t2_candidate(node: ast.FunctionDef, package_types: collections.abc.Mapping[str, ast.ClassDef]) -> bool:
    """True when node is pure over well-defined types and has logic a property can test."""
    if not isinstance(node, ast.FunctionDef):
        return False
    arguments = node.args
    decorators = {short_name(decorator) for decorator in node.decorator_list}
    parameters = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    if arguments.vararg is not None:
        parameters.append(arguments.vararg)
    if arguments.kwarg is not None:
        parameters.append(arguments.kwarg)
    if not parameters or 'classmethod' in decorators:
        return False
    if parameters[0].arg in {'self', 'cls'} and 'staticmethod' not in decorators:
        return False
    returns = node.returns
    if returns is None or (isinstance(returns, ast.Constant) and returns.value is None):
        return False
    annotations = [parameter.annotation for parameter in parameters]
    if any(annotation is None for annotation in annotations):
        return False
    if not all(is_well_defined_type(annotation, package_types, set()) for annotation in [*annotations, returns] if annotation is not None):
        return False
    names = {parameter.arg for parameter in parameters}
    effects = auditme.core.SIDE_EFFECT_CALL_NAMES | T2_EXTRA_CALL_NAMES
    own = list(auditme.core.walk_within_scope(node))
    for inner in own:
        if isinstance(inner, (ast.Yield, ast.YieldFrom, ast.Global, ast.Nonlocal, ast.Await)):
            return False
        if isinstance(inner, ast.Call) and (short_name(inner.func) in effects or root_name(inner.func) in T2_EFFECT_MODULES):
            return False
        targets: list[ast.expr] = []
        if isinstance(inner, ast.Assign):
            targets = inner.targets
        elif isinstance(inner, (ast.AugAssign, ast.AnnAssign)):
            targets = [inner.target]
        elif isinstance(inner, ast.Delete):
            targets = inner.targets
        for target in targets:
            for part in ast.walk(target):
                if isinstance(part, (ast.Attribute, ast.Subscript)) and root_name(part) in names:
                    return False
    return any(isinstance(inner, T2_BRANCHES) for inner in own)


T2_BRIEF = DOC_BRIEFS / 'T2.md'
T2_INVERSES = (('parse', 'format'), ('encode', 'decode'), ('to', 'from'), ('dumps', 'loads'))


def inverse_names(name: str) -> set[str]:
    """The names that invert `name`: `parse_x`/`format_x`, `encode`/`decode`, `to_x`/`from_x`, `dumps`/`loads`."""
    head, separator, rest = name.partition('_')
    found: set[str] = set()
    for first, second in T2_INVERSES:
        if head == first:
            found.add(f'{second}{separator}{rest}')
        elif head == second:
            found.add(f'{first}{separator}{rest}')
    return found


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


def referenced_types(annotations: list[ast.expr], package_types: collections.abc.Mapping[str, ast.ClassDef]) -> set[str]:
    """The package class names the annotations name, directly or through a class's fields."""
    found: set[str] = set()
    pending = [name for annotation in annotations for name in annotation_names(annotation)]
    while pending:
        name = pending.pop()
        if name in found or name not in package_types:
            continue
        found.add(name)
        for field in package_types[name].body:
            if isinstance(field, ast.AnnAssign):
                pending.extend(annotation_names(field.annotation))
    return found


@register_question('T2', T2_BRIEF, ('missing',))
def list_t2_candidates(scope: pathlib.Path, depth: int = DEFAULT_DEPTH) -> list[Candidate]:
    """List every function `is_t2_candidate` accepts, with its types, inverse pairs and tests.

    The hash is a sha256 over its source, each `types` class's source in id
    order, then each `test_files` file's text in path order, NUL-separated.

    Raises:
        PhaseBError: a test file or audited source file does not parse.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    index = auditme.phaseb.testmap.build_index(scope)
    refs = index.refs(depth)
    hidden = {module: auditme.core.type_checking_linenos(file.tree) for module, file in index.sources.items()}
    class_sites: dict[str, tuple[auditme.phaseb.testmap.ParsedFile, ast.ClassDef]] = {}
    for module in sorted(index.sources):
        file = index.sources[module]
        for node in file.tree.body:
            if isinstance(node, ast.ClassDef):
                class_sites[node.name] = (file, node)
    package_types = {name: cls for name, (_, cls) in class_sites.items()}
    accepted = [
        site
        for site in index.sites.values()
        if isinstance(site.node, ast.FunctionDef)
        and (site.cls is None or any(short_name(decorator) == 'staticmethod' for decorator in site.node.decorator_list))
        and not is_overload(site.node)
        and site.node.lineno not in hidden[site.module]
        and is_t2_candidate(site.node, package_types)
    ]
    by_name: dict[str, list[str]] = {}
    for site in accepted:
        by_name.setdefault(site.node.name, []).append(site.id)
    found: list[Candidate] = []
    for site in accepted:
        node = site.node
        arguments = node.args
        parameters = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
        if arguments.vararg is not None:
            parameters.append(arguments.vararg)
        if arguments.kwarg is not None:
            parameters.append(arguments.kwarg)
        annotated = [(parameter.arg, parameter.annotation) for parameter in parameters if parameter.annotation is not None]
        returns = node.returns
        if returns is None:
            continue
        text = '\n'.join(site.lines)
        types: list[dict[str, str | int]] = []
        class_sources: list[tuple[str, bytes]] = []
        for name in referenced_types([*(annotation for _, annotation in annotated), returns], package_types):
            file, cls = class_sites[name]
            start = min([cls.lineno, *(decorator.lineno for decorator in cls.decorator_list)])
            end = cls.end_lineno or cls.lineno
            type_id = f'{file.rel}::{cls.name}'
            types.append({'id': type_id, 'path': file.rel, 'start': start, 'end': end})
            class_sources.append((type_id, '\n'.join(file.lines[start - 1 : end]).encode('utf-8')))
        types.sort(key=lambda entry: str(entry['id']))
        class_sources.sort()
        test_files = index.test_files(site.id, depth)
        parts = [site.source.encode('utf-8'), *(source for _, source in class_sources), *read_test_files(scope, test_files)]
        pairs = sorted(other for inverse in inverse_names(node.name) for other in by_name.get(inverse, ()))
        found.append(
            Candidate(
                question='T2',
                id=site.id,
                path=site.path,
                start=site.start,
                end=site.end,
                payload={
                    'params': [
                        {'name': name, 'annotation': ast.get_source_segment(text, annotation) or ast.unparse(annotation)} for name, annotation in annotated
                    ],
                    'returns': ast.get_source_segment(text, returns) or ast.unparse(returns),
                    'types': types,
                    'pairs': pairs,
                    'tests': [dataclasses.asdict(ref) for ref in refs.get(site.id, ())],
                    'test_files': test_files,
                },
                hash=digest(parts),
            )
        )
    return found
