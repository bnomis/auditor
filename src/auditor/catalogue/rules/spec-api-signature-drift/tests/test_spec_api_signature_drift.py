"""Tests for the `spec-api-signature-drift` rule, shipped from an audit's request (2026-09-01).

It asks a question about specs that nothing asked before.
"""

import collections.abc
import pathlib
import typing

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

SPEC_SIGNATURE = auditor.testing.load_check(__file__)


# auditme: accept[paired-sibling-helpers] a test helper kept inside its own rule directory, which must not import another
def rows(hits: list[dict[str, typing.Any]], rule: str) -> list[dict[str, typing.Any]]:
    return [hit for hit in hits if hit['rule'] == rule]


# --------------------------------------------------------------------------
# check_spec_api_signature_drift - the shape it fires on
# --------------------------------------------------------------------------


SPEC_WITH_API = """
# Extractor

## API

```python
def extract_directory(settings: AppSettings) -> ExtractBatch:
    ...
```
"""


def spec_project(build: Builder, spec_body: str, source: str) -> pathlib.Path:
    return build({'agents/specs/probe/spec.md': spec_body, 'src/probe/mod.py': source})


def test_a_parameter_added_in_the_source_fires(project: Builder, run_check: Runner) -> None:
    """The dominant shape in practice: a fix adds an optional parameter and the
    spec's API block is not updated in the same commit."""
    root = spec_project(
        project,
        """
        ## API

        ```python
        def extract_directory(settings: AppSettings) -> ExtractBatch:
        ```
        """,
        'def extract_directory(settings, output_path=None):\n    return None\n',
    )
    hits = rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift')
    assert len(hits) == 1
    assert hits[0]['path'] == 'agents/specs/probe/spec.md'
    assert 'extract_directory' in hits[0]['variant']
    assert 'output_path=' in hits[0]['variant']
    assert 'src/probe/mod.py:1' in hits[0]['evidence']
    assert hits[0]['related'] == ['src/probe/mod.py']


def test_a_parameter_moving_across_the_keyword_only_marker_fires(project: Builder, run_check: Runner) -> None:
    root = spec_project(
        project,
        """
        ## API

        ```python
        def write_worklist(path, records, cache=None) -> None:
        ```
        """,
        'def write_worklist(path, records, *, cache=None):\n    return None\n',
    )
    hits = rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift')
    assert len(hits) == 1


def test_a_matching_signature_does_not_fire(project: Builder, run_check: Runner) -> None:
    root = spec_project(
        project,
        """
        ## API

        ```python
        def extract_directory(settings: AppSettings, output_path: pathlib.Path | None = None) -> ExtractBatch:
        ```
        """,
        'def extract_directory(settings, output_path=None):\n    return None\n',
    )
    assert rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift') == []


# --------------------------------------------------------------------------
# check_spec_api_signature_drift - carve-outs that must not fire
# --------------------------------------------------------------------------


def test_a_differing_type_annotation_alone_does_not_fire(project: Builder, run_check: Runner) -> None:
    """A spec writes `AppSettings` where the source writes the dotted
    path. Treating that as drift would bury every real finding."""
    root = spec_project(
        project,
        """
        ## API

        ```python
        def build_roster(settings: AppSettings, pass_name: PassName) -> Roster:
        ```
        """,
        'def build_roster(settings: applib.settings.AppSettings, pass_name: applib.assessor.models.PassName) -> Roster:\n    return None\n',
    )
    assert rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift') == []


def test_a_name_with_no_module_level_definition_does_not_fire(project: Builder, run_check: Runner) -> None:
    """A Protocol plus its implementations, and `__init__` everywhere,
    resolve to methods only. A spec block showing such a contract is not
    checked, rather than checked against an arbitrary implementation."""
    root = project(
        {
            'agents/specs/probe/spec.md': """
        ## API

        ```python
        def resolve(self, item: CSLItem) -> str | None:
        ```
        """,
            'src/probe/base.py': 'class Resolver:\n    def resolve(self, item, config, session):\n        return None\n',
            'src/probe/doi.py': 'class DoiResolver:\n    def resolve(self, item, config, session):\n        return None\n',
        }
    )
    assert rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift') == []


def test_a_method_in_a_spec_class_block_does_not_fire(project: Builder, run_check: Runner) -> None:
    """A method written inside a spec's `class` block is not compared with a
    module-level function that happens to share its name: `corpus_definitions`
    holds module-level definitions only, so the two are unrelated."""
    root = project(
        {
            'agents/specs/probe/spec.md': """
        ## API

        ```python
        class Store:
            @classmethod
            def load(cls, path: pathlib.Path, *, strict: bool = True) -> Store:
        ```
        """,
            'src/probe/store.py': 'class Store:\n    @classmethod\n    def load(cls, path, *, strict=True):\n        return None\n',
            'src/probe/other.py': 'def load(path):\n    return None\n',
        }
    )
    assert rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift') == []


def test_a_module_level_def_after_a_spec_class_block_still_fires(project: Builder, run_check: Runner) -> None:
    """Skipping methods ends with the class block: a `def` back at the class
    line's indent is module-level again and is checked."""
    root = spec_project(
        project,
        """
        ## API

        ```python
        class Batch:
            def size(self) -> int:

        def extract_directory(settings: AppSettings) -> ExtractBatch:
        ```
        """,
        'def extract_directory(settings, output_path=None):\n    return None\n',
    )
    hits = rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift')
    assert len(hits) == 1
    assert 'extract_directory' in hits[0]['variant']


def test_an_elided_signature_does_not_fire(project: Builder, run_check: Runner) -> None:
    """`def f(...)` is a spec showing a contract, not a signature."""
    root = spec_project(
        project,
        """
        ## API

        ```python
        def extract_directory(...) -> ExtractBatch:
        ```
        """,
        'def extract_directory(settings, output_path=None):\n    return None\n',
    )
    assert rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift') == []


def test_a_def_outside_an_api_heading_does_not_fire(project: Builder, run_check: Runner) -> None:
    """A worked example under `## Implementation` is illustrative, and the
    next heading ends the API section."""
    root = spec_project(
        project,
        """
        ## API

        ```python
        def extract_directory(settings, output_path=None) -> ExtractBatch:
        ```

        ## Implementation

        ```python
        def extract_directory(settings) -> ExtractBatch:
        ```
        """,
        'def extract_directory(settings, output_path=None):\n    return None\n',
    )
    assert rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift') == []


def test_a_def_named_only_in_prose_does_not_fire(project: Builder, run_check: Runner) -> None:
    root = spec_project(
        project,
        """
        ## API

        The stage's entry point is `def extract_directory(settings) -> ExtractBatch:`,
        which the command calls.
        """,
        'def extract_directory(settings, output_path=None):\n    return None\n',
    )
    assert rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift') == []


def test_audit_reviews_and_task_lists_are_not_read(project: Builder, run_check: Runner) -> None:
    """A review records what was true on the day it ran. Flagging its
    quoted signatures would falsify the record."""
    stale = """
    ## API

    ```python
    def extract_directory(settings) -> ExtractBatch:
    ```
    """
    root = project(
        {
            'agents/audit-reviews/review-1.md': stale,
            'agents/tasks/audit-reviews/tasks-1.md': stale,
            'src/probe/mod.py': 'def extract_directory(settings, output_path=None):\n    return None\n',
        }
    )
    assert rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift') == []


def test_a_spec_inside_a_hidden_directory_is_not_read(project: Builder, run_check: Runner) -> None:
    """A Claude Code worktree is a second checkout under `.claude/worktrees/`.
    Its specs belong to another branch, so reading them doubled every hit."""
    stale = """
    ## API

    ```python
    def extract_directory(settings) -> ExtractBatch:
    ```
    """
    root = project(
        {
            '.claude/worktrees/wt/agents/specs/probe/spec.md': stale,
            'src/probe/mod.py': 'def extract_directory(settings, output_path=None):\n    return None\n',
        }
    )
    assert rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift') == []


def test_a_scoped_accept_marker_accepts_the_drift(project: Builder, run_check: Runner) -> None:
    root = spec_project(
        project,
        """
        ## API

        ```python
        # auditme: accept[spec-api-signature-drift] the extra parameter is internal, deliberately not in the contract
        def extract_directory(settings: AppSettings) -> ExtractBatch:
        ```
        """,
        'def extract_directory(settings, output_path=None):\n    return None\n',
    )
    hits = rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift')
    assert len(hits) == 1
    assert hits[0]['accepted'] is True
    assert 'internal' in hits[0]['accepted_reason']


def test_a_marker_scoped_to_another_rule_does_not_accept_the_drift(project: Builder, run_check: Runner) -> None:
    root = spec_project(
        project,
        """
        ## API

        ```python
        # auditme: accept[literal-duplication] answers a different question
        def extract_directory(settings: AppSettings) -> ExtractBatch:
        ```
        """,
        'def extract_directory(settings, output_path=None):\n    return None\n',
    )
    hits = rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift')
    assert len(hits) == 1
    assert hits[0]['accepted'] is False


def test_two_module_level_defs_sharing_a_name_do_not_fire(project: Builder, run_check: Runner) -> None:
    """Genuine ambiguity: the check cannot know which one the spec means."""
    root = project(
        {
            'agents/specs/probe/spec.md': """
        ## API

        ```python
        def resolve_path(settings) -> pathlib.Path:
        ```
        """,
            'src/probe/one.py': 'def resolve_path(settings, root=None):\n    return None\n',
            'src/probe/two.py': 'def resolve_path(settings, base=None):\n    return None\n',
        }
    )
    assert rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift') == []


def test_a_test_double_method_does_not_make_a_library_name_ambiguous(project: Builder, run_check: Runner) -> None:
    """The bug this check's own first run against a real project exposed.

    One project's `write_worklist` is a module-level library function AND the name
    of a method on a test double. Resolving per-root reported the spec as
    drifting from whichever one that pass happened to see - two rows, two
    different "source says" clauses, for one spec line. Resolving corpus-wide
    over module-level defs only gives one answer, the right one.
    """
    root = project(
        {
            'agents/specs/probe/spec.md': """
        ## API

        ```python
        def write_worklist(path, records) -> None:
        ```
        """,
            'src/probe/worklist.py': 'def write_worklist(path, records, *, cache=None):\n    return None\n',
            'src/tests/probe/test_double.py': """
        class FakeSink:
            def write_worklist(self, path, key, *, verdict='include'):
                return None
        """,
        }
    )
    hits = rows(run_check(SPEC_SIGNATURE, root), 'spec-api-signature-drift')
    assert len(hits) == 1
    assert 'cache=' in hits[0]['variant']
    assert 'verdict=' not in hits[0]['variant']


def test_the_result_is_the_same_whichever_root_the_pass_is_over(project: Builder, run_check: Runner) -> None:
    """Corpus-wide resolution makes the check root-independent, so the
    driver's duplicate suppressor collapses the passes to one row."""
    files = {
        'agents/specs/probe/spec.md': """
        ## API

        ```python
        def extract_directory(settings) -> ExtractBatch:
        ```
        """,
        'src/probe/mod.py': 'def extract_directory(settings, output_path=None):\n    return None\n',
        'src/tests/probe/test_mod.py': 'def test_it():\n    return None\n',
    }
    root = project(files)
    over_library = run_check(SPEC_SIGNATURE, root, package='probe')
    over_tests = run_check(SPEC_SIGNATURE, root, src_root='src/tests')
    assert rows(over_library, 'spec-api-signature-drift') == rows(over_tests, 'spec-api-signature-drift')
    assert len(rows(over_library, 'spec-api-signature-drift')) == 1
