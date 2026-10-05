"""Tests for the naming, ordering and annotation-style predicates."""

import collections.abc
import pathlib

import auditme.rules.style_and_naming
import pytest

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

TEXT_PATTERNS = auditme.rules.style_and_naming.check_text_patterns
PERCENT = auditme.rules.style_and_naming.check_percent_formatting
LITERALS = auditme.rules.style_and_naming.check_nonalphabetical_literals
DICT_KEYS = auditme.rules.style_and_naming.check_non_alphabetical_dict_keys
BARE_PARAMETRIC = auditme.rules.style_and_naming.check_bare_parametric_annotation
DUPLICATED_WORD = auditme.rules.style_and_naming.check_duplicated_word
BARE_NONBUILTIN = auditme.rules.style_and_naming.check_bare_nonbuiltin_generic_annotation
UNPACK_READ = auditme.rules.style_and_naming.check_underscore_unpack_target_read
FORLOOP_READ = auditme.rules.style_and_naming.check_underscore_forloop_target_read


def rules_found(hits: list[dict]) -> set[str]:
    return {hit['rule'] for hit in hits}


# --------------------------------------------------------------------------
# check_text_patterns
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('source', 'rule'),
    [
        pytest.param('from os import *\n', 'wildcard-imports', id='wildcard-imports'),
        pytest.param('from __future__ import annotations\n', 'future-annotations', id='future-annotations'),
        pytest.param('import numpy as np\n', 'aliased-imports', id='aliased-imports'),
        pytest.param('def f() -> None:\n    import numpy as np\n', 'aliased-imports', id='aliased-imports-indented'),
        pytest.param('def f() -> None:\n    """Run:\n\n        import tests.probe as t\n    """\n', 'aliased-imports', id='aliased-imports-docstring'),
        pytest.param('import typing\n\nvalue: typing.Optional[int] = None\n', 'legacy-typing', id='legacy-typing'),
        pytest.param("value = 'a {}'.format(1)\n", 'legacy-formatting-format', id='legacy-formatting-format'),
        pytest.param('import logging\n', 'stdlib-logging', id='stdlib-logging'),
        pytest.param('from .base import Thing\n', 'relative-import-nonpackage', id='relative-import-nonpackage'),
        pytest.param('def _helper() -> None:\n    return None\n', 'leading-underscore-def-class', id='leading-underscore-def-class'),
        pytest.param('_CACHE = {}\n', 'leading-underscore-const-upper', id='leading-underscore-const-upper'),
        pytest.param('_cache = {}\n', 'leading-underscore-const-lower', id='leading-underscore-const-lower'),
        pytest.param('class Thing:\n    def __init__(self) -> None:\n        self._value = 1\n', 'leading-underscore-self', id='leading-underscore-self'),
        pytest.param('def f(obj: object) -> object:\n    return obj._attr\n', 'leading-underscore-attribute-access', id='attribute-access'),
    ],
)
def test_each_text_pattern_fires(source: str, rule: str, project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': source})
    assert rule in rules_found(run_check(TEXT_PATTERNS, root))


def test_a_commented_out_line_is_not_a_text_pattern_hit(project: Builder, run_check: Runner) -> None:
    """A pattern inside a comment is discussion, not code."""
    root = project({'src/probe/mod.py': '# from os import *\n# import logging\n'})
    assert run_check(TEXT_PATTERNS, root) == []


def test_a_relative_import_in_an_init_is_the_sanctioned_re_export(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/__init__.py': "from .base import Thing\n\n__all__ = ['Thing']\n"})
    assert 'relative-import-nonpackage' not in rules_found(run_check(TEXT_PATTERNS, root))


def test_a_text_pattern_hit_can_be_accepted_by_its_own_rule(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'from os import *  # auditme: accept[wildcard-imports] re-export shim\n'})
    hits = [hit for hit in run_check(TEXT_PATTERNS, root) if hit['rule'] == 'wildcard-imports']
    assert len(hits) == 1
    assert hits[0]['accepted']
    assert hits[0]['accepted_reason'] == 're-export shim'


def test_a_marker_for_another_text_rule_does_not_accept_this_one(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'from os import *  # auditme: accept[aliased-imports] unrelated\n'})
    hits = [hit for hit in run_check(TEXT_PATTERNS, root) if hit['rule'] == 'wildcard-imports']
    assert len(hits) == 1
    assert not hits[0]['accepted']


def test_an_end_anchored_pattern_needs_its_marker_on_the_line_above(project: Builder, run_check: Runner) -> None:
    """`stdlib-logging` matches `^import logging$`, so an inline marker moves
    the line out of the pattern rather than accepting the hit. Both forms
    silence it; only the marker above records a reason in the output."""
    inline = project({'src/probe/mod.py': 'import logging  # auditme: accept[stdlib-logging] third-party callback wants one\n'})
    assert 'stdlib-logging' not in rules_found(run_check(TEXT_PATTERNS, inline))

    above = project({'src/probe/other.py': '# auditme: accept[stdlib-logging] third-party callback wants one\nimport logging\n'})
    hits = [hit for hit in run_check(TEXT_PATTERNS, above) if hit['rule'] == 'stdlib-logging']
    assert len(hits) == 1
    assert hits[0]['accepted']


# --------------------------------------------------------------------------
# check_percent_formatting
# --------------------------------------------------------------------------


def test_percent_s_formatting_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "def f(e: Exception) -> str:\n    return 'Exception: %s' % e\n"})
    hits = run_check(PERCENT, root)
    assert [hit['rule'] for hit in hits] == ['legacy-formatting-percent']
    assert hits[0]['line'] == 2


def test_a_strftime_directive_is_not_percent_formatting(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "import datetime\n\n\ndef f(when: datetime.datetime) -> str:\n    return when.strftime('%Y-%m-%d %H:%M:%S')\n"})
    assert run_check(PERCENT, root) == []


def test_a_line_with_several_percent_literals_reports_once(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "def f(a: str, b: str) -> str:\n    return '%s' + '%d' + a + b\n"})
    assert len(run_check(PERCENT, root)) == 1


# --------------------------------------------------------------------------
# check_nonalphabetical_literals
# --------------------------------------------------------------------------


def test_an_unsorted_string_list_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "NAMES = ['bird', 'aardvark']\n"})
    hits = run_check(LITERALS, root)
    assert [hit['rule'] for hit in hits] == ['non-alphabetical-literal']
    assert hits[0]['line'] == 1


def test_an_unsorted_frozenset_literal_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "NAMES = frozenset({'bird', 'aardvark'})\n"})
    assert len(run_check(LITERALS, root)) == 1


def test_a_sorted_string_list_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "NAMES = ['aardvark', 'bird']\n"})
    assert run_check(LITERALS, root) == []


def test_a_list_of_non_strings_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """Ordering is only meaningful where the members are names."""
    root = project({'src/probe/mod.py': 'SIZES = [2, 1]\n'})
    assert run_check(LITERALS, root) == []


def test_a_single_member_list_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "NAMES = ['bird']\n"})
    assert run_check(LITERALS, root) == []


def test_a_list_inside_a_function_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """The rule is about module-level configuration, not local working values."""
    root = project({'src/probe/mod.py': "def f() -> list[str]:\n    names = ['bird', 'aardvark']\n    return names\n"})
    assert run_check(LITERALS, root) == []


# --------------------------------------------------------------------------
# check_non_alphabetical_dict_keys
# --------------------------------------------------------------------------


def test_an_unsorted_dict_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "SCORERS = {'recall': 1, 'accuracy': 2}\n"})
    hits = run_check(DICT_KEYS, root)
    assert [hit['rule'] for hit in hits] == ['non-alphabetical-dict-keys']


def test_a_sorted_dict_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': "SCORERS = {'accuracy': 2, 'recall': 1}\n"})
    assert run_check(DICT_KEYS, root) == []


def test_a_dict_with_non_string_keys_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'CODES = {2: "b", 1: "a"}\n'})
    assert run_check(DICT_KEYS, root) == []


# --------------------------------------------------------------------------
# check_bare_parametric_annotation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    'source',
    [
        pytest.param('def f(values: dict) -> None:\n    return None\n', id='parameter'),
        pytest.param('def f() -> list:\n    return []\n', id='return'),
        pytest.param('VALUES: dict = {}\n', id='module-level'),
        pytest.param('def f(values: dict | None) -> None:\n    return None\n', id='union-member'),
    ],
)
def test_a_bare_builtin_generic_annotation_is_a_hit(source: str, project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': source})
    hits = run_check(BARE_PARAMETRIC, root)
    assert [hit['rule'] for hit in hits] == ['bare-parametric-annotation']


def test_a_parametric_annotation_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'def f(values: dict[str, int]) -> list[str]:\n    return []\n'})
    assert run_check(BARE_PARAMETRIC, root) == []


def test_one_line_with_two_bare_annotations_reports_once(project: Builder, run_check: Runner) -> None:
    """`reported` is keyed by line, so a signature cannot report twice."""
    root = project({'src/probe/mod.py': 'def f(a: dict, b: list) -> None:\n    return None\n'})
    assert len(run_check(BARE_PARAMETRIC, root)) == 1


# --------------------------------------------------------------------------
# check_duplicated_word
# --------------------------------------------------------------------------


def test_a_duplicated_word_in_a_comment_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': '# resolve the the settings first\nvalue = 1\n'})
    hits = run_check(DUPLICATED_WORD, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('duplicated-word', 1)]


def test_a_duplicated_word_in_a_docstring_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': '"""Resolve the the settings."""\n'})
    assert len(run_check(DUPLICATED_WORD, root)) == 1


def test_a_grammatical_repeat_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """`that that` and friends are ordinary English, not a typo."""
    root = project({'src/probe/mod.py': '# the value that that helper returns\n'})
    assert run_check(DUPLICATED_WORD, root) == []


def test_a_repeat_in_code_rather_than_prose_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """`not not value` repeats a word, but the line is neither comment nor string."""
    root = project({'src/probe/mod.py': 'def f(value: object) -> bool:\n    return not not value\n'})
    assert run_check(DUPLICATED_WORD, root) == []


# --------------------------------------------------------------------------
# check_bare_nonbuiltin_generic_annotation
# --------------------------------------------------------------------------


def test_a_bare_dotted_generic_annotation_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import multiprocessing\n\n\ndef f(q: multiprocessing.Queue) -> None:\n    return None\n'})
    hits = run_check(BARE_NONBUILTIN, root)
    assert [hit['rule'] for hit in hits] == ['bare-nonbuiltin-generic-annotation']
    assert 'multiprocessing.Queue' in hits[0]['variant']


def test_an_imported_alias_resolves_to_its_full_name(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'from queue import Queue\n\n\ndef f(q: Queue) -> None:\n    return None\n'})
    hits = run_check(BARE_NONBUILTIN, root)
    assert len(hits) == 1
    assert 'queue.Queue' in hits[0]['variant']


def test_a_parametric_non_builtin_annotation_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'import multiprocessing\n\n\ndef f(q: multiprocessing.Queue[int]) -> None:\n    return None\n'})
    assert run_check(BARE_NONBUILTIN, root) == []


def test_a_builtin_generic_is_left_to_the_other_check(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'def f(values: dict) -> None:\n    return None\n'})
    assert run_check(BARE_NONBUILTIN, root) == []


# --------------------------------------------------------------------------
# check_underscore_unpack_target_read
# --------------------------------------------------------------------------


def test_an_unpacked_underscore_name_that_is_read_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def f(pair: tuple[int, int]) -> int:
                _first, second = pair
                return _first + second
            """
        }
    )
    hits = run_check(UNPACK_READ, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('underscore-unpack-target-read', 2)]
    assert '_first' in hits[0]['variant']


def test_an_unpacked_underscore_name_that_is_never_read_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def f(pair: tuple[int, int]) -> int:
                _first, second = pair
                return second
            """
        }
    )
    assert run_check(UNPACK_READ, root) == []


def test_a_bare_underscore_target_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """Single `_` is the sanctioned throwaway."""
    root = project(
        {
            'src/probe/mod.py': """
            def f(pair: tuple[int, int]) -> int:
                _, second = pair
                return second
            """
        }
    )
    assert run_check(UNPACK_READ, root) == []


# --------------------------------------------------------------------------
# check_underscore_forloop_target_read
# --------------------------------------------------------------------------


def test_a_loop_target_marked_unused_but_read_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def f(items: list[int]) -> int:
                total = 0
                for _item in items:
                    total += _item
                return total
            """
        }
    )
    hits = run_check(FORLOOP_READ, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('underscore-forloop-target-read', 3)]


def test_a_loop_target_marked_unused_and_unused_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
            def f(items: list[int]) -> int:
                total = 0
                for _item in items:
                    total += 1
                return total
            """
        }
    )
    assert run_check(FORLOOP_READ, root) == []
