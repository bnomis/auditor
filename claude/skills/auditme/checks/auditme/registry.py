"""The check registry: every check, in the order the sweep runs them."""

import auditme.rules.duplication
import auditme.rules.error_handling
import auditme.rules.imports_and_surfaces
import auditme.rules.project_hygiene
import auditme.rules.state_and_effects
import auditme.rules.style_and_naming

CHECKS = (
    auditme.rules.project_hygiene.check_ruff,
    auditme.rules.style_and_naming.check_text_patterns,
    auditme.rules.style_and_naming.check_percent_formatting,
    auditme.rules.imports_and_surfaces.check_def_class_in_init,
    auditme.rules.imports_and_surfaces.check_in_function_imports,
    auditme.rules.error_handling.check_silent_broad_except,
    auditme.rules.error_handling.check_broad_except_wrong_level,
    auditme.rules.error_handling.check_except_interpolation,
    auditme.rules.duplication.check_literal_duplication,
    auditme.rules.style_and_naming.check_nonalphabetical_literals,
    auditme.rules.imports_and_surfaces.check_unused_submodule_imports,
    auditme.rules.duplication.check_paired_sibling_helpers,
    auditme.rules.imports_and_surfaces.check_layering_violations,
    auditme.rules.state_and_effects.check_constructor_disk_io,
    auditme.rules.imports_and_surfaces.check_passthrough_shim,
    auditme.rules.imports_and_surfaces.check_empty_init_with_exporting_siblings,
    auditme.rules.error_handling.check_mixed_raise_types,
    auditme.rules.imports_and_surfaces.check_migration_shim_consumers,
    auditme.rules.state_and_effects.check_silent_self_mutation,
    auditme.rules.error_handling.check_asymmetric_exception_translation,
    auditme.rules.error_handling.check_sibling_error_no_common_base,
    auditme.rules.duplication.check_duplicate_side_effect_per_target,
    auditme.rules.error_handling.check_cli_entry_missing_error_envelope,
    auditme.rules.duplication.check_redundant_sink_caller_plus_callee,
    auditme.rules.state_and_effects.check_return_value_shadows_instance_attr,
    auditme.rules.error_handling.check_try_wrapping_with_too_broad,
    auditme.rules.duplication.check_duplicate_call_sequence,
    auditme.rules.error_handling.check_layer_has_domain_error_but_raises_stdlib,
    auditme.rules.error_handling.check_inconsistent_error_translation,
    auditme.rules.state_and_effects.check_parameter_mutation,
    auditme.rules.state_and_effects.check_pure_name_has_side_effect,
    auditme.rules.state_and_effects.check_mutable_store_without_copy,
    auditme.rules.error_handling.check_filesystem_envelope_gap,
    auditme.rules.error_handling.check_filesystem_op_without_envelope,
    auditme.rules.state_and_effects.check_assert_never_missing,
    auditme.rules.state_and_effects.check_build_name_has_side_effect,
    auditme.rules.state_and_effects.check_mutable_module_level_exported,
    auditme.rules.state_and_effects.check_callback_hotpath_io,
    auditme.rules.duplication.check_recompile_duplication,
    auditme.rules.error_handling.check_logger_exception_graceful_degradation,
    auditme.rules.style_and_naming.check_non_alphabetical_dict_keys,
    auditme.rules.style_and_naming.check_bare_parametric_annotation,
    auditme.rules.error_handling.check_docstring_raises_mismatch,
    auditme.rules.imports_and_surfaces.check_reexport_in_non_init,
    auditme.rules.state_and_effects.check_dataclass_optional_always_set,
    auditme.rules.state_and_effects.check_dead_local_init,
    auditme.rules.style_and_naming.check_duplicated_word,
    auditme.rules.error_handling.check_missing_raises_section,
    auditme.rules.state_and_effects.check_subprocess_without_memoisation,
    auditme.rules.error_handling.check_bare_except_in_module_with_narrow_errors,
    auditme.rules.style_and_naming.check_bare_nonbuiltin_generic_annotation,
    auditme.rules.style_and_naming.check_underscore_unpack_target_read,
    auditme.rules.style_and_naming.check_underscore_forloop_target_read,
    auditme.rules.error_handling.check_failure_as_absence,
    auditme.rules.project_hygiene.check_phase_section_doc_reference,
    auditme.rules.error_handling.check_get_container_default_then_method_call,
    auditme.rules.imports_and_surfaces.check_annotated_all_assignment,
    auditme.rules.error_handling.check_translator_envelope_gap,
    auditme.rules.imports_and_surfaces.check_as_import,
    auditme.rules.state_and_effects.check_mutable_members_in_immutable_wrapper,
    auditme.rules.style_and_naming.check_leading_underscore_nested_def_class,
    auditme.rules.style_and_naming.check_leading_underscore_binding,
    auditme.rules.imports_and_surfaces.check_from_import,
    auditme.rules.style_and_naming.check_typing_deprecated_alias,
    auditme.rules.error_handling.check_raises_section_drift,
)

# The checks that read only the project, never the root they are handed. The
# driver runs these once, before the per-root passes, whether or not the
# project has a root, so a project with no Python still has its lockfile and
# ruff pin checked. None is in CHECKS: a per-root pass would repeat it.
PROJECT_CHECKS = (
    auditme.rules.project_hygiene.check_lockfile,
    auditme.rules.project_hygiene.check_ruff_version,
    auditme.rules.project_hygiene.check_spec_api_signature_drift,
)
