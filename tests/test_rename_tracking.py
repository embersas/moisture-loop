"""Slice 13 live-defect F2/F3 regression: actuator Entity Registry renames.

SPEC 46 item 3 requires validated ``async_track_entity_registry_updated_event``
auto-fixup.  The durable equivalence key is the Entity Registry entry UUID
(SPEC 6, 23.2 item 1, 25.1.1, I35): a different current entity ID for the same
UUID is the same actuator, so the safety record, lineage, zone history,
blocker keys, accounting and applied configuration must all survive it, and a
textual rename must never be processed as a T21/T39 configuration change.
Entity-ID reuse by a different UUID and missing durable identity still fail
closed (PI25, TB9, I33).

End-to-end through the real config flow, real setup, real platforms and the
real Entity Registry on the supported Home Assistant harness.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("homeassistant")

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from test_entities import (
    ACTUATOR,
    SENSOR,
    settle,
    setup_with_zone,
)

from custom_components.soilsync.const import DOMAIN
from custom_components.soilsync.models import (
    BlockerReason,
    CompletionReason,
    ControllerState,
    IdentityStatus,
    PossibleFlowOwner,
    RuntimeLifecycle,
    SessionMode,
)
from custom_components.soilsync.repairs import ISSUE_IDENTITY_CONFLICT, record_issue_id

RENAMED = "valve.valve_1_renamed"


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations):
    return


class MovableValve:
    """Scripted valve whose addressable entity ID can be renamed."""

    def __init__(self, hass, entity_id: str) -> None:
        self.hass = hass
        self.entity_id = entity_id
        self.on_calls = 0
        self.off_calls = 0
        self.close_behavior = "ack"
        self.set_state("closed", 0)

        async def open_valve(call) -> None:
            self.on_calls += 1
            self.set_state("open", 100, context=call.context)

        async def close_valve(call) -> None:
            self.off_calls += 1
            if self.close_behavior == "ack":
                self.set_state("closed", 0, context=call.context)

        hass.services.async_register("valve", "open_valve", open_valve)
        hass.services.async_register("valve", "close_valve", close_valve)

    def set_state(self, state: str, position: int = 0, context=None) -> None:
        self.hass.states.async_set(
            self.entity_id,
            state,
            {"supported_features": 3, "current_position": position},
            context=context,
        )

    def move_state_to(self, entity_id: str) -> None:
        """Mirror what a real entity platform does across a rename."""
        old = self.hass.states.get(self.entity_id)
        assert old is not None
        previous = self.entity_id
        self.entity_id = entity_id
        self.hass.states.async_set(entity_id, old.state, dict(old.attributes))
        self.hass.states.async_remove(previous)


async def _build_env(hass, freezer, *, register_sensor: bool):
    freezer.move_to("2026-08-21 12:00:00+00:00")
    registry = er.async_get(hass)
    actuator_entry = registry.async_get_or_create(
        "valve", "test", "rename-valve", suggested_object_id="valve_1"
    )
    assert actuator_entry.entity_id == ACTUATOR
    sensor_entry = None
    if register_sensor:
        sensor_entry = registry.async_get_or_create(
            "sensor", "test", "rename-sensor", suggested_object_id="moisture_1"
        )
        assert sensor_entry.entity_id == SENSOR
    valve = MovableValve(hass, ACTUATOR)
    hass.states.async_set(SENSOR, "35")
    await hass.async_block_till_done()
    entry, subentry_id = await setup_with_zone(hass)
    from types import SimpleNamespace

    return SimpleNamespace(
        hass=hass,
        freezer=freezer,
        registry=registry,
        actuator_entry=actuator_entry,
        sensor_entry=sensor_entry,
        valve=valve,
        entry=entry,
        subentry_id=subentry_id,
    )


@pytest.fixture
async def env(hass, freezer):
    """Registry-backed actuator; the moisture sensor has no Registry entry."""
    yield await _build_env(hass, freezer, register_sensor=False)


@pytest.fixture
async def env_registered_sensor(hass, freezer):
    """Both configured entities are Entity Registry backed."""
    yield await _build_env(hass, freezer, register_sensor=True)


async def advance(env, seconds: float) -> None:
    env.freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(env.hass, dt_util.utcnow())
    await settle(env.hass)


async def set_moisture(env, value: str) -> None:
    env.hass.states.async_set(SENSOR, value)
    await settle(env.hass)


def runtime(env):
    return env.entry.runtime_data


def canonical(env):
    """Return (record, history) for the single configured zone."""
    live = runtime(env)
    controller = live.controllers[env.subentry_id]
    record = live.store.data.safety_records[controller.safety_record_id]
    history = live.store.data.zone_histories[record.zone_history_id]
    return record, history


def identity_issue_ids(env) -> list[str]:
    return [
        issue.issue_id
        for issue in ir.async_get(env.hass).issues.values()
        if issue.domain == DOMAIN and ISSUE_IDENTITY_CONFLICT in issue.issue_id
    ]


async def rename_actuator(env, new_entity_id: str = RENAMED) -> None:
    """Rename in the real Entity Registry and move the state like a platform."""
    env.registry.async_update_entity(env.valve.entity_id, new_entity_id=new_entity_id)
    env.valve.move_state_to(new_entity_id)
    await settle(env.hass)


class TestActuatorRenameTracking:
    async def test_r1_idle_rename_keeps_one_record_and_follows_addressing(self, env) -> None:
        """R1: IDLE exact-UUID rename; same record/lineage/history, no Repair."""
        live = runtime(env)
        before_record, before_history = canonical(env)
        durable_uuid = before_record.actuator_identity.registry_entry_id
        assert durable_uuid == env.actuator_entry.id
        applied_before = live.coordinator.applied_snapshot
        assert applied_before is not None
        zone_before = applied_before.by_subentry_id()[env.subentry_id]

        await rename_actuator(env)

        after_record, _after_history = canonical(env)
        # Durable safety identity is untouched.
        assert after_record.safety_record_id == before_record.safety_record_id
        assert after_record.safety_lineage_id == before_record.safety_lineage_id
        assert after_record.zone_history_id == before_history.zone_history_id
        assert after_record.actuator_identity.registry_entry_id == durable_uuid
        assert after_record.actuator_identity.identity_status is IdentityStatus.REGISTRY_CONFIRMED
        assert after_record.runtime_lifecycle is RuntimeLifecycle.ACTIVE
        assert len(live.store.data.safety_records) == 1
        # Current addressing followed the rename.
        assert after_record.actuator_identity.last_known_entity_id == RENAMED
        controller = live.controllers[env.subentry_id]
        assert controller.config.actuator == RENAMED
        # The configured reference and therefore the fingerprint are unchanged,
        # so this is not a configuration change (SPEC 9, 12.2, 14 T21/T39).
        applied_after = live.coordinator.applied_snapshot
        assert applied_after is not None
        zone_after = applied_after.by_subentry_id()[env.subentry_id]
        assert zone_after.config_fingerprint == zone_before.config_fingerprint
        assert applied_after.entry_snapshot_fingerprint == applied_before.entry_snapshot_fingerprint
        assert env.entry.subentries[env.subentry_id].data["actuator"] == ACTUATOR
        # No Repair, clean barrier, entry still usable.
        assert identity_issue_ids(env) == []
        assert after_record.identity_incident is None
        assert not live.coordinator.failed
        assert not live.coordinator.dirty
        assert live.slots.snapshot().admission_open
        assert live.action_refusal_key(controller) is None

    async def test_r1_rename_keeps_observation_and_off_ability(self, env) -> None:
        """The renamed entity is observed and commandable with no gap."""
        live = runtime(env)
        await rename_actuator(env)
        controller = live.controllers[env.subentry_id]
        # The removed old entity ID must never look like actuator loss.
        assert controller.state is ControllerState.IDLE
        assert controller.active_fault is None
        # Observation continues on the renamed entity.
        env.valve.set_state("open", 100)
        await settle(env.hass)
        assert controller.assessment.observed_on
        assert controller.external_on
        record, _ = canonical(env)
        assert BlockerReason.EXTERNAL_FLOW in record.blocker_reasons
        env.valve.set_state("closed", 0)
        await settle(env.hass)
        record, _ = canonical(env)
        assert BlockerReason.EXTERNAL_FLOW not in record.blocker_reasons
        assert controller.assessment.proven_off

    async def test_r2_rename_during_watering_does_not_terminate_the_session(self, env) -> None:
        """R2: no unsafe extra ON, no false CONFIG_CHANGED, still addressable."""
        live = runtime(env)
        controller = live.controllers[env.subentry_id]
        await controller.async_manual_start(600.0)
        await settle(env.hass)
        assert controller.state is ControllerState.WATERING
        session_before = controller.session
        assert session_before is not None
        assert session_before.mode is SessionMode.MANUAL
        on_calls_before = env.valve.on_calls

        await rename_actuator(env)

        assert env.valve.on_calls == on_calls_before  # no unsafe extra ON
        assert controller.state is ControllerState.WATERING
        session_after = controller.session
        assert session_after is not None
        assert session_after.session_id == session_before.session_id
        assert session_after.pending_termination_reason is None
        record, _ = canonical(env)
        assert record.runtime_lifecycle is RuntimeLifecycle.ACTIVE
        assert record.actuator_identity.last_known_entity_id == RENAMED
        assert identity_issue_ids(env) == []
        # SPEC 11.4/21: the reconciliation this rename triggers must not
        # relabel integration-owned possible flow as external_flow; that key
        # could never be released by this record's own OFF evidence.
        assert BlockerReason.EXTERNAL_FLOW not in record.blocker_reasons
        assert record.possible_flow_owner is PossibleFlowOwner.INTEGRATION

        # OFF ability continues through the renamed addressing.
        await controller.async_stop_watering()
        await settle(env.hass)
        assert env.valve.off_calls >= 1
        assert controller.state is ControllerState.IDLE
        summary = controller.last_summary
        assert summary is not None
        assert summary.reason is CompletionReason.USER_STOP
        assert summary.reason is not CompletionReason.CONFIG_CHANGED
        # No key survives a normal stop on proven OFF.
        record, _ = canonical(env)
        assert record.blocker_reasons == ()
        assert record.possible_flow_owner is None
        assert runtime(env).slots.blockers() == frozenset()

    async def test_r3_rename_during_soaking_keeps_the_same_session(self, env) -> None:
        """R3: the soak survives; identity and timing are unchanged."""
        live = runtime(env)
        controller = live.controllers[env.subentry_id]
        await set_moisture(env, "20")
        assert controller.state is ControllerState.WATERING
        await advance(env, 301)
        assert controller.state is ControllerState.SOAKING
        session_before = controller.session
        assert session_before is not None

        await rename_actuator(env)

        assert controller.state is ControllerState.SOAKING
        session_after = controller.session
        assert session_after is not None
        assert session_after.session_id == session_before.session_id
        assert session_after.soak_ends_at_utc == session_before.soak_ends_at_utc
        assert session_after.recheck_not_before_utc == session_before.recheck_not_before_utc
        assert session_after.pending_termination_reason is None
        record, history = canonical(env)
        assert record.actuator_identity.last_known_entity_id == RENAMED
        assert history.zone_runtime.session is not None
        assert history.zone_runtime.session.context.session_id == session_before.session_id
        assert identity_issue_ids(env) == []

    async def test_r4_reload_after_rename_loads_and_reuses_the_record(self, env) -> None:
        """R4/F3: reload returns LOADED with the same exact safety record."""
        before_record, before_history = canonical(env)
        await rename_actuator(env)

        assert await env.hass.config_entries.async_reload(env.entry.entry_id)
        await settle(env.hass)

        assert env.entry.state is ConfigEntryState.LOADED
        live = runtime(env)
        after_record, _after_history = canonical(env)
        assert after_record.safety_record_id == before_record.safety_record_id
        assert after_record.safety_lineage_id == before_record.safety_lineage_id
        assert after_record.zone_history_id == before_history.zone_history_id
        assert after_record.actuator_identity.registry_entry_id == env.actuator_entry.id
        assert after_record.actuator_identity.last_known_entity_id == RENAMED
        assert after_record.runtime_lifecycle is RuntimeLifecycle.ACTIVE
        assert after_record.identity_incident is None
        assert len(live.store.data.safety_records) == 1
        assert identity_issue_ids(env) == []
        assert not live.coordinator.failed
        assert live.controllers[env.subentry_id].config.actuator == RENAMED

    async def test_r5_restart_after_rename_resolves_by_registry_uuid(self, env) -> None:
        """R5: a full unload/setup cycle resolves the same durable identity."""
        controller = runtime(env).controllers[env.subentry_id]
        await set_moisture(env, "20")
        assert controller.state is ControllerState.WATERING
        await advance(env, 60)
        await controller.async_stop_watering()
        await settle(env.hass)
        before_record, before_history = canonical(env)
        assert before_history.daily is not None
        charged = before_history.daily.runtime_s
        assert charged > 0.0
        last_end = before_history.last_session_end_utc

        await rename_actuator(env)
        assert await env.hass.config_entries.async_unload(env.entry.entry_id)
        await settle(env.hass)
        assert await env.hass.config_entries.async_setup(env.entry.entry_id)
        await settle(env.hass)

        assert env.entry.state is ConfigEntryState.LOADED
        live = runtime(env)
        after_record, after_history = canonical(env)
        assert after_record.safety_record_id == before_record.safety_record_id
        assert after_record.safety_lineage_id == before_record.safety_lineage_id
        assert after_record.zone_history_id == before_history.zone_history_id
        assert after_record.actuator_identity.registry_entry_id == env.actuator_entry.id
        assert after_record.actuator_identity.last_known_entity_id == RENAMED
        assert live.controllers[env.subentry_id].config.actuator == RENAMED
        # No budget or interval reset (SPEC 10.4, I35).
        assert after_history.daily is not None
        assert after_history.daily.runtime_s == pytest.approx(charged)
        assert after_history.last_session_end_utc == last_end
        assert len(live.store.data.safety_records) == 1
        assert identity_issue_ids(env) == []

    async def test_r6_entity_id_reuse_by_a_different_uuid_fails_closed(self, env) -> None:
        """R6/PI25: a competing durable identity is ambiguity, never adoption."""
        before_record, _ = canonical(env)
        await rename_actuator(env)
        # A genuinely different entity now claims the configured reference.
        other = env.registry.async_get_or_create(
            "valve", "test", "rename-imposter", suggested_object_id="valve_1"
        )
        assert other.entity_id == ACTUATOR
        assert other.id != env.actuator_entry.id
        env.hass.states.async_set(
            ACTUATOR, "closed", {"supported_features": 3, "current_position": 0}
        )
        await settle(env.hass)

        assert not await env.hass.config_entries.async_reload(env.entry.entry_id)
        await settle(env.hass)

        assert env.entry.state is ConfigEntryState.SETUP_RETRY
        assert identity_issue_ids(env) == [
            record_issue_id(
                env.entry.entry_id,
                before_record.safety_record_id,
                ISSUE_IDENTITY_CONFLICT,
            )
        ]

    async def test_r6_identity_repair_clears_once_the_ambiguity_is_resolved(self, env) -> None:
        """A resolved incident must not leave a stale exact-record Repair."""
        before_record, _ = canonical(env)
        await rename_actuator(env)
        imposter = env.registry.async_get_or_create(
            "valve", "test", "rename-imposter", suggested_object_id="valve_1"
        )
        env.hass.states.async_set(
            ACTUATOR, "closed", {"supported_features": 3, "current_position": 0}
        )
        await settle(env.hass)
        assert not await env.hass.config_entries.async_reload(env.entry.entry_id)
        await settle(env.hass)
        assert identity_issue_ids(env)

        # Remove the competing identity: the durable UUID is unambiguous again.
        env.registry.async_remove(imposter.entity_id)
        env.hass.states.async_remove(ACTUATOR)
        await settle(env.hass)
        assert await env.hass.config_entries.async_reload(env.entry.entry_id)
        await settle(env.hass)

        assert env.entry.state is ConfigEntryState.LOADED
        after_record, _ = canonical(env)
        assert after_record.safety_record_id == before_record.safety_record_id
        assert after_record.identity_incident is None
        assert after_record.actuator_identity.last_known_entity_id == RENAMED
        assert identity_issue_ids(env) == []

    async def test_r7_missing_durable_identity_fails_closed(self, env) -> None:
        """R7: a removed Registry entry is never guessed from text."""
        before_record, _ = canonical(env)
        env.registry.async_remove(ACTUATOR)
        env.hass.states.async_remove(ACTUATOR)
        await settle(env.hass)

        assert not await env.hass.config_entries.async_reload(env.entry.entry_id)
        await settle(env.hass)

        assert env.entry.state is ConfigEntryState.SETUP_RETRY
        assert before_record.safety_record_id

    async def test_r8_rename_racing_reconciliation_publishes_the_latest_snapshot(self, env) -> None:
        """R8: the latest stable verified snapshot wins; identity is retained."""
        live = runtime(env)
        before_record, _ = canonical(env)
        subentry = env.entry.subentries[env.subentry_id]
        # Rename and reconfigure in the same event-loop turn.
        env.registry.async_update_entity(env.valve.entity_id, new_entity_id=RENAMED)
        env.valve.move_state_to(RENAMED)
        assert env.hass.config_entries.async_update_subentry(
            env.entry,
            subentry,
            data={**dict(subentry.data), "name": "Renamed bed"},
        )
        await settle(env.hass, cycles=30)

        live = runtime(env)
        after_record, _ = canonical(env)
        assert after_record.safety_record_id == before_record.safety_record_id
        assert after_record.actuator_identity.registry_entry_id == env.actuator_entry.id
        assert after_record.actuator_identity.last_known_entity_id == RENAMED
        assert after_record.applied_config is not None
        assert after_record.applied_config.normalized_settings.name == "Renamed bed"
        assert live.coordinator.observed_generation == live.coordinator.applied_generation
        assert not live.coordinator.dirty
        assert not live.coordinator.failed
        assert len(live.store.data.safety_records) == 1
        assert identity_issue_ids(env) == []

    async def test_r9_native_delete_after_rename_keeps_a_safe_tombstone(self, env) -> None:
        """R9: the tombstone keeps the exact UUID and the new addressing."""
        live = runtime(env)
        before_record, _ = canonical(env)
        await rename_actuator(env)

        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        await settle(env.hass, cycles=30)

        retained = live.store.data.safety_records[before_record.safety_record_id]
        assert retained.runtime_lifecycle in (
            RuntimeLifecycle.DELETE_PENDING,
            RuntimeLifecycle.RETIRED,
        )
        assert retained.active_subentry_id is None
        assert retained.safety_lineage_id == before_record.safety_lineage_id
        assert retained.actuator_identity.registry_entry_id == env.actuator_entry.id
        assert retained.actuator_identity.last_known_entity_id == RENAMED
        assert retained.identity_incident is None
        assert len(live.store.data.safety_records) == 1
        assert env.valve.on_calls == 0

    async def test_r10_rename_during_an_off_operation_keeps_one_off_path(self, env) -> None:
        """R10: one OFF operation; the confirmation is never lost."""
        live = runtime(env)
        controller = live.controllers[env.subentry_id]
        await controller.async_manual_start(600.0)
        await settle(env.hass)
        assert controller.state is ControllerState.WATERING
        env.valve.close_behavior = "silent"

        await controller.async_stop_watering()
        await settle(env.hass)
        off_calls_before_rename = env.valve.off_calls
        assert off_calls_before_rename >= 1
        assert controller.state is ControllerState.WATERING  # OFF still in flight

        await rename_actuator(env)
        assert controller.state is ControllerState.WATERING

        # Terminal OFF now arrives on the renamed entity.
        env.valve.close_behavior = "ack"
        env.valve.set_state("closed", 0)
        await settle(env.hass)

        assert controller.state is ControllerState.IDLE
        summary = controller.last_summary
        assert summary is not None
        assert summary.reason is CompletionReason.USER_STOP
        assert controller.session is None
        record, _ = canonical(env)
        assert BlockerReason.INTEGRATION_OFF_UNCONFIRMED not in record.blocker_reasons
        assert record.actuator_identity.last_known_entity_id == RENAMED
        assert env.valve.on_calls == 1  # exactly the one manual ON


class TestRenameVerificationFailsClosed:
    """Only an exact durable Registry UUID match may re-point addressing.

    SPEC 23.2 items 1-3 and 25.1.1: the entity ID is resolution metadata, so
    a rename candidate that does not resolve to the stored durable identity
    must leave runtime addressing untouched and fall through to ordinary
    fail-closed reconciliation (I33, I35).
    """

    async def test_rename_to_a_different_registry_identity_is_refused(self, env) -> None:
        live = runtime(env)
        controller = live.controllers[env.subentry_id]
        imposter = env.registry.async_get_or_create(
            "valve", "test", "rename-other", suggested_object_id="valve_other"
        )
        assert imposter.id != env.actuator_entry.id
        env.hass.states.async_set(
            imposter.entity_id, "closed", {"supported_features": 3, "current_position": 0}
        )
        await settle(env.hass)

        env.hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED,
            {
                "action": "update",
                "entity_id": imposter.entity_id,
                "old_entity_id": ACTUATOR,
                "changes": {},
            },
        )
        await settle(env.hass)

        assert controller.config.actuator == ACTUATOR
        record, _ = canonical(env)
        assert record.actuator_identity.last_known_entity_id == ACTUATOR
        assert record.actuator_identity.registry_entry_id == env.actuator_entry.id
        # The original entity is still the observed and commandable one.
        env.valve.set_state("open", 100)
        await settle(env.hass)
        assert controller.assessment.observed_on

    async def test_rename_without_durable_identity_is_refused(self, env) -> None:
        """A sensor with no Registry entry can never be re-pointed by text."""
        live = runtime(env)
        controller = live.controllers[env.subentry_id]
        _, history = canonical(env)
        assert history.zone_runtime.sensor_identity.registry_entry_id is None

        env.hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED,
            {
                "action": "update",
                "entity_id": "sensor.moisture_1_renamed",
                "old_entity_id": SENSOR,
                "changes": {},
            },
        )
        await settle(env.hass)

        assert controller.config.moisture_sensor == SENSOR
        _, history_after = canonical(env)
        assert history_after.zone_runtime.sensor_identity.last_known_entity_id == SENSOR

    async def test_verified_sensor_rename_is_tracked(self, env_registered_sensor) -> None:
        """SPEC 10.4: sensor renames follow the same registry-first rule."""
        env = env_registered_sensor
        live = runtime(env)
        controller = live.controllers[env.subentry_id]
        before_record, before_history = canonical(env)
        assert before_history.zone_runtime.sensor_identity.registry_entry_id == (
            env.sensor_entry.id
        )
        renamed_sensor = "sensor.moisture_1_renamed"

        env.registry.async_update_entity(SENSOR, new_entity_id=renamed_sensor)
        env.hass.states.async_set(renamed_sensor, "35")
        env.hass.states.async_remove(SENSOR)
        await settle(env.hass)

        assert controller.config.moisture_sensor == renamed_sensor
        after_record, after_history = canonical(env)
        assert after_record.safety_record_id == before_record.safety_record_id
        assert after_record.zone_history_id == before_history.zone_history_id
        assert after_history.zone_runtime.sensor_identity.registry_entry_id == env.sensor_entry.id
        assert after_history.zone_runtime.sensor_identity.last_known_entity_id == renamed_sensor
        assert identity_issue_ids(env) == []
        # Observation continues through the renamed sensor.
        env.hass.states.async_set(renamed_sensor, "22")
        await settle(env.hass)
        assert controller.observation.value == 22.0
        assert controller.active_fault is None
