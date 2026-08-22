"""Slice 9 tests: controller entry and zone subentry flows (§§9, 24.3, 29).

Runs the real HA 2025.9.0 flow machinery (HA1: the subentry helper's exact
signature is exercised). Skips cleanly in the pure environment.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("homeassistant")

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.moisture_loop.const import (
    CONF_RUNTIME_STORE_GENERATION_ID,
    CONF_RUNTIME_STORE_INITIALIZED,
    DOMAIN,
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
    async def test_add_zone_creates_subentry_and_schedules_one_reload(self, hass, entities) -> None:
        entry = await create_controller_entry(hass)
        with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
            result = await run_zone_add_flow(hass, entry)
            # The reload is deferred with call_soon so the flow manager
            # attaches the subentry first; drain the loop inside the patch.
            await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert schedule_reload.call_count == 1
        assert len(entry.subentries) == 1
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
        with patch.object(hass.config_entries, "async_schedule_reload"):
            result = await run_zone_add_flow(hass, entry, identity=identity)
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
        with patch.object(hass.config_entries, "async_schedule_reload"):
            await run_zone_add_flow(hass, entry)
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
        with patch.object(hass.config_entries, "async_schedule_reload"):
            await run_zone_add_flow(hass, entry)
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
            result = await hass.config_entries.subentries.async_configure(
                result["flow_id"], THRESHOLDS
            )
            result = await hass.config_entries.subentries.async_configure(result["flow_id"], LIMITS)
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

    async def test_changed_data_prepares_then_reloads_once(self, hass, entities) -> None:
        entry = await self.make_entry_with_zone(hass)
        runtime = MagicMock()
        runtime.async_prepare_reconfigure = AsyncMock()
        entry.runtime_data = runtime
        subentry_id, result = await self.start_reconfigure(hass, entry)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], IDENTITY)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**THRESHOLDS, "target_threshold": 45.0}
        )
        with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
            result = await hass.config_entries.subentries.async_configure(result["flow_id"], LIMITS)
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        # §24.3: safety preparation before the data update; one reload.
        runtime.async_prepare_reconfigure.assert_awaited_once_with(subentry_id)
        assert schedule_reload.call_count == 1
        assert entry.subentries[subentry_id].data["target_threshold"] == 45.0
        assert entry.update_listeners == []

    async def test_unchanged_submission_skips_termination_and_reload(self, hass, entities) -> None:
        entry = await self.make_entry_with_zone(hass)
        runtime = MagicMock()
        runtime.async_prepare_reconfigure = AsyncMock()
        entry.runtime_data = runtime
        _subentry_id, result = await self.start_reconfigure(hass, entry)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], IDENTITY)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], THRESHOLDS)
        with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
            result = await hass.config_entries.subentries.async_configure(result["flow_id"], LIMITS)
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        # Unchanged data: no unnecessary pre-termination, no reload (§24.3,
        # reload_even_if_entry_is_unchanged=False).
        runtime.async_prepare_reconfigure.assert_not_awaited()
        schedule_reload.assert_not_called()

    async def test_reconfigure_without_loaded_runtime_still_updates(self, hass, entities) -> None:
        entry = await self.make_entry_with_zone(hass)
        subentry_id, result = await self.start_reconfigure(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**IDENTITY, "name": "Renamed bed"}
        )
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], THRESHOLDS)
        with patch.object(hass.config_entries, "async_schedule_reload"):
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
