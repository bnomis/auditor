"""The A19 lister: every site the A19 question applies to."""

import ast
import collections
import textwrap
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import collections.abc
    import pathlib

A19_RULES = ('broad-except-wrong-level', 'logger-exception-graceful-degradation', 'silent-broad-except')


def broad_except_hits(
    scope: pathlib.Path, src_root: pathlib.Path, rule: str, finder: collections.abc.Callable[[ast.AST], collections.abc.Iterable[ast.ExceptHandler]]
) -> None:
    """Emit each site the finder reports under the rule id, as the rule does, for `capture_hits`."""
    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in finder(tree):
            auditor.api.emit(rule=rule, variant='', path=auditor.api.relpath(path, scope), line=node.lineno, evidence='', accepted=False, accepted_reason=None)


def silent_broad_except_hits(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """The `silent-broad-except` sites, for `capture_hits`."""
    broad_except_hits(scope, src_root, 'silent-broad-except', auditor.api.silent_broad_except_sites)


def wrong_level_broad_except_hits(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """The `broad-except-wrong-level` sites, for `capture_hits`."""
    broad_except_hits(scope, src_root, 'broad-except-wrong-level', auditor.api.wrong_level_broad_except_sites)


def graceful_degradation_hits(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """The `logger-exception-graceful-degradation` sites, for `capture_hits`."""
    for path in auditor.api.all_py_files(src_root):
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for lineno in auditor.api.graceful_degradation_sites(tree):
            auditor.api.emit_site(scope, path, 'logger-exception-graceful-degradation', lineno)


A19_CHECKS = (
    silent_broad_except_hits,
    wrong_level_broad_except_hits,
    graceful_degradation_hits,
)


LOGGER_NAMES = frozenset({'LOGGER', '_logger', 'log', 'logger', 'logging', 'loguru.logger'})


LOG_LEVELS = frozenset({'critical', 'debug', 'error', 'exception', 'info', 'warn', 'warning'})


LEAVING_STATEMENTS = (ast.Return, ast.Raise, ast.Continue, ast.Break)


def logger_call_level(node: ast.AST) -> str | None:
    """The level when the node is a call to a logging method on a logger name, else None."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr not in LOG_LEVELS:
        return None
    receiver = auditor.api.dotted_name(node.func.value)
    if receiver is None:
        return None
    return node.func.attr if receiver.removeprefix('self.') in LOGGER_NAMES else None


def log_calls_of(handler: ast.ExceptHandler) -> list[str]:
    """Each logger call in the handler body as `level: text`, text being its first argument."""
    calls: list[str] = []
    for statement in handler.body:
        for node in ast.walk(statement):
            level = logger_call_level(node)
            if level is not None and isinstance(node, ast.Call):
                calls.append(f'{level}: {ast.unparse(node.args[0]) if node.args else ""}')
    return calls


def function_summary(function: auditor.api.FunctionNode) -> dict[str, str | None]:
    """Name, signature, return annotation and last statement of a function."""
    return {
        'name': function.name,
        'signature': ast.unparse(function.args),
        'returns': ast.unparse(function.returns) if function.returns is not None else None,
        'last_statement': ast.unparse(function.body[-1]) if function.body else None,
    }


def handler_anchor_lines(handler: ast.ExceptHandler, function: auditor.api.FunctionNode | None) -> list[int]:
    """The handler's lines, plus the function's last `return` when the handler falls through."""
    lines = list(range(handler.lineno, (handler.end_lineno or handler.lineno) + 1))
    falls_through = not handler.body or not isinstance(handler.body[-1], LEAVING_STATEMENTS)
    if falls_through and function is not None and function.body and isinstance(function.body[-1], ast.Return):
        lines.append(function.body[-1].lineno)
    return lines


def carries_a19_marker(lines: list[str], anchors: list[int]) -> bool:
    """Whether an accept marker for an A19 rule sits on a handler's lines or the line above one.

    The marker records the user's decision to keep the handler, as SKILL.md's
    "Conflicts with no winner" prescribes, so a handler the sweep does not
    report is left out as a sweep hit is.
    """
    return any(auditor.api.accept_reason(lines, line, rule=rule) for line in anchors for rule in A19_RULES)


def list_candidates(scope: pathlib.Path) -> list[auditor.api.Candidate]:
    """Every broad handler and every handler logging `.exception(` that neither a sweep hit nor an A19 accept marker already settles."""
    files = auditor.api.read_audited_files(scope)
    hits = auditor.api.capture_hits(scope, A19_CHECKS)
    found: list[auditor.api.Candidate] = []
    for file in files:
        scopes = auditor.api.scope_nodes(file.tree)
        counter = auditor.api.SiteCounter()
        for qualname, node in auditor.api.walk_with_qualname(file.tree):
            if not isinstance(node, (ast.Try, ast.TryStar)):
                continue
            function = scopes.get(qualname)
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function = None
            try_source = textwrap.dedent('\n'.join(file.lines[node.lineno - 1 : node.end_lineno]))
            for handler in node.handlers:
                log_calls = log_calls_of(handler)
                logs_exception = any(call.startswith('exception: ') for call in log_calls)
                if not (auditor.api.is_broad_handler(handler) or logs_exception):
                    continue
                number = counter.next(f'{qualname}::except')
                anchors = handler_anchor_lines(handler, function)
                if auditor.api.hit_on_anchor(hits, file.rel, anchors, A19_RULES) or carries_a19_marker(file.lines, anchors):
                    continue
                function_source = textwrap.dedent('\n'.join(file.lines[function.lineno - 1 : function.end_lineno])) if function is not None else try_source
                handler_source = textwrap.dedent('\n'.join(file.lines[handler.lineno - 1 : handler.end_lineno]))
                found.append(
                    auditor.api.span_candidate(
                        'A19',
                        f'{file.rel}::{qualname}::except#{number}',
                        file.rel,
                        handler.lineno,
                        handler.end_lineno or handler.lineno,
                        {
                            'handler': handler_source,
                            'try': try_source,
                            'function': function_summary(function) if function is not None else None,
                            'log_calls': log_calls,
                        },
                        [function_source],
                    )
                )
    return found
