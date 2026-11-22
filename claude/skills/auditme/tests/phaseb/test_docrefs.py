"""Tests for docrefs: markdown sections and code-shaped names."""

import subprocess
import textwrap
import typing

import auditme.core
import auditme.phaseb
import auditme.phaseb.docrefs
import hypothesis
import hypothesis.strategies
import pytest

if typing.TYPE_CHECKING:
    import pathlib


def read_sections(tmp_path: pathlib.Path, text: str, name: str = 'docs/guide.md') -> list[auditme.phaseb.docrefs.DocSection]:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding='utf-8')
    return auditme.phaseb.docrefs.read_sections(path, tmp_path)


def section_tokens(sections: list[auditme.phaseb.docrefs.DocSection]) -> list[str]:
    return [token for section in sections for _, token in section.names]


# sections


def test_nested_headings_join_with_separator(tmp_path):
    sections = read_sections(tmp_path, '# A\n\ntext\n\n## B\n\ntext\n\n### C\n\n## D\n')
    assert [s.heading_path for s in sections] == ['A', 'A > B', 'A > B > C', 'A > D']
    assert sections[0].doc == 'docs/guide.md'
    assert (sections[0].start, sections[0].end) == (1, 4)
    assert sections[-1].end == 11


def test_repeated_heading_path_gets_suffix(tmp_path):
    sections = read_sections(tmp_path, '# A\n## Usage\n## Usage\n## Usage\n')
    assert [s.heading_path for s in sections] == ['A', 'A > Usage', 'A > Usage#2', 'A > Usage#3']


def test_hash_line_in_fence_is_not_a_heading(tmp_path):
    sections = read_sections(tmp_path, '# A\n\n```sh\n# comment\n```\n')
    assert [s.heading_path for s in sections] == ['A']


@pytest.mark.parametrize(
    'token',
    [
        'src/pkg/mod',
        'mod.py',
        'a.md',
        'a.toml',
        'a.yaml',
        'a.yml',
        'a.json',
        'a.sh',
        'a.txt',
        'a.lock',
        '--limit',
        'max_size',
        'pkg.mod',
        'AppSettings',
        'run_it()',
        'Probe.load(x, y)',
    ],
)
def test_name_shapes_kept(tmp_path, token):
    sections = read_sections(tmp_path, f'# A\n\nSee `{token}` here.\n')
    assert len(sections[0].names) == 1
    assert sections[0].names[0][0] == 3


def test_trailing_call_is_dropped_from_token(tmp_path):
    sections = read_sections(tmp_path, '# A\n\n`Probe.load(x, y)` and `run_it()`\n')
    assert section_tokens(sections) == ['Probe.load', 'run_it']


@pytest.mark.parametrize('token', ['two words', 'a<b>', '/etc/probe.py', '~/probe.py', 'word', 'Word', 'x', '-x'])
def test_name_shapes_dropped(tmp_path, token):
    sections = read_sections(tmp_path, f'# A\n\nSee `{token}` here.\n')
    assert sections[0].names == []


def test_def_and_class_lines_in_api_fence_count(tmp_path):
    text = """\
        # S

        ## API

        ```python
        class Probe:
            def load(self) -> int:
                ...


        def helper(x):
            ...
        ```

        ## Other

        ```python
        def ignored(x):
            ...
        ```
    """
    sections = read_sections(tmp_path, text, 'agents/specs/probe/spec.md')
    api = next(s for s in sections if s.heading_path == 'S > API')
    assert [token for _, token in api.names] == ['Probe', 'load', 'helper']
    assert [line for line, _ in api.names] == [6, 7, 11]
    other = next(s for s in sections if s.heading_path == 'S > Other')
    assert other.names == []


def test_names_come_back_in_line_order(tmp_path):
    sections = read_sections(tmp_path, '# A\n\n`b_two`\n\n`a_one`\n')
    assert [line for line, _ in sections[0].names] == [3, 5]


def test_backticks_in_other_fences_are_not_names(tmp_path):
    sections = read_sections(tmp_path, '# A\n\n```\n`max_size`\n```\n')
    assert sections[0].names == []


def test_undecodable_file_raises(tmp_path):
    path = tmp_path / 'bad.md'
    path.write_bytes(b'# A\n\xff\xfe\n')
    with pytest.raises(auditme.phaseb.PhaseBError):
        auditme.phaseb.docrefs.read_sections(path, tmp_path)


def test_directory_raises(tmp_path):
    (tmp_path / 'dir.md').mkdir()
    with pytest.raises(auditme.phaseb.PhaseBError):
        auditme.phaseb.docrefs.read_sections(tmp_path / 'dir.md', tmp_path)


# resolution

FIXTURE = {
    'AGENTS.md': '# Agents\n',
    'agents/specs/probe/spec.md': '# Probe\n',
    'docs/guide.md': '# Guide\n',
    'docs/sub/notes.md': '# Notes\n',
    'src/pkg/__init__.py': 'from pkg.mod import run_it\n',
    'src/pkg/mod.py': """
        import argparse


        def run_it():
            return 1


        def twice():
            return 1


        class Probe:
            size: int = 3

            def load(self):
                return 2

            @staticmethod
            def twice():
                return 3


        class Inner:
            port: int = 80


        class AppSettings(BaseSettings):
            app: Inner = Inner()
            name: str = 'x'


        def parse():
            parser = argparse.ArgumentParser()
            parser.add_argument('--limit', type=int)
            return parser
    """,
}


def run_git(root: pathlib.Path, *args: str) -> None:
    subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def indexed(tmp_path: pathlib.Path) -> tuple[pathlib.Path, auditme.phaseb.docrefs.CorpusIndex]:
    for name, text in FIXTURE.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding='utf-8')
    run_git(tmp_path, 'init', '-q')
    run_git(tmp_path, 'add', '-A')
    (tmp_path / 'untracked.py').write_text('x = 1\n', encoding='utf-8')
    return tmp_path, auditme.phaseb.docrefs.CorpusIndex.build(tmp_path)


def resolve_token(indexed, token: str, doc: str = 'docs/guide.md') -> list[auditme.phaseb.docrefs.DocTarget]:
    root, index = indexed
    return auditme.phaseb.docrefs.read_name_targets(token, root / doc, index)


def test_one_index_build_resolves_the_roots_once(indexed, monkeypatch):
    root, _ = indexed
    auditme.core.clear_source_cache()
    calls: list[pathlib.Path] = []
    real = auditme.core.declared_roots

    def counting(scope):
        calls.append(scope)
        return real(scope)

    monkeypatch.setattr(auditme.core, 'declared_roots', counting)
    auditme.phaseb.docrefs.CorpusIndex.build(root)
    assert len(calls) == 1


def test_tracked_path_relative_to_root(indexed):
    (target,) = resolve_token(indexed, 'src/pkg/mod.py')
    assert (target.kind, target.id, target.path) == ('file', 'src/pkg/mod.py', 'src/pkg/mod.py')


def test_tracked_directory_resolves(indexed):
    (target,) = resolve_token(indexed, 'src/pkg')
    assert (target.kind, target.id) == ('directory', 'src/pkg')


def test_path_relative_to_the_document(indexed):
    (target,) = resolve_token(indexed, 'sub/notes.md')
    assert (target.kind, target.id) == ('file', 'docs/sub/notes.md')


def test_untracked_path_does_not_resolve(indexed):
    assert resolve_token(indexed, 'untracked.py') == []


def test_dotted_reexport_resolves_to_definition(indexed):
    (target,) = resolve_token(indexed, 'pkg.run_it')
    assert (target.kind, target.id) == ('function', 'src/pkg/mod.py::run_it')


def test_unique_bare_function_and_class(indexed):
    (function,) = resolve_token(indexed, 'run_it')
    (cls,) = resolve_token(indexed, 'AppSettings')
    assert (function.kind, cls.kind) == ('function', 'class')
    assert cls.id == 'src/pkg/mod.py::AppSettings'


def test_bare_name_defined_twice_returns_both(indexed):
    found = resolve_token(indexed, 'twice')
    assert sorted(t.kind for t in found) == ['function', 'method']
    assert sorted(t.id for t in found) == ['src/pkg/mod.py::Probe.twice', 'src/pkg/mod.py::twice']


def test_class_method_and_field(indexed):
    (method,) = resolve_token(indexed, 'Probe.load')
    (field,) = resolve_token(indexed, 'Probe.size')
    assert (method.kind, method.id) == ('method', 'src/pkg/mod.py::Probe.load')
    assert (field.kind, field.id) == ('field', 'src/pkg/mod.py::Probe.size')


def test_setting_through_a_settings_class(indexed):
    (target,) = resolve_token(indexed, 'app.port')
    assert (target.kind, target.id) == ('setting', 'src/pkg/mod.py::Inner.port')


def test_dotted_key_with_no_settings_field_does_not_resolve(indexed):
    assert resolve_token(indexed, 'nothing.port') == []
    assert resolve_token(indexed, 'size.port') == []


def test_option_literal_passed_to_add_argument(indexed):
    (target,) = resolve_token(indexed, '--limit')
    assert (target.kind, target.id) == ('option', 'src/pkg/mod.py::--limit')


def test_unknown_name_returns_empty(indexed):
    assert resolve_token(indexed, 'never_defined') == []
    assert resolve_token(indexed, '--never') == []


def test_each_target_carries_path_and_lines(indexed):
    (target,) = resolve_token(indexed, 'run_it')
    assert target.path == 'src/pkg/mod.py'
    assert (target.start, target.end) == (5, 6)
    (method,) = resolve_token(indexed, 'Probe.load')
    assert (method.start, method.end) == (16, 17)
    (static,) = (t for t in resolve_token(indexed, 'twice') if t.kind == 'method')
    assert (static.start, static.end) == (19, 21)


def test_git_failure_raises(tmp_path):
    with pytest.raises(auditme.phaseb.PhaseBError):
        auditme.phaseb.docrefs.CorpusIndex.build(tmp_path)


IDENT = hypothesis.strategies.from_regex(r'[A-Za-z_][A-Za-z0-9_]{0,8}', fullmatch=True)


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    ident=IDENT, indent=hypothesis.strategies.text(alphabet=' ', max_size=4), kind=hypothesis.strategies.sampled_from(['def {}(', 'class {}(', 'class {}:'])
)
def test_api_fence_name_recovers_the_defined_name(ident: str, indent: str, kind: str) -> None:
    assert auditme.phaseb.docrefs.api_fence_name(indent + kind.format(ident)) == ident


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(text=hypothesis.strategies.text(alphabet='abc xyz=()', max_size=15))
def test_api_fence_name_is_none_for_other_lines(text: str) -> None:
    hypothesis.assume(not text.lstrip().startswith(('def', 'class', 'async')))
    assert auditme.phaseb.docrefs.api_fence_name(text) is None


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(
    lines=hypothesis.strategies.lists(
        hypothesis.strategies.sampled_from(['plain', 'has `tok_a` here', '```', 'in `fenced_tok`', 'two `a.b` and ` c_d `', '`  `']), max_size=10
    ),
)
def test_backticked_tokens_are_in_range_stripped_and_outside_fences(lines: list[str]) -> None:
    found = auditme.phaseb.docrefs.backticked_tokens(lines, 1, len(lines))
    numbers = [entry[0] for entry in found]
    assert numbers == sorted(numbers)
    fenced = False
    inside = set()
    for number, line in enumerate(lines, 1):
        if line == '```':
            fenced = not fenced
        elif fenced:
            inside.add(number)
    for number, token in found:
        assert 1 <= number <= len(lines)
        assert token
        assert token == token.strip()
        assert number not in inside


@hypothesis.settings(max_examples=20, deadline=10000)
@hypothesis.given(token=hypothesis.strategies.text(alphabet='abcXYZ_./~-<> ()', max_size=14))
def test_code_shaped_is_idempotent_and_has_no_space(token: str) -> None:
    shaped = auditme.phaseb.docrefs.code_shaped(token)
    if shaped is None:
        return
    assert ' ' not in shaped
    assert '<' not in shaped
    assert auditme.phaseb.docrefs.code_shaped(shaped) == shaped
