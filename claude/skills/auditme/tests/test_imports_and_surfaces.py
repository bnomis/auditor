"""Tests for the import-graph and public-surface predicates."""

import collections.abc
import pathlib
import types
import typing

import auditme.core
import auditme.rules.imports_and_surfaces

if typing.TYPE_CHECKING:
    import pytest

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

DEF_CLASS_IN_INIT = auditme.rules.imports_and_surfaces.check_def_class_in_init
IN_FUNCTION_IMPORTS = auditme.rules.imports_and_surfaces.check_in_function_imports
UNUSED_SUBMODULE = auditme.rules.imports_and_surfaces.check_unused_submodule_imports
LAYERING = auditme.rules.imports_and_surfaces.check_layering_violations
PASSTHROUGH = auditme.rules.imports_and_surfaces.check_passthrough_shim
EMPTY_INIT = auditme.rules.imports_and_surfaces.check_empty_init_with_exporting_siblings
MIGRATION_SHIM = auditme.rules.imports_and_surfaces.check_migration_shim_consumers
REEXPORT = auditme.rules.imports_and_surfaces.check_reexport_in_non_init
AS_IMPORT = auditme.rules.imports_and_surfaces.check_as_import
FROM_IMPORT = auditme.rules.imports_and_surfaces.check_from_import

AS_IMPORT_AGENTS = """
# probe

## Imports

**Always use the full import path.** `from X import Y` is permitted in exactly
one place: an `__init__.py` re-export list. `import numpy as np` is a violation
too - no `as` imports either.
"""

LAYERING_AGENTS = """
# probe

## Package Layering

data < config < models

### Accepted cross-layer exceptions

| Importer | Imported | Reason |
|----------|----------|--------|
| `data` | `config` | settings are read at load time |
"""


# --------------------------------------------------------------------------
# check_def_class_in_init
# --------------------------------------------------------------------------


def test_a_def_in_an_init_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/__init__.py': 'def helper() -> None:\n    return None\n'})
    hits = run_check(DEF_CLASS_IN_INIT, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('def-class-in-init', 1)]


def test_a_class_in_an_init_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/__init__.py': 'class Thing:\n    pass\n'})
    assert len(run_check(DEF_CLASS_IN_INIT, root)) == 1


def test_a_def_in_an_ordinary_module_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'def helper() -> None:\n    return None\n'})
    assert run_check(DEF_CLASS_IN_INIT, root) == []


def test_an_indented_def_in_an_init_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """The rule is about top-level definitions; a method inside a re-exported
    class body is not one."""
    root = project({'src/probe/__init__.py': 'if True:\n    def helper() -> None:\n        return None\n'})
    assert run_check(DEF_CLASS_IN_INIT, root) == []


# --------------------------------------------------------------------------
# check_in_function_imports
# --------------------------------------------------------------------------


def test_an_import_inside_a_function_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def parse(text: str) -> object:
                import json
                return json.loads(text)
            """
        }
    )
    hits = run_check(IN_FUNCTION_IMPORTS, root)
    assert [(hit['rule'], hit['variant'], hit['line']) for hit in hits] == [('in-function-import', 'stdlib', 2)]


def test_a_first_party_in_function_import_is_labelled_as_such(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def parse(text: str) -> object:
                import probe.heavy
                return probe.heavy.run(text)
            """
        }
    )
    assert [hit['variant'] for hit in run_check(IN_FUNCTION_IMPORTS, root)] == ['first-party']


def test_a_module_under_a_declared_root_is_labelled_first_party(project: Builder, run_check: Runner, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def parse(text: str) -> object:
                import gitutils
                import auditme.core
                return gitutils, auditme.core
            """,
            'bin/gitutils.py': 'VALUE = 1\n',
            'lib/auditme/__init__.py': '',
        }
    )
    monkeypatch.setattr(
        auditme.core,
        'ROOT_MODULES',
        types.MappingProxyType({root / 'bin': auditme.core.TOP_LEVEL, root / 'lib' / 'auditme': auditme.core.PACKAGE}),
    )
    assert [hit['variant'] for hit in run_check(IN_FUNCTION_IMPORTS, root)] == ['first-party', 'first-party']


def test_a_module_outside_every_declared_root_stays_third_party(project: Builder, run_check: Runner, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def parse(text: str) -> object:
                import requests
                return requests
            """,
            'bin/gitutils.py': 'VALUE = 1\n',
        }
    )
    monkeypatch.setattr(auditme.core, 'ROOT_MODULES', types.MappingProxyType({root / 'bin': auditme.core.TOP_LEVEL}))
    assert [hit['variant'] for hit in run_check(IN_FUNCTION_IMPORTS, root)] == ['third-party']


def test_an_import_under_type_checking_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """The `TYPE_CHECKING` guard has to be tested inside a function.

    A module-level guard is never reached: the check only walks function
    scopes, so a module-level fixture would pass whether or not the
    `TYPE_CHECKING` exemption existed.
    """
    root = project(
        {
            'src/probe/mod.py': """
            import typing


            def parse(text: str) -> object:
                if typing.TYPE_CHECKING:
                    import json
                return text
            """
        }
    )
    assert run_check(IN_FUNCTION_IMPORTS, root) == []


def test_the_same_import_without_the_guard_is_a_hit(project: Builder, run_check: Runner) -> None:
    """The counterpart to the test above: the guard is what makes the difference."""
    root = project(
        {
            'src/probe/mod.py': """
            def parse(text: str) -> object:
                if text:
                    import json
                    return json.loads(text)
                return text
            """
        }
    )
    assert len(run_check(IN_FUNCTION_IMPORTS, root)) == 1


def test_an_optional_dependency_probe_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """`try: import x / except ImportError` is how an optional dependency is
    detected, not a lazy import hiding a startup cost."""
    root = project(
        {
            'src/probe/mod.py': """
            def has_orjson() -> bool:
                try:
                    import orjson
                except ImportError:
                    return False
                return bool(orjson)
            """
        }
    )
    assert run_check(IN_FUNCTION_IMPORTS, root) == []


def test_an_init_file_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/__init__.py': """
            def build() -> object:
                import json
                return json
            """
        }
    )
    assert run_check(IN_FUNCTION_IMPORTS, root) == []


def test_an_agents_table_row_accepts_the_pair(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'AGENTS.md': """
            ## Accepted lazy imports

            | Importer | Imported | Reason |
            |----------|----------|--------|
            | `probe.mod` | `json` | startup cost |
            """,
            'src/probe/mod.py': """
            def parse(text: str) -> object:
                import json
                return json.loads(text)
            """,
        }
    )
    hits = run_check(IN_FUNCTION_IMPORTS, root)
    assert len(hits) == 1
    assert hits[0]['accepted']
    assert 'probe.mod -> json' in hits[0]['accepted_reason']


# --------------------------------------------------------------------------
# check_unused_submodule_imports
# --------------------------------------------------------------------------


def test_an_unreferenced_submodule_import_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import os.path\n\nVALUE = 1\n'})
    hits = run_check(UNUSED_SUBMODULE, root)
    assert [(hit['rule'], hit['evidence']) for hit in hits] == [('unused-submodule-import', 'import os.path')]


def test_a_referenced_submodule_import_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "import os.path\n\nVALUE = os.path.join('a', 'b')\n"})
    assert run_check(UNUSED_SUBMODULE, root) == []


def test_a_reference_through_the_root_package_counts_as_use(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import os.path\n\nVALUE = os.getcwd()\n'})
    assert run_check(UNUSED_SUBMODULE, root) == []


def test_a_plain_import_without_a_dot_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import os\n\nVALUE = 1\n'})
    assert run_check(UNUSED_SUBMODULE, root) == []


# --------------------------------------------------------------------------
# check_layering_violations
# --------------------------------------------------------------------------


def test_an_upward_import_violates_the_layering(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'AGENTS.md': LAYERING_AGENTS,
            'src/probe/data/loader.py': 'import probe.models.thing\n\nVALUE = probe.models.thing\n',
        }
    )
    hits = run_check(LAYERING, root)
    assert [(hit['rule'], hit['variant']) for hit in hits] == [('layering-violation', 'data imports models (upward)')]


def test_a_downward_import_is_not_a_violation(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'AGENTS.md': LAYERING_AGENTS,
            'src/probe/models/thing.py': 'import probe.data.loader\n\nVALUE = probe.data.loader\n',
        }
    )
    assert run_check(LAYERING, root) == []


def test_an_agents_exception_row_permits_the_inversion(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'AGENTS.md': LAYERING_AGENTS,
            'src/probe/data/loader.py': 'import probe.config.settings\n\nVALUE = probe.config.settings\n',
        }
    )
    assert run_check(LAYERING, root) == []


def test_a_project_that_declares_no_layering_is_not_checked(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/data/loader.py': 'import probe.models.thing\n\nVALUE = probe.models.thing\n'})
    assert run_check(LAYERING, root) == []


def test_a_layering_violation_under_type_checking_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'AGENTS.md': LAYERING_AGENTS,
            'src/probe/data/loader.py': 'import typing\n\nif typing.TYPE_CHECKING:\n    import probe.models.thing\n',
        }
    )
    assert run_check(LAYERING, root) == []


# --------------------------------------------------------------------------
# check_passthrough_shim
# --------------------------------------------------------------------------


def test_a_function_that_only_forwards_its_arguments_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def load(path: str, mode: str) -> object:
                return probe.core.load(path, mode)
            """
        }
    )
    hits = run_check(PASSTHROUGH, root)
    assert [(hit['rule'], hit['variant']) for hit in hits] == [('passthrough-shim', 'load is a pass-through wrapper for probe.core.load')]


def test_a_docstring_does_not_stop_it_being_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def load(path: str) -> object:
                \"\"\"Load the thing.\"\"\"
                return probe.core.load(path)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 1


def test_a_function_that_does_more_than_forward_is_not_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def load(path: str) -> object:
                resolved = path.strip()
                return probe.core.load(resolved)
            """
        }
    )
    assert run_check(PASSTHROUGH, root) == []


def test_a_call_with_a_computed_argument_is_not_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core


            def load(path: str) -> object:
                return probe.core.load(path.strip())
            """
        }
    )
    assert run_check(PASSTHROUGH, root) == []


# --------------------------------------------------------------------------
# check_empty_init_with_exporting_siblings
# --------------------------------------------------------------------------


EXPORTING_SIBLING = "__all__ = ['A', 'B', 'C', 'D', 'E']\n"


def test_an_empty_init_beside_an_exporting_sibling_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/__init__.py': '',
            'src/probe/rich/__init__.py': EXPORTING_SIBLING,
            'src/probe/sparse/__init__.py': '"""Nothing exported."""\n',
        }
    )
    hits = run_check(EMPTY_INIT, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('empty-init-while-siblings-export', 'src/probe/sparse/__init__.py')]


def test_no_sibling_with_a_real_surface_means_the_rule_does_not_apply(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/__init__.py': '',
            'src/probe/thin/__init__.py': "__all__ = ['A']\n",
            'src/probe/sparse/__init__.py': '"""Nothing exported."""\n',
        }
    )
    assert run_check(EMPTY_INIT, root) == []


def test_a_marker_anywhere_in_the_file_accepts_the_finding(project: Builder, run_check: Runner) -> None:
    """A docstring-only `__init__.py` has no line to hang an inline marker on."""
    root = project(
        {
            'src/probe/__init__.py': '',
            'src/probe/rich/__init__.py': EXPORTING_SIBLING,
            'src/probe/sparse/__init__.py': '"""Nothing exported."""\n\n# auditme: accept[empty-init-while-siblings-export] internal grouping only\n',
        }
    )
    hits = run_check(EMPTY_INIT, root)
    assert len(hits) == 1
    assert hits[0]['accepted']
    assert hits[0]['accepted_reason'] == 'internal grouping only'


def test_a_call_that_repeats_a_parameter_is_not_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            def load(name: str) -> object:
                return probe.core.get(name, name)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 0


def test_a_keyword_with_a_computed_value_is_not_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            def load(x: str) -> object:
                return probe.core.load(x, size=len(x))
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 0


def test_a_double_star_keyword_is_not_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            def load(x: str, **opts: object) -> object:
                return probe.core.load(x, **opts)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 0


def test_a_pytest_fixture_is_not_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            @pytest.fixture
            def load(x: str) -> object:
                return probe.core.load(x)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 0


def test_a_pytest_fixture_with_arguments_is_not_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            @pytest.fixture(scope='module')
            def load(x: str) -> object:
                return probe.core.load(x)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 0


def test_any_decorator_excludes_a_function_from_being_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            @probe.core.register
            def load(x: str) -> object:
                return probe.core.load(x)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 0


def test_a_forward_with_a_keyword_parameter_is_still_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            def load(a: str, key: str) -> object:
                return probe.core.load(a, key=key)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 1


def test_a_forward_of_two_positionals_is_still_a_shim(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            import probe.core
            import pytest


            def load(a: str, b: str) -> object:
                return probe.core.load(a, b)
            """
        }
    )
    assert len(run_check(PASSTHROUGH, root)) == 1


# --------------------------------------------------------------------------
# check_migration_shim_consumers
# --------------------------------------------------------------------------


SHIM_TREE = {
    'src/probe/core.py': 'class Thing:\n    pass\n',
    'src/probe/shim.py': 'import probe.core\n\nThing = probe.core.Thing\n',
}


def test_importing_a_symbol_through_a_shim_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({**SHIM_TREE, 'src/probe/user.py': 'from probe.shim import Thing\n\nVALUE = Thing\n'})
    hits = run_check(MIGRATION_SHIM, root)
    assert [(hit['rule'], hit['path']) for hit in hits] == [('migration-shim-consumer', 'src/probe/user.py')]
    assert 'canonical home is `probe.core`' in hits[0]['variant']


def test_reading_a_symbol_off_a_shim_module_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({**SHIM_TREE, 'src/probe/user.py': 'import probe.shim\n\nVALUE = probe.shim.Thing\n'})
    hits = run_check(MIGRATION_SHIM, root)
    assert len(hits) == 1
    assert 'reads `Thing` from shim' in hits[0]['variant']


def test_importing_from_the_canonical_home_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({**SHIM_TREE, 'src/probe/user.py': 'from probe.core import Thing\n\nVALUE = Thing\n'})
    assert run_check(MIGRATION_SHIM, root) == []


def test_the_shim_module_itself_is_not_its_own_consumer(project: Builder, run_check: Runner) -> None:
    root = project(SHIM_TREE)
    assert run_check(MIGRATION_SHIM, root) == []


def test_one_shim_importing_from_another_is_not_a_consumer(project: Builder, run_check: Runner) -> None:
    """A module that is itself a shim is part of the migration, not a victim of
    it, so it is excluded even when it reads through a sibling shim."""
    root = project(
        {
            **SHIM_TREE,
            'src/probe/other.py': 'import probe.core\n\nOther = probe.core.Other\n\nfrom probe.shim import Thing\n\nVALUE = Thing\n',
        }
    )
    assert run_check(MIGRATION_SHIM, root) == []


# --------------------------------------------------------------------------
# check_reexport_in_non_init
# --------------------------------------------------------------------------


def test_a_reexport_outside_an_init_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import probe.core\n\nThing = probe.core.Thing\n'})
    hits = run_check(REEXPORT, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('reexport-in-non-init', 3)]


def test_a_reexport_inside_an_init_is_the_sanctioned_place(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/__init__.py': 'import probe.core\n\nThing = probe.core.Thing\n'})
    assert run_check(REEXPORT, root) == []


def test_an_assignment_whose_name_differs_is_not_a_reexport(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import probe.core\n\nDEFAULT = probe.core.Thing\n'})
    assert run_check(REEXPORT, root) == []


# --------------------------------------------------------------------------
# check_as_import
# --------------------------------------------------------------------------


def test_an_as_import_is_a_hit_where_the_project_bans_it(project: Builder, run_check: Runner) -> None:
    root = project({'AGENTS.md': AS_IMPORT_AGENTS, 'src/probe/mod.py': 'import numpy as np\n'})
    hits = run_check(AS_IMPORT, root)
    assert [(hit['rule'], hit['line'], hit['evidence']) for hit in hits] == [('as-import', 1, 'import numpy as np')]
    assert hits[0]['variant'] == 'import X as Y'


def test_an_aliased_from_import_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'AGENTS.md': AS_IMPORT_AGENTS, 'src/probe/mod.py': 'from probe.core import Thing as Widget\n'})
    hits = run_check(AS_IMPORT, root)
    assert [(hit['variant'], hit['evidence']) for hit in hits] == [('from M import X as Y', 'from probe.core import Thing as Widget')]


def test_an_as_import_inside_a_function_is_a_hit(project: Builder, run_check: Runner) -> None:
    """The site that prompted this was a fixture body, which the full-path-imports codemod
    and ruff's ICN003 both walked past."""
    root = project(
        {
            'AGENTS.md': AS_IMPORT_AGENTS,
            'src/probe/mod.py': """
            def fixture() -> object:
                import gitutils as module

                return module
            """,
        }
    )
    hits = run_check(AS_IMPORT, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('as-import', 2)]


def test_an_unaliased_import_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'AGENTS.md': AS_IMPORT_AGENTS, 'src/probe/mod.py': 'import numpy\nimport probe.core\n'})
    assert run_check(AS_IMPORT, root) == []


def test_an_as_import_is_not_a_hit_where_the_project_does_not_ban_it(project: Builder, run_check: Runner) -> None:
    """`import numpy as np` is idiomatic nearly everywhere; the check is gated
    on the project declaring the rule in its own AGENTS.md."""
    root = project({'AGENTS.md': '# probe\n\n## Imports\n\nFollow isort ordering.\n', 'src/probe/mod.py': 'import numpy as np\n'})
    assert run_check(AS_IMPORT, root) == []


def test_an_as_import_is_not_a_hit_with_no_agents_file(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import numpy as np\n'})
    assert run_check(AS_IMPORT, root) == []


def test_prose_mentioning_imports_is_not_a_declared_ban(project: Builder, run_check: Runner) -> None:
    """The keyword has to be quoted; otherwise ordinary prose gates the check on."""
    root = project(
        {
            'AGENTS.md': '# probe\n\nThere are no vendored imports as such in this tree.\n',
            'src/probe/mod.py': 'import numpy as np\n',
        }
    )
    assert run_check(AS_IMPORT, root) == []


def test_a_renaming_reexport_in_an_init_is_the_sanctioned_place(project: Builder, run_check: Runner) -> None:
    root = project({'AGENTS.md': AS_IMPORT_AGENTS, 'src/probe/__init__.py': 'from probe.core import Thing as Widget\n'})
    assert run_check(AS_IMPORT, root) == []


def test_a_plain_aliased_import_in_an_init_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    """`import x as y` is not a re-export list, wherever it is written."""
    root = project({'AGENTS.md': AS_IMPORT_AGENTS, 'src/probe/__init__.py': 'import probe.core as core\n'})
    assert [hit['rule'] for hit in run_check(AS_IMPORT, root)] == ['as-import']


def test_a_scoped_accept_marker_dismisses_the_as_import(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'AGENTS.md': AS_IMPORT_AGENTS,
            'src/probe/mod.py': 'import gitutils as module  # auditme: accept[as-import] must follow syspath_prepend\n',
        }
    )
    hits = run_check(AS_IMPORT, root)
    assert [(hit['accepted'], hit['accepted_reason']) for hit in hits] == [(True, 'must follow syspath_prepend')]


def test_a_marker_scoped_to_another_rule_does_not_dismiss_it(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'AGENTS.md': AS_IMPORT_AGENTS,
            'src/probe/mod.py': 'import gitutils as module  # auditme: accept[in-function-import] lazy on purpose\n',
        }
    )
    assert [hit['accepted'] for hit in run_check(AS_IMPORT, root)] == [False]


# --------------------------------------------------------------------------
# check_from_import
# --------------------------------------------------------------------------


def test_a_from_import_in_a_module_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'from pathlib import Path, PurePath\n'})
    hits = run_check(FROM_IMPORT, root)
    assert [(hit['rule'], hit['line'], hit['evidence']) for hit in hits] == [('from-import', 1, 'from pathlib import Path, PurePath')]


def test_a_from_import_inside_a_function_or_type_checking_block_is_a_hit(project: Builder, run_check: Runner) -> None:
    """A from-import is one wherever it is written; the sites that prompted the
    check included a conftest fixture body."""
    root = project(
        {
            'src/probe/mod.py': """
            import typing

            if typing.TYPE_CHECKING:
                from probe.core import Thing


            def fixture() -> object:
                from probe.core import Widget

                return Widget
            """,
        }
    )
    assert [hit['line'] for hit in run_check(FROM_IMPORT, root)] == [4, 8]


def test_a_relative_from_import_in_a_module_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'from . import core\n'})
    assert [hit['evidence'] for hit in run_check(FROM_IMPORT, root)] == ['from . import core']


def test_the_test_tree_is_swept_like_any_other_root(project: Builder, run_check: Runner) -> None:
    root = project({'src/tests/conftest.py': 'from probe.core import Thing\n'})
    assert [hit['path'] for hit in run_check(FROM_IMPORT, root, package='tests')] == ['src/tests/conftest.py']


def test_a_from_import_in_an_init_is_the_sanctioned_re_export(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/__init__.py': "from .core import Thing\nfrom probe.base import Widget\n\n__all__ = ['Thing', 'Widget']\n"})
    assert run_check(FROM_IMPORT, root) == []


def test_future_and_star_imports_are_left_to_their_own_rules(project: Builder, run_check: Runner) -> None:
    """`future-annotations` and `wildcard-imports` already report these lines."""
    root = project({'src/probe/mod.py': 'from __future__ import annotations\nfrom os import *\n'})
    assert run_check(FROM_IMPORT, root) == []


def test_a_plain_import_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import pathlib\nimport probe.core\n'})
    assert run_check(FROM_IMPORT, root) == []


def test_the_check_needs_no_declaration_in_agents(project: Builder, run_check: Runner) -> None:
    """Unlike `as-import`, the rule is the shared standard, not a project opt-in."""
    root = project({'AGENTS.md': '# probe\n\n## Imports\n\nFollow isort ordering.\n', 'src/probe/mod.py': 'from pathlib import Path\n'})
    assert [hit['rule'] for hit in run_check(FROM_IMPORT, root)] == ['from-import']


def test_a_marker_on_a_continuation_line_accepts_a_multiline_from_import(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            from probe.core import (
                Thing,  # auditme: accept[from-import] vendored module
            )
            """,
        }
    )
    assert [(hit['accepted'], hit['accepted_reason']) for hit in run_check(FROM_IMPORT, root)] == [(True, 'vendored module')]


def test_a_scoped_accept_marker_dismisses_the_from_import(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'from pathlib import Path  # auditme: accept[from-import] generated code\n'})
    assert [(hit['accepted'], hit['accepted_reason']) for hit in run_check(FROM_IMPORT, root)] == [(True, 'generated code')]


def test_a_marker_scoped_to_another_rule_does_not_dismiss_the_from_import(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'from pathlib import Path  # auditme: accept[as-import] unrelated\n'})
    assert [hit['accepted'] for hit in run_check(FROM_IMPORT, root)] == [False]


def test_declared_root_modules_are_listed_once_per_run(project: Builder, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'bin/tool.py': '', 'bin/pkg/__init__.py': ''})
    monkeypatch.setattr(auditme.core, 'ROOT_MODULES', types.MappingProxyType({root / 'bin': auditme.core.TOP_LEVEL}))
    auditme.core.clear_source_cache()
    calls: list[pathlib.Path] = []
    real = pathlib.Path.glob

    def counting(self: pathlib.Path, pattern: str, **kwargs: typing.Any) -> typing.Any:
        calls.append(self)
        return real(self, pattern, **kwargs)

    monkeypatch.setattr(pathlib.Path, 'glob', counting)
    first = auditme.rules.imports_and_surfaces.declared_root_modules()
    second = auditme.rules.imports_and_surfaces.declared_root_modules()
    assert first == second == {'tool', 'pkg'}
    assert len(calls) == 1


def test_the_all_guard_scan_runs_once_per_sweep_over_two_roots(project: Builder, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project({'src/probe/a.py': 'x = 1\n', 'src/probe/b.py': "y = getattr(m, '__all__')\n"})
    auditme.core.clear_source_cache()
    calls: list[pathlib.Path] = []
    real = auditme.rules.imports_and_surfaces.scan_has_all_guard

    def counting(scope: pathlib.Path) -> bool:
        calls.append(scope)
        return real(scope)

    monkeypatch.setattr(auditme.rules.imports_and_surfaces, 'scan_has_all_guard', counting)
    answers = [auditme.rules.imports_and_surfaces.project_has_all_guard(root) for _ in range(2)]
    assert answers == [True, True]
    assert calls == [root]
