"""Helpers that read exception handlers, raised errors and class lineage, for rules to share."""

import auditor.errorsites

# The helpers live in the runner, where the Phase B listers and the checks not yet moved read them too.
ERRORS_MODULE_NAMES = auditor.errorsites.ERRORS_MODULE_NAMES  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
FILESYSTEM_TOUCHING_CALLS = (
    auditor.errorsites.FILESYSTEM_TOUCHING_CALLS
)  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
callable_short_name = auditor.errorsites.callable_short_name  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
class_lineage = auditor.errorsites.class_lineage  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
is_broad_handler = auditor.errorsites.is_broad_handler  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
package_class_parents = auditor.errorsites.package_class_parents  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
raises_section_names = auditor.errorsites.raises_section_names  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
silent_broad_except_sites = (
    auditor.errorsites.silent_broad_except_sites
)  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
translator_envelopes = auditor.errorsites.translator_envelopes  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
wrong_level_broad_except_sites = (
    auditor.errorsites.wrong_level_broad_except_sites
)  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name

__all__ = [
    'ERRORS_MODULE_NAMES',
    'FILESYSTEM_TOUCHING_CALLS',
    'callable_short_name',
    'class_lineage',
    'is_broad_handler',
    'package_class_parents',
    'raises_section_names',
    'silent_broad_except_sites',
    'translator_envelopes',
    'wrong_level_broad_except_sites',
]
