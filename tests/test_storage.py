"""Slice 4 HA-harness tests: SafetyStore (SPECIFICATION.md §23, PI1-PI11,
PI18-PI20 at the storage layer).

Requires the pytest-homeassistant-custom-component harness; skips cleanly in
the pure environment.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta

import pytest

pytest.importorskip("homeassistant")

from custom_components.moisture_loop.models import (
    ActuatorAssessment,
    AutoEvaluate,
    ControllerState,
    DailyRuntime,
    FaultCode,
    ManualStartRequested,
    MoistureClassification,
    MoistureObservation,
    ResourceAssessment,
    RunIds,
    SessionContext,
    SessionIdentity,
    SessionMode,
    StoreData,
    TransitionInput,
    ZoneConfig,
    ZoneRecord,
    store_data_to_dict,
)
from custom_components.moisture_loop.state_machine import decide
from custom_components.moisture_loop.storage import (
    SafetyStore,
    SetupClassification,
    StoreNotLoadedError,
    StoreWriteVerificationError,
)

ENTRY_ID = "entry-1"
GENERATION = "11111111-2222-3333-4444-555555555555"
KEY = f"moisture_loop.{ENTRY_ID}"
NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)


def make_store(hass) -> SafetyStore:
    return SafetyStore(hass, ENTRY_ID, GENERATION)


def seed(hass_storage: dict, data: StoreData) -> None:
    hass_storage[KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": KEY,
        "data": store_data_to_dict(data),
    }


def store_snapshot(
    generation: str = GENERATION,
    revision: int = 5,
    active: str | None = "run-a",
    clean: str | None = "run-a",
    zones: dict[str, ZoneRecord] | None = None,
) -> StoreData:
    return StoreData(
        generation_id=generation,
        store_revision=revision,
        run=RunIds(active_run_id=active, last_clean_shutdown_run_id=clean),
        zones=zones if zones is not None else {"zone-a": ZoneRecord(ControllerState.IDLE, True)},
    )


def soaking_record(owner: str = "run-a") -> ZoneRecord:
    return ZoneRecord(
        state=ControllerState.SOAKING,
        enabled=True,
        daily=DailyRuntime(date(2026, 8, 21), 300.0),
        session=SessionContext(
            session_id="sess-1",
            owner_run_id=owner,
            config_fingerprint="fp-1",
            mode=SessionMode.AUTO,
            started_at_utc=NOW - timedelta(minutes=40),
            cycle=1,
            session_runtime_s=300.0,
            pulse_intent_at_utc=NOW - timedelta(minutes=30),
            pulse_commanded_at_utc=NOW - timedelta(minutes=29),
            pulse_confirmed_at_utc=NOW - timedelta(minutes=29),
            off_confirmed_at_utc=NOW - timedelta(minutes=25),
            soak_ends_at_utc=NOW - timedelta(minutes=5),
            recheck_not_before_utc=NOW - timedelta(minutes=5),
            recheck_grace_deadline_at_utc=NOW + timedelta(minutes=115),
        ),
    )


class TestSetupMatrix:
    """§23.5 decision matrix (PI1-PI6, PI8)."""

    async def test_pi1_first_install(self, hass, hass_storage) -> None:
        store = make_store(hass)
        classification, data = await store.async_classify_setup(False)
        assert classification is SetupClassification.FIRST_INSTALL
        assert data is None
        created = await store.async_first_initialize()
        assert created.store_revision == 1
        assert created.generation_id == GENERATION
        assert created.run == RunIds(None, None)
        assert created.zones == {}
        assert KEY in hass_storage
        # A later run with the flag set adopts the same store.
        fresh = make_store(hass)
        classification2, data2 = await fresh.async_classify_setup(True)
        assert classification2 is SetupClassification.INITIALIZED_OK
        assert data2 == created

    async def test_pi2_pi6_interrupted_initialization(self, hass, hass_storage) -> None:
        existing = store_snapshot(revision=7)
        seed(hass_storage, existing)
        store = make_store(hass)
        classification, data = await store.async_classify_setup(False)
        assert classification is SetupClassification.INTERRUPTED_INITIALIZATION
        # Session/budget data is preserved, not reset (PI6).
        assert data == existing
        assert store.data.store_revision == 7

    async def test_pi3_initialized_but_absent(self, hass, hass_storage) -> None:
        store = make_store(hass)
        classification, data = await store.async_classify_setup(True)
        assert classification is SetupClassification.INTEGRITY_LOSS
        assert data is None
        assert not store.loaded

    async def test_pi4_corrupt_returns_none_and_unloadable_raises(self, hass) -> None:
        store = make_store(hass)
        # Core moves corrupt JSON aside and returns None.
        store._store.async_load = _async_return(None)  # type: ignore[method-assign]
        classification, _ = await store.async_classify_setup(True)
        assert classification is SetupClassification.INTEGRITY_LOSS

        store2 = make_store(hass)
        store2._store.async_load = _async_raise(OSError("unreadable"))  # type: ignore[method-assign]
        classification2, _ = await store2.async_classify_setup(True)
        assert classification2 is SetupClassification.INTEGRITY_LOSS

    async def test_pi5_generation_mismatch_is_never_first_install(self, hass, hass_storage) -> None:
        seed(hass_storage, store_snapshot(generation="other-generation"))
        for initialized in (True, False):
            store = make_store(hass)
            classification, _ = await store.async_classify_setup(initialized)
            assert classification is SetupClassification.INTEGRITY_LOSS

    async def test_pi8_future_store_version(self, hass, hass_storage) -> None:
        payload = store_data_to_dict(store_snapshot())
        payload["version"] = 2
        hass_storage[KEY] = {"version": 1, "minor_version": 1, "key": KEY, "data": payload}
        for initialized in (True, False):
            store = make_store(hass)
            classification, _ = await store.async_classify_setup(initialized)
            assert classification is SetupClassification.INTEGRITY_LOSS

    async def test_malformed_payload_with_uninitialized_flag_is_loss(
        self, hass, hass_storage
    ) -> None:
        """Present-but-malformed data is never treated as a first install."""
        hass_storage[KEY] = {
            "version": 1,
            "minor_version": 1,
            "key": KEY,
            "data": {"version": 1, "surprise": True},
        }
        store = make_store(hass)
        classification, _ = await store.async_classify_setup(False)
        assert classification is SetupClassification.INTEGRITY_LOSS


class TestVerifiedWrites:
    """§23.4 atomicity, revision, read-back (PI7, PI11, PI20)."""

    async def test_every_store_uses_atomic_writes(self, hass, hass_storage) -> None:
        store = make_store(hass)
        assert store._store._atomic_writes is True
        await store.async_first_initialize()
        # The read-back Store is created fresh per write with the same flag;
        # assert via the module factory used for it.
        from custom_components.moisture_loop.storage import _new_store

        assert _new_store(hass, KEY)._atomic_writes is True

    async def test_pi7_write_failure_fails_closed(self, hass, hass_storage) -> None:
        store = make_store(hass)
        store._store.async_save = _async_raise(OSError("disk full"))  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError):
            await store.async_first_initialize()
        assert not store.loaded
        assert KEY not in hass_storage
        # Setup remains re-runnable as a first install (flag stayed false).
        fresh = make_store(hass)
        classification, _ = await fresh.async_classify_setup(False)
        assert classification is SetupClassification.FIRST_INSTALL

    async def test_pi7_swallowed_write_detected_by_read_back(self, hass, hass_storage) -> None:
        """Core consumes write errors; the fresh-Store round trip catches it."""
        store = make_store(hass)
        store._store.async_save = _async_return(None)  # silently does nothing
        with pytest.raises(StoreWriteVerificationError, match="no data"):
            await store.async_first_initialize()
        assert not store.loaded

    async def test_pi11_failed_write_leaves_previous_revision(self, hass, hass_storage) -> None:
        previous = store_snapshot(revision=5)
        seed(hass_storage, previous)
        store = make_store(hass)
        await store.async_classify_setup(True)
        store._store.async_save = _async_raise(OSError("interrupted"))  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError):
            await store.async_update_zone(
                "zone-a", lambda r: ZoneRecord(ControllerState.DISABLED, False)
            )
        # In-memory snapshot not adopted; on-disk data is the previous
        # complete revision.
        assert store.data == previous
        fresh = make_store(hass)
        _, data = await fresh.async_classify_setup(True)
        assert data == previous

    async def test_accessors_before_load(self, hass) -> None:
        store = make_store(hass)
        assert store.generation_id == GENERATION
        assert not store.loaded
        with pytest.raises(StoreNotLoadedError):
            _ = store.data

    async def test_read_back_load_failure_is_write_failure(
        self, hass, hass_storage, monkeypatch
    ) -> None:
        store = make_store(hass)

        class _BrokenStore:
            async def async_load(self):
                raise OSError("read-back unreadable")

        import custom_components.moisture_loop.storage as storage_module

        monkeypatch.setattr(storage_module, "_new_store", lambda *a: _BrokenStore())
        with pytest.raises(StoreWriteVerificationError, match="read-back load failed"):
            await store.async_first_initialize()
        assert not store.loaded

    async def test_read_back_malformed_is_write_failure(self, hass, hass_storage) -> None:
        store = make_store(hass)

        async def garbling_save(payload) -> None:
            hass_storage[KEY] = {
                "version": 1,
                "minor_version": 1,
                "key": KEY,
                "data": {"version": 1, "nonsense": True},
            }

        store._store.async_save = garbling_save  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError, match="malformed"):
            await store.async_first_initialize()

    async def test_read_back_generation_mismatch_is_write_failure(self, hass, hass_storage) -> None:
        store = make_store(hass)

        async def wrong_generation_save(payload) -> None:
            tampered = dict(payload)
            tampered["generation_id"] = "someone-else"
            hass_storage[KEY] = {
                "version": 1,
                "minor_version": 1,
                "key": KEY,
                "data": tampered,
            }

        store._store.async_save = wrong_generation_save  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError, match="generation mismatch"):
            await store.async_first_initialize()

    async def test_read_back_payload_mismatch_is_write_failure(self, hass, hass_storage) -> None:
        seed(hass_storage, store_snapshot(revision=5))
        store = make_store(hass)
        await store.async_classify_setup(True)

        async def zone_tampering_save(payload) -> None:
            tampered = dict(payload)
            zones = {k: dict(v) for k, v in tampered["zones"].items()}
            zones["zone-a"]["enabled"] = False
            tampered["zones"] = zones
            hass_storage[KEY] = {
                "version": 1,
                "minor_version": 1,
                "key": KEY,
                "data": tampered,
            }

        store._store.async_save = zone_tampering_save  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError, match="payload mismatch"):
            await store.async_update_zone(
                "zone-a", lambda r: ZoneRecord(ControllerState.IDLE, True)
            )

    async def test_read_back_mismatch_prevents_adoption(self, hass, hass_storage) -> None:
        seed(hass_storage, store_snapshot(revision=5))
        store = make_store(hass)
        await store.async_classify_setup(True)

        async def tampering_save(payload) -> None:
            tampered = dict(payload)
            tampered["store_revision"] = 999
            hass_storage[KEY] = {
                "version": 1,
                "minor_version": 1,
                "key": KEY,
                "data": tampered,
            }

        store._store.async_save = tampering_save  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError, match="revision mismatch"):
            await store.async_update_zone(
                "zone-a", lambda r: ZoneRecord(ControllerState.IDLE, True)
            )
        assert store.data.store_revision == 5

    async def test_revisions_increase_monotonically(self, hass, hass_storage) -> None:
        store = make_store(hass)
        await store.async_first_initialize()
        assert store.data.store_revision == 1
        for expected in (2, 3, 4):
            await store.async_update_zone(
                "zone-a", lambda r: ZoneRecord(ControllerState.IDLE, True)
            )
            assert store.data.store_revision == expected

    async def test_pi20_concurrent_zone_writes_serialize(self, hass, hass_storage) -> None:
        store = make_store(hass)
        await store.async_first_initialize()

        async def write(zone_id: str, enabled: bool) -> None:
            await store.async_update_zone(
                zone_id, lambda r: ZoneRecord(ControllerState.IDLE, enabled)
            )

        await asyncio.gather(
            write("zone-a", True),
            write("zone-b", False),
            write("zone-c", True),
        )
        data = store.data
        # No lost updates: every zone present with its own state.
        assert set(data.zones) == {"zone-a", "zone-b", "zone-c"}
        assert data.zones["zone-b"].enabled is False
        # Strictly increasing complete revisions: 1 (init) + 3 writes.
        assert data.store_revision == 4
        fresh = make_store(hass)
        _, reloaded = await fresh.async_classify_setup(True)
        assert reloaded == data


class TestRunProtocol:
    """§23.3 run-ID primitives (PI18, PI19)."""

    async def test_clean_detection_and_new_run(self, hass, hass_storage) -> None:
        seed(hass_storage, store_snapshot(active="run-a", clean="run-a"))
        store = make_store(hass)
        await store.async_classify_setup(True)
        previous = await store.async_begin_new_run("run-b")
        assert previous.previous_run_was_clean
        assert store.data.run == RunIds("run-b", "run-a")

    async def test_pi18_crashed_intermediate_run_is_unclean(self, hass, hass_storage) -> None:
        """Run A clean -> Run B persisted active then crash -> Run C mismatch."""
        seed(hass_storage, store_snapshot(active="run-a", clean="run-a"))
        run_b = make_store(hass)
        await run_b.async_classify_setup(True)
        await run_b.async_begin_new_run("run-b")
        # Run B crashes here (no clean marking). Run C starts fresh:
        run_c = make_store(hass)
        await run_c.async_classify_setup(True)
        previous = await run_c.async_begin_new_run("run-c")
        assert previous == RunIds("run-b", "run-a")
        assert not previous.previous_run_was_clean  # no stale clean truth

    async def test_pi19_unverified_new_run_id_fails_closed(self, hass, hass_storage) -> None:
        seed(hass_storage, store_snapshot(active="run-a", clean="run-a"))
        store = make_store(hass)
        await store.async_classify_setup(True)
        store._store.async_save = _async_return(None)  # swallowed write
        with pytest.raises(StoreWriteVerificationError):
            await store.async_begin_new_run("run-b")
        # The previous snapshot is untouched; this process never becomes
        # watering-capable (the caller aborts setup on the exception).
        assert store.data.run == RunIds("run-a", "run-a")

    async def test_mark_clean_shutdown(self, hass, hass_storage) -> None:
        seed(hass_storage, store_snapshot(active="run-b", clean="run-a"))
        store = make_store(hass)
        await store.async_classify_setup(True)
        await store.async_mark_clean_shutdown()
        assert store.data.run == RunIds("run-b", "run-b")
        fresh = make_store(hass)
        _, data = await fresh.async_classify_setup(True)
        assert data is not None and data.run.previous_run_was_clean


class TestSoakingRebase:
    """§23.3/§25.3 owner rebase primitive (LC10 storage portion)."""

    async def test_rebase_changes_owner_only(self, hass, hass_storage) -> None:
        record = soaking_record(owner="run-a")
        seed(hass_storage, store_snapshot(zones={"zone-a": record}))
        store = make_store(hass)
        await store.async_classify_setup(True)
        await store.async_rebase_soaking_owner("zone-a", "run-b")
        rebased = store.data.zones["zone-a"]
        assert rebased.session is not None and record.session is not None
        assert rebased.session.owner_run_id == "run-b"
        assert rebased.session == record.session.evolve(owner_run_id="run-b")
        assert rebased.evolve(session=record.session) == record

    async def test_rebase_write_failure_fails_closed(self, hass, hass_storage) -> None:
        record = soaking_record(owner="run-a")
        seed(hass_storage, store_snapshot(zones={"zone-a": record}))
        store = make_store(hass)
        await store.async_classify_setup(True)
        store._store.async_save = _async_raise(OSError("boom"))  # type: ignore[method-assign]
        with pytest.raises(StoreWriteVerificationError):
            await store.async_rebase_soaking_owner("zone-a", "run-b")
        assert store.data.zones["zone-a"] == record  # LC9 storage portion

    async def test_rebase_without_session_raises(self, hass, hass_storage) -> None:
        seed(hass_storage, store_snapshot())
        store = make_store(hass)
        await store.async_classify_setup(True)
        with pytest.raises(StoreNotLoadedError):
            await store.async_rebase_soaking_owner("zone-a", "run-b")


class TestIntegrityReconstruction:
    """§23.5 steps 4-5 plus PI9/PI10 budget consequences."""

    async def test_reconstruction_exhausts_current_day(self, hass, hass_storage) -> None:
        store = make_store(hass)
        data = await store.async_reconstruct_after_integrity_loss(
            {"zone-a": 3600, "zone-b": 7200}, date(2026, 8, 21)
        )
        for zone_id, max_daily in (("zone-a", 3600.0), ("zone-b", 7200.0)):
            record = data.zones[zone_id]
            assert record.state is ControllerState.FAULT
            assert record.active_fault is FaultCode.RESTORED_FROM_UNSAFE_STATE
            assert record.daily == DailyRuntime(date(2026, 8, 21), max_daily)
        fresh = make_store(hass)
        classification, reloaded = await fresh.async_classify_setup(True)
        assert classification is SetupClassification.INITIALIZED_OK
        assert reloaded == data

    async def test_pi9_pi10_blocks_auto_and_manual_even_after_same_day_ack(
        self, hass, hass_storage
    ) -> None:
        """The reconstructed record refuses both modes through pure guards."""
        store = make_store(hass)
        data = await store.async_reconstruct_after_integrity_loss(
            {"zone-a": 3600}, date(2026, 8, 21)
        )
        record = data.zones["zone-a"]
        config = ZoneConfig(
            name="Zone A",
            moisture_sensor="sensor.a",
            actuator="switch.a",
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

        def zone_input(event, fault):
            return TransitionInput(
                now_utc=NOW,
                config=config,
                state=record.state,
                enabled=record.enabled,
                session=None,
                active_fault=fault,
                secondary_fault=None,
                observation=MoistureObservation(27.0, MoistureClassification.VALID, NOW, 0.0),
                daily_runtime_s=record.daily.runtime_s if record.daily else 0.0,
                last_session_end_utc=None,
                actuator=ActuatorAssessment(True, True, False),
                resource=ResourceAssessment(True, True),
                armed_watchdog=None,
                event=event,
                new_session_identity=SessionIdentity("s", "r", "f"),
            )

        # With the fault latched: manual refused (blocking fault).
        refused = decide(zone_input(ManualStartRequested(600.0), record.active_fault))
        assert refused.transition_id == "T41"
        # AUTO in FAULT never evaluates.
        assert decide(zone_input(AutoEvaluate(), record.active_fault)).no_op
        # After same-day acknowledgement (fault cleared, state IDLE), the
        # exhausted budget still refuses both modes (PI10).
        acked = record.evolve(state=ControllerState.IDLE, active_fault=None)
        record = acked
        auto = decide(zone_input(AutoEvaluate(), None))
        assert auto.transition_id == "T2"
        assert auto.guard_result is not None
        assert "G-DAY" in auto.guard_result.failed_guards
        manual = decide(zone_input(ManualStartRequested(600.0), None))
        assert manual.guard_result is not None
        assert "G-MANUAL-SAFE:daily_exhausted" in manual.guard_result.failed_guards


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner


def _async_raise(exc: Exception):
    async def _inner(*args, **kwargs):
        raise exc

    return _inner
