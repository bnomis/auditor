import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib


CALLBACK_METHOD_RE = re.compile(r'^on_(step|log|evaluate|train_\w+|batch_\w+|epoch_\w+|predict_\w+|save|init_\w+)$')


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
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
        (`if self.opened is None: ...`) - we can't verify that
        mechanically, so the check is coarse: any such call is flagged.

    One-time setup belongs in `__init__`; if the setup cannot move there
    (rare), add `# auditme: accept <reason>`.
    """
    HOT_IO = {'open', 'mkdir', 'write_text', 'write_bytes'}
    for path in auditor.api.all_py_files(src_root):
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            # Heuristic: class inherits from a *Callback base OR file
            # imports TrainerCallback (we just check the class bases).
            base_names = []
            for b in cls.bases:
                base_names.append(ast.unparse(b))
            base_str = ' '.join(base_names)
            looks_like_callback = 'Callback' in base_str or 'TrainerCallback' in base_str
            # Also accept if any method in the class matches the callback pattern
            has_callback_method = any(isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and CALLBACK_METHOD_RE.match(m.name) for m in cls.body)
            if not (looks_like_callback or has_callback_method):
                continue
            for method in cls.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not CALLBACK_METHOD_RE.match(method.name):
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
                    accept = auditor.api.accept_reason(lines, sub.lineno, rule='callback-hotpath-io')
                    auditor.api.emit(
                        rule='callback-hotpath-io',
                        variant=f'{cls.name}.{method.name} performs per-event `{short}`; move setup to __init__',
                        path=rel,
                        line=sub.lineno,
                        evidence=(lines[sub.lineno - 1].strip()[:200] if sub.lineno <= len(lines) else ''),
                        accepted=bool(accept),
                        accepted_reason=accept,
                    )
                    break
