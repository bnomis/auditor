"""Tests for the `redundant-sink-caller-plus-callee` check."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

REDUNDANT_SINK = auditor.testing.load_check(__file__)


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
