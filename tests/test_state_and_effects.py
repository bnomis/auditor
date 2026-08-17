"""Tests for the mutation, side-effect and hidden-state predicates."""

import collections.abc
import pathlib

import auditme.rules.state_and_effects

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

CONSTRUCTOR_IO = auditme.rules.state_and_effects.check_constructor_disk_io
SELF_MUTATION = auditme.rules.state_and_effects.check_silent_self_mutation
RETURN_SHADOWS = auditme.rules.state_and_effects.check_return_value_shadows_instance_attr
PARAM_MUTATION = auditme.rules.state_and_effects.check_parameter_mutation
PURE_NAME = auditme.rules.state_and_effects.check_pure_name_has_side_effect
STORE_WITHOUT_COPY = auditme.rules.state_and_effects.check_mutable_store_without_copy
ASSERT_NEVER = auditme.rules.state_and_effects.check_assert_never_missing
BUILD_NAME = auditme.rules.state_and_effects.check_build_name_has_side_effect
MUTABLE_EXPORT = auditme.rules.state_and_effects.check_mutable_module_level_exported
CALLBACK_IO = auditme.rules.state_and_effects.check_callback_hotpath_io
DATACLASS_OPTIONAL = auditme.rules.state_and_effects.check_dataclass_optional_always_set
DEAD_LOCAL = auditme.rules.state_and_effects.check_dead_local_init
SUBPROCESS = auditme.rules.state_and_effects.check_subprocess_without_memoisation


# --------------------------------------------------------------------------
# check_constructor_disk_io
# --------------------------------------------------------------------------


def test_a_constructor_that_touches_disk_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib


            class Store:
                def __init__(self, root: pathlib.Path) -> None:
                    root.mkdir(parents=True, exist_ok=True)
                    self.root = root
            """
        }
    )
    hits = run_check(CONSTRUCTOR_IO, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('constructor-disk-io', 6)]
    assert hits[0]['variant'] == 'Store.__init__ calls disk-IO `mkdir`'


def test_disk_io_in_an_ordinary_method_is_not_a_constructor_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib


            class Store:
                def __init__(self, root: pathlib.Path) -> None:
                    self.root = root

                def prepare(self) -> None:
                    self.root.mkdir(parents=True, exist_ok=True)
            """
        }
    )
    assert run_check(CONSTRUCTOR_IO, root) == []


# --------------------------------------------------------------------------
# check_silent_self_mutation
# --------------------------------------------------------------------------


def test_a_stage_method_that_reassigns_owned_state_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Pipeline:
                def __init__(self, config: dict) -> None:
                    self.config = config

                def tokenize(self, patched: dict) -> None:
                    self.config = patched
            """
        }
    )
    hits = run_check(SELF_MUTATION, root)
    assert [(hit['rule'], hit['variant']) for hit in hits] == [('silent-self-mutation', 'Pipeline.tokenize reassigns self.config')]


def test_a_method_named_for_mutation_may_mutate(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Pipeline:
                def __init__(self, config: dict) -> None:
                    self.config = config

                def update_config(self, patched: dict) -> None:
                    self.config = patched

                def set_config(self, patched: dict) -> None:
                    self.config = patched
            """
        }
    )
    assert run_check(SELF_MUTATION, root) == []


def test_reassigning_an_attribute_the_caller_never_supplied_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """The rule is about the caller's view of their own object drifting."""
    root = project(
        {
            'src/probe/mod.py': """
            class Pipeline:
                def __init__(self, config: dict) -> None:
                    self.config = config
                    self.cache = {}

                def tokenize(self) -> None:
                    self.cache = {'a': 1}
            """
        }
    )
    assert run_check(SELF_MUTATION, root) == []


# --------------------------------------------------------------------------
# check_return_value_shadows_instance_attr
# --------------------------------------------------------------------------


def test_returning_a_divergent_copy_of_owned_state_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Pipeline:
                def __init__(self, config: dict) -> None:
                    self.config = config

                def tokenize(self) -> dict:
                    patched_config = self.config.copy()
                    patched_config['tokenized'] = True
                    return patched_config
            """
        }
    )
    hits = run_check(RETURN_SHADOWS, root)
    assert [hit['rule'] for hit in hits] == ['return-shadows-instance-attr']
    assert 'callers must reassign' in hits[0]['variant']


def test_a_local_that_is_not_derived_from_the_attribute_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Pipeline:
                def __init__(self, config: dict) -> None:
                    self.config = config

                def tokenize(self) -> dict:
                    patched_config = {'fresh': True}
                    return patched_config
            """
        }
    )
    assert run_check(RETURN_SHADOWS, root) == []


# --------------------------------------------------------------------------
# check_parameter_mutation
# --------------------------------------------------------------------------


def test_a_validator_that_writes_into_its_argument_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def validate_config(config: dict) -> bool:
                config['checked'] = True
                return True
            """
        }
    )
    hits = run_check(PARAM_MUTATION, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('parameter-mutation-in-pure-function', 2)]
    assert 'item assignment' in hits[0]['variant']


def test_a_validator_that_calls_a_mutating_method_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def check_config(config: dict, extra: dict) -> bool:
                config.update(extra)
                return True
            """
        }
    )
    hits = run_check(PARAM_MUTATION, root)
    assert len(hits) == 1
    assert '.update()' in hits[0]['variant']


def test_a_function_that_advertises_mutation_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def apply_config(config: dict) -> bool:
                config['checked'] = True
                return True
            """
        }
    )
    assert run_check(PARAM_MUTATION, root) == []


def test_a_validator_that_mutates_a_local_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def validate_config(config: dict) -> dict:
                copied = dict(config)
                copied['checked'] = True
                return copied
            """
        }
    )
    assert run_check(PARAM_MUTATION, root) == []


# --------------------------------------------------------------------------
# check_pure_name_has_side_effect
# --------------------------------------------------------------------------


def test_a_get_function_that_writes_to_disk_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib


            def get_run_dir(root: pathlib.Path) -> pathlib.Path:
                root.mkdir(parents=True, exist_ok=True)
                return root
            """
        }
    )
    hits = run_check(PURE_NAME, root)
    assert [hit['rule'] for hit in hits] == ['pure-name-has-side-effect']
    assert '`mkdir`' in hits[0]['variant']


def test_a_load_function_may_do_io(project: Builder, run_check: Runner) -> None:
    """`load_*` names promise IO; the rule is about names that do not."""
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib


            def load_run_dir(root: pathlib.Path) -> pathlib.Path:
                root.mkdir(parents=True, exist_ok=True)
                return root
            """
        }
    )
    assert run_check(PURE_NAME, root) == []


def test_a_side_effect_inside_a_returned_closure_is_not_the_function_s_own(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import collections.abc
            import pathlib


            def get_preparer(root: pathlib.Path) -> collections.abc.Callable[[], None]:
                def prepare() -> None:
                    root.mkdir(parents=True, exist_ok=True)

                return prepare
            """
        }
    )
    assert run_check(PURE_NAME, root) == []


# --------------------------------------------------------------------------
# check_mutable_store_without_copy
# --------------------------------------------------------------------------


def test_storing_a_dict_parameter_by_reference_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Store:
                def __init__(self, options: dict[str, int]) -> None:
                    self.options = options
            """
        }
    )
    hits = run_check(STORE_WITHOUT_COPY, root)
    assert [hit['rule'] for hit in hits] == ['mutable-store-without-copy']


def test_a_defensive_copy_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Store:
                def __init__(self, options: dict[str, int]) -> None:
                    self.options = dict(options)
            """
        }
    )
    assert run_check(STORE_WITHOUT_COPY, root) == []


def test_an_immutable_parameter_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            class Store:
                def __init__(self, options: tuple[int, ...]) -> None:
                    self.options = options
            """
        }
    )
    assert run_check(STORE_WITHOUT_COPY, root) == []


# --------------------------------------------------------------------------
# check_assert_never_missing
# --------------------------------------------------------------------------


def test_a_three_arm_string_dispatch_without_an_else_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def score(kind: str) -> int:
                if kind == 'alpha':
                    return 1
                elif kind == 'beta':
                    return 2
                elif kind == 'gamma':
                    return 3
                return 0
            """
        }
    )
    hits = run_check(ASSERT_NEVER, root)
    assert [hit['rule'] for hit in hits] == ['assert-never-missing']
    assert 'has no else' in hits[0]['variant']


def test_a_chain_that_ends_in_assert_never_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import typing


            def score(kind: str) -> int:
                if kind == 'alpha':
                    return 1
                elif kind == 'beta':
                    return 2
                elif kind == 'gamma':
                    return 3
                else:
                    typing.assert_never(kind)
            """
        }
    )
    assert run_check(ASSERT_NEVER, root) == []


def test_a_two_arm_chain_is_legitimately_bi_valued(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def score(kind: str) -> int:
                if kind == 'alpha':
                    return 1
                elif kind == 'beta':
                    return 2
                return 0
            """
        }
    )
    assert run_check(ASSERT_NEVER, root) == []


# --------------------------------------------------------------------------
# check_build_name_has_side_effect
# --------------------------------------------------------------------------


def test_a_build_function_that_reads_the_clock_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import datetime


            def build_run_name(prefix: str) -> str:
                return prefix + datetime.datetime.now().isoformat()
            """
        }
    )
    hits = run_check(BUILD_NAME, root)
    assert [hit['rule'] for hit in hits] == ['build-name-has-side-effect']
    assert '`now`' in hits[0]['variant']


def test_a_build_function_that_only_assembles_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def build_run_name(prefix: str, suffix: str) -> str:
                return prefix + '-' + suffix
            """
        }
    )
    assert run_check(BUILD_NAME, root) == []


def test_a_function_that_promises_nothing_may_read_the_clock(project: Builder, run_check: Runner) -> None:
    """Only `build_`/`compute_` names carry the pure-assembly contract."""
    root = project(
        {
            'src/probe/mod.py': """
            import datetime


            def stamp_run_name(prefix: str) -> str:
                return prefix + datetime.datetime.now().isoformat()
            """
        }
    )
    assert run_check(BUILD_NAME, root) == []


# --------------------------------------------------------------------------
# check_mutable_module_level_exported
# --------------------------------------------------------------------------


def test_a_mutable_global_imported_elsewhere_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/settings.py': "DEFAULTS = {'a': 1}\n",
            'src/probe/user.py': 'from probe.settings import DEFAULTS\n\nVALUE = DEFAULTS\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('mutable-module-level-exported', 'src/probe/settings.py')]
    assert 'types.MappingProxyType(...)' in hits[0]['variant']


def test_a_mutable_global_read_by_attribute_access_is_a_hit(project: Builder, run_check: Runner) -> None:
    """The project standard is dotted access, so both forms must count."""
    root = project(
        {
            'src/probe/settings.py': 'DEFAULTS = [1, 2]\n',
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert len(hits) == 1
    assert 'tuple(...)' in hits[0]['variant']


def test_a_mutable_global_nobody_imports_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/settings.py': "DEFAULTS = {'a': 1}\n"})
    assert run_check(MUTABLE_EXPORT, root) == []


def test_an_immutably_wrapped_global_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/settings.py': "import types\n\nDEFAULTS = types.MappingProxyType({'a': 1})\n",
            'src/probe/user.py': 'from probe.settings import DEFAULTS\n\nVALUE = DEFAULTS\n',
        }
    )
    assert run_check(MUTABLE_EXPORT, root) == []


def test_a_reader_in_a_sibling_package_still_counts(project: Builder, run_check: Runner) -> None:
    """The driver sweeps one package per pass; readers live in all of them.

    A project whose `src/` holds the library and the test tree keeps its
    cross-module readers in the sibling package, so a reader scan rooted at the
    package under audit sees none of them and the export reads as private.
    """
    root = project(
        {
            'src/probe/settings.py': "DEFAULTS = {'a': 1}\n",
            'src/tests/test_settings.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('mutable-module-level-exported', 'src/probe/settings.py')]


def test_a_mutable_global_built_by_a_comprehension_is_a_hit(project: Builder, run_check: Runner) -> None:
    """`{k: f(k) for k in ...}` is the same mutable dict `{...}` is."""
    root = project(
        {
            'src/probe/settings.py': 'MODES = {name: name.upper() for name in ("a", "b")}\n',
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.MODES\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert len(hits) == 1
    assert 'dict comprehension' in hits[0]['variant']
    assert 'types.MappingProxyType(...)' in hits[0]['variant']


def test_an_annotated_mutable_global_is_a_hit(project: Builder, run_check: Runner) -> None:
    """An annotation is not a wrapper: `typing.Mapping` over a dict still mutates."""
    root = project(
        {
            'src/probe/settings.py': 'import typing\n\nDEFAULTS: typing.Mapping[str, int] = {"a": 1}\n',
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('mutable-module-level-exported', 3)]


def test_a_global_built_by_a_call_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """A `Call` value's type is not knowable from the assignment; see the
    rejected request in the skill's `requests.md`."""
    root = project(
        {
            'src/probe/settings.py': 'import probe.factory\n\nDEFAULTS = probe.factory.build()\n',
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    assert run_check(MUTABLE_EXPORT, root) == []


def test_a_scoped_accept_marker_dismisses_the_mutable_export(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/settings.py': "DEFAULTS = {'a': 1}  # auditme: accept[mutable-module-level-exported] callers copy\n",
            'src/probe/user.py': 'import probe.settings\n\nVALUE = probe.settings.DEFAULTS\n',
        }
    )
    hits = run_check(MUTABLE_EXPORT, root)
    assert [(hit['accepted'], hit['accepted_reason']) for hit in hits] == [(True, 'callers copy')]


# --------------------------------------------------------------------------
# check_callback_hotpath_io
# --------------------------------------------------------------------------


def test_a_callback_that_opens_a_file_per_event_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib


            class Reporter(TrainerCallback):
                def __init__(self, root: pathlib.Path) -> None:
                    self.root = root

                def on_log(self, args: object, state: object, control: object) -> None:
                    self.root.mkdir(parents=True, exist_ok=True)
            """
        }
    )
    hits = run_check(CALLBACK_IO, root)
    assert [hit['rule'] for hit in hits] == ['callback-hotpath-io']
    assert 'Reporter.on_log' in hits[0]['variant']


def test_the_same_setup_in_the_constructor_is_not_a_callback_hit(project: Builder, run_check: Runner) -> None:
    """This is the documented winner of the A18 / constructor-disk-io conflict."""
    root = project(
        {
            'src/probe/mod.py': """
            import pathlib


            class Reporter(TrainerCallback):
                def __init__(self, root: pathlib.Path) -> None:
                    root.mkdir(parents=True, exist_ok=True)
                    self.root = root

                def on_log(self, args: object, state: object, control: object) -> None:
                    return None
            """
        }
    )
    assert run_check(CALLBACK_IO, root) == []


# --------------------------------------------------------------------------
# check_dataclass_optional_always_set
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# check_dead_local_init
# --------------------------------------------------------------------------


def test_an_initial_value_overridden_on_every_branch_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def resolve(flag: bool) -> dict:
                result = {}
                if flag:
                    result = {'a': 1}
                    return result
                else:
                    result = {'b': 2}
                    return result
            """
        }
    )
    hits = run_check(DEAD_LOCAL, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('dead-local-init', 2)]


def test_an_initial_value_with_no_else_branch_is_not_dead(project: Builder, run_check: Runner) -> None:
    """Without an else the initial value is what the fall-through path returns."""
    root = project(
        {
            'src/probe/mod.py': """
            def resolve(flag: bool) -> dict:
                result = {}
                if flag:
                    result = {'a': 1}
                    return result
            """
        }
    )
    assert run_check(DEAD_LOCAL, root) == []


# --------------------------------------------------------------------------
# check_subprocess_without_memoisation
# --------------------------------------------------------------------------


def test_an_uncached_query_that_shells_out_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import subprocess


            def get_head_sha() -> str:
                return subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True).stdout
            """
        }
    )
    hits = run_check(SUBPROCESS, root)
    assert [hit['rule'] for hit in hits] == ['subprocess-without-memoisation']


def test_a_cached_query_that_shells_out_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import functools
            import subprocess


            @functools.cache
            def get_head_sha() -> str:
                return subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True).stdout
            """
        }
    )
    assert run_check(SUBPROCESS, root) == []


def test_a_name_that_does_not_promise_invariance_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import subprocess


            def run_git_command() -> str:
                return subprocess.run(['git', 'status'], capture_output=True).stdout
            """
        }
    )
    assert run_check(SUBPROCESS, root) == []
