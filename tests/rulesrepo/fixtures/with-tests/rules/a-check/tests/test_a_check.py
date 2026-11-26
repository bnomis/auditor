def test_project_fixture_builds_a_tree(project) -> None:
    root = project({'src/probe/mod.py': 'x = 1\n'})
    assert (root / 'src' / 'probe' / 'mod.py').read_text(encoding='utf-8') == 'x = 1\n'
