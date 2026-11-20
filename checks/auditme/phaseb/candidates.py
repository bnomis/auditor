"""The Phase B data model and the registry of per-question candidate listers."""

import collections.abc
import dataclasses
import pathlib
import typing

from auditme.phaseb.errors import PhaseBError


@dataclasses.dataclass(frozen=True)
class Candidate:
    """One site a question applies to."""

    question: str  # e.g. 'A4'
    id: str  # '<repo-relative path>::<qualname>'
    path: str
    start: int
    end: int
    payload: dict[str, typing.Any]  # question-specific; A4: raises, callees, unresolved
    hash: str  # sha256 hex over the candidate's source and its callees' source


@dataclasses.dataclass(frozen=True)
class Verdict:
    """One reviewer's ruling on one candidate."""

    question: str
    id: str
    hash: str  # the candidate hash it was judged against
    brief_version: int
    findings: dict[str, list[str]]  # A4: {'missing': [...], 'extra': [...]}
    reason: str
    judged: str  # ISO date
    dismissed: str | None = None  # 'YYYY-MM-DD: <reason>' once the operator dismisses it

    @property
    def flagged(self) -> bool:
        """True when any findings list is non-empty and the verdict is not dismissed."""
        return self.dismissed is None and any(self.findings.values())


Lister = collections.abc.Callable[[pathlib.Path], list[Candidate]]

REGISTRY: dict[str, tuple[Lister, pathlib.Path]] = {}


def register_question(question: str, brief: pathlib.Path) -> collections.abc.Callable[[Lister], Lister]:
    """Register a candidate lister for a Phase B question, with its brief."""

    def decorate(lister: Lister) -> Lister:
        REGISTRY[question] = (lister, brief)
        return lister

    return decorate


def registered(question: str) -> tuple[Lister, pathlib.Path]:
    """Return a question's lister and brief path.

    Raises:
        PhaseBError: question has no registered lister.
    """
    try:
        return REGISTRY[question]
    except KeyError:
        raise PhaseBError(f'no Phase B lister is registered for question {question!r}; known: {sorted(REGISTRY)}') from None


def question_brief(question: str) -> pathlib.Path:
    """Return the path of a question's brief.

    Raises:
        PhaseBError: question has no registered lister.
    """
    return registered(question)[1]


def list_candidates(question: str, root: pathlib.Path) -> list[Candidate]:
    """List every candidate for question under root, sorted by id.

    Raises:
        PhaseBError: question has no registered lister.
    """
    lister, _ = registered(question)
    return sorted(lister(root), key=lambda candidate: candidate.id)
