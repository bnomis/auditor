"""Tests for `leading-underscore-binding`, shipped from an audit's request (2026-10-05).

The check replaces the five `destructure`/`forloop` text patterns, which saw
only the first two positions of a target, and adds every shape no regex could
anchor on: starred targets, later tuple positions, parameters and locals.
"""

import collections.abc
import pathlib
import typing

import pytest

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

BINDING = auditor.testing.load_check(__file__)
TEXT_PATTERNS = auditor.testing.load_check(__file__, 'text-patterns')


def found(hits: list[dict[str, typing.Any]]) -> list[tuple[int, str]]:
    return [(hit['line'], hit['variant']) for hit in hits if hit['rule'] == 'leading-underscore-binding']


# --------------------------------------------------------------------------
# The shapes it fires on
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        pytest.param('def f(pair):\n    first, _second = pair\n', [(2, 'binding `_second`')], id='second-position'),
        pytest.param('def f(row):\n    a, b, _c = row\n', [(2, 'binding `_c`')], id='third-position'),
        pytest.param('def f(row):\n    head, *_rest = row\n', [(2, 'binding `_rest`')], id='starred'),
        pytest.param('def f(row):\n    (a, (b, _c)) = row\n', [(2, 'binding `_c`')], id='nested-tuple'),
        pytest.param('def f():\n    _local = 1\n', [(2, 'binding `_local`')], id='local-assignment'),
        pytest.param('def f(rows):\n    for a, b, _c in rows:\n        pass\n', [(2, 'binding `_c`')], id='loop-third-position'),
        pytest.param('def f(rows):\n    for _i in rows:\n        pass\n', [(2, 'binding `_i`')], id='loop-short-name'),
        pytest.param('def f(rows):\n    return [_x for _x in rows]\n', [(2, 'binding `_x`')], id='comprehension'),
        pytest.param('def f(opener):\n    with opener() as _handle:\n        pass\n', [(2, 'binding `_handle`')], id='with-as'),
        pytest.param('def f(read):\n    if (_n := read()):\n        return 1\n', [(2, 'binding `_n`')], id='walrus'),
        pytest.param(
            'def f(run):\n    try:\n        run()\n    except ValueError as _error:\n        pass\n', [(4, '`except ... as` name `_error`')], id='except-as'
        ),
        pytest.param('def f(_settings):\n    return 1\n', [(1, 'parameter `_settings`')], id='parameter'),
        pytest.param('def f(*, _flag):\n    return 1\n', [(1, 'parameter `_flag`')], id='keyword-only-parameter'),
        pytest.param('def f(*_args, **_kwargs):\n    return 1\n', [(1, '`*` parameter `_args`'), (1, '`**` parameter `_kwargs`')], id='varargs'),
        pytest.param('handler = lambda _a, *_k: None\n', [(1, 'lambda parameter `_a`'), (1, 'lambda `*` parameter `_k`')], id='lambda'),
        pytest.param('class Thing:\n    _cache = {}\n', [(2, 'binding `_cache`')], id='class-attribute'),
        pytest.param('import sys\n\nif sys.platform:\n    _flag = 1\n', [(4, 'binding `_flag`')], id='module-level-under-if'),
        pytest.param('def f(value):\n    match value:\n        case [first, *_rest]:\n            pass\n', [(3, '`match` capture `_rest`')], id='match-star'),
        pytest.param(
            'def f(value):\n    match value:\n        case {"a": 1, **_rest}:\n            pass\n', [(3, '`match` capture `_rest`')], id='match-mapping-rest'
        ),
    ],
)
def test_each_binding_shape_fires(source: str, expected: list[tuple[int, str]], project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': source})
    assert found(run_check(BINDING, root)) == expected


def test_a_parameter_on_its_own_line_reports_that_line(project: Builder, run_check: Runner) -> None:
    """A multi-line signature reports the parameter's line, so an accept marker
    beside it answers for that parameter alone."""
    root = project(
        {
            'src/probe/mod.py': """
        def f(
            settings,
            _tmp,
        ):
            return settings
        """
        }
    )
    assert found(run_check(BINDING, root)) == [(3, 'parameter `_tmp`')]


# --------------------------------------------------------------------------
# The shapes it must not fire on
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    'source',
    [
        pytest.param('def f(pair, _):\n    first, _ = pair\n    for _ in pair:\n        pass\n', id='bare-underscore'),
        pytest.param('def f(*_, **__):\n    return 1\n', id='bare-underscore-varargs'),
        pytest.param('class Thing:\n    __slots__ = ()\n    __private = 1\n\n    def __init__(self):\n        pass\n', id='dunder-and-mangled'),
        pytest.param('def f(obj):\n    obj._attr = 1\n    obj.items[_KEY] = 2\n', id='attribute-and-subscript-targets'),
        pytest.param('def f():\n    def _helper():\n        pass\n\n    class _Local:\n        pass\n', id='def-and-class-names'),
        pytest.param('def f(value):\n    return value\n', id='plain-names'),
    ],
)
def test_a_non_binding_or_sanctioned_name_does_not_fire(source: str, project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': source})
    assert found(run_check(BINDING, root)) == []


@pytest.mark.parametrize('source', ['_CACHE = {}\n', '_cache: dict = {}\n'])
def test_a_module_level_assignment_is_left_to_the_const_regexes(source: str, project: Builder, run_check: Runner) -> None:
    """Reporting it under both rules would count one site twice."""
    root = project({'src/probe/mod.py': source})
    assert found(run_check(BINDING, root)) == []
    assert any(hit['rule'].startswith('leading-underscore-const-') for hit in run_check(TEXT_PATTERNS, root))


def test_a_module_level_unpack_is_reported_here(project: Builder, run_check: Runner) -> None:
    """Only a plain-name target belongs to the const regexes; an unpack does not
    match them, so this check owns it."""
    root = project({'src/probe/mod.py': 'first, _second = 1, 2\n'})
    assert found(run_check(BINDING, root)) == [(1, 'binding `_second`')]


def test_the_retired_regex_rules_no_longer_fire(project: Builder, run_check: Runner) -> None:
    """The text patterns must not report what this check now reports, or each
    site is counted twice."""
    root = project({'src/probe/mod.py': 'def f(pairs):\n    _a, b = pairs[0]\n    for _k, v in pairs:\n        pass\n'})
    retired = {hit['rule'] for hit in run_check(TEXT_PATTERNS, root)} & {
        'leading-underscore-destructure-first',
        'leading-underscore-destructure-second',
        'leading-underscore-forloop-first',
        'leading-underscore-forloop-second',
        'leading-underscore-forloop-single',
    }
    assert retired == set()
    assert len(found(run_check(BINDING, root))) == 2


# --------------------------------------------------------------------------
# Accept markers
# --------------------------------------------------------------------------


def test_a_scoped_marker_accepts_the_hit(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'def f(_hook):  # auditme: accept[leading-underscore-binding] name fixed by the caller\n    return 1\n'})
    hits = [hit for hit in run_check(BINDING, root) if hit['rule'] == 'leading-underscore-binding']
    assert len(hits) == 1
    assert hits[0]['accepted']
    assert hits[0]['accepted_reason'] == 'name fixed by the caller'


def test_a_marker_for_another_rule_does_not_accept_it(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'def f(_hook):  # auditme: accept[leading-underscore-self] unrelated\n    return 1\n'})
    hits = [hit for hit in run_check(BINDING, root) if hit['rule'] == 'leading-underscore-binding']
    assert len(hits) == 1
    assert not hits[0]['accepted']
