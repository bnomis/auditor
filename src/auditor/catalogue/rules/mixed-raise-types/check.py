import ast
import collections
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag methods/functions that raise two or more different exception
    types where the types do not share a clear inheritance relationship.
    A common architecture smell: half the invariants raise PipelineError,
    half raise stdlib RuntimeError - callers cannot establish a clean
    catch envelope."""
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            raised_types: dict[str, list[int]] = collections.defaultdict(list)
            for inner in ast.walk(node):
                if isinstance(inner, ast.Raise) and isinstance(inner.exc, ast.Call):
                    fn = inner.exc.func
                    if isinstance(fn, ast.Name):
                        raised_types[fn.id].append(inner.lineno)
                    elif isinstance(fn, ast.Attribute):
                        raised_types[ast.unparse(fn).split('.')[-1]].append(inner.lineno)
            if len(raised_types) < 2:
                continue
            # exclude common cases where the mix is intentional: re-raise of
            # input-validation distinct from internal invariants is signalled
            # by error suffix matching: ConfigError + InputEnvelopeError is one
            # cluster; RuntimeError + PipelineError is a real mix
            STDLIB_EXCS = {'RuntimeError', 'ValueError', 'TypeError', 'KeyError', 'IndexError', 'AttributeError'}
            project_excs = {n for n in raised_types if n.endswith('Error') and n not in STDLIB_EXCS}
            if not project_excs:
                continue
            mixed_with_stdlib = STDLIB_EXCS & raised_types.keys()
            if not mixed_with_stdlib:
                continue
            # Emit ONE finding per function, listing every raise site
            sample_line = sorted(min(v) for v in raised_types.values())[0]
            accept = auditor.api.accept_reason(lines, sample_line, rule='mixed-raise-types')
            evidence = f'{node.name}: raises {sorted(raised_types.keys())}'
            auditor.api.emit(
                rule='mixed-raise-types',
                variant=f'{node.name} mixes stdlib ({sorted(mixed_with_stdlib)}) with project errors ({sorted(project_excs)})',
                path=rel,
                line=node.lineno,
                evidence=evidence,
                accepted=bool(accept),
                accepted_reason=accept,
            )
