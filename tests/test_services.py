"""Slice 10 tests: integration-level actions (SPECIFICATION.md §5.3, §31).

LC1 (registration lifecycle) and LC2 (device resolution matrix) plus manual
duration validation/refusal routing. Skips cleanly in the pure environment.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("homeassistant")

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from test_entities import (
    SENSOR,
    ScriptedValve,
    settle,
    setup_with_zone,
)

from custom_components.soilsync.const import DOMAIN

ALL_SERVICES = ("start_manual_watering", "stop_watering", "evaluate_zone", "clear_fault")


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations):
    return


@pytest.fixture
async def env(hass, freezer):
    freezer.move_to("2026-08-21 12:00:00+00:00")
    valve = ScriptedValve(hass)
    hass.states.async_set(SENSOR, "33")
    await hass.async_block_till_done()
    entry, subentry_id = await setup_with_zone(hass)
    device = dr.async_get(hass).async_get_device({(DOMAIN, subentry_id)})
    assert device is not None
    from types import SimpleNamespace

    yield SimpleNamespace(
        hass=hass,
        freezer=freezer,
        valve=valve,
        entry=entry,
        subentry_id=subentry_id,
        device=device,
        runtime=entry.runtime_data,
    )


async def call(env, service: str, **data):
    await env.hass.services.async_call(DOMAIN, service, data, blocking=True)
    await settle(env.hass)


async def advance(env, seconds: float) -> None:
    env.freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(env.hass, dt_util.utcnow())
    await settle(env.hass)


def raises_key(excinfo) -> str:
    return excinfo.value.translation_key


class TestActionLifecycle:
    async def test_lc1_actions_exist_with_zero_entries(self, hass) -> None:
        assert await async_setup_component(hass, DOMAIN, {})
        for service in ALL_SERVICES:
            assert hass.services.has_service(DOMAIN, service), service

    async def test_lc1_actions_survive_unload_and_reject_safely(self, env) -> None:
        assert await env.hass.config_entries.async_unload(env.entry.entry_id)
        await settle(env.hass)
        for service in ALL_SERVICES:
            assert env.hass.services.has_service(DOMAIN, service), service
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "stop_watering", device_id=env.device.id)
        assert raises_key(excinfo) == "entry_not_loaded"

    async def test_lc1_no_duplicate_registration_across_reloads(self, env) -> None:
        await env.hass.config_entries.async_reload(env.entry.entry_id)
        await settle(env.hass)
        for service in ALL_SERVICES:
            assert env.hass.services.has_service(DOMAIN, service), service

    @pytest.mark.parametrize("lifecycle", ["delete_pending", "retired"])
    @pytest.mark.parametrize("service", ALL_SERVICES)
    async def test_non_active_runtime_refuses_actions(self, env, lifecycle, service) -> None:
        from custom_components.soilsync.models import RuntimeLifecycle

        controller = env.runtime.controllers[env.subentry_id]
        controller.runtime_lifecycle = RuntimeLifecycle(lifecycle)
        try:
            with pytest.raises(ServiceValidationError) as excinfo:
                data = {"device_id": env.device.id}
                if service == "start_manual_watering":
                    data["duration"] = 60
                await call(env, service, **data)
            assert raises_key(excinfo) == "zone_not_active"
            assert env.valve.on_calls == 0
        finally:
            controller.runtime_lifecycle = RuntimeLifecycle.ACTIVE

    @pytest.mark.parametrize(
        ("attribute", "translation_key"),
        [("dirty", "reconciliation_busy"), ("failed", "reconciliation_failed")],
    )
    @pytest.mark.parametrize("service", ALL_SERVICES)
    async def test_reconciliation_barrier_refuses_actions(
        self, env, attribute, translation_key, service
    ) -> None:
        coordinator = env.runtime.coordinator
        setattr(coordinator, attribute, True)
        try:
            with pytest.raises(ServiceValidationError) as excinfo:
                data = {"device_id": env.device.id}
                if service == "start_manual_watering":
                    data["duration"] = 60
                await call(env, service, **data)
            assert raises_key(excinfo) == translation_key
            assert env.valve.on_calls == 0
        finally:
            setattr(coordinator, attribute, False)


class TestDeviceResolution:
    async def test_lc2_unknown_device(self, env) -> None:
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "evaluate_zone", device_id="no-such-device")
        assert raises_key(excinfo) == "device_not_found"

    async def test_lc2_wrong_integration_device(self, env) -> None:
        registry = dr.async_get(env.hass)
        other = registry.async_get_or_create(
            config_entry_id=env.entry.entry_id,
            identifiers={("other_domain", "other-thing")},
        )
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "evaluate_zone", device_id=other.id)
        assert raises_key(excinfo) == "not_a_zone_device"

    async def test_lc2_deleted_zone(self, env) -> None:
        env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        # The device may be garbage collected with the subentry; simulate a
        # stale automation target by re-creating the identifier.
        registry = dr.async_get(env.hass)
        stale = registry.async_get_or_create(
            config_entry_id=env.entry.entry_id,
            identifiers={(DOMAIN, env.subentry_id)},
        )
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "evaluate_zone", device_id=stale.id)
        assert raises_key(excinfo) == "zone_deleted"

    async def test_lc2_unloaded_entry(self, env) -> None:
        assert await env.hass.config_entries.async_unload(env.entry.entry_id)
        await settle(env.hass)
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "evaluate_zone", device_id=env.device.id)
        assert raises_key(excinfo) == "entry_not_loaded"


class TestManualAction:
    async def test_manual_start_runs_bounded_session(self, env) -> None:
        await call(env, "start_manual_watering", device_id=env.device.id, duration=600)
        controller = env.runtime.controllers[env.subentry_id]
        assert controller.state.value == "watering"
        assert controller.session.mode.value == "manual"
        assert controller.session.manual_effective_duration_s == 600.0
        assert env.valve.on_calls == 1
        await advance(env, 600)
        assert controller.state.value == "idle"
        assert env.valve.off_calls == 1

    async def test_manual_clamps_to_configured_caps(self, env) -> None:
        await call(env, "start_manual_watering", device_id=env.device.id, duration=999999)
        controller = env.runtime.controllers[env.subentry_id]
        assert controller.session is not None
        assert controller.session.manual_effective_duration_s == 1800.0  # manual max

    @pytest.mark.parametrize("duration", [0, -5, float("nan"), float("inf")])
    async def test_invalid_duration_refused(self, env, duration) -> None:
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "start_manual_watering", device_id=env.device.id, duration=duration)
        assert raises_key(excinfo) == "invalid_duration"
        assert env.valve.on_calls == 0

    async def test_manual_refused_while_disabled(self, env) -> None:
        controller = env.runtime.controllers[env.subentry_id]
        await controller.async_set_enabled(False)
        await settle(env.hass)
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "start_manual_watering", device_id=env.device.id, duration=600)
        assert raises_key(excinfo) == "zone_disabled"

    async def test_manual_refused_with_active_session(self, env) -> None:
        await call(env, "start_manual_watering", device_id=env.device.id, duration=600)
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "start_manual_watering", device_id=env.device.id, duration=600)
        assert raises_key(excinfo) == "session_active"

    async def test_manual_refused_for_blocking_fault(self, env) -> None:
        env.hass.states.async_set(SENSOR, "20")
        await settle(env.hass)
        env.valve.set_state("unavailable")
        await settle(env.hass)  # ACTUATOR_UNAVAILABLE mid-pulse
        env.valve.set_state("closed", 0)
        await settle(env.hass)
        controller = env.runtime.controllers[env.subentry_id]
        assert controller.active_fault is not None
        assert not controller.active_fault.allows_manual
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "start_manual_watering", device_id=env.device.id, duration=600)
        assert raises_key(excinfo) == "fault_blocks_manual"

    async def test_manual_sensor_fault_remains_allowed(self, env) -> None:
        env.hass.states.async_set(SENSOR, "20")
        await settle(env.hass)
        env.hass.states.async_set(SENSOR, "unavailable")
        await settle(env.hass)
        controller = env.runtime.controllers[env.subentry_id]
        assert controller.active_fault.value == "sensor_unavailable"
        await call(env, "start_manual_watering", device_id=env.device.id, duration=60)
        assert controller.state.value == "watering"
        assert controller.session.mode.value == "manual"

    async def test_manual_refused_when_daily_exhausted(self, env) -> None:
        controller = env.runtime.controllers[env.subentry_id]
        await call(env, "start_manual_watering", device_id=env.device.id, duration=1800)
        await advance(env, 1800)
        await call(env, "start_manual_watering", device_id=env.device.id, duration=1800)
        await advance(env, 1800)
        assert controller.daily.runtime_s == pytest.approx(3600.0)
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "start_manual_watering", device_id=env.device.id, duration=600)
        assert raises_key(excinfo) == "daily_budget_exhausted"

    async def test_manual_refused_while_resource_occupied(self, env) -> None:
        from custom_components.soilsync.models import BlockerReason

        record_id = env.runtime.bindings[env.subentry_id].safety_record_id
        await env.runtime.slots.async_add_blocker(record_id, BlockerReason.EXTERNAL_FLOW)
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "start_manual_watering", device_id=env.device.id, duration=600)
        assert raises_key(excinfo) == "water_resource_occupied"


class TestOtherActions:
    async def test_stop_and_evaluate_route_normally(self, env) -> None:
        env.hass.states.async_set(SENSOR, "20")
        await settle(env.hass)
        controller = env.runtime.controllers[env.subentry_id]
        assert controller.state.value == "watering"
        await call(env, "stop_watering", device_id=env.device.id)
        assert controller.state.value == "idle"
        # Stop in an inactive state is a safe no-op.
        await call(env, "stop_watering", device_id=env.device.id)
        # Evaluate uses normal guards (min interval just reset): refused.
        await call(env, "evaluate_zone", device_id=env.device.id)
        assert env.valve.on_calls == 1

    async def test_clear_fault_refusal_and_success(self, env) -> None:
        env.hass.states.async_set(SENSOR, "20")
        await settle(env.hass)
        env.hass.states.async_set(SENSOR, "unavailable")
        await settle(env.hass)  # FAULT(SENSOR_UNAVAILABLE)
        controller = env.runtime.controllers[env.subentry_id]
        assert controller.active_fault is not None
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "clear_fault", device_id=env.device.id)
        assert raises_key(excinfo) == "fault_not_clearable"
        env.hass.states.async_set(SENSOR, "33")
        await settle(env.hass)  # auto-clears (T42)
        assert controller.active_fault is None
        await call(env, "clear_fault", device_id=env.device.id)  # no-op


class TestServiceEdges:
    async def test_device_from_other_entry_is_rejected(self, env) -> None:
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        other_entry = MockConfigEntry(domain="other_domain")
        other_entry.add_to_hass(env.hass)
        registry = dr.async_get(env.hass)
        impostor = registry.async_get_or_create(
            config_entry_id=other_entry.entry_id,
            identifiers={(DOMAIN, "fake-zone")},
        )
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "evaluate_zone", device_id=impostor.id)
        assert raises_key(excinfo) == "not_a_zone_device"

    async def test_zone_without_controller_not_ready(self, env) -> None:
        env.runtime.controllers.pop(env.subentry_id)
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "evaluate_zone", device_id=env.device.id)
        assert raises_key(excinfo) == "zone_not_ready"

    async def test_manual_refused_when_actuator_not_ready(self, env) -> None:
        env.valve.set_state("unavailable")
        await settle(env.hass)
        with pytest.raises(ServiceValidationError) as excinfo:
            await call(env, "start_manual_watering", device_id=env.device.id, duration=600)
        assert raises_key(excinfo) == "actuator_not_ready"

    async def test_unknown_guard_refusal_falls_back(self, env) -> None:
        from types import SimpleNamespace

        from custom_components.soilsync.models import GuardResult
        from custom_components.soilsync.services import _raise_for_refusal

        decision = SimpleNamespace(
            guard_result=GuardResult(passed=False, failed_guards=("mystery-guard",))
        )
        with pytest.raises(ServiceValidationError) as excinfo:
            _raise_for_refusal(decision, "start_manual_watering")
        assert excinfo.value.translation_key == "request_refused"
        # A passing result and a slot wait are not refusals.
        _raise_for_refusal(SimpleNamespace(guard_result=None), "x")
        slot_wait = SimpleNamespace(
            guard_result=GuardResult(passed=False, failed_guards=("G-SLOT",))
        )
        _raise_for_refusal(slot_wait, "x")

    async def test_double_registration_is_a_noop(self, env) -> None:
        from custom_components.soilsync.services import async_register_services

        async_register_services(env.hass)  # second call: no duplicate errors
        for service in ALL_SERVICES:
            assert env.hass.services.has_service(DOMAIN, service)


class TestFinalCoverageEdges:
    async def test_needs_water_is_on_guard_direct(self, env) -> None:
        from custom_components.soilsync.binary_sensor import (
            ZoneNeedsWaterBinarySensor,
        )

        controller = env.runtime.controllers[env.subentry_id]
        entity = ZoneNeedsWaterBinarySensor(env.runtime, controller, env.subentry_id)
        env.hass.states.async_set(SENSOR, "unavailable")
        await settle(env.hass)
        assert entity.available is False
        assert entity.is_on is False  # guarded even if queried directly

    async def test_midnight_trigger_evaluates_zones(self, env) -> None:
        controller = env.runtime.controllers[env.subentry_id]
        assert controller.assessment.available  # snapshot property
        # Advance to the next HA-local midnight and fire the time change.
        local_tz = dt_util.get_default_time_zone()
        now_local = dt_util.utcnow().astimezone(local_tz)
        next_midnight = (now_local + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        delta = (next_midnight - now_local).total_seconds()
        env.freezer.tick(timedelta(seconds=delta))
        async_fire_time_changed(env.hass, dt_util.utcnow())
        await settle(env.hass)
        # 33% is above the start threshold: the midnight evaluation refused.
        assert env.valve.on_calls == 0

    async def test_listener_unsubscribe_is_idempotent(self, env) -> None:
        controller = env.runtime.controllers[env.subentry_id]
        calls: list = []
        unsub = controller.async_add_listener(lambda: calls.append(1))
        unsub()
        unsub()  # second removal is a no-op
