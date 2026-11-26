"""Tests for the checks of the `dataclass-optional-always-set` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

DATACLASS_OPTIONAL = auditor.testing.load_check(__file__)


def test_a_nullable_field_always_set_in_post_init_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import dataclasses


            @dataclasses.dataclass
            class Config:
                run_dir: str | None = None

                def __post_init__(self) -> None:
                    self.run_dir = '/tmp/run'
            """
        }
    )
    hits = run_check(DATACLASS_OPTIONAL, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('dataclass-optional-always-set', 6)]


def test_a_conditionally_set_nullable_field_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import dataclasses


            @dataclasses.dataclass
            class Config:
                run_dir: str | None = None
                enabled: bool = False

                def __post_init__(self) -> None:
                    if self.enabled:
                        self.run_dir = '/tmp/run'
            """
        }
    )
    assert run_check(DATACLASS_OPTIONAL, root) == []


def test_an_ordinary_class_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Config:
                run_dir: str | None = None

                def __post_init__(self) -> None:
                    self.run_dir = '/tmp/run'
            """
        }
    )
    assert run_check(DATACLASS_OPTIONAL, root) == []
