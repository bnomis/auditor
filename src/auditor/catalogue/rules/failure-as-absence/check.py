import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


# Directories whose modules adapt an external service. AGENTS.md's
# failure-versus-absence rule is written for "a source or resolver"; LLM
# providers are the same shape - an adapter over a remote API - so they are
# included. Scope is deliberately narrow: outside an adapter, a bare
# `return None` from an except handler is often a legitimate cache miss or
# optional lookup, and firing on those would make the check untrustworthy.
EXTERNAL_ADAPTER_DIRS = frozenset({'providers', 'resolvers', 'sources'})


# What counts as "recording a failure the caller can see". Logging does not:
# a log line is not a value the caller can branch on, which is the whole point
# of the rule.
FAILURE_WORD_RE = re.compile(r'error|failure|failed|cannot_answer', re.IGNORECASE)


LOGGING_CALL_RE = re.compile(r'^(logger|logging|log)\b|\.(debug|info|warning|error|exception|critical)$')


STATUS_TEST_RE = re.compile(r'\b(status|status_code|statuscode)\b')


def clean_absence_return(node: ast.Return) -> str | None:
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
    if isinstance(value, ast.Tuple) and value.elts and all(isinstance(e, ast.Constant) and e.value is None for e in value.elts):
        return f'return ({", ".join(["None"] * len(value.elts))})'
    return None


def records_visible_failure(stmts: list[ast.stmt]) -> bool:
    """True when these statements raise, or set something the caller reads.

    A keyword argument counts (`SearchBatch(..., error=str(e))`) because that
    is the project's documented alternative to raising. A logger call does not,
    however error-shaped its name.
    """
    for stmt in stmts:
        for child in [stmt, *auditor.api.walk_within_scope(stmt)]:
            if isinstance(child, ast.Raise):
                return True
            if isinstance(child, ast.keyword) and child.arg and FAILURE_WORD_RE.search(child.arg):
                return True
            if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                if any(FAILURE_WORD_RE.search(ast.unparse(t)) for t in targets if t is not None):
                    return True
            if isinstance(child, ast.Call):
                func_src = ast.unparse(child.func)
                if LOGGING_CALL_RE.search(func_src):
                    continue
                if FAILURE_WORD_RE.search(func_src):
                    return True
    return False


def status_failure_branch(node: ast.If) -> list[ast.stmt] | None:
    """Return whichever branch of an HTTP-status test runs on a non-200."""
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return None
    if not STATUS_TEST_RE.search(ast.unparse(test)):
        return None
    op = test.ops[0]
    if isinstance(op, (ast.NotEq, ast.GtE, ast.Gt, ast.NotIn)):
        return node.body
    if isinstance(op, (ast.Eq, ast.In)):
        return node.orelse or None
    return None


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
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
    for path in auditor.api.all_py_files(src_root):
        parts = set(path.parts)
        if 'tests' in parts or not (parts & EXTERNAL_ADAPTER_DIRS):
            continue
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                variant, body = 'caught exception returns empty', node.body
            elif isinstance(node, ast.If):
                body = status_failure_branch(node)
                if body is None:
                    continue
                variant = 'non-200 branch returns empty'
            else:
                continue
            if records_visible_failure(body):
                continue
            for child in [*body, *(c for stmt in body for c in auditor.api.walk_within_scope(stmt))]:
                if not isinstance(child, ast.Return):
                    continue
                label = clean_absence_return(child)
                if label is None:
                    continue
                accept = auditor.api.accept_reason(lines, child.lineno, rule='failure-as-absence') or auditor.api.accept_reason(
                    lines, node.lineno, rule='failure-as-absence'
                )
                auditor.api.emit(
                    rule='failure-as-absence',
                    variant=f'{variant} ({label})',
                    path=rel,
                    line=child.lineno,
                    evidence=lines[child.lineno - 1].strip()[:200] if child.lineno <= len(lines) else label,
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
