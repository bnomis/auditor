"""Tests for the `/auditme-project-setup` templates."""

import pathlib
import re

SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
TEMPLATES = SKILL_DIR / 'templates'

NAMES = [
    'pre-commit-config.yaml',
    'ci.yml',
    'ci-audit-step.yml',
    'AGENTS.md',
    'CLAUDE.md',
    'TODO.md',
    'DONE.md',
    'claude/rules/README.md',
]
PLACEHOLDERS = {'AUDITOR_REV', 'PROJECT_NAME', 'TEST_COMMAND'}
ALIAS_REWRITE = 'url."git@github-auditor:bnomis/auditor.git".insteadOf "git@github.com:bnomis/auditor.git"'
AUDIT_COMMAND = 'pre-commit run auditme-all --hook-stage manual --all-files'
DEPLOY_KEY_LINES = (
    'AUDITOR_DEPLOY_KEY',
    'Host github-auditor',
    'IdentitiesOnly yes',
    'StrictHostKeyChecking yes',
    'api.github.com/meta',
    'if: always()',
    'rm -f ~/.ssh/auditor_deploy_key',
    ALIAS_REWRITE,
)


def read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding='utf-8')


def test_every_template_exists() -> None:
    for name in NAMES:
        assert (TEMPLATES / name).is_file(), name


def test_placeholders_are_the_documented_set() -> None:
    for name in NAMES:
        for found in re.findall(r'\{\{(\w+)\}\}', read(name)):
            assert found in PLACEHOLDERS, (name, found)


def test_claude_md_imports_agents_md() -> None:
    assert read('CLAUDE.md').strip() == '@AGENTS.md'


def test_pre_commit_config_structure() -> None:
    text = read('pre-commit-config.yaml')
    assert text.startswith('repos:\n')
    assert '- repo: git@github.com:bnomis/auditor.git' in text
    assert 'rev: {{AUDITOR_REV}}' in text
    for hook in (
        'ruff-check',
        'ruff-format',
        'shellcheck',
        'auditme-changed',
        'auditme-all',
    ):
        assert f'- id: {hook}' in text, hook


def test_ci_structure() -> None:
    text = read('ci.yml')
    for key in ('name:', 'on:', 'jobs:', 'steps:'):
        assert re.search(rf'^\s*{key}', text, re.MULTILINE), key
    for needle in (
        *DEPLOY_KEY_LINES,
        'uv sync',
        'pre-commit run --all-files',
        AUDIT_COMMAND,
        '{{TEST_COMMAND}}',
    ):
        assert needle in text, needle
    assert text.index('uv sync') < text.index(AUDIT_COMMAND)
    assert text.index('{{TEST_COMMAND}}') < text.index('AUDITOR_DEPLOY_KEY')
    assert 'ssh-keyscan' not in text
    assert 'ssh-keyscan' not in read('ci-audit-step.yml')


def test_ci_audit_step_shares_the_ci_deploy_key_step() -> None:
    step = read('ci-audit-step.yml')
    ci = read('ci.yml')
    for needle in (*DEPLOY_KEY_LINES, AUDIT_COMMAND):
        assert needle in step, needle
        assert needle in ci, needle
    assert not re.search(r'\{\{\w+\}\}', step)


def test_todo_and_done_have_title_headers() -> None:
    assert read('TODO.md').startswith('# TODO\n')
    assert read('DONE.md').startswith('# DONE\n')


def test_rules_readme_points_at_rule_scope() -> None:
    assert 'rule-scope.md' in read('claude/rules/README.md')


def test_templates_name_no_real_project_path_or_date() -> None:
    for name in NAMES:
        text = read(name)
        assert not re.search(r'/Users/|/home/|\b\d{4}-\d{2}-\d{2}\b', text), name


def test_new_projects_run_the_whole_tree_check_on_push() -> None:
    """`auditme-all` is published at the manual stage only, so a project adopted
    over a backlog is not blocked on push; a new project, which starts with none,
    switches the push stage on in its own config."""
    lines = read('pre-commit-config.yaml').splitlines()
    start = lines.index('      - id: auditme-all')
    assert lines[start + 1] == '        stages: [manual, pre-push]'
    changed = lines.index('      - id: auditme-changed')
    assert lines[changed + 1] == '      - id: auditme-all'


def test_ci_python_can_run_the_checker() -> None:
    """The hooks run the checker with the `python3` on PATH, and the checker
    uses syntax of this repository's `requires-python` (PEP 758 `except A, B:`),
    so CI must install that minor version."""
    pyproject = (SKILL_DIR.parents[2] / 'pyproject.toml').read_text(encoding='utf-8')
    minor = re.search(r'requires-python = ">=(\d+\.\d+)', pyproject).group(1)
    assert f'python-version: "{minor}"' in read('ci.yml')


def test_ci_installs_pre_commit_before_running_it() -> None:
    text = read('ci.yml')
    assert 'uv tool install pre-commit' in text
    assert text.index('uv tool install pre-commit') < text.index('pre-commit run')


def test_ci_puts_the_synced_tools_on_path() -> None:
    """After `uv sync` the project's locked tools are in `.venv/bin`; the
    checker runs `.venv/bin/ruff` itself, and the step puts the same tools on
    PATH for every other hook before the audit runs."""
    text = read('ci.yml')
    line = 'echo "$PWD/.venv/bin" >> "$GITHUB_PATH"'
    assert line in text
    assert text.index('uv sync') < text.index(line) < text.index(AUDIT_COMMAND)
