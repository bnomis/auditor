import ast
import re
import typing

import auditor.api

if typing.TYPE_CHECKING:
    import pathlib

API_HEADING_RE = re.compile(r'^#{2,4}\s+API\b', re.IGNORECASE)
ANY_HEADING_RE = re.compile(r'^#{1,6}\s+')
BACKTICK_FENCE_RE = re.compile(r'^\s*```')


def signature_params(node: ast.AST) -> list[str] | None:
    """Render a def's parameters as an ordered list of comparable names.

    A keyword-only marker is rendered as a `*` entry and a default as a
    `=` suffix, so a parameter that moved across the `*` or lost its
    default reads as a difference. Types are deliberately NOT compared:
    a spec routinely writes `AppSettings` where the source writes
    `applib.settings.AppSettings`, and treating that as drift would
    bury the real findings.
    """
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    args = node.args
    out: list[str] = []
    positional = list(args.posonlyargs) + list(args.args)
    defaults_start = len(positional) - len(args.defaults)
    for i, arg in enumerate(positional):
        out.append(arg.arg + ('=' if i >= defaults_start else ''))
    if args.vararg is not None:
        out.append('*' + args.vararg.arg)
    elif args.kwonlyargs:
        out.append('*')
    for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        out.append(arg.arg + ('=' if default is not None else ''))
    if args.kwarg is not None:
        out.append('**' + args.kwarg.arg)
    return out


def parse_spec_def(block_lines: list[str], start: int) -> tuple[ast.AST, int] | None:
    """Parse one `def` from a spec code block, joining wrapped lines.

    Returns the parsed node and the index of the last line consumed, or
    None if the signature cannot be parsed - which is the carve-out for a
    signature the spec deliberately elides (`def f(...)`, `# ...`).
    """
    joined = ''
    index = start
    while index < len(block_lines) and index - start < 20:
        joined += block_lines[index].strip() + ' '
        if joined.count('(') and joined.count('(') == joined.count(')'):
            break
        index += 1
    else:
        return None
    body = joined.strip()
    if '...' in body[body.index('(') :]:
        return None
    body = body.removesuffix(':').rstrip() + ': pass'
    try:
        module = ast.parse(body)
    except SyntaxError:
        return None
    if not module.body or not isinstance(module.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    return module.body[0], index


def check(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag a `def` in a spec's API block whose signature no longer matches the source.

    A spec states a function's contract in a fenced block under an `API`
    heading. When a change adds a parameter and the spec is not updated in
    the same commit, the two drift - and a reader cannot detect it without
    opening both files. Both halves are machine-readable, so this asks the
    question mechanically.

    Signal:
      - a `def`/`async def` line inside a fenced code block that follows an
        `## API` (or `### API`) heading and precedes the next heading;
      - the same bare name resolves to exactly one module-level definition
        across the whole corpus (see `corpus_definitions`);
      - the ordered parameter lists differ (see `signature_params` - names,
        `*` placement and the presence of a default, never types).

    Refinements (each has a test asserting it does not fire):
      - **An ambiguous name does not fire.** If the corpus holds more than
        one module-level `def` with that name, the check cannot know which one
        the spec means, so it says nothing rather than guessing.
      - **A method in a spec's `class` block does not fire.** A `def`
        indented under a `class` line in the same fence is a method; methods
        are not in `corpus_definitions`, so its bare name would otherwise be
        compared with an unrelated module-level function of the same name.
      - **A name with no module-level definition does not fire.** A Protocol
        method plus its implementations, and `__init__` everywhere, resolve to
        methods only; a spec block showing such a contract is not checked.
      - **An elided signature does not fire.** `def f(...)` and a block
        carrying `# ...` are a spec showing a contract rather than a
        signature.
      - **Types are not compared.** A spec's `settings: AppSettings`
        against a source's `settings: applib.settings.AppSettings` is
        the same parameter.
      - **Prose does not fire.** Only fenced blocks under an API heading are
        read, so a spec naming a function in a sentence is out of scope.
      - **Audit reviews and task lists are not read.** They are dated
        records of what was true when they ran, and regenerating or
        flagging them would falsify the record.

    Raised as a request by an audit (shipped 2026-09-01) that found many
    instances by hand in a single pass, nearly all of them a
    parameter added by a fix whose commit did not touch the spec.
    """
    definitions = auditor.api.corpus_definitions(scope, src_root)
    if not definitions:
        return

    for doc in auditor.api.spec_markdown_files(scope):
        lines = auditor.api.source_lines(doc)
        rel = auditor.api.relpath(doc, scope)
        in_api_section = False
        in_fence = False
        class_indent: int | None = None
        index = 0
        while index < len(lines):
            line = lines[index]
            if BACKTICK_FENCE_RE.match(line):
                in_fence = not in_fence
                class_indent = None
                index += 1
                continue
            if not in_fence and ANY_HEADING_RE.match(line):
                in_api_section = bool(API_HEADING_RE.match(line))
                index += 1
                continue
            if not (in_fence and in_api_section):
                index += 1
                continue
            indent = len(line) - len(line.lstrip())
            if line.strip() and class_indent is not None and indent <= class_indent:
                class_indent = None
            class_match = auditor.api.CLASS_LINE_RE.match(line)
            if class_match and class_indent is None:
                class_indent = len(class_match.group(1))
                index += 1
                continue
            match = auditor.api.DEF_LINE_RE.match(line)
            if not match:
                index += 1
                continue
            if class_indent is not None:
                index += 1
                continue
            parsed = parse_spec_def(lines, index)
            if parsed is None:
                index += 1
                continue
            spec_node, last_index = parsed
            name = match.group(1)
            candidates = definitions.get(name, [])
            if len(candidates) != 1:
                index = last_index + 1
                continue
            source_node, source_path = candidates[0]
            spec_params = signature_params(spec_node)
            source_params = signature_params(source_node)
            if spec_params is None or source_params is None or spec_params == source_params:
                index = last_index + 1
                continue
            accept = auditor.api.accept_reason(lines, index + 1, end_lineno=last_index + 1, rule='spec-api-signature-drift')
            auditor.api.emit(
                related=[auditor.api.relpath(source_path, scope)],
                rule='spec-api-signature-drift',
                variant=f'{name}: spec says ({", ".join(spec_params)}), source says ({", ".join(source_params)})',
                path=rel,
                line=index + 1,
                evidence=f'{line.strip()[:120]} | {auditor.api.relpath(source_path, scope)}:{source_node.lineno}',
                accepted=bool(accept),
                accepted_reason=accept,
            )
            index = last_index + 1
