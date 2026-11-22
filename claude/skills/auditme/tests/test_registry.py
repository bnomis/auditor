"""Tests for the check registry.

`CHECKS` is the sweep's contract with its own output. A check that is written
but never registered runs nowhere while looking shipped, and a check that moves
within the tuple reorders every hit after it - which reads as a diff in the
next audit even though nothing was found differently. Both failures are silent
without a test.
"""

import annotationlib
import inspect
import pathlib

import auditme.registry
import auditme.rules.duplication
import auditme.rules.error_handling
import auditme.rules.imports_and_surfaces
import auditme.rules.project_hygiene
import auditme.rules.state_and_effects
import auditme.rules.style_and_naming

RULE_MODULES = (
    auditme.rules.duplication,
    auditme.rules.error_handling,
    auditme.rules.imports_and_surfaces,
    auditme.rules.project_hygiene,
    auditme.rules.state_and_effects,
    auditme.rules.style_and_naming,
)

TESTS_DIR = pathlib.Path(__file__).resolve().parent

ORDER_BASELINE = TESTS_DIR / 'registry-order.txt'


def defined_check_names() -> set[str]:
    """Every `check_*` function each rules module defines itself."""
    names: set[str] = set()
    for module in RULE_MODULES:
        for name, value in vars(module).items():
            if name.startswith('check_') and inspect.isfunction(value) and value.__module__ == module.__name__:
                names.add(name)
    return names


def registered_check_names() -> list[str]:
    return [check.__name__ for check in (*auditme.registry.CHECKS, *auditme.registry.PROJECT_CHECKS)]


def test_every_defined_check_is_registered() -> None:
    """A check absent from `CHECKS` runs on nothing while looking shipped."""
    unregistered = defined_check_names() - set(registered_check_names())
    assert not unregistered, f'defined but not in CHECKS: {sorted(unregistered)}'


def test_every_registered_check_is_defined_in_a_rules_module() -> None:
    stray = set(registered_check_names()) - defined_check_names()
    assert not stray, f'in CHECKS but not defined by a rules module: {sorted(stray)}'


def test_no_check_is_registered_twice() -> None:
    """A duplicate entry would report every one of its hits twice."""
    names = registered_check_names()
    assert len(names) == len(set(names))


def test_the_spec_signature_check_runs_once_per_sweep_not_once_per_root() -> None:
    """It reads the specs and the whole corpus, never the root it is handed, so a per-root pass would repeat it."""
    assert auditme.rules.project_hygiene.check_spec_api_signature_drift in auditme.registry.PROJECT_CHECKS
    assert auditme.rules.project_hygiene.check_spec_api_signature_drift not in auditme.registry.CHECKS


def test_every_check_takes_a_scope_and_a_source_root() -> None:
    for check in auditme.registry.CHECKS:
        parameters = list(inspect.signature(check, annotation_format=annotationlib.Format.FORWARDREF).parameters)
        assert parameters == ['scope', 'src_root'], f'{check.__name__} takes {parameters}'


def test_every_registered_check_is_exercised_by_a_test_module() -> None:
    """A check with no test is a predicate nobody has stated the shape of.

    The reference only has to be by name: each check's own module asserts the
    shape it fires on and the carve-outs it skips. This test exists so that
    adding a check without tests fails here rather than being noticed an audit
    cycle later.
    """
    referenced: set[str] = set()
    names = registered_check_names()
    for path in sorted(TESTS_DIR.glob('test_*.py')):
        if path.name == pathlib.Path(__file__).name:
            continue
        text = path.read_text(encoding='utf-8')
        referenced.update(name for name in names if name in text)
    missing = set(names) - referenced
    assert not missing, f'no test module exercises: {sorted(missing)}'


def test_registered_order_is_preserved() -> None:
    """Appending is free; moving an existing entry is not.

    The baseline records the order the checks were in when it was last written.
    A new check may be inserted anywhere without touching the baseline, because
    the assertion is that the baseline is still a *subsequence* of `CHECKS`.
    Reordering or removing a recorded check breaks it, which is the intent: it
    changes the emission order of every subsequent hit, and the next audit
    reads that as a finding delta. If a removal is deliberate, rewrite the
    baseline in the same commit.
    """
    baseline = [line.strip() for line in ORDER_BASELINE.read_text(encoding='utf-8').splitlines() if line.strip() and not line.startswith('#')]
    remaining = iter(registered_check_names())
    for position, name in enumerate(baseline):
        found = any(candidate == name for candidate in remaining)
        assert found, f'{name} (registry-order.txt line {position + 1}) has moved earlier in CHECKS or been removed'


CROSS_FILE_RULES = frozenset(
    {
        'asymmetric-exception-translation',
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
            'src/probe/setup.py': 'def setup_experiment(name: str) -> int:\n    return len(name)\n',
            'src/probe/wrap_a.py': WRAPPED_CALLER.format(name='run_a'),
            'src/probe/wrap_b.py': WRAPPED_CALLER.format(name='run_b'),
            'src/probe/settings.py': "DEFAULTS = {'a': 1}\n",
            'src/probe/user.py': 'from probe.settings import DEFAULTS\n\nVALUE = DEFAULTS\n',
            'src/probe/mod.py': 'def extract_directory(settings, output_path=None):\n    return None\n',
            'agents/specs/probe/spec.md': '## API\n\n```python\ndef extract_directory(settings: Settings) -> Batch:\n```\n',
            'src/probe/declares.py': 'class ProbeError(Exception):\n    pass\n\n\ndef check(text):\n    """Check.\n\n    Raises:\n        ProbeError: bad.\n    """\n    return text\n',
            'src/probe/calls.py': 'import probe.declares\n\n\ndef run(text):\n    """Run.\n\n    Raises:\n        ValueError: never.\n    """\n    return probe.declares.check(text)\n',
        }
    )
    hits = []
    for check in (*auditme.registry.CHECKS, *auditme.registry.PROJECT_CHECKS):
        hits.extend(run_check(check, root))
    emitting = {hit['rule'] for hit in hits if 'related' in hit}
    assert emitting == CROSS_FILE_RULES
    for hit in hits:
        if 'related' in hit:
            assert hit['related'] == sorted(set(hit['related']))
            assert hit['path'] not in hit['related']
