"""Markdown sections and the code-shaped names in them, for the Doc listers."""

import dataclasses
import pathlib
import re

from auditme.phaseb.errors import PhaseBError
from auditme.rules.project_hygiene import _CLASS_LINE_RE, _DEF_LINE_RE

# Changed only by a skill change with a brief version bump.
PATH_EXTENSIONS = ('.py', '.md', '.toml', '.yaml', '.yml', '.json', '.sh', '.txt', '.lock')
TREE_DEPTH = 3

_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
_FENCE_RE = re.compile(r'^\s*(```|~~~)')
_INLINE_CODE_RE = re.compile(r'`([^`\n]+)`')
_TRAILING_CALL_RE = re.compile(r'\(.*\)$')
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
    token = _TRAILING_CALL_RE.sub('', token.strip())
    if not token or ' ' in token or '<' in token:
        return None
    if token.startswith(('/', '~')):
        return None
    if '/' in token or token.endswith(PATH_EXTENSIONS) or _OPTION_RE.match(token):
        return token
    if _IDENTIFIER_RE.match(token) and ('_' in token or '.' in token or _INNER_CAPITAL_RE.search(token)):
        return token
    return None


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
        raise PhaseBError(f'cannot read {path}: {error}') from error
    doc = path.relative_to(root).as_posix()
    lines = text.splitlines()
    stack: list[tuple[int, str]] = []  # (level, title) of the enclosing headings
    seen: dict[str, int] = {}
    raw: list[tuple[str, int, list[tuple[int, str]], bool]] = []  # path, start, names, under API
    in_fence = False
    for number, line in enumerate(lines, start=1):
        if _FENCE_RE.match(line):
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
