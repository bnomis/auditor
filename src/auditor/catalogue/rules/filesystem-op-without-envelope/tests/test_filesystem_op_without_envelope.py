"""Tests for the checks of the `filesystem-op-without-envelope` rule."""

import collections.abc
import pathlib

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

FS_NO_ENVELOPE = auditor.testing.load_check(__file__)


def test_a_public_entry_point_writing_with_no_try_is_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/store/errors.py': 'class StoreError(Exception):\n    pass\n',
            'src/probe/store/writer.py': """
            import pathlib


            def save(path: pathlib.Path, text: str) -> None:
                \"\"\"Write the text.

                Raises:
                    StoreError: on failure.
                \"\"\"
                path.write_text(text)
            """,
        }
    )
    hits = run_check(FS_NO_ENVELOPE, root)
    assert [hit['rule'] for hit in hits] == ['filesystem-op-without-envelope']
    assert '`write_text`' in hits[0]['variant']


def test_the_same_write_inside_a_try_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/store/errors.py': 'class StoreError(Exception):\n    pass\n',
            'src/probe/store/writer.py': """
            import pathlib

            import probe.store.errors


            def save(path: pathlib.Path, text: str) -> None:
                \"\"\"Write the text.

                Raises:
                    StoreError: on failure.
                \"\"\"
                try:
                    path.write_text(text)
                except OSError as exc:
                    raise probe.store.errors.StoreError('save failed') from exc
            """,
        }
    )
    assert run_check(FS_NO_ENVELOPE, root) == []


def test_an_internal_helper_may_let_oserror_propagate(project: Builder, run_check: Runner) -> None:
    """Only functions on the package's public error contract are flagged."""
    root = project(
        {
            'src/probe/store/errors.py': 'class StoreError(Exception):\n    pass\n',
            'src/probe/store/writer.py': 'import pathlib\n\n\ndef save(path: pathlib.Path, text: str) -> None:\n    path.write_text(text)\n',
        }
    )
    assert run_check(FS_NO_ENVELOPE, root) == []


def test_a_call_to_a_same_module_helper_that_wraps_oserror_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    """The helper holds the envelope, so the caller's `read_text(path)` is not a primitive."""
    root = project(
        {
            'src/probe/store/errors.py': 'class StoreError(Exception):\n    pass\n',
            'src/probe/store/reader.py': """
            import pathlib

            import probe.store.errors


            def read_text(path: pathlib.Path) -> str:
                try:
                    return path.read_text(encoding='utf-8')
                except OSError as exc:
                    raise probe.store.errors.StoreError('cannot read') from exc


            def load(path: pathlib.Path) -> str:
                \"\"\"Read the file.

                Raises:
                    StoreError: on failure.
                \"\"\"
                return read_text(path)
            """,
        }
    )
    assert run_check(FS_NO_ENVELOPE, root) == []


def test_a_same_module_helper_without_an_oserror_handler_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    root = project(
        {
            'src/probe/store/errors.py': 'class StoreError(Exception):\n    pass\n',
            'src/probe/store/reader.py': """
            import pathlib


            def read_text(path: pathlib.Path) -> str:
                return path.read_text(encoding='utf-8')


            def load(path: pathlib.Path) -> str:
                \"\"\"Read the file.

                Raises:
                    StoreError: on failure.
                \"\"\"
                return read_text(path)
            """,
        }
    )
    assert [hit['rule'] for hit in run_check(FS_NO_ENVELOPE, root)] == ['filesystem-op-without-envelope']
