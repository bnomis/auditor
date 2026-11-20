"""Tests for docrefs: markdown sections and code-shaped names."""

import pathlib
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
