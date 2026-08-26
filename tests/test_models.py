"""Slice 1 tests: pure domain models (SPECIFICATION.md §§6, 9, 10, 12, 26).

Pure layer: must run with no homeassistant package installed.
"""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta

import pytest

from custom_components.moisture_loop import const
from custom_components.moisture_loop.models import (
    ActuatorAssessment,
    ActuatorFinding,
    ActuatorIdentity,
    AppliedConfigurationShadow,
    AppliedEntityIdentity,
    AutoEvaluate,
    BlockerReason,
    CompletionReason,
    ControllerState,
    DailyRuntime,
    Decision,
    ExecuteOff,
    FaultCode,
    GuardResult,
    IdentityStatus,
    ManualClampReason,
    MoistureClassification,
    MoistureObservation,
    NormalizedZoneSettings,
    ReasonClass,
    ResourceAssessment,
    RuntimeEstimationReason,
    RuntimeLifecycle,
    SafetyRecord,
    SensorIdentity,
    SessionContext,
    SessionMode,
    TransitionInput,
    WatchdogToken,
    ZoneConfig,
    ZoneRuntime,
)

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)


def make_config(**overrides: object) -> ZoneConfig:
    base: dict[str, object] = {
        "name": "Front bed",
        "moisture_sensor": "sensor.front_bed_moisture",
        "actuator": "switch.front_bed_valve",
        "start_threshold": const.DEFAULT_START_THRESHOLD,
        "target_threshold": const.DEFAULT_TARGET_THRESHOLD,
        "pulse_duration_s": const.DEFAULT_PULSE_DURATION_S,
        "soak_duration_s": const.DEFAULT_SOAK_DURATION_S,
        "max_cycles": const.DEFAULT_MAX_CYCLES,
        "max_session_runtime_s": const.DEFAULT_MAX_SESSION_RUNTIME_S,
        "max_daily_runtime_s": const.DEFAULT_MAX_DAILY_RUNTIME_S,
        "min_session_interval_s": const.DEFAULT_MIN_SESSION_INTERVAL_S,
        "sensor_max_age_s": const.DEFAULT_SENSOR_MAX_AGE_S,
        "actuator_confirm_timeout_s": const.DEFAULT_ACTUATOR_CONFIRM_TIMEOUT_S,
        "manual_max_duration_s": const.DEFAULT_MANUAL_MAX_DURATION_S,
    }
    base.update(overrides)
    return ZoneConfig(**base)  # type: ignore[arg-type]


def valid_observation(
    value: float = 27.0,
    reported_at: datetime = NOW,
    age_s: float = 0.0,
) -> MoistureObservation:
    return MoistureObservation(
        value=value,
        classification=MoistureClassification.VALID,
        reported_at_utc=reported_at,
        age_s=age_s,
    )


# ---------------------------------------------------------------------------
# Enum completeness and round-trip-safe representations
# ---------------------------------------------------------------------------


class TestEnumCompleteness:
    def test_controller_states_exact(self) -> None:
        assert {s.value for s in ControllerState} == {
            "disabled",
            "idle",
            "watering",
            "soaking",
            "fault",
        }

    def test_session_modes_exact(self) -> None:
        assert {m.value for m in SessionMode} == {"auto", "manual"}

    def test_moisture_classifications_exact(self) -> None:
        assert {c.value for c in MoistureClassification} == {
            "valid",
            "stale",
            "invalid",
            "unavailable",
        }

    def test_fault_codes_exact(self) -> None:
        assert {f.value for f in FaultCode} == {
            "sensor_unavailable",
            "sensor_stale",
            "sensor_invalid",
            "actuator_unavailable",
            "actuator_on_timeout",
            "actuator_off_timeout",
            "configuration_invalid",
            "restored_from_unsafe_state",
        }

    def test_completion_reasons_exact_fourteen(self) -> None:
        assert {r.value for r in CompletionReason} == {
            "target_reached",
            "manual_complete",
            "max_cycles",
            "max_session_runtime",
            "daily_runtime_limit",
            "user_stop",
            "zone_disabled",
            "external_actuator_state_change",
            "config_reload",
            "config_changed",
            "home_assistant_shutdown",
            "restart_recovery",
            "sensor_fault",
            "actuator_fault",
        }
        assert len(CompletionReason) == 14

    def test_estimation_reasons_exact(self) -> None:
        assert {r.value for r in RuntimeEstimationReason} == {
            "none",
            "restart_found_on",
            "restart_found_off_unknown_stop",
            "off_unconfirmed",
        }

    def test_blocker_reasons_exact(self) -> None:
        assert {r.value for r in BlockerReason} == {
            "external_flow",
            "integration_off_unconfirmed",
            "actuator_not_proven_off",
        }

    def test_clamp_reasons_exact(self) -> None:
        assert {r.value for r in ManualClampReason} == {
            "manual_max_duration",
            "max_session_runtime",
            "remaining_daily_budget",
        }

    def test_startup_findings_exact(self) -> None:
        assert {f.value for f in ActuatorFinding} == {"on", "off", "unproven"}

    @pytest.mark.parametrize(
        "enum_cls",
        [
            ControllerState,
            SessionMode,
            MoistureClassification,
            FaultCode,
            CompletionReason,
            RuntimeEstimationReason,
            BlockerReason,
            ManualClampReason,
            ActuatorFinding,
        ],
    )
    def test_round_trip_by_value(self, enum_cls: type) -> None:
        for member in enum_cls:
            assert enum_cls(member.value) is member
            assert isinstance(member.value, str)


class TestFaultMatrix:
    """§26.1 fault property matrix."""

    def test_every_fault_blocks_automatic(self) -> None:
        assert all(f.blocks_automatic for f in FaultCode)

    def test_manual_allowed_only_for_sensor_faults(self) -> None:
        allowed = {f for f in FaultCode if f.allows_manual}
        assert allowed == {
            FaultCode.SENSOR_UNAVAILABLE,
            FaultCode.SENSOR_STALE,
            FaultCode.SENSOR_INVALID,
        }

    def test_auto_clear_set(self) -> None:
        auto = {f for f in FaultCode if f.auto_clears}
        assert auto == {
            FaultCode.SENSOR_UNAVAILABLE,
            FaultCode.SENSOR_STALE,
            FaultCode.SENSOR_INVALID,
            FaultCode.ACTUATOR_UNAVAILABLE,
            FaultCode.ACTUATOR_ON_TIMEOUT,
        }

    def test_user_ack_set(self) -> None:
        ack = {f for f in FaultCode if f.requires_user_ack}
        assert ack == {
            FaultCode.ACTUATOR_OFF_TIMEOUT,
            FaultCode.RESTORED_FROM_UNSAFE_STATE,
        }

    def test_reconfigure_only(self) -> None:
        assert FaultCode.CONFIGURATION_INVALID.requires_reconfigure
        assert not any(
            f.requires_reconfigure for f in FaultCode if f is not FaultCode.CONFIGURATION_INVALID
        )


class TestReasonClasses:
    def test_classes(self) -> None:
        expected = {
            CompletionReason.TARGET_REACHED: ReasonClass.SUCCESS,
            CompletionReason.MANUAL_COMPLETE: ReasonClass.SUCCESS,
            CompletionReason.MAX_CYCLES: ReasonClass.CONSTRAINED,
            CompletionReason.MAX_SESSION_RUNTIME: ReasonClass.CONSTRAINED,
            CompletionReason.DAILY_RUNTIME_LIMIT: ReasonClass.CONSTRAINED,
            CompletionReason.USER_STOP: ReasonClass.CANCELLATION,
            CompletionReason.ZONE_DISABLED: ReasonClass.CANCELLATION,
            CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE: ReasonClass.CANCELLATION,
            CompletionReason.CONFIG_RELOAD: ReasonClass.CANCELLATION,
            CompletionReason.CONFIG_CHANGED: ReasonClass.CANCELLATION,
            CompletionReason.HOME_ASSISTANT_SHUTDOWN: ReasonClass.CANCELLATION,
            CompletionReason.RESTART_RECOVERY: ReasonClass.RECOVERY,
            CompletionReason.SENSOR_FAULT: ReasonClass.FAULT,
            CompletionReason.ACTUATOR_FAULT: ReasonClass.FAULT,
        }
        for reason, cls in expected.items():
            assert reason.reason_class is cls


# ---------------------------------------------------------------------------
# ZoneConfig §9 boundary matrix
# ---------------------------------------------------------------------------


class TestZoneConfigBounds:
    def test_defaults_are_valid(self) -> None:
        make_config().validate()

    @pytest.mark.parametrize(
        ("field_name", "good_values", "bad_values"),
        [
            ("name", ["a", "x" * 64], ["", "x" * 65]),
            ("start_threshold", [1.0, 30.0], [0.0, 0.9, 100.0]),
            ("target_threshold", [40.0, 100.0], [1.9, 101.0]),
            ("pulse_duration_s", [30, 1800], [29, 1801]),
            ("soak_duration_s", [60, 14400], [59, 14401]),
            ("max_cycles", [1, 20], [0, 21]),
            ("max_session_runtime_s", [300, 14400], [299, 14401]),
            ("max_daily_runtime_s", [300, 43200], [299, 43201]),
            ("min_session_interval_s", [900, 604800], [899, 604801]),
            ("sensor_max_age_s", [300, 86400], [299, 86401]),
            ("actuator_confirm_timeout_s", [5, 300], [4, 301]),
            ("manual_max_duration_s", [60, 7200], [59, 7201]),
        ],
    )
    def test_field_boundaries(
        self, field_name: str, good_values: list[object], bad_values: list[object]
    ) -> None:
        for good in good_values:
            cfg = make_config(**{field_name: good})
            assert not cfg.validation_errors(), f"{field_name}={good} should be valid"
        for bad in bad_values:
            cfg = make_config(**{field_name: bad})
            assert cfg.validation_errors(), f"{field_name}={bad} should be invalid"

    def test_start_strictly_less_than_target(self) -> None:
        assert not make_config(start_threshold=39.0, target_threshold=40.0).validation_errors()
        assert make_config(start_threshold=40.0, target_threshold=40.0).validation_errors()
        assert make_config(start_threshold=41.0, target_threshold=40.0).validation_errors()

    def test_start_99_target_100_is_valid(self) -> None:
        assert not make_config(start_threshold=99.0, target_threshold=100.0).validation_errors()

    def test_session_and_daily_lower_bound_is_pulse_duration(self) -> None:
        # pulse == session == daily minimum is allowed
        cfg = make_config(pulse_duration_s=600, max_session_runtime_s=600, max_daily_runtime_s=600)
        assert not cfg.validation_errors()
        # session below pulse is invalid
        assert make_config(pulse_duration_s=600, max_session_runtime_s=599).validation_errors()
        # daily below pulse is invalid
        assert make_config(pulse_duration_s=600, max_daily_runtime_s=599).validation_errors()

    def test_entity_domain_checks(self) -> None:
        assert make_config(moisture_sensor="binary_sensor.x").validation_errors()
        assert make_config(moisture_sensor="sensor").validation_errors()
        assert make_config(actuator="light.x").validation_errors()
        assert not make_config(actuator="valve.bed").validation_errors()
        assert not make_config(actuator="switch.bed").validation_errors()

    def test_validate_raises_with_all_violations(self) -> None:
        cfg = make_config(start_threshold=0.0, max_cycles=0)
        with pytest.raises(ValueError) as excinfo:
            cfg.validate()
        message = str(excinfo.value)
        assert "start_threshold" in message
        assert "max_cycles" in message

    def test_config_is_frozen_and_deterministic(self) -> None:
        a, b = make_config(), make_config()
        assert a == b
        with pytest.raises(FrozenInstanceError):
            a.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MoistureObservation
# ---------------------------------------------------------------------------


class TestMoistureObservation:
    def test_valid_observation_ok(self) -> None:
        valid_observation().validate()

    def test_boundary_values_0_and_100_are_valid(self) -> None:
        valid_observation(value=0.0).validate()
        valid_observation(value=100.0).validate()

    @pytest.mark.parametrize("bad", [-0.1, 100.1, float("nan"), float("inf"), None])
    def test_valid_classification_rejects_bad_value(self, bad: float | None) -> None:
        obs = MoistureObservation(
            value=bad,
            classification=MoistureClassification.VALID,
            reported_at_utc=NOW,
            age_s=0.0,
        )
        with pytest.raises(ValueError):
            obs.validate()

    def test_valid_requires_reported_at_and_age(self) -> None:
        with pytest.raises(ValueError):
            MoistureObservation(27.0, MoistureClassification.VALID, None, 0.0).validate()
        with pytest.raises(ValueError):
            MoistureObservation(27.0, MoistureClassification.VALID, NOW, None).validate()
        with pytest.raises(ValueError):
            MoistureObservation(27.0, MoistureClassification.VALID, NOW, -1.0).validate()

    def test_naive_datetime_rejected(self) -> None:
        naive = datetime(2026, 8, 21, 12, 0, 0)
        with pytest.raises(ValueError):
            MoistureObservation(27.0, MoistureClassification.VALID, naive, 0.0).validate()

    def test_unavailable_must_not_carry_value(self) -> None:
        MoistureObservation(None, MoistureClassification.UNAVAILABLE, None, None).validate()
        with pytest.raises(ValueError):
            MoistureObservation(27.0, MoistureClassification.UNAVAILABLE, None, None).validate()

    def test_invalid_may_carry_raw_value(self) -> None:
        MoistureObservation(-5.0, MoistureClassification.INVALID, NOW, 0.0).validate()
        MoistureObservation(None, MoistureClassification.INVALID, None, None).validate()

    def test_freshness_equality_is_fresh(self) -> None:
        """§6: reported_at_utc >= now - sensor_max_age; equality is fresh."""
        max_age = 7200
        boundary = NOW - timedelta(seconds=max_age)
        assert valid_observation(reported_at=boundary).is_fresh(NOW, max_age)
        just_older = boundary - timedelta(microseconds=1)
        assert not valid_observation(reported_at=just_older).is_fresh(NOW, max_age)

    def test_fresh_until(self) -> None:
        obs = valid_observation(reported_at=NOW)
        assert obs.fresh_until(7200) == NOW + timedelta(seconds=7200)
        no_time = MoistureObservation(None, MoistureClassification.UNAVAILABLE, None, None)
        assert no_time.fresh_until(7200) is None


# ---------------------------------------------------------------------------
# Session structures and supporting models
# ---------------------------------------------------------------------------


def make_session(**overrides: object) -> SessionContext:
    base: dict[str, object] = {
        "session_id": "sess-1",
        "owner_run_id": "run-1",
        "config_fingerprint": "fp-1",
        "mode": SessionMode.AUTO,
        "started_at_utc": NOW,
    }
    base.update(overrides)
    return SessionContext(**base)  # type: ignore[arg-type]


class TestSessionContext:
    def test_defaults(self) -> None:
        s = make_session()
        assert s.cycle == 0
        assert s.session_runtime_s == 0.0
        assert s.runtime_estimation_reason is RuntimeEstimationReason.NONE
        assert s.pending_termination_reason is None
        assert s.manual_clamp_reasons == ()

    def test_evolve_returns_new_frozen_instance(self) -> None:
        s = make_session()
        s2 = s.evolve(cycle=3)
        assert s2.cycle == 3
        assert s.cycle == 0
        assert s2 is not s
        with pytest.raises(FrozenInstanceError):
            s.cycle = 5  # type: ignore[misc]

    def test_retained_fault_must_be_sensor_only(self) -> None:
        make_session(retained_sensor_fault=FaultCode.SENSOR_STALE)
        with pytest.raises(ValueError):
            make_session(retained_sensor_fault=FaultCode.ACTUATOR_OFF_TIMEOUT)

    def test_naive_start_rejected(self) -> None:
        with pytest.raises(ValueError):
            make_session(started_at_utc=datetime(2026, 8, 21))

    def test_equality_deterministic(self) -> None:
        assert make_session() == make_session()
        assert make_session(cycle=1) != make_session(cycle=2)


class TestSupportingModels:
    def test_watchdog_token_requires_utc(self) -> None:
        WatchdogToken(1, NOW)
        with pytest.raises(ValueError):
            WatchdogToken(1, datetime(2026, 8, 21))

    def test_watchdog_token_equality_exact(self) -> None:
        assert WatchdogToken(1, NOW) == WatchdogToken(1, NOW)
        assert WatchdogToken(1, NOW) != WatchdogToken(2, NOW)
        assert WatchdogToken(1, NOW) != WatchdogToken(1, NOW + timedelta(seconds=1))

    def test_daily_runtime_rejects_negative(self) -> None:
        DailyRuntime(date(2026, 8, 21), 0.0)
        with pytest.raises(ValueError):
            DailyRuntime(date(2026, 8, 21), -1.0)

    def test_guard_result_invariants(self) -> None:
        GuardResult(passed=True)
        GuardResult(passed=False, failed_guards=(const.GUARD_FRESH,))
        with pytest.raises(ValueError):
            GuardResult(passed=True, failed_guards=(const.GUARD_FRESH,))
        with pytest.raises(ValueError):
            GuardResult(passed=False)

    def test_actuator_assessment_contradiction_rejected(self) -> None:
        ActuatorAssessment(available=True, proven_off=True, observed_on=False)
        with pytest.raises(ValueError):
            ActuatorAssessment(available=True, proven_off=True, observed_on=True)


class TestTransitionStructures:
    def test_transition_input_validation(self) -> None:
        good = TransitionInput(
            now_utc=NOW,
            config=make_config(),
            state=ControllerState.IDLE,
            enabled=True,
            session=None,
            active_fault=None,
            secondary_fault=None,
            observation=valid_observation(),
            daily_runtime_s=0.0,
            last_session_end_utc=None,
            actuator=ActuatorAssessment(True, True, False),
            resource=ResourceAssessment(slot_granted=False, blockers_empty=True),
            armed_watchdog=None,
            event=AutoEvaluate(),
        )
        assert good.state is ControllerState.IDLE
        with pytest.raises(ValueError):
            TransitionInput(
                now_utc=datetime(2026, 8, 21),
                config=make_config(),
                state=ControllerState.IDLE,
                enabled=True,
                session=None,
                active_fault=None,
                secondary_fault=None,
                observation=valid_observation(),
                daily_runtime_s=0.0,
                last_session_end_utc=None,
                actuator=ActuatorAssessment(True, True, False),
                resource=ResourceAssessment(False, True),
                armed_watchdog=None,
                event=AutoEvaluate(),
            )
        with pytest.raises(ValueError):
            TransitionInput(
                now_utc=NOW,
                config=make_config(),
                state=ControllerState.IDLE,
                enabled=True,
                session=None,
                active_fault=None,
                secondary_fault=None,
                observation=valid_observation(),
                daily_runtime_s=-1.0,
                last_session_end_utc=None,
                actuator=ActuatorAssessment(True, True, False),
                resource=ResourceAssessment(False, True),
                armed_watchdog=None,
                event=AutoEvaluate(),
            )

    def test_decision_final_session_requires_clear(self) -> None:
        with pytest.raises(ValueError):
            Decision(transition_id=None, new_state=None, final_session=make_session())
        Decision(
            transition_id=None,
            new_state=None,
            clear_session=True,
            final_session=make_session(),
        )

    def test_decision_invariants(self) -> None:
        Decision(transition_id=None, new_state=None, no_op=True)
        with pytest.raises(ValueError):
            Decision(transition_id=None, new_state=ControllerState.IDLE, no_op=True)
        with pytest.raises(ValueError):
            Decision(transition_id=None, new_state=None, actions=(ExecuteOff(),), no_op=True)
        with pytest.raises(ValueError):
            Decision(
                transition_id=None,
                new_state=None,
                session=make_session(),
                clear_session=True,
            )


class TestPureBoundary:
    def test_importing_models_does_not_import_homeassistant(self) -> None:
        try:
            import homeassistant  # noqa: F401
        except ImportError:
            pass
        else:
            pytest.skip(
                "boundary proof runs in the pure environment; here the HA "
                "harness itself imports homeassistant"
            )
        assert "custom_components.moisture_loop.models" in sys.modules
        assert not any(m == "homeassistant" or m.startswith("homeassistant.") for m in sys.modules)

    def test_defaults_within_bounds(self) -> None:
        assert const.DEFAULT_START_THRESHOLD < const.DEFAULT_TARGET_THRESHOLD
        make_config().validate()


class TestRemainingBranches:
    def test_is_fresh_without_report_time_is_never_fresh(self) -> None:
        obs = MoistureObservation(None, MoistureClassification.UNAVAILABLE, None, None)
        assert not obs.is_fresh(NOW, 7200)

    def test_non_utc_timezone_rejected(self) -> None:
        from datetime import timezone

        brisbane_like = timezone(timedelta(hours=10))
        with pytest.raises(ValueError):
            WatchdogToken(1, datetime(2026, 8, 21, 12, tzinfo=brisbane_like))

    def test_transition_input_validates_last_session_end(self) -> None:
        with pytest.raises(ValueError):
            TransitionInput(
                now_utc=NOW,
                config=make_config(),
                state=ControllerState.IDLE,
                enabled=True,
                session=None,
                active_fault=None,
                secondary_fault=None,
                observation=valid_observation(),
                daily_runtime_s=0.0,
                last_session_end_utc=datetime(2026, 8, 21),
                actuator=ActuatorAssessment(True, True, False),
                resource=ResourceAssessment(False, True),
                armed_watchdog=None,
                event=AutoEvaluate(),
            )


class TestSpec4CanonicalModels:
    def test_store_schema_and_lifecycle_are_exact(self) -> None:
        assert const.STORE_SCHEMA_VERSION == 2
        assert {value.value for value in RuntimeLifecycle} == {
            "active",
            "delete_pending",
            "retired",
        }
        assert {value.value for value in ControllerState} == {
            "disabled",
            "idle",
            "watering",
            "soaking",
            "fault",
        }

    def test_actuator_identity_is_durable_and_domain_coherent(self) -> None:
        identity = ActuatorIdentity(
            "registry-uuid",
            "switch.front_bed_valve",
            "switch",
            IdentityStatus.REGISTRY_CONFIRMED,
            "switch.turn_off",
            30,
        )
        assert identity.registry_entry_id == "registry-uuid"
        with pytest.raises(ValueError, match="OFF service"):
            ActuatorIdentity(
                "registry-uuid",
                "switch.front_bed_valve",
                "switch",
                IdentityStatus.REGISTRY_CONFIRMED,
                "valve.close_valve",
                30,
            )

    def test_unresolved_identity_does_not_invent_schema1_values(self) -> None:
        identity = ActuatorIdentity(None, None, None, IdentityStatus.MISSING, None, None)
        assert identity.registry_entry_id is None
        assert identity.last_known_entity_id is None
        assert identity.domain is None

    def test_applied_shadow_is_frozen_normalized_data(self) -> None:
        config = make_config()
        shadow = AppliedConfigurationShadow(
            subentry_id="zone-a",
            config_fingerprint="config-fp",
            entry_snapshot_fingerprint="snapshot-fp",
            applied_generation=1,
            normalized_settings=NormalizedZoneSettings.from_config(config),
            sensor_identity=AppliedEntityIdentity(None, config.moisture_sensor, "sensor"),
            actuator_identity=AppliedEntityIdentity(None, config.actuator, "switch"),
        )
        with pytest.raises(FrozenInstanceError):
            shadow.applied_generation = 2  # type: ignore[misc]

    def test_zone_runtime_rejects_actuator_fault_ownership(self) -> None:
        with pytest.raises(ValueError, match="zone_fault"):
            ZoneRuntime(
                enabled=True,
                state=ControllerState.FAULT,
                zone_fault=FaultCode.ACTUATOR_OFF_TIMEOUT,
                secondary_fault=None,
                sensor_identity=SensorIdentity(None, "sensor.front_bed_moisture"),
                last_session_summary=None,
                session=None,
            )

    def test_safety_record_has_no_logical_zone_authority_fields(self) -> None:
        fields = set(SafetyRecord.__dataclass_fields__)
        assert fields.isdisjoint({"enabled", "state", "sensor_identity", "zone_fault", "session"})
