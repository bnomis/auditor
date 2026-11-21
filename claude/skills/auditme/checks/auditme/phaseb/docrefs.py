"""Markdown sections and the code-shaped names in them, for the Doc listers."""

import ast
import dataclasses
import os.path
import pathlib
import re
import subprocess

import auditme.core
from auditme.phaseb.errors import PhaseBError
from auditme.rules.project_hygiene import _CLASS_LINE_RE, _DEF_LINE_RE

# Changed only by a skill change with a brief version bump.
PATH_EXTENSIONS = ('.json', '.lock', '.md', '.py', '.sh', '.toml', '.txt', '.yaml', '.yml')
TREE_DEPTH = 3

_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
FENCE_RE = re.compile(r'^\s*(```|~~~)')
_INLINE_CODE_RE = re.compile(r'`([^`\n]+)`')
TRAILING_CALL_RE = re.compile(r'\(.*\)$')
_IDENTIFIER_RE = re.compile(r'^[A-Za-z_]\w*(\.\w+)*$')
_INNER_CAPITAL_RE = re.compile(r'[a-z0-9][A-Z]')
_OPTION_RE = re.compile(r'^--[A-Za-z][\w-]*$')


@dataclasses.dataclass(frozen=True)
class DocSection:
    """A markdown section: a heading to the next heading of any level, outside fences."""

    doc: str  # repo-relative path
    heading_path: str  # enclosing headings' titles joined by ' > ', '#2' on a repeat
    start: int
    end: int
    names: list[tuple[int, str]]  # (line, token) per code-shaped name, in line order


def _code_shaped(token: str) -> str | None:
    """Return the token without a trailing call when it is a code-shaped name, else None."""
    token = TRAILING_CALL_RE.sub('', token.strip())
    if not token or ' ' in token or '<' in token:
        return None
    if token.startswith(('/', '~')):
        return None
    if '/' in token or token.endswith(PATH_EXTENSIONS) or _OPTION_RE.match(token):
        return token
    if _IDENTIFIER_RE.match(token) and ('_' in token or '.' in token or _INNER_CAPITAL_RE.search(token)):
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
            found.extend((number, match.group(1).strip()) for match in _INLINE_CODE_RE.finditer(line) if match.group(1).strip())
    return found


def _api_fence_name(line: str) -> str | None:
    """Return the name a `def` or `class` line defines, else None."""
    match = _DEF_LINE_RE.match(line)
    if match:
        return match.group(1)
    if _CLASS_LINE_RE.match(line):
        return re.split(r'[(:]', line.strip().split(None, 1)[1])[0].strip()
    return None


def read_sections(path: pathlib.Path, root: pathlib.Path) -> list[DocSection]:
    """Split a markdown file into sections with their code-shaped names.

    Raises:
        PhaseBError: the file cannot be read or decoded as UTF-8.
    """
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as error:
        raise PhaseBError(f'cannot read {path}') from error
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
        heading = None if in_fence else _HEADING_RE.match(line)
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
                name = _api_fence_name(line)
                if name:
                    names.append((number, name))
            continue
        for match in _INLINE_CODE_RE.finditer(line):
            token = _code_shaped(match.group(1))
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


@dataclasses.dataclass
class CorpusIndex:
    """Everything `resolve_name` looks names up in, built once per lister call."""

    scope: pathlib.Path
    files: frozenset[str]
    directories: frozenset[str]
    definitions: dict[str, list[tuple[ast.AST, pathlib.Path]]]
    sites: dict[tuple[pathlib.Path, int], DocTarget]
    by_dotted: dict[str, DocTarget]
    aliases: dict[str, str]
    classes: dict[str, list[ClassInfo]]
    options: dict[str, list[DocTarget]]

    @classmethod
    def build(cls, scope: pathlib.Path) -> 'CorpusIndex':
        """Index the corpus under `scope`.

        Raises:
            PhaseBError: `git ls-files` fails, as it does outside a work tree.
            RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
        """
        files = tracked_files(scope)
        directories = frozenset(parent.as_posix() for name in files for parent in pathlib.PurePosixPath(name).parents if parent.as_posix() != '.')
        roots = auditme.core._audit_roots(scope)
        src_root = roots[0] if roots else scope / 'src'
        definitions = auditme.core.corpus_definitions(scope, src_root, classes=True)
        index = cls(scope, files, directories, definitions, {}, {}, {}, {}, {})
        from_bindings: dict[str, dict[str, str]] = {}
        for path in auditme.core.corpus_py_files(scope, src_root):
            try:
                tree = ast.parse('\n'.join(auditme.core._source_lines(path)))
            except SyntaxError:
                continue
            rel = auditme.core._relpath(path, scope)
            root = next((r for r in roots if path.is_relative_to(r)), None)
            module = auditme.core.module_dotted(path, root) if root else None
            if module:
                from_bindings[module] = auditme.core.from_import_bindings(tree, module, path.name == '__init__.py')
            index.add_module(tree, path, rel, module)
        index.aliases = auditme.core.reexport_aliases(from_bindings, index.by_dotted.keys())
        return index

    def add_module(self, tree: ast.Module, path: pathlib.Path, rel: str, module: str | None) -> None:
        """Record a module's functions, classes and option literals."""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.record(path, node, DocTarget('function', f'{rel}::{node.name}', rel, *span(node)), module, node.name)
            elif isinstance(node, ast.ClassDef):
                target = DocTarget('class', f'{rel}::{node.name}', rel, *span(node))
                self.record(path, node, target, module, node.name)
                self.classes.setdefault(node.name, []).append(self.class_info(node, target, path, rel, module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and call_name(node) in OPTION_CALLS:
                for value in [*node.args, *(keyword.value for keyword in node.keywords)]:
                    if isinstance(value, ast.Constant) and isinstance(value.value, str) and _OPTION_RE.match(value.value):
                        target = DocTarget('option', f'{rel}::{value.value}', rel, node.lineno, node.end_lineno or node.lineno)
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
        info = ClassInfo(target, bases, {}, {})
        for member in node.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method = DocTarget('method', f'{rel}::{node.name}.{member.name}', rel, *span(member))
                info.members[member.name] = method
                self.record(path, member, method, module, f'{node.name}.{member.name}')
            elif isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                info.members[member.target.id] = field_target(node.name, rel, member.target.id, member)
                info.field_types[member.target.id] = [n.id for n in ast.walk(member.annotation) if isinstance(n, ast.Name)]
            elif isinstance(member, ast.Assign):
                for name in (t.id for t in member.targets if isinstance(t, ast.Name)):
                    info.members[name] = field_target(node.name, rel, name, member)
        return info

    def settings_classes(self) -> set[str]:
        """Names of the classes deriving, directly or through other corpus classes, from `BaseSettings`."""
        found: set[str] = set()
        changed = True
        while changed:
            changed = False
            for name, infos in self.classes.items():
                if name not in found and any(SETTINGS_BASE in info.bases or found & set(info.bases) for info in infos):
                    found.add(name)
                    changed = True
        return found


def field_target(class_name: str, rel: str, name: str, node: ast.stmt) -> DocTarget:
    """The target of a class field's statement."""
    return DocTarget('field', f'{rel}::{class_name}.{name}', rel, node.lineno, node.end_lineno or node.lineno)


def span(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> tuple[int, int]:
    """First and last line of a def or class, decorators included."""
    start = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
    return start, node.end_lineno or node.lineno


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
        raise PhaseBError(f'git ls-files failed in {scope}') from error
    return frozenset(name for name in result.stdout.decode('utf-8', errors='surrogateescape').split('\0') if name)


def file_target(index: CorpusIndex, rel: str) -> DocTarget:
    """The target of a tracked file, spanning all its lines.

    Raises:
        PhaseBError: the file cannot be read.
    """
    try:
        lines = (index.scope / rel).read_bytes().count(b'\n') + 1
    except OSError as error:
        raise PhaseBError(f'cannot read {rel}') from error
    return DocTarget('file', rel, rel, 1, lines)


def resolve_path(token: str, doc: pathlib.Path, index: CorpusIndex) -> list[DocTarget]:
    """A tracked file or directory, relative to the repository root, then to the document's directory."""
    if '/' not in token and not token.endswith(PATH_EXTENSIONS):
        return []
    doc_dir = doc.parent.relative_to(index.scope).as_posix()
    for candidate in (token, f'{doc_dir}/{token}'):
        rel = os.path.normpath(candidate.rstrip('/')).replace(os.sep, '/')
        if rel.startswith('..') or rel == '.':
            continue
        if rel in index.files:
            return [file_target(index, rel)]
        if rel in index.directories:
            return [DocTarget('directory', rel, rel, 1, 1)]
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
    owners = [(info, info.field_types.get(first, [])) for name in index.settings_classes() for info in index.classes[name] if first in info.members]
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


def resolve_name(token: str, doc: pathlib.Path, index: CorpusIndex) -> list[DocTarget]:
    """Resolve one token: [] for nothing, one target, or several when ambiguous.

    Tries, in order: a tracked path, a dotted name through the re-export
    aliases, a bare name, `Class.member`, a setting key, a command-line option.
    Each is positive evidence; nothing resolves by resemblance.
    """
    for step in (resolve_path, resolve_dotted, resolve_bare, resolve_member, resolve_setting, resolve_option):
        found = step(token, doc, index)
        if found:
            return found
    return []
