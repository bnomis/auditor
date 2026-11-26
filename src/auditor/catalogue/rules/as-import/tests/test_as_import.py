"""Tests for the checks of the `as-import` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

AS_IMPORT = auditor.testing.load_check(__file__)

AS_IMPORT_AGENTS = """
# probe

## Imports

**Always use the full import path.** `from X import Y` is permitted in exactly
one place: an `__init__.py` re-export list. `import numpy as np` is a violation
too - no `as` imports either.
"""


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
