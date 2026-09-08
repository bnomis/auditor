"""Checks on project-level artefacts rather than source."""

import ast
import json
import pathlib
import re
import subprocess

from auditme.core import _accept_reason, _all_py_files, _emit, _relpath, _source_lines
from auditme.rules.state_and_effects import _corpus_py_files


def check_ruff(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    for cmd, variant in (
        (['ruff', 'check', '--output-format=json', str(src_root)], 'ruff-check'),
        (['ruff', 'format', '--check', str(src_root)], 'ruff-format'),
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=scope)
        except FileNotFoundError:
            _emit(
                rule='ruff',
                variant=variant,
                path=None,
                line=None,
                evidence='ruff not installed',
                accepted=False,
                accepted_reason=None,
            )
            continue
        if variant == 'ruff-check' and result.stdout.strip():
            try:
                for hit in json.loads(result.stdout):
                    _emit(
                        rule='ruff',
                        variant=hit.get('code', 'ruff-check'),
                        path=_relpath(pathlib.Path(hit['filename']), scope),
                        line=hit['location']['row'],
                        evidence=hit.get('message', ''),
                        accepted=False,
                        accepted_reason=None,
                    )
            except json.JSONDecodeError:
                _emit(rule='ruff', variant='ruff-check-parse-error', path=None, line=None, evidence=result.stdout[:200], accepted=False, accepted_reason=None)
        elif variant == 'ruff-format' and result.returncode != 0:
            for ln in result.stdout.splitlines() + result.stderr.splitlines():
                if 'Would reformat' in ln or ln.endswith('.py'):
                    _emit(
                        rule='ruff', variant='ruff-format', path=ln.split(':')[0].strip(), line=None, evidence=ln.strip(), accepted=False, accepted_reason=None
                    )


# `uv lock --check` exits non-zero both when the lockfile is genuinely stale
# and when it could not resolve at all. Only the first message is the drift.
_LOCKFILE_DRIFT_MARKER = 'needs to be updated'
_LOCKFILE_TIMESTAMP_RE = re.compile(r'\d{4}-\d{2}-\d{2}T[\d:.]+Z?')


def check_lockfile(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    pyproject = scope / 'pyproject.toml'
    uvlock = scope / 'uv.lock'
    if not pyproject.exists() or not uvlock.exists():
        return
    try:
        result = subprocess.run(['uv', 'lock', '--check'], capture_output=True, text=True, cwd=scope)
    except FileNotFoundError:
        return
    if result.returncode == 0:
        return

    output = (result.stderr or result.stdout).strip()
    # uv's progress chatter carries a resolution timestamp, and a network
    # failure carries whatever the transport said. Both change between runs, so
    # emitting the raw output made this check report a different evidence
    # string every time on an unchanged tree - see the convergence rules in
    # SKILL.md. Keep only the error lines, with any timestamp masked.
    error_lines = [line.strip() for line in output.splitlines() if line.strip().startswith('error:')]
    evidence = _LOCKFILE_TIMESTAMP_RE.sub('<timestamp>', ' '.join(error_lines))[:200]

    # A lockfile that needs regenerating and a lockfile that could not be
    # checked are different facts: the first is drift, the second means the
    # question went unanswered. Reporting both as drift is the
    # failure-versus-absence defect, in the checker rather than in the code
    # under audit.
    if _LOCKFILE_DRIFT_MARKER in output:
        variant = 'uv lock --check reports the lockfile is out of date'
        evidence = evidence or 'lockfile needs updating'
    else:
        variant = 'uv lock --check could not verify the lockfile'
        evidence = evidence or 'no error detail on stderr or stdout'

    _emit(
        rule='lockfile-drift',
        variant=variant,
        path='uv.lock',
        line=None,
        evidence=evidence,
        accepted=False,
        accepted_reason=None,
    )


_PHASE_REF_RE = re.compile(r'\bPhase\s+[1-9][a-z]?\b')

_SECTION_REF_RE = re.compile(r'\bSection\s+[0-9]+\.[0-9]+\b')


def check_phase_section_doc_reference(scope: pathlib.Path, src_root: pathlib.Path) -> None:
    """Flag src/ docstrings and comments that reference numbered
    `Phase N` or `Section X.Y` spec locations. These cross-references
    rot when specs are renumbered.

    Signal:
      - Line in a .py file in src/ matches `\\bPhase [1-9][a-z]?\\b` or
        `\\bSection [0-9]+\\.[0-9]+\\b`.
      - Line is part of a docstring (triple-quoted string) OR a comment
        (starts with `#` after optional whitespace).
      - The file does NOT carry a file-level `# auditme: accept <reason>`
        marker on any comment-only line (to allow modules that render
        user-facing Phase vocabulary to be excused wholesale).
      - Hit is not explicitly accepted via inline marker.
    """
    file_level_accept_re = re.compile(r'^\s*#\s*auditme:\s*accept\s+.*phase-section')
    for path in _all_py_files(src_root):
        rel = _relpath(path, scope)
        lines = _source_lines(path)
        # File-level accept check: if any line is a comment-only
        # `# auditme: accept phase-section ...`, skip the file.
        if any(file_level_accept_re.search(raw) for raw in lines):
            continue
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            continue
        # Collect docstring line ranges
        docstring_ranges: list[tuple[int, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                doc = ast.get_docstring(node, clean=False)
                if doc and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                    const = node.body[0]
                    end = getattr(const, 'end_lineno', const.lineno)
                    docstring_ranges.append((const.lineno, end))

        def in_docstring(ln: int) -> bool:
            return any(a <= ln <= b for a, b in docstring_ranges)

        for idx, raw in enumerate(lines, 1):
            matches = list(_PHASE_REF_RE.finditer(raw)) + list(_SECTION_REF_RE.finditer(raw))
            if not matches:
                continue
            stripped = raw.strip()
            is_comment = stripped.startswith('#')
            if not (is_comment or in_docstring(idx)):
                continue
            accept = _accept_reason(lines, idx, rule='phase-section-doc-reference')
            _emit(
                rule='phase-section-doc-reference',
                variant=f'numeric spec cross-reference {matches[0].group(0)!r}',
                path=rel,
                line=idx,
                evidence=stripped[:200],
                accepted=bool(accept),
                accepted_reason=accept,
            )


_API_HEADING_RE = re.compile(r'^#{2,4}\s+API\b', re.IGNORECASE)
_ANY_HEADING_RE = re.compile(r'^#{1,6}\s+')
_FENCE_RE = re.compile(r'^\s*```')
_DEF_LINE_RE = re.compile(r'^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(')
_SPEC_SKIP_PARTS = frozenset({'.git', '.venv', 'node_modules', '__pycache__', 'audit-reviews', 'tasks'})


def _signature_params(node: ast.AST) -> list[str] | None:
    """Render a def's parameters as an ordered list of comparable names.

    A keyword-only marker is rendered as a `*` entry and a default as a
    `=` suffix, so a parameter that moved across the `*` or lost its
    default reads as a difference. Types are deliberately NOT compared:
    a spec routinely writes `LitRevSettings` where the source writes
    `litlib.settings.LitRevSettings`, and treating that as drift would
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
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        out.append(arg.arg + ('=' if default is not None else ''))
    if args.kwarg is not None:
        out.append('**' + args.kwarg.arg)
    return out


def _parse_spec_def(block_lines: list[str], start: int) -> tuple[ast.AST, int] | None:
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


def _source_definitions(scope: pathlib.Path, src_root: pathlib.Path) -> dict[str, list[tuple[ast.AST, pathlib.Path]]]:
    """Every MODULE-LEVEL `def` across the whole corpus, keyed by bare name.

    Two deliberate choices, both learned from the first run against a real
    project:

    - **Corpus-wide, not per-root.** The driver audits one root per pass, so
      resolving against `src_root` answers a different question on each pass:
      litrev's `write_worklist` resolved to the library function on the
      `src/litlib` pass and to a test double's method on the `src/tests` one,
      and the spec was reported as drifting from both. A name is ambiguous or
      it is not, and that is a property of the corpus.
    - **Module-level only.** A method that happens to share a module-level
      function's name is not a candidate for the `def` a spec's API block
      documents - it is usually a test double. Including methods made every
      such name ambiguous and silently dropped a real finding.
    """
    out: dict[str, list[tuple[ast.AST, pathlib.Path]]] = {}
    for path in _corpus_py_files(scope, src_root):
        try:
            tree = ast.parse('\n'.join(_source_lines(path)))
        except SyntaxError:
            continue
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.setdefault(node.name, []).append((node, path))
    return out


def _spec_markdown_files(scope: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path for path in scope.rglob('*.md') if not _SPEC_SKIP_PARTS & set(path.relative_to(scope).parts))


def check_spec_api_signature_drift(scope: pathlib.Path, src_root: pathlib.Path) -> None:
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
        across the whole corpus (see `_source_definitions`);
      - the ordered parameter lists differ (see `_signature_params` - names,
        `*` placement and the presence of a default, never types).

    Refinements (each has a test asserting it does not fire):
      - **An ambiguous name does not fire.** If the corpus holds more than
        one module-level `def` with that name, the check cannot know which one
        the spec means, so it says nothing rather than guessing.
      - **A name with no module-level definition does not fire.** A Protocol
        method plus its implementations, and `__init__` everywhere, resolve to
        methods only; a spec block showing such a contract is not checked.
      - **An elided signature does not fire.** `def f(...)` and a block
        carrying `# ...` are a spec showing a contract rather than a
        signature.
      - **Types are not compared.** A spec's `settings: LitRevSettings`
        against a source's `settings: litlib.settings.LitRevSettings` is
        the same parameter.
      - **Prose does not fire.** Only fenced blocks under an API heading are
        read, so a spec naming a function in a sentence is out of scope.
      - **Audit reviews and task lists are not read.** They are dated
        records of what was true when they ran, and regenerating or
        flagging them would falsify the record.

    Raised as a request by litrev's review-11 (2026-09-01), which found
    around twenty instances by hand in a single pass, nearly all of them a
    parameter added by a fix whose commit did not touch the spec.
    """
    definitions = _source_definitions(scope, src_root)
    if not definitions:
        return

    for doc in _spec_markdown_files(scope):
        lines = _source_lines(doc)
        rel = _relpath(doc, scope)
        in_api_section = False
        in_fence = False
        index = 0
        while index < len(lines):
            line = lines[index]
            if _FENCE_RE.match(line):
                in_fence = not in_fence
                index += 1
                continue
            if not in_fence and _ANY_HEADING_RE.match(line):
                in_api_section = bool(_API_HEADING_RE.match(line))
                index += 1
                continue
            if not (in_fence and in_api_section):
                index += 1
                continue
            match = _DEF_LINE_RE.match(line)
            if not match:
                index += 1
                continue
            parsed = _parse_spec_def(lines, index)
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
            spec_params = _signature_params(spec_node)
            source_params = _signature_params(source_node)
            if spec_params is None or source_params is None or spec_params == source_params:
                index = last_index + 1
                continue
            accept = _accept_reason(lines, index + 1, end_lineno=last_index + 1, rule='spec-api-signature-drift')
            _emit(
                rule='spec-api-signature-drift',
                variant=f'{name}: spec says ({", ".join(spec_params)}), source says ({", ".join(source_params)})',
                path=rel,
                line=index + 1,
                evidence=f'{line.strip()[:120]} | {_relpath(source_path, scope)}:{source_node.lineno}',
                accepted=bool(accept),
                accepted_reason=accept,
            )
            index = last_index + 1
