"""Tests for the predicates that compare code across files."""

import collections.abc
import pathlib

import auditor.rules.duplication

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

LITERAL = auditor.rules.duplication.check_literal_duplication
SIBLING_HELPERS = auditor.rules.duplication.check_paired_sibling_helpers
SIDE_EFFECT = auditor.rules.duplication.check_duplicate_side_effect_per_target
REDUNDANT_SINK = auditor.rules.duplication.check_redundant_sink_caller_plus_callee
CALL_SEQUENCE = auditor.rules.duplication.check_duplicate_call_sequence
RECOMPILE = auditor.rules.duplication.check_recompile_duplication


# --------------------------------------------------------------------------
# check_literal_duplication
# --------------------------------------------------------------------------


def test_the_same_string_list_in_two_files_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': "NAMES = ['alpha', 'beta']\n",
            'src/probe/b.py': "LABELS = ['alpha', 'beta']\n",
        }
    )
    hits = run_check(LITERAL, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [
        ('literal-duplication', 'src/probe/a.py'),
        ('literal-duplication', 'src/probe/b.py'),
    ]
    assert [hit['related'] for hit in hits] == [['src/probe/b.py'], ['src/probe/a.py']]


def test_set_membership_is_compared_without_order(project: Builder, run_check: Runner) -> None:
    """A frozenset is unordered, so two spellings of the same set collide."""
    root = project(
        {
            'src/probe/a.py': "NAMES = frozenset({'alpha', 'beta'})\n",
            'src/probe/b.py': "LABELS = frozenset({'beta', 'alpha'})\n",
        }
    )
    assert len(run_check(LITERAL, root)) == 2


def test_a_reordered_list_is_a_different_literal(project: Builder, run_check: Runner) -> None:
    """A list is ordered, so the order is part of what makes it the same."""
    root = project(
        {
            'src/probe/a.py': "NAMES = ['alpha', 'beta']\n",
            'src/probe/b.py': "LABELS = ['beta', 'alpha']\n",
        }
    )
    assert run_check(LITERAL, root) == []


def test_a_literal_that_appears_once_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/a.py': "NAMES = ['alpha', 'beta']\n"})
    assert run_check(LITERAL, root) == []


def test_a_one_member_literal_in_a_test_file_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': "NAMES = ['alpha']\n",
            'src/probe/test_b.py': "def test_x() -> None:\n    assert sorted(['alpha']) == ['alpha']\n    names = ['alpha']\n",
        }
    )
    assert run_check(LITERAL, root) == []


def test_a_literal_inside_an_assert_or_pytest_param_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': "NAMES = ['alpha', 'beta']\n",
            'src/probe/test_b.py': (
                'import pytest\n'
                "CASES = [pytest.param(['alpha', 'beta'], id='x')]\n"
                'def test_x() -> None:\n'
                "    assert sorted(['beta', 'alpha']) == ['alpha', 'beta']\n"
            ),
        }
    )
    assert run_check(LITERAL, root) == []


def test_the_same_one_member_literal_in_source_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': "NAMES = ['alpha']\n",
            'src/probe/b.py': "LABELS = ['alpha']\n",
        }
    )
    assert len(run_check(LITERAL, root)) == 2


def test_a_repeated_multi_member_literal_in_test_set_up_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/test_a.py': "def test_a() -> None:\n    names = ['alpha', 'beta']\n",
            'src/probe/test_b.py': "def test_b() -> None:\n    names = ['alpha', 'beta']\n",
        }
    )
    assert len(run_check(LITERAL, root)) == 2


def test_a_list_of_non_strings_is_not_compared(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/a.py': 'SIZES = [1, 2]\n', 'src/probe/b.py': 'LIMITS = [1, 2]\n'})
    assert run_check(LITERAL, root) == []


# --------------------------------------------------------------------------
# check_paired_sibling_helpers
# --------------------------------------------------------------------------


SHARED_BODY = """
def {name}(path: str) -> str:
    resolved = path.strip().lower()
    return resolved + '-a-long-enough-suffix'
"""


def test_two_functions_with_the_same_body_in_different_files_are_hits(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': SHARED_BODY.format(name='load_a'),
            'src/probe/b.py': SHARED_BODY.format(name='load_b'),
        }
    )
    hits = run_check(SIBLING_HELPERS, root)
    assert {hit['path'] for hit in hits} == {'src/probe/a.py', 'src/probe/b.py'}
    assert all(hit['rule'] == 'paired-sibling-helpers' for hit in hits)
    assert {hit['path']: hit['related'] for hit in hits} == {'src/probe/a.py': ['src/probe/b.py'], 'src/probe/b.py': ['src/probe/a.py']}


def test_two_copies_in_one_file_are_not_a_cross_file_pair(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/a.py': SHARED_BODY.format(name='load_a') + SHARED_BODY.format(name='load_b')})
    assert run_check(SIBLING_HELPERS, root) == []


def test_a_short_body_is_below_the_threshold(project: Builder, run_check: Runner) -> None:
    """Two-line trivia matches everywhere and would drown the real finding."""
    root = project(
        {
            'src/probe/a.py': 'def load_a() -> int:\n    return 1\n',
            'src/probe/b.py': 'def load_b() -> int:\n    return 1\n',
        }
    )
    assert run_check(SIBLING_HELPERS, root) == []


# --------------------------------------------------------------------------
# check_duplicate_side_effect_per_target
# --------------------------------------------------------------------------


def test_two_methods_flushing_the_same_attribute_are_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.writer


            class Pipeline:
                def tokenize(self, splits: list[str]) -> None:
                    probe.writer.flush_config(self.run_dir)

                def train(self, splits: list[str]) -> None:
                    probe.writer.flush_config(self.run_dir)
            """
        }
    )
    hits = run_check(SIDE_EFFECT, root)
    assert [hit['rule'] for hit in hits] == ['duplicate-side-effect-per-target']
    assert 'tokenize, train' in hits[0]['variant']


def test_one_method_calling_the_sink_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.writer


            class Pipeline:
                def tokenize(self, splits: list[str]) -> None:
                    probe.writer.flush_config(self.run_dir)

                def train(self, splits: list[str]) -> None:
                    return None
            """
        }
    )
    assert run_check(SIDE_EFFECT, root) == []


def test_a_call_with_no_self_attribute_argument_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """Without a shared target there is no shared thing being overwritten."""
    root = project(
        {
            'src/probe/mod.py': """
            import probe.writer


            class Pipeline:
                def tokenize(self, splits: list[str]) -> None:
                    probe.writer.flush_config(splits)

                def train(self, splits: list[str]) -> None:
                    probe.writer.flush_config(splits)
            """
        }
    )
    assert run_check(SIDE_EFFECT, root) == []


def test_methods_named_for_mutation_are_out_of_scope(project: Builder, run_check: Runner) -> None:
    """`save_*` and `flush_*` are expected to write; that is what they are for."""
    root = project(
        {
            'src/probe/mod.py': """
            import probe.writer


            class Pipeline:
                def save_early(self) -> None:
                    probe.writer.flush_config(self.run_dir)

                def save_late(self) -> None:
                    probe.writer.flush_config(self.run_dir)
            """
        }
    )
    assert run_check(SIDE_EFFECT, root) == []


# --------------------------------------------------------------------------
# check_redundant_sink_caller_plus_callee
# --------------------------------------------------------------------------


REDUNDANT_TREE = {
    'src/probe/cli.py': """
    import probe.pipeline
    import probe.writer


    def run_evaluate(config: dict, run_dir: str) -> None:
        probe.writer.flush_config(config, run_dir)
        probe.pipeline.tokenize(config, run_dir)
    """,
    'src/probe/pipeline.py': """
    import probe.writer


    def tokenize(config: dict, run_dir: str) -> None:
        probe.writer.flush_config(config, run_dir)
    """,
}


def test_a_caller_that_repeats_its_helper_s_sink_call_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(REDUNDANT_TREE)
    hits = run_check(REDUNDANT_SINK, root)
    assert [(hit['rule'], hit['path'], hit['line']) for hit in hits] == [('redundant-sink-caller-plus-callee', 'src/probe/cli.py', 6)]


def test_a_sink_call_after_the_helper_is_not_redundant(project: Builder, run_check: Runner) -> None:
    """Only forward-direction redundancy counts: a later write may be
    deliberately re-flushing state the helper changed."""
    root = project(
        {
            **REDUNDANT_TREE,
            'src/probe/cli.py': """
            import probe.pipeline
            import probe.writer


            def run_evaluate(config: dict, run_dir: str) -> None:
                probe.pipeline.tokenize(config, run_dir)
                probe.writer.flush_config(config, run_dir)
            """,
        }
    )
    assert run_check(REDUNDANT_SINK, root) == []


def test_different_arguments_are_not_redundant(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            **REDUNDANT_TREE,
            'src/probe/cli.py': """
            import probe.pipeline
            import probe.writer


            def run_evaluate(config: dict, run_dir: str, report: str) -> None:
                probe.writer.flush_config(report)
                probe.pipeline.tokenize(config, run_dir)
            """,
        }
    )
    assert run_check(REDUNDANT_SINK, root) == []


def test_a_sink_call_in_a_nested_def_is_not_the_helper_s_own(project: Builder, run_check: Runner) -> None:
    """The helper's sink call sits inside a def nested in it, which may never run."""
    root = project(
        {
            **REDUNDANT_TREE,
            'src/probe/pipeline.py': """
            import probe.writer


            def tokenize(config: dict, run_dir: str) -> None:
                def later() -> None:
                    probe.writer.flush_config(config, run_dir)
            """,
        }
    )
    assert run_check(REDUNDANT_SINK, root) == []


def test_a_helper_call_in_a_nested_def_is_not_the_caller_s_own(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            **REDUNDANT_TREE,
            'src/probe/cli.py': """
            import probe.pipeline
            import probe.writer


            def run_evaluate(config: dict, run_dir: str) -> None:
                probe.writer.flush_config(config, run_dir)

                def later() -> None:
                    probe.pipeline.tokenize(config, run_dir)
            """,
        }
    )
    assert run_check(REDUNDANT_SINK, root) == []


def test_self_recursion_is_not_a_helper_call(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/cli.py': """
            import probe.writer


            def run_evaluate(config: dict, run_dir: str, depth: int) -> None:
                probe.writer.flush_config(config, run_dir)
                if depth:
                    run_evaluate(config, run_dir, depth - 1)
            """,
        }
    )
    assert run_check(REDUNDANT_SINK, root) == []


def test_a_helper_is_resolved_by_its_qualified_name(project: Builder, run_check: Runner) -> None:
    """`other.tokenize` is not `probe.pipeline.tokenize`, though the short names match."""
    root = project(
        {
            **REDUNDANT_TREE,
            'src/probe/cli.py': """
            import other
            import probe.writer


            def run_evaluate(config: dict, run_dir: str) -> None:
                probe.writer.flush_config(config, run_dir)
                other.tokenize(config, run_dir)
            """,
        }
    )
    assert run_check(REDUNDANT_SINK, root) == []


def test_a_bare_helper_name_defined_in_two_modules_matches_neither(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            **REDUNDANT_TREE,
            'src/probe/extra.py': """
            import probe.writer


            def tokenize(config: dict, run_dir: str) -> None:
                probe.writer.flush_config(config, run_dir)
            """,
            'src/probe/cli.py': """
            from probe.pipeline import tokenize
            import probe.writer


            def run_evaluate(config: dict, run_dir: str) -> None:
                probe.writer.flush_config(config, run_dir)
                tokenize(config, run_dir)
            """,
        }
    )
    assert run_check(REDUNDANT_SINK, root) == []


def test_different_keyword_values_are_not_redundant(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/pipeline.py': """
            import probe.writer


            def tokenize(config: dict, run_dir: str) -> None:
                probe.writer.flush_config(config, path=run_dir)
            """,
            'src/probe/cli.py': """
            import probe.pipeline
            import probe.writer


            def run_evaluate(config: dict, run_dir: str, other_dir: str) -> None:
                probe.writer.flush_config(config, path=other_dir)
                probe.pipeline.tokenize(config, run_dir)
            """,
        }
    )
    assert run_check(REDUNDANT_SINK, root) == []


def test_the_same_keyword_values_are_still_redundant(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/pipeline.py': """
            import probe.writer


            def tokenize(config: dict, run_dir: str) -> None:
                probe.writer.flush_config(config, path=run_dir)
            """,
            'src/probe/cli.py': """
            import probe.pipeline
            import probe.writer


            def run_evaluate(config: dict, run_dir: str) -> None:
                probe.writer.flush_config(config, path=run_dir)
                probe.pipeline.tokenize(config, run_dir)
            """,
        }
    )
    assert len(run_check(REDUNDANT_SINK, root)) == 1


# --------------------------------------------------------------------------
# check_duplicate_call_sequence
# --------------------------------------------------------------------------


CALL_CHAIN = """
import probe.helper


def {name}(value: str) -> str:
    probe.helper.alpha(value)
    probe.helper.bravo(value)
    probe.helper.charlie(value)
    probe.helper.delta(value)
    probe.helper.echo(value)
    probe.helper.foxtrot(value)
    probe.helper.golf(value)
    return value
"""


def test_two_functions_with_the_same_call_skeleton_are_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': CALL_CHAIN.format(name='run_first'),
            'src/probe/b.py': CALL_CHAIN.format(name='run_second'),
        }
    )
    hits = run_check(CALL_SEQUENCE, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('duplicate-call-sequence', 'src/probe/a.py')]
    assert 'run_second' in hits[0]['variant']
    assert hits[0]['related'] == ['src/probe/b.py']


PLUMBING_CHAIN = """
import probe.helper
import sqlite3


def {name}(value: str) -> str:
    probe.helper.alpha(value)
    conn = sqlite3.connect(value)
    conn.execute(value)
    conn.fetchall(value)
    conn.close(value)
    probe.helper.{tail}(value)
    return value
"""


def test_a_sequence_that_is_mostly_connection_plumbing_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """connect/execute/close describe the framework, not the shape of the code.

    Two unrelated database tests both open a connection, run a statement and
    close it. Counting those made them look like copies of each other, which
    matters most in a codebase that forbids `from X import Y`: every call is
    dotted there, so nothing filtered them out.
    """
    root = project(
        {
            'src/probe/a.py': PLUMBING_CHAIN.format(name='run_first', tail='bravo'),
            'src/probe/b.py': PLUMBING_CHAIN.format(name='run_second', tail='charlie'),
        }
    )
    assert run_check(CALL_SEQUENCE, root) == []


def test_a_short_call_sequence_is_below_the_threshold(project: Builder, run_check: Runner) -> None:
    short = 'import probe.helper\n\n\ndef {name}(value: str) -> str:\n    probe.helper.alpha(value)\n    probe.helper.bravo(value)\n    return value\n'
    root = project({'src/probe/a.py': short.format(name='run_first'), 'src/probe/b.py': short.format(name='run_second')})
    assert run_check(CALL_SEQUENCE, root) == []


def test_two_copies_in_one_file_are_treated_as_a_family(project: Builder, run_check: Runner) -> None:
    """Within-file repetition is usually a deliberate family of similar
    functions; cross-file repetition is the architectural smell."""
    root = project({'src/probe/a.py': CALL_CHAIN.format(name='run_first') + CALL_CHAIN.format(name='run_second')})
    assert run_check(CALL_SEQUENCE, root) == []


# --------------------------------------------------------------------------
# check_recompile_duplication
# --------------------------------------------------------------------------


def test_the_same_regex_constant_name_in_two_files_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': "import re\n\nTOKEN_RE = re.compile(r'^[a-z]+$')\n",
            'src/probe/b.py': "import re\n\nTOKEN_RE = re.compile(r'^[a-z]+$')\n",
        }
    )
    hits = run_check(RECOMPILE, root)
    assert {hit['path'] for hit in hits} == {'src/probe/a.py', 'src/probe/b.py'}
    assert all(hit['rule'] == 'recompile-duplication' for hit in hits)
    assert {hit['path']: hit['related'] for hit in hits} == {'src/probe/a.py': ['src/probe/b.py'], 'src/probe/b.py': ['src/probe/a.py']}


def test_a_differently_named_regex_constant_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': "import re\n\nTOKEN_RE = re.compile(r'^[a-z]+$')\n",
            'src/probe/b.py': "import re\n\nWORD_RE = re.compile(r'^[a-z]+$')\n",
        }
    )
    assert run_check(RECOMPILE, root) == []


def test_a_regex_constant_defined_once_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/a.py': "import re\n\nTOKEN_RE = re.compile(r'^[a-z]+$')\n"})
    assert run_check(RECOMPILE, root) == []


def test_a_non_literal_pattern_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/a.py': 'import re\n\nPATTERN = "x"\nTOKEN_RE = re.compile(PATTERN)\n',
            'src/probe/b.py': 'import re\n\nPATTERN = "x"\nTOKEN_RE = re.compile(PATTERN)\n',
        }
    )
    assert run_check(RECOMPILE, root) == []
