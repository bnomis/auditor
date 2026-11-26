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

BARE_HANDLER_MARK = auditor.errorsites.BARE_HANDLER_MARK  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
BROAD_HANDLER_NAMES = auditor.errorsites.BROAD_HANDLER_NAMES  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
LOADER_CALLS = auditor.errorsites.LOADER_CALLS  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
STDLIB_ERRORS = auditor.errorsites.STDLIB_ERRORS  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
HandlerLevel = auditor.errorsites.HandlerLevel  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
expand_level = auditor.errorsites.expand_level  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
filesystem_envelope_gap_sites = (
    auditor.errorsites.filesystem_envelope_gap_sites
)  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
filesystem_op_sites = auditor.errorsites.filesystem_op_sites  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
function_levels = auditor.errorsites.function_levels  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
graceful_degradation_sites = (
    auditor.errorsites.graceful_degradation_sites
)  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
level_catches = auditor.errorsites.level_catches  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
module_tuple_constants = (
    auditor.errorsites.module_tuple_constants
)  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
nested_call_sites = auditor.errorsites.nested_call_sites  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
raised_name = auditor.errorsites.raised_name  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
translator_gap_sites = auditor.errorsites.translator_gap_sites  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name
tuple_constants = auditor.errorsites.tuple_constants  # auditme: accept[reexport-in-non-init] the API publishes the runner's helper under this name

__all__ = [
    'BARE_HANDLER_MARK',
    'BROAD_HANDLER_NAMES',
    'ERRORS_MODULE_NAMES',
    'FILESYSTEM_TOUCHING_CALLS',
    'LOADER_CALLS',
    'STDLIB_ERRORS',
    'HandlerLevel',
    'callable_short_name',
    'class_lineage',
    'expand_level',
    'filesystem_envelope_gap_sites',
    'filesystem_op_sites',
    'function_levels',
    'graceful_degradation_sites',
    'is_broad_handler',
    'level_catches',
    'module_tuple_constants',
    'nested_call_sites',
    'package_class_parents',
    'raised_name',
    'raises_section_names',
    'silent_broad_except_sites',
    'translator_envelopes',
    'translator_gap_sites',
    'tuple_constants',
    'wrong_level_broad_except_sites',
]
