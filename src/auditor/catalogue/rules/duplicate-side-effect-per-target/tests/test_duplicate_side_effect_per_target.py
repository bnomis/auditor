"""Tests for the `duplicate-side-effect-per-target` check."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

SIDE_EFFECT = auditor.testing.load_check(__file__)


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
