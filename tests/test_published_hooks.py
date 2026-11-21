"""Tests for `.pre-commit-hooks.yaml`: the full set of hooks, and the names hook.

The audit hooks' fields are tested beside the checker
(`claude/skills/auditme/tests/test_hooks_manifest.py`). The manifest is flat,
so a minimal reader stands in for a YAML parser.
"""

import pathlib
import subprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / '.pre-commit-hooks.yaml'

NAMES_HOOK = {
    'entry': 'bin/check-foreign-names.sh',
    'exclude': r'^uv\.lock$',
    'language': 'script',
    'stages': '[pre-commit, commit-msg]',
}


def read_manifest() -> dict[str, dict[str, str]]:
    hooks: dict[str, dict[str, str]] = {}
    current: dict[str, str] = {}
    for line in MANIFEST.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        text = line.removeprefix('- ').strip()
        key, _, value = text.partition(':')
        if line.startswith('- '):
            current = {}
        current[key.strip()] = value.strip()
        if key.strip() == 'id':
            hooks[current['id']] = current
    return hooks


def test_manifest_publishes_the_audit_and_names_hooks() -> None:
    assert sorted(read_manifest()) == ['auditme-all', 'auditme-changed', 'no-project-names']


def test_names_hook_fields() -> None:
    hook = read_manifest()['no-project-names']
    assert {key: hook[key] for key in NAMES_HOOK} == NAMES_HOOK


def test_names_hook_script_is_executable_in_the_index() -> None:
    staged = subprocess.run(
        ['git', 'ls-files', '-s', NAMES_HOOK['entry']],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert staged.startswith('100755 ')
