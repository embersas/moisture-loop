"""Slice 11 tests: Repairs, diagnostics, events, and logging (§§26, 32-34).

End-to-end through the real flows/platforms. Skips in the pure environment.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("homeassistant")

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from test_entities import (
    ACTUATOR,
    SENSOR,
    ScriptedValve,
    settle,
    setup_with_zone,
)

from custom_components.moisture_loop.const import DOMAIN
from custom_components.moisture_loop.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.moisture_loop.repairs import (
    ISSUE_OFF_UNCONFIRMED,
    async_create_fix_flow,
    record_issue_id,
)

EVENT_TYPES = (
    f"{DOMAIN}_session_started",
    f"{DOMAIN}_session_finished",
    f"{DOMAIN}_fault_set",
    f"{DOMAIN}_fault_cleared",
)


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations):
    return


@pytest.fixture
async def env(hass, freezer):
    freezer.move_to("2026-08-21 12:00:00+00:00")
    actuator_entry = er.async_get(hass).async_get_or_create(
        "valve", "test", "repairs-valve", suggested_object_id="valve_1"
    )
    assert actuator_entry.entity_id == ACTUATOR
    valve = ScriptedValve(hass)
    hass.states.async_set(SENSOR, "33")
    await hass.async_block_till_done()
    entry, subentry_id = await setup_with_zone(hass)
    events: list = []

    @callback
    def capture(event) -> None:
        events.append(event)

    for event_type in EVENT_TYPES:
        hass.bus.async_listen(event_type, capture)
    from types import SimpleNamespace

    yield SimpleNamespace(
        hass=hass,
        freezer=freezer,
        valve=valve,
        entry=entry,
        subentry_id=subentry_id,
        runtime=entry.runtime_data,
        events=events,
    )


async def advance(env, seconds: float) -> None:
    env.freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(env.hass, dt_util.utcnow())
    await settle(env.hass)


async def set_moisture(env, value: str) -> None:
    env.hass.states.async_set(SENSOR, value)
    await settle(env.hass)


def issue(hass, issue_id: str):
    return ir.async_get(hass).async_get_issue(DOMAIN, issue_id)


def kinds(env) -> list[str]:
    return [event.event_type.removeprefix(f"{DOMAIN}_") for event in env.events]


class TestRepairs:
    async def test_actuator_off_unconfirmed_critical_lifecycle(self, env) -> None:
        await set_moisture(env, "20")
        env.valve.close_behavior = "silent"

        async def silent_close(call) -> None:
            env.valve.off_calls += 1

        env.hass.services.async_register("valve", "close_valve", silent_close)
        controller = env.runtime.controllers[env.subentry_id]
        await controller.async_stop_watering()
        await settle(env.hass)
        for _ in range(3):
            await advance(env, 30)
        issue_id = record_issue_id(
            env.entry.entry_id,
            controller.safety_record_id,
            ISSUE_OFF_UNCONFIRMED,
        )
        created = issue(env.hass, issue_id)
        assert created is not None
        assert created.severity is ir.IssueSeverity.CRITICAL  # §34 true panic
        assert created.is_fixable
        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        await settle(env.hass)
        retained = env.runtime.store.data.safety_records[controller.safety_record_id]
        assert retained.runtime_lifecycle.value == "delete_pending"
        assert issue(env.hass, issue_id) is not None
        assert dr.async_get(env.hass).async_get_device({(DOMAIN, env.subentry_id)}) is None
        # Accounting continues until proven OFF; the issue clears only after
        # observed OFF plus acknowledgement (§26.1).
        assert kinds(env).count("session_finished") == 0
        env.valve.set_state("closed", 0)
        await settle(env.hass)
        assert issue(env.hass, issue_id) is not None  # ack still required
        finished = [event for event in env.events if event.event_type.endswith("session_finished")]
        assert len(finished) == 1
        assert finished[0].data["safety_record_id"] == controller.safety_record_id
        assert "device_id" not in finished[0].data
        flow = await async_create_fix_flow(env.hass, issue_id, created.data)
        flow.hass = env.hass
        assert (await flow.async_step_init())["type"].value == "form"
        assert (await flow.async_step_confirm({}))["type"].value == "create_entry"
        assert issue(env.hass, issue_id) is None

    async def test_exact_record_fix_rejects_stale_lineage(self, env) -> None:
        await set_moisture(env, "20")

        async def silent_close(call) -> None:
            env.valve.off_calls += 1

        env.hass.services.async_register("valve", "close_valve", silent_close)
        controller = env.runtime.controllers[env.subentry_id]
        await controller.async_stop_watering()
        await settle(env.hass)
        for _ in range(3):
            await advance(env, 30)
        issue_id = record_issue_id(
            env.entry.entry_id,
            controller.safety_record_id,
            ISSUE_OFF_UNCONFIRMED,
        )
        created = issue(env.hass, issue_id)
        stale_data = {**created.data, "safety_lineage_id": "stale-lineage"}
        flow = await async_create_fix_flow(env.hass, issue_id, stale_data)
        flow.hass = env.hass
        result = await flow.async_step_confirm({})
        assert result["errors"]["base"] == "record_not_found"
        assert issue(env.hass, issue_id) is not None

    async def test_retired_tombstone_fix_without_controller_or_device(self, env) -> None:
        from custom_components.moisture_loop.models import FaultCode

        controller = env.runtime.controllers[env.subentry_id]
        record_id = controller.safety_record_id
        await env.runtime.store.async_reconcile(
            lambda data: (
                {
                    **data.safety_records,
                    record_id: data.safety_records[record_id].evolve(
                        actuator_fault=FaultCode.ACTUATOR_OFF_TIMEOUT,
                        acknowledgement_required=True,
                    ),
                },
                dict(data.zone_histories),
            )
        )
        env.runtime._sync_repairs_from_authority()
        issue_id = record_issue_id(env.entry.entry_id, record_id, ISSUE_OFF_UNCONFIRMED)
        created = issue(env.hass, issue_id)
        assert created is not None

        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        await settle(env.hass)
        record = env.runtime.store.data.safety_records[record_id]
        assert record.runtime_lifecycle.value == "retired"
        assert env.runtime.controller_for_safety_record(record_id) is None
        assert dr.async_get(env.hass).async_get_device({(DOMAIN, env.subentry_id)}) is None
        assert issue(env.hass, issue_id) is not None

        flow = await async_create_fix_flow(env.hass, issue_id, created.data)
        flow.hass = env.hass
        assert (await flow.async_step_confirm({}))["type"].value == "create_entry"
        await settle(env.hass)
        acknowledged = env.runtime.store.data.safety_records[record_id]
        assert acknowledged.actuator_fault is None
        assert not acknowledged.acknowledgement_required
        assert issue(env.hass, issue_id) is None
        cleared = env.events[-1]
        assert cleared.event_type.endswith("fault_cleared")
        assert cleared.data["safety_record_id"] == record_id
        assert "device_id" not in cleared.data

    async def test_sensor_missing_error_issue(self, env) -> None:
        from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED

        env.hass.states.async_remove(SENSOR)
        env.hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED, {"action": "remove", "entity_id": SENSOR}
        )
        await settle(env.hass)
        created = issue(env.hass, f"zone_sensor_missing_{env.subentry_id}")
        assert created is not None
        assert created.severity is ir.IssueSeverity.ERROR
        controller = env.runtime.controllers[env.subentry_id]
        assert controller.active_fault is not None
        assert controller.active_fault.value == "configuration_invalid"

    async def test_integrity_issue_created_on_loss(self, hass, freezer) -> None:
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        from custom_components.moisture_loop import EntryRuntime
        from custom_components.moisture_loop.const import (
            CONF_RUNTIME_STORE_GENERATION_ID,
            CONF_RUNTIME_STORE_INITIALIZED,
        )

        freezer.move_to("2026-08-21 12:00:00+00:00")
        ScriptedValve(hass)
        await hass.async_block_till_done()
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_RUNTIME_STORE_GENERATION_ID: "gen-x",
                CONF_RUNTIME_STORE_INITIALIZED: True,  # store absent -> loss
            },
        )
        entry.add_to_hass(hass)
        runtime = EntryRuntime(hass, entry)
        await runtime.async_initialize()
        created = issue(hass, f"runtime_store_integrity_lost_{entry.entry_id}")
        assert created is not None
        assert created.severity is ir.IssueSeverity.ERROR
        await runtime.async_unload()


class TestEvents:
    async def test_session_events_have_identity_and_summary(self, env) -> None:
        await set_moisture(env, "20")
        started = next(e for e in env.events if e.event_type.endswith("session_started"))
        assert started.data["zone_id"] == env.subentry_id
        assert started.data["zone_name"] == "Front bed"
        assert started.data["mode"] == "auto"
        assert started.data["session_id"]
        device = dr.async_get(env.hass).async_get_device({(DOMAIN, env.subentry_id)})
        assert started.data["device_id"] == device.id
        controller = env.runtime.controllers[env.subentry_id]
        await controller.async_stop_watering()
        await settle(env.hass)
        finished = next(e for e in env.events if e.event_type.endswith("session_finished"))
        assert finished.data["reason"] == "user_stop"
        assert finished.data["runtime_s"] >= 0
        assert finished.data["runtime_estimated"] is False
        assert finished.data["cycles"] == 1
        assert finished.data["moisture_before"] == 20.0
        assert kinds(env).count("session_finished") == 1  # exactly one finish

    async def test_manual_fault_event_ordering(self, env) -> None:
        """MF3/MF4 event side: no churn; finish before clear on recovery."""
        await set_moisture(env, "20")
        await set_moisture(env, "unavailable")  # fault_set(SENSOR_UNAVAILABLE)
        await settle(env.hass)
        assert kinds(env).count("fault_set") == 1
        events_before = len(env.events)
        controller = env.runtime.controllers[env.subentry_id]
        await controller.async_manual_start(300.0)
        await settle(env.hass)
        new_kinds = kinds(env)[events_before:]
        assert "fault_cleared" not in new_kinds  # starting manual never clears
        assert "session_started" in new_kinds
        await set_moisture(env, "33")  # recovery mid-manual
        await advance(env, 300)  # manual completes
        tail = kinds(env)
        finish_idx = len(tail) - 1 - tail[::-1].index("session_finished")
        clear_idx = len(tail) - 1 - tail[::-1].index("fault_cleared")
        assert finish_idx < clear_idx  # §20.3/§32 ordering
        # Returning through WATERING emitted no duplicate fault_set.
        assert tail.count("fault_set") == 1

    async def test_delayed_off_defers_single_finish(self, env) -> None:
        """AC4 event side: one finish, only after accounting closes."""
        await set_moisture(env, "20")

        async def silent_close(call) -> None:
            env.valve.off_calls += 1

        env.hass.services.async_register("valve", "close_valve", silent_close)
        controller = env.runtime.controllers[env.subentry_id]
        await controller.async_stop_watering()
        await settle(env.hass)
        for _ in range(3):
            await advance(env, 30)
        assert "session_finished" not in kinds(env)  # accounting open
        env.valve.set_state("closed", 0)
        await settle(env.hass)
        assert kinds(env).count("session_finished") == 1

    async def test_deleted_record_fault_event_needs_no_device(self, env) -> None:
        from custom_components.moisture_loop.models import FaultCode

        controller = env.runtime.controllers[env.subentry_id]
        record_id = controller.safety_record_id
        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        await settle(env.hass)
        assert dr.async_get(env.hass).async_get_device({(DOMAIN, env.subentry_id)}) is None
        await env.runtime.store.async_reconcile(
            lambda data: (
                {
                    **data.safety_records,
                    record_id: data.safety_records[record_id].evolve(
                        actuator_fault=FaultCode.ACTUATOR_UNAVAILABLE,
                    ),
                },
                dict(data.zone_histories),
            )
        )
        env.runtime._make_emitter(env.subentry_id, record_id)(
            "fault_set", {"fault": FaultCode.ACTUATOR_UNAVAILABLE.value}
        )
        await settle(env.hass)
        event = env.events[-1]
        assert event.event_type.endswith("fault_set")
        assert event.data["safety_record_id"] == record_id
        assert event.data["subentry_id"] is None
        assert "device_id" not in event.data


class TestDiagnostics:
    async def test_diagnostics_content_and_redaction(self, env) -> None:
        await set_moisture(env, "20")  # active session for anchors
        diagnostics = await async_get_config_entry_diagnostics(env.hass, env.entry)
        assert diagnostics["manifest"]["integration_type"] == "hub"
        # The zone-add reload re-ran setup: the first pass was the first
        # install; this (second) run adopted the initialized store.
        assert diagnostics["store"]["setup_classification"] == "initialized_ok"
        assert diagnostics["store"]["schema_version"] == 3
        assert diagnostics["store"]["store_revision"] >= 1
        assert diagnostics["store"]["previous_run_was_clean"] is False
        assert len(diagnostics["store"]["current_run_id_short"]) == 8
        # Redaction: the generation UUID never appears in clear text.
        assert diagnostics["entry_data"]["runtime_store_generation_id"] == "**REDACTED**"
        assert diagnostics["raw_store"]["generation_id"] == "**REDACTED**"
        zone = diagnostics["zones"][env.subentry_id]
        assert zone["lifecycle"] == "active"
        assert zone["safety_record_id"] == env.runtime.controllers[env.subentry_id].safety_record_id
        assert zone["zone_history"]["zone_runtime"]["state"] == "watering"
        assert zone["applied_shadow"]["actuator_identity"]["last_known_entity_id"] == ACTUATOR
        assert zone["runtime"]["observation"]["classification"] == "valid"
        session = zone["zone_history"]["zone_runtime"]["current_session"]["context"]
        assert session["mode"] == "auto"
        assert session["pulse_intent_at_utc"] is not None
        assert zone["runtime"]["actuator_classification"]["observed_on"] is True
        assert diagnostics["slot_manager"]["owner"] == env.subentry_id
        # Measured vs estimated runtime is explicit.
        assert session["runtime_estimated"] is False

    async def test_diagnostics_retained_tombstone_without_device(self, env) -> None:
        record_id = env.runtime.controllers[env.subentry_id].safety_record_id
        env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        await settle(env.hass)
        runtime = env.entry.runtime_data
        diagnostics = await async_get_config_entry_diagnostics(env.hass, env.entry)
        retained = diagnostics["retained_tombstones"][record_id]
        assert retained["active_subentry_id"] is None
        assert retained["lifecycle"] in ("delete_pending", "retired")
        assert retained["safety_record_id"] == record_id
        assert dr.async_get(env.hass).async_get_device({(DOMAIN, env.subentry_id)}) is None
        assert runtime.store.data.safety_records[record_id].safety_record_id == record_id

    async def test_diagnostics_transitions_ring(self, env) -> None:
        await set_moisture(env, "20")
        controller = env.runtime.controllers[env.subentry_id]
        await controller.async_stop_watering()
        await settle(env.hass)
        diagnostics = await async_get_config_entry_diagnostics(env.hass, env.entry)
        transitions = diagnostics["recent_transitions"]
        assert transitions, "transition buffer must not be empty"
        assert len(transitions) <= 50
        ids = [t["transition"] for t in transitions]
        assert "T1" in ids
        assert "T17" in ids
        assert all(t["zone_id"] == env.subentry_id for t in transitions)


class TestLogging:
    async def test_safety_relevant_levels(self, env, caplog) -> None:
        caplog.set_level(logging.DEBUG, logger="custom_components.moisture_loop")
        await set_moisture(env, "20")
        assert any(
            record.levelno == logging.INFO and "session started" in record.message
            for record in caplog.records
        )
        await set_moisture(env, "unavailable")
        await settle(env.hass)
        # Sensor-fault termination is WARNING, never DEBUG-only (§33.1).
        assert any(
            record.levelno == logging.WARNING and "sensor fault" in record.message
            for record in caplog.records
        )

    async def test_off_timeout_logs_error(self, env, caplog) -> None:
        caplog.set_level(logging.DEBUG, logger="custom_components.moisture_loop")
        await set_moisture(env, "20")

        async def silent_close(call) -> None:
            env.valve.off_calls += 1

        env.hass.services.async_register("valve", "close_valve", silent_close)
        controller = env.runtime.controllers[env.subentry_id]
        await controller.async_stop_watering()
        await settle(env.hass)
        for _ in range(3):
            await advance(env, 30)
        assert any(
            record.levelno == logging.ERROR and "not proven after retries" in record.message
            for record in caplog.records
        )

    async def test_normal_pulse_details_are_debug(self, env, caplog) -> None:
        caplog.set_level(logging.DEBUG, logger="custom_components.moisture_loop")
        await set_moisture(env, "33")  # a guard-refused evaluation
        refusal_records = [
            record
            for record in caplog.records
            if "MoistureReport" in record.message and record.levelno == logging.DEBUG
        ]
        assert refusal_records  # per-observation noise stays DEBUG


class TestRepairEdges:
    async def test_async_reload_failure_creates_reconciliation_issue(self, env) -> None:
        from custom_components.moisture_loop.repairs import (
            ISSUE_RECONCILIATION_FAILED,
        )

        subentry = env.entry.subentries[env.subentry_id]
        changed = {**subentry.data, "name": "Reload failure"}
        with patch.object(
            env.hass.config_entries,
            "async_reload",
            AsyncMock(return_value=False),
        ):
            assert env.hass.config_entries.async_update_subentry(env.entry, subentry, data=changed)
            await settle(env.hass)
        assert env.runtime.coordinator.failed
        created = issue(
            env.hass,
            f"{ISSUE_RECONCILIATION_FAILED}_{env.entry.entry_id}",
        )
        assert created is not None
        assert created.severity is ir.IssueSeverity.ERROR
        assert not env.runtime.slots.snapshot().admission_open

    async def test_reconciliation_failure_issue_clears_only_after_recovery(self, env) -> None:
        from custom_components.moisture_loop.models import BlockerReason
        from custom_components.moisture_loop.reconciliation import ReconciliationError
        from custom_components.moisture_loop.repairs import (
            ISSUE_RECONCILIATION_FAILED,
        )

        runtime = env.runtime
        record_id = runtime.controllers[env.subentry_id].safety_record_id
        await runtime.slots.async_add_blocker(record_id, BlockerReason.INTEGRATION_OFF_UNCONFIRMED)
        runtime.coordinator._fail(ReconciliationError("stage-6 injected failure"))
        runtime._sync_repairs_from_authority()
        issue_id = f"{ISSUE_RECONCILIATION_FAILED}_{env.entry.entry_id}"
        created = issue(env.hass, issue_id)
        assert created is not None
        assert created.severity is ir.IssueSeverity.ERROR
        assert not runtime.slots.snapshot().admission_open

        subentry = env.entry.subentries[env.subentry_id]
        assert env.hass.config_entries.async_update_subentry(
            env.entry, subentry, title="Reconciled"
        )
        await settle(env.hass)
        assert not runtime.coordinator.failed
        assert issue(env.hass, issue_id) is None
        assert (
            record_id,
            BlockerReason.INTEGRATION_OFF_UNCONFIRMED,
        ) in runtime.slots.blockers()

    async def test_configuration_fault_clears_after_reconfigure_reload(self, env) -> None:
        from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED

        env.hass.states.async_remove(SENSOR)
        env.hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED, {"action": "remove", "entity_id": SENSOR}
        )
        await settle(env.hass)
        assert issue(env.hass, f"zone_sensor_missing_{env.subentry_id}") is not None
        # A reconfiguration restores a valid sensor and reloads the entry.
        env.hass.states.async_set(SENSOR, "33")
        await env.hass.config_entries.async_reload(env.entry.entry_id)
        await settle(env.hass)
        runtime = env.entry.runtime_data
        controller = runtime.controllers[env.subentry_id]
        assert controller.active_fault is None
        assert controller.state.value == "idle"
        assert issue(env.hass, f"zone_sensor_missing_{env.subentry_id}") is None

    async def test_actuator_missing_error_issue(self, env) -> None:
        from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED

        env.hass.states.async_remove(ACTUATOR)
        # Actuator loss during IDLE keeps the zone safe; entity removal via
        # the sensor path drives CONFIGURATION_INVALID with the actuator
        # missing, creating the actuator issue.
        env.hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED, {"action": "remove", "entity_id": SENSOR}
        )
        await settle(env.hass)
        assert issue(env.hass, f"zone_actuator_missing_{env.subentry_id}") is not None

    async def test_integrity_ack_clears_issue(self, hass, freezer) -> None:
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        from custom_components.moisture_loop import EntryRuntime
        from custom_components.moisture_loop.const import (
            CONF_RUNTIME_STORE_GENERATION_ID,
            CONF_RUNTIME_STORE_INITIALIZED,
        )

        freezer.move_to("2026-08-21 12:00:00+00:00")
        ScriptedValve(hass)
        hass.states.async_set(SENSOR, "33")
        await hass.async_block_till_done()
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_RUNTIME_STORE_GENERATION_ID: "gen-x",
                CONF_RUNTIME_STORE_INITIALIZED: True,
            },
            subentries_data=[],
        )
        entry.add_to_hass(hass)
        runtime = EntryRuntime(hass, entry)
        await runtime.async_initialize()
        issue_id = f"runtime_store_integrity_lost_{entry.entry_id}"
        assert issue(hass, issue_id) is not None
        # With no zones holding the fault, an ack-driven clear removes it.
        runtime._make_emitter("phantom-zone")(
            "fault_cleared", {"fault": "restored_from_unsafe_state"}
        )
        await settle(hass)
        assert issue(hass, issue_id) is None
        await runtime.async_unload()


class TestInstrumentationEdges:
    async def test_emitter_repair_branches_direct(self, env) -> None:
        emit = env.runtime._make_emitter(env.subentry_id)
        # Zone-level integrity fault (e.g. failed safety write) creates the
        # entry-level issue; clearing config faults deletes entity issues.
        emit("fault_set", {"fault": "restored_from_unsafe_state"})
        await settle(env.hass)
        issue_id = f"runtime_store_integrity_lost_{env.entry.entry_id}"
        assert issue(env.hass, issue_id) is not None
        emit("fault_cleared", {"fault": "configuration_invalid"})
        await settle(env.hass)

    async def test_config_fault_persists_while_entity_still_missing(self, env) -> None:
        from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED

        env.hass.states.async_remove(SENSOR)
        env.hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED, {"action": "remove", "entity_id": SENSOR}
        )
        await settle(env.hass)
        # Reload WITHOUT restoring the sensor: the fault must persist.
        await env.hass.config_entries.async_reload(env.entry.entry_id)
        await settle(env.hass)
        controller = env.entry.runtime_data.controllers[env.subentry_id]
        assert controller.active_fault is not None
        assert controller.active_fault.value == "configuration_invalid"

    async def test_success_completion_logs_info(self, env, caplog) -> None:
        caplog.set_level(logging.INFO, logger="custom_components.moisture_loop")
        controller = env.runtime.controllers[env.subentry_id]
        await controller.async_manual_start(60.0)
        await settle(env.hass)
        await advance(env, 60)
        assert any(
            record.levelno == logging.INFO
            and "session finished (manual_complete)" in record.message
            for record in caplog.records
        )

    async def test_constrained_completion_logs_warning(self, env, caplog) -> None:
        caplog.set_level(logging.DEBUG, logger="custom_components.moisture_loop")
        from custom_components.moisture_loop.models import (
            AutoEvaluate,
            CompletionReason,
            ControllerState,
            Decision,
        )

        controller = env.runtime.controllers[env.subentry_id]
        decision = Decision(
            transition_id="T26",
            new_state=ControllerState.IDLE,
            reason=CompletionReason.MAX_CYCLES,
            clear_session=True,
        )
        inp = controller._build_input(AutoEvaluate())
        controller._record_and_log(decision, inp)
        assert any(
            record.levelno == logging.WARNING
            and "completed constrained (max_cycles)" in record.message
            for record in caplog.records
        )
