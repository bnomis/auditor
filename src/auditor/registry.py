"""The check registry: every check, in the order the sweep runs them.

Transitional: the built-in checks not yet moved, followed by every rule already
in `auditor/catalogue/`, loaded through `auditor.rulesrepo.import_entry`. The
catalogue's rules come in name order after the built-ins.
"""

import pathlib
import typing

import auditor.rules.error_handling
import auditor.rules.project_hygiene
import auditor.rulesrepo

if typing.TYPE_CHECKING:
    import collections.abc

CATALOGUE_ROOT = pathlib.Path(__file__).resolve().parent / 'catalogue'
CATALOGUE = auditor.rulesrepo.load(CATALOGUE_ROOT)


def catalogue_check(rule: auditor.rulesrepo.Rule) -> collections.abc.Callable[[pathlib.Path, pathlib.Path], None]:
    """A check that imports the rule's `check.py` when it first runs, named by the rule directory."""

    def run(scope: pathlib.Path, src_root: pathlib.Path) -> None:
        auditor.rulesrepo.import_entry(rule, 'check.py').check(scope, src_root)

    run.__name__ = rule.name
    return run


BUILTIN_CHECKS = (
    auditor.rules.project_hygiene.check_ruff,
    auditor.rules.error_handling.check_filesystem_envelope_gap,
    auditor.rules.error_handling.check_filesystem_op_without_envelope,
    auditor.rules.error_handling.check_logger_exception_graceful_degradation,
    auditor.rules.error_handling.check_docstring_raises_mismatch,
    auditor.rules.error_handling.check_missing_raises_section,
    auditor.rules.error_handling.check_bare_except_in_module_with_narrow_errors,
    auditor.rules.error_handling.check_failure_as_absence,
    auditor.rules.project_hygiene.check_phase_section_doc_reference,
    auditor.rules.error_handling.check_get_container_default_then_method_call,
    auditor.rules.error_handling.check_translator_envelope_gap,
    auditor.rules.error_handling.check_raises_section_drift,
)

CHECKS = (
    *BUILTIN_CHECKS,
    *(catalogue_check(rule) for rule in CATALOGUE.rules if rule.kind == 'check'),
)

# The checks that read only the project, never the root they are handed. The
# driver runs these once, before the per-root passes, whether or not the
# project has a root, so a project with no Python still has its lockfile and
# ruff pin checked. None is in CHECKS: a per-root pass would repeat it.
BUILTIN_PROJECT_CHECKS = (
    auditor.rules.project_hygiene.check_lockfile,
    auditor.rules.project_hygiene.check_ruff_version,
    auditor.rules.project_hygiene.check_spec_api_signature_drift,
)

PROJECT_CHECKS = (
    *BUILTIN_PROJECT_CHECKS,
    *(catalogue_check(rule) for rule in CATALOGUE.rules if rule.kind == 'project-check'),
)

# Every rule id the checker can emit, `ruff` and `lockfile-drift` included.
# `[tool.auditme] never-accepted` validates its names against this set; a test
# keeps it equal to the source's emitted ids and the rule tables in the guide.
BUILTIN_RULE_IDS = frozenset(
    {
        'assert-never-missing',
        'asymmetric-exception-translation',
        'auditme-check-crash',
        'bare-except-in-module-with-narrow-errors',
        'broad-except-wrong-level',
        'build-name-has-side-effect',
        'callback-hotpath-io',
        'cli-entry-missing-error-envelope',
        'constructor-disk-io',
        'dataclass-optional-always-set',
        'dead-local-init',
        'discarded-tuple-return',
        'docstring-raises-mismatch',
        'except-interpolation',
        'failure-as-absence',
        'filesystem-envelope-gap',
        'filesystem-op-without-envelope',
        'get-container-default-then-method-call',
        'inconsistent-error-translation',
        'layer-has-domain-error-raises-stdlib',
        'leading-underscore-def-class',
        'lockfile-drift',
        'logger-exception-graceful-degradation',
        'missing-raises-section',
        'mixed-raise-types',
        'mutable-members-in-immutable-wrapper',
        'mutable-module-level-exported',
        'mutable-store-without-copy',
        'parameter-mutation-in-pure-function',
        'phase-section-doc-reference',
        'pure-name-has-side-effect',
        'raises-section-drift',
        'return-shadows-instance-attr',
        'ruff',
        'ruff-version-drift',
        'sibling-errors-no-common-base',
        'silent-broad-except',
        'silent-self-mutation',
        'spec-api-signature-drift',
        'src-loose-module',
        'subprocess-without-memoisation',
        'translator-envelope-gap',
        'try-wrapping-with-block-too-broad',
        'unreadable-file',
    }
)

RULE_IDS = BUILTIN_RULE_IDS | CATALOGUE.rule_ids()
