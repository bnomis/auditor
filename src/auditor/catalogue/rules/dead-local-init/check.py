import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


# Walk every branch arm; ensure it starts with an assignment
# to var_name or a return, not a read.
def branch_overrides(branch: list[ast.stmt], var_name: str) -> bool:
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
                rs = ast.unparse(s.value)
                # if body reads var_name in return, branch did not override;
                # if it returned something else, the initial value was dead
                return not re.search(rf'\b{re.escape(var_name)}\b', rs)
            return True
    return False


def walk_chain(stmt: ast.If, var_name: str) -> bool:
    if not branch_overrides(stmt.body, var_name):
        return False
    orelse = stmt.orelse
    while orelse:
        if len(orelse) == 1 and isinstance(orelse[0], ast.If):
            nxt = orelse[0]
            if not branch_overrides(nxt.body, var_name):
                return False
            orelse = nxt.orelse
        else:
            return branch_overrides(orelse, var_name)
    return False  # no else branch => init might be read on that path


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
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
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
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
            if (
                isinstance(value, ast.Dict)
                and not value.keys
                or isinstance(value, ast.List)
                and not value.elts
                or isinstance(value, ast.Set)
                and not value.elts
                or isinstance(value, ast.Tuple)
                and not value.elts
                or (
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and value.func.id in auditor.api.BARE_GENERIC_NAMES
                    and not value.args
                    and not value.keywords
                )
            ):
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

            if not walk_chain(if_stmt, var_name):
                continue
            accept = auditor.api.accept_reason(lines, first.lineno, rule='dead-local-init')
            auditor.api.emit(
                rule='dead-local-init',
                variant=f'`{var_name} = <empty>` at top of {func.name} is unconditionally overridden in all if/elif/else branches',
                path=rel,
                line=first.lineno,
                evidence=(lines[first.lineno - 1].strip()[:200] if first.lineno <= len(lines) else ''),
                accepted=bool(accept),
                accepted_reason=accept,
            )
