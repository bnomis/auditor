"""The Phase B data model and the registry of per-question candidate listers."""

import collections.abc
import dataclasses
import os
import pathlib
import re
import typing

import auditor.api.base
import auditor.api.candidates
import auditor.registry
import auditor.rulesrepo


@dataclasses.dataclass(frozen=True)
class Verdict:
    """One reviewer's ruling on one candidate."""

    question: str
    id: str
    hash: str  # the candidate hash it was judged against
    brief_version: int
    findings: dict[str, list[str]]  # one list per registered kind
    reason: str
    judged: str  # ISO date
    dismissed: str | None = None  # 'YYYY-MM-DD: <reason>' once the operator dismisses it

    @property
    def flagged(self) -> bool:
        """True when any findings list is non-empty and the verdict is not dismissed."""
        return self.dismissed is None and any(self.findings.values())


Lister = collections.abc.Callable[[pathlib.Path], list[auditor.api.candidates.Candidate]]

DEFAULT_BATCH_SIZE = 48

# auditme: accept[mutable-module-level-exported] filled by `@register_question` at import, and patched by a test
REGISTRY: dict[str, tuple[Lister, pathlib.Path, int]] = {}
# auditme: accept[mutable-module-level-exported] filled by `@register_question` at import beside `REGISTRY`, and patched by a test
KINDS: dict[str, tuple[str, ...]] = {}
# auditme: accept[mutable-module-level-exported] filled by `@register_question(takes_depth=True)` at import beside `REGISTRY`
TAKES_DEPTH: set[str] = set()


def registered_questions() -> list[str]:
    """The questions a lister is registered for, sorted."""
    return sorted(REGISTRY)


def depth_questions() -> list[str]:
    """The questions whose lister takes a `--depth`, sorted."""
    return sorted(TAKES_DEPTH)


def register_question(
    question: str,
    brief: pathlib.Path,
    kinds: tuple[str, ...],
    batch_size: int = DEFAULT_BATCH_SIZE,
    takes_depth: bool = False,
) -> collections.abc.Callable[[Lister], Lister]:
    """Register a candidate lister for a Phase B question, with its brief, finding kinds and batch size.

    The kinds are the keys of the `findings` object in the question's result
    line, in the order the brief names them. The batch size is how many
    candidates one reviewer judges when `phaseb.py plan` is not given
    `--batch-size`; a question whose candidates are costly to judge registers
    a smaller one. A question whose lister follows callees registers
    `takes_depth`, and only then is a depth handed to its lister.

    Raises:
        PhaseBError: kinds is empty or names a kind twice.
    """
    if not kinds:
        raise auditor.api.base.PhaseBError(f'question {question!r} registers no finding kinds')
    if len(set(kinds)) != len(kinds):
        raise auditor.api.base.PhaseBError(f'question {question!r} registers a finding kind twice: {list(kinds)}')

    def decorate(lister: Lister) -> Lister:
        REGISTRY[question] = (lister, brief, batch_size)
        KINDS[question] = tuple(kinds)
        if takes_depth:
            TAKES_DEPTH.add(question)
        else:
            TAKES_DEPTH.discard(question)
        return lister

    return decorate


def repository_lister(rule: auditor.rulesrepo.Rule) -> Lister:
    """A lister that imports the rule's `lister.py` when it first runs, so an import error is raised where the candidates are asked for."""

    def lister(scope: pathlib.Path) -> list[auditor.api.candidates.Candidate]:
        return list(auditor.rulesrepo.import_entry(rule, 'lister.py').list_candidates(scope))

    return lister


def repository_depth_lister(rule: auditor.rulesrepo.Rule) -> Lister:
    """Like `repository_lister`, for a question whose `rule.toml` sets `takes-depth`: the depth is handed on."""

    def lister(scope: pathlib.Path, depth: int | None = None) -> list[auditor.api.candidates.Candidate]:
        return list(auditor.rulesrepo.import_entry(rule, 'lister.py').list_candidates(scope, auditor.api.candidates.DEFAULT_DEPTH if depth is None else depth))

    return lister


def register_repository(repo: auditor.rulesrepo.RulesRepo) -> None:
    """Replace the registrations with the repository's questions that have a lister.

    `kinds`, `batch-size` and `takes-depth` come from `rule.toml` and the brief
    is the rule's `brief.md`.

    Raises:
        PhaseBError: a question registers no kinds or names a kind twice.
    """
    REGISTRY.clear()
    KINDS.clear()
    TAKES_DEPTH.clear()
    for rule in repo.rules:
        if rule.kind != 'question' or not (rule.path / 'lister.py').is_file():
            continue
        takes_depth = bool(rule.meta.get('takes-depth', False))
        register_question(
            str(rule.meta['id']),
            rule.path / 'brief.md',
            tuple(str(kind) for kind in typing.cast('list[str]', rule.meta['kinds'])),
            batch_size=int(typing.cast('int', rule.meta.get('batch-size', DEFAULT_BATCH_SIZE))),
            takes_depth=takes_depth,
        )(repository_depth_lister(rule) if takes_depth else repository_lister(rule))


def use_rules_repository() -> None:
    """When `$AUDITOR_RULES_PATH` is set, replace the registrations with the repository's questions that have a lister.

    Unset, the registrations stay: the catalogue's questions, until the built-in registry is removed.

    Raises:
        RulesRepoError: the variable is set but empty, or the repository is invalid.
        PhaseBError: a question registers no kinds or names a kind twice.
    """
    if auditor.rulesrepo.RULES_PATH_VARIABLE not in os.environ:
        return
    register_repository(auditor.rulesrepo.load(auditor.rulesrepo.rules_root()))


def registered(question: str) -> tuple[Lister, pathlib.Path, int]:
    """Return a question's lister, brief path and batch size.

    Raises:
        PhaseBError: question has no registered lister.
    """
    try:
        return REGISTRY[question]
    except KeyError:
        raise auditor.api.base.PhaseBError(f'no Phase B lister is registered for question {question!r}; known: {sorted(REGISTRY)}') from None


def question_brief(question: str) -> pathlib.Path:
    """Return the path of a question's brief.

    Raises:
        PhaseBError: question has no registered lister.
    """
    return registered(question)[1]


def question_kinds(question: str) -> tuple[str, ...]:
    """Return the finding kinds registered for a question.

    Raises:
        PhaseBError: question has no registered lister.
    """
    registered(question)  # auditme: accept[discarded-tuple-return] called only for the PhaseBError it raises on an unknown question
    return KINDS[question]


def question_batch_size(question: str) -> int:
    """Return the number of candidates one reviewer judges for a question.

    Raises:
        PhaseBError: question has no registered lister.
    """
    return registered(question)[2]


def list_candidates(question: str, root: pathlib.Path, depth: int | None = None) -> list[auditor.api.candidates.Candidate]:
    """List every candidate for question under root, sorted by id.

    A depth is handed to a lister registered as taking one, which follows
    callees that far; without one the lister uses its own default.

    Raises:
        PhaseBError: question has no registered lister, or a depth is given for
            a question whose lister takes none.
        RootsError: `[tool.auditme]` in `pyproject.toml` declares an invalid root.
    """
    lister, _, _ = registered(question)
    if depth is None:
        found = lister(root)
    elif question in TAKES_DEPTH:
        found = lister(root, depth)  # type: ignore[call-arg]
    else:
        raise auditor.api.base.PhaseBError(f'question {question!r} takes no depth; only {sorted(TAKES_DEPTH)} do')
    return sorted(found, key=lambda candidate: candidate.id)


BRIEF_VERSION_LINE = re.compile(r'^\*\*Brief version:\*\*\s*(\d+)\s*$', re.MULTILINE)


def brief_version(brief: pathlib.Path) -> int:
    """Return the version a brief declares on its `**Brief version:** N` line.

    Raises:
        PhaseBError: the brief cannot be read or has not exactly one version line.
    """
    try:
        text = brief.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as error:
        raise auditor.api.base.PhaseBError(f'cannot read brief {brief}') from error
    found = BRIEF_VERSION_LINE.findall(text)
    if len(found) != 1 or int(found[0]) < 1:
        raise auditor.api.base.PhaseBError(f'brief {brief} must have exactly one `**Brief version:** N` line with N a positive integer')
    return int(found[0])


register_repository(auditor.registry.CATALOGUE)  # transitional: the questions of the catalogue, until the built-in registry is removed
