import ast
import collections
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag methods of one class that call the same sink with the same attribute target."""
    MUTATING_METHOD_NAMES = {
        'set',
        'reset',
        'clear',
        'update',
        'mutate',
        'merge',
        'replace',
        'apply',
        'patch',
        'override',
        'flush',
        'write',
        'persist',
        'save',
        'emit',
        'dump',
    }
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            # For each method, collect calls of the shape f(..., self.<attr>, ...)
            # keyed by (callee_dotted, frozenset(self.<attr> args))
            calls_per_key: dict[tuple[str, tuple[str, ...]], list[tuple[str, int]]] = collections.defaultdict(list)
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
                    callee = ast.unparse(inner.func)
                    # collect self.<attr> args
                    self_args: list[str] = []
                    for a in inner.args:
                        src = ast.unparse(a)
                        if src.startswith('self.'):
                            self_args.append(src)
                    for kw in inner.keywords:
                        if kw.arg is None:
                            continue
                        src = ast.unparse(kw.value)
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
                looks_like_sink = any(tok in callee_tail for tok in auditor.api.SINK_TOKENS)
                target_is_path_or_dir = any('dir' in a.lower() or 'path' in a.lower() or 'file' in a.lower() for a in self_args)
                if not (looks_like_sink or target_is_path_or_dir):
                    continue
                _, first_line = sites[0]
                accept = auditor.api.accept_reason(lines, first_line, rule='duplicate-side-effect-per-target')
                auditor.api.emit(
                    rule='duplicate-side-effect-per-target',
                    variant=f'{cls.name}.{{{", ".join(sorted(method_names))}}} all call {callee}({", ".join(self_args)})',
                    path=rel,
                    line=first_line,
                    evidence=f'{cls.name}: methods {sorted(method_names)} share sink {callee}',
                    accepted=bool(accept),
                    accepted_reason=accept,
                )
