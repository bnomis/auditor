#!/usr/bin/env python3
"""Audit checks driver.

Runs every mechanical check across the scope and emits JSON-lines.
Each line represents one hit. Callers (the auditme skill) must
transcribe every line into a finding - there is no sampling, filtering,
or "accepted because pre-existing" logic in the calling layer.

Usage:
    audit.py <scope-root> [--package <package-name>]

<scope-root> is the directory containing src/, agents/, docs/, etc.
<package-name> defaults to the single directory under src/.

Output schema (one JSON object per line):
    {
        "rule": "<rule-family-name>",
        "variant": "<variant-within-family>",
        "path": "<relative path>",
        "line": <1-indexed line number or null>,
        "evidence": "<source snippet or identifier>",
        "accepted": <bool>,
        "accepted_reason": "<why, if accepted>"
    }

Acceptance is determined exclusively by:
    1. AGENTS.md "Accepted cross-layer exceptions" / "Accepted lazy imports" tables
    2. An inline `# auditme: accept <reason>` comment on the preceding or
       same line as the hit.

No other signal acts as acceptance. The existence of a finding in a
prior review, a decision note, or an assumption of intentionality does
NOT make a hit accepted. Callers must treat `accepted=false` as a
required finding.
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import subprocess
import sys
from collections import defaultdict
from typing import Iterable

# An accept marker may name the single rule it answers for:
#     # auditme: accept[failure-as-absence] the caller reads batch.error
# An unscoped marker accepts every rule that fires on the line, which is how
# every marker written before 2026-08-12 behaves. That form is retained so no
# existing marker needs migrating, but it is the reason a newly added check can
# arrive silently pre-accepted: a marker weighed for one rule cannot have
# considered a rule that did not exist when it was written. New markers should
# name their rule.
ACCEPT_COMMENT_RE = re.compile(r'#\s*auditme:\s*accept\b(?:\[([a-z0-9-]+)\])?\s*(.*)$')


def _emit(**kwargs) -> None:
    print(json.dumps(kwargs, sort_keys=True))


def _source_lines(path: pathlib.Path) -> list[str]:
    try:
        return path.read_text(encoding='utf-8').splitlines()
    except UnicodeDecodeError:
        return []


def _accept_reason(
    lines: list[str],
    lineno: int,
    end_lineno: int | None = None,
    rule: str | None = None,
) -> str | None:
    """Return the accept reason covering this line for this rule, if any.

    A marker scoped to a rule (`accept[some-rule]`) answers only for that rule;
    one that names a different rule is ignored, so a decision taken about
    tracebacks cannot silently excuse a later check about return values. An
    unscoped marker answers for everything, which keeps every pre-existing
    marker working unchanged.

    `rule=None` means the caller has not said which rule is asking, and every
    marker matches. Passing the rule is what makes scoping effective, so a new
    check should always pass it.
    """
    candidates = list(range(lineno - 1, lineno + 1))
    if end_lineno is not None and end_lineno > lineno:
        candidates.extend(range(lineno + 1, end_lineno + 1))
    for candidate_lineno in candidates:
        if 1 <= candidate_lineno <= len(lines):
            m = ACCEPT_COMMENT_RE.search(lines[candidate_lineno - 1])
            if not m:
                continue
            scoped_to, reason = m.group(1), m.group(2)
            if scoped_to and rule and scoped_to != rule:
                continue
            return reason.strip() or 'no reason given'
    return None


def _type_checking_linenos(tree: ast.AST) -> set[int]:
    """Return line numbers inside any `if TYPE_CHECKING:` block."""
    result: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test_src = ast.unparse(node.test) if hasattr(ast, 'unparse') else ''
            if 'TYPE_CHECKING' in test_src:
                for child in ast.walk(node):
                    if hasattr(child, 'lineno'):
                        result.add(child.lineno)
    return result


def _all_py_files(src_root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in src_root.rglob('*.py'))


def _relpath(p: pathlib.Path, root: pathlib.Path) -> str:
    return str(p.relative_to(root))


def _accepted_lazy_imports(scope: pathlib.Path) -> set[tuple[str, str]]:
    agents = scope / 'AGENTS.md'
    if not agents.exists():
        return set()
    text = agents.read_text(encoding='utf-8')
    pairs: set[tuple[str, str]] = set()
    for line in text.splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < 2:
            continue
        m0 = re.findall(r'`([a-zA-Z_.][a-zA-Z0-9_.]*)`', cells[0])
        m1 = re.findall(r'`([a-zA-Z_.][a-zA-Z0-9_.]*)`', cells[1])
        for a in m0:
            for b in m1:
                pairs.add((a, b))
    return pairs


def check_ruff(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    for cmd, variant in (
        (['ruff', 'check', '--output-format=json', str(src_root)], 'ruff-check'),
        (['ruff', 'format', '--check', str(src_root)], 'ruff-format'),
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=scope)
        except FileNotFoundError:
            _emit(
                rule='ruff',
                variant=variant,
                path=None,
                line=None,
                evidence='ruff not installed',
                accepted=False,
                accepted_reason=None,
            )
            continue
        if variant == 'ruff-check' and result.stdout.strip():
            try:
                for hit in json.loads(result.stdout):
                    _emit(
                        rule='ruff',
                        variant=hit.get('code', 'ruff-check'),
                        path=_relpath(pathlib.Path(hit['filename']), scope),
                        line=hit['location']['row'],
                        evidence=hit.get('message', ''),
                        accepted=False,
                        accepted_reason=None,
                    )
            except json.JSONDecodeError:
                _emit(rule='ruff', variant='ruff-check-parse-error', path=None, line=None, evidence=result.stdout[:200], accepted=False, accepted_reason=None)
        elif variant == 'ruff-format' and result.returncode != 0:
            for ln in result.stdout.splitlines() + result.stderr.splitlines():
                if 'Would reformat' in ln or ln.endswith('.py'):
                    _emit(
                        rule='ruff', variant='ruff-format', path=ln.split(':')[0].strip(), line=None, evidence=ln.strip(), accepted=False, accepted_reason=None
                    )


def check_text_patterns(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    patterns: list[tuple[str, str, re.Pattern]] = [
        ('wildcard-imports', 'from X import *', re.compile(r'^from [\w.]+ import \*')),
        ('future-annotations', 'from __future__', re.compile(r'^from __future__ ')),
        ('aliased-imports', 'import X as Y', re.compile(r'^import [\w.]+ as [\w]+$')),
        ('legacy-typing', 'Union/Optional/List/Dict/Tuple/Set/FrozenSet/Type', re.compile(r'\b(Union|Optional|List|Dict|Tuple|Set|FrozenSet|Type)\[')),
        ('legacy-formatting-format', '.format() call', re.compile(r'\.format\s*\(')),
        # %-formatting is a pain to disambiguate from strftime. Do it in a
        # dedicated check below (check_percent_formatting).
        ('stdlib-logging', 'stdlib logging import', re.compile(r'^(import logging$|from logging )')),
        ('relative-import-nonpackage', 'relative import outside __init__.py', re.compile(r'^from \.+\w')),
        ('leading-underscore-def-class', 'module-level def/class _x', re.compile(r'^(def|class) _[a-zA-Z]')),
        ('leading-underscore-const-upper', 'module-level _NAME = ...', re.compile(r'^_[A-Z][A-Z0-9_]*\s*[:=]')),
        ('leading-underscore-const-lower', 'module-level _name = ...', re.compile(r'^_[a-z][a-zA-Z0-9_]*\s*[:=]')),
        ('leading-underscore-self', 'self._attr', re.compile(r'\bself\._[a-zA-Z]')),
        ('leading-underscore-destructure-first', 'destructured `_x, y = ...`', re.compile(r'^\s+_[a-z][a-zA-Z0-9_]*\s*,\s*[a-zA-Z]')),
        ('leading-underscore-destructure-second', 'destructured `x, _y = ...`', re.compile(r'^\s+[a-zA-Z][a-zA-Z0-9_]*\s*,\s*_[a-zA-Z][a-zA-Z0-9_]*\s*=')),
        ('leading-underscore-forloop-single', 'for _x in', re.compile(r'\bfor\s+_[a-z][a-zA-Z0-9_]+\s+in\b')),
        ('leading-underscore-forloop-first', 'for _x, y in', re.compile(r'\bfor\s+_[a-z][a-zA-Z0-9_]*\s*,\s*[a-zA-Z_][a-zA-Z0-9_]*\s+in\b')),
        ('leading-underscore-forloop-second', 'for x, _y in', re.compile(r'\bfor\s+[a-zA-Z][a-zA-Z0-9_]*\s*,\s*_[a-zA-Z][a-zA-Z0-9_]*\s+in\b')),
        ('leading-underscore-attribute-access', 'obj._attr in code or docstring', re.compile(r'[a-zA-Z_][\w]*\._[a-zA-Z]')),
    ]
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        is_init = path.name == '__init__.py'
        for idx, raw in enumerate(lines, 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith('#'):
                continue
            for rule, variant, pat in patterns:
                if rule == 'relative-import-nonpackage' and is_init:
                    continue
                if not pat.search(raw):
                    continue
                accept = _accept_reason(lines, idx, rule=rule)
                _emit(
                    rule=rule,
                    variant=variant,
                    path=rel,
                    line=idx,
                    evidence=stripped[:200],
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


_STRFTIME_TOKENS = {'%Y', '%y', '%m', '%d', '%H', '%I', '%M', '%S', '%p', '%A', '%a', '%B', '%b', '%j', '%U', '%W', '%c', '%x', '%X', '%Z', '%z', '%f'}


def check_percent_formatting(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `%s`/`%d`/`%r`-style C-printf formatting in Python string literals,
    but do NOT flag strftime directives. Heuristic: if the literal contains
    any strftime token (e.g. `%Y`, `%m`), treat it as a strftime call site."""
    suspect_re = re.compile(r'%[sdrfg]|%\d+[sdrfg]')
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        for idx, raw in enumerate(lines, 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith('#'):
                continue
            # extract string literals
            strings = re.findall(r"""(?:[fF]?r?)?['"](?:[^'"\\]|\\.)*['"]""", raw)
            for s in strings:
                if not suspect_re.search(s):
                    continue
                if any(tok in s for tok in _STRFTIME_TOKENS):
                    continue
                accept = _accept_reason(lines, idx, rule='legacy-formatting-percent')
                _emit(
                    rule='legacy-formatting-percent',
                    variant='%-style C-printf formatting in Python string',
                    path=rel,
                    line=idx,
                    evidence=stripped[:200],
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
                break


def check_def_class_in_init(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    for path in _all_py_files(src_root):
        if path.name != '__init__.py':
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        for idx, raw in enumerate(lines, 1):
            if re.match(r'^(def |class )', raw):
                accept = _accept_reason(lines, idx, rule='def-class-in-init')
                _emit(
                    rule='def-class-in-init',
                    variant='top-level def or class in __init__.py',
                    path=rel,
                    line=idx,
                    evidence=raw.strip()[:200],
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


def _walk_function_scopes(tree: ast.AST) -> Iterable[ast.AST]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


_STDLIB = {
    'abc',
    'argparse',
    'ast',
    'asyncio',
    'base64',
    'collections',
    'contextlib',
    'copy',
    'csv',
    'dataclasses',
    'datetime',
    'decimal',
    'enum',
    'errno',
    'functools',
    'gc',
    'glob',
    'gzip',
    'hashlib',
    'heapq',
    'importlib',
    'inspect',
    'io',
    'ipaddress',
    'itertools',
    'json',
    'locale',
    'logging',
    'math',
    'mimetypes',
    'operator',
    'os',
    'pathlib',
    'platform',
    'pprint',
    'queue',
    'random',
    're',
    'secrets',
    'shlex',
    'shutil',
    'signal',
    'socket',
    'sqlite3',
    'ssl',
    'stat',
    'string',
    'struct',
    'subprocess',
    'sys',
    'tempfile',
    'textwrap',
    'threading',
    'time',
    'timeit',
    'token',
    'tokenize',
    'traceback',
    'types',
    'typing',
    'unicodedata',
    'urllib',
    'uuid',
    'warnings',
    'weakref',
    'xml',
    'zipfile',
    'zoneinfo',
}


def check_in_function_imports(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    accepted_pairs = _accepted_lazy_imports(scope)
    for path in _all_py_files(src_root):
        if path.name == '__init__.py':
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        type_checking_linenos = _type_checking_linenos(tree)
        importerror_linenos: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                handles = False
                for h in node.handlers:
                    if (
                        isinstance(h.type, ast.Name)
                        and h.type.id in {'ImportError', 'ModuleNotFoundError'}
                        or (
                            isinstance(h.type, ast.Tuple)
                            and any(isinstance(e, ast.Name) and e.id in {'ImportError', 'ModuleNotFoundError'} for e in h.type.elts)
                        )
                    ):
                        handles = True
                if handles:
                    for child in node.body:
                        for sub in ast.walk(child):
                            if hasattr(sub, 'lineno'):
                                importerror_linenos.add(sub.lineno)
        importer_module = rel.replace('/', '.').removesuffix('.py').removeprefix('src.')
        for func in _walk_function_scopes(tree):
            for inner in ast.walk(func):
                if not isinstance(inner, (ast.Import, ast.ImportFrom)):
                    continue
                if inner.lineno in type_checking_linenos:
                    continue
                if inner.lineno in importerror_linenos:
                    continue
                if isinstance(inner, ast.Import):
                    imported_names = [n.name for n in inner.names]
                else:
                    imported_names = [inner.module or '']
                accept = _accept_reason(lines, inner.lineno, rule='in-function-import')
                for imported in imported_names:
                    pair_accepted = any(importer_module.startswith(a) and imported.startswith(b) for (a, b) in accepted_pairs)
                    if pair_accepted:
                        accept = accept or f'AGENTS.md accepted ({importer_module} -> {imported})'
                    top = imported.split('.')[0]
                    variant = 'stdlib' if top in _STDLIB else ('first-party' if importer_module.split('.')[0] == top else 'third-party')
                    _emit(
                        rule='in-function-import',
                        variant=variant,
                        path=rel,
                        line=inner.lineno,
                        evidence=f'{"import" if isinstance(inner, ast.Import) else "from"} {imported}',
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )


def check_silent_broad_except(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            exc = node.type
            exc_names: list[str] = []
            if isinstance(exc, ast.Name):
                exc_names = [exc.id]
            elif isinstance(exc, ast.Tuple):
                exc_names = [e.id for e in exc.elts if isinstance(e, ast.Name)]
            elif exc is None:
                exc_names = ['*bare*']
            if not any(n in {'Exception', 'BaseException', '*bare*'} for n in exc_names):
                continue
            body_src = '\n'.join(ast.unparse(c) for c in node.body) if hasattr(ast, 'unparse') else ''
            has_log = bool(re.search(r'\blogger\.|loguru\.logger\.|logging\.', body_src))
            has_raise = any(isinstance(c, ast.Raise) for c in ast.walk(node))
            if has_log or has_raise:
                continue
            accept = _accept_reason(lines, node.lineno, rule='silent-broad-except')
            _emit(
                rule='silent-broad-except',
                variant='no logger and no raise in body',
                path=rel,
                line=node.lineno,
                evidence=lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else '',
                accepted=bool(accept),
                accepted_reason=accept,
            )


def _stmt_end_by_lineno(tree: ast.AST) -> dict[int, int]:
    """Map each source line to the max end_lineno of any statement enclosing it."""
    mapping: dict[int, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            for ln in range(node.lineno, node.end_lineno + 1):
                if mapping.get(ln, 0) < node.end_lineno:
                    mapping[ln] = node.end_lineno
    return mapping


def _is_categorical_class_name_expr(expr_src: str, bound: str) -> bool:
    """Return True when expr_src is a categorical class-name access on the
    bound exception name (e.g. ``type(exc).__name__`` or
    ``exc.__class__.__qualname__``). These patterns expose only the
    exception class string, not the lossy ``str(exc)`` message body, and
    do not duplicate the chained traceback that ``raise ... from exc``
    or ``logger.exception`` already preserve.
    """
    safe_attrs = ('__name__', '__qualname__')
    bound_re = re.escape(bound)
    patterns = [rf'^type\(\s*{bound_re}\s*\)\.{attr}$' for attr in safe_attrs]
    patterns += [rf'^{bound_re}\.__class__\.{attr}$' for attr in safe_attrs]
    return any(re.match(p, expr_src.strip()) for p in patterns)


def check_except_interpolation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag f-string or logger-positional interpolation of a caught
    exception variable inside an ``except ... as <bound>:`` block.
    Rationale: ``raise X from exc`` and ``logger.exception(...)`` already
    preserve the chained traceback at full fidelity; embedding
    ``str(exc)`` (or its f-string equivalent) into a new message
    produces a truncated copy that drifts from the original.

    Exception (review-36): ``type(<bound>).__name__`` / ``__qualname__``
    and ``<bound>.__class__.__name__`` / ``__qualname__`` access only
    the exception class name string. The class name is a categorical
    hint, not a lossy duplication of the message body, so these
    patterns are skipped without emitting a hit. See
    ``_is_categorical_class_name_expr``.
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        stmt_end = _stmt_end_by_lineno(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler) or not node.name:
                continue
            bound = node.name
            seen_linenos: set[tuple[int, str]] = set()
            for inner in ast.walk(node):
                if isinstance(inner, ast.JoinedStr):
                    flagged = False
                    for v in inner.values:
                        if flagged:
                            break
                        if isinstance(v, ast.FormattedValue):
                            expr_src = ast.unparse(v.value) if hasattr(ast, 'unparse') else ''
                            if not re.search(rf'\b{re.escape(bound)}\b', expr_src):
                                continue
                            if _is_categorical_class_name_expr(expr_src, bound):
                                continue
                            key = (inner.lineno, 'fstring')
                            if key in seen_linenos:
                                flagged = True
                                break
                            seen_linenos.add(key)
                            end_ln = stmt_end.get(inner.lineno)
                            accept = _accept_reason(lines, inner.lineno, end_ln, rule='except-interpolation')
                            _emit(
                                rule='except-interpolation',
                                variant='f-string interpolates caught exception',
                                path=rel,
                                line=inner.lineno,
                                evidence=(lines[inner.lineno - 1].strip()[:200] if inner.lineno <= len(lines) else ''),
                                accepted=bool(accept),
                                accepted_reason=accept,
                            )
                            flagged = True
                            break
                if isinstance(inner, ast.Call):
                    func_src = ast.unparse(inner.func) if hasattr(ast, 'unparse') else ''
                    if re.search(r'logger\.(warning|error|exception)$', func_src):
                        for arg in inner.args:
                            arg_src = ast.unparse(arg) if hasattr(ast, 'unparse') else ''
                            if re.fullmatch(rf'\s*{re.escape(bound)}\s*', arg_src):
                                key = (inner.lineno, 'logger-arg')
                                if key in seen_linenos:
                                    continue
                                seen_linenos.add(key)
                                end_ln = stmt_end.get(inner.lineno)
                                accept = _accept_reason(lines, inner.lineno, end_ln, rule='except-interpolation')
                                _emit(
                                    rule='except-interpolation',
                                    variant='logger positional arg is caught exception',
                                    path=rel,
                                    line=inner.lineno,
                                    evidence=(lines[inner.lineno - 1].strip()[:200] if inner.lineno <= len(lines) else ''),
                                    accepted=bool(accept),
                                    accepted_reason=accept,
                                )


def check_literal_duplication(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    bucket: dict[tuple, set[tuple[str, int, str]]] = defaultdict(set)
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        # Find frozenset(...) / set(...) call nodes so we can skip their inner ast.Set/Tuple child
        skip_inner_nodes: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'frozenset', 'set'}:
                if node.args and isinstance(node.args[0], (ast.Set, ast.Tuple, ast.List)):
                    skip_inner_nodes.add(id(node.args[0]))
        for node in ast.walk(tree):
            if id(node) in skip_inner_nodes:
                continue
            members = None
            kind = None
            if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
                members = node.elts
                kind = type(node).__name__
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {'frozenset', 'set'}:
                    if node.args and isinstance(node.args[0], (ast.Set, ast.Tuple, ast.List)):
                        members = node.args[0].elts
                        kind = 'frozenset'
            if not members:
                continue
            consts: list[str] = []
            ok = True
            for m in members:
                if isinstance(m, ast.Constant) and isinstance(m.value, str):
                    consts.append(m.value)
                else:
                    ok = False
                    break
            if not ok or not consts:
                continue
            if kind in {'Set', 'frozenset'}:
                key = ('unordered', tuple(sorted(consts)))
            else:
                key = ('ordered', tuple(consts))
            bucket[key].add((rel, node.lineno, repr(tuple(consts))))
    for key, hits in bucket.items():
        if len(hits) < 2:
            continue
        # A single file can legitimately have two copies at different linenos;
        # that's still a finding. But if the same (path, line) is hit twice,
        # dedup via the set.
        for rel, lineno, evidence in sorted(hits):
            full = scope / rel
            full_lines = _source_lines(full)
            accept = _accept_reason(full_lines, lineno, rule='literal-duplication')
            _emit(
                rule='literal-duplication',
                variant=f'identical {key[0]} literal across {len(hits)} locations',
                path=rel,
                line=lineno,
                evidence=evidence[:200],
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_nonalphabetical_literals(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if value is None:
                continue
            members = None
            if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
                members = value.elts
            elif (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == 'frozenset'
                and value.args
                and isinstance(value.args[0], (ast.Set, ast.List, ast.Tuple))
            ):
                members = value.args[0].elts
            if not members or len(members) < 2:
                continue
            if not all(isinstance(m, ast.Constant) and isinstance(m.value, str) for m in members):
                continue
            actual = [m.value for m in members]
            if actual == sorted(actual):
                continue
            accept = _accept_reason(lines, node.lineno, rule='non-alphabetical-literal')
            _emit(
                rule='non-alphabetical-literal',
                variant='string members not alphabetically sorted',
                path=rel,
                line=node.lineno,
                evidence=f'{actual!r}',
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_unused_submodule_imports(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        full_src = '\n'.join(lines)
        for node in tree.body:
            if not isinstance(node, ast.Import):
                continue
            for alias in node.names:
                if alias.asname:
                    continue
                if '.' not in alias.name:
                    continue
                import_line_src = lines[node.lineno - 1] if node.lineno <= len(lines) else ''
                remainder = full_src.replace(import_line_src, '', 1)
                if re.search(rf'\b{re.escape(alias.name)}\b', remainder):
                    continue
                root_name = alias.name.split('.')[0]
                if re.search(rf'\b{re.escape(root_name)}\.', remainder):
                    continue
                accept = _accept_reason(lines, node.lineno, rule='unused-submodule-import')
                _emit(
                    rule='unused-submodule-import',
                    variant='import X.Y.Z never referenced',
                    path=rel,
                    line=node.lineno,
                    evidence=f'import {alias.name}',
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


def check_paired_sibling_helpers(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    bodies: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            try:
                body_src = '\n'.join(ast.unparse(b) for b in node.body if not isinstance(b, ast.Expr) or not isinstance(b.value, ast.Constant))
            except Exception:
                continue
            if not body_src.strip() or len(body_src) < 40:
                continue
            bodies[body_src].append((rel, node.lineno, node.name))
    for body_src, hits in bodies.items():
        if len(hits) < 2:
            continue
        files = {h[0] for h in hits}
        if len(files) < 2:
            continue
        for rel, lineno, fname in hits:
            full = scope / rel
            full_lines = _source_lines(full)
            accept = _accept_reason(full_lines, lineno, rule='paired-sibling-helpers')
            peers = sorted(set(h[2] for h in hits) - {fname})
            _emit(
                rule='paired-sibling-helpers',
                variant=f'{len(hits)} functions share a body across files',
                path=rel,
                line=lineno,
                evidence=f'def {fname}(...) - matches: {", ".join(peers) or "(peer)"}',
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_lockfile(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    pyproject = scope / 'pyproject.toml'
    uvlock = scope / 'uv.lock'
    if not pyproject.exists() or not uvlock.exists():
        return
    try:
        result = subprocess.run(['uv', 'lock', '--check'], capture_output=True, text=True, cwd=scope)
        if result.returncode != 0:
            _emit(
                rule='lockfile-drift',
                variant='uv lock --check failed',
                path='uv.lock',
                line=None,
                evidence=(result.stderr or result.stdout).strip()[:200],
                accepted=False,
                accepted_reason=None,
            )
    except FileNotFoundError:
        pass


def _parse_package_layering(scope: pathlib.Path) -> tuple[list[str], set[tuple[str, str]]]:
    """Parse AGENTS.md's Package Layering section.

    Returns (layer_order, accepted_exceptions). layer_order is a list of
    package names from low to high; accepted_exceptions is a set of
    (importer_pkg, imported_pkg) pairs that are explicitly allowed to
    invert the layering.
    """
    agents = scope / 'AGENTS.md'
    if not agents.exists():
        return [], set()
    text = agents.read_text(encoding='utf-8')
    layer_order: list[str] = []
    accepted: set[tuple[str, str]] = set()
    in_layering_section = False
    in_exceptions_table = False
    for line in text.splitlines():
        if re.match(r'^##+\s+Package\s+Layering', line, re.IGNORECASE):
            in_layering_section = True
            continue
        if in_layering_section and re.match(r'^##+ ', line):
            # next heading; check if it is the exceptions sub-section
            if re.search(r'Accepted\s+(cross-layer\s+)?exceptions?', line, re.IGNORECASE):
                in_exceptions_table = True
                continue
            else:
                in_layering_section = False
                in_exceptions_table = False
                continue
        if in_layering_section and not in_exceptions_table and not layer_order:
            # match `data < config < ...` or similar single-line layer order
            if '<' in line and '`' not in line:
                clean = line.strip().strip('`')
                parts = [p.strip().strip('`') for p in clean.split('<')]
                if len(parts) >= 2 and all(re.match(r'^[a-z_][a-z0-9_]*$', p) for p in parts):
                    layer_order = parts
            elif line.strip().startswith('```'):
                continue
        if in_exceptions_table and line.startswith('|'):
            cells = [c.strip() for c in line.strip('|').split('|')]
            if len(cells) < 2:
                continue
            m0 = re.findall(r'`([a-zA-Z_.][a-zA-Z0-9_.]*)`', cells[0])
            m1 = re.findall(r'`([a-zA-Z_.][a-zA-Z0-9_.]*)`', cells[1])
            for a in m0:
                for b in m1:
                    accepted.add((a.split('.')[0], b.split('.')[0]))
    return layer_order, accepted


def check_layering_violations(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Walk every import; if it is a first-party import and goes upward
    in the layering chain, flag unless the (importer, imported) pair is
    in AGENTS.md's accepted-exceptions table or the line carries an
    `# auditme: accept` marker."""
    layer_order, accepted = _parse_package_layering(scope)
    if not layer_order:
        return
    rank = {pkg: i for i, pkg in enumerate(layer_order)}
    package_root_name = src_root.name  # e.g. 'feathf'

    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        # importer's package is the first component under src_root
        rel_parts = path.relative_to(src_root).parts
        if len(rel_parts) < 2:
            continue
        importer_pkg = rel_parts[0]
        if importer_pkg not in rank:
            continue
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        tc_linenos = _type_checking_linenos(tree)
        for node in ast.walk(tree):
            module_name = None
            if isinstance(node, ast.Import):
                if node.lineno in tc_linenos:
                    continue
                for alias in node.names:
                    module_name = alias.name
                    _maybe_emit_layering(rel, lines, node.lineno, importer_pkg, module_name,
                                         rank, accepted, package_root_name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.lineno in tc_linenos:
                    continue
                module_name = node.module
                _maybe_emit_layering(rel, lines, node.lineno, importer_pkg, module_name,
                                     rank, accepted, package_root_name)


def _maybe_emit_layering(rel, lines, lineno, importer_pkg, module_name,
                         rank, accepted, package_root_name):
    if not module_name.startswith(package_root_name + '.'):
        return
    parts = module_name.split('.')
    if len(parts) < 2:
        return
    imported_pkg = parts[1]
    if imported_pkg == importer_pkg:
        return
    if imported_pkg not in rank:
        return
    if rank[imported_pkg] <= rank[importer_pkg]:
        return  # downward or equal; fine
    if (importer_pkg, imported_pkg) in accepted:
        return
    accept = _accept_reason(lines, lineno, rule='layering-violation')
    _emit(
        rule='layering-violation',
        variant=f'{importer_pkg} imports {imported_pkg} (upward)',
        path=rel,
        line=lineno,
        evidence=f'import {module_name}',
        accepted=bool(accept),
        accepted_reason=accept,
    )


def check_broad_except_wrong_level(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `except (Exception|BaseException):` blocks whose body calls
    logger.warning / logger.error / logger.debug / logger.info instead of
    logger.exception. Distinct from check_silent_broad_except, which only
    catches blocks with NO logger call at all."""
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            exc = node.type
            exc_names: list[str] = []
            if isinstance(exc, ast.Name):
                exc_names = [exc.id]
            elif isinstance(exc, ast.Tuple):
                exc_names = [e.id for e in exc.elts if isinstance(e, ast.Name)]
            elif exc is None:
                exc_names = ['*bare*']
            if not any(n in {'Exception', 'BaseException', '*bare*'} for n in exc_names):
                continue
            body_src = '\n'.join(ast.unparse(c) for c in node.body) if hasattr(ast, 'unparse') else ''
            wrong_level = re.search(r'\b(logger|loguru\.logger|logging)\.(warning|error|info|debug)\(', body_src)
            if not wrong_level:
                continue
            accept = _accept_reason(lines, node.lineno, rule='broad-except-wrong-level')
            _emit(
                rule='broad-except-wrong-level',
                variant='broad except logs at warning/error/info/debug instead of exception',
                path=rel,
                line=node.lineno,
                evidence=lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else '',
                accepted=bool(accept),
                accepted_reason=accept,
            )


_DISK_IO_NAMES = {
    'open', 'mkdir', 'rmdir', 'unlink', 'rmtree', 'makedirs', 'remove',
    'read_text', 'write_text', 'read_bytes', 'write_bytes', 'touch',
    'iterdir', 'glob', 'rglob', 'exists', 'is_file', 'is_dir', 'stat',
    'copy', 'copytree', 'move', 'rename', 'replace', 'symlink_to',
    'mkstemp', 'mkdtemp',
}


def check_constructor_disk_io(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag disk I/O operations inside `__init__` methods. Constructors
    should accept already-loaded data, not perform I/O on demand."""
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            for member in cls.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if member.name != '__init__':
                    continue
                for inner in ast.walk(member):
                    if not isinstance(inner, ast.Call):
                        continue
                    fname = None
                    if isinstance(inner.func, ast.Name):
                        fname = inner.func.id
                    elif isinstance(inner.func, ast.Attribute):
                        fname = inner.func.attr
                    if fname not in _DISK_IO_NAMES:
                        continue
                    accept = _accept_reason(lines, inner.lineno, rule='constructor-disk-io')
                    _emit(
                        rule='constructor-disk-io',
                        variant=f'{cls.name}.__init__ calls disk-IO `{fname}`',
                        path=rel,
                        line=inner.lineno,
                        evidence=lines[inner.lineno - 1].strip()[:200]
                        if inner.lineno <= len(lines) else '',
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )


def check_passthrough_shim(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag module-level functions whose body is exactly `return f(...)`
    where the call's args are the function's own parameters. These are
    pass-through shims that add no behaviour and obscure the real callee."""
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # strip a leading docstring
            body = [b for b in node.body if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
            if len(body) != 1:
                continue
            stmt = body[0]
            if not isinstance(stmt, ast.Return) or not isinstance(stmt.value, ast.Call):
                continue
            call = stmt.value
            # Compare args: every positional must be a Name matching a parameter
            param_names = [a.arg for a in node.args.args]
            if not call.args:
                continue
            if not all(isinstance(a, ast.Name) and a.id in param_names for a in call.args):
                continue
            try:
                call_src = ast.unparse(call.func)
            except Exception:
                continue
            # skip self.<method>(args) - that's typical delegation, not a shim
            if call_src.startswith('self.'):
                continue
            accept = _accept_reason(lines, node.lineno, rule='passthrough-shim')
            _emit(
                rule='passthrough-shim',
                variant=f'{node.name} is a pass-through wrapper for {call_src}',
                path=rel,
                line=node.lineno,
                evidence=f'def {node.name}(...): return {call_src}(...)',
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_empty_init_with_exporting_siblings(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag any subpackage `__init__.py` that exports nothing while at
    least one sibling subpackage exports a non-trivial public surface.
    Sparse public surfaces force consumers to reach into private submodules.

    Acceptance (review-36): this is a file-level finding, so the
    accept-marker scan looks at every line in the file rather than just
    the docstring line. A docstring-only ``__init__.py`` cannot host an
    inline comment on the docstring opener; the marker has to land on a
    separate comment-only line. Any line containing
    ``# auditme: accept <reason>`` accepts the file."""
    init_files: dict[pathlib.Path, int] = {}
    for path in _all_py_files(src_root):
        if path.name != '__init__.py':
            continue
        # Skip the top-level package init (parent is src_root itself)
        if path.parent == src_root:
            continue
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        export_count = 0
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == '__all__':
                        if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                            export_count = len(node.value.elts)
            elif isinstance(node, (ast.ImportFrom,)) and node.module:
                # `from .x import Y` style re-exports
                export_count += len(node.names)
        init_files[path] = export_count
    if not init_files:
        return
    sibling_max = max(init_files.values())
    if sibling_max < 5:
        return  # no sibling exports a non-trivial surface; rule does not apply
    for path, count in init_files.items():
        if count != 0:
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        # File-level finding: scan every line for an `# auditme: accept`
        # marker. The standard line-bracketed `_accept_reason` only checks
        # the hit line and its predecessor, but a docstring-only
        # `__init__.py` cannot host an inline comment on the docstring
        # line itself - the marker has to land on a comment-only line
        # somewhere in the file.
        accept: str | None = None
        for ln in range(1, len(lines) + 1):
            accept = _accept_reason(lines, ln, rule='empty-init-while-siblings-export')
            if accept:
                break
        _emit(
            rule='empty-init-while-siblings-export',
            variant=f'{path.parent.name}/__init__.py exports 0 symbols; siblings export up to {sibling_max}',
            path=rel,
            line=1,
            evidence=f'no __all__ and no re-exports',
            accepted=bool(accept),
            accepted_reason=accept,
        )


def check_mixed_raise_types(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag methods/functions that raise two or more different exception
    types where the types do not share a clear inheritance relationship.
    A common architecture smell: half the invariants raise PipelineError,
    half raise stdlib RuntimeError - callers cannot establish a clean
    catch envelope."""
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            raised_types: dict[str, list[int]] = defaultdict(list)
            for inner in ast.walk(node):
                if isinstance(inner, ast.Raise) and isinstance(inner.exc, ast.Call):
                    fn = inner.exc.func
                    if isinstance(fn, ast.Name):
                        raised_types[fn.id].append(inner.lineno)
                    elif isinstance(fn, ast.Attribute):
                        try:
                            raised_types[ast.unparse(fn).split('.')[-1]].append(inner.lineno)
                        except Exception:
                            pass
            if len(raised_types) < 2:
                continue
            # exclude common cases where the mix is intentional: re-raise of
            # input-validation distinct from internal invariants is signalled
            # by error suffix matching: ConfigError + InputEnvelopeError is one
            # cluster; RuntimeError + PipelineError is a real mix
            stdlib_excs = {'RuntimeError', 'ValueError', 'TypeError', 'KeyError', 'IndexError', 'AttributeError'}
            project_excs = {n for n in raised_types if n.endswith('Error') and n not in stdlib_excs}
            if not project_excs:
                continue
            mixed_with_stdlib = stdlib_excs & raised_types.keys()
            if not mixed_with_stdlib:
                continue
            # Emit ONE finding per function, listing every raise site
            sample_line = sorted(min(v) for v in raised_types.values())[0]
            accept = _accept_reason(lines, sample_line, rule='mixed-raise-types')
            evidence = f'{node.name}: raises {sorted(raised_types.keys())}'
            _emit(
                rule='mixed-raise-types',
                variant=f'{node.name} mixes stdlib ({sorted(mixed_with_stdlib)}) with project errors ({sorted(project_excs)})',
                path=rel,
                line=node.lineno,
                evidence=evidence,
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_migration_shim_consumers(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Detect re-export shims (`X = canonical.X` style aliases) and flag
    any consumer that imports via the shim instead of the canonical home.

    Mechanical signal: a module-level assignment `X = pkg.mod.X` where the
    LHS name equals the RHS attribute is a re-export shim for symbol X
    whose canonical home is `pkg.mod`. Any importer that reads `X` via
    the shim's path is using a deprecated migration shim.
    """
    package_root_name = src_root.name
    # canonical_home: dict[symbol_name -> set[canonical_module_dotted_path]]
    canonical_home: dict[str, set[str]] = defaultdict(set)
    # shims: dict[shim_module_dotted_path -> set[(symbol, canonical_module)]]
    shims: dict[str, set[tuple[str, str]]] = defaultdict(set)

    for path in _all_py_files(src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = _relpath(path, scope)
        # mod path like 'feathf.models.settings'
        rel_parts = path.relative_to(src_root).parts
        if rel_parts[-1] == '__init__.py':
            shim_mod = package_root_name + '.' + '.'.join(rel_parts[:-1]) if len(rel_parts) > 1 else package_root_name
        else:
            shim_mod = package_root_name + '.' + '.'.join(rel_parts)[:-3]  # strip '.py'
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            # X = feathf.something.X
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if value is None:
                continue
            if not (isinstance(value, ast.Attribute) and isinstance(value.value, ast.Attribute | ast.Name)):
                continue
            # unparse RHS to get full dotted path
            try:
                rhs = ast.unparse(value)
            except Exception:
                continue
            if not rhs.startswith(package_root_name + '.'):
                continue
            sym = value.attr
            for tgt in targets:
                if isinstance(tgt, ast.Name) and tgt.id == sym:
                    canonical_mod = rhs.rsplit('.', 1)[0]  # everything before the symbol
                    canonical_home[sym].add(canonical_mod)
                    shims[shim_mod].add((sym, canonical_mod))
    # Now walk all imports project-wide; for each symbol with an established
    # canonical home AND a known shim, find any consumer that reads the
    # symbol via the shim's module path.
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        # the consumer is itself a module; do not flag the canonical or shim
        rel_parts = path.relative_to(src_root).parts
        if rel_parts[-1] == '__init__.py':
            consumer_mod = package_root_name + '.' + '.'.join(rel_parts[:-1]) if len(rel_parts) > 1 else package_root_name
        else:
            consumer_mod = package_root_name + '.' + '.'.join(rel_parts)[:-3]
        if consumer_mod in shims:
            continue
        lines = _source_lines(path)
        for node in ast.walk(tree):
            # Pattern 1: `from <shim_mod> import X` where X has a canonical home elsewhere
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module in shims:
                    for alias in node.names:
                        for sym, canonical_mod in shims[node.module]:
                            if alias.name == sym and canonical_mod != node.module:
                                accept = _accept_reason(lines, node.lineno, rule='migration-shim-consumer')
                                _emit(
                                    rule='migration-shim-consumer',
                                    variant=f'imports `{sym}` via shim `{node.module}`; canonical home is `{canonical_mod}`',
                                    path=rel,
                                    line=node.lineno,
                                    evidence=f'from {node.module} import {sym}',
                                    accepted=bool(accept),
                                    accepted_reason=accept,
                                )
            # Pattern 2: `<shim_mod>.X` attribute access where X has a canonical home
            if isinstance(node, ast.Attribute) and isinstance(node.value, (ast.Name, ast.Attribute)):
                try:
                    full = ast.unparse(node)
                except Exception:
                    continue
                if not full.startswith(package_root_name + '.'):
                    continue
                # Split into module-prefix and attr
                parent_mod, _, attr = full.rpartition('.')
                if parent_mod in shims:
                    for sym, canonical_mod in shims[parent_mod]:
                        if attr == sym and canonical_mod != parent_mod:
                            line_no = getattr(node, 'lineno', 1)
                            accept = _accept_reason(lines, line_no, rule='migration-shim-consumer')
                            _emit(
                                rule='migration-shim-consumer',
                                variant=f'reads `{sym}` from shim `{parent_mod}`; canonical home is `{canonical_mod}`',
                                path=rel,
                                line=line_no,
                                evidence=full[:200],
                                accepted=bool(accept),
                                accepted_reason=accept,
                            )


def check_silent_self_mutation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag methods (other than __init__ / __post_init__ / setters / setX-named
    methods / clear / reset / load) that reassign `self.<attr>` where `<attr>`
    was set from a constructor argument of the same name in __init__.

    The pattern is: a method whose name signals a non-mutating operation
    (a stage, a compute, a build, a load, a predict, a tokenize, a train,
    an evaluate) silently mutates state the caller passed in. Downstream
    stages consume the mutation through `self.<attr>` but a Python-API
    caller holding a reference to the original sees their view drift.
    """
    MUTATING_METHOD_NAMES = {
        'set', 'reset', 'clear', 'update', 'mutate', 'merge', 'replace',
        'apply', 'patch', 'override',
    }
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            # Find attrs assigned in __init__ from a same-named argument
            owned_attrs: set[str] = set()
            init = next(
                (m for m in cls.body
                 if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and m.name == '__init__'),
                None,
            )
            if init is not None:
                arg_names = {a.arg for a in init.args.args}
                for inner in ast.walk(init):
                    if not isinstance(inner, ast.Assign):
                        continue
                    for tgt in inner.targets:
                        if (isinstance(tgt, ast.Attribute)
                                and isinstance(tgt.value, ast.Name)
                                and tgt.value.id == 'self'
                                and isinstance(inner.value, ast.Name)
                                and inner.value.id == tgt.attr
                                and inner.value.id in arg_names):
                            owned_attrs.add(tgt.attr)
            if not owned_attrs:
                continue
            for member in cls.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if member.name in {'__init__', '__post_init__', '__setattr__'}:
                    continue
                lname = member.name.lower()
                # Method names that signal mutation are allowed (caller knows)
                if any(lname.startswith(p + '_') or lname == p for p in MUTATING_METHOD_NAMES):
                    continue
                if lname.startswith('set_'):
                    continue
                for inner in ast.walk(member):
                    if not isinstance(inner, ast.Assign):
                        continue
                    for tgt in inner.targets:
                        if not (isinstance(tgt, ast.Attribute)
                                and isinstance(tgt.value, ast.Name)
                                and tgt.value.id == 'self'):
                            continue
                        if tgt.attr not in owned_attrs:
                            continue
                        accept = _accept_reason(lines, inner.lineno, rule='silent-self-mutation')
                        _emit(
                            rule='silent-self-mutation',
                            variant=f'{cls.name}.{member.name} reassigns self.{tgt.attr}',
                            path=rel,
                            line=inner.lineno,
                            evidence=(lines[inner.lineno - 1].strip()[:200]
                                      if inner.lineno <= len(lines) else ''),
                            accepted=bool(accept),
                            accepted_reason=accept,
                        )


def check_asymmetric_exception_translation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Detect functions F such that:
      - F is a module-level (or public-looking) function that itself does
        NOT have a try/except around its body translating third-party
        exceptions to a project error class.
      - Every known call site of F is inside a `try: ... except <ProjectError>: ...`
        block that catches a third-party exception class and translates.
      - There are 2+ call sites with this shape.

    The asymmetric contract is a smell: a new caller that doesn't wrap F
    will leak the third-party exception. Mechanical signal the finding.
    """
    # First pass: enumerate every module-level function and whether its body
    # contains a top-level try/except handler.
    function_index: dict[str, tuple[str, int, bool]] = {}
    # function_index key is full dotted path (e.g. 'feathf.registry.runs.setup_mlflow_experiment')
    package_root_name = src_root.name

    for path in _all_py_files(src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = _relpath(path, scope)
        rel_parts = path.relative_to(src_root).parts
        if rel_parts[-1] == '__init__.py':
            mod = package_root_name + '.' + '.'.join(rel_parts[:-1]) if len(rel_parts) > 1 else package_root_name
        else:
            mod = package_root_name + '.' + '.'.join(rel_parts)[:-3]
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Check if function's OWN body has a try/except that catches anything
            has_own_try = any(isinstance(child, ast.Try) for child in node.body)
            function_index[f'{mod}.{node.name}'] = (rel, node.lineno, has_own_try)

    # Second pass: for every call to a known function, check the surrounding
    # context. If every call site in the project is inside a `try: ...
    # except <something>:` block AND the function itself has no try, flag.
    call_sites: dict[str, list[tuple[str, int, bool]]] = defaultdict(list)
    # key: callee full dotted path; value: list of (caller_path, lineno, is_wrapped)

    for path in _all_py_files(src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = _relpath(path, scope)
        # Track which nodes are inside a try block
        try_descendants: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                # Does this try have a handler that looks like it translates to
                # a ProjectError (a class name ending in 'Error' defined in this
                # package)? We only care about try blocks whose handlers raise
                # something that ends in 'Error'.
                translates = False
                for handler in node.handlers:
                    # Inspect handler body for `raise <Something>Error(...)`
                    for sub in ast.walk(handler):
                        if isinstance(sub, ast.Raise) and isinstance(sub.exc, ast.Call):
                            try:
                                raised = ast.unparse(sub.exc.func)
                            except Exception:
                                continue
                            # name ends in 'Error' or similar
                            tail = raised.rsplit('.', 1)[-1]
                            if tail.endswith('Error'):
                                translates = True
                                break
                    if translates:
                        break
                if translates:
                    for child in node.body:
                        for sub in ast.walk(child):
                            if hasattr(sub, 'lineno'):
                                try_descendants.add(id(sub))
        # Now walk every Call node and check its callee
        # We need to resolve callee to a full dotted path. Use ast.unparse.
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            try:
                callee_src = ast.unparse(node.func)
            except Exception:
                continue
            # Look up in function_index: match any entry whose suffix == callee_src
            # or whose full dotted path == callee_src
            callee_candidates = []
            if callee_src in function_index:
                callee_candidates.append(callee_src)
            else:
                # match `short_name` against entries where dotted path ends in `.short_name`
                for full in function_index:
                    if full.endswith('.' + callee_src):
                        callee_candidates.append(full)
            for callee in callee_candidates:
                is_wrapped = id(node) in try_descendants
                call_sites[callee].append((rel, node.lineno, is_wrapped))

    # Third pass: emit findings
    for callee, sites in call_sites.items():
        if len(sites) < 2:
            continue
        callee_path, callee_line, callee_has_try = function_index[callee]
        if callee_has_try:
            continue
        if not all(is_wrapped for (_, _, is_wrapped) in sites):
            continue
        # Every call site is wrapped; the function itself has no try.
        accept = _accept_reason(_source_lines(scope / callee_path), callee_line, rule='asymmetric-exception-translation')
        sites_summary = '; '.join(f'{p}:{n}' for (p, n, _) in sites[:5])
        _emit(
            rule='asymmetric-exception-translation',
            variant=f'{callee} has no own try/except; all {len(sites)} callers wrap it',
            path=callee_path,
            line=callee_line,
            evidence=f'called (wrapped) from: {sites_summary}',
            accepted=bool(accept),
            accepted_reason=accept,
        )


def check_sibling_error_no_common_base(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Detect project error classes that sit side-by-side in a `*/errors.py`
    module but have different base classes (one subclasses ProjectError,
    another subclasses stdlib Exception). The mismatch is a smell:
    existing `except ProjectError` catch sites will miss the sibling.

    Signal:
      - A file named `errors.py` defines >= 2 classes whose names end in
        `Error`.
      - At least one of the classes subclasses a project-local error base
        (any name ending in 'Error' that is not stdlib Exception).
      - At least one of the classes subclasses stdlib `Exception`
        (or has no explicit base).
      - The two groups are not related by inheritance within the file.

    A common mistake is defining `SignatureError(Exception)` next to
    `RegistryError(Exception)` without making them share a hierarchy.
    Call sites that catch `RegistryError` never catch `SignatureError`.
    """
    package_root_name = src_root.name
    for path in _all_py_files(src_root):
        if path.name != 'errors.py':
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        error_classes: list[tuple[str, int, list[str]]] = []
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith('Error'):
                continue
            base_names: list[str] = []
            for base in node.bases:
                try:
                    base_names.append(ast.unparse(base))
                except Exception:
                    pass
            error_classes.append((node.name, node.lineno, base_names))
        if len(error_classes) < 2:
            continue
        # Partition into "rooted at stdlib Exception" vs "rooted at a
        # project Error parent"
        rooted_at_stdlib: list[tuple[str, int, list[str]]] = []
        rooted_at_project: list[tuple[str, int, list[str]]] = []
        for name, lineno, bases in error_classes:
            if not bases or any(b.split('.')[-1] == 'Exception' for b in bases):
                rooted_at_stdlib.append((name, lineno, bases))
            elif any(b.split('.')[-1].endswith('Error') for b in bases):
                # If the base is one of the other classes defined in this file,
                # that's a real hierarchy; otherwise it's a new root
                sibling_names = {n for n, _, _ in error_classes}
                if any(b.split('.')[-1] in sibling_names for b in bases):
                    rooted_at_project.append((name, lineno, bases))
                else:
                    rooted_at_stdlib.append((name, lineno, bases))
            else:
                rooted_at_stdlib.append((name, lineno, bases))
        if len(rooted_at_stdlib) < 2:
            continue
        # At least two sibling roots. Emit one finding per class whose
        # sibling is not caught together by any call site.
        # Build set of classes actually used in except clauses anywhere in the tree.
        caught_elsewhere: dict[str, set[str]] = defaultdict(set)
        for src in _all_py_files(src_root):
            try:
                other_tree = ast.parse(src.read_text(encoding='utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for sub in ast.walk(other_tree):
                if not isinstance(sub, ast.ExceptHandler):
                    continue
                if sub.type is None:
                    continue
                try:
                    type_src = ast.unparse(sub.type)
                except Exception:
                    continue
                for caught in re.findall(r'[a-zA-Z_.][a-zA-Z0-9_.]*', type_src):
                    tail = caught.split('.')[-1]
                    caught_elsewhere[tail].add(_relpath(src, scope))
        # Find the two classes most likely to belong together: if a class C
        # is caught at site S and a sibling D in the same file is never
        # caught together at S, D leaks.
        sibling_names = {name for name, _, _ in rooted_at_stdlib}
        if len(sibling_names) < 2:
            continue
        # Emit one finding per file naming all co-defined siblings.
        first_name, first_line, _ = rooted_at_stdlib[0]
        accept = _accept_reason(lines, first_line, rule='sibling-errors-no-common-base')
        _emit(
            rule='sibling-errors-no-common-base',
            variant=f'{len(sibling_names)} Error classes co-defined with no shared parent: {sorted(sibling_names)}',
            path=rel,
            line=first_line,
            evidence=f'classes: {", ".join(sorted(sibling_names))}',
            accepted=bool(accept),
            accepted_reason=accept,
        )


def check_duplicate_side_effect_per_target(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag when two or more methods on the same class call the same
    sink function with an argument pointing to the same attribute target.

    Signal:
      - Class C defines methods M1, M2 (M1 != M2, both non-private,
        both non-dunder, neither named like a pure setter).
      - M1 and M2 each call F(<args>) where F is a module-level function
        in the project.
      - At least one argument to F is `self.<attr>` and is identical
        across the call sites.

    Example: `Pipeline.tokenize` and `Pipeline.train` both call
    `feathf.config.persistence.flush_resolved_config(..., self.run_dir)`.
    Calling from multiple stages silently re-flushes the same target and
    can overwrite a patched snapshot if stages write different config
    versions.
    """
    MUTATING_METHOD_NAMES = {
        'set', 'reset', 'clear', 'update', 'mutate', 'merge', 'replace',
        'apply', 'patch', 'override', 'flush', 'write', 'persist', 'save',
        'emit', 'dump',
    }
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            # For each method, collect calls of the shape f(..., self.<attr>, ...)
            # keyed by (callee_dotted, frozenset(self.<attr> args))
            calls_per_key: dict[tuple[str, tuple[str, ...]], list[tuple[str, int]]] = defaultdict(list)
            for member in cls.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                mname = member.name
                if mname.startswith('_'):
                    continue
                lname = mname.lower()
                if any(lname.startswith(p + '_') or lname == p for p in MUTATING_METHOD_NAMES):
                    continue
                for inner in ast.walk(member):
                    if not isinstance(inner, ast.Call):
                        continue
                    try:
                        callee = ast.unparse(inner.func)
                    except Exception:
                        continue
                    # collect self.<attr> args
                    self_args: list[str] = []
                    for a in inner.args:
                        try:
                            src = ast.unparse(a)
                        except Exception:
                            continue
                        if src.startswith('self.'):
                            self_args.append(src)
                    for kw in inner.keywords:
                        if kw.arg is None:
                            continue
                        try:
                            src = ast.unparse(kw.value)
                        except Exception:
                            continue
                        if src.startswith('self.'):
                            self_args.append(src)
                    if not self_args:
                        continue
                    key = (callee, tuple(sorted(self_args)))
                    calls_per_key[key].append((mname, inner.lineno))
            for (callee, self_args), sites in calls_per_key.items():
                method_names = {m for (m, _) in sites}
                if len(method_names) < 2:
                    continue
                # Deduplicate the sink function itself; only emit when callee
                # looks like a sink (write/flush/persist/save/emit/log/dump)
                # or when the arg set suggests a shared target
                callee_tail = callee.rsplit('.', 1)[-1].lower()
                looks_like_sink = any(
                    tok in callee_tail
                    for tok in ('flush', 'write', 'save', 'persist', 'emit', 'dump', 'log', 'publish', 'upload', 'register')
                )
                target_is_path_or_dir = any('dir' in a.lower() or 'path' in a.lower() or 'file' in a.lower() for a in self_args)
                if not (looks_like_sink or target_is_path_or_dir):
                    continue
                first_method, first_line = sites[0]
                accept = _accept_reason(lines, first_line, rule='duplicate-side-effect-per-target')
                _emit(
                    rule='duplicate-side-effect-per-target',
                    variant=f'{cls.name}.{{{", ".join(sorted(method_names))}}} all call {callee}({", ".join(self_args)})',
                    path=rel,
                    line=first_line,
                    evidence=f'{cls.name}: methods {sorted(method_names)} share sink {callee}',
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


def check_cli_entry_missing_error_envelope(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag CLI entry-point functions (top-level functions in `cli/*.py`
    whose name starts with `run_`) that have no top-level try/except.

    The rule: if at least one sibling CLI entry in the project does have
    a top-level try/except catching a project error class, flag every
    CLI entry that does not. CLI entries are the error envelope for
    user-facing errors; an unenveloped entry will surface untranslated
    third-party exceptions.
    """
    cli_dir = src_root / 'cli'
    if not cli_dir.is_dir():
        return
    # First pass: enumerate all CLI run_* entries and whether they wrap
    # something in a top-level try/except.
    entries: list[tuple[str, int, str, bool]] = []  # (path, lineno, fname, has_outer_try)
    for path in sorted(cli_dir.rglob('*.py')):
        if path.name == '__init__.py':
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith('run_'):
                continue
            # Only consider true CLI dispatch entries. Heuristics to
            # exclude helper functions in cli/*.py:
            #   - return annotation is `int` (CLI commands return an
            #     exit code)
            #   - OR has a parameter annotated with a name ending in
            #     `.Feathf` / `.Cmd` / any cappa dispatcher root (the
            #     dispatcher-aware second argument)
            returns_int = False
            if node.returns is not None:
                try:
                    ret_src = ast.unparse(node.returns)
                    if ret_src.strip() == 'int':
                        returns_int = True
                except Exception:
                    pass
            # params whose annotation string contains a capitalised cappa
            # command class (the `parent: 'feathf.cli.app.Feathf'` style)
            has_cappa_param = False
            for arg in node.args.args:
                if arg.annotation is None:
                    continue
                try:
                    ann_src = ast.unparse(arg.annotation)
                except Exception:
                    continue
                if re.search(r"\.[A-Z]\w+['\"]?$", ann_src.strip("'\"")):
                    has_cappa_param = True
                    break
            if not (returns_int or has_cappa_param):
                continue
            # Is there any Try in the function body? (Any depth.) The
            # rule is: CLI entry must have at least one try/except
            # somewhere to be considered "enveloped".
            has_try = any(isinstance(sub, ast.Try) for sub in ast.walk(node))
            entries.append((rel, node.lineno, node.name, has_try))
    if not entries:
        return
    # If at least one entry has a try/except, any entry without one is flagged.
    any_has_try = any(has_try for (_, _, _, has_try) in entries)
    if not any_has_try:
        return
    for rel, lineno, fname, has_try in entries:
        if has_try:
            continue
        full = scope / rel
        lines = _source_lines(full)
        accept = _accept_reason(lines, lineno, rule='cli-entry-missing-error-envelope')
        _emit(
            rule='cli-entry-missing-error-envelope',
            variant=f'{fname} has no top-level try/except',
            path=rel,
            line=lineno,
            evidence=f'def {fname}(...): (no try/except; siblings do wrap)',
            accepted=bool(accept),
            accepted_reason=accept,
        )


def check_redundant_sink_caller_plus_callee(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions that call a sink S directly, and then call a helper
    G which itself also calls S with IDENTICAL argument signatures.

    Example: `run_evaluate` calls `flush_resolved_config(config, run_dir)`
    at line L1, then calls `pipeline.tokenize(splits)` which itself
    calls `flush_resolved_config(config, run_dir)`. The argument
    signatures match, so the outer call is redundant.

    Tight signal to avoid the O(n^2) false positives on large pipelines
    (where one orchestrator calls five helpers that each log metrics -
    those are NOT redundant, they log different arguments):
      - Function F calls sink S(args1) at line L1.
      - Function F calls helper G at line L2 where L2 > L1.
      - G is a module-level function in this project whose body also
        calls S(args2).
      - args1 and args2 have the same **normalised argument tails**:
        for each positional arg, the trailing name (`config`, `run_dir`)
        matches; for each keyword arg, the keyword matches.
      - S's short name contains a sink token (`flush`, `write`, `save`,
        `persist`, `emit`, `dump`, `log`, `publish`, `upload`,
        `register`).
    """
    package_root_name = src_root.name
    SINK_TOKENS = ('flush', 'write', 'save', 'persist', 'emit', 'dump',
                   'log', 'publish', 'upload', 'register')

    def _arg_signature(call: ast.Call) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Normalise a call's arguments into (positional_tails, kwargs).

        Normalisation keeps role tokens that survive renames: `patched_config`
        and `self.config` both normalise to `config`. The last underscore-
        separated token is the "role"; common prefixes (`patched_`, `new_`,
        `effective_`, `resolved_`) drop out, so `patched_config` == `config`.
        """
        positional: list[str] = []
        for a in call.args:
            try:
                src = ast.unparse(a)
            except Exception:
                continue
            tail = src
            if tail.startswith('self.'):
                tail = tail[5:]
            # If attribute access, take the last segment
            tail = tail.rsplit('.', 1)[-1]
            # If still contains underscores (e.g. `patched_config`,
            # `new_run_dir`, `resolved_config`), keep a suffix that
            # preserves the last two underscore-segments for `run_dir`
            # style names, otherwise just the last segment.
            parts = tail.split('_')
            if len(parts) >= 2:
                # keep the last two segments if they look like `run_dir`,
                # otherwise just the last one
                last_two = '_'.join(parts[-2:])
                if last_two in {'run_dir', 'run_id', 'trial_id', 'split_id', 'split_name'}:
                    tail = last_two
                else:
                    tail = parts[-1]
            positional.append(tail)
        kwargs: list[str] = []
        for kw in call.keywords:
            if kw.arg is not None:
                kwargs.append(kw.arg)
        return tuple(positional), tuple(sorted(kwargs))

    # First pass: index every project function's sink calls with their signatures.
    function_sinks: dict[str, dict[str, list[tuple[tuple[str, ...], tuple[str, ...]]]]] = defaultdict(lambda: defaultdict(list))
    # function_sinks[func_key][sink_callee] = list of (positional_tails, kwarg_keys)
    for path in _all_py_files(src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel_parts = path.relative_to(src_root).parts
        if rel_parts[-1] == '__init__.py':
            continue
        mod = package_root_name + '.' + '.'.join(rel_parts)[:-3]
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            key = f'{mod}.{node.name}'
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                try:
                    callee = ast.unparse(inner.func)
                except Exception:
                    continue
                callee_tail = callee.rsplit('.', 1)[-1].lower()
                tail_parts = set(re.split(r'[_\W]+', callee_tail))
                if not any(tok in tail_parts for tok in SINK_TOKENS):
                    continue
                function_sinks[key][callee].append(_arg_signature(inner))
    if not function_sinks:
        return

    # Build lookup: short_name -> set of full keys
    short_to_full: dict[str, set[str]] = defaultdict(set)
    for key in function_sinks:
        short = key.rsplit('.', 1)[-1]
        short_to_full[short].add(key)

    # Second pass: walk each function. For each direct sink call, look for
    # a later helper call whose target (any full key matching its short name)
    # makes the SAME sink call with the SAME signature.
    for path in _all_py_files(src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            direct_sinks: list[tuple[int, str, tuple[tuple[str, ...], tuple[str, ...]]]] = []
            helper_calls: list[tuple[int, str]] = []
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                try:
                    callee = ast.unparse(inner.func)
                except Exception:
                    continue
                tail = callee.rsplit('.', 1)[-1].lower()
                tail_parts = set(re.split(r'[_\W]+', tail))
                if any(tok in tail_parts for tok in SINK_TOKENS):
                    direct_sinks.append((inner.lineno, callee, _arg_signature(inner)))
                else:
                    short = callee.rsplit('.', 1)[-1]
                    if short in short_to_full:
                        helper_calls.append((inner.lineno, callee))
            if not direct_sinks or not helper_calls:
                continue
            reported: set[tuple[int, str]] = set()
            for sink_line, sink_callee, sink_sig in direct_sinks:
                sink_tail = sink_callee.rsplit('.', 1)[-1]
                dedup_key = (sink_line, sink_callee)
                if dedup_key in reported:
                    continue
                found_redundant = False
                for helper_line, helper_callee in helper_calls:
                    if helper_line <= sink_line:
                        continue  # only forward-direction redundancy
                    short = helper_callee.rsplit('.', 1)[-1]
                    for full in short_to_full.get(short, set()):
                        for inner_callee, sigs in function_sinks.get(full, {}).items():
                            if inner_callee.rsplit('.', 1)[-1] != sink_tail:
                                continue
                            if sink_sig not in sigs:
                                continue
                            accept = _accept_reason(lines, sink_line, rule='redundant-sink-caller-plus-callee')
                            _emit(
                                rule='redundant-sink-caller-plus-callee',
                                variant=f'{node.name} calls {sink_callee}(...) then {helper_callee} which re-calls {inner_callee} with the same args',
                                path=rel,
                                line=sink_line,
                                evidence=(f'direct {sink_callee}{sink_sig[0]} at line {sink_line}; '
                                          f'helper {helper_callee} at line {helper_line} -> {full}'),
                                accepted=bool(accept),
                                accepted_reason=accept,
                            )
                            reported.add(dedup_key)
                            found_redundant = True
                            break
                        if found_redundant:
                            break
                    if found_redundant:
                        break


def check_return_value_shadows_instance_attr(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag class methods that return a value named identically to an
    instance attribute (either alone or as part of a tuple). The
    contract "caller must reassign self.X" is implicit and unenforced.

    Signal:
      - Class C stores `self.X` in `__init__` from a same-named arg.
      - A method M on C (other than __init__/__post_init__) returns
        either `X` directly or a tuple that contains a local `patched_X`
        / `new_X` / `X` (i.e. a Name whose id is `X` or contains `X`).
      - The method's docstring or body mutates the local value away
        from `self.X`.

    This is the `Pipeline.tokenize` pattern: returns `(tokenized,
    patched_config)` where `patched_config` is a divergent copy of
    `self.config`; callers must `self.config = patched_config` or the
    instance silently drifts.
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            owned_attrs: set[str] = set()
            init = next(
                (m for m in cls.body
                 if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and m.name == '__init__'),
                None,
            )
            if init is None:
                continue
            arg_names = {a.arg for a in init.args.args}
            for inner in ast.walk(init):
                if not isinstance(inner, ast.Assign):
                    continue
                for tgt in inner.targets:
                    if (isinstance(tgt, ast.Attribute)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == 'self'
                            and isinstance(inner.value, ast.Name)
                            and inner.value.id == tgt.attr
                            and inner.value.id in arg_names):
                        owned_attrs.add(tgt.attr)
            if not owned_attrs:
                continue
            for member in cls.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if member.name in {'__init__', '__post_init__'}:
                    continue
                # Look for Return nodes inside the method body
                for ret in ast.walk(member):
                    if not isinstance(ret, ast.Return):
                        continue
                    returned_names: list[str] = []
                    if isinstance(ret.value, ast.Name):
                        returned_names.append(ret.value.id)
                    elif isinstance(ret.value, ast.Tuple):
                        for elt in ret.value.elts:
                            if isinstance(elt, ast.Name):
                                returned_names.append(elt.id)
                    for rname in returned_names:
                        for attr in owned_attrs:
                            # exact match OR contains attr name (e.g. `patched_config`)
                            if rname == attr or (f'_{attr}' in rname) or (f'{attr}_' in rname):
                                # also require that the method body assigns a local
                                # derived from self.<attr> to that name (to avoid FPs
                                # where the method just happens to have a local named X)
                                has_derivation = False
                                for inner in ast.walk(member):
                                    if (isinstance(inner, ast.Assign)
                                            and any(isinstance(t, ast.Name) and t.id == rname
                                                    for t in inner.targets)):
                                        src = ast.unparse(inner.value) if hasattr(ast, 'unparse') else ''
                                        if f'self.{attr}' in src:
                                            has_derivation = True
                                            break
                                if not has_derivation:
                                    continue
                                accept = _accept_reason(lines, ret.lineno, rule='return-shadows-instance-attr')
                                _emit(
                                    rule='return-shadows-instance-attr',
                                    variant=f'{cls.name}.{member.name} returns `{rname}` which shadows self.{attr}; callers must reassign',
                                    path=rel,
                                    line=ret.lineno,
                                    evidence=(lines[ret.lineno - 1].strip()[:200]
                                              if ret.lineno <= len(lines) else ''),
                                    accepted=bool(accept),
                                    accepted_reason=accept,
                                )
                                break


def check_try_wrapping_with_too_broad(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `try: with X(): body...` patterns where the except handler
    re-invokes work that was inside the `with` body, assuming the
    exception came from `__enter__`.

    Signal:
      - An `ast.Try` node whose body starts with an `ast.With` block.
      - The `with` body contains one or more call statements.
      - The `except` handler body itself contains at least one call
        whose callee name matches a callee inside the `with` body.
      - The handler's intent (per comments/log messages) is startup
        failure - but the catch will also fire for any exception raised
        inside the `with` body.

    The `run_batch` double-run: `try: with open_batch_run(): run_pipeline_and_finalise(...)`
    catches `RegistryError`, and the handler calls `run_pipeline_and_finalise(...)`
    again. If `RegistryError` escapes from the `with` body (not startup),
    the pipeline runs twice.
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            if not node.body:
                continue
            # First statement is a `with`
            first = node.body[0]
            if not isinstance(first, ast.With):
                continue
            # Collect call names in the with-body
            with_body_callees: set[str] = set()
            for stmt in first.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Call):
                        try:
                            callee = ast.unparse(sub.func)
                        except Exception:
                            continue
                        short = callee.rsplit('.', 1)[-1]
                        with_body_callees.add(short)
            if not with_body_callees:
                continue
            # Collect call names in each handler's body
            for handler in node.handlers:
                handler_callees: set[str] = set()
                for stmt in handler.body:
                    for sub in ast.walk(stmt):
                        if isinstance(sub, ast.Call):
                            try:
                                callee = ast.unparse(sub.func)
                            except Exception:
                                continue
                            short = callee.rsplit('.', 1)[-1]
                            handler_callees.add(short)
                # Overlap of non-trivial callees
                overlap = {
                    c for c in with_body_callees & handler_callees
                    # Skip logger/print/etc. noise
                    if c not in {'warning', 'info', 'error', 'exception',
                                 'debug', 'print', 'format', 'str', 'repr',
                                 'len'}
                    # Skip class / exception constructors (CamelCase) -
                    # they are error construction, not "work".
                    and not (c[:1].isupper() if c else True)
                }
                if not overlap:
                    continue
                accept = _accept_reason(lines, handler.lineno, rule='try-wrapping-with-block-too-broad')
                _emit(
                    rule='try-wrapping-with-block-too-broad',
                    variant=f'except handler re-invokes {sorted(overlap)!r} from the wrapped `with` body',
                    path=rel,
                    line=handler.lineno,
                    evidence=(lines[handler.lineno - 1].strip()[:200]
                              if handler.lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


def check_duplicate_call_sequence(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag two functions (across different classes or modules) that
    share a long subsequence of call-name tokens in the same order.

    Signal:
      - For every FunctionDef / AsyncFunctionDef, extract the ordered
        sequence of callee short-names from calls with >=1 argument and
        whose callee is dotted (skips stdlib / builtin 1-word calls).
      - Skip very short sequences (< 5 calls) to avoid false positives.
      - Normalise: drop sequential duplicates (so `logger.info` stutter
        does not dominate the signature).
      - Group functions by the longest-common-subsequence key, which
        is the ordered tuple of distinct callee short-names appearing
        in each function.
      - If two functions share a LCS-key of length >= 5, emit.
    """
    # Build per-function signature
    signatures: list[tuple[str, int, str, tuple[str, ...]]] = []
    for path in _all_py_files(src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = _relpath(path, scope)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            seq: list[str] = []
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                try:
                    callee = ast.unparse(inner.func)
                except Exception:
                    continue
                # Require a dotted callee (skip bare len(), str(), dict() etc.)
                if '.' not in callee:
                    continue
                short = callee.rsplit('.', 1)[-1]
                if short in {'warning', 'info', 'error', 'exception',
                             'debug', 'format', 'get', 'set', 'append',
                             'extend', 'update', 'pop', 'items', 'keys',
                             'values', 'join', 'split', 'strip', 'lower',
                             'upper', 'replace', 'startswith', 'endswith',
                             'replace', 'items', 'dumps', 'loads', 'copy',
                             'deepcopy', 'write_text', 'read_text',
                             'mkdir', 'exists', 'is_file', 'is_dir',
                             'as_posix', 'resolve'}:
                    continue
                if seq and seq[-1] == short:
                    continue
                seq.append(short)
            # Keep the sequence as an ordered tuple; require >= 5 distinct calls
            if len(seq) < 5:
                continue
            fname = node.name
            signatures.append((rel, node.lineno, fname, tuple(seq)))

    if len(signatures) < 2:
        return

    # Compute longest common subsequences pairwise; report pairs that share
    # a subsequence of length >= 5. Quadratic in function count - bounded
    # to architecturally-significant functions (we already filtered to >=5).
    def _lcs(a: tuple[str, ...], b: tuple[str, ...]) -> list[str]:
        n, m = len(a), len(b)
        if n == 0 or m == 0:
            return []
        # use rolling arrays
        prev = [0] * (m + 1)
        curr = [0] * (m + 1)
        back: list[list[int]] = [[0] * (m + 1) for _ in range(n + 1)]
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                if a[i - 1] == b[j - 1]:
                    curr[j] = prev[j - 1] + 1
                    back[i][j] = 1
                elif prev[j] >= curr[j - 1]:
                    curr[j] = prev[j]
                    back[i][j] = 2
                else:
                    curr[j] = curr[j - 1]
                    back[i][j] = 3
            prev, curr = curr, prev
        # Reconstruct
        i, j = n, m
        out: list[str] = []
        while i > 0 and j > 0:
            d = back[i][j]
            if d == 1:
                out.append(a[i - 1])
                i -= 1
                j -= 1
            elif d == 2:
                i -= 1
            else:
                j -= 1
        out.reverse()
        return out

    # Count how many distinct functions each call-name appears in
    call_fanout: dict[str, int] = defaultdict(int)
    for (_, _, _, seq) in signatures:
        for c in set(seq):
            call_fanout[c] += 1
    # Calls that appear in >30% of all functions are too generic to count
    n_funcs = max(len(signatures), 1)
    generic_threshold = max(5, n_funcs // 3)
    generic_calls = {c for c, n in call_fanout.items() if n > generic_threshold}

    reported: set[tuple[str, str]] = set()
    for i, (rel_a, line_a, fname_a, seq_a) in enumerate(signatures):
        for (rel_b, line_b, fname_b, seq_b) in signatures[i + 1:]:
            if (rel_a, fname_a) == (rel_b, fname_b):
                continue
            # Skip intra-file pairs: within-file duplication is usually a
            # legitimate family of similar shaped functions (e.g. chart
            # generators). Cross-file duplication is the architectural smell.
            if rel_a == rel_b:
                continue
            # Skip if top-level packages match AND both are leaf functions
            # in the same kind of module (e.g. both in `*/metrics.py`).
            pkg_a = rel_a.split('/', 2)[:2]
            pkg_b = rel_b.split('/', 2)[:2]
            # Only interesting if LCS is long enough
            lcs = _lcs(seq_a, seq_b)
            if len(lcs) < 6:
                continue
            # Drop generic calls that appear in many functions; the LCS
            # must still be long enough after the drop.
            meaningful_lcs = [c for c in lcs if c not in generic_calls]
            if len(meaningful_lcs) < 5:
                continue
            # Require the LCS to cover MOST of BOTH sequences. A shared
            # sub-skeleton of 6+ calls that each function also decorates
            # with 4-5 unique calls is not duplication, it's a family.
            # True duplication means each function is ~70%+ the same.
            if len(lcs) / max(len(seq_a), 1) < 0.7:
                continue
            if len(lcs) / max(len(seq_b), 1) < 0.7:
                continue
            key_a = (rel_a, fname_a)
            key_b = (rel_b, fname_b)
            pair_key = tuple(sorted([f'{k[0]}:{k[1]}' for k in (key_a, key_b)]))
            if pair_key in reported:
                continue
            reported.add(pair_key)
            full_a = scope / rel_a
            accept = _accept_reason(_source_lines(full_a), line_a, rule='duplicate-call-sequence')
            _emit(
                rule='duplicate-call-sequence',
                variant=f'{fname_a} shares {len(lcs)} calls in order with {rel_b}:{fname_b}',
                path=rel_a,
                line=line_a,
                evidence=f'shared sequence: {" -> ".join(meaningful_lcs or lcs)} (peer at {rel_b}:{line_b}:{fname_b})',
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_layer_has_domain_error_but_raises_stdlib(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag modules that raise stdlib exceptions (ValueError, RuntimeError,
    TypeError, KeyError) for domain errors when a sibling `errors.py` in
    the same package defines a domain-error class.

    Signal:
      - Package P contains an `errors.py` defining at least one `*Error`
        class.
      - Another module M in the same package P raises a stdlib exception
        (ValueError, RuntimeError, TypeError, KeyError) at module-level
        or function scope.
      - The stdlib raise is NOT inside an `except` block (which is the
        re-raise-with-narrower-type pattern and is fine).

    Scope rationale (review-73): the "widen to any module that imports a
    domain `*Error` lazily" variant was tried and discarded because it
    over-fired on `config/structures.py.__post_init__` validation raises,
    which AGENTS.md's "Error type policy by layer" permits (`config` has
    no own `*Error` class and only lazily imports `PipelineError` for a
    narrow cross-stage violation). The narrower same-package predicate is
    the stable form.
    """
    STDLIB_EXCS = {'ValueError', 'RuntimeError', 'KeyError'}
    # First pass: find every package with a domain error class
    package_has_domain_error: set[tuple[str, ...]] = set()
    for path in _all_py_files(src_root):
        if path.name != 'errors.py':
            continue
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.endswith('Error'):
                pkg = path.relative_to(src_root).parts[:-1]
                package_has_domain_error.add(pkg)
                break

    if not package_has_domain_error:
        return

    # Second pass: walk every module raising stdlib errors
    for path in _all_py_files(src_root):
        if path.name in {'errors.py', '__init__.py'}:
            continue
        pkg = path.relative_to(src_root).parts[:-1]
        if pkg not in package_has_domain_error:
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        # Track which Raise nodes are inside an except block
        except_bodies: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                for child in ast.walk(node):
                    if hasattr(child, 'lineno'):
                        except_bodies.add(child.lineno)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise):
                continue
            if node.lineno in except_bodies:
                continue
            exc_call = node.exc
            exc_name = None
            if isinstance(exc_call, ast.Call):
                if isinstance(exc_call.func, ast.Name):
                    exc_name = exc_call.func.id
            elif isinstance(exc_call, ast.Name):
                exc_name = exc_call.id
            if exc_name not in STDLIB_EXCS:
                continue
            accept = _accept_reason(lines, node.lineno, rule='layer-has-domain-error-raises-stdlib')
            _emit(
                rule='layer-has-domain-error-raises-stdlib',
                variant=f'{pkg[-1] if pkg else "(root)"} package defines *Error classes but this module raises {exc_name}',
                path=rel,
                line=node.lineno,
                evidence=(lines[node.lineno - 1].strip()[:200]
                          if node.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_inconsistent_error_translation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag helper functions F that raise a domain error E, where two or
    more distinct callers of F translate E to different project-error
    classes. Divergent translation is a semantic bug: the same
    underlying failure surfaces as different error types to different
    consumers.

    Signal:
      - Function F at path P has at least one `raise <E>(...)` where E
        ends in `Error` (a project domain error).
      - Two or more functions elsewhere call F, each wrapping the call
        in a `try: ... except <E>: raise <T_i>(...)` where the raised
        translation target classes T_i differ across callers.
    """
    package_root_name = src_root.name

    # Pass 1: for each module-level function, enumerate the *Error classes
    # it raises directly (i.e. not via re-raise of a caught exception).
    function_raises: dict[str, set[str]] = defaultdict(set)
    function_path_line: dict[str, tuple[str, int]] = {}
    for path in _all_py_files(src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = _relpath(path, scope)
        rel_parts = path.relative_to(src_root).parts
        if rel_parts[-1] == '__init__.py':
            continue
        mod = package_root_name + '.' + '.'.join(rel_parts)[:-3]
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            key = f'{mod}.{node.name}'
            function_path_line[key] = (rel, node.lineno)
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Raise) or inner.exc is None:
                    continue
                target = inner.exc.func if isinstance(inner.exc, ast.Call) else inner.exc
                if isinstance(target, (ast.Name, ast.Attribute)):
                    try:
                        src = ast.unparse(target)
                    except Exception:
                        continue
                    tail = src.rsplit('.', 1)[-1]
                    if tail.endswith('Error'):
                        function_raises[key].add(tail)

    if not function_raises:
        return

    # Short-name lookup
    short_to_full: dict[str, set[str]] = defaultdict(set)
    for key in function_raises:
        short = key.rsplit('.', 1)[-1]
        short_to_full[short].add(key)

    # Pass 2: for every call site of a function in function_raises, find
    # the enclosing try/except and the translation target if any.
    translations: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    # translations[callee_full][caught_error] = set of translated target classes
    for path in _all_py_files(src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            # find calls inside the try body to known functions
            for body_stmt in node.body:
                for sub in ast.walk(body_stmt):
                    if not isinstance(sub, ast.Call):
                        continue
                    try:
                        callee = ast.unparse(sub.func)
                    except Exception:
                        continue
                    short = callee.rsplit('.', 1)[-1]
                    for full in short_to_full.get(short, set()):
                        caught_classes: set[str] = set()
                        for h in node.handlers:
                            if h.type is None:
                                continue
                            try:
                                type_src = ast.unparse(h.type)
                            except Exception:
                                continue
                            for caught in re.findall(r'[A-Za-z_][A-Za-z_0-9]*', type_src):
                                if caught.endswith('Error'):
                                    caught_classes.add(caught)
                        # For each caught class that the callee actually raises,
                        # record the translation target(s)
                        for caught in caught_classes:
                            if caught not in function_raises.get(full, set()):
                                continue
                            for h in node.handlers:
                                if h.type is None:
                                    continue
                                try:
                                    h_src = ast.unparse(h.type)
                                except Exception:
                                    continue
                                if caught not in h_src:
                                    continue
                                for handler_stmt in h.body:
                                    for raisesub in ast.walk(handler_stmt):
                                        if not isinstance(raisesub, ast.Raise):
                                            continue
                                        if raisesub.exc is None:
                                            continue
                                        tgt = raisesub.exc.func if isinstance(raisesub.exc, ast.Call) else raisesub.exc
                                        if not isinstance(tgt, (ast.Name, ast.Attribute)):
                                            continue
                                        try:
                                            tgt_src = ast.unparse(tgt)
                                        except Exception:
                                            continue
                                        tgt_tail = tgt_src.rsplit('.', 1)[-1]
                                        if tgt_tail.endswith('Error'):
                                            translations[full][caught].add(tgt_tail)

    # Pass 3: emit findings for callees whose domain error is translated
    # to 2+ distinct targets across the codebase.
    for callee_full, err_map in translations.items():
        for caught, targets in err_map.items():
            if len(targets) < 2:
                continue
            if callee_full not in function_path_line:
                continue
            rel, lineno = function_path_line[callee_full]
            full_path = scope / rel
            lines = _source_lines(full_path)
            accept = _accept_reason(lines, lineno, rule='inconsistent-error-translation')
            _emit(
                rule='inconsistent-error-translation',
                variant=f'{callee_full} raises {caught}; callers translate to {sorted(targets)}',
                path=rel,
                line=lineno,
                evidence=f'{caught} -> {sorted(targets)}',
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_parameter_mutation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions that mutate a parameter's dict/list items while
    the function name or docstring suggests pure validation / checking.

    Signal:
      - Function F has parameter P (typed as dict/list or named like
        `merged`, `config`, `data`, `params`).
      - F's name starts with `check_`, `validate_`, `is_`, `has_`,
        `get_`, `compute_`, `resolve_`, `parse_`.
      - F's body contains `P[key] = value` or `P.update(...)` or
        `P.pop(...)` or `P.append(...)` or similar mutation on P.
    """
    # `compute_` is intentionally omitted - HF Trainer's `compute_loss` and
    # similar methods routinely mutate their `inputs` dict. The pure-naming
    # contract does not hold for overridden framework methods.
    PURE_PREFIXES = ('check_', 'validate_', 'is_', 'has_', 'get_',
                     'resolve_', 'parse_', 'find_', 'count_')
    MUTATION_METHODS = {'update', 'pop', 'append', 'extend', 'insert',
                        'remove', 'clear', 'setdefault', 'popitem'}
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(node.name.startswith(p) for p in PURE_PREFIXES):
                continue
            param_names = {a.arg for a in node.args.args}
            if not param_names:
                continue
            # Walk body for mutation of a parameter
            for inner in ast.walk(node):
                # item assignment: param[k] = v
                if isinstance(inner, ast.Assign):
                    for tgt in inner.targets:
                        if isinstance(tgt, ast.Subscript) and isinstance(tgt.value, ast.Name):
                            if tgt.value.id in param_names:
                                accept = _accept_reason(lines, inner.lineno, rule='parameter-mutation-in-pure-function')
                                _emit(
                                    rule='parameter-mutation-in-pure-function',
                                    variant=f'{node.name} mutates parameter `{tgt.value.id}` via item assignment',
                                    path=rel,
                                    line=inner.lineno,
                                    evidence=(lines[inner.lineno - 1].strip()[:200]
                                              if inner.lineno <= len(lines) else ''),
                                    accepted=bool(accept),
                                    accepted_reason=accept,
                                )
                # augmented assignment: param[k] += v
                if isinstance(inner, ast.AugAssign):
                    if (isinstance(inner.target, ast.Subscript)
                            and isinstance(inner.target.value, ast.Name)
                            and inner.target.value.id in param_names):
                        accept = _accept_reason(lines, inner.lineno, rule='parameter-mutation-in-pure-function')
                        _emit(
                            rule='parameter-mutation-in-pure-function',
                            variant=f'{node.name} mutates parameter `{inner.target.value.id}` via augmented assignment',
                            path=rel,
                            line=inner.lineno,
                            evidence=(lines[inner.lineno - 1].strip()[:200]
                                      if inner.lineno <= len(lines) else ''),
                            accepted=bool(accept),
                            accepted_reason=accept,
                        )
                # method call: param.update(...), param.append(...)
                if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute):
                    if (isinstance(inner.func.value, ast.Name)
                            and inner.func.value.id in param_names
                            and inner.func.attr in MUTATION_METHODS):
                        accept = _accept_reason(lines, inner.lineno, rule='parameter-mutation-in-pure-function')
                        _emit(
                            rule='parameter-mutation-in-pure-function',
                            variant=f'{node.name} mutates parameter `{inner.func.value.id}` via `.{inner.func.attr}()`',
                            path=rel,
                            line=inner.lineno,
                            evidence=(lines[inner.lineno - 1].strip()[:200]
                                      if inner.lineno <= len(lines) else ''),
                            accepted=bool(accept),
                            accepted_reason=accept,
                        )


_SIDE_EFFECT_CALL_NAMES = {
    'mkdir', 'rmdir', 'unlink', 'rmtree', 'makedirs', 'remove',
    'write_text', 'write_bytes', 'touch', 'copytree',
    'symlink_to', 'mkstemp', 'mkdtemp',
}


def check_pure_name_has_side_effect(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions whose name suggests a pure query/resolution but
    whose body calls a disk-write/IO side-effect function.

    Signal:
      - Function name starts with `resolve_`, `find_`, `get_`, `compute_`,
        `check_`, `parse_`, `is_`, `has_`, `validate_`, `count_`, `build_`.
      - Function body contains a call whose callee short-name is in
        {mkdir, rmdir, unlink, rmtree, makedirs, remove, write_text,
         write_bytes, touch, copy, copytree, move, rename, replace,
         symlink_to, mkstemp, mkdtemp, dump, dumps, save}.
      - The side-effect call is not inside a nested `def` (otherwise
        we'd flag factory functions that return a closure).
    """
    # `compute_` / `build_` are covered by check_build_name_has_side_effect
    # which documents allowed exceptions per-call-site rather than banning
    # the prefix outright. `load_` is deliberately omitted: load_* functions
    # legitimately perform IO.
    PURE_PREFIXES = ('resolve_', 'find_', 'get_', 'check_',
                     'parse_', 'is_', 'has_', 'validate_', 'count_',
                     'allocate_')
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(node.name.startswith(p) for p in PURE_PREFIXES):
                continue
            # Walk only the direct body (and its nested statements) but not
            # nested function definitions
            def walk_non_nested(n):
                for sub in ast.iter_child_nodes(n):
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                        continue
                    yield sub
                    yield from walk_non_nested(sub)
            for sub in walk_non_nested(node):
                if not isinstance(sub, ast.Call):
                    continue
                callee_short = None
                if isinstance(sub.func, ast.Name):
                    callee_short = sub.func.id
                elif isinstance(sub.func, ast.Attribute):
                    callee_short = sub.func.attr
                if callee_short not in _SIDE_EFFECT_CALL_NAMES:
                    continue
                accept = _accept_reason(lines, sub.lineno, rule='pure-name-has-side-effect')
                _emit(
                    rule='pure-name-has-side-effect',
                    variant=f'{node.name} calls side-effect `{callee_short}` despite name implying a pure query',
                    path=rel,
                    line=sub.lineno,
                    evidence=(lines[sub.lineno - 1].strip()[:200]
                              if sub.lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
                break  # one finding per function is enough


def check_mutable_store_without_copy(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `__init__` methods that store a parameter typed as dict/list
    onto `self.<name>` without taking a defensive copy. Callers share
    the reference with the instance; if anyone mutates later, all
    observers see the change.

    Signal:
      - `__init__` has a parameter P whose annotation mentions `dict`
        or `list` (at the top level; allows `dict | None`, `list[str]`,
        `dict[str, Any]` forms).
      - The body assigns `self.<P> = <P>` with no `.copy()` /
        `.deepcopy()` / `dict(...)` / `list(...)` / `frozenset(...)`
        wrapping.
      - The parameter is not annotated as `frozenset`, `tuple`, or a
        project dataclass (which is immutable by convention).
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            init = next(
                (m for m in cls.body
                 if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and m.name == '__init__'),
                None,
            )
            if init is None:
                continue
            # Collect args typed as dict/list at top level of annotation
            mutable_args: set[str] = set()
            for arg in init.args.args:
                if arg.annotation is None:
                    continue
                try:
                    ann_src = ast.unparse(arg.annotation)
                except Exception:
                    continue
                # top-level `dict` or `list` (allow `| None`, subscripts)
                # but not inside tuple/frozenset/etc.
                normalised = ann_src.split('|')[0].strip()
                root = re.match(r'^([a-zA-Z_][a-zA-Z_0-9]*)', normalised)
                if not root:
                    continue
                root_name = root.group(1)
                if root_name in {'dict', 'list'}:
                    mutable_args.add(arg.arg)
            if not mutable_args:
                continue
            # Walk init body for self.X = X where X in mutable_args and
            # the RHS is a bare Name (no .copy() wrapping)
            for stmt in init.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                for tgt in stmt.targets:
                    if not (isinstance(tgt, ast.Attribute)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == 'self'):
                        continue
                    if not isinstance(stmt.value, ast.Name):
                        continue
                    if stmt.value.id not in mutable_args:
                        continue
                    if tgt.attr != stmt.value.id:
                        continue
                    accept = _accept_reason(lines, stmt.lineno, rule='mutable-store-without-copy')
                    _emit(
                        rule='mutable-store-without-copy',
                        variant=f'{cls.name}.__init__ stores dict/list parameter `{stmt.value.id}` by reference',
                        path=rel,
                        line=stmt.lineno,
                        evidence=(lines[stmt.lineno - 1].strip()[:200]
                                  if stmt.lineno <= len(lines) else ''),
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )


# Callees that indicate the wrapped try-block touches local filesystem
# cache / does writing I/O. Catching only library-specific exceptions
# (MlflowException, BotoException, etc.) without also catching OSError
# leaks disk failures to callers.
_FILESYSTEM_TOUCHING_CALLS = {
    # Third-party helpers that cache to disk / upload / download
    'download_artifacts', 'download_file', 'download', 'save_model',
    'log_artifact', 'log_artifacts', 'log_model', 'from_pretrained',
    'save_pretrained', 'push_to_hub', 'snapshot_download',
    'upload_file', 'upload_artifacts',
    # Pathlib / open / stdlib filesystem primitives used directly.
    # `replace`, `rename`, `copy`, `remove` are intentionally omitted -
    # `str.replace`, `dataclasses.replace`, `list.copy`, `dict.copy`,
    # `list.remove` are overwhelmingly common; the false-positive rate
    # on their bare names dominates.
    'write_text', 'write_bytes', 'read_text', 'read_bytes',
    'mkdir', 'unlink', 'rmdir', 'touch', 'rmtree', 'makedirs',
    'symlink_to', 'copytree',
    # Common library read entry points that open the file under the hood
    'read_csv', 'read_json', 'read_parquet', 'read_table',
    'read_excel', 'read_pickle', 'read_feather', 'read_hdf',
    'read_sql', 'read_sql_query', 'read_sql_table',
    'from_csv', 'from_json',
}


def check_filesystem_envelope_gap(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `try` blocks that call a filesystem-touching third-party
    helper (`download_artifacts`, `from_pretrained`, `snapshot_download`,
    etc.) where the `except` tuple does not include `OSError` (or a
    parent like `Exception`/`BaseException`).

    These helpers write to a local cache directory; disk-full,
    read-only, or permission-denied failures surface as `OSError` /
    `PermissionError`, not as the library's own exception. The narrow
    except clause lets those propagate past the wrapper's promise to
    translate to a project error class.
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            # Does the body call any filesystem-touching helper?
            touched_fs = False
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if not isinstance(sub, ast.Call):
                        continue
                    short = None
                    if isinstance(sub.func, ast.Name):
                        short = sub.func.id
                    elif isinstance(sub.func, ast.Attribute):
                        short = sub.func.attr
                    if short in _FILESYSTEM_TOUCHING_CALLS:
                        touched_fs = True
                        break
                if touched_fs:
                    break
            if not touched_fs:
                continue
            # Does ANY except handler catch OSError/Exception/BaseException?
            covers_os = False
            for handler in node.handlers:
                if handler.type is None:
                    covers_os = True
                    break
                try:
                    type_src = ast.unparse(handler.type)
                except Exception:
                    continue
                names = set(re.findall(r'[A-Za-z_][A-Za-z_0-9]*', type_src))
                if {'OSError', 'Exception', 'BaseException', 'IOError',
                    'PermissionError', 'FileNotFoundError'} & names:
                    covers_os = True
                    break
            if covers_os:
                continue
            # Emit a finding at the first handler's line so the reviewer
            # sees the narrow catch.
            first_handler = node.handlers[0] if node.handlers else None
            lineno = first_handler.lineno if first_handler is not None else node.lineno
            # List the caught classes for context
            caught = []
            for h in node.handlers:
                if h.type is None:
                    caught.append('<bare>')
                else:
                    try:
                        caught.append(ast.unparse(h.type))
                    except Exception:
                        pass
            accept = _accept_reason(lines, lineno, rule='filesystem-envelope-gap')
            _emit(
                rule='filesystem-envelope-gap',
                variant=f'try block touches filesystem (download/from_pretrained/etc.) but except tuple {caught!r} omits OSError',
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200]
                          if lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_filesystem_op_without_envelope(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag public entry-point functions that perform filesystem writes
    (`write_text` / `write_bytes` / `mkdir` / `unlink` / `rmtree` / etc.)
    WITHOUT a surrounding try/except anywhere in the function body.

    Signal:
      - Function F lives in a package P whose `errors.py` defines at
        least one `*Error` class (so the layer has a domain error to
        translate to).
      - F is a PUBLIC entry point of the package: either exported from
        the package's `__init__.py` (via `__all__` or a `from .X import F`
        re-export), OR its docstring mentions `Raises` (signalling it is
        part of the package's error contract).
      - F calls a filesystem-write primitive
        (`write_text`, `write_bytes`, `mkdir`, `unlink`, `rmdir`,
        `touch`, `rmtree`, `makedirs`, `symlink_to`, `copytree`).
      - The call is not inside any `ast.Try` block within F.

    Internal utilities (functions called only by other functions in the
    same package) are NOT flagged - they legitimately let `OSError`
    propagate to a caller that holds the envelope.

    `filesystem-envelope-gap` catches the case where a try exists but
    the except tuple is too narrow. This check catches the case where
    no try exists at all AND the function is part of the package's
    public error contract.
    """
    # Drop `replace`, `rename`, `copy`, `remove` - too noisy due to
    # str.replace, dataclasses.replace, list.copy, list.remove etc.
    # `read_text` / `read_bytes` / `from_pretrained` added per review-34
    # predicate-extension decision: packages with a domain *Error must
    # envelope read-path IO too, not only writes.
    STDLIB_WRITE_CALLS = {
        'write_text', 'write_bytes', 'mkdir', 'unlink', 'rmdir',
        'touch', 'rmtree', 'makedirs',
        'symlink_to', 'copytree',
        'read_text', 'read_bytes',
        'from_pretrained',
    }
    # First pass: find every package with a domain error class
    package_has_domain_error: set[tuple[str, ...]] = set()
    for path in _all_py_files(src_root):
        if path.name != 'errors.py':
            continue
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.endswith('Error'):
                pkg = path.relative_to(src_root).parts[:-1]
                package_has_domain_error.add(pkg)
                break
    if not package_has_domain_error:
        return

    # For each package with a domain error, collect the names exported
    # from its `__init__.py` (via __all__ or re-exports).
    package_exports: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for path in _all_py_files(src_root):
        if path.name != '__init__.py':
            continue
        pkg = path.relative_to(src_root).parts[:-1]
        if pkg not in package_has_domain_error:
            continue
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id == '__all__':
                        if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    package_exports[pkg].add(elt.value)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    package_exports[pkg].add(alias.asname or alias.name)

    for path in _all_py_files(src_root):
        if path.name in {'errors.py', '__init__.py'}:
            continue
        pkg = path.relative_to(src_root).parts[:-1]
        if pkg not in package_has_domain_error:
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        exports = package_exports.get(pkg, set())
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Public entry-point test: either exported from package
            # __init__ OR docstring mentions "Raises"
            is_exported = func.name in exports
            docstring = ast.get_docstring(func) or ''
            mentions_raises = bool(re.search(r'\bRaises?\b', docstring))
            if not (is_exported or mentions_raises):
                continue
            # Collect linenos inside any try block within this function
            try_linenos: set[int] = set()
            for sub in ast.walk(func):
                if isinstance(sub, ast.Try):
                    for stmt in sub.body:
                        for innersub in ast.walk(stmt):
                            if hasattr(innersub, 'lineno'):
                                try_linenos.add(innersub.lineno)
            # Walk for filesystem write calls
            for inner in ast.walk(func):
                if not isinstance(inner, ast.Call):
                    continue
                short = None
                if isinstance(inner.func, ast.Name):
                    short = inner.func.id
                elif isinstance(inner.func, ast.Attribute):
                    short = inner.func.attr
                if short not in STDLIB_WRITE_CALLS:
                    continue
                if inner.lineno in try_linenos:
                    continue
                accept = _accept_reason(lines, inner.lineno, rule='filesystem-op-without-envelope')
                _emit(
                    rule='filesystem-op-without-envelope',
                    variant=f'{func.name} calls `{short}` with no surrounding try/except in the function body',
                    path=rel,
                    line=inner.lineno,
                    evidence=(lines[inner.lineno - 1].strip()[:200]
                              if inner.lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
                break  # one finding per function


_LITERAL_DISPATCH_TYPE_NAMES = frozenset({'str'})  # extensible via helper below


def check_assert_never_missing(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `if/elif` chains that dispatch on string equality of a single
    variable and either (a) terminate without an `else` or (b) end with a
    plain `else:` body, instead of `else: typing.assert_never(var)`.

    Only chains with >= 3 string-equality tests are considered (a 2-arm
    if/else is legitimately bi-valued). The variable may be typed as
    `Literal[...]` or an enum, but we cannot verify the type mechanically
    across files; the predicate is kept purely structural (count + shape).

    Cure: replace the trailing `else:` (or absent `else`) with
        else:
            typing.assert_never(var)
    which lets the type-checker verify exhaustion.
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            # Walk the chain, collecting tested variable names
            chain_var: str | None = None
            chain_len = 0
            cursor: ast.If | None = node
            terminal_else: list[ast.stmt] | None = None
            consistent = True
            while cursor is not None:
                test = cursor.test
                var_name = _extract_string_eq_var(test)
                if var_name is None:
                    consistent = False
                    break
                if chain_var is None:
                    chain_var = var_name
                elif var_name != chain_var:
                    consistent = False
                    break
                chain_len += 1
                orelse = cursor.orelse
                if not orelse:
                    terminal_else = None
                    cursor = None
                elif len(orelse) == 1 and isinstance(orelse[0], ast.If):
                    cursor = orelse[0]
                else:
                    terminal_else = orelse
                    cursor = None
            if not consistent or chain_var is None or chain_len < 3:
                continue
            # Already uses assert_never? OK.
            if terminal_else is not None:
                has_assert_never = False
                for stmt in terminal_else:
                    for sub in ast.walk(stmt):
                        if isinstance(sub, ast.Call):
                            src = ''
                            try:
                                src = ast.unparse(sub.func)
                            except Exception:
                                pass
                            if 'assert_never' in src:
                                has_assert_never = True
                                break
                    if has_assert_never:
                        break
                if has_assert_never:
                    continue
            accept = _accept_reason(lines, node.lineno, rule='assert-never-missing')
            _emit(
                rule='assert-never-missing',
                variant=(f'if/elif chain on `{chain_var}` with {chain_len} string-equality arms '
                         f'{"has fall-through else" if terminal_else else "has no else"}; '
                         f'should end with `else: typing.assert_never({chain_var})`'),
                path=rel,
                line=node.lineno,
                evidence=(lines[node.lineno - 1].strip()[:200]
                          if node.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


def _extract_string_eq_var(test: ast.expr) -> str | None:
    """Return `name` if `test` is `name == "literal"` or `"literal" == name`,
    otherwise None."""
    if not isinstance(test, ast.Compare):
        return None
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return None
    left = test.left
    right = test.comparators[0]
    if (isinstance(left, ast.Name)
            and isinstance(right, ast.Constant)
            and isinstance(right.value, str)):
        return left.id
    if (isinstance(right, ast.Name)
            and isinstance(left, ast.Constant)
            and isinstance(left.value, str)):
        return right.id
    return None


def check_build_name_has_side_effect(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `build_*` / `compute_*` functions that call subprocess, clock,
    uuid, random, or filesystem-write primitives. `build_*` names imply
    pure assembly from inputs; the listed side-effect calls contradict
    that contract.

    Signal:
      - Function name starts with `build_` or `compute_`.
      - Function body contains a call whose callee short-name is in the
        side-effect set below (extends `_SIDE_EFFECT_CALL_NAMES` with
        `subprocess.run`, `datetime.now`, `uuid.uuid4`, `time.time`).
      - The call is not inside a nested function.

    The separate `check_pure_name_has_side_effect` covers the 9 other
    pure prefixes; `build_`/`compute_` are split out because their
    side-effect enumerations include clock/uuid (not relevant to the
    others) and because reporting's `build_*_data` family has a large
    number of accepted-via-comment sites that would dominate the output
    if bundled.
    """
    BUILD_SIDE_EFFECTS = _SIDE_EFFECT_CALL_NAMES | {
        'run',       # subprocess.run
        'check_output', 'check_call', 'Popen',
        'now', 'utcnow',  # datetime.now / datetime.utcnow
        'time', 'monotonic', 'perf_counter',
        'uuid1', 'uuid3', 'uuid4', 'uuid5',
        'random', 'randint', 'choice', 'shuffle',
    }
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not (node.name.startswith('build_') or node.name.startswith('compute_')):
                continue
            def walk_non_nested(n):
                for sub in ast.iter_child_nodes(n):
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                        continue
                    yield sub
                    yield from walk_non_nested(sub)
            for sub in walk_non_nested(node):
                if not isinstance(sub, ast.Call):
                    continue
                callee_short = None
                if isinstance(sub.func, ast.Name):
                    callee_short = sub.func.id
                elif isinstance(sub.func, ast.Attribute):
                    callee_short = sub.func.attr
                if callee_short not in BUILD_SIDE_EFFECTS:
                    continue
                accept = _accept_reason(lines, sub.lineno, rule='build-name-has-side-effect')
                _emit(
                    rule='build-name-has-side-effect',
                    variant=f'{node.name} calls side-effect `{callee_short}` despite `build_`/`compute_` name',
                    path=rel,
                    line=sub.lineno,
                    evidence=(lines[sub.lineno - 1].strip()[:200]
                              if sub.lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
                break


def check_mutable_module_level_exported(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag module-level mutable containers that are imported by name from
    another module in the same corpus. Externally-imported globals should
    be immutable so callers cannot mutate shared state.

    Signal:
      - Module-level `NAME = {...}` / `NAME = [...]` / `NAME = set(...)`
        where the RHS is NOT wrapped in `types.MappingProxyType`,
        `frozenset`, or `tuple`.
      - `NAME` appears in some other file's `from <this-module> import NAME`.

    Locked enumeration (per SKILL.md A20):
      dict literal -> must be `types.MappingProxyType(...)`.
      set literal  -> must be `frozenset(...)`.
      list literal -> must be `tuple(...)`.

    Private (non-imported) mutable globals are NOT flagged - that is a
    different rule.
    """
    # First pass: for every module, collect top-level Assign/AnnAssign
    # targets whose RHS is a bare dict/list/set literal, plus the module
    # dotted-import path.
    candidates: list[tuple[pathlib.Path, ast.stmt, str]] = []
    module_name_of: dict[pathlib.Path, str] = {}
    for path in _all_py_files(src_root):
        # Canonical module path (from src root, dotted)
        parts = path.relative_to(src_root).with_suffix('').parts
        if parts and parts[-1] == '__init__':
            parts = parts[:-1]
        module_dotted = '.'.join((src_root.name,) + parts)
        module_name_of[path] = module_dotted
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in tree.body:
            value = None
            name = None
            if isinstance(node, ast.Assign):
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    name = node.targets[0].id
                    value = node.value
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.value is not None:
                    name = node.target.id
                    value = node.value
            if name is None or value is None:
                continue
            if not isinstance(value, (ast.Dict, ast.List, ast.Set)):
                continue
            if name.startswith('_'):
                continue
            candidates.append((path, node, name))

    if not candidates:
        return

    # Second pass: for each candidate, check whether ANY other file uses
    # that name, either via `from <module> import NAME` or via attribute
    # access of the form `<module>.NAME`. The project coding standard
    # uses full-dotted attribute access instead of `from X import Y`, so
    # we must catch both forms.
    imports_of: dict[tuple[str, str], list[tuple[pathlib.Path, int]]] = defaultdict(list)
    for path in _all_py_files(src_root):
        try:
            src_text = path.read_text(encoding='utf-8')
            tree = ast.parse(src_text)
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                for alias in node.names:
                    imports_of[(node.module, alias.name)].append((path, node.lineno))
            elif isinstance(node, ast.Attribute):
                # Build dotted prefix for nested attribute chains:
                # `feathf.evaluation.primary.METRICS_BY_HEAD` -> module
                # `feathf.evaluation.primary`, name `METRICS_BY_HEAD`.
                parts = []
                cur: ast.AST = node
                while isinstance(cur, ast.Attribute):
                    parts.append(cur.attr)
                    cur = cur.value
                if not isinstance(cur, ast.Name):
                    continue
                parts.append(cur.id)
                parts.reverse()
                if len(parts) < 2:
                    continue
                module = '.'.join(parts[:-1])
                name = parts[-1]
                imports_of[(module, name)].append((path, node.lineno))

    for path, assign_node, name in candidates:
        module = module_name_of[path]
        importers = imports_of.get((module, name), [])
        # Only flag if imported from a DIFFERENT file
        external_importers = [(p, ln) for p, ln in importers if p != path]
        if not external_importers:
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        accept = _accept_reason(lines, assign_node.lineno, rule='mutable-module-level-exported')
        kind = type(assign_node.value).__name__
        required_wrap = {
            'Dict': 'types.MappingProxyType(...)',
            'Set': 'frozenset(...)',
            'List': 'tuple(...)',
        }.get(kind, '(immutable wrapper)')
        _emit(
            rule='mutable-module-level-exported',
            variant=(f'{name} is a mutable {kind.lower()} literal imported by '
                     f'{len(external_importers)} other file(s); wrap in {required_wrap}'),
            path=rel,
            line=assign_node.lineno,
            evidence=(lines[assign_node.lineno - 1].strip()[:200]
                      if assign_node.lineno <= len(lines) else ''),
            accepted=bool(accept),
            accepted_reason=accept,
        )


_CALLBACK_METHOD_RE = re.compile(r'^on_(step|log|evaluate|train_\w+|batch_\w+|epoch_\w+|predict_\w+|save|init_\w+)$')


def check_callback_hotpath_io(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag HF `Trainer` callback methods whose body contains per-event
    filesystem IO (`Path.open`, bare `open`, `Path.mkdir`, `write_text`,
    `write_bytes`).

    Signal:
      - Method is a member of a class that inherits from any `*Callback`
        / `TrainerCallback` base (matched by bare-name ancestry, since we
        don't resolve imports).
      - Method name matches `on_(step|log|evaluate|train_*|batch_*|epoch_*|predict_*|save|init_*)`.
      - Method body calls `open`, `Path.open`, `.mkdir`, `.write_text`,
        `.write_bytes`.
      - The call is not inside an attribute-cache guard
        (`if self._opened is None: ...`) - we can't verify that
        mechanically, so the check is coarse: any such call is flagged.

    One-time setup belongs in `__init__`; if the setup cannot move there
    (rare), add `# auditme: accept <reason>`.
    """
    HOT_IO = {'open', 'mkdir', 'write_text', 'write_bytes'}
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            # Heuristic: class inherits from a *Callback base OR file
            # imports TrainerCallback (we just check the class bases).
            base_names = []
            for b in cls.bases:
                try:
                    base_names.append(ast.unparse(b))
                except Exception:
                    pass
            base_str = ' '.join(base_names)
            looks_like_callback = (
                'Callback' in base_str or 'TrainerCallback' in base_str
            )
            # Also accept if any method in the class matches the callback pattern
            has_callback_method = any(
                isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                and _CALLBACK_METHOD_RE.match(m.name)
                for m in cls.body
            )
            if not (looks_like_callback or has_callback_method):
                continue
            for method in cls.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not _CALLBACK_METHOD_RE.match(method.name):
                    continue
                for sub in ast.walk(method):
                    if not isinstance(sub, ast.Call):
                        continue
                    short = None
                    if isinstance(sub.func, ast.Name):
                        short = sub.func.id
                    elif isinstance(sub.func, ast.Attribute):
                        short = sub.func.attr
                    if short not in HOT_IO:
                        continue
                    accept = _accept_reason(lines, sub.lineno, rule='callback-hotpath-io')
                    _emit(
                        rule='callback-hotpath-io',
                        variant=f'{cls.name}.{method.name} performs per-event `{short}`; move setup to __init__',
                        path=rel,
                        line=sub.lineno,
                        evidence=(lines[sub.lineno - 1].strip()[:200]
                                  if sub.lineno <= len(lines) else ''),
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )
                    break


def check_recompile_duplication(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag module-level constants assigned from `re.compile(...)` when
    the same CONSTANT NAME is also assigned from `re.compile(...)` in
    another file.

    Name collision across files is the real risk - the two copies read
    as if they express the same predicate, so any change to one silently
    drifts from the other. Comparing regex literals byte-wise would miss
    functionally-equivalent variants (e.g., `r'^foo$'` vs `r'^(foo)$'`),
    so the predicate is scoped to name duplication.

    Signal:
      - Module-level `Assign`/`AnnAssign` whose RHS is
        `re.compile(<literal>)`.
      - Same LHS name appears in >= 2 distinct files.
    """
    # name -> list of (path, lineno, literal)
    sites: dict[str, list[tuple[pathlib.Path, int, str]]] = defaultdict(list)
    for path in _all_py_files(src_root):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            target_name: str | None = None
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    target_name = node.targets[0].id
                    value = node.value
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    target_name = node.target.id
                    value = node.value
            if target_name is None or value is None:
                continue
            if not isinstance(value, ast.Call):
                continue
            is_re_compile = False
            if isinstance(value.func, ast.Attribute) and value.func.attr == 'compile':
                if isinstance(value.func.value, ast.Name) and value.func.value.id == 're':
                    is_re_compile = True
            if not is_re_compile:
                continue
            if not value.args:
                continue
            arg0 = value.args[0]
            if not (isinstance(arg0, ast.Constant) and isinstance(arg0.value, str)):
                continue
            sites[target_name].append((path, node.lineno, arg0.value))

    for name, locations in sites.items():
        distinct_paths = {p for p, _, _ in locations}
        if len(distinct_paths) < 2:
            continue
        for path, lineno, literal in locations:
            rel = _relpath(path, scope)
            lines = _source_lines(path)
            accept = _accept_reason(lines, lineno, rule='recompile-duplication')
            other_paths = sorted({_relpath(p, scope) for p, _, _ in locations if p != path})
            _emit(
                rule='recompile-duplication',
                variant=(f'constant `{name} = re.compile(...)` also defined in '
                         f'{other_paths!r}; canonicalise to one home'),
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200]
                          if lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_logger_exception_graceful_degradation(
    scope: pathlib.Path, src_root: pathlib.Path,
) -> None:
    """Flag `except` handlers that call `logger.exception(...)` and then
    `return <constant>` without raising. `logger.exception` is reserved
    for unexpected failures; a handler that logs-then-returns-default is
    a graceful-degradation path and should use `logger.warning` /
    `logger.debug` instead, so log severity matches the handling
    intent.

    Signal:
      - An `ast.ExceptHandler` whose body contains a `logger.exception(...)`
        call AND contains no `ast.Raise`.
      - EITHER the handler body ends with `return <Constant>` OR the
        enclosing function body ends with `return <Constant>` (so the
        handler falls through to the graceful-degradation default).
      - The enclosing function's return annotation is NOT `int`. CLI entry
        points return `int` exit codes and `logger.exception + return 2`
        is the canonical CLI error-contract, not graceful degradation.
    """
    # Build a map of lineno -> enclosing FunctionDef return annotation.
    def _enclosing_return_annotation(tree: ast.AST, lineno: int) -> str | None:
        best: tuple[int, str | None] | None = None
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            start = node.lineno
            end = getattr(node, 'end_lineno', None) or start
            if not (start <= lineno <= end):
                continue
            ann = None
            if node.returns is not None:
                try:
                    ann = ast.unparse(node.returns)
                except Exception:
                    ann = None
            if best is None or start > best[0]:
                best = (start, ann)
        return best[1] if best else None

    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            has_logger_exception = False
            has_raise = False
            handler_last_return: ast.Return | None = None
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Call):
                        src = ''
                        try:
                            src = ast.unparse(sub.func)
                        except Exception:
                            pass
                        if src.endswith('logger.exception') or src.endswith('.exception'):
                            if 'logger' in src or 'loguru' in src:
                                has_logger_exception = True
                    if isinstance(sub, ast.Raise):
                        has_raise = True
                if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant):
                    handler_last_return = stmt
            if not has_logger_exception:
                continue
            if has_raise:
                continue
            # The graceful-degradation default lives either at the end of
            # the handler body (`return <Constant>`) or at the end of the
            # enclosing function body (handler falls through).
            fallthrough_return: ast.Return | None = None
            if handler_last_return is None:
                for fn in ast.walk(tree):
                    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    start = fn.lineno
                    end = getattr(fn, 'end_lineno', None) or start
                    if not (start <= node.lineno <= end):
                        continue
                    last_stmt = fn.body[-1] if fn.body else None
                    if (isinstance(last_stmt, ast.Return)
                            and isinstance(last_stmt.value, ast.Constant)):
                        fallthrough_return = last_stmt
                    break
            default_return = handler_last_return or fallthrough_return
            if default_return is None:
                continue
            lineno = default_return.lineno
            # Exclude CLI entry points (return `int` exit code)
            ret_ann = _enclosing_return_annotation(tree, lineno)
            if ret_ann is not None and ret_ann.strip() == 'int':
                continue
            accept = _accept_reason(lines, lineno, rule='logger-exception-graceful-degradation')
            _emit(
                rule='logger-exception-graceful-degradation',
                variant=('except handler calls logger.exception then returns a '
                         'constant default; use logger.warning or logger.debug instead'),
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200]
                          if lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_non_alphabetical_dict_keys(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag module-level dict assignments whose keys are all string
    literals and NOT in alphabetical order. Companion to
    `check_nonalphabetical_literals` which covers list/tuple/set/frozenset.

    The project-wide ordering rule treats enum-like collections as a
    shared convention: a dict mapping a closed domain (metric-name to
    scorer, error-code to message, etc.) should be alphabetised unless
    the order carries semantic meaning.
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if not isinstance(value, ast.Dict):
                continue
            keys = value.keys
            if not keys or len(keys) < 2:
                continue
            if not all(isinstance(k, ast.Constant) and isinstance(k.value, str) for k in keys):
                continue
            actual = [k.value for k in keys]
            if actual == sorted(actual):
                continue
            accept = _accept_reason(lines, node.lineno, rule='non-alphabetical-dict-keys')
            _emit(
                rule='non-alphabetical-dict-keys',
                variant='dict with string keys not alphabetically sorted',
                path=rel,
                line=node.lineno,
                evidence=f'keys: {actual!r}',
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_bare_parametric_annotation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag annotations that use `dict`, `list`, `tuple`, `set`, or
    `frozenset` without a parametric type (`dict[str, int]`, `list[X]`,
    etc.). Bare `dict` / `list` loses type information that pyright /
    mypy / readers need.

    Applies to:
      - function parameter annotations
      - function return annotations
      - class / module-level AnnAssign targets
      - local AnnAssign targets inside function bodies
    """
    BARE_GENERICS = {'dict', 'list', 'tuple', 'set', 'frozenset'}
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        reported: set[int] = set()

        def _flag_annotation(ann: ast.AST, ctx: str) -> None:
            # Walk the annotation expression to find any `Name` matching
            # a bare generic. `Subscript(Name(id='dict'), ...)` is fine.
            # `Name(id='dict')` alone is a bare annotation. Handle
            # `dict | None`, `dict | Other`, etc. by descending into BinOp.
            def _visit(node: ast.AST) -> None:
                if isinstance(node, ast.Subscript):
                    # parametric; if slice is `dict` itself that's fine too, stop
                    return
                if isinstance(node, ast.Name) and node.id in BARE_GENERICS:
                    lineno = getattr(node, 'lineno', None)
                    if lineno is None or lineno in reported:
                        return
                    reported.add(lineno)
                    accept = _accept_reason(lines, lineno, rule='bare-parametric-annotation')
                    _emit(
                        rule='bare-parametric-annotation',
                        variant=f'{ctx} uses bare `{node.id}` without element type',
                        path=rel,
                        line=lineno,
                        evidence=(lines[lineno - 1].strip()[:200]
                                  if 1 <= lineno <= len(lines) else ''),
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )
                elif isinstance(node, ast.BinOp):
                    _visit(node.left)
                    _visit(node.right)
                elif isinstance(node, ast.Tuple):
                    for elt in node.elts:
                        _visit(elt)
            _visit(ann)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in (*node.args.args, *node.args.kwonlyargs, *node.args.posonlyargs):
                    if arg.annotation is not None:
                        _flag_annotation(arg.annotation, f'{node.name}({arg.arg}:)')
                if node.returns is not None:
                    _flag_annotation(node.returns, f'{node.name} -> ')
            elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
                tgt = node.target
                ctx = 'annotation'
                if isinstance(tgt, ast.Name):
                    ctx = f'{tgt.id}:'
                _flag_annotation(node.annotation, ctx)


def check_docstring_raises_mismatch(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions whose docstring declares `Raises: <X>` (or a
    sphinx-style `:raises X:` or a plain 'Raises X' sentence) where the
    body actually raises a different exception class.

    Signal:
      - Function has a docstring.
      - Docstring mentions at least one exception class name (via
        `Raises:` section, `:raises X:` role, or 'Raises FooError' prose).
      - Function body contains `raise <Y>(...)` statements, all of which
        raise a class NOT listed in the docstring, and no `raise` re-raises
        a caught variable.
    """
    # Match exception class names from docstrings in a few common shapes
    docstring_class_re = re.compile(
        r'(?:Raises[\s:]+|:raises\s+|^\s*Raises?\s+)'
        r'([A-Za-z_][\w.]*Error)', re.MULTILINE
    )
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = ast.get_docstring(node)
            if not doc:
                continue
            declared = {m.rsplit('.', 1)[-1] for m in docstring_class_re.findall(doc)}
            if not declared:
                continue
            # Collect actual raised classes (excluding re-raises of bound vars)
            actual: set[str] = set()
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Raise) or inner.exc is None:
                    continue
                target = inner.exc.func if isinstance(inner.exc, ast.Call) else inner.exc
                if isinstance(target, (ast.Name, ast.Attribute)):
                    try:
                        src = ast.unparse(target)
                    except Exception:
                        continue
                    tail = src.rsplit('.', 1)[-1]
                    if tail.endswith('Error'):
                        actual.add(tail)
            if not actual:
                continue
            if actual & declared:
                continue  # intersection non-empty => at least one documented match
            # Every actual raise is not in declared list => mismatch
            accept = _accept_reason(lines, node.lineno, rule='docstring-raises-mismatch')
            _emit(
                rule='docstring-raises-mismatch',
                variant=f'{node.name} docstring declares `Raises: {sorted(declared)}` but body raises {sorted(actual)}',
                path=rel,
                line=node.lineno,
                evidence=f'docstring: {sorted(declared)} | body: {sorted(actual)}',
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_reexport_in_non_init(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag module-level assignments `X = <dotted.path>.X` in files OTHER
    than `__init__.py`. Re-exports belong in the package's `__init__.py`;
    mid-tree re-export shims fragment the public surface and create
    migration-shim-style consumer drift.
    """
    for path in _all_py_files(src_root):
        if path.name == '__init__.py':
            continue
        rel = _relpath(path, scope)
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        lines = _source_lines(path)
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            # pattern: LHS is a single Name; RHS is Attribute whose
            # trailing .attr matches the LHS name
            if len(node.targets) != 1:
                continue
            tgt = node.targets[0]
            if not isinstance(tgt, ast.Name):
                continue
            if not isinstance(node.value, ast.Attribute):
                continue
            if node.value.attr != tgt.id:
                continue
            # The RHS must be a module path (Attribute of Attribute or Name)
            try:
                rhs_src = ast.unparse(node.value)
            except Exception:
                continue
            accept = _accept_reason(lines, node.lineno, rule='reexport-in-non-init')
            _emit(
                rule='reexport-in-non-init',
                variant=f'`{tgt.id} = {rhs_src}` at module scope in non-__init__.py file',
                path=rel,
                line=node.lineno,
                evidence=(lines[node.lineno - 1].strip()[:200]
                          if node.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_dataclass_optional_always_set(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag dataclass fields annotated as `X | None` (defaulting to
    `None`) where `__post_init__` unconditionally reassigns them to
    a non-None value. The `| None` is inaccurate - the field is never
    None after construction.

    Signal:
      - Class decorated with `@dataclass` or inheriting from a dataclass
        convention.
      - AnnAssign field `X: Y | None = <default>` (or `= field(default=None)`).
      - `__post_init__` method assigns `self.X = <expr>` unconditionally
        (not inside an `if`/`try`/`for`).
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            # Is it a dataclass? Check decorators
            is_dataclass = False
            for dec in cls.decorator_list:
                try:
                    dec_src = ast.unparse(dec)
                except Exception:
                    continue
                if 'dataclass' in dec_src:
                    is_dataclass = True
                    break
            if not is_dataclass:
                continue
            # Collect X | None fields defaulting to None
            nullable_fields: dict[str, int] = {}
            for item in cls.body:
                if not isinstance(item, ast.AnnAssign):
                    continue
                if not isinstance(item.target, ast.Name):
                    continue
                try:
                    ann_src = ast.unparse(item.annotation)
                except Exception:
                    continue
                if 'None' not in ann_src:
                    continue
                # Check default is None (direct or `field(default=None)`)
                default_is_none = False
                if item.value is None:
                    continue
                if isinstance(item.value, ast.Constant) and item.value.value is None:
                    default_is_none = True
                elif isinstance(item.value, ast.Call):
                    for kw in item.value.keywords:
                        if kw.arg == 'default' and isinstance(kw.value, ast.Constant) and kw.value.value is None:
                            default_is_none = True
                if default_is_none:
                    nullable_fields[item.target.id] = item.lineno
            if not nullable_fields:
                continue
            # Find __post_init__
            post_init = next(
                (m for m in cls.body
                 if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and m.name == '__post_init__'),
                None,
            )
            if post_init is None:
                continue
            # Check top-level body of __post_init__ for unconditional
            # `self.<X> = <non-None>` on each nullable field
            for stmt in post_init.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                for tgt in stmt.targets:
                    if not (isinstance(tgt, ast.Attribute)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == 'self'):
                        continue
                    if tgt.attr not in nullable_fields:
                        continue
                    # Check RHS is not None
                    if isinstance(stmt.value, ast.Constant) and stmt.value.value is None:
                        continue
                    field_lineno = nullable_fields[tgt.attr]
                    accept = _accept_reason(lines, field_lineno, rule='dataclass-optional-always-set')
                    _emit(
                        rule='dataclass-optional-always-set',
                        variant=f'{cls.name}.{tgt.attr} typed `X | None` but __post_init__ always assigns non-None',
                        path=rel,
                        line=field_lineno,
                        evidence=(lines[field_lineno - 1].strip()[:200]
                                  if field_lineno <= len(lines) else ''),
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )


def check_dead_local_init(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag function bodies where a local variable is assigned an
    initial value at the top of the body, then unconditionally reassigned
    before any use in all code paths.

    Simple signal (low-FP only):
      - First statement in function body is `x = <literal or empty constructor>`.
      - All subsequent statements in the function body before the first
        read of `x` are reassignments to `x` inside a closed branch
        structure (an `if/elif/else` chain where every branch ends with
        `return <expr involving x>` or with `x = ...`).

    Restricting to "initial empty-constructor assignment + exhaustive
    if/elif/else that returns" keeps the check low-FP.
    """
    EMPTY_CONSTRUCTORS = {'dict', 'list', 'set', 'tuple', 'frozenset'}
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = [s for s in func.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
            if len(body) < 2:
                continue
            first = body[0]
            if not isinstance(first, (ast.Assign, ast.AnnAssign)):
                continue
            targets = first.targets if isinstance(first, ast.Assign) else [first.target]
            if len(targets) != 1 or not isinstance(targets[0], ast.Name):
                continue
            var_name = targets[0].id
            value = first.value
            if value is None:
                continue
            is_empty_init = False
            if isinstance(value, ast.Dict) and not value.keys:
                is_empty_init = True
            elif isinstance(value, ast.List) and not value.elts:
                is_empty_init = True
            elif isinstance(value, ast.Set) and not value.elts:
                is_empty_init = True
            elif isinstance(value, ast.Tuple) and not value.elts:
                is_empty_init = True
            elif (isinstance(value, ast.Call)
                  and isinstance(value.func, ast.Name)
                  and value.func.id in EMPTY_CONSTRUCTORS
                  and not value.args
                  and not value.keywords):
                is_empty_init = True
            if not is_empty_init:
                continue
            # Check remaining body: is it an if/elif/else whose every
            # branch either returns or reassigns var_name before reading it?
            rest = body[1:]
            if len(rest) != 1:
                continue
            if_stmt = rest[0]
            if not isinstance(if_stmt, ast.If):
                continue
            # Walk every branch arm; ensure it starts with an assignment
            # to var_name or a return, not a read.
            def _branch_overrides(branch: list) -> bool:
                for s in branch:
                    # Assigns var_name before reading
                    if isinstance(s, (ast.Assign, ast.AnnAssign)):
                        tgts = s.targets if isinstance(s, ast.Assign) else [s.target]
                        for t in tgts:
                            if isinstance(t, ast.Name) and t.id == var_name:
                                return True
                    # Returns something that uses var_name - don't flag;
                    # this isn't dead init
                    if isinstance(s, ast.Return):
                        if s.value is not None:
                            try:
                                rs = ast.unparse(s.value)
                            except Exception:
                                return False
                            # if body reads var_name in return, branch did not override
                            if re.search(rf'\b{re.escape(var_name)}\b', rs):
                                return False
                            return True  # returned something else, initial was dead
                        return True
                return False
            def _walk_chain(stmt: ast.If) -> bool:
                if not _branch_overrides(stmt.body):
                    return False
                orelse = stmt.orelse
                while orelse:
                    if len(orelse) == 1 and isinstance(orelse[0], ast.If):
                        nxt = orelse[0]
                        if not _branch_overrides(nxt.body):
                            return False
                        orelse = nxt.orelse
                    else:
                        return _branch_overrides(orelse)
                return False  # no else branch => init might be read on that path
            if not _walk_chain(if_stmt):
                continue
            accept = _accept_reason(lines, first.lineno, rule='dead-local-init')
            _emit(
                rule='dead-local-init',
                variant=f'`{var_name} = <empty>` at top of {func.name} is unconditionally overridden in all if/elif/else branches',
                path=rel,
                line=first.lineno,
                evidence=(lines[first.lineno - 1].strip()[:200]
                          if first.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_duplicated_word(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    dup_re = re.compile(r'\b([a-z]{2,})\s+\1\b', re.IGNORECASE)
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        for idx, raw in enumerate(lines, 1):
            m = dup_re.search(raw)
            if not m:
                continue
            word = m.group(1).lower()
            if word in {'that', 'had', 'has', 'as', 'in', 'is'}:
                continue
            s = raw.strip()
            if not (s.startswith('#') or '"""' in raw or "'''" in raw or '"' in raw or "'" in raw):
                continue
            accept = _accept_reason(lines, idx, rule='duplicated-word')
            _emit(
                rule='duplicated-word',
                variant=f'duplicated word {word!r}',
                path=rel,
                line=idx,
                evidence=s[:200],
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_missing_raises_section(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions whose body raises a project exception but whose
    docstring lacks any `Raises:` / `:raises:` section.

    Signal:
      - Function has a non-empty docstring.
      - Function body contains at least one `ast.Raise` whose exception
        class name ends in `Error` and that is NOT a bare `raise` inside
        an except block (pure re-raise) and NOT a re-raise of a caught
        variable (`raise exc_var`).
      - Docstring contains NO `Raises:` block, `:raises X:` role, or
        sentence beginning with `Raises `.
    """
    # Accept any of:
    #   - a `Raises:` / `Raise:` header line (napoleon / google style)
    #   - sphinx `:raises X:` role
    #   - a prose sentence `Raise <X>Error` or `Raises <X>Error` that may
    #     use a dotted-module-qualified form (`featmo.ensemble.errors.LoadError`)
    raises_marker_re = re.compile(
        r'(?:^\s*Raises?\s*:|:raises\s+[A-Za-z_]|\bRaises?\s+[A-Za-z_][\w.]*Error\b)',
        re.MULTILINE,
    )
    STDLIB_ERRORS = {
        'ValueError', 'TypeError', 'RuntimeError', 'KeyError', 'IndexError',
        'AttributeError', 'NotImplementedError', 'OSError', 'FileNotFoundError',
        'PermissionError', 'IsADirectoryError', 'UnicodeDecodeError',
        'UnicodeEncodeError', 'ArithmeticError', 'ZeroDivisionError',
        'StopIteration', 'StopAsyncIteration', 'AssertionError', 'LookupError',
        'MemoryError', 'OverflowError', 'ReferenceError', 'SystemError',
        'BufferError', 'ImportError', 'ModuleNotFoundError', 'NameError',
        'UnboundLocalError', 'IndentationError', 'SyntaxError', 'TabError',
        'EOFError', 'FloatingPointError', 'GeneratorExit', 'KeyboardInterrupt',
        'RecursionError', 'SystemExit', 'TimeoutError', 'ConnectionError',
        'ConnectionAbortedError', 'ConnectionRefusedError', 'ConnectionResetError',
        'BrokenPipeError', 'ChildProcessError', 'BlockingIOError', 'InterruptedError',
        'ProcessLookupError', 'NotADirectoryError', 'FileExistsError',
        'Exception', 'BaseException',
    }
    for path in _all_py_files(src_root):
        if path.name == '__init__.py' or path.name == 'errors.py':
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = ast.get_docstring(node)
            if not doc:
                continue
            if raises_marker_re.search(doc):
                continue
            # Does body raise a project *Error class, not a re-raise or stdlib?
            found_project_raise = False
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Raise):
                    continue
                if inner.exc is None:
                    continue  # bare `raise` re-raise
                target = inner.exc.func if isinstance(inner.exc, ast.Call) else inner.exc
                if isinstance(target, ast.Name):
                    # a re-raise of a caught variable is `raise exc_var` - Name without Call
                    if not isinstance(inner.exc, ast.Call):
                        continue
                    name = target.id
                elif isinstance(target, ast.Attribute):
                    name = target.attr
                else:
                    continue
                if not name.endswith('Error'):
                    continue
                if name in STDLIB_ERRORS:
                    continue  # stdlib raises are covered by the layer-stdlib check
                found_project_raise = True
                break
            if not found_project_raise:
                continue
            accept = _accept_reason(lines, node.lineno, rule='missing-raises-section')
            _emit(
                rule='missing-raises-section',
                variant=f'{node.name} raises a project *Error but docstring lacks a Raises: section',
                path=rel,
                line=node.lineno,
                evidence=(lines[node.lineno - 1].strip()[:200]
                          if node.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


_SUBPROCESS_CALL_RE = re.compile(r'\b(subprocess|sp)\.(run|check_output|check_call|Popen|call)\b')


def check_subprocess_without_memoisation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag functions that invoke `subprocess.run` / `subprocess.check_output`
    / `subprocess.check_call` without a memoisation decorator, when the
    function name suggests a request-invariant query.

    Signal:
      - Function body calls one of `subprocess.run|check_output|check_call|
        Popen|call`.
      - Function has NO `@functools.cache`, `@functools.lru_cache`, `@cache`,
        or `@lru_cache` decorator.
      - Function name starts with a pure-query prefix (`get_`, `resolve_`,
        `compute_`, `find_`, `check_`, `parse_`, `is_`, `has_`, `validate_`,
        `count_`). Other names are assumed per-call intentional.
    """
    PURE_PREFIXES = ('get_', 'resolve_', 'compute_', 'find_', 'check_',
                     'parse_', 'is_', 'has_', 'validate_', 'count_')
    CACHE_DECORATORS = {'cache', 'lru_cache', 'cached', 'functools.cache', 'functools.lru_cache'}
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(node.name.startswith(p) for p in PURE_PREFIXES):
                continue
            # Collect decorator names
            decorators: set[str] = set()
            for dec in node.decorator_list:
                target = dec.func if isinstance(dec, ast.Call) else dec
                try:
                    decorators.add(ast.unparse(target))
                except Exception:
                    pass
            if decorators & CACHE_DECORATORS:
                continue
            # Scan body for subprocess calls
            hit_line = None
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                try:
                    call_src = ast.unparse(inner.func)
                except Exception:
                    continue
                if _SUBPROCESS_CALL_RE.search(call_src):
                    hit_line = inner.lineno
                    break
            if hit_line is None:
                continue
            accept = _accept_reason(lines, hit_line, rule='subprocess-without-memoisation')
            _emit(
                rule='subprocess-without-memoisation',
                variant=f'{node.name} shells out via subprocess without @functools.cache',
                path=rel,
                line=hit_line,
                evidence=(lines[hit_line - 1].strip()[:200]
                          if hit_line <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_bare_except_in_module_with_narrow_errors(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag modules that inconsistently mix `except Exception` / `except
    BaseException` with narrow `except <X>_ERRORS:` tuples in separate
    sites. The mixed pattern signals an incomplete sweep toward narrow
    except tuples.

    Signal:
      - Module has at least one `except Exception` / `except BaseException`
        (bare or with bound name).
      - Module ALSO has at least one `except <NAME>_ERRORS:` or
        `except (*<NAME>_ERRORS, ...):` tuple-handler where NAME_ERRORS
        is referenced as an `ast.Name`.
      - Flag the bare-except sites, not the narrow ones.
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        bare_handlers: list[ast.ExceptHandler] = []
        narrow_errors_tuple_seen = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            t = node.type
            if t is None:
                bare_handlers.append(node)
                continue
            names = []
            if isinstance(t, ast.Tuple):
                for elt in t.elts:
                    if isinstance(elt, ast.Name):
                        names.append(elt.id)
                    elif isinstance(elt, ast.Starred) and isinstance(elt.value, ast.Name):
                        names.append(elt.value.id)
            elif isinstance(t, ast.Name):
                names.append(t.id)
            if any(n.endswith('_ERRORS') or n.endswith('_EXCEPTIONS') for n in names):
                narrow_errors_tuple_seen = True
                continue
            if any(n in {'Exception', 'BaseException'} for n in names):
                bare_handlers.append(node)
        if not (narrow_errors_tuple_seen and bare_handlers):
            continue
        for handler in bare_handlers:
            accept = _accept_reason(lines, handler.lineno, rule='bare-except-in-module-with-narrow-errors')
            _emit(
                rule='bare-except-in-module-with-narrow-errors',
                variant='bare except Exception in module that elsewhere uses *_ERRORS tuple',
                path=rel,
                line=handler.lineno,
                evidence=(lines[handler.lineno - 1].strip()[:200]
                          if handler.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )


_PARAMETRIC_NONBUILTIN_GENERICS = {
    'multiprocessing.Queue',
    'multiprocessing.queues.Queue',
    'queue.Queue',
    'asyncio.Queue',
    'concurrent.futures.Future',
    'concurrent.futures.Executor',
    'collections.deque',
    'collections.OrderedDict',
    'collections.defaultdict',
    'collections.Counter',
    'weakref.WeakKeyDictionary',
    'weakref.WeakValueDictionary',
}


def check_bare_nonbuiltin_generic_annotation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag annotations that reference a parameterisable non-builtin
    class without its type parameter.

    Signal:
      - `ast.AnnAssign.annotation` or a parameter annotation is an
        `ast.Attribute` (e.g. `multiprocessing.Queue`) OR an `ast.Name`
        whose resolved full name is in the parametric-non-builtin set.
      - The annotation is NOT wrapped in `ast.Subscript` (which would
        indicate parametric use like `multiprocessing.Queue[int]`).

    Builtin generics (`dict`/`list`/`tuple`/`set`/`frozenset`) are
    handled by `check_bare_parametric_annotation` and skipped here.
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        # Build import alias map so `Queue` resolves to `multiprocessing.Queue`
        # when imported as `from multiprocessing import Queue`.
        alias_to_full: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    alias_to_full[alias.asname or alias.name] = f'{node.module}.{alias.name}'
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    alias_to_full[alias.asname or alias.name.split('.')[0]] = alias.name

        reported: set[int] = set()

        def _flag(ann: ast.AST) -> None:
            if isinstance(ann, ast.Subscript):
                return  # parametric
            full = None
            if isinstance(ann, ast.Attribute):
                try:
                    full = ast.unparse(ann)
                except Exception:
                    return
            elif isinstance(ann, ast.Name):
                full = alias_to_full.get(ann.id, ann.id)
            if full is None:
                return
            if full not in _PARAMETRIC_NONBUILTIN_GENERICS:
                return
            lineno = getattr(ann, 'lineno', None)
            if lineno is None or lineno in reported:
                return
            reported.add(lineno)
            accept = _accept_reason(lines, lineno, rule='bare-nonbuiltin-generic-annotation')
            _emit(
                rule='bare-nonbuiltin-generic-annotation',
                variant=f'bare `{full}` annotation without type parameter',
                path=rel,
                line=lineno,
                evidence=(lines[lineno - 1].strip()[:200]
                          if 1 <= lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in (*node.args.args, *node.args.kwonlyargs, *node.args.posonlyargs):
                    if arg.annotation is not None:
                        _flag(arg.annotation)
                if node.returns is not None:
                    _flag(node.returns)
            elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
                _flag(node.annotation)


def _collect_name_loads(scope: ast.AST) -> dict[str, list[int]]:
    """Return a map of Name.id -> [lineno, ...] for every Load within
    `scope` (not descending into nested function or class definitions)."""
    result: dict[str, list[int]] = defaultdict(list)

    def walk(n: ast.AST) -> None:
        for sub in ast.iter_child_nodes(n):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                result[sub.id].append(sub.lineno)
            walk(sub)
    walk(scope)
    return result


def _leading_underscore_names(target: ast.AST) -> list[tuple[str, int]]:
    """Return `(name, lineno)` for every `_foo` Store-name inside a
    tuple-unpack target (or a bare `_foo`). Skips bare `_`."""
    out: list[tuple[str, int]] = []

    def walk(n: ast.AST) -> None:
        if isinstance(n, ast.Name):
            if n.id.startswith('_') and n.id != '_' and not n.id.startswith('__'):
                out.append((n.id, n.lineno))
        elif isinstance(n, (ast.Tuple, ast.List)):
            for elt in n.elts:
                walk(elt)
        elif isinstance(n, ast.Starred):
            walk(n.value)
    walk(target)
    return out


def check_underscore_unpack_target_read(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag tuple-unpack assignments with a leading-underscore target
    whose name is subsequently READ in the enclosing scope. A leading
    underscore conventionally marks an unused binding; reading it is
    misleading.

    Signal:
      - `ast.Assign` or `ast.AnnAssign` where the target is a Tuple/List
        containing `Name(id='_foo', ctx=Store)` with a leading underscore
        (not bare `_`, not dunder).
      - `_foo` appears as `ast.Name(ctx=Load)` somewhere later in the
        same function (or module scope if at module level).
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        # Enclosing scopes: module-level plus each function
        scopes: list[ast.AST] = [tree]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.append(node)
        for scope_node in scopes:
            loads = _collect_name_loads(scope_node)
            for node in ast.iter_child_nodes(scope_node) if scope_node is tree else ast.walk(scope_node):
                if scope_node is not tree and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)) and node is not scope_node:
                    continue
                targets: list[ast.AST] = []
                if isinstance(node, ast.Assign):
                    targets = list(node.targets)
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                else:
                    continue
                for target in targets:
                    if not isinstance(target, (ast.Tuple, ast.List)):
                        continue
                    for name, lineno in _leading_underscore_names(target):
                        reads_after = [ln for ln in loads.get(name, []) if ln > lineno]
                        if not reads_after:
                            continue
                        accept = _accept_reason(lines, lineno, rule='underscore-unpack-target-read')
                        _emit(
                            rule='underscore-unpack-target-read',
                            variant=f'`{name}` unpacked but read at line {reads_after[0]}',
                            path=rel,
                            line=lineno,
                            evidence=(lines[lineno - 1].strip()[:200]
                                      if 1 <= lineno <= len(lines) else ''),
                            accepted=bool(accept),
                            accepted_reason=accept,
                        )


def check_underscore_forloop_target_read(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag `for _x in ...:` (or tuple form `for _x, y in ...:`) where
    `_x` is subsequently READ inside the loop body.

    Signal:
      - `ast.For` / `ast.AsyncFor` with a target that contains a leading-
        underscore `Name(ctx=Store)` (not bare `_`, not dunder).
      - The same name appears as `ast.Name(ctx=Load)` within the loop's
        body statements (not nested function defs).
    """
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.For, ast.AsyncFor)):
                continue
            underscore_targets = _leading_underscore_names(node.target)
            if not underscore_targets:
                continue
            # Collect loads inside loop body
            body_loads: set[str] = set()
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                        continue
                    if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                        body_loads.add(sub.id)
            for name, lineno in underscore_targets:
                if name not in body_loads:
                    continue
                accept = _accept_reason(lines, lineno, rule='underscore-forloop-target-read')
                _emit(
                    rule='underscore-forloop-target-read',
                    variant=f'for-loop target `{name}` read inside body',
                    path=rel,
                    line=lineno,
                    evidence=(lines[lineno - 1].strip()[:200]
                              if 1 <= lineno <= len(lines) else ''),
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


# Directories whose modules adapt an external service. AGENTS.md's
# failure-versus-absence rule is written for "a source or resolver"; LLM
# providers are the same shape - an adapter over a remote API - so they are
# included. Scope is deliberately narrow: outside an adapter, a bare
# `return None` from an except handler is often a legitimate cache miss or
# optional lookup, and firing on those would make the check untrustworthy.
EXTERNAL_ADAPTER_DIRS = frozenset({'sources', 'resolvers', 'providers'})

# What counts as "recording a failure the caller can see". Logging does not:
# a log line is not a value the caller can branch on, which is the whole point
# of the rule.
_FAILURE_WORD_RE = re.compile(r'error|failure|failed|cannot_answer', re.IGNORECASE)
_LOGGING_CALL_RE = re.compile(r'^(logger|logging|log)\b|\.(debug|info|warning|error|exception|critical)$')
_STATUS_TEST_RE = re.compile(r'\b(status|status_code|statuscode)\b')


def _walk_within_scope(node: ast.AST) -> Iterable[ast.AST]:
    """Yield descendants of node without entering a nested function or class.

    ast.walk cannot prune, and a `return None` inside a nested helper belongs
    to that helper, not to the handler being examined.
    """
    stack: list[ast.AST] = list(ast.iter_child_nodes(node))
    while stack:
        current = stack.pop()
        yield current
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(current))


def _clean_absence_return(node: ast.Return) -> str | None:
    """Label this return if it signals 'nothing here', else None.

    Covers the tuple form because `resolve_chain` returns `(None, None)`.
    """
    value = node.value
    if value is None:
        return 'bare return'
    if isinstance(value, ast.Constant) and value.value is None:
        return 'return None'
    if isinstance(value, ast.List) and not value.elts:
        return 'return []'
    if isinstance(value, ast.Dict) and not value.keys:
        return 'return {}'
    if isinstance(value, ast.Tuple) and value.elts and all(
        isinstance(e, ast.Constant) and e.value is None for e in value.elts
    ):
        return f'return ({", ".join(["None"] * len(value.elts))})'
    return None


def _records_visible_failure(stmts: list[ast.stmt]) -> bool:
    """True when these statements raise, or set something the caller reads.

    A keyword argument counts (`SearchBatch(..., error=str(e))`) because that
    is the project's documented alternative to raising. A logger call does not,
    however error-shaped its name.
    """
    for stmt in stmts:
        for child in [stmt, *_walk_within_scope(stmt)]:
            if isinstance(child, ast.Raise):
                return True
            if isinstance(child, ast.keyword) and child.arg and _FAILURE_WORD_RE.search(child.arg):
                return True
            if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                if any(_FAILURE_WORD_RE.search(ast.unparse(t)) for t in targets if t is not None):
                    return True
            if isinstance(child, ast.Call):
                func_src = ast.unparse(child.func)
                if _LOGGING_CALL_RE.search(func_src):
                    continue
                if _FAILURE_WORD_RE.search(func_src):
                    return True
    return False


def _status_failure_branch(node: ast.If) -> list[ast.stmt] | None:
    """Return whichever branch of an HTTP-status test runs on a non-200."""
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return None
    if not _STATUS_TEST_RE.search(ast.unparse(test)):
        return None
    op = test.ops[0]
    if isinstance(op, (ast.NotEq, ast.GtE, ast.Gt, ast.NotIn)):
        return node.body
    if isinstance(op, (ast.Eq, ast.In)):
        return node.orelse or None
    return None


def check_failure_as_absence(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a clean-absence return reached from a caught exception or a non-200.

    AGENTS.md ("Failure versus absence") requires that a source or resolver
    never return None/[] for a non-200 response or a caught exception without
    also recording a failure the caller can see - by raising, or by setting an
    error field the caller reads. Returning empty is reserved for a genuine
    "the request completed and there was nothing to find". Conflating the two
    makes a network outage read as "this paper has no match", which is silently
    wrong rather than loudly wrong.

    Two shapes are detected:
      A. An `except` handler whose body reaches a clean-absence return with no
         raise and no error-recording statement.
      B. The non-200 branch of an HTTP status test doing the same.

    Deliberately NOT detected - documented non-goals, not oversights:
      - The loop-continue shape, where a per-item handler `continue`s and the
        function later returns a collection that happens to be empty. Catching
        it needs flow analysis and would fire on legitimate partial-result
        paths, where returning what did parse is correct.
      - Count guards such as `if failed == attempted: raise`, where the defect
        is the arithmetic and the return is innocent.
    Both remain Phase B's job. This check owns the direct shapes, where a
    verdict needs no judgement.
    """
    for path in _all_py_files(src_root):
        parts = set(path.parts)
        if 'tests' in parts or not (parts & EXTERNAL_ADAPTER_DIRS):
            continue
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                variant, body = 'caught exception returns empty', node.body
            elif isinstance(node, ast.If):
                body = _status_failure_branch(node)
                if body is None:
                    continue
                variant = 'non-200 branch returns empty'
            else:
                continue
            if _records_visible_failure(body):
                continue
            for child in [*body, *(c for stmt in body for c in _walk_within_scope(stmt))]:
                if not isinstance(child, ast.Return):
                    continue
                label = _clean_absence_return(child)
                if label is None:
                    continue
                accept = _accept_reason(lines, child.lineno, rule='failure-as-absence') or _accept_reason(lines, node.lineno, rule='failure-as-absence')
                _emit(
                    rule='failure-as-absence',
                    variant=f'{variant} ({label})',
                    path=rel,
                    line=child.lineno,
                    evidence=lines[child.lineno - 1].strip()[:200] if child.lineno <= len(lines) else label,
                    accepted=bool(accept),
                    accepted_reason=accept,
                )


_PHASE_REF_RE = re.compile(r'\bPhase\s+[1-9][a-z]?\b')
_SECTION_REF_RE = re.compile(r'\bSection\s+[0-9]+\.[0-9]+\b')


def check_phase_section_doc_reference(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag src/ docstrings and comments that reference numbered
    `Phase N` or `Section X.Y` spec locations. These cross-references
    rot when specs are renumbered.

    Signal:
      - Line in a .py file in src/ matches `\\bPhase [1-9][a-z]?\\b` or
        `\\bSection [0-9]+\\.[0-9]+\\b`.
      - Line is part of a docstring (triple-quoted string) OR a comment
        (starts with `#` after optional whitespace).
      - The file does NOT carry a file-level `# auditme: accept <reason>`
        marker on any comment-only line (to allow modules that render
        user-facing Phase vocabulary to be excused wholesale).
      - Hit is not explicitly accepted via inline marker.
    """
    file_level_accept_re = re.compile(
        r'^\s*#\s*auditme:\s*accept\s+.*phase-section'
    )
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        # File-level accept check: if any line is a comment-only
        # `# auditme: accept phase-section ...`, skip the file.
        if any(file_level_accept_re.search(raw) for raw in lines):
            continue
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        # Collect docstring line ranges
        docstring_ranges: list[tuple[int, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                doc = ast.get_docstring(node, clean=False)
                if doc and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                    const = node.body[0]
                    end = getattr(const, 'end_lineno', const.lineno)
                    docstring_ranges.append((const.lineno, end))
        def in_docstring(ln: int) -> bool:
            return any(a <= ln <= b for a, b in docstring_ranges)

        for idx, raw in enumerate(lines, 1):
            matches = list(_PHASE_REF_RE.finditer(raw)) + list(_SECTION_REF_RE.finditer(raw))
            if not matches:
                continue
            stripped = raw.strip()
            is_comment = stripped.startswith('#')
            if not (is_comment or in_docstring(idx)):
                continue
            accept = _accept_reason(lines, idx, rule='phase-section-doc-reference')
            _emit(
                rule='phase-section-doc-reference',
                variant=f'numeric spec cross-reference {matches[0].group(0)!r}',
                path=rel,
                line=idx,
                evidence=stripped[:200],
                accepted=bool(accept),
                accepted_reason=accept,
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('scope', type=pathlib.Path, help='Project root (containing src/, agents/, ...)')
    parser.add_argument('--package', help='Source package under src/ (default: first dir)', default=None)
    args = parser.parse_args()

    scope = args.scope.resolve()
    if not (scope / 'src').exists():
        print(f'ERROR: {scope}/src does not exist', file=sys.stderr)
        return 2

    if args.package:
        src_root = scope / 'src' / args.package
    else:
        children = sorted(p for p in (scope / 'src').iterdir() if p.is_dir())
        if not children:
            print(f'ERROR: no package under {scope}/src', file=sys.stderr)
            return 2
        src_root = children[0]

    if not src_root.exists():
        print(f'ERROR: {src_root} not found', file=sys.stderr)
        return 2

    for check in (
        check_ruff,
        check_text_patterns,
        check_percent_formatting,
        check_def_class_in_init,
        check_in_function_imports,
        check_silent_broad_except,
        check_broad_except_wrong_level,
        check_except_interpolation,
        check_literal_duplication,
        check_nonalphabetical_literals,
        check_unused_submodule_imports,
        check_paired_sibling_helpers,
        check_layering_violations,
        check_constructor_disk_io,
        check_passthrough_shim,
        check_empty_init_with_exporting_siblings,
        check_mixed_raise_types,
        check_migration_shim_consumers,
        check_silent_self_mutation,
        check_asymmetric_exception_translation,
        check_sibling_error_no_common_base,
        check_duplicate_side_effect_per_target,
        check_cli_entry_missing_error_envelope,
        check_redundant_sink_caller_plus_callee,
        check_return_value_shadows_instance_attr,
        check_try_wrapping_with_too_broad,
        check_duplicate_call_sequence,
        check_layer_has_domain_error_but_raises_stdlib,
        check_inconsistent_error_translation,
        check_parameter_mutation,
        check_pure_name_has_side_effect,
        check_mutable_store_without_copy,
        check_filesystem_envelope_gap,
        check_filesystem_op_without_envelope,
        check_assert_never_missing,
        check_build_name_has_side_effect,
        check_mutable_module_level_exported,
        check_callback_hotpath_io,
        check_recompile_duplication,
        check_logger_exception_graceful_degradation,
        check_non_alphabetical_dict_keys,
        check_bare_parametric_annotation,
        check_docstring_raises_mismatch,
        check_reexport_in_non_init,
        check_dataclass_optional_always_set,
        check_dead_local_init,
        check_lockfile,
        check_duplicated_word,
        check_missing_raises_section,
        check_subprocess_without_memoisation,
        check_bare_except_in_module_with_narrow_errors,
        check_bare_nonbuiltin_generic_annotation,
        check_underscore_unpack_target_read,
        check_underscore_forloop_target_read,
        check_failure_as_absence,
        check_phase_section_doc_reference,
    ):
        try:
            check(scope, src_root)
        except Exception as exc:
            _emit(
                rule='auditme-check-crash',
                variant=check.__name__,
                path=None,
                line=None,
                evidence=f'{type(exc).__name__}: {exc}',
                accepted=False,
                accepted_reason=None,
            )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
