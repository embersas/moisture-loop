"""Slice 10 tests: per-zone entities (SPECIFICATION.md §28).

End-to-end through the real config flow, real setup, and real platforms on
HA 2025.9.0. Skips cleanly in the pure environment.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("homeassistant")

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.moisture_loop.const import DOMAIN

SENSOR = "sensor.moisture_1"
ACTUATOR = "valve.valve_1"

IDENTITY = {"name": "Front bed", "moisture_sensor": SENSOR, "actuator": ACTUATOR}
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
    "min_session_interval": 900,
    "sensor_max_age": 7200,
    "actuator_confirm_timeout": 30,
    "manual_max_duration": 1800,
}


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations):
    return


class ScriptedValve:
    """Scripted valve actuator: the valve component is never loaded by the
    integration, so these service doubles are not shadowed by a real
    platform (unlike domain switch, whose services the forwarded enabled
    switch platform registers)."""

    def __init__(self, hass) -> None:
        self.hass = hass
        self.on_calls = 0
        self.off_calls = 0
        hass.states.async_set(ACTUATOR, "closed", {"supported_features": 3, "current_position": 0})

        async def open_valve(call) -> None:
            self.on_calls += 1
            hass.states.async_set(
                ACTUATOR, "open", {"supported_features": 3, "current_position": 100}
            )

        async def close_valve(call) -> None:
            self.off_calls += 1
            hass.states.async_set(
                ACTUATOR, "closed", {"supported_features": 3, "current_position": 0}
            )

        hass.services.async_register("valve", "open_valve", open_valve)
        hass.services.async_register("valve", "close_valve", close_valve)

    def set_state(self, state: str, position: int | None = None) -> None:
        attrs = {"supported_features": 3}
        if position is not None:
            attrs["current_position"] = position
        self.hass.states.async_set(ACTUATOR, state, attrs)


async def settle(hass, cycles: int = 12) -> None:
    import asyncio

    for _ in range(cycles):
        await asyncio.sleep(0)
        await hass.async_block_till_done()


async def setup_with_zone(hass) -> tuple:
    """Create the controller and one zone through the real flows."""
    assert await async_setup_component(hass, DOMAIN, {})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    entry = result["result"]
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], IDENTITY)
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], THRESHOLDS)
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], LIMITS)
    await settle(hass)  # the scheduled reload picks up the new zone
    subentry_id = next(iter(entry.subentries))
    return entry, subentry_id


def entity_id(hass, platform: str, unique_id: str) -> str:
    registry = er.async_get(hass)
    found = registry.async_get_entity_id(platform, DOMAIN, unique_id)
    assert found is not None, f"missing entity {platform}/{unique_id}"
    return found


@pytest.fixture
async def env(hass, freezer):
    freezer.move_to("2026-08-21 12:00:00+00:00")
    switch = ScriptedValve(hass)
    hass.states.async_set(SENSOR, "33")
    await hass.async_block_till_done()
    entry, subentry_id = await setup_with_zone(hass)
    from types import SimpleNamespace

    yield SimpleNamespace(
        hass=hass,
        freezer=freezer,
        switch=switch,
        entry=entry,
        subentry_id=subentry_id,
        runtime=entry.runtime_data,
    )


async def advance(e, seconds: float) -> None:
    e.freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(e.hass, dt_util.utcnow())
    await settle(e.hass)


async def set_moisture(e, value: str) -> None:
    e.hass.states.async_set(SENSOR, value)
    await settle(e.hass)


class TestEntityCreationAndAttribution:
    async def test_all_entities_exist_with_stable_unique_ids(self, env) -> None:
        sid = env.subentry_id
        expected = {
            "sensor": ["status", "watering_runtime_today", "last_session", "next_eligible"],
            "binary_sensor": ["watering", "problem", "needs_water"],
            "switch": ["enabled"],
            "button": ["stop", "evaluate_now", "clear_fault"],
        }
        for platform, keys in expected.items():
            for key in keys:
                eid = entity_id(env.hass, platform, f"{sid}_{key}")
                assert env.hass.states.get(eid) is not None, eid

    async def test_zone_device_and_subentry_attribution(self, env) -> None:
        device_registry = dr.async_get(env.hass)
        device = device_registry.async_get_device({(DOMAIN, env.subentry_id)})
        assert device is not None
        assert device.name == "Front bed"
        assert env.entry.entry_id in device.config_entries
        # Device and entities are attributed to the zone subentry.
        assert device.config_entries_subentries[env.entry.entry_id] == {env.subentry_id}
        registry = er.async_get(env.hass)
        status = registry.async_get(entity_id(env.hass, "sensor", f"{env.subentry_id}_status"))
        assert status is not None
        assert status.config_subentry_id == env.subentry_id
        assert status.device_id == device.id


class TestSensorEntities:
    async def test_status_and_attributes(self, env) -> None:
        eid = entity_id(env.hass, "sensor", f"{env.subentry_id}_status")
        state = env.hass.states.get(eid)
        assert state.state == "idle"
        assert state.attributes["moisture"] == 33.0
        assert state.attributes["moisture_classification"] == "valid"
        assert state.attributes["active_fault"] is None
        assert state.attributes["external_actuator_on"] is False
        assert state.attributes["water_resource_blockers"] == []

    async def test_status_reflects_watering_session(self, env) -> None:
        await set_moisture(env, "20")
        eid = entity_id(env.hass, "sensor", f"{env.subentry_id}_status")
        state = env.hass.states.get(eid)
        assert state.state == "watering"
        assert state.attributes["mode"] == "auto"
        assert state.attributes["cycle"] == 1
        assert state.attributes["sensor_fresh_until_utc"] is not None

    async def test_runtime_today_and_last_session(self, env) -> None:
        await set_moisture(env, "20")
        await advance(env, 300)  # pulse ends -> SOAKING
        runtime_eid = entity_id(env.hass, "sensor", f"{env.subentry_id}_watering_runtime_today")
        assert float(env.hass.states.get(runtime_eid).state) == pytest.approx(300.0)
        # Complete the session at the recheck.
        await advance(env, 1200)
        await set_moisture(env, "45")
        last_eid = entity_id(env.hass, "sensor", f"{env.subentry_id}_last_session")
        last = env.hass.states.get(last_eid)
        assert last.attributes["reason"] == "target_reached"
        assert last.attributes["cycles"] == 1
        assert last.attributes["moisture_after"] == 45.0
        next_eid = entity_id(env.hass, "sensor", f"{env.subentry_id}_next_eligible")
        assert env.hass.states.get(next_eid).state != "unknown"

    async def test_next_eligible_unknown_without_history(self, env) -> None:
        next_eid = entity_id(env.hass, "sensor", f"{env.subentry_id}_next_eligible")
        assert env.hass.states.get(next_eid).state == "unknown"


class TestBinarySensors:
    async def test_needs_water_semantics(self, env) -> None:
        eid = entity_id(env.hass, "binary_sensor", f"{env.subentry_id}_needs_water")
        assert env.hass.states.get(eid).state == "off"  # 33 >= 30
        await set_moisture(env, "29.9")
        # A dry report also starts a session; the informational view stays
        # a view (I27) — but here we assert the value semantics.
        assert env.hass.states.get(eid).state == "on"
        await set_moisture(env, "unavailable")
        assert env.hass.states.get(eid).state == "unavailable"  # never falsely off

    async def test_watering_and_problem(self, env) -> None:
        watering_eid = entity_id(env.hass, "binary_sensor", f"{env.subentry_id}_watering")
        problem_eid = entity_id(env.hass, "binary_sensor", f"{env.subentry_id}_problem")
        assert env.hass.states.get(watering_eid).state == "off"
        assert env.hass.states.get(problem_eid).state == "off"
        await set_moisture(env, "20")
        assert env.hass.states.get(watering_eid).state == "on"
        # Sensor failure mid-pulse -> fault; problem turns on.
        await set_moisture(env, "unavailable")
        assert env.hass.states.get(problem_eid).state == "on"
        assert env.hass.states.get(watering_eid).state == "off"

    async def test_watering_on_for_external_flow(self, env) -> None:
        env.switch.set_state("open", 100)  # external ON while IDLE
        await settle(env.hass)
        watering_eid = entity_id(env.hass, "binary_sensor", f"{env.subentry_id}_watering")
        assert env.hass.states.get(watering_eid).state == "on"
        status_eid = entity_id(env.hass, "sensor", f"{env.subentry_id}_status")
        blockers = env.hass.states.get(status_eid).attributes["water_resource_blockers"]
        assert blockers == [
            {
                "safety_record_id": env.runtime.controllers[env.subentry_id].safety_record_id,
                "reason": "external_flow",
            }
        ]


class TestControls:
    async def test_enabled_switch_round_trip(self, env) -> None:
        eid = entity_id(env.hass, "switch", f"{env.subentry_id}_enabled")
        assert env.hass.states.get(eid).state == "on"
        await env.hass.services.async_call("switch", "turn_off", {"entity_id": eid}, blocking=True)
        await settle(env.hass)
        assert env.hass.states.get(eid).state == "off"
        status_eid = entity_id(env.hass, "sensor", f"{env.subentry_id}_status")
        assert env.hass.states.get(status_eid).state == "disabled"
        await env.hass.services.async_call("switch", "turn_on", {"entity_id": eid}, blocking=True)
        await settle(env.hass)
        assert env.hass.states.get(status_eid).state == "idle"

    async def test_controls_refuse_while_reconciliation_dirty(self, env) -> None:
        from homeassistant.exceptions import HomeAssistantError

        from custom_components.moisture_loop.button import ZoneEvaluateButton
        from custom_components.moisture_loop.switch import ZoneEnabledSwitch

        controller = env.runtime.controllers[env.subentry_id]
        switch = ZoneEnabledSwitch(env.runtime, controller, env.subentry_id)
        button = ZoneEvaluateButton(env.runtime, controller, env.subentry_id)
        env.runtime.coordinator.dirty = True
        try:
            assert switch.available is False
            assert button.available is False
            with pytest.raises(HomeAssistantError) as excinfo:
                await switch.async_turn_off()
            assert excinfo.value.translation_key == "reconciliation_busy"
            with pytest.raises(HomeAssistantError) as excinfo:
                await button.async_press()
            assert excinfo.value.translation_key == "reconciliation_busy"
        finally:
            env.runtime.coordinator.dirty = False

    async def test_stop_button_terminates_session(self, env) -> None:
        await set_moisture(env, "20")
        stop_eid = entity_id(env.hass, "button", f"{env.subentry_id}_stop")
        await env.hass.services.async_call(
            "button", "press", {"entity_id": stop_eid}, blocking=True
        )
        await settle(env.hass)
        status_eid = entity_id(env.hass, "sensor", f"{env.subentry_id}_status")
        assert env.hass.states.get(status_eid).state == "idle"
        last_eid = entity_id(env.hass, "sensor", f"{env.subentry_id}_last_session")
        assert env.hass.states.get(last_eid).attributes["reason"] == "user_stop"

    async def test_evaluate_button_uses_normal_guards(self, env) -> None:
        eval_eid = entity_id(env.hass, "button", f"{env.subentry_id}_evaluate_now")
        # 33% is above the start threshold: evaluation refuses; nothing runs.
        await env.hass.services.async_call(
            "button", "press", {"entity_id": eval_eid}, blocking=True
        )
        await settle(env.hass)
        assert env.switch.on_calls == 0

    async def test_clear_fault_button(self, env) -> None:
        await set_moisture(env, "20")
        await set_moisture(env, "unavailable")  # AUTO abort -> FAULT
        status_eid = entity_id(env.hass, "sensor", f"{env.subentry_id}_status")
        assert env.hass.states.get(status_eid).state == "fault"
        await set_moisture(env, "33")  # sensor recovers -> auto-clear (T42)
        assert env.hass.states.get(status_eid).state == "idle"
        clear_eid = entity_id(env.hass, "button", f"{env.subentry_id}_clear_fault")
        # Pressing with no fault is a safe no-op.
        await env.hass.services.async_call(
            "button", "press", {"entity_id": clear_eid}, blocking=True
        )
