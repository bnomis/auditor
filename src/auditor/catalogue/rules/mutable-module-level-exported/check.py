import typing

import auditor.api

if typing.TYPE_CHECKING:
    import ast
    import pathlib


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag module-level mutable containers that are read by name from
    another module in the same corpus. Externally-read globals should
    be immutable so callers cannot mutate shared state.

    Signal:
      - Module-level `NAME = {...}` / `NAME = [...]` / `NAME = {...}` set
        literal, the comprehension form of any of the three, or a call to
        the bare builtin `dict(...)` / `list(...)` / `set(...)`, where the
        value is NOT wrapped in `types.MappingProxyType`, `frozenset`, or
        `tuple`.
      - `NAME` is read from another file, as `from <this-module> import NAME`,
        as `<this-module>.NAME`, or as
        `sys.modules['<this-module>'].NAME`; see `dotted_read`.

    Locked enumeration (per SKILL.md A20):
      dict -> must be `types.MappingProxyType(...)`.
      set  -> must be `frozenset(...)`.
      list -> must be `tuple(...)`.

    A comprehension is the same container as its literal - `{k: f(k) for ...}`
    is a `dict`, mutable and shared exactly as `{...}` is - so it is the same
    finding, and so is a builtin constructor call (`list(...)`), which states
    its type just as plainly (ruled 2026-10-31). Any other `Call` value
    (`DEFAULTS = get_defaults()`) is deliberately NOT covered: its type is not
    knowable from the assignment.

    The reader scan covers every root the sweep reads - every package under
    `src/` and every extra root such as `bin/` - not just the root being
    swept; see `corpus_py_files`.

    A wrapped value is this check's non-goal and
    `check_mutable_members_in_immutable_wrapper`'s subject: the wrapper is
    shallow, so `types.MappingProxyType({'a': []})` satisfies this predicate
    while still handing every caller a live `list`.

    Private (non-read) mutable globals are NOT flagged - that is a
    different rule.
    """
    # First pass: for every module, collect top-level Assign/AnnAssign
    # targets whose RHS is a bare dict/list/set - literal or comprehension -
    # plus the module dotted-import path.
    candidates: list[tuple[pathlib.Path, ast.stmt, ast.expr, str]] = []
    module_name_of: dict[pathlib.Path, str] = {}
    for path in auditor.api.all_py_files(src_root):
        module_name_of[path] = auditor.api.module_dotted(path, src_root)
        lines = auditor.api.source_lines(path)
        tree = auditor.api.read_and_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            name, value = auditor.api.module_level_binding(node)
            if name is None or value is None or name.startswith('_'):
                continue
            if auditor.api.mutable_value_shape(value) is None:
                continue
            candidates.append((path, node, value, name))

    if not candidates:
        return

    # Second pass: for each candidate, check whether ANY other file reads that
    # name. See `reads_by_module_and_name` for the forms a read is written in.
    imports_of = auditor.api.reads_by_module_and_name(scope, src_root)
    for path, assign_node, value, name in candidates:
        module = module_name_of[path]
        # auditme: accept[get-container-default-then-method-call] an internal mapping that never holds `None`
        importers = imports_of.get((module, name), [])
        # Only flag if imported from a DIFFERENT file
        external_importers = [(p, ln) for p, ln in importers if p != path]
        if not external_importers:
            continue
        rel = auditor.api.relpath(path, scope)
        lines = auditor.api.source_lines(path)
        accept = auditor.api.accept_reason(lines, assign_node.lineno, rule='mutable-module-level-exported')
        shape, required_wrap = auditor.api.mutable_value_shape(value)
        auditor.api.emit(
            related=[auditor.api.relpath(p, scope) for p, _ in external_importers],
            rule='mutable-module-level-exported',
            variant=(f'{name} is a mutable {shape} read by {len(external_importers)} other file(s); wrap in {required_wrap}'),
            path=rel,
            line=assign_node.lineno,
            evidence=(lines[assign_node.lineno - 1].strip()[:200] if assign_node.lineno <= len(lines) else ''),
            accepted=bool(accept),
            accepted_reason=accept,
        )
