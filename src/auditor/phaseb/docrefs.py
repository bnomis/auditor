"""Markdown sections and the code-shaped names in them, for the Doc listers."""

import ast
import dataclasses
import os.path
import pathlib
import re
import subprocess

import auditor.core
import auditor.hygiene
import auditor.phaseb.errors

# Changed only by a skill change with a brief version bump.
PATH_EXTENSIONS = ('.json', '.lock', '.md', '.py', '.sh', '.toml', '.txt', '.yaml', '.yml')
TREE_DEPTH = 3

HEADING_RE = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
FENCE_RE = re.compile(r'^\s*(```|~~~)')
INLINE_CODE_RE = re.compile(r'`([^`\n]+)`')
TRAILING_CALL_RE = re.compile(r'\(.*\)$')
IDENTIFIER_RE = re.compile(r'^[A-Za-z_]\w*(\.\w+)*$')
INNER_CAPITAL_RE = re.compile(r'[a-z0-9][A-Z]')
OPTION_RE = re.compile(r'^--[A-Za-z][\w-]*$')


@dataclasses.dataclass(frozen=True)
class DocSection:
    """A markdown section: a heading to the next heading of any level, outside fences."""

    doc: str  # repo-relative path
    heading_path: str  # enclosing headings' titles joined by ' > ', '#2' on a repeat
    start: int
    end: int
    names: list[tuple[int, str]]  # (line, token) per code-shaped name, in line order


def code_shaped(token: str) -> str | None:
    """Return the token without a trailing call when it is a code-shaped name, else None."""
    token = TRAILING_CALL_RE.sub('', token.strip())
    if not token or ' ' in token or '<' in token:
        return None
    if token.startswith(('/', '~')):
        return None
    if '/' in token or token.endswith(PATH_EXTENSIONS) or OPTION_RE.match(token):
        return token
    if IDENTIFIER_RE.match(token) and ('_' in token or '.' in token or INNER_CAPITAL_RE.search(token)):
        return token
    return None


def is_path_shaped(token: str) -> bool:
    """True when a code-shaped token names a path: it holds `/` or ends in a known extension."""
    return '/' in token or token.endswith(PATH_EXTENSIONS)


def backticked_tokens(lines: list[str], start: int, end: int) -> list[tuple[int, str]]:
    """Every backticked token (line, text) between lines `start` and `end`, outside fences."""
    found: list[tuple[int, str]] = []
    in_fence = False
    for number in range(start, end + 1):
        line = lines[number - 1]
        if FENCE_RE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            found.extend((number, match.group(1).strip()) for match in INLINE_CODE_RE.finditer(line) if match.group(1).strip())
    return found


def api_fence_name(line: str) -> str | None:
    """Return the name a `def` or `class` line defines, else None."""
    match = auditor.hygiene.DEF_LINE_RE.match(line)
    if match:
        return match.group(1)
    if auditor.hygiene.CLASS_LINE_RE.match(line):
        return re.split(r'[(:]', line.strip().split(None, 1)[1])[0].strip()
    return None


def read_sections(path: pathlib.Path, root: pathlib.Path) -> list[DocSection]:
    """Split a markdown file into sections with their code-shaped names.

    Raises:
        PhaseBError: the file cannot be read or decoded as UTF-8.
    """
    try:
        text = auditor.core.cached_bytes(path).decode('utf-8')
    except (OSError, UnicodeDecodeError) as error:
        raise auditor.phaseb.errors.PhaseBError(f'cannot read {path}') from error
    doc = path.relative_to(root).as_posix()
    lines = text.splitlines()
    stack: list[tuple[int, str]] = []  # (level, title) of the enclosing headings
    seen: dict[str, int] = {}
    raw: list[tuple[str, int, list[tuple[int, str]], bool]] = []  # path, start, names, under API
    in_fence = False
    for number, line in enumerate(lines, start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        heading = None if in_fence else HEADING_RE.match(line)
        if heading:
            level, title = len(heading.group(1)), heading.group(2)
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            heading_path = ' > '.join(t for _, t in stack)
            seen[heading_path] = seen.get(heading_path, 0) + 1
            unique = heading_path if seen[heading_path] == 1 else f'{heading_path}#{seen[heading_path]}'
            raw.append((unique, number, [], any(t == 'API' for _, t in stack)))
            continue
        if not raw:
            continue
        names = raw[-1][2]
        if in_fence:
            if raw[-1][3]:
                name = api_fence_name(line)
                if name:
                    names.append((number, name))
            continue
        for match in INLINE_CODE_RE.finditer(line):
            token = code_shaped(match.group(1))
            if token:
                names.append((number, token))
    sections = []
    for position, (heading_path, start, names, _) in enumerate(raw):
        end = raw[position + 1][1] - 1 if position + 1 < len(raw) else len(lines)
        sections.append(DocSection(doc=doc, heading_path=heading_path, start=start, end=end, names=names))
    return sections


# resolution

OPTION_CALLS = frozenset({'Option', 'add_argument', 'option'})
SETTINGS_BASE = 'BaseSettings'


@dataclasses.dataclass(frozen=True)
class DocTarget:
    """What a name resolves to; kind is function, class, method, field, setting, option, file or directory."""

    kind: str
    id: str  # 'path::qualname', or 'path' for a file or directory
    path: str
    start: int
    end: int


@dataclasses.dataclass
class ClassInfo:
    """A module-level class: its target, base names and members by name."""

    target: DocTarget
    bases: list[str]
    members: dict[str, DocTarget]
    field_types: dict[str, list[str]]  # field name -> class names its annotation mentions


@dataclasses.dataclass(frozen=True)
class CorpusIndex:
    """Everything `read_name_targets` looks names up in, built once per lister call."""

    scope: pathlib.Path
    files: frozenset[str]
    directories: frozenset[str]
    definitions: dict[str, list[tuple[ast.AST, pathlib.Path]]]
    sites: dict[tuple[pathlib.Path, int], DocTarget]
    by_dotted: dict[str, DocTarget]
    aliases: dict[str, str]
    classes: dict[str, list[ClassInfo]]
    options: dict[str, list[DocTarget]]
    settings: frozenset[str]

    @classmethod
    def build(cls, scope: pathlib.Path) -> 'CorpusIndex':
        """Index the corpus under `scope`.

        Raises:
            PhaseBError: `git ls-files` fails, as it does outside a work tree.
            RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
        """
        files = tracked_files(scope)
        directories = frozenset(parent.as_posix() for name in files for parent in pathlib.PurePosixPath(name).parents if parent.as_posix() != '.')
        roots, _ = auditor.core.cached_roots(scope)
        src_root = roots[0] if roots else scope / 'src'
        definitions = auditor.core.corpus_definitions(scope, src_root, classes=True)
        entries = IndexEntries()
        from_bindings: dict[str, dict[str, str]] = {}
        for path in auditor.core.cached_corpus_files(scope, src_root):
            tree = auditor.core.read_and_parse(path)
            if tree is None:
                continue
            rel = auditor.core.relpath(path, scope)
            root = next((r for r in roots if path.is_relative_to(r)), None)
            module = auditor.core.module_dotted(path, root) if root else None
            if module:
                from_bindings[module] = auditor.core.from_import_bindings(tree, module, path.name == '__init__.py')
            entries.add_module(tree, path, rel, module)
        aliases = auditor.core.reexport_aliases(from_bindings, entries.by_dotted.keys())
        settings = settings_classes(entries.classes)
        return cls(scope, files, directories, definitions, entries.sites, entries.by_dotted, aliases, entries.classes, entries.options, settings)


def settings_classes(classes: dict[str, list[ClassInfo]]) -> frozenset[str]:
    """Names of the classes deriving, directly or through other corpus classes, from `BaseSettings`."""
    found: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, infos in classes.items():
            if name not in found and any(SETTINGS_BASE in info.bases or found & set(info.bases) for info in infos):
                found.add(name)
                changed = True
    return frozenset(found)


@dataclasses.dataclass
class IndexEntries:
    """The dicts `CorpusIndex.build` assembles module by module, before it freezes them into the index."""

    sites: dict[tuple[pathlib.Path, int], DocTarget] = dataclasses.field(default_factory=dict)
    by_dotted: dict[str, DocTarget] = dataclasses.field(default_factory=dict)
    classes: dict[str, list[ClassInfo]] = dataclasses.field(default_factory=dict)
    options: dict[str, list[DocTarget]] = dataclasses.field(default_factory=dict)

    def add_module(self, tree: ast.Module, path: pathlib.Path, rel: str, module: str | None) -> None:
        """Record a module's functions, classes and option literals."""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.record(path, node, node_target('function', rel, node.name, node), module, node.name)
            elif isinstance(node, ast.ClassDef):
                target = node_target('class', rel, node.name, node)
                self.record(path, node, target, module, node.name)
                self.classes.setdefault(node.name, []).append(self.class_info(node, target, path, rel, module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and call_name(node) in OPTION_CALLS:
                for value in [*node.args, *(keyword.value for keyword in node.keywords)]:
                    if isinstance(value, ast.Constant) and isinstance(value.value, str) and OPTION_RE.match(value.value):
                        target = node_target('option', rel, value.value, node)
                        self.options.setdefault(value.value, []).append(target)

    def record(
        self, path: pathlib.Path, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, target: DocTarget, module: str | None, qualname: str
    ) -> None:
        """Index a definition by its position and, where its module is known, its dotted name."""
        self.sites[(path, node.lineno)] = target
        if module:
            self.by_dotted[f'{module}.{qualname}'] = target

    def class_info(self, node: ast.ClassDef, target: DocTarget, path: pathlib.Path, rel: str, module: str | None) -> ClassInfo:
        """Collect a class's bases, methods and fields."""
        bases = [base.id if isinstance(base, ast.Name) else base.attr for base in node.bases if isinstance(base, (ast.Name, ast.Attribute))]
        members: dict[str, DocTarget] = {}
        field_types: dict[str, list[str]] = {}
        for member in node.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method = node_target('method', rel, f'{node.name}.{member.name}', member)
                members[member.name] = method
                self.record(path, member, method, module, f'{node.name}.{member.name}')
            elif isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                members[member.target.id] = field_target(node.name, rel, member.target.id, member)
                field_types[member.target.id] = [n.id for n in ast.walk(member.annotation) if isinstance(n, ast.Name)]
            elif isinstance(member, ast.Assign):
                for name in (t.id for t in member.targets if isinstance(t, ast.Name)):
                    members[name] = field_target(node.name, rel, name, member)
        return ClassInfo(target, bases, members, field_types)


def field_target(class_name: str, rel: str, name: str, node: ast.stmt) -> DocTarget:
    """The target of a class field's statement."""
    return node_target('field', rel, f'{class_name}.{name}', node)


def node_target(kind: str, rel: str, qualname: str, node: ast.stmt) -> DocTarget:
    """The target of a definition or statement: lines from its first decorator, if any, to its end."""
    start = min([node.lineno, *(decorator.lineno for decorator in getattr(node, 'decorator_list', ()))])
    return DocTarget(kind, f'{rel}::{qualname}', rel, start, node.end_lineno or node.lineno)


def path_target(kind: str, rel: str, last_line: int) -> DocTarget:
    """The target of a file or directory: its path, from line 1."""
    return DocTarget(kind, rel, rel, 1, last_line)


def call_name(call: ast.Call) -> str | None:
    """The bare name a call invokes, or None when it is neither a name nor an attribute."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def tracked_files(scope: pathlib.Path) -> frozenset[str]:
    """The repository-relative paths `git ls-files -z` lists.

    Raises:
        PhaseBError: git fails, as it does outside a work tree.
    """
    try:
        # git from PATH, fixed arguments: the same tool the user runs against the audited project.
        result = subprocess.run(['git', 'ls-files', '-z'], cwd=scope, capture_output=True, check=True)  # noqa: S603, S607
    except (OSError, subprocess.CalledProcessError) as error:
        raise auditor.phaseb.errors.PhaseBError(f'git ls-files failed in {scope}') from error
    return frozenset(name for name in result.stdout.decode('utf-8', errors='surrogateescape').split('\0') if name)


def read_file_target(index: CorpusIndex, rel: str) -> DocTarget:
    """The target of a tracked file, spanning all its lines.

    The file is read through the per-run byte cache, so a file read for its
    line count is not read again for its hash.

    Raises:
        PhaseBError: the file cannot be read.
    """
    try:
        lines = auditor.core.cached_bytes(index.scope / rel).count(b'\n') + 1
    except OSError as error:
        raise auditor.phaseb.errors.PhaseBError(f'cannot read {rel}') from error
    return path_target('file', rel, lines)


def read_path_targets(token: str, doc: pathlib.Path, index: CorpusIndex) -> list[DocTarget]:
    """A tracked file or directory, relative to the repository root, then to the document's directory.

    Raises:
        PhaseBError: a matching file cannot be read for its line count.
    """
    if '/' not in token and not token.endswith(PATH_EXTENSIONS):
        return []
    doc_dir = doc.parent.relative_to(index.scope).as_posix()
    for candidate in (token, f'{doc_dir}/{token}'):
        rel = os.path.normpath(candidate.rstrip('/')).replace(os.sep, '/')
        if rel.startswith('..') or rel == '.':
            continue
        if rel in index.files:
            return [read_file_target(index, rel)]
        if rel in index.directories:
            return [path_target('directory', rel, 1)]
    return []


def resolve_dotted(token: str, doc: pathlib.Path, index: CorpusIndex) -> list[DocTarget]:
    """A dotted name, followed through the re-export aliases."""
    target = index.by_dotted.get(index.aliases.get(token, token))
    return [target] if target else []


def resolve_bare(token: str, doc: pathlib.Path, index: CorpusIndex) -> list[DocTarget]:
    """A bare function, class or method name; several when it is defined more than once."""
    found = {
        index.sites[(path, node.lineno)]
        for node, path in index.definitions.get(token, [])
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and (path, node.lineno) in index.sites
    }
    return sorted(found, key=lambda target: target.id)


def resolve_member(token: str, doc: pathlib.Path, index: CorpusIndex) -> list[DocTarget]:
    """`Class.method` or `Class.field`."""
    owner, _, member = token.partition('.')
    found = {info.members[member] for info in index.classes.get(owner, []) if member in info.members}
    return sorted(found, key=lambda target: target.id)


def resolve_setting(token: str, doc: pathlib.Path, index: CorpusIndex) -> list[DocTarget]:
    """A dotted key: a field of a settings class, then a field of each field's class."""
    first, *rest = token.split('.')
    owners = [(info, info.field_types.get(first, [])) for name in index.settings for info in index.classes[name] if first in info.members]
    targets = {info.members[first] for info, _ in owners}
    for segment in rest:
        next_owners: list[tuple[ClassInfo, list[str]]] = []
        targets = set()
        for _, type_names in owners:
            for type_name in type_names:
                for info in index.classes.get(type_name, []):
                    if segment in info.members and info.members[segment].kind == 'field':
                        targets.add(info.members[segment])
                        next_owners.append((info, info.field_types.get(segment, [])))
        owners = next_owners
    return sorted((dataclasses.replace(target, kind='setting') for target in targets), key=lambda target: target.id)


def resolve_option(token: str, doc: pathlib.Path, index: CorpusIndex) -> list[DocTarget]:
    """A `--name` literal passed to `add_argument`, `option` or `Option`."""
    return sorted(set(index.options.get(token, [])), key=lambda target: target.id)


def read_name_targets(token: str, doc: pathlib.Path, index: CorpusIndex) -> list[DocTarget]:
    """Resolve one token: [] for nothing, one target, or several when ambiguous.

    Tries, in order: a tracked path, a dotted name through the re-export
    aliases, a bare name, `Class.member`, a setting key, a command-line option.
    Each is positive evidence; nothing resolves by resemblance.

    Raises:
        PhaseBError: a matching file cannot be read for its line count.
    """
    for step in (read_path_targets, resolve_dotted, resolve_bare, resolve_member, resolve_setting, resolve_option):
        found = step(token, doc, index)
        if found:
            return found
    return []
