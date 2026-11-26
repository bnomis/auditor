"""Tests for the checks of the `text-patterns` rule."""

import ast
import collections.abc
import pathlib
import typing

import hypothesis
import hypothesis.strategies
import pytest

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

TEXT_PATTERNS = auditor.testing.load_check(__file__)
CHECK_MODULE = auditor.testing.load_check_module(__file__)
NESTED_UNDERSCORE = CHECK_MODULE.check_nested_def_class


def rules_found(hits: list[dict[str, typing.Any]]) -> set[str]:
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


CODE_ONLY_FIXTURE_TEXT = {
    'aliased-imports': 'import numpy as np',
    'leading-underscore-attribute-access': 'return obj._attr',
    'leading-underscore-const-lower': '_cache = {}',
    'leading-underscore-const-upper': '_CACHE = {}',
    'leading-underscore-def-class': 'def _helper(): pass',
    'leading-underscore-self': 'self._value = 1',
    'legacy-typing': 'value: Optional[int] = None',
    'relative-import-nonpackage': 'from .base import Thing',
}


@pytest.mark.parametrize('rule', sorted(CODE_ONLY_FIXTURE_TEXT))
def test_pattern_in_plain_string_literal_does_not_fire(rule: str, project: Builder, run_check: Runner) -> None:
    """A fixture's source held in a plain string is data, not code (refinement 2026-11-21)."""
    text = CODE_ONLY_FIXTURE_TEXT[rule]
    source = f'SINGLE = {text!r}\nMULTI = """\n{text}\n"""\n'
    root = project({'src/probe/mod.py': source})
    assert rule not in rules_found(run_check(TEXT_PATTERNS, root))


@pytest.mark.parametrize('rule', sorted(CODE_ONLY_FIXTURE_TEXT))
def test_pattern_as_code_after_string_literal_still_fires(rule: str, project: Builder, run_check: Runner) -> None:
    text = CODE_ONLY_FIXTURE_TEXT[rule]
    source = f'NAME = "x"\n{text}\n'
    root = project({'src/probe/mod.py': source})
    assert rule in rules_found(run_check(TEXT_PATTERNS, root))


def test_pattern_in_docstring_still_fires(project: Builder, run_check: Runner) -> None:
    source = 'def f() -> None:\n    """Run:\n\n        self._value = 1\n    """\n'
    root = project({'src/probe/mod.py': source})
    assert 'leading-underscore-self' in rules_found(run_check(TEXT_PATTERNS, root))


def test_pattern_after_a_string_on_the_same_line_still_fires(project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': 'x = "a"; y = obj._attr\n'})
    assert 'leading-underscore-attribute-access' in rules_found(run_check(TEXT_PATTERNS, root))


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


@pytest.mark.parametrize(
    'source',
    [
        pytest.param('import os\n\nos._exit(1)\n', id='os-exit'),
        pytest.param('def f(point: object) -> object:\n    return point._asdict()\n', id='namedtuple-asdict'),
        pytest.param('def f(Point: type) -> object:\n    return Point._fields\n', id='namedtuple-fields'),
        pytest.param('def f(Point: type, row: list) -> object:\n    return Point._make(row)\n', id='namedtuple-make'),
        pytest.param('def f(point: object) -> object:\n    return point._replace(x=1)\n', id='namedtuple-replace'),
        pytest.param('def f(point: object) -> object:\n    """Return `point._asdict()` with `os._exit` untouched."""\n', id='docstring'),
    ],
)
def test_a_documented_public_stdlib_name_is_not_attribute_access(source: str, project: Builder, run_check: Runner) -> None:
    """`os._exit` and namedtuple's `_asdict`, `_fields`, `_make` and `_replace`
    are public API spelt with a leading underscore; there is nothing to rename."""
    root = project({'src/probe/mod.py': source})
    assert 'leading-underscore-attribute-access' not in rules_found(run_check(TEXT_PATTERNS, root))


@pytest.mark.parametrize(
    'source',
    [
        pytest.param('def f(obj: object) -> object:\n    return obj._attr\n', id='private-attribute'),
        pytest.param('import sys\n\nframe = sys._getframe(2)\n', id='sys-getframe'),
        pytest.param('import os\n\nvalue = os._private\n', id='other-os-name'),
        pytest.param('import os\n\nos._exit(obj._attr)\n', id='exempt-and-private-on-one-line'),
    ],
)
def test_the_stdlib_exemption_names_only_documented_names(source: str, project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': source})
    assert 'leading-underscore-attribute-access' in rules_found(run_check(TEXT_PATTERNS, root))


def test_the_collections_abc_set_is_not_legacy_typing(project: Builder, run_check: Runner) -> None:
    """`collections.abc.Set` is the modern ABC that `typing.AbstractSet` became,
    not the deprecated `typing.Set`; a project carried an accept marker for it."""
    root = project({'src/probe/mod.py': 'import collections.abc\n\nvalue: collections.abc.Set[str] = frozenset()\n'})
    assert 'legacy-typing' not in rules_found(run_check(TEXT_PATTERNS, root))


@pytest.mark.parametrize(
    'source',
    [
        pytest.param('import typing\n\nvalue: typing.Set[str] = set()\n', id='typing-set'),
        pytest.param('value: Set[str] = set()\n', id='bare-set'),
        pytest.param('import collections.abc\n\nvalue: collections.abc.Set[typing.Optional[int]] = frozenset()\n', id='other-name-same-line'),
    ],
)
def test_the_set_carve_out_is_only_for_collections_abc(source: str, project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': source})
    assert 'legacy-typing' in rules_found(run_check(TEXT_PATTERNS, root))


@pytest.mark.parametrize(
    'source',
    [
        pytest.param("value = 'a ' 'b {}'.format(1)\n", id='implicit-concatenation'),
        pytest.param("value = (\n    'a {}'\n    .format(1)\n)\n", id='format-on-a-later-line'),
    ],
)
def test_format_on_a_string_literal_is_a_hit(source: str, project: Builder, run_check: Runner) -> None:
    root = project({'src/probe/mod.py': source})
    hits = [hit for hit in run_check(TEXT_PATTERNS, root) if hit['rule'] == 'legacy-formatting-format']
    assert len(hits) == 1
    assert '.format' in hits[0]['evidence']


@pytest.mark.parametrize(
    'source',
    [
        pytest.param('def f(template: str) -> str:\n    return template.format(column=1)\n', id='name-receiver'),
        pytest.param('def f(fields: dict[str, str]) -> str:\n    return CONFIG.prefix.format(**fields)\n', id='attribute-receiver'),
        pytest.param('def f() -> None:\n    """Render with \'{}\'.format(x) - a recipe, not code."""\n', id='docstring'),
    ],
)
def test_format_on_a_runtime_template_is_not_a_hit(source: str, project: Builder, run_check: Runner) -> None:
    """A template read from config at run time can never be an f-string."""
    root = project({'src/probe/mod.py': source})
    assert 'legacy-formatting-format' not in rules_found(run_check(TEXT_PATTERNS, root))


CODE_LINE = hypothesis.strategies.text(alphabet=hypothesis.strategies.characters(blacklist_characters='\n\r', blacklist_categories=['Cs']), max_size=30)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    prefix=hypothesis.strategies.text(alphabet='abc =()', max_size=8),
    obj=hypothesis.strategies.from_regex(r'[a-z]{1,6}', fullmatch=True),
    attr=hypothesis.strategies.from_regex(r'_zz[a-z]{1,6}', fullmatch=True),
)
def test_stdlib_public_access_only_is_false_once_an_unlisted_underscore_access_is_added(prefix: str, obj: str, attr: str) -> None:
    check = CHECK_MODULE.is_stdlib_public_access_only
    hypothesis.assume(not CHECK_MODULE.ATTRIBUTE_ACCESS.search(prefix))
    assert check(prefix)
    assert not check(f'{prefix} {obj}.{attr}')


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(lines=hypothesis.strategies.lists(CODE_LINE, max_size=6))
def test_literal_format_lines_stay_inside_the_file(lines: list[str]) -> None:
    try:
        tree = ast.parse('\n'.join(lines))
    except SyntaxError, ValueError:
        assert CHECK_MODULE.literal_format_lines(None) == set()
        return
    found = CHECK_MODULE.literal_format_lines(tree)
    assert all(1 <= number <= len(lines) for number in found)


def parse_or_none(lines: list[str]) -> ast.Module | None:
    try:
        return ast.parse('\n'.join(lines))
    except SyntaxError:
        return None


MASK_SOURCES = hypothesis.strategies.lists(
    hypothesis.strategies.sampled_from(
        ['x = "abc"', 'y = 1', 'z = f(\'q r\', "s")', '# "note"', 'def f():', '    """doc"""', '    return "é ü"', 'w = """multi', 'line"""']
    ),
    max_size=6,
)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(lines=MASK_SOURCES)
def test_mask_string_literals_keeps_shape_only_blanks_and_is_idempotent(lines: list[str]) -> None:
    masked = CHECK_MODULE.mask_string_literals(lines, parse_or_none(lines))
    assert len(masked) == len(lines)
    for before, after in zip(lines, masked, strict=True):
        assert len(before) == len(after)
        assert all(new == old or new == ' ' for old, new in zip(before, after, strict=True))
    assert CHECK_MODULE.mask_string_literals(masked, parse_or_none(masked)) == masked


def rows(hits: list[dict[str, typing.Any]], rule: str) -> list[dict[str, typing.Any]]:
    return [hit for hit in hits if hit['rule'] == rule]


# --------------------------------------------------------------------------
# the nested def/class half of `text-patterns` - the shape it fires on
# --------------------------------------------------------------------------


def test_a_def_nested_in_a_function_fires(project: Builder, run_check: Runner) -> None:
    """The instances that prompted this all have exactly this shape: a conftest
    fixture returning a leading-underscore local factory."""
    root = project(
        {
            'src/probe/mod.py': """
        def make_item():
            def _build(value):
                return value
            return _build
        """
        }
    )
    hits = rows(run_check(NESTED_UNDERSCORE, root), 'leading-underscore-def-class')
    assert len(hits) == 1
    assert hits[0]['line'] == 2
    assert hits[0]['path'] == 'src/probe/mod.py'
    assert '_build' in hits[0]['variant']


def test_a_class_nested_in_a_function_fires(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
        def build_double():
            class _Tracking:
                pass
            return _Tracking
        """
        }
    )
    hits = rows(run_check(NESTED_UNDERSCORE, root), 'leading-underscore-def-class')
    assert len(hits) == 1
    assert 'class _Tracking' in hits[0]['variant']


def test_an_async_def_and_a_doubly_nested_def_both_fire(project: Builder, run_check: Runner) -> None:
    """The walk descends to any depth, so a helper inside a helper is found."""
    root = project(
        {
            'src/probe/mod.py': """
        def outer():
            async def _collect():
                return []
            def _middle():
                def _inner():
                    return 1
                return _inner
            return _collect, _middle
        """
        }
    )
    hits = rows(run_check(NESTED_UNDERSCORE, root), 'leading-underscore-def-class')
    assert sorted(hit['line'] for hit in hits) == [2, 4, 5]


# --------------------------------------------------------------------------
# the nested def/class half of `text-patterns` - carve-outs that must not fire
# --------------------------------------------------------------------------


def test_a_module_level_def_does_not_fire_here(project: Builder, run_check: Runner) -> None:
    """The regex form in check_text_patterns owns the module-level case.
    Firing here too would double-report every one of them."""
    root = project({'src/probe/mod.py': 'def _helper():\n    return 1\n'})
    assert rows(run_check(NESTED_UNDERSCORE, root), 'leading-underscore-def-class') == []


def test_a_method_does_not_fire(project: Builder, run_check: Runner) -> None:
    """A private method is a different naming question, answered by
    `leading-underscore-self` and by the project's own surface rules."""
    root = project(
        {
            'src/probe/mod.py': """
        def build():
            class _Holder:
                def _private(self):
                    return 1
            return _Holder
        """
        }
    )
    hits = rows(run_check(NESTED_UNDERSCORE, root), 'leading-underscore-def-class')
    # The nested class fires; the method inside it does not.
    assert [hit['line'] for hit in hits] == [2]
    assert 'class _Holder' in hits[0]['variant']


def test_a_dunder_does_not_fire(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
        def build():
            class _Holder:
                pass
            def __init_hook__():
                return 1
            return _Holder, __init_hook__
        """
        }
    )
    hits = rows(run_check(NESTED_UNDERSCORE, root), 'leading-underscore-def-class')
    # The single-underscore class fires; the dunder def does not.
    assert [hit['line'] for hit in hits] == [2]


def test_a_name_shadowing_an_outer_binding_does_not_fire(project: Builder, run_check: Runner) -> None:
    """A nested `_foo` where `_foo` also exists at module scope is a
    deliberate local override; renaming it would break the shadowing."""
    root = project(
        {
            'src/probe/mod.py': """
        def _shared():
            return 'module'

        def build():
            def _shared():
                return 'local'
            return _shared()
        """
        }
    )
    hits = rows(run_check(NESTED_UNDERSCORE, root), 'leading-underscore-def-class')
    assert [hit['line'] for hit in hits] == []


def test_a_clean_nested_helper_does_not_fire(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
        def make_item():
            def build(value):
                return value
            return build
        """
        }
    )
    assert rows(run_check(NESTED_UNDERSCORE, root), 'leading-underscore-def-class') == []


def test_a_scoped_accept_marker_accepts_the_nested_form(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
        def make_item():
            # auditme: accept[leading-underscore-def-class] deliberate, see the note above
            def _build(value):
                return value
            return _build
        """
        }
    )
    hits = rows(run_check(NESTED_UNDERSCORE, root), 'leading-underscore-def-class')
    assert len(hits) == 1
    assert hits[0]['accepted'] is True
    assert 'deliberate' in hits[0]['accepted_reason']


def test_a_marker_scoped_to_another_rule_does_not_accept_it(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/mod.py': """
        def make_item():
            # auditme: accept[literal-duplication] answers a different question
            def _build(value):
                return value
            return _build
        """
        }
    )
    hits = rows(run_check(NESTED_UNDERSCORE, root), 'leading-underscore-def-class')
    assert len(hits) == 1
    assert hits[0]['accepted'] is False
