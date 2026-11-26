"""Tests for the error-handling helpers the catalogue rules and the listers share.

Each rule's own tests sit in its rule directory under `src/auditor/catalogue/rules/`.
"""

import ast
import collections.abc
import pathlib

import hypothesis
import hypothesis.strategies
import pytest

import auditor.api.errors
import auditor.core

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

# --------------------------------------------------------------------------
# package_class_parents and class_lineage
# --------------------------------------------------------------------------


def parse_modules(*sources: str) -> list[ast.Module]:
    return [ast.parse(source) for source in sources]


def test_package_class_parents_strips_module_prefix_from_bases() -> None:
    trees = parse_modules('class A(Base): pass\nclass B(mod.Base): pass\n')
    parents = auditor.api.errors.package_class_parents(trees)
    assert parents['A'] == {'Base'}
    assert parents['B'] == {'Base'}


def test_package_class_parents_pools_modules() -> None:
    trees = parse_modules('class A(Base): pass\n', 'class B(A): pass\n')
    parents = auditor.api.errors.package_class_parents(trees)
    assert set(parents) >= {'A', 'B'}
    assert parents['B'] == {'A'}


def test_class_lineage_is_transitive() -> None:
    parents = {'C': {'B'}, 'B': {'A'}, 'A': set()}
    assert auditor.api.errors.class_lineage('C', parents) == {'A', 'B', 'C'}


def test_class_lineage_terminates_on_a_cycle() -> None:
    parents = {'A': {'B'}, 'B': {'A'}}
    assert auditor.api.errors.class_lineage('A', parents) == {'A', 'B'}


def test_class_lineage_of_an_unknown_name_is_itself() -> None:
    assert auditor.api.errors.class_lineage('Nope', {}) == {'Nope'}


# --------------------------------------------------------------------------
# is_broad_handler
# --------------------------------------------------------------------------


def handler(clause: str) -> ast.ExceptHandler:
    tree = ast.parse(f'try:\n    pass\n{clause}:\n    pass\n')
    node = tree.body[0]
    assert isinstance(node, ast.Try)
    return node.handlers[0]


@pytest.mark.parametrize(
    'clause',
    ['except', 'except Exception', 'except BaseException', 'except (ValueError, Exception)', 'except (BaseException, OSError)'],
)
def test_is_broad_handler_true(clause: str) -> None:
    assert auditor.api.errors.is_broad_handler(handler(clause))


@pytest.mark.parametrize('clause', ['except ValueError', 'except (ValueError, OSError)'])
def test_is_broad_handler_false(clause: str) -> None:
    assert not auditor.api.errors.is_broad_handler(handler(clause))


def test_callable_short_name_reduces_each_invocation_form_to_its_bare_name() -> None:
    for source in ('translate', 'translate()', "translate('x')", 'errors.translate', "errors.translate('x')"):
        node = ast.parse(source, mode='eval').body
        assert auditor.api.errors.callable_short_name(node) == 'translate'
    assert auditor.api.errors.callable_short_name(ast.parse('fns[0]', mode='eval').body) is None


def test_raises_section_names_reads_each_entry_and_stops_at_the_section_end() -> None:
    doc = 'Summary.\n\nRaises:\n    ParseError: bad input.\n        Continuation line.\n    - store.WriteError: disk full.\n\nReturns:\n    LaterError is not an entry.\n'
    assert auditor.api.errors.raises_section_names(doc) == {'ParseError', 'WriteError'}
    assert auditor.api.errors.raises_section_names('No section here.') == set()


def test_raises_section_names_reads_every_name_of_a_combined_entry() -> None:
    doc = 'Summary.\n\nRaises:\n    ParseError, store.WriteError: bad input or a full disk.\n    - FetchError ,LoadError: none.\n'
    assert auditor.api.errors.raises_section_names(doc) == {'FetchError', 'LoadError', 'ParseError', 'WriteError'}


def test_translator_envelopes_map_a_translating_function_to_what_it_catches(project: Builder) -> None:
    root = project(
        {
            'src/pkg/__init__.py': '',
            'src/pkg/errors.py': (
                'def translate(fn):\n'
                '    try:\n'
                '        return fn()\n'
                '    except OSError:\n'
                '        raise PkgError("io")\n'
                '\n'
                'def probe():\n'
                '    try:\n'
                '        import extra\n'
                '    except ImportError:\n'
                '        extra = None\n'
            ),
        }
    )
    envelopes = auditor.api.errors.translator_envelopes(root / 'src')
    assert envelopes == {'translate': frozenset({'OSError'})}


IDENTIFIER = hypothesis.strategies.from_regex(r'[A-Za-z_][A-Za-z0-9_]{0,8}', fullmatch=True)
SPACES = hypothesis.strategies.text(alphabet=' \t', max_size=3)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    names=hypothesis.strategies.lists(hypothesis.strategies.from_regex(r'[A-Z][a-z]{0,6}Error', fullmatch=True), unique=True, max_size=5),
    bullet=hypothesis.strategies.sampled_from(['', '- ', '* ']),
    dotted=hypothesis.strategies.booleans(),
)
def test_raises_section_names_round_trips_a_generated_section(names: list[str], bullet: str, dotted: bool) -> None:
    body = [f'    {bullet}{"pkg.mod." if dotted else ""}{name}: raised when {name} applies\n        deeper OtherError line' for name in names]
    doc = 'Summary.\n\nRaises:\n' + '\n'.join(body) + '\n'
    found = auditor.api.errors.raises_section_names(doc)
    assert found == set(names)
    assert all(name.endswith('Error') for name in found)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    graph=hypothesis.strategies.dictionaries(
        hypothesis.strategies.sampled_from('abcdef'), hypothesis.strategies.sets(hypothesis.strategies.sampled_from('abcdef'), max_size=3), max_size=6
    ),
    name=hypothesis.strategies.sampled_from('abcdefg'),
)
def test_class_lineage_is_the_transitive_closure_and_terminates_on_cycles(graph: dict[str, set[str]], name: str) -> None:
    lineage = auditor.api.errors.class_lineage(name, graph)
    assert name in lineage
    assert all(parent in lineage for member in lineage for parent in graph.get(member, ()))
    expected = {name}
    grew = True
    while grew:
        grew = False
        for member in list(expected):
            for parent in graph.get(member, ()):
                if parent not in expected:
                    expected.add(parent)
                    grew = True
    assert lineage == expected


def test_tuple_constants_reads_class_tuples_and_leaves_out_ambiguous_names() -> None:
    trees = [
        ast.parse('HANDLED = (ParseError, errors.FetchError)\nCODES = (1, 2)\nTWICE = (ParseError,)\nTWICE = (FetchError,)\nCLASH = (ParseError,)\n'),
        ast.parse('CLASH = (FetchError,)\n'),
    ]
    assert auditor.api.errors.tuple_constants(trees) == {'HANDLED': frozenset({'FetchError', 'ParseError'})}
