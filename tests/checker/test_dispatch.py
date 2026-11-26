"""Tests for the string-dispatch chain walker."""

import ast

import auditor.dispatch


def first_if(source: str) -> ast.If:
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.If)
    return node


THREE_ARMS = """
if mode == 'a':
    pass
elif mode == 'b':
    pass
elif mode == 'c':
    pass
"""


def test_if_chain_returns_subject_and_tests() -> None:
    chain = auditor.dispatch.if_chain(first_if(THREE_ARMS), auditor.dispatch.extract_string_eq_var)
    assert chain is not None
    assert chain.subject == 'mode'
    assert len(chain.tests) == 3
    assert chain.orelse is None


def test_if_chain_returns_the_final_else_body() -> None:
    chain = auditor.dispatch.if_chain(
        first_if(THREE_ARMS + 'else:\n    x = 1\n'),
        auditor.dispatch.extract_string_eq_var,
    )
    assert chain is not None
    assert chain.orelse is not None
    assert len(chain.orelse) == 1


def test_if_chain_rejects_a_second_subject() -> None:
    source = THREE_ARMS.replace("elif mode == 'b'", "elif other == 'b'")
    assert auditor.dispatch.if_chain(first_if(source), auditor.dispatch.extract_string_eq_var) is None


def test_if_chain_rejects_a_test_the_callable_rejects() -> None:
    assert auditor.dispatch.if_chain(first_if(THREE_ARMS), lambda test: None) is None
