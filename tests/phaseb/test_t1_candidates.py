"""Tests for the T1 lister: reasons, candidates, tests and the content hash."""

import ast
import textwrap

from auditme.phaseb import candidates


def _reasons(source: str, name: str = 'target') -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    for parent in ast.walk(tree):
        cls = parent if isinstance(parent, ast.ClassDef) else None
        body = parent.body if isinstance(parent, (ast.Module, ast.ClassDef)) else []
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                return candidates.t1_reasons(node, cls)
    raise AssertionError(name)


def test_if_gives_if() -> None:
    assert _reasons('def target(x):\n    if x:\n        return 1\n') == ['if']


def test_elif_gives_if() -> None:
    source = 'def target(x):\n    if x:\n        pass\n    elif x > 1:\n        pass\n'
    assert _reasons(source) == ['if']


def test_try_with_except_gives_try() -> None:
    assert _reasons('def target():\n    try:\n        pass\n    except ValueError:\n        pass\n') == ['try']


def test_try_star_with_handler_gives_try() -> None:
    assert _reasons('def target():\n    try:\n        pass\n    except* ValueError:\n        pass\n') == ['try']


def test_try_finally_alone_gives_nothing() -> None:
    assert _reasons('def target():\n    try:\n        pass\n    finally:\n        pass\n') == []


def test_match_gives_match() -> None:
    assert _reasons('def target(x):\n    match x:\n        case 1:\n            pass\n') == ['match']


STATE = """
    class Probe:
        def target(self):
            self.state = 1

        def other(self):
            if self.state == 2:
                pass
"""


def test_assignment_to_tested_attribute_gives_state() -> None:
    assert _reasons(STATE) == ['state']


def test_state_by_match_subject_and_comparison() -> None:
    match = 'class Probe:\n    def target(self):\n        self.mode = 1\n\n    def other(self):\n        match self.mode:\n            case 1:\n                pass\n'
    compare = 'class Probe:\n    def target(self):\n        self.mode = 1\n\n    def other(self):\n        return self.mode == 1\n'
    assert _reasons(match) == ['state']
    assert _reasons(compare) == ['state']


def test_attribute_no_other_method_tests_gives_nothing() -> None:
    source = 'class Probe:\n    def target(self):\n        self.count = 1\n\n    def other(self):\n        return self.count\n'
    assert _reasons(source) == []


def test_own_test_of_attribute_is_not_evidence() -> None:
    source = 'class Probe:\n    def target(self):\n        self.mode = 1\n        return self.mode == 1\n'
    assert _reasons(source) == []


def test_non_branching_constructs_give_nothing() -> None:
    source = 'def target(xs, x):\n    y = 1 if x else 2\n    zs = [z for z in xs if z]\n    assert x\n    return y, zs\n'
    assert _reasons(source) == []


def test_if_in_nested_def_gives_nothing() -> None:
    source = 'def target():\n    def inner(x):\n        if x:\n            pass\n    return inner\n'
    assert _reasons(source) == []


def test_reasons_in_fixed_order_without_repeats() -> None:
    source = """
        class Probe:
            def target(self, x):
                self.state = 1
                match x:
                    case 1:
                        pass
                try:
                    pass
                except ValueError:
                    pass
                if x:
                    pass
                if x > 1:
                    pass

            def other(self):
                if self.state:
                    pass
    """
    assert _reasons(source) == ['if', 'try', 'match', 'state']
