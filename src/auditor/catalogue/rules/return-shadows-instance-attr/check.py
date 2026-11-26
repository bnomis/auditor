import ast
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
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
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            owned_attrs: set[str] = set()
            init = next(
                (m for m in cls.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name == '__init__'),
                None,
            )
            if init is None:
                continue
            arg_names = {a.arg for a in init.args.args}
            for inner in ast.walk(init):
                if not isinstance(inner, ast.Assign):
                    continue
                for tgt in inner.targets:
                    if (
                        isinstance(tgt, ast.Attribute)
                        and isinstance(tgt.value, ast.Name)
                        and tgt.value.id == 'self'
                        and isinstance(inner.value, ast.Name)
                        and inner.value.id == tgt.attr
                        and inner.value.id in arg_names
                    ):
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
                                    if isinstance(inner, ast.Assign) and any(isinstance(t, ast.Name) and t.id == rname for t in inner.targets):
                                        src = ast.unparse(inner.value) if hasattr(ast, 'unparse') else ''
                                        if f'self.{attr}' in src:
                                            has_derivation = True
                                            break
                                if not has_derivation:
                                    continue
                                accept = auditor.api.accept_reason(lines, ret.lineno, rule='return-shadows-instance-attr')
                                auditor.api.emit(
                                    rule='return-shadows-instance-attr',
                                    variant=f'{cls.name}.{member.name} returns `{rname}` which shadows self.{attr}; callers must reassign',
                                    path=rel,
                                    line=ret.lineno,
                                    evidence=(lines[ret.lineno - 1].strip()[:200] if ret.lineno <= len(lines) else ''),
                                    accepted=bool(accept),
                                    accepted_reason=accept,
                                )
                                break
