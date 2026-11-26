"""The default rule catalogue is a valid rules repository."""

import ast
import itertools
import json
import pathlib
import tomllib
import typing

import auditor.rulescli
import auditor.rulesrepo
import auditor.sweep

CATALOGUE = pathlib.Path(__file__).resolve().parents[2] / 'src' / 'auditor' / 'catalogue'


def test_rules_check_passes_over_the_catalogue(monkeypatch, capsys) -> None:
    monkeypatch.setenv(auditor.rulesrepo.RULES_PATH_VARIABLE, str(CATALOGUE))
    assert auditor.rulescli.main(['check']) == 0, capsys.readouterr()


def test_every_standards_entry_names_a_standard_rule() -> None:
    repo = auditor.rulesrepo.load(CATALOGUE)
    standards = {rule.name for rule in repo.rules if rule.kind == 'standard'}
    for rule in repo.rules:
        for name in typing.cast('list[str]', rule.meta.get('standards', [])):
            assert name in standards, f'{rule.name} lists {name}, which is not a standard rule'


SWEPT_BODY = (
    'import json\n\n\ndef parse(payload):\n    parsed = json.loads(payload)\n    usage = parsed.get("usage", {})\n    return usage.get("input_tokens", 0)\n'
)


def test_the_sweep_reads_each_catalogue_rule_file_once_by_its_path(project, capsys) -> None:
    root = project(
        {
            'src/probe/__init__.py': '__all__: list[str] = []\n',
            'src/probe/catalogue/rules/probe-rule/check.py': SWEPT_BODY,
            'src/probe/catalogue/rules/probe-rule/lister.py': SWEPT_BODY,
        }
    )
    assert auditor.sweep.main([str(root)]) == 0
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    paths = [record['path'] for record in records if record['rule'] == 'get-container-default-then-method-call']
    assert sorted(paths) == [
        'src/probe/catalogue/rules/probe-rule/check.py',
        'src/probe/catalogue/rules/probe-rule/lister.py',
    ]


REPO = auditor.rulesrepo.load(CATALOGUE)
PLAN = auditor.sweep.repo_plan(REPO)
RULE_IDS = REPO.rule_ids()
CHECKS_DIR = CATALOGUE.parent  # src/auditor


def test_the_spec_signature_check_runs_once_per_sweep_not_once_per_root() -> None:
    """It reads the specs and the whole corpus, never the root it is handed, so a per-root pass would repeat it."""
    assert 'rules/spec-api-signature-drift/check.py' in [label for label, _ in PLAN.project_checks]
    assert 'rules/spec-api-signature-drift/check.py' not in [label for label, _ in PLAN.checks]


CROSS_FILE_RULES = frozenset(
    {
        'asymmetric-exception-translation',
        'discarded-tuple-return',
        'duplicate-call-sequence',
        'literal-duplication',
        'mutable-module-level-exported',
        'paired-sibling-helpers',
        'raises-section-drift',
        'recompile-duplication',
        'spec-api-signature-drift',
    }
)

SHARED_FUNCTION = """
def {name}(path: str) -> str:
    resolved = path.strip().lower()
    return resolved + '-a-long-enough-suffix'
"""

CALL_CHAIN = """
import probe.helper


def {name}(value: str) -> str:
    probe.helper.alpha(value)
    probe.helper.bravo(value)
    probe.helper.charlie(value)
    probe.helper.delta(value)
    probe.helper.echo(value)
    probe.helper.foxtrot(value)
    probe.helper.golf(value)
    return value
"""

WRAPPED_CALLER = """
import probe.errors
import probe.setup


def {name}(label: str) -> int:
    try:
        return probe.setup.setup_experiment(label)
    except Exception as exc:
        raise probe.errors.ProbeError('setup failed') from exc
"""


def test_exactly_the_cross_file_rules_emit_related(project, run_check) -> None:
    """A rule that compares files must name the other files, so a scope filter
    can report a hit when only its peer changed. A rule added later that
    compares files without `related` is not in this set and fails here."""
    root = project(
        {
            'src/probe/lit_a.py': "NAMES = ['alpha', 'beta']\n",
            'src/probe/lit_b.py': "LABELS = ['alpha', 'beta']\n",
            'src/probe/sib_a.py': SHARED_FUNCTION.format(name='load_a'),
            'src/probe/sib_b.py': SHARED_FUNCTION.format(name='load_b'),
            'src/probe/seq_a.py': CALL_CHAIN.format(name='run_first'),
            'src/probe/seq_b.py': CALL_CHAIN.format(name='run_second'),
            'src/probe/re_a.py': "import re\n\nTOKEN_RE = re.compile(r'^[a-z]+$')\n",
            'src/probe/re_b.py': "import re\n\nTOKEN_RE = re.compile(r'^[a-z]+$')\n",
            'src/probe/setup.py': 'import pathlib\n\n\ndef setup_experiment(name: str) -> int:\n    return len(pathlib.Path(name).read_text())\n',
            'src/probe/wrap_a.py': WRAPPED_CALLER.format(name='run_a'),
            'src/probe/wrap_b.py': WRAPPED_CALLER.format(name='run_b'),
            'src/probe/settings.py': "DEFAULTS = {'a': 1}\n",
            'src/probe/user.py': 'from probe.settings import DEFAULTS\n\nVALUE = DEFAULTS\n',
            'src/probe/mod.py': 'def extract_directory(settings, output_path=None):\n    return None\n',
            'agents/specs/probe/spec.md': '## API\n\n```python\ndef extract_directory(settings: Settings) -> Batch:\n```\n',
            'src/probe/declares.py': 'class ProbeError(Exception):\n    pass\n\n\ndef check(text):\n    """Check.\n\n    Raises:\n        ProbeError: bad.\n    """\n    return text\n',
            'src/probe/tup_a.py': "def pair(x: int) -> tuple[int, str]:\n    return x, 'a'\n",
            'src/probe/tup_b.py': 'import probe.tup_a\n\n\ndef run(x: int) -> None:\n    probe.tup_a.pair(x)\n',
            'src/probe/calls.py': 'import probe.declares\n\n\ndef run(text):\n    """Run.\n\n    Raises:\n        ValueError: never.\n    """\n    return probe.declares.check(text)\n',
        }
    )
    hits = []
    for _, check in (*PLAN.project_checks, *PLAN.checks):
        hits.extend(run_check(check, root))
    emitting = {hit['rule'] for hit in hits if 'related' in hit}
    assert emitting == CROSS_FILE_RULES
    for hit in hits:
        if 'related' in hit:
            assert hit['related'] == sorted(set(hit['related']))
            assert hit['path'] not in hit['related']


CHECKER_GUIDE = CATALOGUE.parents[2] / 'docs' / 'guide' / 'checker.md'


def emitted_rule_literals() -> set[str]:
    """Every `rule='<literal>'` keyword in the checker's source, read with `ast`."""
    paths = sorted(CHECKS_DIR.rglob('*.py'))
    found: set[str] = set()
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.keyword) and node.arg == 'rule' and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                found.add(node.value.value)
    return found


def documented_rule_ids() -> set[str]:
    """The first-column ids of every `Rule id` table under `## The rules` in the checker guide."""
    section = CHECKER_GUIDE.read_text(encoding='utf-8').split('\n## The rules', 1)[1].split('\n## ', 1)[0]
    lines = section.splitlines()
    found: set[str] = set()
    for index, line in enumerate(lines):
        if not line.startswith('| Rule id'):
            continue
        for row in itertools.takewhile(lambda text: text.startswith('|'), lines[index + 2 :]):
            found.add(row.split('|')[1].strip().strip('`'))
    return found


def test_every_rule_the_source_emits_is_in_rule_ids() -> None:
    """`never-accepted` validates its names against `rule_ids()`; a rule missing from it could not be listed."""
    missing = emitted_rule_literals() - RULE_IDS
    assert not missing, f'emitted but not in rule_ids(): {sorted(missing)}'


def test_rule_ids_matches_the_rule_tables_in_the_checker_guide() -> None:
    """The guide's tables and `rule_ids()` list the same ids, so a rule added to one cannot go missing from the other."""
    documented = documented_rule_ids()
    assert documented, 'no Rule id table found under "## The rules"'
    assert documented == set(RULE_IDS), f'only in the guide: {sorted(documented - RULE_IDS)}; only in rule_ids(): {sorted(RULE_IDS - documented)}'


def test_rule_ids_includes_the_never_accepted_rules() -> None:
    assert {'ruff', 'lockfile-drift'} <= RULE_IDS


def pack_rules() -> dict[str, list[str]]:
    packs = tomllib.loads((CATALOGUE / 'packs.toml').read_text(encoding='utf-8'))['packs']
    return {name: list(pack['rules']) for name, pack in packs.items()}


def test_every_rule_directory_is_in_exactly_one_pack() -> None:
    directories = {path.name for path in (CATALOGUE / 'rules').iterdir() if path.is_dir()}
    listed = [name for rules in pack_rules().values() for name in rules]
    assert sorted(listed) == sorted(directories), (
        f'in no pack: {sorted(directories - set(listed))}; '
        f'not a rule directory: {sorted(set(listed) - directories)}; '
        f'in several packs: {sorted(name for name in set(listed) if listed.count(name) > 1)}'
    )
