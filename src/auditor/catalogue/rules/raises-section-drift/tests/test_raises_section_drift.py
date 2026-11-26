"""Tests for the checks of the `raises-section-drift` rule."""

import collections.abc
import pathlib
import typing

import pytest

import auditor.testing

Builder = collections.abc.Callable[[dict[str, str]], pathlib.Path]
Runner = collections.abc.Callable[..., list[dict]]

RAISES_DRIFT = auditor.testing.load_check(__file__)

# --- raises-section-drift ---------------------------------------------------

ERRORS = """class ProbeError(Exception):
    pass


class ParseError(ProbeError):
    pass


class FetchError(ProbeError):
    pass
"""

CALLEE = """import probe.errors


def parse(text: str) -> int:
    \"\"\"Parse it.

    Raises:
        ParseError: the text is not a number.
    \"\"\"
    if not text.isdigit():
        raise probe.errors.ParseError(text)
    return int(text)
"""


def drift(project: Builder, run_check: Runner, caller: str) -> list[tuple[str, str]]:
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/parse.py': CALLEE, 'src/probe/use.py': caller})
    return sorted((hit['path'], hit['variant']) for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift')


def test_a_callee_error_missing_from_raises_is_a_hit(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors
import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        FetchError: nothing to load.
    \"\"\"
    if not text:
        raise probe.errors.FetchError('empty')
    return probe.parse.parse(text)
"""
    assert drift(project, run_check, caller) == [('src/probe/use.py', 'load: Raises: omits ParseError, declared by probe.parse.parse')]


def test_a_callee_error_names_the_callee_file_as_related(project: Builder, run_check: Runner) -> None:
    caller = """import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ValueError: never.
    \"\"\"
    return probe.parse.parse(text)
"""
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/parse.py': CALLEE, 'src/probe/use.py': caller})
    hits = [hit for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift']
    assert [hit.get('related') for hit in hits] == [['src/probe/parse.py']]


def test_a_combined_raises_entry_declares_each_name(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors
import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        FetchError, ParseError: nothing to load, or bad text.
    \"\"\"
    if not text:
        raise probe.errors.FetchError('empty')
    return probe.parse.parse(text)
"""
    assert drift(project, run_check, caller) == []


HANDLED = ERRORS + '\n\nHANDLED_ERRORS = (ParseError, FetchError)\n'


def tuple_drift(project: Builder, run_check: Runner, caller: str) -> list[tuple[str, str]]:
    root = project({'src/probe/errors.py': HANDLED, 'src/probe/parse.py': CALLEE, 'src/probe/use.py': caller})
    return sorted((hit['path'], hit['variant']) for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift')


def test_a_handler_naming_a_tuple_constant_catches_its_members(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors
import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        FetchError: nothing to load.
    \"\"\"
    if not text:
        raise probe.errors.FetchError('empty')
    try:
        return probe.parse.parse(text)
    except probe.errors.HANDLED_ERRORS:
        return 0
"""
    assert tuple_drift(project, run_check, caller) == []


def test_an_error_a_tuple_constant_handler_always_catches_is_an_extra(project: Builder, run_check: Runner) -> None:
    caller = """import probe.parse
from probe.errors import HANDLED_ERRORS


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ParseError: bad text.
    \"\"\"
    try:
        return probe.parse.parse(text)
    except HANDLED_ERRORS:
        return 0
"""
    assert tuple_drift(project, run_check, caller) == [('src/probe/use.py', 'load: Raises: declares ParseError, which never reaches the caller')]


def test_an_error_its_own_except_always_catches_is_an_extra(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors
import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ParseError: bad text.
    \"\"\"
    try:
        return probe.parse.parse(text)
    except probe.errors.ParseError:
        return 0
"""
    assert drift(project, run_check, caller) == [('src/probe/use.py', 'load: Raises: declares ParseError, which never reaches the caller')]


def test_a_handler_that_re_raises_does_not_catch(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors
import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ParseError: bad text.
    \"\"\"
    try:
        return probe.parse.parse(text)
    except probe.errors.ParseError:
        print('bad')
        raise
"""
    assert drift(project, run_check, caller) == []


@pytest.mark.parametrize('later', ['probe.errors.ProbeError', 'Exception'])
def test_a_re_raising_handler_wins_over_a_later_broader_one(project: Builder, run_check: Runner, later: str) -> None:
    caller = f"""import probe.errors
import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ParseError: bad text.
    \"\"\"
    try:
        return probe.parse.parse(text)
    except probe.errors.ParseError:
        raise
    except {later}:
        return 0
"""
    assert drift(project, run_check, caller) == []


def test_an_unresolved_call_under_a_re_raising_handler_is_not_an_extra(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors


def load(text: str, reader: object) -> int:
    \"\"\"Load it.

    Raises:
        ParseError: bad text.
    \"\"\"
    try:
        return reader(text)
    except probe.errors.ParseError:
        raise
    except Exception:
        return 0
"""
    assert drift(project, run_check, caller) == []


def test_catching_a_base_class_catches_its_subclasses(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors
import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        FetchError: nothing to load.
    \"\"\"
    if not text:
        raise probe.errors.FetchError('empty')
    try:
        return probe.parse.parse(text)
    except probe.errors.ProbeError:
        return 0
"""
    assert drift(project, run_check, caller) == []


def test_declaring_a_base_class_covers_its_subclasses(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors
import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ProbeError: anything the package raises.
    \"\"\"
    if not text:
        raise probe.errors.FetchError('empty')
    return probe.parse.parse(text)
"""
    assert drift(project, run_check, caller) == []


def test_a_method_call_on_self_follows_the_method(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors


class Loader:
    def check(self, text: str) -> None:
        \"\"\"Check it.

        Raises:
            FetchError: nothing to load.
        \"\"\"
        if not text:
            raise probe.errors.FetchError('empty')

    def load(self, text: str) -> str:
        \"\"\"Load it.

        Raises:
            ParseError: never raised here.
        \"\"\"
        self.check(text)
        return text
"""
    assert drift(project, run_check, caller) == [('src/probe/use.py', 'load: Raises: omits FetchError, declared by probe.use.Loader.check')]


def test_a_function_without_a_raises_section_is_not_this_check(project: Builder, run_check: Runner) -> None:
    caller = """import probe.parse


def load(text: str) -> int:
    \"\"\"Load it.\"\"\"
    return probe.parse.parse(text)
"""
    assert drift(project, run_check, caller) == []


def test_a_callee_in_another_package_is_not_followed(project: Builder, run_check: Runner) -> None:
    caller = """import other.parse


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ValueError: bad text.
    \"\"\"
    if not text:
        raise ValueError(text)
    return other.parse.parse(text)
"""
    assert drift(project, run_check, caller) == []


def test_a_scoped_marker_accepts_raises_drift(project: Builder, run_check: Runner) -> None:
    caller = """import probe.parse


def load(text: str) -> int:  # auditme: accept[raises-section-drift] callers never see a bad text
    \"\"\"Load it.

    Raises:
        ValueError: never.
    \"\"\"
    return probe.parse.parse(text)
"""
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/parse.py': CALLEE, 'src/probe/use.py': caller})
    hits = [hit for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift']
    assert [(hit['accepted'], hit['accepted_reason']) for hit in hits] == [(True, 'callers never see a bad text')]


def test_an_unreached_declared_error_with_no_handler_is_not_an_extra(project: Builder, run_check: Runner) -> None:
    """A declared error may reach through a call the check cannot resolve (an
    instance method, a callable passed in), so an extra needs positive evidence:
    a handler in the function that catches it."""
    caller = """import probe.errors


def load(reader, text: str) -> int:
    \"\"\"Load it.

    Raises:
        ParseError: the reader cannot parse the text.
    \"\"\"
    return reader.read(text)
"""
    assert drift(project, run_check, caller) == []


def test_a_function_re_exported_by_a_package_init_is_followed(project: Builder, run_check: Runner) -> None:
    caller = """import probe.tools


def load(text: str) -> int:
    \"\"\"Load it.

    Raises:
        ValueError: never.
    \"\"\"
    return probe.tools.parse(text)
"""
    root = project(
        {
            'src/probe/errors.py': ERRORS,
            'src/probe/tools/__init__.py': 'from probe.tools.parse import parse\n',
            'src/probe/tools/parse.py': CALLEE,
            'src/probe/use.py': caller,
        }
    )
    hits = [hit for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift']
    assert [hit['variant'] for hit in hits] == ['load: Raises: omits ParseError, declared by probe.tools.parse.parse']


def test_a_self_call_to_an_inherited_method_is_not_followed(project: Builder, run_check: Runner) -> None:
    """`self.load()` where the method is defined on a base class resolves to
    nothing in this class, and must not crash the sweep."""
    caller = """import base


class Loader(base.Base):
    def run(self) -> None:
        \"\"\"Run.

        Raises:
            ValueError: never.
        \"\"\"
        self.load()
"""
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/parse.py': CALLEE, 'src/probe/use.py': caller})
    assert run_check(RAISES_DRIFT, root) == []


def test_an_error_class_from_outside_the_package_is_not_a_domain_error(project: Builder, run_check: Runner) -> None:
    """A domain error is a class the package defines: `sqlite3.Error`, whose
    tail is just `Error`, and a third-party `*Error` are neither."""
    callee = """import sqlite3


def write(rows: list) -> None:
    \"\"\"Write them.

    Raises:
        sqlite3.Error: the database refused the rows.
        OtherLibError: the other library failed.
    \"\"\"
    del rows
"""
    caller = """import probe.write


def store(rows: list) -> None:
    \"\"\"Store them.

    Raises:
        ValueError: never.
    \"\"\"
    probe.write.write(rows)
"""
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/write.py': callee, 'src/probe/use.py': caller})
    assert run_check(RAISES_DRIFT, root) == []


# --- raises-section-drift: errors guarded by unset optional arguments -------

LOAD_CALLER = """import probe.errors
import probe.loader


def run(name: str, *args: str) -> int:
    \"\"\"Run it.

    Raises:
        FetchError: nothing to run.
    \"\"\"
    if not name:
        raise probe.errors.FetchError('empty')
    return {call}
"""

OPTIONAL_CALLEE = """import probe.errors

LIMIT = 3


def load({params}) -> int:
    \"\"\"Load it.

    Raises:
        ParseError: bad input.
    \"\"\"
{body}"""

GUARDED = '    if strict:\n        raise probe.errors.ParseError(name)\n    return 0\n'
OMITS_PARSE_ERROR = [('src/probe/use.py', 'run: Raises: omits ParseError, declared by probe.loader.load')]


def loader_drift(project: Builder, run_check: Runner, call: str, params: str = 'name: str, strict: bool = False', body: str = GUARDED) -> list[tuple[str, str]]:
    callee = OPTIONAL_CALLEE.format(params=params, body=body)
    caller = LOAD_CALLER.format(call=call)
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/loader.py': callee, 'src/probe/use.py': caller})
    return sorted((hit['path'], hit['variant']) for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift')


def test_a_call_leaving_the_guarding_optional_argument_unset_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    assert loader_drift(project, run_check, "probe.loader.load('x')") == []


def test_a_keyword_only_optional_guard_left_unset_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    assert loader_drift(project, run_check, "probe.loader.load('x')", params='name: str, *, strict: bool = False') == []


def test_a_self_call_leaving_the_optional_argument_unset_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors


class Runner:
    def load(self, name: str, strict: bool = False) -> int:
        \"\"\"Load it.

        Raises:
            ParseError: bad input.
        \"\"\"
        if strict:
            raise probe.errors.ParseError(name)
        return 0

    def run(self, name: str) -> int:
        \"\"\"Run it.

        Raises:
            FetchError: nothing to run.
        \"\"\"
        if not name:
            raise probe.errors.FetchError('empty')
        return self.load(name)
"""
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/use.py': caller})
    assert [hit for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift'] == []


def test_a_self_call_supplying_the_optional_argument_positionally_is_a_hit(project: Builder, run_check: Runner) -> None:
    caller = """import probe.errors


class Runner:
    def load(self, name: str, strict: bool = False) -> int:
        \"\"\"Load it.

        Raises:
            ParseError: bad input.
        \"\"\"
        if strict:
            raise probe.errors.ParseError(name)
        return 0

    def run(self, name: str) -> int:
        \"\"\"Run it.

        Raises:
            FetchError: nothing to run.
        \"\"\"
        if not name:
            raise probe.errors.FetchError('empty')
        return self.load(name, True)
"""
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/use.py': caller})
    hits = [hit['variant'] for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift']
    assert hits == ['run: Raises: omits ParseError, declared by probe.use.Runner.load']


@pytest.mark.parametrize('call', ["probe.loader.load('x', True)", "probe.loader.load('x', strict=True)", 'probe.loader.load(*args)'])
def test_a_call_supplying_the_optional_argument_is_still_a_hit(project: Builder, run_check: Runner, call: str) -> None:
    assert loader_drift(project, run_check, call) == OMITS_PARSE_ERROR


def test_a_guard_on_a_parameter_without_a_default_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    body = '    if not name.isdigit():\n        raise probe.errors.ParseError(name)\n    return 0\n'
    assert loader_drift(project, run_check, "probe.loader.load('x')", body=body) == OMITS_PARSE_ERROR


def test_a_guard_on_a_module_level_name_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    body = '    if LIMIT > 2:\n        raise probe.errors.ParseError(name)\n    return 0\n'
    assert loader_drift(project, run_check, "probe.loader.load('x')", body=body) == OMITS_PARSE_ERROR


def test_an_error_also_raised_outside_the_guard_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    body = GUARDED.replace('    return 0\n', '    raise probe.errors.ParseError(name)\n')
    assert loader_drift(project, run_check, "probe.loader.load('x')", body=body) == OMITS_PARSE_ERROR


def test_a_callee_only_documenting_the_error_is_still_a_hit(project: Builder, run_check: Runner) -> None:
    body = '    return probe.parse.parse(name)\n'
    assert loader_drift(project, run_check, "probe.loader.load('x')", body=body) == OMITS_PARSE_ERROR


# --- raises-section-drift: called nested functions --------------------------

NESTED_CALLER = """import probe.errors
import probe.parse


def run(text: str, other: str, strict: bool) -> int:
    \"\"\"Run it.

    Raises:
        {declared}: the text is bad.
    \"\"\"
{body}"""

REPRODUCTION = """    def attempt() -> int:
        try:
            return probe.parse.parse(text)
        except probe.errors.ParseError:
            if strict:
                raise
            return 0

    try:
        probe.parse.parse(other)
    except probe.errors.ParseError:
        pass
    return attempt()
"""


def nested_drift(project: Builder, run_check: Runner, body: str, declared: str = 'ParseError') -> list[tuple[str, str]]:
    return drift(project, run_check, NESTED_CALLER.format(declared=declared, body=body))


def test_a_called_nested_def_that_re_raises_keeps_the_declaration_reaching(project: Builder, run_check: Runner) -> None:
    assert nested_drift(project, run_check, REPRODUCTION) == []


def test_a_nested_def_never_called_adds_nothing(project: Builder, run_check: Runner) -> None:
    body = """    def attempt() -> int:
        return probe.parse.parse(text)

    return 0
"""
    assert nested_drift(project, run_check, body, declared='FetchError') == []


def test_a_nested_def_called_outside_any_try_reaches_the_subject(project: Builder, run_check: Runner) -> None:
    body = """    def attempt() -> int:
        return probe.parse.parse(text)

    return attempt()
"""
    assert nested_drift(project, run_check, body, declared='FetchError') == [
        ('src/probe/use.py', 'run: Raises: omits ParseError, declared by probe.parse.parse')
    ]


def test_a_nested_def_called_inside_a_catching_try_does_not_reach(project: Builder, run_check: Runner) -> None:
    body = """    def attempt() -> int:
        return probe.parse.parse(text)

    try:
        return attempt()
    except probe.errors.ParseError:
        return 0
"""
    assert nested_drift(project, run_check, body) == [('src/probe/use.py', 'run: Raises: declares ParseError, which never reaches the caller')]


def test_a_bare_raise_in_a_def_inside_a_handler_does_not_make_it_re_raise(project: Builder, run_check: Runner) -> None:
    body = """    try:
        return probe.parse.parse(text)
    except probe.errors.ParseError:
        def again() -> None:
            raise

        return 0
"""
    assert nested_drift(project, run_check, body) == [('src/probe/use.py', 'run: Raises: declares ParseError, which never reaches the caller')]


# --- raises-section-drift: Class.method() calls -----------------------------

PROBE_CLASS = """import probe.errors


class Probe:
    {decorator}
    def load({params}) -> int:
        \"\"\"Load it.

        Raises:
            ParseError: bad input.
        \"\"\"
{body}"""

PROBE_RAISES = '        raise probe.errors.ParseError(path)\n'
PROBE_GUARDED = '        if strict:\n            raise probe.errors.ParseError(path)\n        return 0\n'
PROBE_RUN = """

def run(path: str) -> int:
    \"\"\"Run it.

    Raises:
        FetchError: nothing to run.
    \"\"\"
    if not path:
        raise probe.errors.FetchError('empty')
{call}
"""
PROBE_IMPORT_CALLER = 'import probe.errors\nimport probe.conf\nfrom probe.conf import Probe\n' + PROBE_RUN
PROBE_OMITS = [('src/probe/use.py', 'run: Raises: omits ParseError, declared by probe.conf.Probe.load')]
PROBE_OMITS_LOCAL = [('src/probe/use.py', 'run: Raises: omits ParseError, declared by probe.use.Probe.load')]


def probe_class(decorator: str = '@classmethod', params: str = 'cls, path: str', body: str = PROBE_RAISES) -> str:
    return PROBE_CLASS.format(decorator=decorator, params=params, body=body)


def class_call_drift(project: Builder, run_check: Runner, files: dict[str, str]) -> list[tuple[str, str]]:
    root = project({'src/probe/errors.py': ERRORS, **files})
    return sorted((hit['path'], hit['variant']) for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift')


def test_a_class_method_call_on_a_class_in_the_same_module_is_a_hit(project: Builder, run_check: Runner) -> None:
    caller = probe_class() + PROBE_RUN.format(call='    return Probe.load(path)')
    assert class_call_drift(project, run_check, {'src/probe/use.py': caller}) == PROBE_OMITS_LOCAL


def test_a_class_method_call_on_an_imported_class_is_a_hit(project: Builder, run_check: Runner) -> None:
    files = {'src/probe/conf.py': probe_class(), 'src/probe/use.py': PROBE_IMPORT_CALLER.format(call='    return Probe.load(path)')}
    assert class_call_drift(project, run_check, files) == PROBE_OMITS


def test_a_handler_around_a_class_method_call_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    call = '    try:\n        return Probe.load(path)\n    except probe.errors.ParseError:\n        return 0'
    files = {'src/probe/conf.py': probe_class(), 'src/probe/use.py': PROBE_IMPORT_CALLER.format(call=call)}
    assert class_call_drift(project, run_check, files) == []


def test_a_classmethod_guarded_by_an_unset_optional_argument_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    conf = probe_class(params='cls, path: str, strict: bool = False', body=PROBE_GUARDED)
    files = {'src/probe/conf.py': conf, 'src/probe/use.py': PROBE_IMPORT_CALLER.format(call='    return Probe.load(path)')}
    assert class_call_drift(project, run_check, files) == []


def test_a_classmethod_with_the_guarding_argument_supplied_positionally_is_a_hit(project: Builder, run_check: Runner) -> None:
    conf = probe_class(params='cls, strict: bool = False', body=PROBE_GUARDED)
    files = {'src/probe/conf.py': conf, 'src/probe/use.py': PROBE_IMPORT_CALLER.format(call='    return Probe.load(True)')}
    assert class_call_drift(project, run_check, files) == PROBE_OMITS


def test_a_staticmethod_with_the_guarding_argument_supplied_is_a_hit(project: Builder, run_check: Runner) -> None:
    conf = probe_class(decorator='@staticmethod', params='path: str, strict: bool = False', body=PROBE_GUARDED)
    files = {'src/probe/conf.py': conf, 'src/probe/use.py': PROBE_IMPORT_CALLER.format(call='    return Probe.load(path, True)')}
    assert class_call_drift(project, run_check, files) == PROBE_OMITS


def test_a_staticmethod_guarded_by_an_unset_optional_argument_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    conf = probe_class(decorator='@staticmethod', params='path: str, strict: bool = False', body=PROBE_GUARDED)
    files = {'src/probe/conf.py': conf, 'src/probe/use.py': PROBE_IMPORT_CALLER.format(call='    return Probe.load(path)')}
    assert class_call_drift(project, run_check, files) == []


# --- raises-section-drift: section-less callees -----------------------------

INNER = """import probe.errors


def perform() -> int:
    \"\"\"Do it.

    Raises:
        ProbeError: always.
    \"\"\"
    raise probe.errors.ProbeError('x')
"""
WRAP_HEAD = 'import probe.errors\nimport probe.inner\n\n\n'
SUBJECT = """import probe.errors
import probe.wrap


def run(path: str) -> int:
    \"\"\"Run it.

    Raises:
{raises}
    \"\"\"
{call}
"""
WRAP_OMITS = 'run: Raises: omits ProbeError, '
VIA_WRAPPER = f'{WRAP_OMITS}declared by probe.inner.perform via probe.wrap.wrapper'


def wrapper_file(name: str = 'wrapper', callee: str = 'probe.inner.perform()', body: str | None = None) -> str:
    body = body if body is not None else f'    return {callee}'
    return f'{WRAP_HEAD}def {name}() -> int:\n    """Defer to the callee."""\n{body}\n'


def subject_file(call: str = '    return probe.wrap.wrapper()', raises: str = '        ValueError: never.', head: str = '') -> str:
    return head + SUBJECT.format(raises=raises, call=call)


def sectionless_hits(project: Builder, run_check: Runner, files: dict[str, str]) -> list[dict[str, typing.Any]]:
    root = project({'src/probe/errors.py': ERRORS, 'src/probe/inner.py': INNER, **files})
    return [hit for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift' and hit['path'] == 'src/probe/use.py']


def sectionless_variants(project: Builder, run_check: Runner, files: dict[str, str]) -> list[str]:
    return sorted(hit['variant'] for hit in sectionless_hits(project, run_check, files))


def test_a_section_less_wrapper_passes_the_callee_error_through(project: Builder, run_check: Runner) -> None:
    files = {'src/probe/wrap.py': wrapper_file(), 'src/probe/use.py': subject_file()}
    hits = sectionless_hits(project, run_check, files)
    assert [hit['variant'] for hit in hits] == [VIA_WRAPPER]
    assert hits[0]['related'] == ['src/probe/inner.py', 'src/probe/wrap.py']


def test_a_declared_error_or_its_base_covers_the_wrapper_error(project: Builder, run_check: Runner) -> None:
    body = "    raise probe.errors.ParseError('x')"
    for declared in ('ProbeError', 'ParseError'):
        files = {'src/probe/wrap.py': wrapper_file(body=body), 'src/probe/use.py': subject_file(raises=f'        {declared}: always.')}
        assert sectionless_variants(project, run_check, files) == []
    files = {'src/probe/wrap.py': wrapper_file(), 'src/probe/use.py': subject_file(raises='        ProbeError: always.')}
    assert sectionless_variants(project, run_check, files) == []


def test_a_handler_around_the_wrapper_call_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    call = '    try:\n        return probe.wrap.wrapper()\n    except probe.errors.ProbeError:\n        return 0'
    files = {'src/probe/wrap.py': wrapper_file(), 'src/probe/use.py': subject_file(call=call)}
    assert sectionless_variants(project, run_check, files) == []


def test_a_handler_inside_the_wrapper_is_not_a_hit(project: Builder, run_check: Runner) -> None:
    body = '    try:\n        return probe.inner.perform()\n    except probe.errors.ProbeError:\n        return 0'
    files = {'src/probe/wrap.py': wrapper_file(body=body), 'src/probe/use.py': subject_file()}
    assert sectionless_variants(project, run_check, files) == []


def test_a_wrapper_that_re_raises_is_a_hit(project: Builder, run_check: Runner) -> None:
    body = '    try:\n        return probe.inner.perform()\n    except probe.errors.ProbeError:\n        raise'
    files = {'src/probe/wrap.py': wrapper_file(body=body), 'src/probe/use.py': subject_file()}
    assert sectionless_variants(project, run_check, files) == [VIA_WRAPPER]


def test_a_raise_in_the_wrapper_is_named_as_raised_by_it(project: Builder, run_check: Runner) -> None:
    files = {'src/probe/wrap.py': wrapper_file(body="    raise probe.errors.ProbeError('x')"), 'src/probe/use.py': subject_file()}
    assert sectionless_variants(project, run_check, files) == [f'{WRAP_OMITS}raised by probe.wrap.wrapper']


def test_two_wrappers_are_followed_and_listed_in_call_order(project: Builder, run_check: Runner) -> None:
    wrap = (
        'import probe.inner\nimport probe.wrap\n\n\n'
        'def outer() -> int:\n    """Defer."""\n    return probe.wrap.inner()\n\n\n'
        'def inner() -> int:\n    """Defer."""\n    return probe.inner.perform()\n'
    )
    files = {'src/probe/wrap.py': wrap, 'src/probe/use.py': subject_file(call='    return probe.wrap.outer()')}
    assert sectionless_variants(project, run_check, files) == [
        f'{WRAP_OMITS}declared by probe.inner.perform via probe.wrap.outer, probe.wrap.inner',
    ]


def test_three_wrappers_are_past_the_depth_bound(project: Builder, run_check: Runner) -> None:
    wrap = (
        'import probe.inner\nimport probe.wrap\n\n\n'
        'def one() -> int:\n    """Defer."""\n    return probe.wrap.two()\n\n\n'
        'def two() -> int:\n    """Defer."""\n    return probe.wrap.three()\n\n\n'
        'def three() -> int:\n    """Defer."""\n    return probe.inner.perform()\n'
    )
    files = {'src/probe/wrap.py': wrap, 'src/probe/use.py': subject_file(call='    return probe.wrap.one()')}
    assert sectionless_variants(project, run_check, files) == []


def test_a_cycle_of_section_less_callees_ends(project: Builder, run_check: Runner) -> None:
    wrap = (
        'import probe.inner\nimport probe.wrap\n\n\n'
        'def a() -> int:\n    """Defer."""\n    return probe.wrap.b()\n\n\n'
        'def b() -> int:\n    """Defer."""\n    probe.wrap.a()\n    return probe.inner.perform()\n'
    )
    files = {'src/probe/wrap.py': wrap, 'src/probe/use.py': subject_file(call='    return probe.wrap.a()')}
    assert sectionless_variants(project, run_check, files) == [f'{WRAP_OMITS}declared by probe.inner.perform via probe.wrap.a, probe.wrap.b']


GUARDED_LOAD = """import probe.errors


def load(path: str, strict: bool = False) -> int:
    \"\"\"Load it.

    Raises:
        ProbeError: when strict.
    \"\"\"
    if strict:
        raise probe.errors.ProbeError(path)
    return 0
"""


def test_the_unset_optional_guard_applies_inside_a_wrapper(project: Builder, run_check: Runner) -> None:
    for argument, expected in (("'x'", []), ("'x', strict=True", [f'{WRAP_OMITS}declared by probe.load.load via probe.wrap.wrapper'])):
        wrap = wrapper_file(callee=f'probe.load.load({argument})').replace('import probe.inner', 'import probe.load')
        files = {'src/probe/load.py': GUARDED_LOAD, 'src/probe/wrap.py': wrap, 'src/probe/use.py': subject_file()}
        assert sectionless_variants(project, run_check, files) == expected


def test_a_declared_error_reached_through_a_wrapper_is_not_an_extra(project: Builder, run_check: Runner) -> None:
    call = '    try:\n        probe.inner.perform()\n    except probe.errors.ProbeError:\n        pass\n    return probe.wrap.wrapper()'
    files = {
        'src/probe/wrap.py': wrapper_file(),
        'src/probe/use.py': subject_file(call=call, raises='        ProbeError: always.', head='import probe.inner\n'),
    }
    assert sectionless_variants(project, run_check, files) == []


def test_a_marker_accepts_a_wrapper_hit(project: Builder, run_check: Runner) -> None:
    caller = subject_file().replace('def run(path: str) -> int:', 'def run(path: str) -> int:  # auditme: accept[raises-section-drift] wrapper is internal')
    files = {'src/probe/wrap.py': wrapper_file(), 'src/probe/use.py': caller}
    hits = sectionless_hits(project, run_check, files)
    assert [(hit['accepted'], hit['accepted_reason']) for hit in hits] == [(True, 'wrapper is internal')]


# --- raises-section-drift: first-party libraries outside the project --------

LIB_ERRORS = """class LibError(Exception):
    \"\"\"Raised by lib.\"\"\"
"""
LIB_LOAD = """import lib.errors


def load() -> int:
    \"\"\"Load it.

    Raises:
        LibError: always.
    \"\"\"
    raise lib.errors.LibError('x')
"""
LIB_WRAP = """import lib.load


def wrapped() -> int:
    \"\"\"Defer to load.\"\"\"
    return lib.load.load()
"""
LIB_SUBJECT = """import lib.errors
import lib.load
import lib.wrap


def run() -> int:
    \"\"\"Run it.

    Raises:
{raises}
    \"\"\"
{call}
"""
FIRST_PARTY_KEY = '[tool.auditme]\nfirst-party = ["../lib/src/lib"]\n'


def first_party_project(
    tmp_path: pathlib.Path,
    project: Builder,
    *,
    raises: str = '        ValueError: never.',
    call: str = '    return lib.load.load()',
    key: str = FIRST_PARTY_KEY,
    lib_extra: dict[str, str] | None = None,
) -> pathlib.Path:
    """Build `tmp_path/app` (the project) with a library beside it in `tmp_path/lib/src/lib`."""
    project(
        {
            'lib/src/lib/__init__.py': '',
            'lib/src/lib/errors.py': LIB_ERRORS,
            'lib/src/lib/load.py': LIB_LOAD,
            'lib/src/lib/wrap.py': LIB_WRAP,
            **{f'lib/src/lib/{name}': text for name, text in (lib_extra or {}).items()},
            'app/pyproject.toml': key,
            'app/src/probe/__init__.py': '',
            'app/src/probe/use.py': LIB_SUBJECT.format(raises=raises, call=call),
        }
    )
    return tmp_path / 'app'


def first_party_hits(root: pathlib.Path, run_check: Runner) -> list[dict[str, typing.Any]]:
    return [hit for hit in run_check(RAISES_DRIFT, root) if hit['rule'] == 'raises-section-drift']


def test_a_first_party_callee_declaring_an_error_the_section_omits_is_a_hit(tmp_path: pathlib.Path, project: Builder, run_check: Runner) -> None:
    root = first_party_project(tmp_path, project)
    hits = first_party_hits(root, run_check)
    assert [hit['variant'] for hit in hits] == ['run: Raises: omits LibError, declared by lib.load.load']
    assert hits[0]['path'] == 'src/probe/use.py'
    assert hits[0]['related'] == ['../lib/src/lib/load.py']


def test_a_declared_or_caught_first_party_error_is_no_hit(tmp_path: pathlib.Path, project: Builder, run_check: Runner) -> None:
    declared = first_party_project(tmp_path / 'a', project, raises='        LibError: always.')
    assert first_party_hits(declared, run_check) == []
    call = '    try:\n        return lib.load.load()\n    except lib.errors.LibError:\n        return 0'
    caught = first_party_project(tmp_path / 'b', project, call=call)
    assert first_party_hits(caught, run_check) == []


def test_a_section_less_first_party_wrapper_names_the_chain(tmp_path: pathlib.Path, project: Builder, run_check: Runner) -> None:
    root = first_party_project(tmp_path, project, call='    return lib.wrap.wrapped()')
    hits = first_party_hits(root, run_check)
    assert [hit['variant'] for hit in hits] == ['run: Raises: omits LibError, declared by lib.load.load via lib.wrap.wrapped']
    assert hits[0]['related'] == ['../lib/src/lib/load.py', '../lib/src/lib/wrap.py']


def test_without_the_key_a_first_party_callee_is_not_followed(tmp_path: pathlib.Path, project: Builder, run_check: Runner) -> None:
    root = first_party_project(tmp_path, project, key='[tool.auditme]\n')
    assert first_party_hits(root, run_check) == []


def test_no_hit_is_emitted_on_a_first_party_file(tmp_path: pathlib.Path, project: Builder, run_check: Runner) -> None:
    lib_subject = 'import lib.load\n\n\ndef again() -> int:\n    """Again.\n\n    Raises:\n        ValueError: never.\n    """\n    return lib.load.load()\n'
    root = first_party_project(tmp_path, project, lib_extra={'again.py': lib_subject})
    paths = {hit['path'] for hit in first_party_hits(root, run_check)}
    assert paths == {'src/probe/use.py'}
