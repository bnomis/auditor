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

ACCEPT_COMMENT_RE = re.compile(r'#\s*auditme:\s*accept\b\s*(.*)$')


def _emit(**kwargs) -> None:
    print(json.dumps(kwargs, sort_keys=True))


def _source_lines(path: pathlib.Path) -> list[str]:
    try:
        return path.read_text(encoding='utf-8').splitlines()
    except UnicodeDecodeError:
        return []


def _accept_reason(lines: list[str], lineno: int) -> str | None:
    for candidate_lineno in (lineno, lineno - 1):
        if 1 <= candidate_lineno <= len(lines):
            m = ACCEPT_COMMENT_RE.search(lines[candidate_lineno - 1])
            if m:
                return m.group(1).strip() or 'no reason given'
    return None


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
        ('leading-underscore-destructure', 'destructured `_x, y = ...`', re.compile(r'^\s+_[a-z][a-zA-Z0-9_]*\s*,\s*[a-zA-Z]')),
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
                accept = _accept_reason(lines, idx)
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
                accept = _accept_reason(lines, idx)
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
                accept = _accept_reason(lines, idx)
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
        type_checking_linenos: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                test_src = ast.unparse(node.test) if hasattr(ast, 'unparse') else ''
                if 'TYPE_CHECKING' in test_src:
                    for child in ast.walk(node):
                        if hasattr(child, 'lineno'):
                            type_checking_linenos.add(child.lineno)
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
        importer_module = rel.replace('/', '.').removesuffix('.py')
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
                accept = _accept_reason(lines, inner.lineno)
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
            accept = _accept_reason(lines, node.lineno)
            _emit(
                rule='silent-broad-except',
                variant='no logger and no raise in body',
                path=rel,
                line=node.lineno,
                evidence=lines[node.lineno - 1].strip()[:200] if node.lineno <= len(lines) else '',
                accepted=bool(accept),
                accepted_reason=accept,
            )


def check_except_interpolation(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler) or not node.name:
                continue
            bound = node.name
            seen_linenos: set[tuple[int, str]] = set()
            for inner in ast.walk(node):
                if isinstance(inner, ast.JoinedStr):
                    for v in inner.values:
                        if isinstance(v, ast.FormattedValue):
                            expr_src = ast.unparse(v.value) if hasattr(ast, 'unparse') else ''
                            if re.search(rf'\b{re.escape(bound)}\b', expr_src):
                                key = (inner.lineno, 'fstring')
                                if key in seen_linenos:
                                    break
                                seen_linenos.add(key)
                                accept = _accept_reason(lines, inner.lineno)
                                _emit(
                                    rule='except-interpolation',
                                    variant='f-string interpolates caught exception',
                                    path=rel,
                                    line=inner.lineno,
                                    evidence=(lines[inner.lineno - 1].strip()[:200] if inner.lineno <= len(lines) else ''),
                                    accepted=bool(accept),
                                    accepted_reason=accept,
                                )
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
                                accept = _accept_reason(lines, inner.lineno)
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
            accept = _accept_reason(full_lines, lineno)
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
            accept = _accept_reason(lines, node.lineno)
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
                accept = _accept_reason(lines, node.lineno)
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
            accept = _accept_reason(full_lines, lineno)
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
        for node in ast.walk(tree):
            module_name = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    _maybe_emit_layering(rel, lines, node.lineno, importer_pkg, module_name,
                                         rank, accepted, package_root_name)
            elif isinstance(node, ast.ImportFrom) and node.module:
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
    accept = _accept_reason(lines, lineno)
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
            accept = _accept_reason(lines, node.lineno)
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
                    accept = _accept_reason(lines, inner.lineno)
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
            accept = _accept_reason(lines, node.lineno)
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
    Sparse public surfaces force consumers to reach into private submodules."""
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
        accept = _accept_reason(lines, 1)
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
            accept = _accept_reason(lines, sample_line)
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
                                accept = _accept_reason(lines, node.lineno)
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
                            accept = _accept_reason(lines, line_no)
                            _emit(
                                rule='migration-shim-consumer',
                                variant=f'reads `{sym}` from shim `{parent_mod}`; canonical home is `{canonical_mod}`',
                                path=rel,
                                line=line_no,
                                evidence=full[:200],
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
            accept = _accept_reason(lines, idx)
            _emit(
                rule='duplicated-word',
                variant=f'duplicated word {word!r}',
                path=rel,
                line=idx,
                evidence=s[:200],
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
        check_lockfile,
        check_duplicated_word,
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
