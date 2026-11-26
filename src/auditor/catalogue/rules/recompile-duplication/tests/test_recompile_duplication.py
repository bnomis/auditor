"""Tests for the `recompile-duplication` check."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

RECOMPILE = auditor.testing.load_check(__file__)


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
