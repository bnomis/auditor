"""Tests for `get-container-default-then-method-call`.

The defect: `dict.get`'s default fires only for an *absent* key, so
`x = payload.get('usage', {})` still binds `None` when the payload carries an
explicit `null`, and the next `x.get(...)` raises `AttributeError` rather than
the package's domain error.
"""

import collections.abc
import pathlib

import auditme.rules.error_handling

RULE = 'get-container-default-then-method-call'

CHECK = auditme.rules.error_handling.check_get_container_default_then_method_call

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]


def probe(body: str, path: str = 'src/probe/mod.py') -> dict[str, str]:
    return {path: body}


def test_dict_default_then_get_on_the_result_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})
                return usage.get('input_tokens', 0)
            """
        )
    )
    hits = run_check(CHECK, root)
    assert [(hit['rule'], hit['path'], hit['line']) for hit in hits] == [(RULE, 'src/probe/mod.py', 6)]
    assert not hits[0]['accepted']
    assert 'usage.get()' in hits[0]['variant']
    assert hits[0]['evidence'] == "usage = parsed.get('usage', {})"


def test_list_default_then_for_loop_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> list[str]:
                parsed = json.loads(payload)
                items = parsed.get('items', [])
                names = []
                for item in items:
                    names.append(str(item))
                return names
            """
        )
    )
    hits = run_check(CHECK, root)
    assert len(hits) == 1
    assert 'iteration over items' in hits[0]['variant']


def test_list_default_then_comprehension_is_a_hit(project: Builder, run_check: Runner) -> None:
    """`ast.comprehension` carries no lineno, so it needs its own case.

    An earlier draft filtered every use whose lineno sorted before the
    assignment's, and a comprehension - reporting lineno 0 by default - was
    silently dropped by that filter.
    """
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> list[str]:
                parsed = json.loads(payload)
                items = parsed.get('items', [])
                return [str(item) for item in items]
            """
        )
    )
    hits = run_check(CHECK, root)
    assert len(hits) == 1
    assert 'iteration over items' in hits[0]['variant']


def test_empty_tuple_default_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                tags = parsed.get('tags', ())
                return tags.count('x')
            """
        )
    )
    hits = run_check(CHECK, root)
    assert len(hits) == 1
    assert 'default ()' in hits[0]['variant']


def test_the_shape_inside_a_method_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            class Parser:
                def parse(self, parsed: dict) -> int:
                    usage = parsed.get('usage', {})
                    return usage.get('input_tokens', 0)
            """
        )
    )
    hits = run_check(CHECK, root)
    assert len(hits) == 1
    assert hits[0]['line'] == 3


def test_the_shape_at_module_scope_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import json

            PARSED = json.loads('{}')
            SECTION = PARSED.get('section', {})
            KEYS = list(SECTION.keys())
            """
        )
    )
    hits = run_check(CHECK, root)
    assert len(hits) == 1
    assert hits[0]['line'] == 4


def test_isinstance_guard_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """The cure one project actually applied at every site an audit raised.

    A predicate that did not recognise it would re-report each of those fixes
    as a fresh defect, which is the convergence failure the skill exists to
    prevent.
    """
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})
                if not isinstance(usage, dict):
                    raise ValueError('usage was not an object')
                return usage.get('input_tokens', 0)
            """
        )
    )
    assert run_check(CHECK, root) == []


def test_is_none_guard_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})
                if usage is None:
                    return 0
                return usage.get('input_tokens', 0)
            """
        )
    )
    assert run_check(CHECK, root) == []


def test_falsiness_guard_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})
                if not usage:
                    return 0
                return usage.get('input_tokens', 0)
            """
        )
    )
    assert run_check(CHECK, root) == []


def test_truth_test_as_the_whole_condition_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})
                if usage:
                    return usage.get('input_tokens', 0)
                return 0
            """
        )
    )
    assert run_check(CHECK, root) == []


def test_boolean_operand_guard_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})
                if usage and usage.get('input_tokens'):
                    return usage.get('input_tokens', 0)
                return 0
            """
        )
    )
    assert run_check(CHECK, root) == []


def test_the_documented_cure_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage') or {}
                return usage.get('input_tokens', 0)
            """
        )
    )
    assert run_check(CHECK, root) == []


def test_scalar_default_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> str:
                parsed = json.loads(payload)
                reason = parsed.get('reason', '')
                return reason.strip()
            """
        )
    )
    assert run_check(CHECK, root) == []


def test_non_empty_container_default_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """A documented non-goal: the same failure, deliberately out of scope."""
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {'input_tokens': 0})
                return usage.get('input_tokens', 0)
            """
        )
    )
    assert run_check(CHECK, root) == []


def test_constructor_call_default_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """Another documented non-goal: `dict()` rather than `{}`."""
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', dict())
                return usage.get('input_tokens', 0)
            """
        )
    )
    assert run_check(CHECK, root) == []


def test_subscripting_the_result_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """Also a documented non-goal - left to Phase B."""
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})
                return usage['input_tokens']
            """
        )
    )
    assert run_check(CHECK, root) == []


def test_a_result_that_is_never_a_receiver_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> dict:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})
                return usage
            """
        )
    )
    assert run_check(CHECK, root) == []


def test_a_use_in_another_scope_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """Scopes are searched separately, so two unrelated locals cannot pair up."""
    root = project(
        probe(
            """
            import json


            def load(payload: str) -> dict:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})
                return usage


            def report(usage: dict) -> int:
                return usage.get('input_tokens', 0)
            """
        )
    )
    assert run_check(CHECK, root) == []


def test_test_files_are_out_of_scope(project: Builder, run_check: Runner) -> None:
    """In a test the payload is a fixture the author wrote."""
    root = project(
        {
            'src/tests/test_parse.py': """
            def test_parse() -> None:
                parsed = {'usage': None}
                usage = parsed.get('usage', {})
                assert usage.get('input_tokens') is None
            """,
            'src/tests/conftest.py': """
            def helper(parsed: dict) -> int:
                usage = parsed.get('usage', {})
                return usage.get('input_tokens', 0)
            """,
        }
    )
    assert run_check(CHECK, root, package='tests') == []


def test_a_scoped_accept_marker_accepts_the_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})  # auditme: accept[get-container-default-then-method-call] schema forbids null
                return usage.get('input_tokens', 0)
            """
        )
    )
    hits = run_check(CHECK, root)
    assert len(hits) == 1
    assert hits[0]['accepted']
    assert hits[0]['accepted_reason'] == 'schema forbids null'


def test_an_accept_marker_on_the_line_above_accepts_the_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                # auditme: accept[get-container-default-then-method-call] schema forbids null
                usage = parsed.get('usage', {})
                return usage.get('input_tokens', 0)
            """
        )
    )
    hits = run_check(CHECK, root)
    assert len(hits) == 1
    assert hits[0]['accepted']


def test_a_marker_scoped_to_another_rule_does_not_accept_the_hit(project: Builder, run_check: Runner) -> None:
    """The whole point of scoped markers: a decision about one rule cannot
    silently excuse a different one."""
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})  # auditme: accept[failure-as-absence] the caller reads batch.error
                return usage.get('input_tokens', 0)
            """
        )
    )
    hits = run_check(CHECK, root)
    assert len(hits) == 1
    assert not hits[0]['accepted']


def test_an_unscoped_accept_marker_accepts_the_hit(project: Builder, run_check: Runner) -> None:
    """Retained so no pre-2026-08-12 marker needs migrating."""
    root = project(
        probe(
            """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})  # auditme: accept schema forbids null
                return usage.get('input_tokens', 0)
            """
        )
    )
    hits = run_check(CHECK, root)
    assert len(hits) == 1
    assert hits[0]['accepted']


def test_an_unparseable_file_is_skipped_rather_than_crashing(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/broken.py': 'def parse(:\n',
            'src/probe/mod.py': """
            import json


            def parse(payload: str) -> int:
                parsed = json.loads(payload)
                usage = parsed.get('usage', {})
                return usage.get('input_tokens', 0)
            """,
        }
    )
    hits = run_check(CHECK, root)
    assert [hit['path'] for hit in hits] == ['src/probe/mod.py']


def test_a_mapping_from_tomllib_is_skipped(project: Builder, run_check: Runner) -> None:
    """TOML has no null, so the default always fires for an absent key."""
    root = project(
        probe(
            """
            import tomllib


            def read(text: str) -> int:
                parsed = tomllib.loads(text)
                tool = parsed.get('tool', {})
                return len(tool.keys())


            def chained(text: str) -> int:
                project = tomllib.loads(text).get('project', {})
                return len(project.keys())
            """
        )
    )
    assert run_check(CHECK, root) == []


def test_a_toml_function_and_its_parameter_are_followed_one_level(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import tomllib


            def read(text: str) -> dict:
                if not text:
                    return {}
                return tomllib.loads(text)


            def tables(pyproject: dict) -> int:
                project = pyproject.get('project', {})
                return len(project.keys())


            def run(text: str) -> int:
                return tables(read(text))
            """
        )
    )
    assert run_check(CHECK, root) == []


def test_a_parameter_that_one_caller_fills_from_json_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        probe(
            """
            import json
            import tomllib


            def read(text: str) -> dict:
                return tomllib.loads(text)


            def tables(pyproject: dict) -> int:
                project = pyproject.get('project', {})
                return len(project.keys())


            def from_toml(text: str) -> int:
                return tables(read(text))


            def from_json(text: str) -> int:
                return tables(json.loads(text))
            """
        )
    )
    assert [hit['rule'] for hit in run_check(CHECK, root)] == [RULE]
