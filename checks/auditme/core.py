"""Shared helpers every check uses."""

from __future__ import annotations
import ast
import json
import pathlib
import re


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

_LITERAL_DISPATCH_TYPE_NAMES = frozenset({'str'})  # extensible via helper below
