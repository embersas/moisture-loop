"""Mechanical spec.7 Stage-7 traceability data.

The specification remains the inventory authority. This module connects each
normative ID to substantive pytest evidence; ``test_traceability.py`` checks
the mapping and ``scripts/check_traceability.py`` checks executed JUnit data.
"""

from __future__ import annotations

from dataclasses import dataclass

PURE = "pure"
HA = "ha-2025.9.0"


@dataclass(frozen=True, slots=True)
class Evidence:
    node: str
    environment: str


@dataclass(frozen=True, slots=True)
class InvariantTrace:
    components: tuple[str, ...]
    normative_ids: tuple[str, ...]
    extra_evidence: tuple[Evidence, ...] = ()


def pure(node: str) -> tuple[Evidence, ...]:
    return (Evidence(node, PURE),)


def ha(node: str) -> tuple[Evidence, ...]:
    return (Evidence(node, HA),)


def both(*items: Evidence) -> tuple[Evidence, ...]:
    return items


NORMATIVE_TEST_EVIDENCE: dict[str, tuple[Evidence, ...]] = {
    # Sensor/report tests.
    "SR1": ha(
        "tests/test_state_reported.py::TestStateReportedMechanics::test_identical_second_write_emits_report_and_advances"
    ),
    "SR2": pure(
        "tests/test_state_machine.py::TestPostSoakEquality::test_old_report_after_deadline_cannot_decide"
    ),
    "SR3": pure(
        "tests/test_state_machine.py::TestPostSoakEquality::test_report_exactly_at_soak_end_qualifies"
    ),
    "SR4": pure(
        "tests/test_state_machine.py::TestPostSoakEquality::test_grace_without_qualifying_report_is_sensor_stale"
    ),
    "SR5": ha(
        "tests/test_zone_controller.py::TestWatchdog::test_sr5_freshness_expiry_stops_flowing_auto"
    ),
    "SR6": ha(
        "tests/test_zone_controller.py::TestWatchdog::test_sr6_identical_report_extends_deadline"
    ),
    "SR7": pure(
        "tests/test_state_machine.py::TestWatchdog::test_valid_report_extends_from_its_own_timestamp"
    ),
    "SR8": ha(
        "tests/test_zone_controller.py::TestWatchdog::test_sr8_invalid_and_unavailable_take_specific_paths"
    ),
    "SR9": ha(
        "tests/test_zone_controller.py::TestManual::test_manual_session_ignores_sensor_health"
    ),
    "SR10": both(
        Evidence(
            "tests/test_state_machine.py::TestWatchdog::test_boundary_race_report_first_prevents_expiry",
            PURE,
        ),
        Evidence(
            "tests/test_state_machine.py::TestWatchdog::test_boundary_race_watchdog_first_terminates_permanently",
            PURE,
        ),
    ),
    "SR11": ha(
        "tests/test_zone_controller.py::TestTerminationRaces::test_ac2_stop_vs_pulse_expiry_single_reason"
    ),
    "SR12": pure("tests/test_state_machine.py::TestHysteresis::test_freshness_equality_is_fresh"),
    "SR13": both(
        Evidence(
            "tests/test_state_machine.py::TestWatchdog::test_sr13_superseded_callback_no_ops", PURE
        ),
        Evidence(
            "tests/test_zone_controller.py::TestWatchdog::test_sr13_deliberately_executed_stale_callback_no_ops",
            HA,
        ),
    ),
    # Store initialization, crash, and persistence.
    "PI1": ha(
        "tests/test_lifecycle.py::TestFirstInstallAndIdentity::test_first_install_transaction"
    ),
    "PI2": ha(
        "tests/test_lifecycle.py::TestFirstInstallAndIdentity::test_interrupted_initialization_completes_flag"
    ),
    "PI3": ha(
        "tests/test_lifecycle.py::TestFirstInstallAndIdentity::test_integrity_loss_blocks_and_exhausts_today"
    ),
    "PI4": ha(
        "tests/test_storage.py::TestInitializationAndLoad::test_pi4_corrupt_or_unreadable_store_fails_closed"
    ),
    "PI5": ha(
        "tests/test_storage.py::TestInitializationAndLoad::test_generation_mismatch_is_never_first_install"
    ),
    "PI6": ha(
        "tests/test_lifecycle.py::TestFirstInstallAndIdentity::test_interrupted_initialization_completes_flag"
    ),
    "PI7": both(
        Evidence(
            "tests/test_lifecycle.py::TestFirstInstallAndIdentity::test_initial_write_failure_fails_setup_and_keeps_flag_false",
            HA,
        ),
        Evidence(
            "tests/test_storage.py::TestVerifiedWritesAndRuns::test_pi7_swallowed_initial_write_detected",
            HA,
        ),
    ),
    "PI8": ha(
        "tests/test_storage.py::TestInitializationAndLoad::test_future_and_malformed_schema2_fail_closed"
    ),
    "PI9": ha(
        "tests/test_lifecycle.py::TestFirstInstallAndIdentity::test_integrity_loss_blocks_and_exhausts_today"
    ),
    "PI10": ha(
        "tests/test_lifecycle.py::TestFirstInstallAndIdentity::test_integrity_loss_blocks_and_exhausts_today"
    ),
    "PI11": both(
        Evidence(
            "tests/test_storage.py::TestVerifiedWritesAndRuns::test_pi11_every_store_is_atomic_and_readback_verified",
            HA,
        ),
        Evidence(
            "tests/test_storage.py::TestVerifiedWritesAndRuns::test_pi11_failed_write_keeps_previous_revision",
            HA,
        ),
    ),
    "PI12": both(
        Evidence(
            "tests/test_lifecycle.py::TestPersistedWateringRecovery::test_pi12_found_on_defensive_off_and_estimate",
            HA,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestF1RestartRecoveryBlockerRelease::test_f1a_proven_defensive_off_releases_matching_blocker",
            HA,
        ),
        Evidence(
            "tests/test_state_machine.py::TestStartupRecovery::test_confirmed_off_releases_only_the_matching_blocker",
            PURE,
        ),
    ),
    "PI13": both(
        Evidence(
            "tests/test_lifecycle.py::TestPersistedWateringRecovery::test_pi13_found_off_estimates_to_reconciliation",
            HA,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestF1RestartRecoveryBlockerRelease::test_f1e_startup_actuator_already_off_leaves_no_blocker",
            HA,
        ),
    ),
    "PI14": both(
        Evidence(
            "tests/test_lifecycle.py::TestPersistedWateringRecovery::test_pi14_unproven_actuator_blocks_and_faults",
            HA,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestF1RestartRecoveryBlockerRelease::test_f1b_unproven_off_retains_blocker_and_open_accounting",
            HA,
        ),
    ),
    "PI15": ha(
        "tests/test_lifecycle.py::TestPersistedWateringRecovery::test_pi15_large_downtime_exhausts_budget"
    ),
    "PI16": pure(
        "tests/test_storage_pure.py::TestConservativeEstimation::test_estimate_covers_every_plausible_stop"
    ),
    "PI17": both(
        Evidence(
            "tests/test_storage_pure.py::TestDailySplitting::test_spec_35_4_midnight_split", PURE
        ),
        Evidence(
            "tests/test_storage_pure.py::TestDailySplitting::test_multi_day_outage_recognizes_every_day",
            PURE,
        ),
        Evidence(
            "tests/test_storage_pure.py::TestDailySplitting::test_dst_spring_forward_day_is_23_hours",
            PURE,
        ),
        Evidence(
            "tests/test_storage_pure.py::TestDailySplitting::test_dst_fall_back_day_is_25_hours",
            PURE,
        ),
    ),
    "PI18": ha(
        "tests/test_storage.py::TestVerifiedWritesAndRuns::test_pi18_crashed_intermediate_run_is_unclean"
    ),
    "PI19": ha(
        "tests/test_storage.py::TestVerifiedWritesAndRuns::test_pi19_unverified_run_id_fails_closed"
    ),
    "PI20": ha(
        "tests/test_storage.py::TestVerifiedWritesAndRuns::test_pi20_canonical_writes_serialize_without_loss"
    ),
    "PI21": both(
        Evidence(
            "tests/test_storage.py::TestVerifiedMigration::test_pi21_configured_schema1_migrates_and_verifies",
            HA,
        ),
        Evidence(
            "tests/test_storage_pure.py::TestSchema1Migration::test_configured_record_preserves_history_and_ownership",
            PURE,
        ),
    ),
    "PI22": both(
        Evidence(
            "tests/test_storage.py::TestVerifiedMigration::test_pi22_store_only_schema1_migrates_unresolved",
            HA,
        ),
        Evidence(
            "tests/test_storage_pure.py::TestSchema1Migration::test_store_only_record_is_unresolved_delete_pending",
            PURE,
        ),
    ),
    "PI23": both(
        Evidence(
            "tests/test_storage.py::TestVerifiedMigration::test_tb7_malformed_schema1_fails_closed",
            HA,
        ),
        Evidence(
            "tests/test_storage.py::TestVerifiedMigration::test_pi23_migration_save_failure_fails_closed",
            HA,
        ),
        Evidence(
            "tests/test_storage.py::TestVerifiedMigration::test_pi23_migration_fresh_read_failure",
            HA,
        ),
        Evidence(
            "tests/test_storage.py::TestVerifiedMigration::test_pi23_migration_payload_tamper", HA
        ),
    ),
    "PI24": both(
        Evidence(
            "tests/test_reconciliation.py::TestRuntimeReconciliation::test_registry_rename_reuses_same_record",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestActuatorRenameTracking::test_r1_idle_rename_keeps_one_record_and_follows_addressing",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestActuatorRenameTracking::test_r9_native_delete_after_rename_keeps_a_safe_tombstone",
            HA,
        ),
    ),
    "PI25": both(
        Evidence(
            "tests/test_reconciliation.py::TestRuntimeReconciliation::test_same_entity_id_new_registry_uuid_fails_closed",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestActuatorRenameTracking::test_r6_entity_id_reuse_by_a_different_uuid_fails_closed",
            HA,
        ),
    ),
    "PI26": both(
        Evidence(
            "tests/test_reconciliation.py::TestRuntimeReconciliation::test_delete_readd_exact_uuid_reuses_record_and_history",
            HA,
        ),
        Evidence(
            "tests/test_reconciliation.py::TestRuntimeReconciliation::test_reactivation_retains_exact_blocker_budget_and_interval",
            HA,
        ),
        Evidence(
            "tests/test_stage4_on_gate.py::TestTerminalAndOffRaces::test_same_record_reactivation_retains_unconfirmed_open_accounting",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestActuatorRenameTracking::test_r5_restart_after_rename_resolves_by_registry_uuid",
            HA,
        ),
    ),
    "PI28": ha(
        "tests/test_tombstone_recovery.py::TestSchemaUpgrade::test_schema2_payload_upgrades_without_losing_state"
    ),
    "PI27": ha(
        "tests/test_storage.py::TestIntegrityAndRetention::test_pi27_tb11_retired_tombstone_never_auto_purged"
    ),
    # Manual/fault.
    "MF1": pure(
        "tests/test_state_machine.py::TestManualFaultMatrix::test_blocking_faults_refuse_manual"
    ),
    "MF2": pure("tests/test_state_machine.py::TestManualClamping::test_spec_35_5_example"),
    "MF3": ha(
        "tests/test_zone_controller.py::TestManual::test_manual_from_sensor_fault_returns_to_fault"
    ),
    "MF4": ha(
        "tests/test_zone_controller.py::TestManual::test_manual_recovery_clears_after_finish"
    ),
    "MF5": ha(
        "tests/test_zone_controller.py::TestManual::test_mf5_actuator_fault_supersedes_mid_manual"
    ),
    "MF6": both(
        Evidence(
            "tests/test_entities.py::TestControls::test_mf6_manual_pulse_buttons_request_their_own_bounded_duration",
            HA,
        ),
        Evidence(
            "tests/test_entities.py::TestControls::test_mf6_manual_pulse_button_above_a_cap_is_clamped_not_refused",
            HA,
        ),
        Evidence(
            "tests/test_entities.py::TestControls::test_mf6_manual_pulse_button_refusal_matches_the_action",
            HA,
        ),
        Evidence(
            "tests/test_entities.py::TestControls::test_mf6_manual_pulse_buttons_refuse_while_disabled",
            HA,
        ),
    ),
    # Actuator/concurrency and external-resource.
    "AC1": ha(
        "tests/test_zone_controller.py::TestTerminationRaces::test_ac1_stop_during_pulse_single_off"
    ),
    "AC2": ha(
        "tests/test_zone_controller.py::TestTerminationRaces::test_ac2_stop_vs_pulse_expiry_single_reason"
    ),
    "AC3": both(
        Evidence(
            "tests/test_lifecycle.py::TestShutdownAndReload::test_off_timeout_keeps_conservative_evidence_and_is_unclean",
            HA,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestStage1ShutdownOwner::test_unload_during_stage1_is_cleanup_and_join_only",
            HA,
        ),
    ),
    "AC4": both(
        Evidence(
            "tests/test_zone_controller.py::TestTerminationRaces::test_ac4_off_timeout_delayed_proof_closes_later",
            HA,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestF1RestartRecoveryBlockerRelease::test_f1c_later_exact_off_closes_but_keeps_acknowledgement",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestActuatorRenameTracking::test_r10_rename_during_an_off_operation_keeps_one_off_path",
            HA,
        ),
    ),
    "ER1": pure(
        "tests/test_slot_manager.py::TestKeyedBlockers::test_er1_external_flow_blocks_other_zone"
    ),
    "ER2": pure(
        "tests/test_state_machine.py::TestExternalOccupancy::test_t55_disabled_external_on_adds_blocker_without_off"
    ),
    "ER3": ha(
        "tests/test_zone_controller.py::TestExternalInterference::test_t54_t58_external_flow_in_idle"
    ),
    "ER4": pure(
        "tests/test_slot_manager.py::TestKeyedBlockers::test_er4_two_external_flows_both_required_off"
    ),
    "ER5": pure(
        "tests/test_slot_manager.py::TestKeyedBlockers::test_er5_blocker_retained_without_off_proof"
    ),
    "ER6": pure(
        "tests/test_slot_manager.py::TestStartupGating::test_er6_no_grant_before_reconciliation_completes"
    ),
    "ER7": both(
        Evidence(
            "tests/test_slot_manager.py::TestKeyedBlockers::test_er7_reasons_coexist_and_release_independently",
            PURE,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestF1RestartRecoveryBlockerRelease::test_f1d_recovery_clears_only_the_matching_record_and_reason",
            HA,
        ),
    ),
    "ER8": both(
        Evidence(
            "tests/test_slot_manager.py::TestAdversarialInterleavings::test_er8_adversarial_interleaving_with_requests",
            PURE,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestF1RestartRecoveryBlockerRelease::test_f1d_recovery_clears_only_the_matching_record_and_reason",
            HA,
        ),
    ),
    "ER9": ha(
        "tests/test_zone_controller.py::TestExternalInterference::test_er9_external_off_during_watering"
    ),
    "ER10": ha(
        "tests/test_zone_controller.py::TestExternalInterference::test_er10_external_on_during_soaking_counter_commanded"
    ),
    "ER11": ha(
        "tests/test_zone_controller.py::TestExternalInterference::test_er11_external_on_during_off_joins_same_operation"
    ),
    "ER12": ha(
        "tests/test_lifecycle.py::TestStartupResourceSafety::test_er12_external_on_before_setup_blocks_grants"
    ),
    # Lifecycle/action/config.
    "LC1": ha(
        "tests/test_services.py::TestActionLifecycle::test_lc1_actions_exist_with_zero_entries"
    ),
    "LC2": ha("tests/test_services.py::TestDeviceResolution::test_lc2_deleted_zone"),
    "LC3": both(
        Evidence(
            "tests/test_config_flow.py::TestZoneReconfigureFlow::test_changed_data_prepares_updates_then_reconciler_reloads_once",
            HA,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestShutdownAndReload::test_lc3_generic_reload_terminates_and_keeps_run_ids",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestActuatorRenameTracking::test_r4_reload_after_rename_loads_and_reuses_the_record",
            HA,
        ),
    ),
    # LC4 is now exercised through the real hass.async_stop() Stage-1
    # shutdown-job path, never by invoking an internal MoistureLoop handler.
    "LC4": both(
        Evidence(
            "tests/test_lifecycle.py::TestShutdownAndReload::test_lc4_full_shutdown_through_real_core_stage_ordering",
            HA,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestShutdownAndReload::test_lc4_manual_watering_full_shutdown",
            HA,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestShutdownAndReload::test_lc4_shutdown_preserves_eligible_soaking",
            HA,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestShutdownAndReload::test_lc4_clean_marker_is_the_final_verified_revision",
            HA,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestStage1ShutdownOwner::test_exactly_one_shutdown_job_per_loaded_entry",
            HA,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestStage1ShutdownOwner::test_shutdown_job_is_registered_before_watering_capable_runtime",
            HA,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestStage1ShutdownOwner::test_reload_does_not_accumulate_shutdown_jobs",
            HA,
        ),
        Evidence("tests/test_foundation.py::test_no_production_stop_event_shutdown_owner", PURE),
        Evidence(
            "tests/test_foundation.py::test_exactly_one_stage1_shutdown_owner_registration", PURE
        ),
    ),
    "LC5": ha("tests/test_lifecycle.py::TestSoakingAdoption::test_lc5_clean_run_adopts_soaking"),
    "LC6": ha(
        "tests/test_lifecycle.py::TestSoakingAdoption::test_lc6_second_clean_run_adopts_again"
    ),
    "LC7": ha(
        "tests/test_lifecycle.py::TestSoakingAdoption::test_lc7_crashed_intermediate_run_rejects"
    ),
    "LC8": ha(
        "tests/test_lifecycle.py::TestSoakingAdoption::test_lc8_fingerprint_change_prevents_rebase"
    ),
    "LC9": ha(
        "tests/test_lifecycle.py::TestSoakingAdoption::test_lc9_rebase_failure_prohibits_setup"
    ),
    "LC10": ha("tests/test_lifecycle.py::TestSoakingAdoption::test_lc5_clean_run_adopts_soaking"),
    "LC11": ha(
        "tests/test_lifecycle.py::TestSoakingAdoption::test_lc11_offline_expired_soak_faults_stale"
    ),
    "LC12": ha(
        "tests/test_lifecycle.py::TestFirstInstallAndIdentity::test_lc12_setup_failure_still_reconciles_hazard"
    ),
    "LC13": both(
        Evidence(
            "tests/test_state_machine.py::TestTransitionTable::test_spec_table_implementation_and_diagram_have_exact_t1_t59_parity",
            PURE,
        ),
        Evidence(
            "tests/test_reconciliation.py::TestRuntimeReconciliation::test_native_delete_watering_uses_config_changed_and_no_resurrection",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestActuatorRenameTracking::test_r2_rename_during_watering_does_not_terminate_the_session",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestActuatorRenameTracking::test_r3_rename_during_soaking_keeps_the_same_session",
            HA,
        ),
    ),
    "LC14": both(
        Evidence(
            "tests/test_state_machine.py::TestNewZoneSafeDefault::test_lc14_fresh_default_admits_no_auto_when_every_other_gate_passes",
            PURE,
        ),
        Evidence(
            "tests/test_state_machine.py::TestNewZoneSafeDefault::test_lc14_repeated_qualifying_reports_never_arm_the_fresh_default",
            PURE,
        ),
        Evidence(
            "tests/test_state_machine.py::TestNewZoneSafeDefault::test_lc14_manual_is_refused_on_the_fresh_default",
            PURE,
        ),
        Evidence(
            "tests/test_config_flow.py::TestNewZoneSafeDefault::test_lc14_fresh_zone_is_created_disabled_and_admits_nothing",
            HA,
        ),
        Evidence(
            "tests/test_config_flow.py::TestNewZoneSafeDefault::test_lc14_two_further_fresh_reports_do_not_arm_the_new_zone",
            HA,
        ),
        Evidence(
            "tests/test_config_flow.py::TestNewZoneSafeDefault::test_lc14_manual_watering_is_refused_while_the_new_zone_is_disabled",
            HA,
        ),
        Evidence(
            "tests/test_config_flow.py::TestNewZoneSafeDefault::test_lc14_explicit_enable_is_the_normal_activation_path",
            HA,
        ),
        Evidence(
            "tests/test_config_flow.py::TestNewZoneSafeDefault::test_lc14_enabled_switch_entity_reflects_the_runtime_state",
            HA,
        ),
        Evidence(
            "tests/test_config_flow.py::TestNewZoneSafeDefault::test_persisted_enabled_state_survives_reload_and_restart",
            HA,
        ),
        Evidence(
            "tests/test_config_flow.py::TestNewZoneSafeDefault::test_reconfigure_preserves_persisted_enabled_state",
            HA,
        ),
    ),
    # Native deletion and final-ON.
    "ND1": ha(
        "tests/test_config_flow.py::TestNativeSubentryDeletion::test_idle_delete_uses_real_websocket_path_without_reload_and_keeps_safety_record"
    ),
    "ND2": ha(
        "tests/test_reconciliation.py::TestRuntimeReconciliation::test_listener_is_single_and_observation_closes_admission"
    ),
    "ND3": both(
        Evidence(
            "tests/test_config_flow.py::TestNativeSubentryDeletion::test_idle_delete_uses_real_websocket_path_without_reload_and_keeps_safety_record",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestActuatorRenameTracking::test_r9_native_delete_after_rename_keeps_a_safe_tombstone",
            HA,
        ),
    ),
    "ND4": ha(
        "tests/test_config_flow.py::TestNativeSubentryDeletion::test_watering_auto_native_delete_closes_flow_and_final_gate"
    ),
    "ND5": ha(
        "tests/test_config_flow.py::TestNativeSubentryDeletion::test_watering_manual_native_delete_uses_one_off_and_never_resumes"
    ),
    "ND6": ha(
        "tests/test_config_flow.py::TestNativeSubentryDeletion::test_soaking_native_delete_revokes_later_pulse_without_extra_off"
    ),
    "ND7": ha(
        "tests/test_stage4_on_gate.py::TestDispatchAndCompensation::test_nd5_nd7_sensor_fault_manual_delete_retains_fault"
    ),
    "ND8": ha(
        "tests/test_stage4_on_gate.py::TestFinalGate::test_nd8_delete_before_intent_prevents_session_and_on"
    ),
    "ND9": ha(
        "tests/test_stage4_on_gate.py::TestFinalGate::test_nd9_delete_after_intent_before_final_gate_has_zero_on"
    ),
    "ND10": ha(
        "tests/test_stage4_on_gate.py::TestDispatchAndCompensation::test_nd10_no_yield_from_gate_to_dispatch_and_delete_inflight"
    ),
    "ND11": ha(
        "tests/test_stage4_on_gate.py::TestDispatchAndCompensation::test_nd11_raise_after_delete_is_uncertain_and_one_off"
    ),
    "ND12": ha(
        "tests/test_stage4_on_gate.py::TestDispatchAndCompensation::test_delete_after_return_before_command_persistence"
    ),
    "ND13": ha(
        "tests/test_stage4_on_gate.py::TestDispatchAndCompensation::test_fingerprint_change_inflight_forbids_continuation"
    ),
    "ND14": ha(
        "tests/test_stage4_on_gate.py::TestFinalGate::test_complete_gate_predicates_fail_closed"
    ),
    "ND15": ha(
        "tests/test_stage4_on_gate.py::TestDispatchAndCompensation::test_snapshot_generation_supersession_invalidates_command_token"
    ),
    "ND16": ha(
        "tests/test_stage4_on_gate.py::TestDispatchAndCompensation::test_native_websocket_delete_returns_while_on_is_inflight"
    ),
    "ND17": ha(
        "tests/test_stage4_on_gate.py::TestTerminalAndOffRaces::test_delete_before_stop_owns_reason_and_stale_callbacks_noop"
    ),
    # Tombstone/blocker/identity.
    "TB1": both(
        Evidence(
            "tests/test_stage4_on_gate.py::TestTerminalAndOffRaces::test_unconfirmed_delete_keeps_exact_blocker_slot_and_open_accounting",
            HA,
        ),
        Evidence(
            "tests/test_repairs.py::TestRepairs::test_actuator_off_unconfirmed_critical_lifecycle",
            HA,
        ),
    ),
    "TB2": ha(
        "tests/test_reconciliation.py::TestRuntimeReconciliation::test_a_to_b_retains_a_hazard_and_continuing_history"
    ),
    "TB3": ha(
        "tests/test_reconciliation.py::TestRuntimeReconciliation::test_store_only_missing_identity_stays_delete_pending"
    ),
    "TB4": ha(
        "tests/test_storage.py::TestStage2ExactRecordPersistence::test_tb4_exact_record_blockers_persist_independently"
    ),
    "TB5": ha(
        "tests/test_reconciliation.py::TestRuntimeReconciliation::test_store_only_active_record_becomes_implicit_tombstone"
    ),
    "TB6": both(
        Evidence(
            "tests/test_reconciliation.py::TestRuntimeReconciliation::test_store_only_active_record_becomes_implicit_tombstone",
            HA,
        ),
        Evidence(
            "tests/test_slot_manager.py::TestStartupGating::test_startup_blocker_populated_before_enable_is_never_missed",
            PURE,
        ),
    ),
    "TB7": ha(
        "tests/test_storage.py::TestVerifiedMigration::test_tb7_malformed_schema1_fails_closed"
    ),
    "TB8": both(
        Evidence(
            "tests/test_reconciliation.py::TestRuntimeReconciliation::test_registry_rename_reuses_same_record",
            HA,
        ),
        Evidence(
            "tests/test_reconciliation.py::TestRuntimeReconciliation::test_store_only_missing_identity_stays_delete_pending",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestActuatorRenameTracking::test_r1_rename_keeps_observation_and_off_ability",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestActuatorRenameTracking::test_r7_missing_durable_identity_fails_closed",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestRenameVerificationFailsClosed::test_rename_without_durable_identity_is_refused",
            HA,
        ),
    ),
    "TB9": both(
        Evidence(
            "tests/test_reconciliation.py::TestRuntimeReconciliation::test_same_entity_id_new_registry_uuid_fails_closed",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestActuatorRenameTracking::test_r6_entity_id_reuse_by_a_different_uuid_fails_closed",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestRenameVerificationFailsClosed::test_rename_to_a_different_registry_identity_is_refused",
            HA,
        ),
    ),
    "TB10": both(
        Evidence(
            "tests/test_reconciliation.py::TestRuntimeReconciliation::test_reactivation_retains_exact_blocker_budget_and_interval",
            HA,
        ),
        Evidence(
            "tests/test_stage4_on_gate.py::TestTerminalAndOffRaces::test_same_record_reactivation_retains_unconfirmed_open_accounting",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestActuatorRenameTracking::test_r5_restart_after_rename_resolves_by_registry_uuid",
            HA,
        ),
    ),
    "TB11": ha(
        "tests/test_storage.py::TestIntegrityAndRetention::test_pi27_tb11_retired_tombstone_never_auto_purged"
    ),
    "TB12": both(
        Evidence(
            "tests/test_repairs.py::TestRepairs::test_exact_record_fix_rejects_stale_lineage", HA
        ),
        Evidence(
            "tests/test_repairs.py::TestRepairs::test_retired_tombstone_fix_without_controller_or_device",
            HA,
        ),
    ),
    "TB13": both(
        Evidence(
            "tests/test_tombstone_recovery.py::TestNegativeSafetyMatrix::test_unavailable_and_unknown_actuators_are_never_recoverable",
            HA,
        ),
        Evidence(
            "tests/test_tombstone_recovery.py::TestNegativeSafetyMatrix::test_reappearing_identity_is_not_recoverable",
            HA,
        ),
        Evidence(
            "tests/test_tombstone_recovery.py::TestNegativeSafetyMatrix::test_unresolved_flow_or_fault_refuses",
            HA,
        ),
        Evidence(
            "tests/test_tombstone_recovery.py::TestNegativeSafetyMatrix::test_active_record_can_never_be_acknowledged",
            HA,
        ),
    ),
    "TB14": both(
        Evidence(
            "tests/test_tombstone_recovery.py::TestRestartDurability::test_acknowledgement_survives_reload_and_does_not_reappear",
            HA,
        ),
        Evidence(
            "tests/test_tombstone_recovery.py::TestRestartDurability::test_a_returning_registry_identity_revokes_the_proof",
            HA,
        ),
    ),
    "TB15": both(
        Evidence(
            "tests/test_tombstone_recovery.py::TestNegativeSafetyMatrix::test_unchecked_confirmation_is_refused",
            HA,
        ),
        Evidence(
            "tests/test_tombstone_recovery.py::TestNegativeSafetyMatrix::test_opening_the_repair_is_not_an_acknowledgement",
            HA,
        ),
        Evidence(
            "tests/test_tombstone_recovery.py::TestNegativeSafetyMatrix::test_record_and_lineage_mismatch_refuse_visibly",
            HA,
        ),
        Evidence(
            "tests/test_tombstone_recovery.py::TestNegativeSafetyMatrix::test_acknowledgement_commands_no_actuator",
            HA,
        ),
        Evidence(
            "tests/test_tombstone_recovery.py::TestNegativeSafetyMatrix::test_other_blockers_remain_effective",
            HA,
        ),
    ),
    "TB16": both(
        Evidence(
            "tests/test_tombstone_recovery.py::TestExact010Reproduction::test_removed_tombstone_fences_a_healthy_zone_then_recovers",
            HA,
        ),
        Evidence(
            "tests/test_tombstone_recovery.py::TestDisableReleasesTheSlot::test_disable_withdraws_a_queued_slot_request",
            HA,
        ),
    ),
    "TB17": both(
        Evidence(
            "tests/test_tombstone_recovery.py::TestExact010Reproduction::test_removed_tombstone_fences_a_healthy_zone_then_recovers",
            HA,
        ),
        Evidence(
            "tests/test_tombstone_recovery.py::TestExact010Reproduction::test_manual_watering_is_fenced_by_the_same_global_blocker",
            HA,
        ),
    ),
    # Actuator replacement.
    "AR1": ha(
        "tests/test_reconciliation.py::TestRuntimeReconciliation::test_a_to_b_retains_a_hazard_and_continuing_history"
    ),
    "AR2": ha(
        "tests/test_reconciliation.py::TestRuntimeReconciliation::test_a_to_b_retains_a_hazard_and_continuing_history"
    ),
    "AR3": both(
        Evidence(
            "tests/test_reconciliation.py::TestRuntimeReconciliation::test_a_to_b_retains_a_hazard_and_continuing_history",
            HA,
        ),
        Evidence(
            "tests/test_storage.py::TestStage2ExactRecordPersistence::test_ar2_ar10_verified_history_handoff_keeps_hazards_on_b",
            HA,
        ),
    ),
    "AR4": both(
        Evidence(
            "tests/test_stage4_on_gate.py::TestTerminalAndOffRaces::test_unconfirmed_delete_keeps_exact_blocker_slot_and_open_accounting",
            HA,
        ),
        Evidence(
            "tests/test_storage.py::TestStage2ExactRecordPersistence::test_ar2_ar10_verified_history_handoff_keeps_hazards_on_b",
            HA,
        ),
    ),
    "AR5": both(
        Evidence(
            "tests/test_config_flow.py::TestZoneReconfigureFlow::test_a_to_retained_b_is_accepted_and_reconciler_reuses_b",
            HA,
        ),
        Evidence(
            "tests/test_storage_pure.py::TestContributionIdentity::test_history_merge_deduplicates_ids_and_adds_unresolved_evidence",
            PURE,
        ),
    ),
    "AR6": ha(
        "tests/test_config_flow.py::TestZoneReconfigureFlow::test_a_to_b_identity_conflict_is_refused_before_core_mutation"
    ),
    "AR7": pure(
        "tests/test_storage_pure.py::TestContributionIdentity::test_conservative_merge_preserves_known_and_adds_unresolved"
    ),
    "AR8": pure(
        "tests/test_storage_pure.py::TestContributionIdentity::test_ar7_ar8_ar17_history_merge_preserves_operational_owner"
    ),
    "AR9": both(
        Evidence(
            "tests/test_slot_manager.py::TestAdversarialInterleavings::test_er8_adversarial_interleaving_with_requests",
            PURE,
        ),
        Evidence(
            "tests/test_reconciliation.py::TestRuntimeReconciliation::test_a_to_b_retains_a_hazard_and_continuing_history",
            HA,
        ),
    ),
    "AR10": ha(
        "tests/test_storage.py::TestStage2ExactRecordPersistence::test_ar2_ar10_verified_history_handoff_keeps_hazards_on_b"
    ),
    "AR11": pure(
        "tests/test_storage_pure.py::TestContributionIdentity::test_ar7_ar8_ar17_history_merge_preserves_operational_owner"
    ),
    "AR12": ha(
        "tests/test_config_flow.py::TestZoneReconfigureFlow::test_ar12_ar13_ar16_retained_b_operational_state_never_overrides_current_zone"
    ),
    "AR13": ha(
        "tests/test_config_flow.py::TestZoneReconfigureFlow::test_ar12_ar13_ar16_retained_b_operational_state_never_overrides_current_zone"
    ),
    "AR14": ha(
        "tests/test_config_flow.py::TestZoneReconfigureFlow::test_a_to_retained_b_is_accepted_and_reconciler_reuses_b"
    ),
    "AR15": ha(
        "tests/test_config_flow.py::TestZoneReconfigureFlow::test_ar15_retained_b_watering_is_closed_and_never_adopted_as_current_session"
    ),
    "AR16": ha(
        "tests/test_config_flow.py::TestZoneReconfigureFlow::test_ar12_ar13_ar16_retained_b_operational_state_never_overrides_current_zone"
    ),
    "AR17": pure(
        "tests/test_storage_pure.py::TestContributionIdentity::test_ar7_ar8_ar17_history_merge_preserves_operational_owner"
    ),
    # Reconciliation races/failures.
    "RC1": ha(
        "tests/test_stage4_on_gate.py::TestTerminalAndOffRaces::test_watchdog_before_delete_retains_sensor_fault_reason"
    ),
    "RC2": ha(
        "tests/test_stage4_on_gate.py::TestTerminalAndOffRaces::test_delete_before_stop_owns_reason_and_stale_callbacks_noop"
    ),
    "RC3": ha(
        "tests/test_stage4_on_gate.py::TestTerminalAndOffRaces::test_terminal_before_delete_wins_and_uses_one_off"
    ),
    "RC4": ha(
        "tests/test_stage4_on_gate.py::TestTerminalAndOffRaces::test_delete_while_off_retry_waits_uses_delayed_exact_proof"
    ),
    "RC5": ha(
        "tests/test_lifecycle.py::TestShutdownAndReload::test_rc5_delete_vs_generic_reload_persists_tombstone_and_never_resumes"
    ),
    "RC6": both(
        Evidence(
            "tests/test_lifecycle.py::TestShutdownAndReload::test_rc6_delete_vs_shutdown_reconstructs_unresolved_tombstone",
            HA,
        ),
        Evidence(
            "tests/test_lifecycle.py::TestStage1ShutdownOwner::test_shutdown_during_reconfigure_preserves_first_terminal_reason",
            HA,
        ),
    ),
    "RC7": ha(
        "tests/test_config_flow.py::TestNativeSubentryDeletion::test_rapid_two_zone_native_deletion_materializes_both_without_reload"
    ),
    "RC8": both(
        Evidence(
            "tests/test_config_flow.py::TestFlowReconciliationBursts::test_add_reconfigure_delete_before_first_application_latest_empty_wins",
            HA,
        ),
        Evidence(
            "tests/test_rename_tracking.py::TestActuatorRenameTracking::test_r8_rename_racing_reconciliation_publishes_the_latest_snapshot",
            HA,
        ),
    ),
    "RC9": both(
        Evidence(
            "tests/test_reconciliation.py::TestCoordinator::test_failure_and_stop_remain_fail_closed",
            HA,
        ),
        Evidence(
            "tests/test_repairs.py::TestRepairEdges::test_reconciliation_failure_issue_clears_only_after_recovery",
            HA,
        ),
    ),
    "RC10": ha(
        "tests/test_reconciliation.py::TestRuntimeReconciliation::test_store_failure_keeps_old_controller_and_barrier_closed"
    ),
    "RC11": ha(
        "tests/test_config_flow.py::TestZoneReconfigureFlow::test_a_to_b_identity_conflict_is_refused_before_core_mutation"
    ),
    "RC12": both(
        Evidence(
            "tests/test_reconciliation.py::TestCoordinator::test_immutable_latest_snapshot_wins_and_stale_cannot_open",
            HA,
        ),
        Evidence(
            "tests/test_reconciliation.py::TestCoordinator::test_reload_failure_is_fail_closed_and_not_retried_equivalently",
            HA,
        ),
    ),
    # Minimum platform.
    "HA1": ha("tests/test_ha_contract.py::test_ha1_exact_minimum_source_contract"),
    "HA2": ha("tests/test_ha_contract.py::test_ha2_exact_minimum_harness_versions"),
}


INVARIANT_TRACEABILITY: dict[str, InvariantTrace] = {
    "I1": InvariantTrace(("state_machine.decide", "ZoneController"), ("SR12",)),
    "I2": InvariantTrace(("MoistureSensorAdapter",), ("SR1",)),
    "I3": InvariantTrace(("state_machine post-soak guards",), ("SR2", "SR3")),
    "I4": InvariantTrace(("state_machine post-soak equality",), ("SR3",)),
    "I5": InvariantTrace(("state_machine", "shared OFF"), ("SR8",)),
    "I6": InvariantTrace(("state_machine MANUAL",), ("SR9", "MF4")),
    "I7": InvariantTrace(("manual guard matrix", "services"), ("MF1", "PI9")),
    "I8": InvariantTrace(("manual clamp",), ("MF2",)),
    "I9": InvariantTrace(("AUTO whole-fit guards",), ("SR12", "AR7")),
    "I10": InvariantTrace(("accounting", "start guards"), ("AC4", "PI15")),
    "I11": InvariantTrace(("startup recovery accounting",), ("PI12", "PI13", "PI16")),
    "I12": InvariantTrace(("HA-local accounting split",), ("PI17",)),
    "I13": InvariantTrace(("startup/reload lifecycle",), ("PI12", "PI13", "LC3")),
    # spec.5 strengthens I14: the clean marker is the final verified safety
    # transaction of complete Stage-1 handling, so LC4 is direct evidence.
    "I14": InvariantTrace(
        ("SafetyStore run protocol", "Stage-1 full-process shutdown owner"),
        ("PI18", "PI19", "LC4"),
    ),
    "I15": InvariantTrace(("controller write-ahead", "final ON fence"), ("ND9", "PI11")),
    "I16": InvariantTrace(
        ("ZoneController shared OFF",),
        ("AC1", "AC2", "AC3", "AC4"),
        (Evidence("tests/test_foundation.py::test_one_shared_off_implementation", PURE),),
    ),
    "I17": InvariantTrace(("ActuatorAdapter",), ("ER5", "PI14")),
    "I18": InvariantTrace(("SlotManager", "reconciliation barrier"), ("ER6", "ND14", "RC12")),
    "I19": InvariantTrace(
        ("exact-record blockers", "SlotManager"),
        ("ER4", "ER7", "AR9"),
        (Evidence("tests/test_foundation.py::test_blocker_ownership_is_safety_record_only", PURE),),
    ),
    "I20": InvariantTrace(("ZoneHistory.zone_runtime",), ("AC1", "AR11", "AR12", "LC14")),
    "I21": InvariantTrace(("SlotManager owner",), ("ER8",)),
    "I22": InvariantTrace(("session owner", "first-terminal arbitration"), ("AC2", "ND17")),
    "I23": InvariantTrace(("ZoneHistory interval",), ("AR8", "PI26")),
    "I24": InvariantTrace(("integrity reconstruction",), ("PI3", "PI8", "PI10")),
    "I25": InvariantTrace(("entry-independent services",), ("LC1", "LC2")),
    "I26": InvariantTrace(
        ("config flow", "reconciler", "ZoneRuntime derivation"), ("LC3", "AR1", "AR12", "AR16")
    ),
    "I27": InvariantTrace(
        ("entities", "state-machine isolation"),
        ("LC2",),
        (Evidence("tests/test_entities.py::TestBinarySensors::test_needs_water_semantics", HA),),
    ),
    "I28": InvariantTrace(
        ("foundation dependency audit",),
        ("HA1",),
        (Evidence("tests/test_foundation.py::test_local_only_and_no_recorder_dependency", PURE),),
    ),
    "I29": InvariantTrace(("Store setup classification",), ("PI1", "PI3", "PI5")),
    "I30": InvariantTrace(("watchdog generation",), ("SR5", "SR6", "SR10", "SR13")),
    "I31": InvariantTrace(("soak adoption", "run protocol"), ("LC5", "LC6", "LC7", "LC10")),
    "I32": InvariantTrace(("final ON authorization",), ("ND8", "ND9", "ND10", "ND14", "ND15")),
    "I33": InvariantTrace(
        ("canonical records", "ZoneRuntime ownership"),
        ("TB1", "AR10", "AR13", "AR15"),
        (Evidence("tests/test_foundation.py::test_schema1_compatibility_is_migration_only", PURE),),
    ),
    "I34": InvariantTrace(("startup config+Store union",), ("TB5", "TB6", "TB7")),
    "I35": InvariantTrace(
        ("durable identity", "reactivation", "replacement"), ("PI24", "PI25", "PI26", "AR5")
    ),
    "I36": InvariantTrace(("generation coordinator", "global barrier"), ("ND15", "RC8", "RC12")),
    "I37": InvariantTrace(
        ("tombstone persistence", "exact acknowledgement"),
        ("PI27", "PI28", "TB4", "TB11", "TB12", "TB13", "TB14"),
    ),
}


TRANSITION_EVIDENCE: dict[str, Evidence] = {
    f"T{number}": Evidence(
        f"tests/test_state_machine.py::TestTransitionTable::test_row_produces_its_transition[T{number}]",
        PURE,
    )
    for number in range(1, 60)
}


def evidence_for_invariant(invariant_id: str) -> tuple[Evidence, ...]:
    """Resolve an invariant's concrete nodes without duplicating mappings."""
    seen: set[Evidence] = set()
    result: list[Evidence] = []
    for normative_id in INVARIANT_TRACEABILITY[invariant_id].normative_ids:
        for item in NORMATIVE_TEST_EVIDENCE[normative_id]:
            if item not in seen:
                seen.add(item)
                result.append(item)
    for item in INVARIANT_TRACEABILITY[invariant_id].extra_evidence:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return tuple(result)
