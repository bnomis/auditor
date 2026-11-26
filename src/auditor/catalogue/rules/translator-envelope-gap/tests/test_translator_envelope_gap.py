"""Tests for the checks of the `translator-envelope-gap` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

TRANSLATOR_GAP = auditor.testing.load_check(__file__)


def translator(catches: str) -> str:
    """A contextmanager that translates `catches` into the package error.

    Written as `@contextlib.contextmanager`, which is the shape one project's store
    uses: it serves as a decorator over a whole function and as a `with` block
    over part of one, from a single definition.
    """
    return f"""
    import collections.abc
    import contextlib
    import json
    import sqlite3


    class ProbeError(Exception):
        pass


    @contextlib.contextmanager
    def translate_store_errors(context: str) -> collections.abc.Generator[None]:
        try:
            yield
        except {catches} as exc:
            raise ProbeError(context) from exc
    """


def test_a_decorator_envelope_omitting_the_parser_error_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.translate_store_errors('failed to query store')
            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])
            """,
        }
    )
    hits = run_check(TRANSLATOR_GAP, root)
    assert [(hit['rule'], hit['path'], hit['line']) for hit in hits] == [('translator-envelope-gap', 'src/probe/query.py', 10)]
    assert "omits ['json.JSONDecodeError']" in hits[0]['variant']


def test_a_decorator_envelope_covering_the_parser_error_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/errors.py': translator('(sqlite3.Error, json.JSONDecodeError)'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.translate_store_errors('failed to query store')
            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])
            """,
        }
    )
    assert run_check(TRANSLATOR_GAP, root) == []


def test_a_decorator_catching_bare_exception_satisfies_every_branch(project: Builder, run_check: Runner) -> None:
    """The carve-out: a broad decorator envelope is as complete as a broad lexical one."""
    root = project(
        {
            'src/probe/errors.py': translator('Exception'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.translate_store_errors('failed to query store')
            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])
            """,
        }
    )
    assert run_check(TRANSLATOR_GAP, root) == []


def test_a_call_inside_a_lexical_try_belongs_to_the_lexical_checks(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.translate_store_errors('failed to query store')
            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                try:
                    return json.loads(row[0])
                except ValueError as exc:
                    raise probe.errors.ProbeError('bad config') from exc
            """,
        }
    )
    assert run_check(TRANSLATOR_GAP, root) == []


def test_a_contextmanager_block_is_an_envelope_too(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            def load_config(conn: sqlite3.Connection) -> dict:
                with probe.errors.translate_store_errors('failed to query store'):
                    row = conn.execute('SELECT config FROM runs').fetchone()
                    return json.loads(row[0])
            """,
        }
    )
    hits = run_check(TRANSLATOR_GAP, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('translator-envelope-gap', 10)]
    assert 'with translate_store_errors' in hits[0]['variant']


def test_a_parse_outside_the_contextmanager_block_has_no_envelope(project: Builder, run_check: Runner) -> None:
    """No envelope at all is `filesystem-op-without-envelope`'s question, not this one."""
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            def load_config(conn: sqlite3.Connection) -> dict:
                with probe.errors.translate_store_errors('failed to query store'):
                    row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])
            """,
        }
    )
    assert run_check(TRANSLATOR_GAP, root) == []


def test_an_undecorated_function_is_out_of_scope(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3


            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])
            """,
        }
    )
    assert run_check(TRANSLATOR_GAP, root) == []


def test_a_decorator_that_translates_nothing_is_not_an_envelope(project: Builder, run_check: Runner) -> None:
    """A decorator whose handler does not raise a `*Error` is not a translator."""
    root = project(
        {
            'src/probe/errors.py': """
            import collections.abc
            import contextlib
            import sqlite3


            @contextlib.contextmanager
            def timed(label: str) -> collections.abc.Generator[None]:
                try:
                    yield
                except sqlite3.Error:
                    return
            """,
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.timed('load')
            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])
            """,
        }
    )
    assert run_check(TRANSLATOR_GAP, root) == []


def test_a_filesystem_call_under_a_parser_only_envelope_is_a_hit(project: Builder, run_check: Runner) -> None:
    """The disk branch of the locked set, reached through the same envelope."""
    root = project(
        {
            'src/probe/errors.py': translator('json.JSONDecodeError'),
            'src/probe/query.py': """
            import pathlib

            import probe.errors


            @probe.errors.translate_store_errors('failed to write')
            def save(path: pathlib.Path, text: str) -> None:
                path.write_text(text)
            """,
        }
    )
    hits = run_check(TRANSLATOR_GAP, root)
    assert [(hit['rule'], hit['line']) for hit in hits] == [('translator-envelope-gap', 8)]
    assert "omits ['OSError']" in hits[0]['variant']


def test_a_function_parsing_several_columns_reports_its_earliest_call(project: Builder, run_check: Runner) -> None:
    """One finding per function, anchored to the first parse rather than to
    whichever the AST walk happened to reach first."""
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.translate_store_errors('failed to query store')
            def load_pair(conn: sqlite3.Connection) -> tuple[dict, dict]:
                left, right = conn.execute('SELECT a, b FROM runs').fetchone()
                return (
                    json.loads(left),
                    json.loads(right),
                )
            """,
        }
    )
    assert [hit['line'] for hit in run_check(TRANSLATOR_GAP, root)] == [11]


def test_a_marker_scoped_to_this_rule_accepts_the_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.translate_store_errors('failed to query store')
            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])  # auditme: accept[translator-envelope-gap] the column is written by this package
            """,
        }
    )
    hits = run_check(TRANSLATOR_GAP, root)
    assert [(hit['accepted'], hit['accepted_reason']) for hit in hits] == [(True, 'the column is written by this package')]


def test_a_marker_scoped_to_another_rule_does_not_accept_the_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/errors.py': translator('sqlite3.Error'),
            'src/probe/query.py': """
            import json
            import sqlite3

            import probe.errors


            @probe.errors.translate_store_errors('failed to query store')
            def load_config(conn: sqlite3.Connection) -> dict:
                row = conn.execute('SELECT config FROM runs').fetchone()
                return json.loads(row[0])  # auditme: accept[except-interpolation] unrelated decision
            """,
        }
    )
    assert [hit['accepted'] for hit in run_check(TRANSLATOR_GAP, root)] == [False]
