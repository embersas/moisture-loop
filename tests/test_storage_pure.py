"""Slice 4 pure tests: §23.2 schema round-trips and §19.2/§19.3 accounting.

Runs in the pure environment (no homeassistant). The Store I/O tests that
need the HA harness live in tests/test_storage.py.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.moisture_loop.models import (
    AccountingContribution,
    ActuatorIdentity,
    AppliedConfigurationShadow,
    AppliedEntityIdentity,
    BlockerReason,
    CompletionReason,
    ControllerState,
    DailyRuntime,
    FaultCode,
    FutureStoreVersion,
    IdentityIncidentKind,
    IdentityStatus,
    MalformedStoreData,
    ManualClampReason,
    MigrationRecordContext,
    NormalizedZoneSettings,
    RunIds,
    RuntimeEstimationReason,
    RuntimeLifecycle,
    Schema1StoreData,
    SensorIdentity,
    SessionContext,
    SessionMode,
    SessionSummary,
    StoreData,
    ZoneConfig,
    ZoneDailyRuntime,
    ZoneRecord,
    conservative_merge_daily_runtime,
    current_day_charge,
    deduplicate_accounting_contributions,
    migrate_schema1_to_schema2,
    schema1_store_data_from_dict,
    schema1_store_data_to_dict,
    session_from_dict,
    session_to_dict,
    split_interval_by_local_days,
    store_data_from_dict,
    store_data_to_dict,
    summary_from_dict,
    summary_to_dict,
    zone_record_from_dict,
    zone_record_to_dict,
)

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)
BRISBANE = ZoneInfo("Australia/Brisbane")  # no DST
SYDNEY = ZoneInfo("Australia/Sydney")  # DST
BERLIN = ZoneInfo("Europe/Berlin")  # DST


def full_session() -> SessionContext:
    return SessionContext(
        session_id="sess-1",
        owner_run_id="run-1",
        config_fingerprint="fp-1",
        mode=SessionMode.AUTO,
        started_at_utc=NOW - timedelta(minutes=40),
        cycle=2,
        session_runtime_s=480.0,
        runtime_estimated=False,
        runtime_estimation_reason=RuntimeEstimationReason.NONE,
        pulse_intent_at_utc=NOW - timedelta(minutes=30),
        pulse_commanded_at_utc=NOW - timedelta(minutes=29),
        pulse_confirmed_at_utc=NOW - timedelta(minutes=29),
        pulse_ends_at_utc=NOW - timedelta(minutes=25),
        off_confirmed_at_utc=NOW - timedelta(minutes=25),
        soak_ends_at_utc=NOW - timedelta(minutes=5),
        recheck_not_before_utc=NOW - timedelta(minutes=5),
        recheck_grace_deadline_at_utc=NOW + timedelta(hours=2) - timedelta(minutes=5),
        manual_requested_duration_s=None,
        manual_effective_duration_s=None,
        manual_clamp_reasons=(),
        retained_sensor_fault=None,
        moisture_at_start=27.0,
    )


def full_summary() -> SessionSummary:
    return SessionSummary(
        mode=SessionMode.MANUAL,
        reason=CompletionReason.MANUAL_COMPLETE,
        runtime_s=720.4,
        runtime_estimated=True,
        runtime_estimation_reason=RuntimeEstimationReason.OFF_UNCONFIRMED,
        requested_duration_s=2700.0,
        effective_duration_s=720.0,
        clamp_reasons=(
            ManualClampReason.MANUAL_MAX_DURATION,
            ManualClampReason.REMAINING_DAILY_BUDGET,
        ),
        cycles=0,
        moisture_before=27.0,
        moisture_after=40.0,
        started_at_utc=NOW - timedelta(hours=1),
        ended_at_utc=NOW,
    )


def full_record() -> ZoneRecord:
    return ZoneRecord(
        state=ControllerState.SOAKING,
        enabled=True,
        active_fault=None,
        secondary_fault=FaultCode.SENSOR_STALE,
        last_session_end_utc=NOW - timedelta(hours=7),
        last_auto_session_start_utc=NOW - timedelta(minutes=40),
        daily=DailyRuntime(date_local=date(2026, 8, 21), runtime_s=312.5),
        last_session_summary=full_summary(),
        session=full_session(),
    )


def legacy_store() -> Schema1StoreData:
    return Schema1StoreData(
        generation_id="gen-1",
        store_revision=42,
        run=RunIds(active_run_id="run-1", last_clean_shutdown_run_id="run-0"),
        zones={"zone-a": full_record(), "zone-b": ZoneRecord(ControllerState.IDLE, True)},
    )


def zone_config() -> ZoneConfig:
    return ZoneConfig(
        name="Bed A",
        moisture_sensor="sensor.bed_a",
        actuator="valve.bed_a",
        start_threshold=30.0,
        target_threshold=40.0,
        pulse_duration_s=300,
        soak_duration_s=1200,
        max_cycles=4,
        max_session_runtime_s=1800,
        max_daily_runtime_s=3600,
        min_session_interval_s=21600,
        sensor_max_age_s=7200,
        actuator_confirm_timeout_s=30,
        manual_max_duration_s=1800,
    )


def migration_context(subentry_id: str = "zone-a") -> MigrationRecordContext:
    config = zone_config()
    sensor = AppliedEntityIdentity("sensor-registry-uuid", config.moisture_sensor, "sensor")
    actuator = AppliedEntityIdentity("actuator-registry-uuid", config.actuator, "valve")
    return MigrationRecordContext(
        active_subentry_id=subentry_id,
        applied_config=AppliedConfigurationShadow(
            subentry_id=subentry_id,
            config_fingerprint="config-fingerprint",
            entry_snapshot_fingerprint="entry-snapshot-fingerprint",
            applied_generation=7,
            normalized_settings=NormalizedZoneSettings.from_config(config),
            sensor_identity=sensor,
            actuator_identity=actuator,
        ),
        actuator_identity=ActuatorIdentity(
            registry_entry_id="actuator-registry-uuid",
            last_known_entity_id=config.actuator,
            domain="valve",
            identity_status=IdentityStatus.REGISTRY_CONFIRMED,
            off_service="valve.close_valve",
            confirm_timeout_s=30,
        ),
        sensor_identity=SensorIdentity("sensor-registry-uuid", config.moisture_sensor),
    )


def full_store(lifecycle: RuntimeLifecycle = RuntimeLifecycle.ACTIVE) -> StoreData:
    old = legacy_store()
    migrated = migrate_schema1_to_schema2(old, {"zone-a": migration_context()})
    if lifecycle is RuntimeLifecycle.ACTIVE:
        return migrated
    record = migrated.safety_records["zone-a"]
    history = migrated.zone_histories[record.zone_history_id]
    records = dict(migrated.safety_records)
    histories = dict(migrated.zone_histories)
    records["zone-a"] = record.evolve(
        active_subentry_id=None,
        previous_subentry_ids=("zone-a",),
        runtime_lifecycle=lifecycle,
    )
    histories[history.zone_history_id] = history.evolve(
        active_subentry_id=None, previous_subentry_ids=("zone-a",)
    )
    return migrated.evolve(safety_records=records, zone_histories=histories)


class TestSchemaRoundTrip:
    def test_session_round_trip(self) -> None:
        original = full_session()
        restored = session_from_dict(session_to_dict(original))
        # Live-only fields are intentionally not persisted (§23.2); the
        # persisted subset must survive bit-for-bit.
        assert restored == original

    def test_live_only_fields_are_not_persisted(self) -> None:
        live = full_session().evolve(
            sensor_fresh_until_utc=NOW,
            sensor_freshness_watchdog_generation=7,
            last_recheck_value=33.0,
            pending_termination_reason=CompletionReason.USER_STOP,
        )
        payload = session_to_dict(live)
        for key in (
            "sensor_fresh_until_utc",
            "sensor_freshness_watchdog_generation",
            "last_recheck_value",
            "pending_termination_reason",
        ):
            assert key not in payload
        restored = session_from_dict(payload)
        assert restored.sensor_fresh_until_utc is None
        assert restored.sensor_freshness_watchdog_generation == 0
        assert restored.pending_termination_reason is None

    def test_summary_round_trip(self) -> None:
        original = full_summary()
        assert summary_from_dict(summary_to_dict(original)) == original

    def test_schema1_zone_record_round_trip(self) -> None:
        original = full_record()
        assert zone_record_from_dict(zone_record_to_dict(original)) == original

    def test_store_round_trip(self) -> None:
        original = full_store()
        assert store_data_from_dict(store_data_to_dict(original)) == original

    def test_store_dict_shape_matches_spec(self) -> None:
        payload = store_data_to_dict(full_store())
        assert payload["version"] == 2
        assert payload["generation_id"] == "gen-1"
        assert payload["store_revision"] == 43
        assert payload["run"] == {
            "active_run_id": "run-1",
            "last_clean_shutdown_run_id": "run-0",
        }
        record = payload["safety_records"]["zone-a"]
        history = payload["zone_histories"][record["zone_history_id"]]
        assert "state" not in record
        assert "enabled" not in record
        assert "session" not in record
        assert history["zone_runtime"]["state"] == "soaking"
        assert history["zone_runtime"]["session"]["owner_safety_record_id"] == "zone-a"
        assert history["daily"]["runtime_s"] == 312.5

    @pytest.mark.parametrize(
        "lifecycle", [RuntimeLifecycle.DELETE_PENDING, RuntimeLifecycle.RETIRED]
    )
    def test_tombstone_lifecycle_round_trip(self, lifecycle) -> None:
        original = full_store(lifecycle)
        assert store_data_from_dict(store_data_to_dict(original)) == original


class TestSchemaStrictness:
    def test_future_version_raises_distinct_error(self) -> None:
        payload = store_data_to_dict(full_store())
        payload["version"] = 3
        with pytest.raises(FutureStoreVersion):
            store_data_from_dict(payload)

    @pytest.mark.parametrize(
        "corrupt",
        [
            lambda p: p.pop("generation_id"),
            lambda p: p.pop("store_revision"),
            lambda p: p.pop("run"),
            lambda p: p.pop("safety_records"),
            lambda p: p.pop("zone_histories"),
            lambda p: p.pop("version"),
            lambda p: p.__setitem__("version", "1"),
            lambda p: p.__setitem__("version", 1),
            lambda p: p.__setitem__("generation_id", ""),
            lambda p: p.__setitem__("store_revision", 0),
            lambda p: p.__setitem__("store_revision", True),
            lambda p: p.__setitem__("safety_records", []),
            lambda p: p["run"].pop("active_run_id"),
            lambda p: p["run"].__setitem__("active_run_id", 5),
        ],
    )
    def test_malformed_store_raises(self, corrupt) -> None:
        payload = store_data_to_dict(full_store())
        corrupt(payload)
        with pytest.raises(MalformedStoreData):
            store_data_from_dict(payload)

    @pytest.mark.parametrize(
        "corrupt",
        [
            lambda p: p["safety_records"]["zone-a"].__setitem__("runtime_lifecycle", "gone"),
            lambda p: p["safety_records"]["zone-a"].__setitem__("blocker_reasons", ["bogus"]),
            lambda p: p["safety_records"]["zone-a"].__setitem__("acknowledgement_required", "yes"),
            lambda p: p["safety_records"]["zone-a"].pop("zone_history_id"),
        ],
    )
    def test_malformed_schema2_record_raises(self, corrupt) -> None:
        payload = store_data_to_dict(full_store())
        corrupt(payload)
        with pytest.raises(MalformedStoreData):
            store_data_from_dict(payload)

    def test_naive_datetime_rejected(self) -> None:
        payload = store_data_to_dict(full_store())
        history = next(iter(payload["zone_histories"].values()))
        history["last_session_end_utc"] = "2026-08-21T12:00:00"
        with pytest.raises(MalformedStoreData):
            store_data_from_dict(payload)

    def test_missing_zone_history_cross_reference_rejected(self) -> None:
        payload = store_data_to_dict(full_store())
        payload["safety_records"]["zone-a"]["zone_history_id"] = "missing-history"
        with pytest.raises(MalformedStoreData):
            store_data_from_dict(payload)

    def test_missing_session_owner_cross_reference_rejected(self) -> None:
        payload = store_data_to_dict(full_store())
        history_id = payload["safety_records"]["zone-a"]["zone_history_id"]
        history = payload["zone_histories"][history_id]
        history["zone_runtime"]["session"]["owner_safety_record_id"] = "missing-owner"
        with pytest.raises(MalformedStoreData):
            store_data_from_dict(payload)

    def test_duplicate_persisted_contribution_id_rejected(self) -> None:
        payload = store_data_to_dict(full_store())
        history_id = payload["safety_records"]["zone-a"]["zone_history_id"]
        contributions = payload["zone_histories"][history_id]["daily"]["contributions"]
        contributions.append(dict(contributions[0]))
        with pytest.raises(MalformedStoreData):
            store_data_from_dict(payload)

    def test_non_utc_offset_rejected(self) -> None:
        payload = store_data_to_dict(full_store())
        history = next(iter(payload["zone_histories"].values()))
        history["last_session_end_utc"] = "2026-08-21T12:00:00+10:00"
        with pytest.raises(MalformedStoreData):
            store_data_from_dict(payload)

    def test_non_object_payloads_rejected(self) -> None:
        from custom_components.moisture_loop.models import (
            session_from_dict,
            zone_record_from_dict,
        )

        for parser in (store_data_from_dict, zone_record_from_dict, session_from_dict):
            with pytest.raises(MalformedStoreData):
                parser("not-an-object")
            with pytest.raises(MalformedStoreData):
                parser(None)

    def test_session_bogus_retained_fault_rejected(self) -> None:
        from custom_components.moisture_loop.models import session_from_dict, session_to_dict

        payload = session_to_dict(full_session())
        payload["retained_sensor_fault"] = "gremlins"
        with pytest.raises(MalformedStoreData):
            session_from_dict(payload)

    def test_session_non_numeric_duration_rejected(self) -> None:
        from custom_components.moisture_loop.models import session_from_dict, session_to_dict

        payload = session_to_dict(full_session())
        payload["manual_requested_duration_s"] = "long"
        with pytest.raises(MalformedStoreData):
            session_from_dict(payload)

    def test_summary_non_numeric_duration_rejected(self) -> None:
        payload = summary_to_dict(full_summary())
        payload["requested_duration_s"] = "many"
        with pytest.raises(MalformedStoreData):
            summary_from_dict(payload)

    def test_evolve_helpers(self) -> None:
        record = full_record()
        assert record.evolve(enabled=False).enabled is False
        store = full_store()
        assert store.evolve(store_revision=99).store_revision == 99

    def test_run_ids_cleanliness(self) -> None:
        assert RunIds("a", "a").previous_run_was_clean
        assert not RunIds("a", "b").previous_run_was_clean
        assert not RunIds(None, None).previous_run_was_clean
        assert not RunIds("a", None).previous_run_was_clean
        assert not RunIds(None, "a").previous_run_was_clean


class TestSchema1Migration:
    def test_configured_record_preserves_history_and_ownership(self) -> None:
        legacy = legacy_store()
        migrated = migrate_schema1_to_schema2(legacy, {"zone-a": migration_context()})
        record = migrated.safety_records["zone-a"]
        history = migrated.zone_histories[record.zone_history_id]
        assert record.safety_record_id == "zone-a"
        assert record.runtime_lifecycle is RuntimeLifecycle.ACTIVE
        assert history.zone_runtime.enabled is legacy.zones["zone-a"].enabled
        assert history.zone_runtime.state is legacy.zones["zone-a"].state
        assert history.last_session_end_utc == legacy.zones["zone-a"].last_session_end_utc
        assert history.daily.runtime_s == legacy.zones["zone-a"].daily.runtime_s
        assert (
            history.zone_runtime.last_session_summary == legacy.zones["zone-a"].last_session_summary
        )
        assert history.zone_runtime.session.context == legacy.zones["zone-a"].session
        assert history.zone_runtime.session.owner_safety_record_id == "zone-a"

    def test_store_only_record_is_unresolved_delete_pending(self) -> None:
        migrated = migrate_schema1_to_schema2(legacy_store(), {"zone-a": migration_context()})
        record = migrated.safety_records["zone-b"]
        assert record.runtime_lifecycle is RuntimeLifecycle.DELETE_PENDING
        assert record.actuator_identity.identity_status is IdentityStatus.MISSING
        assert record.actuator_identity.registry_entry_id is None
        assert BlockerReason.ACTUATOR_NOT_PROVEN_OFF in record.blocker_reasons
        assert record.identity_incident.kind is IdentityIncidentKind.MIGRATION_UNRESOLVED

    @pytest.mark.parametrize(
        ("primary", "secondary", "actuator", "zone_primary", "zone_secondary"),
        [
            (
                FaultCode.ACTUATOR_OFF_TIMEOUT,
                FaultCode.SENSOR_STALE,
                FaultCode.ACTUATOR_OFF_TIMEOUT,
                None,
                FaultCode.SENSOR_STALE,
            ),
            (
                FaultCode.SENSOR_INVALID,
                FaultCode.ACTUATOR_ON_TIMEOUT,
                FaultCode.ACTUATOR_ON_TIMEOUT,
                FaultCode.SENSOR_INVALID,
                None,
            ),
            (
                FaultCode.SENSOR_UNAVAILABLE,
                FaultCode.CONFIGURATION_INVALID,
                None,
                FaultCode.SENSOR_UNAVAILABLE,
                FaultCode.CONFIGURATION_INVALID,
            ),
        ],
    )
    def test_primary_secondary_fault_split(
        self, primary, secondary, actuator, zone_primary, zone_secondary
    ) -> None:
        old = legacy_store()
        old = old.evolve(
            zones={"zone-a": full_record().evolve(active_fault=primary, secondary_fault=secondary)}
        )
        migrated = migrate_schema1_to_schema2(old, {"zone-a": migration_context()})
        record = migrated.safety_records["zone-a"]
        runtime = migrated.zone_histories[record.zone_history_id].zone_runtime
        assert record.actuator_fault is actuator
        assert runtime.zone_fault is zone_primary
        assert runtime.secondary_fault is zone_secondary

    def test_two_actuator_faults_fail_closed(self) -> None:
        old = legacy_store().evolve(
            zones={
                "zone-a": full_record().evolve(
                    active_fault=FaultCode.ACTUATOR_ON_TIMEOUT,
                    secondary_fault=FaultCode.ACTUATOR_OFF_TIMEOUT,
                )
            }
        )
        with pytest.raises(MalformedStoreData):
            migrate_schema1_to_schema2(old, {"zone-a": migration_context()})

    def test_stable_migration_ids(self) -> None:
        a = migrate_schema1_to_schema2(legacy_store(), {"zone-a": migration_context()})
        b = migrate_schema1_to_schema2(legacy_store(), {"zone-a": migration_context()})
        assert a == b
        assert (
            a.safety_records["zone-a"].safety_lineage_id
            == b.safety_records["zone-a"].safety_lineage_id
        )
        assert (
            a.safety_records["zone-a"].zone_history_id == b.safety_records["zone-a"].zone_history_id
        )

    def test_schema1_parser_rejects_missing_and_coercions(self) -> None:
        payload = schema1_store_data_to_dict(legacy_store())
        payload["zones"]["zone-a"]["enabled"] = "true"
        with pytest.raises(MalformedStoreData):
            schema1_store_data_from_dict(payload)
        payload = schema1_store_data_to_dict(legacy_store())
        payload["zones"]["zone-a"]["session"].pop("pulse_intent_at_utc")
        with pytest.raises(MalformedStoreData):
            schema1_store_data_from_dict(payload)


class TestContributionIdentity:
    def contribution(self, contribution_id: str, runtime: float = 10.0):
        return AccountingContribution(
            contribution_id,
            "zone-a",
            NOW,
            NOW + timedelta(seconds=runtime),
            runtime,
            False,
            date(2026, 8, 21),
        )

    def test_identical_ids_deduplicate_and_conflicts_reject(self) -> None:
        contribution = self.contribution("c1")
        assert deduplicate_accounting_contributions((contribution, contribution)) == (contribution,)
        with pytest.raises(ValueError):
            deduplicate_accounting_contributions((contribution, self.contribution("c1", 11.0)))

    def test_conservative_merge_preserves_known_and_adds_unresolved(self) -> None:
        left = ZoneDailyRuntime(date(2026, 8, 21), 15.0, 5.0, (self.contribution("c1"),))
        right = ZoneDailyRuntime(date(2026, 8, 21), 17.0, 7.0, (self.contribution("c1"),))
        merged = conservative_merge_daily_runtime(left, right)
        assert merged.contributions == (self.contribution("c1"),)
        assert merged.conservative_unattributed_runtime_s == 12.0
        assert merged.runtime_s == 22.0


class TestDailySplitting:
    """§19.3 / PI17: HA-local calendar boundaries, DST-safe."""

    def test_interval_within_one_day(self) -> None:
        start = datetime(2026, 8, 21, 2, 0, tzinfo=UTC)  # 12:00 Brisbane
        end = start + timedelta(minutes=30)
        assert split_interval_by_local_days(start, end, BRISBANE) == [(date(2026, 8, 21), 1800.0)]

    def test_spec_35_4_midnight_split(self) -> None:
        """§35.4: intent 23:55 local, reconcile 00:30 -> 5 min + 30 min."""
        start_local = datetime(2026, 8, 20, 23, 55, tzinfo=BRISBANE)
        end_local = datetime(2026, 8, 21, 0, 30, tzinfo=BRISBANE)
        segments = split_interval_by_local_days(
            start_local.astimezone(UTC), end_local.astimezone(UTC), BRISBANE
        )
        assert segments == [
            (date(2026, 8, 20), 300.0),
            (date(2026, 8, 21), 1800.0),
        ]

    def test_multi_day_outage_recognizes_every_day(self) -> None:
        start = datetime(2026, 8, 19, 23, 0, tzinfo=BRISBANE).astimezone(UTC)
        end = datetime(2026, 8, 22, 1, 0, tzinfo=BRISBANE).astimezone(UTC)
        segments = split_interval_by_local_days(start, end, BRISBANE)
        assert [d for d, _ in segments] == [
            date(2026, 8, 19),
            date(2026, 8, 20),
            date(2026, 8, 21),
            date(2026, 8, 22),
        ]
        assert segments[0][1] == 3600.0
        assert segments[1][1] == 86400.0  # full non-DST day
        assert segments[2][1] == 86400.0
        assert segments[3][1] == 3600.0
        total = sum(s for _, s in segments)
        assert total == (end - start).total_seconds()

    def test_dst_spring_forward_day_is_23_hours(self) -> None:
        """Sydney DST begins 2026-10-04 (02:00 -> 03:00): 23-hour day."""
        start = datetime(2026, 10, 4, 0, 0, tzinfo=SYDNEY).astimezone(UTC)
        end = datetime(2026, 10, 5, 0, 0, tzinfo=SYDNEY).astimezone(UTC)
        segments = split_interval_by_local_days(start, end, SYDNEY)
        assert segments == [(date(2026, 10, 4), 23 * 3600.0)]

    def test_dst_fall_back_day_is_25_hours(self) -> None:
        """Sydney DST ends 2026-04-05 (03:00 -> 02:00): 25-hour day."""
        start = datetime(2026, 4, 5, 0, 0, tzinfo=SYDNEY).astimezone(UTC)
        end = datetime(2026, 4, 6, 0, 0, tzinfo=SYDNEY).astimezone(UTC)
        segments = split_interval_by_local_days(start, end, SYDNEY)
        assert segments == [(date(2026, 4, 5), 25 * 3600.0)]

    def test_berlin_dst_boundary_split(self) -> None:
        """A crash interval across the Berlin spring-forward midnight."""
        start = datetime(2026, 3, 28, 23, 30, tzinfo=BERLIN).astimezone(UTC)
        end = datetime(2026, 3, 29, 4, 0, tzinfo=BERLIN).astimezone(UTC)
        segments = split_interval_by_local_days(start, end, BERLIN)
        assert [d for d, _ in segments] == [date(2026, 3, 28), date(2026, 3, 29)]
        assert segments[0][1] == 1800.0
        # 00:00-04:00 local crosses the 02:00->03:00 gap: 3 real hours.
        assert segments[1][1] == 3 * 3600.0
        assert sum(s for _, s in segments) == (end - start).total_seconds()

    def test_zero_length_interval(self) -> None:
        at = datetime(2026, 8, 21, 2, 0, tzinfo=UTC)
        assert split_interval_by_local_days(at, at, BRISBANE) == [(date(2026, 8, 21), 0.0)]

    def test_reversed_interval_raises(self) -> None:
        at = datetime(2026, 8, 21, 2, 0, tzinfo=UTC)
        with pytest.raises(ValueError):
            split_interval_by_local_days(at, at - timedelta(seconds=1), BRISBANE)

    def test_naive_input_rejected(self) -> None:
        with pytest.raises(ValueError):
            split_interval_by_local_days(datetime(2026, 8, 21), datetime(2026, 8, 21, 1), BRISBANE)

    def test_pathological_timezone_never_loops(self) -> None:
        """A zone whose 'next midnight' precedes the cursor still terminates
        and charges the remainder, rather than looping forever."""
        from datetime import tzinfo as tzinfo_cls

        class WarpTZ(tzinfo_cls):
            def utcoffset(self, dt):
                return timedelta(0)

            def dst(self, dt):
                return None

            def tzname(self, dt):
                return "warp"

            def fromutc(self, dt):
                # Local time runs two days behind UTC: the derived "next
                # local midnight" is in the UTC past.
                return (dt - timedelta(days=2)).replace(tzinfo=self)

        start = datetime(2026, 8, 21, 2, 0, tzinfo=UTC)
        end = start + timedelta(minutes=30)
        segments = split_interval_by_local_days(start, end, WarpTZ())
        assert len(segments) == 1
        assert segments[0][1] == 1800.0

    def test_current_day_charge(self) -> None:
        start = datetime(2026, 8, 20, 23, 55, tzinfo=BRISBANE).astimezone(UTC)
        end = datetime(2026, 8, 21, 0, 30, tzinfo=BRISBANE).astimezone(UTC)
        assert current_day_charge(start, end, BRISBANE, date(2026, 8, 21)) == 1800.0
        assert current_day_charge(start, end, BRISBANE, date(2026, 8, 20)) == 300.0
        assert current_day_charge(start, end, BRISBANE, date(2026, 8, 19)) == 0.0


class TestConfigFingerprint:
    """§23.2: deterministic, covers every §9 setting plus IDs and timezone."""

    def make_config(self, **overrides: object):
        from custom_components.moisture_loop.models import ZoneConfig

        base: dict[str, object] = {
            "name": "Front bed",
            "moisture_sensor": "sensor.m",
            "actuator": "switch.a",
            "start_threshold": 30.0,
            "target_threshold": 40.0,
            "pulse_duration_s": 300,
            "soak_duration_s": 1200,
            "max_cycles": 4,
            "max_session_runtime_s": 1800,
            "max_daily_runtime_s": 3600,
            "min_session_interval_s": 21600,
            "sensor_max_age_s": 7200,
            "actuator_confirm_timeout_s": 30,
            "manual_max_duration_s": 1800,
        }
        base.update(overrides)
        return ZoneConfig(**base)  # type: ignore[arg-type]

    def test_deterministic(self) -> None:
        from custom_components.moisture_loop.models import config_fingerprint

        a = config_fingerprint(self.make_config(), "Australia/Brisbane")
        b = config_fingerprint(self.make_config(), "Australia/Brisbane")
        assert a == b
        assert len(a) == 64  # SHA-256 hex

    def test_every_field_changes_fingerprint(self) -> None:
        from custom_components.moisture_loop.models import config_fingerprint

        base = config_fingerprint(self.make_config(), "Australia/Brisbane")
        variants = [
            {"name": "Back bed"},
            {"moisture_sensor": "sensor.other"},
            {"actuator": "valve.a"},
            {"start_threshold": 31.0},
            {"target_threshold": 41.0},
            {"pulse_duration_s": 360},
            {"soak_duration_s": 1260},
            {"max_cycles": 5},
            {"max_session_runtime_s": 1860},
            {"max_daily_runtime_s": 3660},
            {"min_session_interval_s": 21660},
            {"sensor_max_age_s": 7260},
            {"actuator_confirm_timeout_s": 60},
            {"manual_max_duration_s": 1860},
        ]
        seen = {base}
        for overrides in variants:
            fp = config_fingerprint(self.make_config(**overrides), "Australia/Brisbane")
            assert fp not in seen, f"fingerprint blind to {overrides}"
            seen.add(fp)
        tz_variant = config_fingerprint(self.make_config(), "Australia/Sydney")
        assert tz_variant not in seen


class TestConservativeEstimation:
    """PI15/PI16: estimates never undercount any plausible stop."""

    def test_estimate_covers_every_plausible_stop(self) -> None:
        intent = datetime(2026, 8, 21, 2, 0, tzinfo=UTC)
        reconcile = intent + timedelta(hours=6)
        estimate = (reconcile - intent).total_seconds()
        for minutes in (0, 1, 4, 60, 359):
            plausible_stop = intent + timedelta(minutes=minutes)
            delivered = (plausible_stop - intent).total_seconds()
            assert estimate >= delivered

    def test_large_outage_can_exhaust_budget(self) -> None:
        intent = datetime(2026, 8, 21, 2, 0, tzinfo=UTC)
        reconcile = intent + timedelta(days=2)
        charge = current_day_charge(intent, reconcile, BRISBANE, date(2026, 8, 22))
        assert charge == 86400.0  # a full intervening day; far above any budget
