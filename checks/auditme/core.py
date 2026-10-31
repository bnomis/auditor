"""Shared helpers every check uses."""

import ast
import collections.abc
import json
import pathlib
import re

# An accept marker may name the single rule it answers for:
#     # auditme: accept[failure-as-absence] the caller reads batch.error
# An unscoped marker accepts every rule that fires on the line, which is how
# every marker written before 2026-08-12 behaves. That form is retained so no
# existing marker needs migrating, but it is the reason a newly added check can
# arrive silently pre-accepted: a marker weighed for one rule cannot have
# considered a rule that did not exist when it was written. New markers should
# name their rule.
ACCEPT_COMMENT_RE = re.compile(r'#\s*auditme:\s*accept\b(?:\[([a-z0-9-]+)\])?\s*(.*)$')

# Hits already printed this run, as their serialised form. The driver runs every
# check once per package under src/, so the project-level checks - the lockfile
# one, and every check that reads AGENTS.md - see the same project N times and
# would report each of their hits N times. A hit is identified by its whole
# record, so two genuinely different hits can never collide here.
_EMITTED: set[str] = set()


def _emit(related: list[str] | None = None, **kwargs) -> None:
    """Print one hit. `related` names the other files a cross-file hit compares
    against (repository-relative, sorted, de-duplicated); it is omitted when
    empty so every other hit serialises as before."""
    if related:
        kwargs['related'] = sorted(set(related) - {kwargs.get('path')})
        if not kwargs['related']:
            del kwargs['related']
    line = json.dumps(kwargs, sort_keys=True)
    if line in _EMITTED:
        return
    _EMITTED.add(line)
    print(line)


def _source_lines(path: pathlib.Path) -> list[str]:
    try:
        return path.read_text(encoding='utf-8').splitlines()
    except UnicodeDecodeError:
        return []


def _accept_reason(
    lines: list[str],
    lineno: int,
    end_lineno: int | None = None,
    rule: str | None = None,
) -> str | None:
    """Return the accept reason covering this line for this rule, if any.

    A marker scoped to a rule (`accept[some-rule]`) answers only for that rule;
    one that names a different rule is ignored, so a decision taken about
    tracebacks cannot silently excuse a later check about return values. An
    unscoped marker answers for everything, which keeps every pre-existing
    marker working unchanged.

    `rule=None` means the caller has not said which rule is asking, and every
    marker matches. Passing the rule is what makes scoping effective, so a new
    check should always pass it.
    """
    candidates = list(range(lineno - 1, lineno + 1))
    if end_lineno is not None and end_lineno > lineno:
        candidates.extend(range(lineno + 1, end_lineno + 1))
    for candidate_lineno in candidates:
        if 1 <= candidate_lineno <= len(lines):
            m = ACCEPT_COMMENT_RE.search(lines[candidate_lineno - 1])
            if not m:
                continue
            scoped_to, reason = m.group(1), m.group(2)
            if scoped_to and rule and scoped_to != rule:
                continue
            return reason.strip() or 'no reason given'
    return None


def _type_checking_linenos(tree: ast.AST) -> set[int]:
    """Return line numbers inside any `if TYPE_CHECKING:` block."""
    result: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test_src = ast.unparse(node.test) if hasattr(ast, 'unparse') else ''
            if 'TYPE_CHECKING' in test_src:
                for child in ast.walk(node):
                    if hasattr(child, 'lineno'):
                        result.add(child.lineno)
    return result


def _all_py_files(src_root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in src_root.rglob('*.py'))


def _relpath(p: pathlib.Path, root: pathlib.Path) -> str:
    return str(p.relative_to(root))


def _accepted_lazy_imports(scope: pathlib.Path) -> set[tuple[str, str]]:
    agents = scope / 'AGENTS.md'
    if not agents.exists():
        return set()
    text = agents.read_text(encoding='utf-8')
    pairs: set[tuple[str, str]] = set()
    for line in text.splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < 2:
            continue
        m0 = re.findall(r'`([a-zA-Z_.][a-zA-Z0-9_.]*)`', cells[0])
        m1 = re.findall(r'`([a-zA-Z_.][a-zA-Z0-9_.]*)`', cells[1])
        for a in m0:
            for b in m1:
                pairs.add((a, b))
    return pairs


_LITERAL_DISPATCH_TYPE_NAMES = frozenset({'str'})  # extensible via helper below


# Directories outside `src/` that hold auditable Python. A project's scripts
# conventionally live in `bin/`, and until 2026-09-01 the sweep could not see
# them at all: `_packages_under` enumerates packages *under `src/`*, so a
# project whose scripts live in `bin/` got zero rows for them - accepted or
# otherwise - and a summary could record "`bin/` remains at zero unaccepted
# hits" as a measurement of nothing.
#
# The driver rebinds this when `--extra-root` is passed, so a check asking a
# corpus-wide question through `_audit_roots` measures the scope that was
# actually swept rather than the default one. It is a tuple, and rebound rather
# than mutated, so a check cannot change what a later check sees.
EXTRA_ROOT_NAMES: tuple[str, ...] = ('bin',)


def _packages_under(src: pathlib.Path) -> list[pathlib.Path]:
    """Every package directory directly under `src/`, sorted.

    Sorted because emission order is part of the output: `CHECKS`' order fixes
    the order within a package, and this fixes the order of the packages.

    Excludes caches and build artefacts, and any directory holding no `.py`
    file anywhere - not a package, and auditing it only slows the run.
    """
    if not src.is_dir():
        return []
    return sorted(
        p
        for p in src.iterdir()
        if p.is_dir() and not p.name.startswith('.') and p.name != '__pycache__' and not p.name.endswith(('.egg-info', '.dist-info')) and any(p.rglob('*.py'))
    )


def loose_src_modules(scope: pathlib.Path) -> list[pathlib.Path]:
    """Every `.py` file directly in `<scope>/src/`, outside any package, sorted.

    Empty when `src/` is absent. Pure apart from reading the directory.
    """
    src = scope / 'src'
    if not src.is_dir():
        return []
    return sorted(p for p in src.glob('*.py') if p.is_file())


def _extra_roots(scope: pathlib.Path, names: collections.abc.Sequence[str] | None = None) -> list[pathlib.Path]:
    """Every auditable root outside `src/`, in the order `names` gives them.

    `names` defaults to the current `EXTRA_ROOT_NAMES`, read at call time so the
    driver's `--extra-root` rebinding reaches the checks.

    A name that does not exist under `scope`, or that holds no `.py` file, is
    dropped: `bin/` is a default, not a requirement, and a project without one
    must not fail the sweep. The driver checks the roots it was given by name
    itself, so a typo on the command line is an error there rather than a
    silently empty pass here.
    """
    roots: list[pathlib.Path] = []
    for name in EXTRA_ROOT_NAMES if names is None else names:
        root = scope / name
        if root.is_dir() and any(root.rglob('*.py')):
            roots.append(root)
    return roots


def _audit_roots(scope: pathlib.Path) -> list[pathlib.Path]:
    """Every root the sweep passes over: the packages under `src/`, then the extras.

    This is the driver's pass list, and each entry becomes one check's
    `src_root`. A check that instead asks a corpus-wide question - "does
    anything read this name?" - wants every file rather than every root, and
    reads it from `_corpus_py_files`, which spans all of `src/` and the same
    extras. Asking that question of a single root answers about a fragment
    while reading like an answer about the whole.
    """
    return _packages_under(scope / 'src') + _extra_roots(scope)
