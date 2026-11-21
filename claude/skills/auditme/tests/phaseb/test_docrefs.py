"""Tests for docrefs: markdown sections and code-shaped names."""

import pathlib
import subprocess
import textwrap

import pytest
from auditme import phaseb
from auditme.phaseb import docrefs


def _read(tmp_path: pathlib.Path, text: str, name: str = 'docs/guide.md') -> list[docrefs.DocSection]:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding='utf-8')
    return docrefs.read_sections(path, tmp_path)


def _tokens(sections: list[docrefs.DocSection]) -> list[str]:
    return [token for section in sections for _, token in section.names]


# sections


def test_nested_headings_join_with_separator(tmp_path):
    sections = _read(tmp_path, '# A\n\ntext\n\n## B\n\ntext\n\n### C\n\n## D\n')
    assert [s.heading_path for s in sections] == ['A', 'A > B', 'A > B > C', 'A > D']
    assert sections[0].doc == 'docs/guide.md'
    assert (sections[0].start, sections[0].end) == (1, 4)
    assert sections[-1].end == 11


def test_repeated_heading_path_gets_suffix(tmp_path):
    sections = _read(tmp_path, '# A\n## Usage\n## Usage\n## Usage\n')
    assert [s.heading_path for s in sections] == ['A', 'A > Usage', 'A > Usage#2', 'A > Usage#3']


def test_hash_line_in_fence_is_not_a_heading(tmp_path):
    sections = _read(tmp_path, '# A\n\n```sh\n# comment\n```\n')
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
    sections = _read(tmp_path, f'# A\n\nSee `{token}` here.\n')
    assert len(sections[0].names) == 1
    assert sections[0].names[0][0] == 3


def test_trailing_call_is_dropped_from_token(tmp_path):
    sections = _read(tmp_path, '# A\n\n`Probe.load(x, y)` and `run_it()`\n')
    assert _tokens(sections) == ['Probe.load', 'run_it']


@pytest.mark.parametrize('token', ['two words', 'a<b>', '/etc/probe.py', '~/probe.py', 'word', 'Word', 'x', '-x'])
def test_name_shapes_dropped(tmp_path, token):
    sections = _read(tmp_path, f'# A\n\nSee `{token}` here.\n')
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
    sections = _read(tmp_path, text, 'agents/specs/probe/spec.md')
    api = next(s for s in sections if s.heading_path == 'S > API')
    assert [token for _, token in api.names] == ['Probe', 'load', 'helper']
    assert [line for line, _ in api.names] == [6, 7, 11]
    other = next(s for s in sections if s.heading_path == 'S > Other')
    assert other.names == []


def test_names_come_back_in_line_order(tmp_path):
    sections = _read(tmp_path, '# A\n\n`b_two`\n\n`a_one`\n')
    assert [line for line, _ in sections[0].names] == [3, 5]


def test_backticks_in_other_fences_are_not_names(tmp_path):
    sections = _read(tmp_path, '# A\n\n```\n`max_size`\n```\n')
    assert sections[0].names == []


def test_undecodable_file_raises(tmp_path):
    path = tmp_path / 'bad.md'
    path.write_bytes(b'# A\n\xff\xfe\n')
    with pytest.raises(phaseb.PhaseBError):
        docrefs.read_sections(path, tmp_path)


def test_directory_raises(tmp_path):
    (tmp_path / 'dir.md').mkdir()
    with pytest.raises(phaseb.PhaseBError):
        docrefs.read_sections(tmp_path / 'dir.md', tmp_path)


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


def _git(root: pathlib.Path, *args: str) -> None:
    subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def indexed(tmp_path: pathlib.Path) -> tuple[pathlib.Path, docrefs.CorpusIndex]:
    for name, text in FIXTURE.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding='utf-8')
    _git(tmp_path, 'init', '-q')
    _git(tmp_path, 'add', '-A')
    (tmp_path / 'untracked.py').write_text('x = 1\n', encoding='utf-8')
    return tmp_path, docrefs.CorpusIndex.build(tmp_path)


def _resolve(indexed, token: str, doc: str = 'docs/guide.md') -> list[docrefs.DocTarget]:
    root, index = indexed
    return docrefs.resolve_name(token, root / doc, index)


def test_tracked_path_relative_to_root(indexed):
    (target,) = _resolve(indexed, 'src/pkg/mod.py')
    assert (target.kind, target.id, target.path) == ('file', 'src/pkg/mod.py', 'src/pkg/mod.py')


def test_tracked_directory_resolves(indexed):
    (target,) = _resolve(indexed, 'src/pkg')
    assert (target.kind, target.id) == ('directory', 'src/pkg')


def test_path_relative_to_the_document(indexed):
    (target,) = _resolve(indexed, 'sub/notes.md')
    assert (target.kind, target.id) == ('file', 'docs/sub/notes.md')


def test_untracked_path_does_not_resolve(indexed):
    assert _resolve(indexed, 'untracked.py') == []


def test_dotted_reexport_resolves_to_definition(indexed):
    (target,) = _resolve(indexed, 'pkg.run_it')
    assert (target.kind, target.id) == ('function', 'src/pkg/mod.py::run_it')


def test_unique_bare_function_and_class(indexed):
    (function,) = _resolve(indexed, 'run_it')
    (cls,) = _resolve(indexed, 'AppSettings')
    assert (function.kind, cls.kind) == ('function', 'class')
    assert cls.id == 'src/pkg/mod.py::AppSettings'


def test_bare_name_defined_twice_returns_both(indexed):
    found = _resolve(indexed, 'twice')
    assert sorted(t.kind for t in found) == ['function', 'method']
    assert sorted(t.id for t in found) == ['src/pkg/mod.py::Probe.twice', 'src/pkg/mod.py::twice']


def test_class_method_and_field(indexed):
    (method,) = _resolve(indexed, 'Probe.load')
    (field,) = _resolve(indexed, 'Probe.size')
    assert (method.kind, method.id) == ('method', 'src/pkg/mod.py::Probe.load')
    assert (field.kind, field.id) == ('field', 'src/pkg/mod.py::Probe.size')


def test_setting_through_a_settings_class(indexed):
    (target,) = _resolve(indexed, 'app.port')
    assert (target.kind, target.id) == ('setting', 'src/pkg/mod.py::Inner.port')


def test_dotted_key_with_no_settings_field_does_not_resolve(indexed):
    assert _resolve(indexed, 'nothing.port') == []
    assert _resolve(indexed, 'size.port') == []


def test_option_literal_passed_to_add_argument(indexed):
    (target,) = _resolve(indexed, '--limit')
    assert (target.kind, target.id) == ('option', 'src/pkg/mod.py::--limit')


def test_unknown_name_returns_empty(indexed):
    assert _resolve(indexed, 'never_defined') == []
    assert _resolve(indexed, '--never') == []


def test_each_target_carries_path_and_lines(indexed):
    (target,) = _resolve(indexed, 'run_it')
    assert target.path == 'src/pkg/mod.py'
    assert (target.start, target.end) == (5, 6)
    (method,) = _resolve(indexed, 'Probe.load')
    assert (method.start, method.end) == (16, 17)
    (static,) = (t for t in _resolve(indexed, 'twice') if t.kind == 'method')
    assert (static.start, static.end) == (19, 21)


def test_git_failure_raises(tmp_path):
    with pytest.raises(phaseb.PhaseBError):
        docrefs.CorpusIndex.build(tmp_path)
