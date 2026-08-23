"""Slice 9 tests: controller entry and zone subentry flows (§§9, 24.3, 29).

Runs the real HA 2025.9.0 flow machinery (HA1: the subentry helper's exact
signature is exercised). Skips cleanly in the pure environment.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

import pytest

pytest.importorskip("homeassistant")

from aiohttp import TCPConnector
from aiohttp.resolver import ThreadedResolver
from aiohttp.test_utils import TestClient, TestServer
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.moisture_loop.const import (
    CONF_RUNTIME_STORE_GENERATION_ID,
    CONF_RUNTIME_STORE_INITIALIZED,
    DOMAIN,
)
from custom_components.moisture_loop.models import (
    BlockerReason,
    CompletionReason,
    ControllerState,
    FaultCode,
    PersistedSession,
    PossibleFlowOwner,
    PulseDeadlineReached,
    RuntimeLifecycle,
    SessionContext,
    SessionMode,
)

SENSOR = "sensor.moisture_1"
SENSOR_2 = "sensor.moisture_2"
SWITCH = "switch.valve_1"
SWITCH_2 = "switch.valve_2"
VALVE = "valve.valve_1"

IDENTITY = {"name": "Front bed", "moisture_sensor": SENSOR, "actuator": SWITCH}
THRESHOLDS = {
    "start_threshold": 30.0,
    "target_threshold": 40.0,
    "pulse_duration": 300,
    "soak_duration": 1200,
}
LIMITS = {
    "max_cycles": 4,
    "max_session_runtime": 1800,
    "max_daily_runtime": 3600,
    "min_session_interval": 21600,
    "sensor_max_age": 7200,
    "actuator_confirm_timeout": 30,
    "manual_max_duration": 1800,
}
ZONE_DATA = {**IDENTITY, **THRESHOLDS, **LIMITS}


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations):
    return


@pytest.fixture
def entities(hass):
    hass.states.async_set(SENSOR, "33")
    hass.states.async_set(SENSOR_2, "44")
    hass.states.async_set(SWITCH, "off")
    hass.states.async_set(SWITCH_2, "off")
    hass.states.async_set(VALVE, "closed", {"supported_features": 3})


async def create_controller_entry(hass) -> MockConfigEntry:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    return entry


async def run_zone_add_flow(hass, entry, identity=None, thresholds=None, limits=None):
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"), context={"source": "user"}
    )
    if result["type"] is FlowResultType.FORM and result["step_id"] == "user":
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], identity if identity is not None else IDENTITY
        )
    if result["type"] is FlowResultType.FORM and result["step_id"] == "thresholds":
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], thresholds if thresholds is not None else THRESHOLDS
        )
    if result["type"] is FlowResultType.FORM and result["step_id"] == "limits":
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], limits if limits is not None else LIMITS
        )
    return result


async def native_delete_via_websocket(
    hass, hass_access_token: str, entry, subentry_id: str
) -> dict:
    """Exercise Core's unmodified 2025.9 subentry-delete websocket route."""
    assert await async_setup_component(hass, "websocket_api", {})
    assert await async_setup_component(hass, "config", {})
    connector = TCPConnector(
        loop=hass.loop,
        resolver=ThreadedResolver(loop=hass.loop),
    )
    server = TestServer(hass.http.app, loop=hass.loop)
    client = TestClient(server, loop=hass.loop, connector=connector)
    await client.start_server()
    try:
        websocket = await client.ws_connect("/api/websocket")
        assert (await websocket.receive_json())["type"] == "auth_required"
        await websocket.send_json({"type": "auth", "access_token": hass_access_token})
        assert (await websocket.receive_json())["type"] == "auth_ok"
        await websocket.send_json(
            {
                "id": 1,
                "type": "config_entries/subentries/delete",
                "entry_id": entry.entry_id,
                "subentry_id": subentry_id,
            }
        )
        return await websocket.receive_json()
    finally:
        await client.close()


class TestControllerEntryFlow:
    async def test_creates_single_entry_with_identity(self, hass) -> None:
        entry = await create_controller_entry(hass)
        assert entry.title == "Moisture Loop"
        generation = entry.data[CONF_RUNTIME_STORE_GENERATION_ID]
        assert isinstance(generation, str) and len(generation) == 36
        # The entry was created with initialized=false; real setup then ran
        # the §23.5 first-install transaction end-to-end and completed the
        # flag update only after the verified Store write.
        assert entry.data[CONF_RUNTIME_STORE_INITIALIZED] is True
        runtime = entry.runtime_data
        assert runtime.store.data.generation_id == generation
        assert runtime.store.data.store_revision >= 1
        assert len(entry.update_listeners) == 1  # Stage-3 entry reconciler (§5.1)

    async def test_second_entry_aborts(self, hass) -> None:
        await create_controller_entry(hass)
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "single_instance_allowed"

    async def test_generation_is_unique_per_entry(self, hass) -> None:
        entry = await create_controller_entry(hass)
        await hass.config_entries.async_remove(entry.entry_id)
        entry2 = await create_controller_entry(hass)
        assert (
            entry.data[CONF_RUNTIME_STORE_GENERATION_ID]
            != entry2.data[CONF_RUNTIME_STORE_GENERATION_ID]
        )


class TestZoneAddFlow:
    async def test_add_zone_has_no_flow_reload_and_reconciler_reloads_once(
        self, hass, entities
    ) -> None:
        entry = await create_controller_entry(hass)
        original_reload = hass.config_entries.async_reload
        with (
            patch.object(hass.config_entries, "async_schedule_reload") as flow_reload,
            patch.object(
                hass.config_entries, "async_reload", wraps=original_reload
            ) as reconcile_reload,
        ):
            result = await run_zone_add_flow(hass, entry)
            await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        flow_reload.assert_not_called()
        assert reconcile_reload.await_count == 1
        assert len(entry.subentries) == 1
        assert len(entry.update_listeners) == 1
        subentry = next(iter(entry.subentries.values()))
        assert subentry.subentry_type == "zone"
        assert subentry.title == "Front bed"
        data = dict(subentry.data)
        assert data["pulse_duration"] == 300
        assert isinstance(data["pulse_duration"], int)
        assert data["start_threshold"] == 30.0
        assert data["name"] == "Front bed"

    async def test_valve_actuator_with_features_is_accepted(self, hass, entities) -> None:
        entry = await create_controller_entry(hass)
        identity = {**IDENTITY, "actuator": VALVE}
        result = await run_zone_add_flow(hass, entry, identity=identity)
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY

    @pytest.mark.parametrize(
        ("identity", "field", "error"),
        [
            ({**IDENTITY, "name": ""}, "name", "invalid_name"),
            ({**IDENTITY, "name": "x" * 65}, "name", "invalid_name"),
            (
                {**IDENTITY, "moisture_sensor": "sensor.missing"},
                "moisture_sensor",
                "entity_not_found",
            ),
            (
                {**IDENTITY, "actuator": "switch.missing"},
                "actuator",
                "entity_not_found",
            ),
        ],
    )
    async def test_identity_errors(self, hass, entities, identity, field, error) -> None:
        entry = await create_controller_entry(hass)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "zone"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], identity)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {field: error}

    async def test_wrong_domain_rejected_by_backend(self, hass, entities) -> None:
        """Backend validation is authoritative even past the selector."""
        hass.states.async_set("light.lamp", "off")
        entry = await create_controller_entry(hass)
        flow = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "zone"), context={"source": "user"}
        )
        # Bypass frontend filtering by feeding a wrong-domain entity that
        # exists; the selector schema allows any entity_id string here.
        from custom_components.moisture_loop.config_flow import ZoneSubentryFlow

        handler = hass.config_entries.subentries._progress[flow["flow_id"]]
        assert isinstance(handler, ZoneSubentryFlow)
        errors = handler._validate_identity(
            {**IDENTITY, "actuator": "light.lamp"}, reconfigure_id=None
        )
        assert errors == {"actuator": "wrong_domain"}
        errors = handler._validate_identity(
            {**IDENTITY, "moisture_sensor": "light.lamp"}, reconfigure_id=None
        )
        assert errors == {"moisture_sensor": "wrong_domain"}

    async def test_position_only_valve_refused(self, hass, entities) -> None:
        hass.states.async_set("valve.position_only", "closed", {"supported_features": 4})
        entry = await create_controller_entry(hass)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "zone"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**IDENTITY, "actuator": "valve.position_only"}
        )
        assert result["errors"] == {"actuator": "valve_features_missing"}

    async def test_duplicate_name_and_actuator_refused(self, hass, entities) -> None:
        entry = await create_controller_entry(hass)
        await run_zone_add_flow(hass, entry)
        await hass.async_block_till_done()
        # Case-insensitively duplicate name.
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "zone"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"name": "FRONT BED", "moisture_sensor": SENSOR_2, "actuator": SWITCH_2},
        )
        assert result["errors"] == {"name": "duplicate_name"}
        # Duplicate actuator across zones.
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"name": "Back bed", "moisture_sensor": SENSOR_2, "actuator": SWITCH},
        )
        assert result["errors"] == {"actuator": "duplicate_actuator"}

    async def test_shared_sensor_is_warned_not_blocked(self, hass, entities) -> None:
        entry = await create_controller_entry(hass)
        await run_zone_add_flow(hass, entry)
        await hass.async_block_till_done()
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "zone"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"name": "Back bed", "moisture_sensor": SENSOR, "actuator": SWITCH_2},
        )
        assert result["type"] is FlowResultType.FORM  # not blocked
        assert result["step_id"] == "thresholds"
        assert "already used" in result["description_placeholders"]["shared_sensor_warning"]
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], THRESHOLDS)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], LIMITS)
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY

    async def test_strict_threshold_ordering(self, hass, entities) -> None:
        entry = await create_controller_entry(hass)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "zone"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], IDENTITY)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**THRESHOLDS, "start_threshold": 40.0}
        )
        assert result["errors"] == {"target_threshold": "target_not_above_start"}
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**THRESHOLDS, "start_threshold": 39.9}
        )
        assert result["step_id"] == "limits"

    async def test_selector_bounds_reject_out_of_range(self, hass, entities) -> None:
        entry = await create_controller_entry(hass)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "zone"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], IDENTITY)
        with pytest.raises(InvalidData):
            await hass.config_entries.subentries.async_configure(
                result["flow_id"], {**THRESHOLDS, "pulse_duration": 10}
            )

    async def test_backend_catches_cross_field_violations(self, hass, entities) -> None:
        """Session limit below pulse duration passes selectors but fails §9."""
        entry = await create_controller_entry(hass)
        result = await run_zone_add_flow(
            hass,
            entry,
            thresholds={**THRESHOLDS, "pulse_duration": 1800},
            limits={**LIMITS, "max_session_runtime": 900},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "limits"
        assert result["errors"] == {"base": "invalid_configuration"}

    async def test_active_duplicate_is_detected_by_registry_uuid_after_rename(
        self, hass, entities
    ) -> None:
        registry = er.async_get(hass)
        actuator_entry = registry.async_get_or_create(
            "switch", "test", "durable-active", suggested_object_id="durable_active"
        )
        hass.states.async_set(actuator_entry.entity_id, "off")
        entry = await create_controller_entry(hass)
        result = await run_zone_add_flow(
            hass, entry, identity={**IDENTITY, "actuator": actuator_entry.entity_id}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

        renamed = "switch.durable_active_renamed"
        registry.async_update_entity(actuator_entry.entity_id, new_entity_id=renamed)
        hass.states.async_set(renamed, "off")
        flow = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "zone"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(
            flow["flow_id"],
            {"name": "Other bed", "moisture_sensor": SENSOR_2, "actuator": renamed},
        )
        assert result["errors"] == {"actuator": "duplicate_actuator"}

    async def test_exact_retained_uuid_readd_is_accepted_and_reuses_record(
        self, hass, entities
    ) -> None:
        registry = er.async_get(hass)
        actuator_entry = registry.async_get_or_create(
            "switch", "test", "durable-readd", suggested_object_id="durable_readd"
        )
        hass.states.async_set(actuator_entry.entity_id, "off")
        entry = await create_controller_entry(hass)
        result = await run_zone_add_flow(
            hass, entry, identity={**IDENTITY, "actuator": actuator_entry.entity_id}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        runtime = entry.runtime_data
        old_subentry_id = next(iter(entry.subentries))
        old_record_id = runtime.bindings[old_subentry_id].safety_record_id

        assert hass.config_entries.async_remove_subentry(entry, old_subentry_id)
        await hass.async_block_till_done()
        assert runtime.store.data.safety_records[old_record_id].runtime_lifecycle is (
            RuntimeLifecycle.RETIRED
        )

        result = await run_zone_add_flow(
            hass,
            entry,
            identity={
                "name": "Re-added bed",
                "moisture_sensor": SENSOR_2,
                "actuator": actuator_entry.entity_id,
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        active_runtime = entry.runtime_data
        new_subentry_id = next(iter(entry.subentries))
        assert active_runtime.bindings[new_subentry_id].safety_record_id == old_record_id
        assert len(active_runtime.store.data.safety_records) == 1

    async def test_same_entity_id_different_uuid_conflicts_with_retained_record(
        self, hass, entities
    ) -> None:
        registry = er.async_get(hass)
        original = registry.async_get_or_create(
            "switch", "test", "durable-original", suggested_object_id="durable_reused"
        )
        entity_id = original.entity_id
        hass.states.async_set(entity_id, "off")
        entry = await create_controller_entry(hass)
        await run_zone_add_flow(hass, entry, identity={**IDENTITY, "actuator": entity_id})
        await hass.async_block_till_done()
        subentry_id = next(iter(entry.subentries))
        assert hass.config_entries.async_remove_subentry(entry, subentry_id)
        await hass.async_block_till_done()

        registry.async_remove(entity_id)
        hass.states.async_remove(entity_id)
        replacement = registry.async_get_or_create(
            "switch", "test", "durable-replacement", suggested_object_id="durable_reused"
        )
        assert replacement.entity_id == entity_id
        hass.states.async_set(entity_id, "off")
        flow = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "zone"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(
            flow["flow_id"],
            {"name": "Conflicting bed", "moisture_sensor": SENSOR_2, "actuator": entity_id},
        )
        assert result["errors"] == {"actuator": "actuator_identity_conflict"}


class TestZoneReconfigureFlow:
    async def make_entry_with_zone(self, hass) -> MockConfigEntry:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Moisture Loop",
            data={
                CONF_RUNTIME_STORE_GENERATION_ID: "gen-1",
                CONF_RUNTIME_STORE_INITIALIZED: True,
            },
            subentries_data=[
                ConfigSubentryData(
                    data=ZONE_DATA, subentry_type="zone", title="Front bed", unique_id=None
                )
            ],
        )
        entry.add_to_hass(hass)
        return entry

    async def start_reconfigure(self, hass, entry):
        subentry_id = next(iter(entry.subentries))
        return (
            subentry_id,
            await hass.config_entries.subentries.async_init(
                (entry.entry_id, "zone"),
                context={"source": "reconfigure", "subentry_id": subentry_id},
            ),
        )

    async def test_changed_data_prepares_updates_then_reconciler_reloads_once(
        self, hass, entities
    ) -> None:
        entry = await self.make_entry_with_zone(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        runtime = entry.runtime_data
        subentry_id, result = await self.start_reconfigure(hass, entry)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], IDENTITY)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**THRESHOLDS, "target_threshold": 45.0}
        )
        handler = hass.config_entries.subentries._progress[result["flow_id"]]
        original_helper = handler.async_update_and_abort
        original_reload = hass.config_entries.async_reload
        with (
            patch.object(
                runtime,
                "async_prepare_reconfigure",
                wraps=runtime.async_prepare_reconfigure,
            ) as prepare,
            patch.object(handler, "async_update_and_abort", wraps=original_helper) as helper,
            patch.object(hass.config_entries, "async_schedule_reload") as flow_reload,
            patch.object(
                hass.config_entries, "async_reload", wraps=original_reload
            ) as reconcile_reload,
        ):
            result = await hass.config_entries.subentries.async_configure(result["flow_id"], LIMITS)
            await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        prepare.assert_awaited_once_with(subentry_id)
        helper.assert_called_once()
        flow_reload.assert_not_called()
        assert reconcile_reload.await_count == 1
        assert entry.subentries[subentry_id].data["target_threshold"] == 45.0
        assert len(entry.update_listeners) == 1

    async def make_loaded_watering_valve(self, hass):
        registry = er.async_get(hass)
        actuator = registry.async_get_or_create(
            "valve", "test", "flow-active-valve", suggested_object_id="flow_active_valve"
        )
        calls = {"on": 0, "off": 0}

        async def open_valve(call) -> None:
            calls["on"] += 1
            hass.states.async_set(
                actuator.entity_id,
                "open",
                {"supported_features": 3},
                context=call.context,
            )

        async def close_valve(call) -> None:
            calls["off"] += 1
            hass.states.async_set(
                actuator.entity_id,
                "closed",
                {"supported_features": 3},
                context=call.context,
            )

        hass.services.async_register("valve", "open_valve", open_valve)
        hass.services.async_register("valve", "close_valve", close_valve)
        hass.states.async_set(actuator.entity_id, "closed", {"supported_features": 3})
        entry = await create_controller_entry(hass)
        await run_zone_add_flow(hass, entry, identity={**IDENTITY, "actuator": actuator.entity_id})
        await hass.async_block_till_done()
        hass.states.async_set(SENSOR, "20")
        runtime = entry.runtime_data
        subentry_id = next(iter(entry.subentries))
        for _ in range(20):
            await asyncio.sleep(0)
            if runtime.controllers[subentry_id].state is ControllerState.WATERING:
                break
        assert runtime.controllers[subentry_id].state is ControllerState.WATERING
        return entry, runtime, subentry_id, calls

    async def test_unchanged_submission_skips_termination_and_reload(self, hass, entities) -> None:
        entry = await self.make_entry_with_zone(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        runtime = entry.runtime_data
        _subentry_id, result = await self.start_reconfigure(hass, entry)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], IDENTITY)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], THRESHOLDS)
        handler = hass.config_entries.subentries._progress[result["flow_id"]]
        generation = runtime.coordinator.observed_generation
        with (
            patch.object(
                runtime,
                "async_prepare_reconfigure",
                wraps=runtime.async_prepare_reconfigure,
            ) as prepare,
            patch.object(
                handler,
                "async_update_and_abort",
                wraps=handler.async_update_and_abort,
            ) as helper,
            patch.object(hass.config_entries, "async_reload") as reload_entry,
        ):
            result = await hass.config_entries.subentries.async_configure(result["flow_id"], LIMITS)
            await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        prepare.assert_not_awaited()
        helper.assert_not_called()
        reload_entry.assert_not_awaited()
        assert runtime.coordinator.observed_generation == generation

    async def test_unchanged_while_watering_is_a_true_noop(self, hass, entities) -> None:
        entry, runtime, subentry_id, calls = await self.make_loaded_watering_valve(hass)
        controller = runtime.controllers[subentry_id]
        session_id = controller.session.session_id
        _, result = await self.start_reconfigure(hass, entry)
        current = dict(entry.subentries[subentry_id].data)
        identity = {key: current[key] for key in IDENTITY}
        thresholds = {key: current[key] for key in THRESHOLDS}
        limits = {key: current[key] for key in LIMITS}
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], identity)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], thresholds)
        handler = hass.config_entries.subentries._progress[result["flow_id"]]
        with (
            patch.object(runtime, "async_prepare_reconfigure") as prepare,
            patch.object(handler, "async_update_and_abort") as helper,
            patch.object(hass.config_entries, "async_reload") as reload_entry,
        ):
            result = await hass.config_entries.subentries.async_configure(result["flow_id"], limits)
            await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        prepare.assert_not_awaited()
        helper.assert_not_called()
        reload_entry.assert_not_awaited()
        assert controller.state is ControllerState.WATERING
        assert controller.session is not None and controller.session.session_id == session_id
        assert calls == {"on": 1, "off": 0}

    async def test_changed_while_watering_prepares_config_changed_before_mutation(
        self, hass, entities
    ) -> None:
        entry, _runtime, subentry_id, calls = await self.make_loaded_watering_valve(hass)
        _, result = await self.start_reconfigure(hass, entry)
        current = dict(entry.subentries[subentry_id].data)
        identity = {key: current[key] for key in IDENTITY}
        thresholds = {key: current[key] for key in THRESHOLDS}
        thresholds["target_threshold"] = 45.0
        limits = {key: current[key] for key in LIMITS}
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], identity)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], thresholds)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], limits)
        assert result["type"] is FlowResultType.ABORT
        await hass.async_block_till_done()
        applied = entry.runtime_data
        binding = applied.bindings[subentry_id]
        history = applied.store.data.zone_histories[binding.zone_history_id]
        assert history.zone_runtime.last_session_summary is not None
        assert history.zone_runtime.last_session_summary.reason is CompletionReason.CONFIG_CHANGED
        assert calls == {"on": 1, "off": 1}
        assert entry.subentries[subentry_id].data["target_threshold"] == 45.0

    async def test_reconfigure_without_loaded_runtime_still_updates(self, hass, entities) -> None:
        entry = await self.make_entry_with_zone(hass)
        subentry_id, result = await self.start_reconfigure(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**IDENTITY, "name": "Renamed bed"}
        )
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], THRESHOLDS)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], LIMITS)
        assert result["type"] is FlowResultType.ABORT
        assert entry.subentries[subentry_id].title == "Renamed bed"

    async def test_reconfigure_validates_like_add(self, hass, entities) -> None:
        entry = await self.make_entry_with_zone(hass)
        _, result = await self.start_reconfigure(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**IDENTITY, "moisture_sensor": "sensor.missing"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"moisture_sensor": "entity_not_found"}

    async def test_a_to_retained_b_is_accepted_and_reconciler_reuses_b(
        self, hass, entities
    ) -> None:
        registry = er.async_get(hass)
        actuator_a = registry.async_get_or_create(
            "switch", "test", "flow-actuator-a", suggested_object_id="flow_actuator_a"
        )
        actuator_b = registry.async_get_or_create(
            "switch", "test", "flow-actuator-b", suggested_object_id="flow_actuator_b"
        )
        hass.states.async_set(actuator_a.entity_id, "off")
        hass.states.async_set(actuator_b.entity_id, "off")
        entry = await create_controller_entry(hass)

        await run_zone_add_flow(
            hass,
            entry,
            identity={
                "name": "Retained B",
                "moisture_sensor": SENSOR_2,
                "actuator": actuator_b.entity_id,
            },
        )
        await hass.async_block_till_done()
        runtime = entry.runtime_data
        b_subentry_id = next(iter(entry.subentries))
        b_record_id = runtime.bindings[b_subentry_id].safety_record_id
        assert hass.config_entries.async_remove_subentry(entry, b_subentry_id)
        await hass.async_block_till_done()
        await runtime.store.async_reconcile(
            lambda data: (
                {
                    **data.safety_records,
                    b_record_id: data.safety_records[b_record_id].evolve(
                        runtime_lifecycle=RuntimeLifecycle.DELETE_PENDING,
                        blocker_reasons=(BlockerReason.INTEGRATION_OFF_UNCONFIRMED,),
                        possible_flow_owner=PossibleFlowOwner.INTEGRATION,
                        actuator_fault=FaultCode.ACTUATOR_OFF_TIMEOUT,
                        acknowledgement_required=True,
                    ),
                },
                dict(data.zone_histories),
            )
        )

        await run_zone_add_flow(
            hass, entry, identity={**IDENTITY, "actuator": actuator_a.entity_id}
        )
        await hass.async_block_till_done()
        runtime = entry.runtime_data
        a_subentry_id = next(iter(entry.subentries))
        a_history_id = runtime.bindings[a_subentry_id].zone_history_id

        _, result = await self.start_reconfigure(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**IDENTITY, "actuator": actuator_b.entity_id}
        )
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], THRESHOLDS)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], LIMITS)
        assert result["type"] is FlowResultType.ABORT
        await hass.async_block_till_done()

        applied = entry.runtime_data
        binding = applied.bindings[a_subentry_id]
        assert binding.safety_record_id == b_record_id
        assert binding.zone_history_id == a_history_id
        assert len(applied.store.data.safety_records) == 2
        retained_b = applied.store.data.safety_records[b_record_id]
        assert retained_b.blocker_reasons == (BlockerReason.INTEGRATION_OFF_UNCONFIRMED,)
        assert retained_b.actuator_fault is FaultCode.ACTUATOR_OFF_TIMEOUT
        assert retained_b.acknowledgement_required
        assert binding.controller.state is ControllerState.FAULT

    @pytest.mark.parametrize(
        ("current_sensor_state", "expected_fault"),
        [
            ("44", None),
            ("unavailable", FaultCode.SENSOR_UNAVAILABLE),
            ("not-a-number", FaultCode.SENSOR_INVALID),
        ],
    )
    async def test_ar12_ar13_ar16_retained_b_operational_state_never_overrides_current_zone(
        self, hass, entities, current_sensor_state, expected_fault
    ) -> None:
        registry = er.async_get(hass)
        actuator_a = registry.async_get_or_create(
            "switch", "test", "operational-a", suggested_object_id="operational_a"
        )
        actuator_b = registry.async_get_or_create(
            "switch", "test", "operational-b", suggested_object_id="operational_b"
        )
        hass.states.async_set(actuator_a.entity_id, "off")
        hass.states.async_set(actuator_b.entity_id, "off")
        entry = await create_controller_entry(hass)

        await run_zone_add_flow(
            hass,
            entry,
            identity={
                "name": "Historical B",
                "moisture_sensor": SENSOR_2,
                "actuator": actuator_b.entity_id,
            },
        )
        await hass.async_block_till_done()
        runtime = entry.runtime_data
        b_subentry_id = next(iter(entry.subentries))
        b_record_id = runtime.bindings[b_subentry_id].safety_record_id
        await runtime.controllers[b_subentry_id].async_set_enabled(False)
        assert hass.config_entries.async_remove_subentry(entry, b_subentry_id)
        await hass.async_block_till_done()

        b_record = runtime.store.data.safety_records[b_record_id]
        b_history = runtime.store.data.zone_histories[b_record.zone_history_id]
        await runtime.store.async_reconcile(
            lambda data: (
                dict(data.safety_records),
                {
                    **data.zone_histories,
                    b_history.zone_history_id: b_history.evolve(
                        zone_runtime=replace(
                            b_history.zone_runtime,
                            enabled=False,
                            state=ControllerState.FAULT,
                            zone_fault=FaultCode.SENSOR_STALE,
                        )
                    ),
                },
            )
        )

        hass.states.async_set(SENSOR, current_sensor_state)
        await run_zone_add_flow(
            hass, entry, identity={**IDENTITY, "actuator": actuator_a.entity_id}
        )
        await hass.async_block_till_done()
        runtime = entry.runtime_data
        a_subentry_id = next(iter(entry.subentries))
        a_history_id = runtime.bindings[a_subentry_id].zone_history_id
        assert runtime.controllers[a_subentry_id].enabled

        _, result = await self.start_reconfigure(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**IDENTITY, "actuator": actuator_b.entity_id}
        )
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], THRESHOLDS)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], LIMITS)
        assert result["type"] is FlowResultType.ABORT
        await hass.async_block_till_done()

        runtime = entry.runtime_data
        binding = runtime.bindings[a_subentry_id]
        assert binding.safety_record_id == b_record_id
        assert binding.zone_history_id == a_history_id
        controller = binding.controller
        assert controller.enabled
        assert controller.session is None
        assert controller.active_fault is expected_fault
        assert controller.state is (
            ControllerState.IDLE if expected_fault is None else ControllerState.FAULT
        )
        history = runtime.store.data.zone_histories[a_history_id]
        assert history.zone_runtime.enabled
        assert history.zone_runtime.zone_fault is expected_fault
        assert history.zone_runtime.sensor_identity.last_known_entity_id == SENSOR

    async def test_ar15_retained_b_watering_is_closed_and_never_adopted_as_current_session(
        self, hass, entities
    ) -> None:
        registry = er.async_get(hass)
        actuator_a = registry.async_get_or_create(
            "switch", "test", "session-a", suggested_object_id="session_a"
        )
        actuator_b = registry.async_get_or_create(
            "switch", "test", "session-b", suggested_object_id="session_b"
        )
        hass.states.async_set(actuator_a.entity_id, "off")
        hass.states.async_set(actuator_b.entity_id, "off")
        entry = await create_controller_entry(hass)
        await run_zone_add_flow(
            hass,
            entry,
            identity={
                "name": "Historical session B",
                "moisture_sensor": SENSOR_2,
                "actuator": actuator_b.entity_id,
            },
        )
        await hass.async_block_till_done()
        runtime = entry.runtime_data
        b_subentry_id = next(iter(entry.subentries))
        b_record_id = runtime.bindings[b_subentry_id].safety_record_id
        assert hass.config_entries.async_remove_subentry(entry, b_subentry_id)
        await hass.async_block_till_done()
        await run_zone_add_flow(
            hass, entry, identity={**IDENTITY, "actuator": actuator_a.entity_id}
        )
        await hass.async_block_till_done()
        runtime = entry.runtime_data
        a_subentry_id = next(iter(entry.subentries))
        a_history_id = runtime.bindings[a_subentry_id].zone_history_id
        b_record = runtime.store.data.safety_records[b_record_id]
        b_history = runtime.store.data.zone_histories[b_record.zone_history_id]
        instant = hass.states.get(SENSOR).last_reported
        session = SessionContext(
            session_id="retained-b-open-session",
            owner_run_id="crashed-run",
            config_fingerprint=b_record.applied_config.config_fingerprint,
            mode=SessionMode.AUTO,
            started_at_utc=instant - timedelta(minutes=3),
            cycle=1,
            session_runtime_s=0.0,
            pulse_intent_at_utc=instant - timedelta(minutes=2),
            pulse_commanded_at_utc=instant - timedelta(minutes=2),
            pulse_confirmed_at_utc=instant - timedelta(minutes=2),
            pulse_ends_at_utc=instant + timedelta(minutes=3),
            moisture_at_start=20.0,
        )
        await runtime.store.async_reconcile(
            lambda data: (
                {
                    **data.safety_records,
                    b_record_id: data.safety_records[b_record_id].evolve(
                        runtime_lifecycle=RuntimeLifecycle.DELETE_PENDING,
                        blocker_reasons=(BlockerReason.INTEGRATION_OFF_UNCONFIRMED,),
                        possible_flow_owner=PossibleFlowOwner.INTEGRATION,
                    ),
                },
                {
                    **data.zone_histories,
                    b_history.zone_history_id: b_history.evolve(
                        zone_runtime=replace(
                            b_history.zone_runtime,
                            state=ControllerState.WATERING,
                            session=PersistedSession(b_record_id, session),
                        )
                    ),
                },
            )
        )

        _, result = await self.start_reconfigure(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**IDENTITY, "actuator": actuator_b.entity_id}
        )
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], THRESHOLDS)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], LIMITS)
        assert result["type"] is FlowResultType.ABORT
        await hass.async_block_till_done()

        runtime = entry.runtime_data
        binding = runtime.bindings[a_subentry_id]
        assert binding.safety_record_id == b_record_id
        assert binding.zone_history_id == a_history_id
        assert binding.controller.session is None
        assert binding.controller.state is ControllerState.IDLE
        merged = runtime.store.data.zone_histories[a_history_id]
        assert merged.zone_runtime.session is None
        assert merged.daily is not None and merged.daily.runtime_s > 0
        assert b_history.zone_history_id not in runtime.store.data.zone_histories

    async def test_same_uuid_entity_rename_reconfigures_without_false_conflict(
        self, hass, entities
    ) -> None:
        registry = er.async_get(hass)
        actuator = registry.async_get_or_create(
            "switch", "test", "flow-rename", suggested_object_id="flow_rename"
        )
        hass.states.async_set(actuator.entity_id, "off")
        entry = await create_controller_entry(hass)
        await run_zone_add_flow(hass, entry, identity={**IDENTITY, "actuator": actuator.entity_id})
        await hass.async_block_till_done()
        runtime = entry.runtime_data
        subentry_id = next(iter(entry.subentries))
        record_id = runtime.bindings[subentry_id].safety_record_id

        renamed = "switch.flow_rename_new"
        registry.async_update_entity(actuator.entity_id, new_entity_id=renamed)
        hass.states.async_set(renamed, "off")
        _, result = await self.start_reconfigure(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**IDENTITY, "actuator": renamed}
        )
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], THRESHOLDS)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], LIMITS)
        assert result["type"] is FlowResultType.ABORT
        await hass.async_block_till_done()
        applied = entry.runtime_data
        assert applied.bindings[subentry_id].safety_record_id == record_id
        identity = applied.store.data.safety_records[record_id].actuator_identity
        assert identity.last_known_entity_id == renamed

    async def test_a_to_b_identity_conflict_is_refused_before_core_mutation(
        self, hass, entities
    ) -> None:
        registry = er.async_get(hass)
        actuator_a = registry.async_get_or_create(
            "switch", "test", "flow-conflict-a", suggested_object_id="flow_conflict_a"
        )
        retained_b = registry.async_get_or_create(
            "switch", "test", "flow-conflict-b", suggested_object_id="flow_conflict_b"
        )
        reused_entity_id = retained_b.entity_id
        hass.states.async_set(actuator_a.entity_id, "off")
        hass.states.async_set(reused_entity_id, "off")
        entry = await create_controller_entry(hass)
        await run_zone_add_flow(
            hass,
            entry,
            identity={
                "name": "Old B",
                "moisture_sensor": SENSOR_2,
                "actuator": reused_entity_id,
            },
        )
        await hass.async_block_till_done()
        b_subentry_id = next(iter(entry.subentries))
        assert hass.config_entries.async_remove_subentry(entry, b_subentry_id)
        await hass.async_block_till_done()
        registry.async_remove(reused_entity_id)
        hass.states.async_remove(reused_entity_id)
        replacement = registry.async_get_or_create(
            "switch",
            "test",
            "flow-conflict-b-replacement",
            suggested_object_id=reused_entity_id.split(".", 1)[1],
        )
        assert replacement.entity_id == reused_entity_id
        hass.states.async_set(reused_entity_id, "off")

        await run_zone_add_flow(
            hass, entry, identity={**IDENTITY, "actuator": actuator_a.entity_id}
        )
        await hass.async_block_till_done()
        runtime = entry.runtime_data
        a_subentry_id = next(iter(entry.subentries))
        original_data = dict(entry.subentries[a_subentry_id].data)
        records_before = set(runtime.store.data.safety_records)

        _, result = await self.start_reconfigure(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**IDENTITY, "actuator": reused_entity_id}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"actuator": "actuator_identity_conflict"}
        assert dict(entry.subentries[a_subentry_id].data) == original_data
        assert set(runtime.store.data.safety_records) == records_before
        assert runtime.slots.snapshot().admission_open


class TestNativeSubentryDeletion:
    async def test_rapid_two_zone_native_deletion_materializes_both_without_reload(
        self, hass, entities, hass_access_token, socket_enabled
    ) -> None:
        registry = er.async_get(hass)
        actuator_a = registry.async_get_or_create(
            "switch", "test", "native-delete-a", suggested_object_id="native_delete_a"
        )
        actuator_b = registry.async_get_or_create(
            "switch", "test", "native-delete-b", suggested_object_id="native_delete_b"
        )
        hass.states.async_set(actuator_a.entity_id, "off")
        hass.states.async_set(actuator_b.entity_id, "off")
        entry = await create_controller_entry(hass)
        await run_zone_add_flow(
            hass, entry, identity={**IDENTITY, "actuator": actuator_a.entity_id}
        )
        await hass.async_block_till_done()
        await run_zone_add_flow(
            hass,
            entry,
            identity={
                "name": "Second bed",
                "moisture_sensor": SENSOR_2,
                "actuator": actuator_b.entity_id,
            },
        )
        await hass.async_block_till_done()
        runtime = entry.runtime_data
        record_ids = {binding.safety_record_id for binding in runtime.bindings.values()}
        subentry_ids = tuple(entry.subentries)
        assert len(record_ids) == len(subentry_ids) == 2

        with patch.object(hass.config_entries, "async_reload") as reload_entry:
            for subentry_id in subentry_ids:
                response = await native_delete_via_websocket(
                    hass, hass_access_token, entry, subentry_id
                )
                assert response["success"]
            assert entry.subentries == {}
            await hass.async_block_till_done()

        reload_entry.assert_not_awaited()
        assert runtime.controllers == {}
        assert record_ids <= set(runtime.store.data.safety_records)
        assert all(
            runtime.store.data.safety_records[record_id].runtime_lifecycle
            is RuntimeLifecycle.RETIRED
            for record_id in record_ids
        )

    async def test_idle_delete_uses_real_websocket_path_without_reload_and_keeps_safety_record(
        self, hass, entities, hass_access_token, socket_enabled
    ) -> None:
        registry = er.async_get(hass)
        actuator = registry.async_get_or_create(
            "switch", "test", "native-delete-actuator", suggested_object_id="native_delete"
        )
        hass.states.async_set(actuator.entity_id, "off")
        entry = await create_controller_entry(hass)
        await run_zone_add_flow(hass, entry, identity={**IDENTITY, "actuator": actuator.entity_id})
        await hass.async_block_till_done()
        runtime = entry.runtime_data
        subentry_id = next(iter(entry.subentries))
        record_id = runtime.bindings[subentry_id].safety_record_id
        generation = runtime.coordinator.observed_generation

        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        device = device_registry.async_get_device(identifiers={(DOMAIN, subentry_id)})
        assert device is not None
        attributed = [
            entity
            for entity in entity_registry.entities.values()
            if entity.config_subentry_id == subentry_id
        ]
        assert attributed

        with patch.object(hass.config_entries, "async_reload") as reload_entry:
            response = await native_delete_via_websocket(
                hass, hass_access_token, entry, subentry_id
            )
            assert response["success"]
            # Core mutation is already visible when websocket success returns.
            assert subentry_id not in entry.subentries
            await hass.async_block_till_done()

        reload_entry.assert_not_awaited()
        assert runtime.coordinator.observed_generation > generation
        assert not runtime.coordinator.reload_pending
        assert runtime.controllers == {}
        retained = runtime.store.data.safety_records[record_id]
        assert retained.runtime_lifecycle is RuntimeLifecycle.RETIRED
        assert device_registry.async_get(device.id) is None
        assert all(
            entity.config_subentry_id != subentry_id for entity in entity_registry.entities.values()
        )
        assert not hasattr(runtime, "async_prepare_delete")

    async def test_watering_auto_native_delete_closes_flow_and_final_gate(
        self, hass, entities, hass_access_token, socket_enabled
    ) -> None:
        (
            entry,
            runtime,
            subentry_id,
            calls,
        ) = await TestZoneReconfigureFlow().make_loaded_watering_valve(hass)
        controller = runtime.controllers[subentry_id]
        record_id = runtime.bindings[subentry_id].safety_record_id
        with patch.object(hass.config_entries, "async_reload") as reload_entry:
            response = await native_delete_via_websocket(
                hass, hass_access_token, entry, subentry_id
            )
            assert response["success"]
            assert subentry_id not in entry.subentries

            # Membership is the immediate Stage-4 authority even before the
            # asynchronously scheduled listener/reconciler finishes.
            denied = runtime.authorize_on(controller, "deleted-session", "deleted-attempt")
            assert not denied.authorized
            await hass.async_block_till_done()

        reload_entry.assert_not_awaited()
        assert calls == {"on": 1, "off": 1}
        assert not controller.runtime_eligible
        assert runtime.controllers == {}
        retained = runtime.store.data.safety_records[record_id]
        assert retained.runtime_lifecycle is RuntimeLifecycle.RETIRED
        history = runtime.store.data.zone_histories[retained.zone_history_id]
        assert history.zone_runtime.last_session_summary is not None
        assert history.zone_runtime.last_session_summary.reason is CompletionReason.CONFIG_CHANGED

    async def test_watering_manual_native_delete_uses_one_off_and_never_resumes(
        self, hass, entities, hass_access_token, socket_enabled
    ) -> None:
        (
            entry,
            runtime,
            subentry_id,
            calls,
        ) = await TestZoneReconfigureFlow().make_loaded_watering_valve(hass)
        controller = runtime.controllers[subentry_id]
        await hass.async_block_till_done()
        await controller.async_stop_watering()
        await hass.async_block_till_done()
        assert controller.state is ControllerState.IDLE
        decision = await controller.async_manual_start(120)
        assert decision.guard_result is not None
        assert decision.guard_result.failed_guards == ("G-SLOT",)
        await hass.async_block_till_done()
        assert controller.session is not None
        assert controller.session.mode is SessionMode.MANUAL
        assert controller.state is ControllerState.WATERING
        # The session owner is a deliberate HA background task.  Current HA
        # no longer includes that task in async_block_till_done(), so wait for
        # the simulated actuator acknowledgement instead of relying on the
        # harness scheduler's task-draining policy.
        for _ in range(40):
            if controller.session.pulse_confirmed_at_utc is not None:
                break
            await asyncio.sleep(0)
        assert controller.session.pulse_confirmed_at_utc is not None
        before_on = calls["on"]
        before_off = calls["off"]

        response = await native_delete_via_websocket(hass, hass_access_token, entry, subentry_id)
        assert response["success"]
        assert subentry_id not in entry.subentries
        await hass.async_block_till_done()

        assert calls == {"on": before_on, "off": before_off + 1}
        assert runtime.controllers == {}
        record = runtime.store.data.safety_records[controller.safety_record_id]
        history = runtime.store.data.zone_histories[record.zone_history_id]
        assert record.runtime_lifecycle is RuntimeLifecycle.RETIRED
        assert history.zone_runtime.session is None
        assert history.zone_runtime.last_session_summary is not None
        assert history.zone_runtime.last_session_summary.reason is CompletionReason.CONFIG_CHANGED

    async def test_soaking_native_delete_revokes_later_pulse_without_extra_off(
        self, hass, entities, hass_access_token, socket_enabled
    ) -> None:
        (
            entry,
            runtime,
            subentry_id,
            calls,
        ) = await TestZoneReconfigureFlow().make_loaded_watering_valve(hass)
        controller = runtime.controllers[subentry_id]
        await hass.async_block_till_done()
        decision = await controller.async_dispatch(PulseDeadlineReached())
        assert not decision.no_op
        await hass.async_block_till_done()
        assert controller.state is ControllerState.SOAKING
        before = dict(calls)

        response = await native_delete_via_websocket(hass, hass_access_token, entry, subentry_id)
        assert response["success"]
        assert subentry_id not in entry.subentries
        await hass.async_block_till_done()

        assert calls == before
        assert runtime.controllers == {}
        record = runtime.store.data.safety_records[controller.safety_record_id]
        history = runtime.store.data.zone_histories[record.zone_history_id]
        assert record.runtime_lifecycle is RuntimeLifecycle.RETIRED
        assert history.zone_runtime.session is None
        assert history.zone_runtime.last_session_summary is not None
        assert history.zone_runtime.last_session_summary.reason is CompletionReason.CONFIG_CHANGED


class TestFlowReconciliationBursts:
    async def test_add_reconfigure_delete_before_first_application_latest_empty_wins(
        self, hass, entities
    ) -> None:
        entry = await create_controller_entry(hass)
        runtime = entry.runtime_data
        original_apply = runtime.coordinator._snapshot_applier
        started = asyncio.Event()
        release = asyncio.Event()
        first_update_generation = runtime.coordinator.observed_generation + 1

        async def gated_apply(snapshot, is_current) -> None:
            if snapshot.observed_generation == first_update_generation:
                started.set()
                await release.wait()
            await original_apply(snapshot, is_current)

        runtime.coordinator._snapshot_applier = gated_apply
        with patch.object(hass.config_entries, "async_reload") as reload_entry:
            add_result = await run_zone_add_flow(hass, entry)
            assert add_result["type"] is FlowResultType.CREATE_ENTRY
            await started.wait()
            subentry_id = next(iter(entry.subentries))

            result = await hass.config_entries.subentries.async_init(
                (entry.entry_id, "zone"),
                context={"source": "reconfigure", "subentry_id": subentry_id},
            )
            result = await hass.config_entries.subentries.async_configure(
                result["flow_id"], {**IDENTITY, "name": "Transient rename"}
            )
            result = await hass.config_entries.subentries.async_configure(
                result["flow_id"], THRESHOLDS
            )
            result = await hass.config_entries.subentries.async_configure(result["flow_id"], LIMITS)
            assert result["type"] is FlowResultType.ABORT
            assert hass.config_entries.async_remove_subentry(entry, subentry_id)
            release.set()
            await hass.async_block_till_done()

        reload_entry.assert_not_awaited()
        assert entry.subentries == {}
        assert runtime.coordinator.applied_snapshot is not None
        assert runtime.coordinator.applied_snapshot.zones == ()
        assert runtime.coordinator.superseded_count >= 1
        assert runtime.store.data.safety_records == {}
        assert runtime.slots.snapshot().admission_open


class TestFlowEdges:
    async def test_direct_second_user_step_aborts(self, hass) -> None:
        """Defense-in-depth abort inside the step itself."""
        from custom_components.moisture_loop.config_flow import MoistureLoopConfigFlow

        await create_controller_entry(hass)
        flow = MoistureLoopConfigFlow()
        flow.hass = hass
        result = await flow.async_step_user(None)
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "single_instance_allowed"

    async def test_reconfigure_threshold_and_limit_errors(self, hass, entities) -> None:
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_RUNTIME_STORE_GENERATION_ID: "gen-1",
                CONF_RUNTIME_STORE_INITIALIZED: True,
            },
            subentries_data=[
                ConfigSubentryData(
                    data=ZONE_DATA, subentry_type="zone", title="Front bed", unique_id=None
                )
            ],
        )
        entry.add_to_hass(hass)
        subentry_id = next(iter(entry.subentries))
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "zone"),
            context={"source": "reconfigure", "subentry_id": subentry_id},
        )
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], IDENTITY)
        # Threshold ordering error in the reconfigure flow.
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**THRESHOLDS, "start_threshold": 50.0}
        )
        assert result["step_id"] == "reconfigure_thresholds"
        assert result["errors"] == {"target_threshold": "target_not_above_start"}
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**THRESHOLDS, "pulse_duration": 1800}
        )
        assert result["step_id"] == "reconfigure_limits"
        # Cross-field violation caught by the backend in reconfigure too.
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**LIMITS, "max_session_runtime": 900}
        )
        assert result["step_id"] == "reconfigure_limits"
        assert result["errors"] == {"base": "invalid_configuration"}

    async def test_validate_full_short_circuits_on_identity_error(self, hass, entities) -> None:
        from custom_components.moisture_loop.config_flow import ZoneSubentryFlow

        entry = await create_controller_entry(hass)
        flow = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "zone"), context={"source": "user"}
        )
        handler = hass.config_entries.subentries._progress[flow["flow_id"]]
        assert isinstance(handler, ZoneSubentryFlow)
        errors = handler._validate_full({**ZONE_DATA, "name": ""}, reconfigure_id=None)
        assert errors == {"name": "invalid_name"}
