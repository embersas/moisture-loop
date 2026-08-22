"""Spec.4 Stage-3 configuration reconciliation and tombstone tests."""

from __future__ import annotations

import asyncio
from types import MappingProxyType

import pytest

pytest.importorskip("homeassistant")

from homeassistant.config_entries import ConfigEntry, ConfigSubentry, ConfigSubentryData
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.moisture_loop import EntryRuntime
from custom_components.moisture_loop.const import (
    CONF_RUNTIME_STORE_GENERATION_ID,
    CONF_RUNTIME_STORE_INITIALIZED,
    DOMAIN,
)
from custom_components.moisture_loop.models import (
    AppliedEntityIdentity,
    BlockerReason,
    CompletionReason,
    ControllerState,
    DailyRuntime,
    RuntimeLifecycle,
    ZoneConfig,
)
from custom_components.moisture_loop.reconciliation import (
    ConfigurationReconciliationCoordinator,
    ImmutableZoneSnapshot,
    ReconciliationError,
    immutable_entry_snapshot,
    normalized_zone_fingerprint,
)
from custom_components.moisture_loop.slot_manager import SlotManager

GEN = "11111111-2222-3333-4444-555555555555"
SENSOR = "sensor.stage3_moisture"


def zone_data(actuator: str, *, name: str = "Stage 3 bed") -> dict[str, object]:
    return {
        "name": name,
        "moisture_sensor": SENSOR,
        "actuator": actuator,
        "start_threshold": 30.0,
        "target_threshold": 40.0,
        "pulse_duration": 300,
        "soak_duration": 1200,
        "max_cycles": 4,
        "max_session_runtime": 1800,
        "max_daily_runtime": 3600,
        "min_session_interval": 900,
        "sensor_max_age": 7200,
        "actuator_confirm_timeout": 30,
        "manual_max_duration": 1800,
    }


def pure_snapshot(generation: int, name: str):
    config = ZoneConfig(
        name=name,
        moisture_sensor=SENSOR,
        actuator="switch.stage3_valve",
        start_threshold=30.0,
        target_threshold=40.0,
        pulse_duration_s=300,
        soak_duration_s=1200,
        max_cycles=4,
        max_session_runtime_s=1800,
        max_daily_runtime_s=3600,
        min_session_interval_s=900,
        sensor_max_age_s=7200,
        actuator_confirm_timeout_s=30,
        manual_max_duration_s=1800,
    )
    sensor = AppliedEntityIdentity(None, SENSOR, "sensor")
    actuator = AppliedEntityIdentity(None, config.actuator, "switch")
    fingerprint = normalized_zone_fingerprint(
        "zone-a", config, sensor, actuator, "Australia/Brisbane"
    )
    return immutable_entry_snapshot(
        generation,
        [ImmutableZoneSnapshot("zone-a", config, sensor, actuator, fingerprint)],
    )


async def settle(hass, cycles: int = 12) -> None:
    for _ in range(cycles):
        await asyncio.sleep(0)
        await hass.async_block_till_done()


class TestCoordinator:
    async def test_immutable_latest_snapshot_wins_and_stale_cannot_open(self) -> None:
        source = {"name": "generation-10"}
        slots = SlotManager()
        await slots.async_enable_grants()
        started = asyncio.Event()
        release = asyncio.Event()
        applied: list[int] = []

        def build(generation: int):
            return pure_snapshot(generation, source["name"])

        async def apply(snapshot, is_current) -> None:
            applied.append(snapshot.observed_generation)
            if snapshot.observed_generation == 1:
                started.set()
                await release.wait()
            if snapshot.observed_generation == 1:
                assert not is_current()

        coordinator = ConfigurationReconciliationCoordinator(slots, build, apply)
        coordinator.observe_current()
        old_snapshot = coordinator.observed_snapshot
        task = asyncio.create_task(coordinator.async_start())
        await started.wait()

        source["name"] = "generation-11"
        coordinator.observe_current()
        assert old_snapshot is not None
        assert old_snapshot.zones[0].config.name == "generation-10"
        assert slots.snapshot().reconciliation_dirty
        assert not slots.snapshot().admission_open

        release.set()
        await task
        assert applied == [1, 2]
        assert coordinator.applied_generation == 2
        assert coordinator.applied_snapshot is not None
        assert coordinator.applied_snapshot.zones[0].config.name == "generation-11"
        assert coordinator.superseded_count == 1
        assert slots.snapshot().admission_open
        await asyncio.gather(
            coordinator.async_reconcile(),
            coordinator.async_reconcile(),
            coordinator.async_reconcile(),
        )
        assert applied == [1, 2]

    async def test_failure_and_stop_remain_fail_closed(self) -> None:
        slots = SlotManager()
        await slots.async_enable_grants()

        async def fail(_snapshot, _is_current) -> None:
            raise RuntimeError("injected Store failure")

        coordinator = ConfigurationReconciliationCoordinator(
            slots, lambda generation: pure_snapshot(generation, "bad"), fail
        )
        coordinator.observe_current()
        with pytest.raises(ReconciliationError):
            await coordinator.async_start()
        assert coordinator.failed and coordinator.dirty
        assert coordinator.applied_generation == 0
        assert slots.snapshot().reconciliation_failed
        assert not slots.snapshot().admission_open

        gate = asyncio.Event()

        async def slow(_snapshot, _is_current) -> None:
            await gate.wait()

        slots2 = SlotManager()
        await slots2.async_enable_grants()
        stopping = ConfigurationReconciliationCoordinator(
            slots2, lambda generation: pure_snapshot(generation, "stopping"), slow
        )
        stopping.observe_current()
        worker = asyncio.create_task(stopping.async_start())
        await asyncio.sleep(0)
        stop = asyncio.create_task(stopping.async_stop())
        await asyncio.sleep(0)
        gate.set()
        await asyncio.gather(worker, stop)
        assert stopping.applied_generation == 0
        assert not slots2.snapshot().admission_open

    async def test_add_update_delete_burst_coalesces_to_empty_latest(self) -> None:
        source = {"present": True, "name": "added"}
        slots = SlotManager()
        await slots.async_enable_grants()
        started = asyncio.Event()
        release = asyncio.Event()
        applied: list[int] = []

        def build(generation: int):
            if not source["present"]:
                return immutable_entry_snapshot(generation, [])
            return pure_snapshot(generation, source["name"])

        async def apply(snapshot, _is_current) -> None:
            applied.append(snapshot.observed_generation)
            if snapshot.observed_generation == 1:
                started.set()
                await release.wait()

        coordinator = ConfigurationReconciliationCoordinator(slots, build, apply)
        coordinator.observe_current()
        worker = asyncio.create_task(coordinator.async_start())
        await started.wait()
        source["name"] = "updated-once"
        coordinator.observe_current()
        source["name"] = "updated-twice"
        coordinator.observe_current()
        source["present"] = False
        coordinator.observe_current()
        release.set()
        await worker

        assert applied == [1, 4]
        assert coordinator.applied_generation == 4
        assert coordinator.applied_snapshot is not None
        assert coordinator.applied_snapshot.zones == ()
        assert coordinator.superseded_count == 1
        assert slots.snapshot().admission_open


@pytest.fixture
async def runtime_env(hass, hass_storage, freezer):
    freezer.move_to("2026-08-22 10:00:00+10:00")
    registry = er.async_get(hass)
    actuator_entry = registry.async_get_or_create(
        "switch", "test", "stage3-actuator-a", suggested_object_id="stage3_valve"
    )
    actuator = actuator_entry.entity_id
    hass.states.async_set(actuator, "off")
    hass.states.async_set(SENSOR, "35")

    async def turn_on(_call) -> None:
        hass.states.async_set(actuator, "on")

    async def turn_off(_call) -> None:
        hass.states.async_set(actuator, "off")

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Moisture Loop",
        data={
            CONF_RUNTIME_STORE_GENERATION_ID: GEN,
            CONF_RUNTIME_STORE_INITIALIZED: False,
        },
        subentries_data=[
            ConfigSubentryData(
                data=zone_data(actuator),
                subentry_type="zone",
                title="Stage 3 bed",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    runtime = EntryRuntime(hass, entry)
    await runtime.async_initialize()
    await settle(hass)
    yield runtime, entry, actuator_entry, freezer
    await runtime.async_unload()


class TestRuntimeReconciliation:
    async def test_listener_unsubscribe_is_owned_by_entry_unload(
        self, hass, hass_storage, freezer, monkeypatch
    ) -> None:
        freezer.move_to("2026-08-22 10:00:00+10:00")
        registry = er.async_get(hass)
        actuator = registry.async_get_or_create(
            "switch", "test", "listener-cleanup", suggested_object_id="listener_cleanup"
        ).entity_id
        hass.states.async_set(actuator, "off")
        hass.states.async_set(SENSOR, "35")
        callbacks = []
        original_on_unload = ConfigEntry.async_on_unload

        def capture_on_unload(self, func) -> None:
            callbacks.append(func)
            original_on_unload(self, func)

        monkeypatch.setattr(ConfigEntry, "async_on_unload", capture_on_unload)
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_RUNTIME_STORE_GENERATION_ID: GEN,
                CONF_RUNTIME_STORE_INITIALIZED: False,
            },
            subentries_data=[
                ConfigSubentryData(
                    data=zone_data(actuator),
                    subentry_type="zone",
                    title="Listener cleanup",
                    unique_id=None,
                )
            ],
        )
        entry.add_to_hass(hass)
        runtime = EntryRuntime(hass, entry)
        await runtime.async_initialize()
        assert len(entry.update_listeners) == 1
        assert len(callbacks) == 1
        callbacks[0]()
        assert entry.update_listeners == []
        await runtime.async_unload()

    async def test_listener_is_single_and_observation_closes_admission(self, runtime_env) -> None:
        runtime, entry, _actuator_entry, _freezer = runtime_env
        assert runtime._listener_registered
        assert len(entry.update_listeners) == 1
        runtime._register_update_listener()
        assert len(entry.update_listeners) == 1

        listener = entry.update_listeners[0]
        listener_work = listener(runtime.hass, entry)
        assert runtime.coordinator.dirty
        assert not runtime.slots.snapshot().admission_open
        await listener_work

        original = next(iter(entry.subentries.values()))
        old_applied = runtime.coordinator.applied_snapshot
        assert old_applied is not None
        changed = zone_data(original.data["actuator"], name="Changed in place")
        assert runtime.hass.config_entries.async_update_subentry(entry, original, data=changed)
        await settle(runtime.hass)
        assert old_applied.zones[0].config.name == "Stage 3 bed"
        assert runtime.coordinator.applied_snapshot is not None
        assert runtime.coordinator.applied_snapshot.zones[0].config.name == "Changed in place"
        assert runtime.slots.snapshot().admission_open

    async def test_delete_readd_exact_uuid_reuses_record_and_history(self, runtime_env) -> None:
        runtime, entry, actuator_entry, _freezer = runtime_env
        old_subentry_id = next(iter(entry.subentries))
        old_binding = runtime.bindings[old_subentry_id]
        record_id = old_binding.safety_record_id
        lineage_id = runtime.store.data.safety_records[record_id].safety_lineage_id
        history_id = old_binding.zone_history_id
        old_applied = runtime.coordinator.applied_snapshot
        assert old_applied is not None

        assert runtime.hass.config_entries.async_remove_subentry(entry, old_subentry_id)
        await settle(runtime.hass)
        tombstone = runtime.store.data.safety_records[record_id]
        assert tombstone.runtime_lifecycle is RuntimeLifecycle.RETIRED
        assert tombstone.active_subentry_id is None
        assert old_subentry_id in tombstone.previous_subentry_ids
        assert runtime.controllers == {}

        readded_id = "stage3-readded-zone"
        readded = ConfigSubentry(
            data=MappingProxyType(zone_data(actuator_entry.entity_id, name="Re-added")),
            subentry_id=readded_id,
            subentry_type="zone",
            title="Re-added",
            unique_id=None,
        )
        assert runtime.hass.config_entries.async_add_subentry(entry, readded)
        await settle(runtime.hass)

        active = runtime.store.data.safety_records[record_id]
        assert active.runtime_lifecycle is RuntimeLifecycle.ACTIVE
        assert active.active_subentry_id == readded_id
        assert active.safety_lineage_id == lineage_id
        assert active.zone_history_id == history_id
        assert runtime.bindings[readded_id].safety_record_id == record_id
        assert len(runtime.store.data.safety_records) == 1
        assert old_applied.zones[0].subentry_id == old_subentry_id
        assert old_applied.zones[0].config.name == "Stage 3 bed"

    async def test_same_entity_id_new_registry_uuid_fails_closed(self, runtime_env) -> None:
        runtime, entry, actuator_entry, _freezer = runtime_env
        subentry = next(iter(entry.subentries.values()))
        old_record_id = runtime.bindings[subentry.subentry_id].safety_record_id
        entity_id = actuator_entry.entity_id
        registry = er.async_get(runtime.hass)
        registry.async_remove(entity_id)
        runtime.hass.states.async_remove(entity_id)
        replacement = registry.async_get_or_create(
            "switch",
            "test",
            "stage3-different-actuator",
            suggested_object_id=entity_id.split(".", 1)[1],
        )
        assert replacement.entity_id == entity_id
        runtime.hass.states.async_set(entity_id, "off")

        assert runtime.hass.config_entries.async_update_subentry(
            entry, subentry, title="Identity changed"
        )
        await settle(runtime.hass)
        assert runtime.coordinator.failed
        assert runtime.coordinator.dirty
        assert not runtime.slots.snapshot().admission_open
        assert set(runtime.store.data.safety_records) == {old_record_id}
        incident = runtime.store.data.safety_records[old_record_id].identity_incident
        assert incident is not None

    async def test_native_delete_watering_uses_config_changed_and_no_resurrection(
        self, runtime_env
    ) -> None:
        runtime, entry, _actuator_entry, _freezer = runtime_env
        subentry_id = next(iter(entry.subentries))
        record_id = runtime.bindings[subentry_id].safety_record_id
        runtime.hass.states.async_set(SENSOR, "20")
        await settle(runtime.hass)
        assert runtime.controllers[subentry_id].state is ControllerState.WATERING

        assert runtime.hass.config_entries.async_remove_subentry(entry, subentry_id)
        await settle(runtime.hass)
        record = runtime.store.data.safety_records[record_id]
        history = runtime.store.data.zone_histories[record.zone_history_id]
        assert record.runtime_lifecycle is RuntimeLifecycle.RETIRED
        assert history.zone_runtime.session is None
        assert history.zone_runtime.last_session_summary is not None
        assert history.zone_runtime.last_session_summary.reason is CompletionReason.CONFIG_CHANGED
        assert runtime.controllers == {}

    async def test_a_to_b_retains_a_hazard_and_continuing_history(self, runtime_env) -> None:
        runtime, entry, actuator_a, _freezer = runtime_env
        subentry = next(iter(entry.subentries.values()))
        binding_a = runtime.bindings[subentry.subentry_id]
        record_a_id = binding_a.safety_record_id
        history_id = binding_a.zone_history_id
        await binding_a.controller.async_set_enabled(False)
        assert binding_a.controller.state is ControllerState.DISABLED
        runtime.hass.states.async_set(actuator_a.entity_id, "on")
        await settle(runtime.hass)
        assert (record_a_id, BlockerReason.EXTERNAL_FLOW) in runtime.slots.blockers()

        registry = er.async_get(runtime.hass)
        actuator_b = registry.async_get_or_create(
            "switch", "test", "stage3-actuator-b", suggested_object_id="stage3_valve_b"
        )
        runtime.hass.states.async_set(actuator_b.entity_id, "off")
        changed = zone_data(actuator_b.entity_id, name="Actuator B")
        assert runtime.hass.config_entries.async_update_subentry(entry, subentry, data=changed)
        await settle(runtime.hass)

        binding_b = runtime.bindings[subentry.subentry_id]
        assert binding_b.safety_record_id != record_a_id
        assert binding_b.zone_history_id == history_id
        record_a = runtime.store.data.safety_records[record_a_id]
        record_b = runtime.store.data.safety_records[binding_b.safety_record_id]
        assert record_a.runtime_lifecycle is RuntimeLifecycle.DELETE_PENDING
        assert record_b.runtime_lifecycle is RuntimeLifecycle.ACTIVE
        history = runtime.store.data.zone_histories[history_id]
        assert not history.zone_runtime.enabled
        assert history.zone_runtime.state is ControllerState.DISABLED
        assert (record_a_id, BlockerReason.EXTERNAL_FLOW) in runtime.slots.blockers()
        assert BlockerReason.EXTERNAL_FLOW in record_a.blocker_reasons
        assert BlockerReason.EXTERNAL_FLOW not in record_b.blocker_reasons
        assert len(runtime.store.data.safety_records) == 2
        assert not runtime.retained_controllers[record_a_id].runtime_eligible

    async def test_reactivation_retains_exact_blocker_budget_and_interval(
        self, runtime_env
    ) -> None:
        runtime, entry, actuator_entry, _freezer = runtime_env
        old_subentry_id = next(iter(entry.subentries))
        binding = runtime.bindings[old_subentry_id]
        record_id = binding.safety_record_id
        history_id = binding.zone_history_id
        ended = dt_util.utcnow()
        await runtime.store.async_update_record_runtime(
            record_id,
            lambda record: record.evolve(
                last_session_end_utc=ended,
                daily=DailyRuntime(ended.astimezone(runtime._local_tz).date(), 123.0),
            ),
        )
        await runtime.slots.async_add_blocker(record_id, BlockerReason.INTEGRATION_OFF_UNCONFIRMED)

        assert runtime.hass.config_entries.async_remove_subentry(entry, old_subentry_id)
        await settle(runtime.hass)
        tombstone = runtime.store.data.safety_records[record_id]
        assert tombstone.runtime_lifecycle is RuntimeLifecycle.DELETE_PENDING

        readded_id = "stage3-hazard-readd"
        assert runtime.hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType(zone_data(actuator_entry.entity_id)),
                subentry_id=readded_id,
                subentry_type="zone",
                title="Hazard re-add",
                unique_id=None,
            ),
        )
        await settle(runtime.hass)
        active = runtime.store.data.safety_records[record_id]
        history = runtime.store.data.zone_histories[history_id]
        assert active.runtime_lifecycle is RuntimeLifecycle.ACTIVE
        assert active.zone_history_id == history_id
        assert history.last_session_end_utc == ended
        assert history.daily is not None and history.daily.runtime_s == 123.0
        assert (
            record_id,
            BlockerReason.INTEGRATION_OFF_UNCONFIRMED,
        ) in runtime.slots.blockers()

    async def test_registry_rename_reuses_same_record(self, runtime_env) -> None:
        runtime, entry, actuator_entry, _freezer = runtime_env
        subentry = next(iter(entry.subentries.values()))
        record_id = runtime.bindings[subentry.subentry_id].safety_record_id
        registry = er.async_get(runtime.hass)
        renamed_id = "switch.stage3_valve_renamed"
        registry.async_update_entity(actuator_entry.entity_id, new_entity_id=renamed_id)
        runtime.hass.states.async_set(renamed_id, "off")
        assert runtime.hass.config_entries.async_update_subentry(
            entry, subentry, data=zone_data(renamed_id, name="Renamed")
        )
        await settle(runtime.hass)
        assert runtime.bindings[subentry.subentry_id].safety_record_id == record_id
        record = runtime.store.data.safety_records[record_id]
        assert record.actuator_identity.registry_entry_id == actuator_entry.id
        assert record.actuator_identity.last_known_entity_id == renamed_id
        assert len(runtime.store.data.safety_records) == 1

    async def test_store_only_active_record_becomes_implicit_tombstone(self, runtime_env) -> None:
        runtime, entry, actuator_entry, _freezer = runtime_env
        subentry_id = next(iter(entry.subentries))
        record_id = runtime.bindings[subentry_id].safety_record_id

        await runtime.coordinator.async_stop()
        assert runtime.hass.config_entries.async_remove_subentry(entry, subentry_id)
        await settle(runtime.hass)
        assert runtime.store.data.safety_records[record_id].runtime_lifecycle is (
            RuntimeLifecycle.ACTIVE
        )
        await runtime.async_unload()

        restarted = EntryRuntime(runtime.hass, entry)
        await restarted.async_initialize()
        await settle(runtime.hass)
        retained = restarted.store.data.safety_records[record_id]
        assert retained.runtime_lifecycle is RuntimeLifecycle.RETIRED
        assert retained.active_subentry_id is None
        assert retained.actuator_identity.registry_entry_id == actuator_entry.id
        assert restarted.controllers == {}
        await restarted.async_unload()

    async def test_store_only_missing_identity_stays_delete_pending(self, runtime_env) -> None:
        runtime, entry, actuator_entry, _freezer = runtime_env
        subentry_id = next(iter(entry.subentries))
        record_id = runtime.bindings[subentry_id].safety_record_id
        await runtime.coordinator.async_stop()
        assert runtime.hass.config_entries.async_remove_subentry(entry, subentry_id)
        registry = er.async_get(runtime.hass)
        registry.async_remove(actuator_entry.entity_id)
        runtime.hass.states.async_remove(actuator_entry.entity_id)
        await settle(runtime.hass)
        await runtime.async_unload()

        restarted = EntryRuntime(runtime.hass, entry)
        await restarted.async_initialize()
        await settle(runtime.hass)
        retained = restarted.store.data.safety_records[record_id]
        assert retained.runtime_lifecycle is RuntimeLifecycle.DELETE_PENDING
        assert retained.identity_incident is not None
        assert BlockerReason.ACTUATOR_NOT_PROVEN_OFF in retained.blocker_reasons
        assert restarted.controllers == {}
        assert not restarted.slots.blockers_empty()
        await restarted.async_unload()

    async def test_store_failure_keeps_old_controller_and_barrier_closed(self, runtime_env) -> None:
        runtime, entry, _actuator_entry, _freezer = runtime_env
        subentry = next(iter(entry.subentries.values()))
        old_controller = runtime.controllers[subentry.subentry_id]

        async def fail(_mutator):
            raise RuntimeError("injected reconciliation Store failure")

        runtime.store.async_reconcile = fail  # type: ignore[method-assign]
        assert runtime.hass.config_entries.async_update_subentry(
            entry,
            subentry,
            data=zone_data(subentry.data["actuator"], name="Will fail"),
        )
        await settle(runtime.hass)
        assert runtime.coordinator.failed and runtime.coordinator.dirty
        assert not runtime.slots.snapshot().admission_open
        assert runtime.controllers[subentry.subentry_id] is old_controller
