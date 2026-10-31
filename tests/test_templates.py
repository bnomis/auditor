"""Tests for the `/project-setup` templates."""

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
PLACEHOLDERS = {'AGENTS_REV', 'PROJECT_NAME', 'TEST_COMMAND'}
ALIAS_REWRITE = 'url."git@github-agents:bnomis/agents.git".insteadOf "git@github.com:bnomis/agents.git"'
AUDIT_COMMAND = 'pre-commit run auditme-all --hook-stage manual --all-files'
DEPLOY_KEY_LINES = (
    'AGENTS_DEPLOY_KEY',
    'Host github-agents',
    'IdentitiesOnly yes',
    'StrictHostKeyChecking yes',
    'api.github.com/meta',
    'if: always()',
    'rm -f ~/.ssh/agents_deploy_key',
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
    assert '- repo: git@github.com:bnomis/agents.git' in text
    assert 'rev: {{AGENTS_REV}}' in text
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
    assert text.index('{{TEST_COMMAND}}') < text.index('AGENTS_DEPLOY_KEY')
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
