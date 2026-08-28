"""Spec.4 Stage-1 HA Store tests: schema 2 and verified schema-1 migration."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

pytest.importorskip("homeassistant")

from custom_components.moisture_loop.const import (
    STORE_SCHEMA_VERSION,
)
from custom_components.moisture_loop.models import (
    AccountingContribution,
    ActuatorIdentity,
    AppliedConfigurationShadow,
    AppliedEntityIdentity,
    BlockerReason,
    ControllerState,
    DailyRuntime,
    FaultCode,
    IdentityStatus,
    MigrationRecordContext,
    NormalizedZoneSettings,
    PossibleFlowOwner,
    RunIds,
    RuntimeLifecycle,
    SafetyRecord,
    Schema1StoreData,
    SensorIdentity,
    SessionContext,
    SessionMode,
    StoreData,
    ZoneConfig,
    ZoneDailyRuntime,
    ZoneHistory,
    ZoneRecord,
    ZoneRuntime,
    schema1_store_data_to_dict,
    store_data_to_dict,
)
from custom_components.moisture_loop.storage import (
    SafetyStore,
    SetupClassification,
    StoreNotLoadedError,
    StoreWriteVerificationError,
)

ENTRY_ID = "entry-1"
GENERATION = "11111111-2222-3333-4444-555555555555"
KEY = f"moisture_loop.{ENTRY_ID}"
NOW = datetime(2026, 8, 22, 12, tzinfo=UTC)


def make_store(hass) -> SafetyStore:
    return SafetyStore(hass, ENTRY_ID, GENERATION)


def config(zone_id: str) -> ZoneConfig:
    return ZoneConfig(
        name=f"Bed {zone_id}",
        moisture_sensor=f"sensor.{zone_id}",
        actuator=f"switch.{zone_id}",
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


def context(zone_id: str) -> MigrationRecordContext:
    cfg = config(zone_id)
    sensor = AppliedEntityIdentity(f"sensor-reg-{zone_id}", cfg.moisture_sensor, "sensor")
    actuator = AppliedEntityIdentity(f"actuator-reg-{zone_id}", cfg.actuator, "switch")
    return MigrationRecordContext(
        active_subentry_id=zone_id,
        applied_config=AppliedConfigurationShadow(
            subentry_id=zone_id,
            config_fingerprint=f"config-fp-{zone_id}",
            entry_snapshot_fingerprint="snapshot-fp",
            applied_generation=4,
            normalized_settings=NormalizedZoneSettings.from_config(cfg),
            sensor_identity=sensor,
            actuator_identity=actuator,
        ),
        actuator_identity=ActuatorIdentity(
            registry_entry_id=f"actuator-reg-{zone_id}",
            last_known_entity_id=cfg.actuator,
            domain="switch",
            identity_status=IdentityStatus.REGISTRY_CONFIRMED,
            off_service="switch.turn_off",
            confirm_timeout_s=30,
        ),
        sensor_identity=SensorIdentity(f"sensor-reg-{zone_id}", cfg.moisture_sensor),
    )


def session() -> SessionContext:
    return SessionContext(
        session_id="session-1",
        owner_run_id="run-a",
        config_fingerprint="config-fp-zone-a",
        mode=SessionMode.AUTO,
        started_at_utc=NOW - timedelta(minutes=40),
        cycle=2,
        session_runtime_s=480.0,
        pulse_intent_at_utc=NOW - timedelta(minutes=30),
        pulse_commanded_at_utc=NOW - timedelta(minutes=29),
        pulse_confirmed_at_utc=NOW - timedelta(minutes=29),
        pulse_ends_at_utc=NOW - timedelta(minutes=24),
        off_confirmed_at_utc=NOW - timedelta(minutes=24),
        soak_ends_at_utc=NOW - timedelta(minutes=4),
        recheck_not_before_utc=NOW - timedelta(minutes=4),
        recheck_grace_deadline_at_utc=NOW + timedelta(minutes=116),
        moisture_at_start=27.0,
    )


def legacy_snapshot(
    *,
    generation: str = GENERATION,
    revision: int = 7,
    zones: dict[str, ZoneRecord] | None = None,
) -> Schema1StoreData:
    return Schema1StoreData(
        generation_id=generation,
        store_revision=revision,
        run=RunIds("run-a", "run-a"),
        zones=zones
        if zones is not None
        else {
            "zone-a": ZoneRecord(
                ControllerState.SOAKING,
                True,
                secondary_fault=FaultCode.SENSOR_STALE,
                last_session_end_utc=NOW - timedelta(hours=7),
                last_auto_session_start_utc=NOW - timedelta(minutes=40),
                daily=DailyRuntime(date(2026, 8, 22), 312.5),
                session=session(),
            )
        },
    )


def schema2_snapshot(
    *, generation: str = GENERATION, revision: int = 9, zone_ids: tuple[str, ...] = ("zone-a",)
) -> StoreData:
    histories: dict[str, ZoneHistory] = {}
    records: dict[str, SafetyRecord] = {}
    for zone_id in zone_ids:
        current = context(zone_id)
        history_id = f"history-{zone_id}"
        histories[history_id] = ZoneHistory(
            zone_history_id=history_id,
            active_subentry_id=zone_id,
            previous_subentry_ids=(),
            last_session_end_utc=None,
            last_auto_session_start_utc=None,
            zone_runtime=ZoneRuntime(
                enabled=True,
                state=ControllerState.IDLE,
                zone_fault=None,
                secondary_fault=None,
                sensor_identity=current.sensor_identity,
                last_session_summary=None,
                session=None,
            ),
            daily=None,
        )
        records[zone_id] = SafetyRecord(
            safety_record_id=zone_id,
            zone_id=zone_id,
            active_subentry_id=zone_id,
            previous_subentry_ids=(),
            safety_lineage_id=f"lineage-{zone_id}",
            zone_history_id=history_id,
            historical_zone_history_ids=(),
            runtime_lifecycle=RuntimeLifecycle.ACTIVE,
            applied_config=current.applied_config,
            actuator_identity=current.actuator_identity,
            blocker_reasons=(),
            possible_flow_owner=None,
            identity_incident=None,
            actuator_fault=None,
            acknowledgement_required=False,
        )
    return StoreData(
        generation_id=generation,
        store_revision=revision,
        run=RunIds("run-a", "run-a"),
        zone_histories=histories,
        safety_records=records,
    )


def seed_schema1(hass_storage: dict, data: Schema1StoreData) -> None:
    hass_storage[KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": KEY,
        "data": schema1_store_data_to_dict(data),
    }


def seed_current_schema(hass_storage: dict, data: StoreData) -> None:
    hass_storage[KEY] = {
        "version": STORE_SCHEMA_VERSION,
        "minor_version": 1,
        "key": KEY,
        "data": store_data_to_dict(data),
    }


async def update_zone_runtime(store: SafetyStore, zone_id: str, **changes: object) -> None:
    """Mutate one canonical ZoneHistory without a schema-1 projection."""

    def mutate(data):
        records = [record for record in data.safety_records.values() if record.zone_id == zone_id]
        assert len(records) == 1
        record = records[0]
        history = data.zone_histories[record.zone_history_id]
        histories = dict(data.zone_histories)
        histories[history.zone_history_id] = history.evolve(
            zone_runtime=replace(history.zone_runtime, **changes)
        )
        return dict(data.safety_records), histories

    await store.async_reconcile(mutate)


def async_raise(error: Exception):
    async def raising(*_args, **_kwargs):
        raise error

    return raising


def async_return(value):
    async def returning(*_args, **_kwargs):
        return value

    return returning


class TestInitializationAndLoad:
    async def test_pi1_first_install_is_verified_empty_schema2(self, hass, hass_storage) -> None:
        store = make_store(hass)
        classification, data = await store.async_classify_setup(False)
        assert (classification, data) == (SetupClassification.FIRST_INSTALL, None)
        created = await store.async_first_initialize()
        assert created.version == STORE_SCHEMA_VERSION
        assert created.store_revision == 1
        assert created.generation_id == GENERATION
        assert created.run == RunIds(None, None)
        assert created.safety_records == {}
        assert created.zone_histories == {}
        assert hass_storage[KEY]["version"] == STORE_SCHEMA_VERSION

    async def test_valid_schema2_load_is_idempotent_not_remigrated(
        self, hass, hass_storage
    ) -> None:
        expected = schema2_snapshot(revision=12)
        seed_current_schema(hass_storage, expected)
        for initialized in (False, True):
            store = make_store(hass)
            classification, loaded = await store.async_classify_setup(initialized)
            expected_class = (
                SetupClassification.INTERRUPTED_INITIALIZATION
                if not initialized
                else SetupClassification.INITIALIZED_OK
            )
            assert classification is expected_class
            assert loaded == expected
            assert loaded.store_revision == 12

    async def test_initialized_missing_is_integrity_loss(self, hass) -> None:
        store = make_store(hass)
        classification, data = await store.async_classify_setup(True)
        assert classification is SetupClassification.INTEGRITY_LOSS
        assert data is None
        assert not store.loaded

    async def test_pi4_corrupt_or_unreadable_store_fails_closed(self, hass) -> None:
        moved_aside = make_store(hass)
        moved_aside._store.async_load = async_return(None)  # type: ignore[method-assign]
        classification, data = await moved_aside.async_classify_setup(True)
        assert (classification, data) == (SetupClassification.INTEGRITY_LOSS, None)

        unreadable = make_store(hass)
        unreadable._store.async_load = async_raise(OSError("unreadable"))  # type: ignore[method-assign]
        classification, data = await unreadable.async_classify_setup(True)
        assert (classification, data) == (SetupClassification.INTEGRITY_LOSS, None)

    async def test_generation_mismatch_is_never_first_install(self, hass, hass_storage) -> None:
        seed_current_schema(hass_storage, schema2_snapshot(generation="different"))
        for initialized in (False, True):
            classification, _ = await make_store(hass).async_classify_setup(initialized)
            assert classification is SetupClassification.INTEGRITY_LOSS

    async def test_future_and_malformed_schema2_fail_closed(self, hass, hass_storage) -> None:
        payload = store_data_to_dict(schema2_snapshot())
        payload["version"] = STORE_SCHEMA_VERSION + 1
        hass_storage[KEY] = {
            "version": STORE_SCHEMA_VERSION,
            "minor_version": 1,
            "key": KEY,
            "data": payload,
        }
        classification, _ = await make_store(hass).async_classify_setup(True)
        assert classification is SetupClassification.INTEGRITY_LOSS

        payload = store_data_to_dict(schema2_snapshot())
        payload["safety_records"]["zone-a"].pop("zone_history_id")
        hass_storage[KEY] = {
            "version": STORE_SCHEMA_VERSION,
            "minor_version": 1,
            "key": KEY,
            "data": payload,
        }
        classification, _ = await make_store(hass).async_classify_setup(True)
        assert classification is SetupClassification.INTEGRITY_LOSS


class TestVerifiedMigration:
    async def test_pi21_configured_schema1_migrates_and_verifies(self, hass, hass_storage) -> None:
        legacy = legacy_snapshot()
        seed_schema1(hass_storage, legacy)
        store = make_store(hass)
        classification, migrated = await store.async_classify_setup(
            True, {"zone-a": context("zone-a")}
        )
        assert classification is SetupClassification.INITIALIZED_OK
        assert migrated.version == STORE_SCHEMA_VERSION
        assert migrated.store_revision == legacy.store_revision + 1
        record = migrated.safety_records["zone-a"]
        history = migrated.zone_histories[record.zone_history_id]
        assert record.runtime_lifecycle is RuntimeLifecycle.ACTIVE
        assert history.zone_runtime.session.owner_safety_record_id == "zone-a"
        assert history.zone_runtime.session.context == legacy.zones["zone-a"].session
        assert history.daily.runtime_s == legacy.zones["zone-a"].daily.runtime_s
        assert hass_storage[KEY]["version"] == STORE_SCHEMA_VERSION

        fresh = make_store(hass)
        _, reloaded = await fresh.async_classify_setup(True)
        assert reloaded == migrated
        assert reloaded.store_revision == legacy.store_revision + 1

    async def test_pi22_store_only_schema1_migrates_unresolved(self, hass, hass_storage) -> None:
        legacy = legacy_snapshot()
        seed_schema1(hass_storage, legacy)
        _, migrated = await make_store(hass).async_classify_setup(True)
        record = migrated.safety_records["zone-a"]
        assert record.runtime_lifecycle is RuntimeLifecycle.DELETE_PENDING
        assert record.actuator_identity.identity_status is IdentityStatus.MISSING
        assert record.actuator_identity.registry_entry_id is None
        assert record.identity_incident is not None
        assert record.blocker_reasons

    async def test_tb7_malformed_schema1_fails_closed(self, hass, hass_storage) -> None:
        payload = schema1_store_data_to_dict(legacy_snapshot())
        payload["zones"]["zone-a"]["enabled"] = "true"
        hass_storage[KEY] = {"version": 1, "minor_version": 1, "key": KEY, "data": payload}
        store = make_store(hass)
        classification, migrated = await store.async_classify_setup(True)
        assert classification is SetupClassification.INTEGRITY_LOSS
        assert migrated is None
        assert not store.loaded
        assert hass_storage[KEY]["version"] == 1

    async def test_ambiguous_schema1_fault_ownership_fails_closed(self, hass, hass_storage) -> None:
        legacy = legacy_snapshot(
            zones={
                "zone-a": ZoneRecord(
                    ControllerState.FAULT,
                    True,
                    active_fault=FaultCode.ACTUATOR_ON_TIMEOUT,
                    secondary_fault=FaultCode.ACTUATOR_OFF_TIMEOUT,
                )
            }
        )
        seed_schema1(hass_storage, legacy)
        store = make_store(hass)
        classification, migrated = await store.async_classify_setup(
            True, {"zone-a": context("zone-a")}
        )
        assert classification is SetupClassification.INTEGRITY_LOSS
        assert migrated is None
        assert not store.loaded
        assert hass_storage[KEY]["version"] == 1

    async def test_pi23_migration_save_failure_fails_closed(self, hass, hass_storage) -> None:
        seed_schema1(hass_storage, legacy_snapshot())
        store = make_store(hass)
        store._store.async_save = async_raise(OSError("disk full"))  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError, match="safety write failed"):
            await store.async_classify_setup(True, {"zone-a": context("zone-a")})
        assert not store.loaded

    async def test_pi23_migration_fresh_read_failure(self, hass, hass_storage, monkeypatch) -> None:
        seed_schema1(hass_storage, legacy_snapshot())
        store = make_store(hass)

        class BrokenReadback:
            async def async_load(self):
                raise OSError("unreadable")

        import custom_components.moisture_loop.storage as storage_module

        monkeypatch.setattr(storage_module, "_new_store", lambda *_args: BrokenReadback())
        with pytest.raises(StoreWriteVerificationError, match="read-back load failed"):
            await store.async_classify_setup(True, {"zone-a": context("zone-a")})
        assert not store.loaded

    async def test_pi23_migration_payload_tamper(self, hass, hass_storage) -> None:
        seed_schema1(hass_storage, legacy_snapshot())
        store = make_store(hass)

        async def tamper(payload) -> None:
            payload = {**payload, "store_revision": 999}
            hass_storage[KEY] = {
                "version": STORE_SCHEMA_VERSION,
                "minor_version": 1,
                "key": KEY,
                "data": payload,
            }

        store._store.async_save = tamper  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError, match="revision mismatch"):
            await store.async_classify_setup(True, {"zone-a": context("zone-a")})
        assert not store.loaded


class TestVerifiedWritesAndRuns:
    async def test_pi11_every_store_is_atomic_and_readback_verified(self, hass) -> None:
        store = make_store(hass)
        assert store._store._atomic_writes is True
        await store.async_first_initialize()
        from custom_components.moisture_loop.storage import _new_store

        assert _new_store(hass, KEY)._atomic_writes is True

    async def test_initial_write_failure_not_adopted(self, hass) -> None:
        store = make_store(hass)
        store._store.async_save = async_raise(OSError("disk full"))  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError):
            await store.async_first_initialize()
        assert not store.loaded

    async def test_pi7_swallowed_initial_write_detected(self, hass) -> None:
        store = make_store(hass)
        store._store.async_save = async_return(None)  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError, match="no data"):
            await store.async_first_initialize()
        assert not store.loaded

    async def test_accessors_before_load(self, hass) -> None:
        store = make_store(hass)
        assert store.generation_id == GENERATION
        assert not store.loaded
        with pytest.raises(StoreNotLoadedError):
            _ = store.data

    async def test_pi11_failed_write_keeps_previous_revision(self, hass, hass_storage) -> None:
        previous = schema2_snapshot(revision=9)
        seed_current_schema(hass_storage, previous)
        store = make_store(hass)
        await store.async_classify_setup(True)
        store._store.async_save = async_raise(OSError("interrupted"))  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError):
            await update_zone_runtime(
                store, "zone-a", state=ControllerState.DISABLED, enabled=False
            )
        assert store.data == previous
        fresh = make_store(hass)
        _, reloaded = await fresh.async_classify_setup(True)
        assert reloaded == previous

    async def test_readback_malformed_and_generation_mismatch(self, hass, hass_storage) -> None:
        store = make_store(hass)

        async def garble(_payload) -> None:
            hass_storage[KEY] = {
                "version": STORE_SCHEMA_VERSION,
                "minor_version": 1,
                "key": KEY,
                "data": {"version": STORE_SCHEMA_VERSION, "nonsense": True},
            }

        store._store.async_save = garble  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError, match="malformed"):
            await store.async_first_initialize()

        store = make_store(hass)

        async def wrong_generation(payload) -> None:
            tampered = {**payload, "generation_id": "someone-else"}
            hass_storage[KEY] = {
                "version": STORE_SCHEMA_VERSION,
                "minor_version": 1,
                "key": KEY,
                "data": tampered,
            }

        store._store.async_save = wrong_generation  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError, match="generation mismatch"):
            await store.async_first_initialize()

    async def test_readback_payload_mismatch_prevents_adoption(self, hass, hass_storage) -> None:
        previous = schema2_snapshot(revision=9)
        seed_current_schema(hass_storage, previous)
        store = make_store(hass)
        await store.async_classify_setup(True)

        async def tamper(payload) -> None:
            altered = store_data_to_dict(store_data_from_dict(payload))
            history_id = altered["safety_records"]["zone-a"]["zone_history_id"]
            altered["zone_histories"][history_id]["zone_runtime"]["enabled"] = False
            hass_storage[KEY] = {
                "version": STORE_SCHEMA_VERSION,
                "minor_version": 1,
                "key": KEY,
                "data": altered,
            }

        from custom_components.moisture_loop.models import store_data_from_dict

        store._store.async_save = tamper  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError, match="payload mismatch"):
            await update_zone_runtime(store, "zone-a", state=ControllerState.IDLE, enabled=True)
        assert store.data == previous

    async def test_revisions_increase_monotonically(self, hass, hass_storage) -> None:
        seed_current_schema(hass_storage, schema2_snapshot(revision=9))
        store = make_store(hass)
        await store.async_classify_setup(True)
        for expected in (10, 11, 12):
            await update_zone_runtime(store, "zone-a", state=ControllerState.IDLE, enabled=True)
            assert store.data.store_revision == expected

    async def test_run_id_protocol_and_clean_marking(self, hass, hass_storage) -> None:
        seed_current_schema(hass_storage, schema2_snapshot())
        store = make_store(hass)
        await store.async_classify_setup(True)
        previous = await store.async_begin_new_run("run-b")
        assert previous.previous_run_was_clean
        assert store.data.run == RunIds("run-b", "run-a")
        await store.async_mark_clean_shutdown()
        assert store.data.run == RunIds("run-b", "run-b")

    async def test_pi18_crashed_intermediate_run_is_unclean(self, hass, hass_storage) -> None:
        seed_current_schema(hass_storage, schema2_snapshot())
        run_b = make_store(hass)
        await run_b.async_classify_setup(True)
        await run_b.async_begin_new_run("run-b")
        run_c = make_store(hass)
        await run_c.async_classify_setup(True)
        previous = await run_c.async_begin_new_run("run-c")
        assert previous == RunIds("run-b", "run-a")
        assert not previous.previous_run_was_clean

    async def test_pi19_unverified_run_id_fails_closed(self, hass, hass_storage) -> None:
        seed_current_schema(hass_storage, schema2_snapshot())
        store = make_store(hass)
        await store.async_classify_setup(True)
        store._store.async_save = async_return(None)  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError):
            await store.async_begin_new_run("run-b")
        assert store.data.run == RunIds("run-a", "run-a")

    async def test_pi20_canonical_writes_serialize_without_loss(self, hass, hass_storage) -> None:
        seed_current_schema(hass_storage, schema2_snapshot(zone_ids=("zone-a", "zone-b", "zone-c")))
        store = make_store(hass)
        await store.async_classify_setup(True)

        async def write(zone_id: str, enabled: bool) -> None:
            await update_zone_runtime(store, zone_id, state=ControllerState.IDLE, enabled=enabled)

        await asyncio.gather(write("zone-a", True), write("zone-b", False), write("zone-c", True))
        assert {record.zone_id for record in store.data.safety_records.values()} == {
            "zone-a",
            "zone-b",
            "zone-c",
        }
        record_b = next(
            record for record in store.data.safety_records.values() if record.zone_id == "zone-b"
        )
        assert not store.data.zone_histories[record_b.zone_history_id].zone_runtime.enabled
        assert store.data.store_revision == 12

    async def test_canonical_runtime_write_cannot_create_identityless_record(self, hass) -> None:
        store = make_store(hass)
        await store.async_first_initialize()
        with pytest.raises(StoreWriteVerificationError, match="unknown canonical"):
            await store.async_update_controller_runtime(
                "zone-a",
                "history-a",
                state=ControllerState.IDLE,
                enabled=True,
                active_fault=None,
                secondary_fault=None,
                last_session_end_utc=None,
                last_auto_session_start_utc=None,
                daily=None,
                last_session_summary=None,
                session=None,
                possible_flow_owner=None,
            )

    async def test_rebase_changes_only_session_owner(self, hass, hass_storage) -> None:
        legacy = legacy_snapshot()
        seed_schema1(hass_storage, legacy)
        store = make_store(hass)
        await store.async_classify_setup(True, {"zone-a": context("zone-a")})
        record = store.data.safety_records["zone-a"]
        before = store.data.zone_histories[record.zone_history_id].zone_runtime.session.context
        await store.async_rebase_soaking_owner_for_record("zone-a", "run-b")
        after = store.data.zone_histories[record.zone_history_id].zone_runtime.session.context
        assert after == before.evolve(owner_run_id="run-b")

    async def test_rebase_without_session_rejects(self, hass, hass_storage) -> None:
        seed_current_schema(hass_storage, schema2_snapshot())
        store = make_store(hass)
        await store.async_classify_setup(True)
        with pytest.raises(StoreNotLoadedError):
            await store.async_rebase_soaking_owner_for_record("zone-a", "run-b")

    async def test_rebase_write_failure_keeps_session(self, hass, hass_storage) -> None:
        seed_schema1(hass_storage, legacy_snapshot())
        store = make_store(hass)
        await store.async_classify_setup(True, {"zone-a": context("zone-a")})
        previous = store.data
        store._store.async_save = async_raise(OSError("boom"))  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError):
            await store.async_rebase_soaking_owner_for_record("zone-a", "run-b")
        assert store.data == previous


class TestIntegrityAndRetention:
    async def test_integrity_reconstruction_is_schema2_and_exhausts_budget(self, hass) -> None:
        store = make_store(hass)
        data = await store.async_reconstruct_after_integrity_loss(
            {"zone-a": 3600}, date(2026, 8, 22)
        )
        record = data.safety_records["zone-a"]
        history = data.zone_histories[record.zone_history_id]
        assert data.version == STORE_SCHEMA_VERSION
        assert record.actuator_fault is FaultCode.RESTORED_FROM_UNSAFE_STATE
        assert record.acknowledgement_required
        assert record.runtime_lifecycle is RuntimeLifecycle.DELETE_PENDING
        assert history.daily.runtime_s == 3600.0
        assert history.zone_runtime.state is ControllerState.FAULT

    async def test_pi27_tb11_retired_tombstone_never_auto_purged(self, hass, hass_storage) -> None:
        data = schema2_snapshot()
        record = data.safety_records["zone-a"]
        history = data.zone_histories[record.zone_history_id]
        data = data.evolve(
            safety_records={
                "zone-a": record.evolve(
                    active_subentry_id=None,
                    previous_subentry_ids=("zone-a",),
                    runtime_lifecycle=RuntimeLifecycle.RETIRED,
                )
            },
            zone_histories={
                history.zone_history_id: history.evolve(
                    active_subentry_id=None, previous_subentry_ids=("zone-a",)
                )
            },
        )
        seed_current_schema(hass_storage, data)
        store = make_store(hass)
        await store.async_classify_setup(True)
        await store.async_begin_new_run("run-b")
        fresh = make_store(hass)
        _, reloaded = await fresh.async_classify_setup(True)
        assert "zone-a" in reloaded.safety_records
        assert reloaded.safety_records["zone-a"].runtime_lifecycle is RuntimeLifecycle.RETIRED


class TestStage2ExactRecordPersistence:
    async def test_tb4_exact_record_blockers_persist_independently(
        self, hass, hass_storage
    ) -> None:
        seed_current_schema(hass_storage, schema2_snapshot(zone_ids=("zone-a", "zone-b")))
        store = make_store(hass)
        await store.async_classify_setup(True)
        start_revision = store.data.store_revision

        await store.async_set_record_blocker("zone-a", BlockerReason.EXTERNAL_FLOW, active=True)
        await store.async_set_record_blocker(
            "zone-b", BlockerReason.INTEGRATION_OFF_UNCONFIRMED, active=True
        )
        await store.async_set_record_blocker("zone-a", BlockerReason.EXTERNAL_FLOW, active=False)

        assert store.data.safety_records["zone-a"].blocker_reasons == ()
        assert store.data.safety_records["zone-b"].blocker_reasons == (
            BlockerReason.INTEGRATION_OFF_UNCONFIRMED,
        )
        assert store.data.store_revision == start_revision + 3
        unchanged_revision = store.data.store_revision
        await store.async_set_record_blocker("zone-a", BlockerReason.EXTERNAL_FLOW, active=False)
        assert store.data.store_revision == unchanged_revision

        reloaded_store = make_store(hass)
        _, reloaded = await reloaded_store.async_classify_setup(True)
        assert reloaded.safety_records["zone-b"].blocker_reasons == (
            BlockerReason.INTEGRATION_OFF_UNCONFIRMED,
        )

    async def test_ar2_ar10_verified_history_handoff_keeps_hazards_on_b(
        self, hass, hass_storage
    ) -> None:
        data = schema2_snapshot(zone_ids=("zone-a", "zone-b"))
        record_a = data.safety_records["zone-a"].evolve(
            blocker_reasons=(BlockerReason.ACTUATOR_NOT_PROVEN_OFF,),
            possible_flow_owner=PossibleFlowOwner.INTEGRATION,
            actuator_fault=FaultCode.ACTUATOR_UNAVAILABLE,
        )
        record_b = data.safety_records["zone-b"]
        history_a = data.zone_histories[record_a.zone_history_id]
        history_b = data.zone_histories[record_b.zone_history_id]
        contribution_a = AccountingContribution(
            "contribution-a",
            "zone-a",
            NOW - timedelta(seconds=100),
            NOW,
            100.0,
            False,
            date(2026, 8, 22),
        )
        contribution_b = AccountingContribution(
            "contribution-b",
            "zone-b",
            NOW - timedelta(seconds=200),
            NOW,
            200.0,
            True,
            date(2026, 8, 22),
        )
        retired_b = record_b.evolve(
            active_subentry_id=None,
            previous_subentry_ids=("zone-b",),
            runtime_lifecycle=RuntimeLifecycle.RETIRED,
            blocker_reasons=(BlockerReason.EXTERNAL_FLOW,),
            possible_flow_owner=PossibleFlowOwner.EXTERNAL,
            actuator_fault=FaultCode.ACTUATOR_OFF_TIMEOUT,
            acknowledgement_required=True,
        )
        data = data.evolve(
            safety_records={"zone-a": record_a, "zone-b": retired_b},
            zone_histories={
                history_a.zone_history_id: history_a.evolve(
                    last_session_end_utc=NOW - timedelta(hours=3),
                    daily=ZoneDailyRuntime(
                        date(2026, 8, 22), 100.0, contributions=(contribution_a,)
                    ),
                ),
                history_b.zone_history_id: history_b.evolve(
                    active_subentry_id=None,
                    previous_subentry_ids=("zone-b",),
                    last_session_end_utc=NOW - timedelta(hours=1),
                    daily=ZoneDailyRuntime(
                        date(2026, 8, 22), 200.0, contributions=(contribution_b,)
                    ),
                ),
            },
        )
        seed_current_schema(hass_storage, data)
        store = make_store(hass)
        await store.async_classify_setup(True)

        await store.async_merge_zone_history_for_record(history_a.zone_history_id, "zone-b")

        merged_b = store.data.safety_records["zone-b"]
        assert merged_b == retired_b.evolve(
            zone_history_id=history_a.zone_history_id,
            historical_zone_history_ids=(history_b.zone_history_id,),
        )
        assert store.data.safety_records["zone-a"] == record_a
        assert history_b.zone_history_id not in store.data.zone_histories
        merged_history = store.data.zone_histories[history_a.zone_history_id]
        assert merged_history.zone_runtime == history_a.zone_runtime
        assert merged_history.daily is not None
        assert merged_history.daily.runtime_s == 300.0
        assert merged_history.last_session_end_utc == NOW - timedelta(hours=1)

        # B's exact OFF evidence can remove only B's key; A remains A-owned.
        await store.async_set_record_blocker("zone-b", BlockerReason.EXTERNAL_FLOW, active=False)
        assert store.data.safety_records["zone-b"].blocker_reasons == ()
        assert store.data.safety_records["zone-a"].blocker_reasons == (
            BlockerReason.ACTUATOR_NOT_PROVEN_OFF,
        )

        fresh = make_store(hass)
        _, reloaded = await fresh.async_classify_setup(True)
        assert reloaded == store.data

    async def test_history_handoff_rejects_active_record(self, hass, hass_storage) -> None:
        data = schema2_snapshot(zone_ids=("zone-a", "zone-b"))
        seed_current_schema(hass_storage, data)
        store = make_store(hass)
        await store.async_classify_setup(True)
        history_a = data.safety_records["zone-a"].zone_history_id
        with pytest.raises(StoreWriteVerificationError, match="quiesced"):
            await store.async_merge_zone_history_for_record(history_a, "zone-b")
