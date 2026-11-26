"""Tests for the checks of the `phase-section-doc-reference` rule."""

import collections.abc
import pathlib

import auditor.core
import auditor.sweep
import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

PHASE_SECTION = auditor.testing.load_check(__file__)


def test_a_phase_reference_in_a_docstring_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': '"""Runs the Phase 2 sweep."""\n'})
    hits = run_check(PHASE_SECTION, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('phase-section-doc-reference', 1)]
    assert "'Phase 2'" in hits[0]['variant']


def test_a_section_reference_in_a_comment_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': '# see Section 3.1 of the spec\nVALUE = 1\n'})
    assert len(run_check(PHASE_SECTION, root)) == 1


def test_a_phase_reference_in_running_code_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """The rule is about cross-references that rot, not about user-facing text."""
    root = project({'src/probe/mod.py': "LABEL = 'Phase 2'\n"})
    assert run_check(PHASE_SECTION, root) == []


def test_a_file_level_marker_excuses_the_whole_module(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            # auditme: accept phase-section this module renders the user-facing phase vocabulary
            \"\"\"Runs the Phase 2 sweep.\"\"\"

            # and Section 3.1 too
            VALUE = 1
            """
        }
    )
    assert run_check(PHASE_SECTION, root) == []
