"""Spec.4 Stage-4 final-ON authorization and compensation races.

Every interleaving uses controlled Events/Futures or explicit event-loop
turns.  There are no timing sleeps.  Switch and valve service families share
the same command envelope but retain their distinct terminal states/services.
"""

from __future__ import annotations

import asyncio
from types import MappingProxyType, SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from aiohttp import TCPConnector
from aiohttp.resolver import ThreadedResolver
from aiohttp.test_utils import TestClient, TestServer
from homeassistant.config_entries import ConfigSubentry, ConfigSubentryData
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.moisture_loop import EntryRuntime
from custom_components.moisture_loop.const import (
    CONF_RUNTIME_STORE_GENERATION_ID,
    CONF_RUNTIME_STORE_INITIALIZED,
    DOMAIN,
)
from custom_components.moisture_loop.models import (
    BlockerReason,
    CompletionReason,
    ControllerState,
    DisableRequested,
    FaultCode,
    PulseDeadlineReached,
    RuntimeLifecycle,
    SlotGranted,
    SoakDeadlineReached,
    StopRequested,
    WatchdogFired,
)
from custom_components.moisture_loop.zone_controller import OnCommandOutcome

GEN = "44444444-5555-6666-7777-888888888888"
SENSOR = "sensor.stage4_moisture"


def zone_data(actuator: str, *, name: str = "Stage 4 bed") -> dict[str, object]:
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


class BlockingActuator:
    """Controlled switch/valve service implementation with ordered evidence."""

    def __init__(self, hass, domain: str, entity_id: str) -> None:
        self.hass = hass
        self.domain = domain
        self.entity_id = entity_id
        self.on_calls = 0
        self.off_calls = 0
        self.on_started = asyncio.Event()
        self.allow_on = asyncio.Event()
        self.off_started = asyncio.Event()
        self.allow_off = asyncio.Event()
        self.allow_off.set()
        self.raise_after_on = False
        self.off_behavior = "ack"
        self.order: list[str] = []

        initial = "off" if domain == "switch" else "closed"
        hass.states.async_set(entity_id, initial)

        async def turn_on(call) -> None:
            self.on_calls += 1
            self.order.append("dispatch_started")
            self.on_started.set()
            await self.allow_on.wait()
            terminal = "on" if domain == "switch" else "open"
            hass.states.async_set(entity_id, terminal, context=call.context)
            if self.raise_after_on:
                raise RuntimeError("command result uncertain after dispatch")

        async def turn_off(call) -> None:
            self.off_calls += 1
            self.order.append("off_started")
            self.off_started.set()
            await self.allow_off.wait()
            if self.off_behavior == "ack":
                terminal = "off" if domain == "switch" else "closed"
                hass.states.async_set(entity_id, terminal, context=call.context)

        if domain == "switch":
            hass.services.async_register("switch", "turn_on", turn_on)
            hass.services.async_register("switch", "turn_off", turn_off)
        else:
            hass.services.async_register("valve", "open_valve", turn_on)
            hass.services.async_register("valve", "close_valve", turn_off)

    def prove_off(self) -> None:
        terminal = "off" if self.domain == "switch" else "closed"
        self.hass.states.async_set(self.entity_id, terminal)


async def spin_until(predicate, *, turns: int = 100) -> None:
    """Wait only for deterministic event-loop work, never wall-clock time."""
    for _ in range(turns):
        if predicate():
            return
        await asyncio.sleep(0)
    assert predicate()


async def settle(hass, *, turns: int = 30) -> None:
    for _ in range(turns):
        await asyncio.sleep(0)
        await hass.async_block_till_done()


@pytest.fixture(params=("switch", "valve"))
async def command_env(request, hass, hass_storage, freezer):
    freezer.move_to("2026-08-23 10:00:00+10:00")
    domain = request.param
    registry = er.async_get(hass)
    entry_id = f"stage4-{domain}-actuator"
    actuator_entry = registry.async_get_or_create(
        domain,
        "test",
        entry_id,
        suggested_object_id=f"stage4_{domain}_valve",
    )
    actuator = BlockingActuator(hass, domain, actuator_entry.entity_id)
    hass.states.async_set(SENSOR, "35")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Moisture Loop Stage 4",
        data={
            CONF_RUNTIME_STORE_GENERATION_ID: GEN,
            CONF_RUNTIME_STORE_INITIALIZED: False,
        },
        subentries_data=[
            ConfigSubentryData(
                data=zone_data(actuator.entity_id),
                subentry_type="zone",
                title="Stage 4 bed",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    runtime = EntryRuntime(hass, entry)
    await runtime.async_initialize()
    await settle(hass)
    subentry_id = next(iter(entry.subentries))
    controller = runtime.controllers[subentry_id]
    env = SimpleNamespace(
        hass=hass,
        runtime=runtime,
        entry=entry,
        subentry_id=subentry_id,
        controller=controller,
        actuator=actuator,
        freezer=freezer,
    )
    yield env
    actuator.allow_on.set()
    actuator.allow_off.set()
    await settle(hass)
    await runtime.async_unload()


async def start_auto_inflight(env) -> None:
    env.hass.states.async_set(SENSOR, "20")
    await spin_until(lambda: env.actuator.on_started.is_set())
    marker = env.controller.inflight_on
    assert marker is not None
    assert marker.safety_record_id == env.controller.safety_record_id
    assert marker.zone_history_id == env.controller.zone_history_id
    assert marker.session_id == env.controller.session.session_id
    assert marker.outcome is OnCommandOutcome.IN_FLIGHT


async def finish_reconciliation(env) -> None:
    env.actuator.allow_on.set()
    env.actuator.allow_off.set()
    record_id = env.controller.safety_record_id
    await spin_until(
        lambda: (
            env.runtime.store.data.zone_histories[
                env.runtime.store.data.safety_records[record_id].zone_history_id
            ].zone_runtime.session
            is None
        ),
        turns=200,
    )
    await settle(env.hass)


def persisted_summary(env):
    record = env.runtime.store.data.safety_records[env.controller.safety_record_id]
    history = env.runtime.store.data.zone_histories[record.zone_history_id]
    return record, history, history.zone_runtime.last_session_summary


class TestFinalGate:
    @pytest.mark.parametrize("mode", ("auto", "manual"))
    async def test_nd9_delete_after_intent_before_final_gate_has_zero_on(
        self, command_env, mode
    ) -> None:
        env = command_env
        original = env.runtime.store.async_update_controller_runtime
        removed = False
        reconciliation_started = asyncio.Event()
        allow_reconciliation = asyncio.Event()
        original_applier = env.runtime.coordinator._snapshot_applier

        async def hold_reconciliation(snapshot, is_current):
            reconciliation_started.set()
            await allow_reconciliation.wait()
            await original_applier(snapshot, is_current)

        env.runtime.coordinator._snapshot_applier = hold_reconciliation

        async def remove_after_verified_intent(*args, **kwargs):
            nonlocal removed
            result = await original(*args, **kwargs)
            session = kwargs.get("session")
            if (
                not removed
                and session is not None
                and session.pulse_intent_at_utc is not None
                and session.pulse_commanded_at_utc is None
            ):
                removed = True
                assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
            return result

        env.runtime.store.async_update_controller_runtime = remove_after_verified_intent
        if mode == "auto":
            env.hass.states.async_set(SENSOR, "20")
        else:
            await env.controller.async_manual_start(60)
        await spin_until(lambda: reconciliation_started.is_set())
        await spin_until(
            lambda: env.controller.session is None,
            turns=200,
        )
        result = env.controller.last_on_authorization
        allow_reconciliation.set()
        await settle(env.hass)

        assert removed
        assert env.actuator.on_calls == 0
        assert result is not None and not result.authorized
        assert "current_subentry_exists" in result.failed_predicates
        _record, _history, summary = persisted_summary(env)
        assert summary is not None
        assert summary.reason is CompletionReason.CONFIG_CHANGED
        assert summary.runtime_s == 0

    async def test_nd8_delete_before_intent_prevents_session_and_on(self, command_env) -> None:
        env = command_env
        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        await spin_until(lambda: env.subentry_id not in env.runtime.controllers)
        env.hass.states.async_set(SENSOR, "20")
        await settle(env.hass)
        assert env.actuator.on_calls == 0
        assert env.controller.session is None

    async def test_unload_started_after_intent_before_final_gate_has_zero_on(
        self, command_env
    ) -> None:
        env = command_env
        original = env.runtime.store.async_update_controller_runtime
        unload_task = None

        async def begin_unload_after_verified_intent(*args, **kwargs):
            nonlocal unload_task
            result = await original(*args, **kwargs)
            session = kwargs.get("session")
            if (
                unload_task is None
                and session is not None
                and session.pulse_intent_at_utc is not None
                and session.pulse_commanded_at_utc is None
            ):
                unload_task = asyncio.create_task(env.runtime.async_unload())
                await spin_until(lambda: env.runtime.coordinator.stopping)
            return result

        env.runtime.store.async_update_controller_runtime = begin_unload_after_verified_intent
        env.hass.states.async_set(SENSOR, "20")
        await spin_until(lambda: unload_task is not None)
        await unload_task

        assert env.actuator.on_calls == 0
        _record, _history, summary = persisted_summary(env)
        assert summary is not None
        assert summary.reason is CompletionReason.CONFIG_RELOAD
        assert summary.runtime_s == 0

    @pytest.mark.parametrize(
        ("mutation", "reason"),
        (
            ("actuator_unavailable", CompletionReason.ACTUATOR_FAULT),
            ("ordinary_guard", CompletionReason.CONFIG_CHANGED),
        ),
    )
    async def test_live_gate_revocation_after_intent_terminates_zero_flow(
        self, command_env, mutation, reason
    ) -> None:
        env = command_env
        original = env.runtime.store.async_update_controller_runtime
        mutated = False

        async def mutate_after_verified_intent(*args, **kwargs):
            nonlocal mutated
            result = await original(*args, **kwargs)
            session = kwargs.get("session")
            if (
                not mutated
                and session is not None
                and session.pulse_intent_at_utc is not None
                and session.pulse_commanded_at_utc is None
            ):
                mutated = True
                if mutation == "actuator_unavailable":
                    env.hass.states.async_set(env.actuator.entity_id, "unavailable")
                else:
                    # A late ordinary guard revocation must terminate; a
                    # future freshness watchdog is not an applicable event.
                    env.controller._enabled = False
            return result

        env.runtime.store.async_update_controller_runtime = mutate_after_verified_intent
        env.hass.states.async_set(SENSOR, "20")
        await spin_until(lambda: mutated)
        await spin_until(lambda: env.controller.session is None, turns=200)

        assert mutated
        assert env.actuator.on_calls == 0
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is reason

    @pytest.mark.parametrize(
        ("mutation", "predicate"),
        (
            ("dirty", "reconciliation_admission_clear"),
            ("reconciling", "reconciliation_admission_clear"),
            ("failed", "reconciliation_admission_clear"),
            ("stopping", "reconciliation_admission_clear"),
            ("lifecycle", "runtime_lifecycle_active"),
            ("controller", "controller_commandable"),
            ("canonical", "canonical_ownership_matches"),
            ("intent", "verified_hazard_intent_matches"),
            ("slot", "slot_owned_by_session"),
            ("blocker", "keyed_blockers_clear"),
            ("actuator", "actuator_available_and_proven_off"),
            ("ordinary", "ordinary_runtime_guards"),
        ),
    )
    async def test_complete_gate_predicates_fail_closed(
        self, command_env, mutation, predicate
    ) -> None:
        env = command_env
        controller = env.controller
        controller._ensure_session_task = lambda: None
        env.hass.states.async_set(SENSOR, "20")
        await spin_until(
            lambda: (
                controller.session is not None
                and controller.session.pulse_intent_at_utc is not None
            )
        )

        if mutation == "dirty":
            env.runtime.coordinator.observe_current()
        elif mutation == "reconciling":
            env.runtime.coordinator.reconciling = True
        elif mutation == "failed":
            env.runtime.coordinator.failed = True
        elif mutation == "stopping":
            env.runtime.process_stopping = True
        elif mutation == "lifecycle":
            env.runtime.bindings[env.subentry_id].lifecycle = RuntimeLifecycle.DELETE_PENDING
        elif mutation == "controller":
            controller.begin_quiescing()
        elif mutation == "canonical":
            env.runtime.bindings[env.subentry_id].safety_record_id = "wrong-record"
        elif mutation == "intent":
            history = env.runtime.store.data.zone_histories[controller.zone_history_id]
            await env.runtime.store.async_update_controller_runtime(
                controller.safety_record_id,
                controller.zone_history_id,
                state=controller.state,
                enabled=controller.enabled,
                active_fault=controller.active_fault,
                secondary_fault=controller.secondary_fault,
                last_session_end_utc=controller.last_session_end,
                last_auto_session_start_utc=history.last_auto_session_start_utc,
                daily=controller.daily,
                last_session_summary=controller.last_summary,
                session=None,
                possible_flow_owner=None,
            )
        elif mutation == "slot":
            await env.runtime.slots.async_release(env.subentry_id)
        elif mutation == "blocker":
            await env.runtime.slots.async_add_blocker(
                controller.safety_record_id, BlockerReason.EXTERNAL_FLOW
            )
        elif mutation == "actuator":
            env.hass.states.async_set(env.actuator.entity_id, "unavailable")
        else:
            controller._enabled = False

        result = env.runtime.authorize_on(
            controller,
            controller.session.session_id,
            f"gate-{mutation}",
        )
        assert not result.authorized
        assert predicate in result.failed_predicates
        assert env.actuator.on_calls == 0

    async def test_valid_gate_token_is_exact_and_single_use(self, command_env) -> None:
        env = command_env
        controller = env.controller
        controller._ensure_session_task = lambda: None
        env.hass.states.async_set(SENSOR, "20")
        await spin_until(
            lambda: (
                controller.session is not None
                and controller.session.pulse_intent_at_utc is not None
            )
        )
        session = controller.session
        result = env.runtime.authorize_on(controller, session.session_id, "valid-attempt")
        assert result.authorized
        token = result.token
        assert token is not None
        assert token.safety_record_id == controller.safety_record_id
        assert token.zone_history_id == controller.zone_history_id
        assert token.session_id == session.session_id
        assert token.applied_generation == env.runtime.coordinator.applied_generation
        assert env.runtime.recheck_on_authorization(controller, token).authorized
        duplicate = env.runtime.authorize_on(
            controller,
            session.session_id,
            "valid-attempt",
        )
        assert not duplicate.authorized
        assert duplicate.failed_predicates == ("authorization_token_single_use",)
        env.runtime.finish_on_authorization(token)
        retired = env.runtime.recheck_on_authorization(controller, token)
        assert not retired.authorized
        assert "authorization_token_matches" in retired.failed_predicates

    async def test_snapshot_normalization_failure_refuses_authorization(self, command_env) -> None:
        env = command_env
        controller = env.controller
        controller._ensure_session_task = lambda: None
        env.hass.states.async_set(SENSOR, "20")
        await spin_until(lambda: controller.session is not None)

        def fail_snapshot(_generation):
            raise ValueError("injected current-snapshot failure")

        env.runtime._build_immutable_snapshot = fail_snapshot
        result = env.runtime.authorize_on(
            controller,
            controller.session.session_id,
            "snapshot-failure",
        )
        assert not result.authorized
        assert "current_entry_snapshot_matches" in result.failed_predicates
        assert "current_subentry_exists" in result.failed_predicates
        assert env.actuator.on_calls == 0


class TestDispatchAndCompensation:
    async def test_nd5_nd7_sensor_fault_manual_delete_retains_fault(self, command_env) -> None:
        env = command_env
        # Establish the retained sensor-only fault through a real AUTO exit,
        # then prove the MANUAL command envelope remains deletion-safe.
        await start_auto_inflight(env)
        env.actuator.allow_on.set()
        await spin_until(
            lambda: (
                env.controller.session is not None
                and env.controller.session.pulse_confirmed_at_utc is not None
            )
        )
        env.hass.states.async_set(SENSOR, "150")
        await spin_until(
            lambda: (
                env.controller.state is ControllerState.FAULT
                and env.controller.active_fault is FaultCode.SENSOR_INVALID
            )
        )
        assert env.actuator.off_calls == 1

        env.actuator.allow_on.clear()
        env.actuator.on_started.clear()
        await env.controller.async_manual_start(60)
        await spin_until(lambda: env.actuator.on_calls == 2 and env.actuator.on_started.is_set())

        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        await finish_reconciliation(env)

        assert env.actuator.on_calls == 2
        assert env.actuator.off_calls == 2
        _record, history, summary = persisted_summary(env)
        assert summary is not None
        assert summary.reason is CompletionReason.CONFIG_CHANGED
        assert history.zone_runtime.zone_fault is FaultCode.SENSOR_INVALID

    async def test_native_websocket_delete_returns_while_on_is_inflight(
        self,
        command_env,
        hass_access_token,
        socket_enabled,
    ) -> None:
        """ND1/ND11 use Core's real public 2025.9 subentry-delete route."""
        env = command_env
        assert await async_setup_component(env.hass, "websocket_api", {})
        assert await async_setup_component(env.hass, "config", {})
        loop = asyncio.get_running_loop()
        connector = TCPConnector(
            loop=loop,
            resolver=ThreadedResolver(loop=loop),
        )
        server = TestServer(env.hass.http.app, loop=loop)
        client = TestClient(server, loop=loop, connector=connector)
        await client.start_server()
        try:
            websocket = await client.ws_connect("/api/websocket")
            assert (await websocket.receive_json())["type"] == "auth_required"
            await websocket.send_json({"type": "auth", "access_token": hass_access_token})
            assert (await websocket.receive_json())["type"] == "auth_ok"

            await start_auto_inflight(env)
            marker = env.controller.inflight_on
            await websocket.send_json(
                {
                    "id": 1,
                    "type": "config_entries/subentries/delete",
                    "entry_id": env.entry.entry_id,
                    "subentry_id": env.subentry_id,
                }
            )
            response = await websocket.receive_json()
            assert response["success"]
            assert env.subentry_id not in env.entry.subentries
            assert marker is env.controller.inflight_on
            assert marker.outcome is OnCommandOutcome.IN_FLIGHT
            await finish_reconciliation(env)
            assert env.actuator.on_calls == 1
            assert env.actuator.off_calls == 1
            _record, _history, summary = persisted_summary(env)
            assert summary is not None
            assert summary.reason is CompletionReason.CONFIG_CHANGED
        finally:
            await client.close()

    async def test_nd10_no_yield_from_gate_to_dispatch_and_delete_inflight(
        self, command_env
    ) -> None:
        env = command_env
        loop = asyncio.get_running_loop()
        original = env.runtime.authorize_on

        def authorize_and_schedule_delete(controller, session_id, attempt_id):
            result = original(controller, session_id, attempt_id)
            if result.authorized:

                def delete_on_next_loop_turn() -> None:
                    env.actuator.order.append("delete_visible")
                    assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)

                loop.call_soon(delete_on_next_loop_turn)
            return result

        env.runtime.authorize_on = authorize_and_schedule_delete
        await start_auto_inflight(env)
        await spin_until(lambda: "delete_visible" in env.actuator.order)

        assert env.actuator.order[:2] == ["dispatch_started", "delete_visible"]
        assert env.actuator.on_calls == 1
        env.freezer.tick(10)
        await finish_reconciliation(env)
        assert env.actuator.off_calls == 1
        record, history, summary = persisted_summary(env)
        assert record.runtime_lifecycle is RuntimeLifecycle.RETIRED
        assert history.zone_runtime.session is None
        assert summary is not None and summary.reason is CompletionReason.CONFIG_CHANGED
        assert summary.runtime_estimated
        assert summary.runtime_s == pytest.approx(10.0)
        assert history.daily is not None
        assert history.daily.runtime_s == pytest.approx(10.0)

    async def test_nd11_raise_after_delete_is_uncertain_and_one_off(self, command_env) -> None:
        env = command_env
        env.actuator.raise_after_on = True
        await start_auto_inflight(env)
        marker = env.controller.inflight_on
        assert marker is not None
        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        await spin_until(lambda: not env.controller.command_authorization_open)
        await finish_reconciliation(env)

        assert marker.outcome is OnCommandOutcome.RAISED
        assert env.actuator.on_calls == 1
        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.CONFIG_CHANGED
        assert summary.runtime_estimated

    async def test_fingerprint_change_inflight_forbids_continuation(self, command_env) -> None:
        env = command_env
        await start_auto_inflight(env)
        subentry = env.entry.subentries[env.subentry_id]
        assert env.hass.config_entries.async_update_subentry(
            env.entry,
            subentry,
            data=zone_data(env.actuator.entity_id, name="Changed while dispatching"),
        )
        await spin_until(lambda: env.runtime.coordinator.dirty)
        await finish_reconciliation(env)

        assert env.actuator.on_calls == 1
        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.CONFIG_CHANGED

    async def test_snapshot_generation_supersession_invalidates_command_token(
        self, command_env
    ) -> None:
        env = command_env
        await start_auto_inflight(env)
        marker = env.controller.inflight_on
        assert marker is not None
        old_generation = marker.authorization.applied_generation
        env.runtime.coordinator.observe_current()
        await env.runtime.coordinator.async_reconcile()
        assert env.runtime.coordinator.applied_generation > old_generation
        env.actuator.allow_on.set()
        await spin_until(lambda: env.controller.session is None, turns=200)
        await settle(env.hass)

        result = env.controller.last_on_authorization
        assert result is not None and not result.authorized
        assert "authorization_token_matches" in result.failed_predicates
        assert env.controller.runtime_eligible
        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.CONFIG_CHANGED

    async def test_delete_after_return_before_command_persistence(self, command_env) -> None:
        env = command_env
        await start_auto_inflight(env)
        marker = env.controller.inflight_on
        assert marker is not None
        await env.controller._lock.acquire()
        env.actuator.allow_on.set()
        await spin_until(lambda: marker.outcome is OnCommandOutcome.RETURNED)
        env.actuator.order.append("delete_visible")
        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        env.controller._lock.release()
        await finish_reconciliation(env)

        assert env.actuator.order.index("off_started") > env.actuator.order.index("delete_visible")
        assert env.actuator.on_calls == 1
        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.CONFIG_CHANGED
        assert summary.runtime_estimated

    @pytest.mark.parametrize("phase", ("commanded", "confirmed"))
    async def test_config_removed_during_post_call_persistence_compensates(
        self, command_env, phase
    ) -> None:
        env = command_env
        original = env.runtime.store.async_update_controller_runtime
        removed = False

        async def remove_during_selected_write(*args, **kwargs):
            nonlocal removed
            result = await original(*args, **kwargs)
            session = kwargs.get("session")
            marker = env.controller.inflight_on
            if (
                phase == "confirmed"
                and marker is not None
                and marker.outcome is OnCommandOutcome.RETURNED
                and session is not None
                and session.pulse_commanded_at_utc is not None
                and session.pulse_confirmed_at_utc is None
            ):
                # Deterministically expose the matching-context terminal ON
                # acknowledgement before the controller consumes the
                # commanded write and enters its acknowledgement persistence.
                marker.observed_on_at_utc = dt_util.utcnow()
            selected = (
                phase == "commanded"
                and session is not None
                and session.pulse_commanded_at_utc is not None
                and session.pulse_confirmed_at_utc is None
            ) or (
                phase == "confirmed"
                and session is not None
                and session.pulse_confirmed_at_utc is not None
            )
            if (
                not removed
                and marker is not None
                and marker.outcome is OnCommandOutcome.RETURNED
                and selected
            ):
                removed = True
                assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
            return result

        env.runtime.store.async_update_controller_runtime = remove_during_selected_write
        await start_auto_inflight(env)
        env.actuator.allow_on.set()
        await finish_reconciliation(env)

        assert removed
        assert env.actuator.on_calls == 1
        assert env.actuator.off_calls == 1
        assert env.controller.session is None
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.CONFIG_CHANGED

    async def test_inflight_lifecycle_revocation_forbids_continuation(self, command_env) -> None:
        env = command_env
        await start_auto_inflight(env)
        binding = env.runtime.bindings[env.subentry_id]
        binding.lifecycle = RuntimeLifecycle.DELETE_PENDING
        binding.quiescing = True
        env.controller.update_runtime_ownership(
            zone_history_id=binding.zone_history_id,
            lifecycle=RuntimeLifecycle.DELETE_PENDING,
            applied_config=binding.applied_shadow,
        )
        env.actuator.allow_on.set()
        await spin_until(lambda: env.controller.session is None, turns=200)

        result = env.controller.last_on_authorization
        assert result is not None and not result.authorized
        assert "runtime_lifecycle_active" in result.failed_predicates
        assert env.actuator.on_calls == 1
        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.CONFIG_CHANGED

    async def test_t25_second_pulse_rechecks_deleted_configuration(self, command_env) -> None:
        env = command_env
        await start_auto_inflight(env)
        env.actuator.allow_on.set()
        await spin_until(
            lambda: (
                env.controller.session is not None
                and env.controller.session.pulse_confirmed_at_utc is not None
            )
        )
        first = env.controller.session
        env.freezer.move_to(first.pulse_ends_at_utc)
        await env.controller.async_dispatch(PulseDeadlineReached())
        await spin_until(lambda: env.controller.state is ControllerState.SOAKING)
        soaking = env.controller.session
        env.freezer.move_to(soaking.soak_ends_at_utc)
        await env.controller.async_dispatch(SoakDeadlineReached())

        original = env.runtime.store.async_update_controller_runtime
        original_applier = env.runtime.coordinator._snapshot_applier
        reconciliation_started = asyncio.Event()
        allow_reconciliation = asyncio.Event()
        removed = False

        async def hold_reconciliation(snapshot, is_current):
            reconciliation_started.set()
            await allow_reconciliation.wait()
            await original_applier(snapshot, is_current)

        async def remove_on_second_intent(*args, **kwargs):
            nonlocal removed
            result = await original(*args, **kwargs)
            session = kwargs.get("session")
            if (
                not removed
                and session is not None
                and session.cycle == 2
                and session.pulse_intent_at_utc is not None
                and session.pulse_commanded_at_utc is None
            ):
                removed = True
                assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
            return result

        env.runtime.coordinator._snapshot_applier = hold_reconciliation
        env.runtime.store.async_update_controller_runtime = remove_on_second_intent
        env.hass.states.async_set(SENSOR, "25")
        await spin_until(lambda: reconciliation_started.is_set())
        await spin_until(lambda: env.controller.session is None, turns=200)
        result = env.controller.last_on_authorization
        allow_reconciliation.set()
        await settle(env.hass)

        assert removed
        assert result is not None and "current_subentry_exists" in result.failed_predicates
        assert env.actuator.on_calls == 1
        assert env.actuator.off_calls == 2
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.CONFIG_CHANGED

    async def test_reconciliation_failure_during_dispatch_compensates(self, command_env) -> None:
        env = command_env
        await start_auto_inflight(env)
        env.runtime.coordinator.failed = True
        env.runtime.coordinator.dirty = True
        env.runtime.slots.set_reconciliation_state_now(dirty=True, failed=True)
        env.actuator.allow_on.set()
        await spin_until(lambda: env.controller.session is None, turns=200)
        await settle(env.hass)
        result = env.controller.last_on_authorization
        assert result is not None and not result.authorized
        assert "reconciliation_admission_clear" in result.failed_predicates
        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.CONFIG_CHANGED

    async def test_freshness_expires_during_service_without_queued_callback(
        self, command_env
    ) -> None:
        env = command_env
        await start_auto_inflight(env)
        watchdog = env.controller.armed_watchdog
        assert watchdog is not None
        env.freezer.move_to(watchdog.deadline_utc)
        env.actuator.allow_on.set()
        await spin_until(lambda: env.controller.session is None, turns=200)
        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.SENSOR_FAULT

    async def test_external_state_during_marker_is_not_accepted_as_own_ack(
        self, command_env
    ) -> None:
        env = command_env
        await start_auto_inflight(env)
        marker = env.controller.inflight_on
        assert marker is not None
        terminal = "on" if env.actuator.domain == "switch" else "open"
        env.hass.states.async_set(env.actuator.entity_id, terminal)
        for _ in range(10):
            await asyncio.sleep(0)
        assert marker.observed_on_at_utc is None
        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        await finish_reconciliation(env)
        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.CONFIG_CHANGED


class TestInflightLifecycle:
    async def test_forced_cancellation_during_command_persistence_uses_shared_off(
        self, command_env
    ) -> None:
        env = command_env
        original = env.runtime.store.async_update_controller_runtime
        command_write_started = asyncio.Event()
        hold_command_write = asyncio.Event()

        async def hold_commanded_write(*args, **kwargs):
            session = kwargs.get("session")
            if (
                session is not None
                and session.pulse_commanded_at_utc is not None
                and session.pulse_confirmed_at_utc is None
            ):
                command_write_started.set()
                await hold_command_write.wait()
            return await original(*args, **kwargs)

        env.runtime.store.async_update_controller_runtime = hold_commanded_write
        await start_auto_inflight(env)
        env.actuator.allow_on.set()
        await spin_until(lambda: command_write_started.is_set())
        task = env.controller.session_owner_task
        assert task is not None and not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert env.actuator.on_calls == 1
        assert env.actuator.off_calls == 1
        assert env.controller.inflight_on is None
        assert env.controller.session is None
        _record, _history, summary = persisted_summary(env)
        assert summary is not None
        assert summary.reason is CompletionReason.ACTUATOR_FAULT
        assert summary.runtime_estimated

    async def test_generic_unload_during_on_call_joins_compensation(self, command_env) -> None:
        env = command_env
        await start_auto_inflight(env)
        unload = asyncio.create_task(env.runtime.async_unload())
        await spin_until(
            lambda: (
                env.controller.session.pending_termination_reason is CompletionReason.CONFIG_RELOAD
            )
        )
        env.actuator.allow_on.set()
        await unload
        assert env.actuator.on_calls == 1
        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.CONFIG_RELOAD

    async def test_shutdown_during_on_call_preserves_first_reason(self, command_env) -> None:
        env = command_env
        await start_auto_inflight(env)
        shutdown = asyncio.create_task(env.runtime.async_handle_ha_stop(None))
        await spin_until(
            lambda: (
                env.controller.session.pending_termination_reason
                is CompletionReason.HOME_ASSISTANT_SHUTDOWN
            )
        )
        env.actuator.allow_on.set()
        await shutdown
        assert env.actuator.on_calls == 1
        assert env.actuator.off_calls == 1
        assert env.runtime.store.data.run.previous_run_was_clean
        _record, _history, summary = persisted_summary(env)
        assert summary is not None
        assert summary.reason is CompletionReason.HOME_ASSISTANT_SHUTDOWN

    async def test_shutdown_cancellation_fallback_keeps_possible_flow_owned(
        self, command_env
    ) -> None:
        env = command_env
        await start_auto_inflight(env)
        marker = env.controller.inflight_on
        assert marker is not None
        env.runtime.shutdown_off_budget_s = 0
        await env.runtime.async_handle_ha_stop(None)
        assert marker.outcome is OnCommandOutcome.CANCELLED
        assert env.actuator.on_calls == 1
        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None
        assert summary.reason is CompletionReason.HOME_ASSISTANT_SHUTDOWN
        assert summary.runtime_estimated


class TestTerminalAndOffRaces:
    @pytest.mark.parametrize(
        ("terminal", "reason"),
        (
            ("stop", CompletionReason.USER_STOP),
            ("disable", CompletionReason.ZONE_DISABLED),
            ("sensor", CompletionReason.SENSOR_FAULT),
        ),
    )
    async def test_terminal_before_delete_wins_and_uses_one_off(
        self, command_env, terminal, reason
    ) -> None:
        env = command_env
        await start_auto_inflight(env)
        if terminal == "stop":
            await env.controller.async_dispatch(StopRequested())
        elif terminal == "disable":
            await env.controller.async_dispatch(DisableRequested())
        else:
            env.hass.states.async_set(SENSOR, "invalid")
            await spin_until(
                lambda: (
                    env.controller.session.pending_termination_reason
                    is CompletionReason.SENSOR_FAULT
                )
            )
        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        await finish_reconciliation(env)

        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is reason

    async def test_delete_before_stop_owns_reason_and_stale_callbacks_noop(
        self, command_env
    ) -> None:
        env = command_env
        await start_auto_inflight(env)
        watchdog = env.controller.armed_watchdog
        assert watchdog is not None
        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        await spin_until(
            lambda: (
                env.controller.session.pending_termination_reason is CompletionReason.CONFIG_CHANGED
            )
        )
        assert (await env.controller.async_dispatch(StopRequested())).no_op
        await finish_reconciliation(env)
        calls = env.actuator.on_calls
        assert (await env.controller.async_dispatch(PulseDeadlineReached())).no_op
        assert (await env.controller.async_dispatch(WatchdogFired(watchdog))).no_op
        stale_grant = await env.controller.async_dispatch(SlotGranted())
        assert stale_grant.transition_id == "T2"
        assert all(type(action).__name__ != "TurnOn" for action in stale_grant.actions)
        assert env.actuator.on_calls == calls
        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.CONFIG_CHANGED

    async def test_watchdog_before_delete_retains_sensor_fault_reason(self, command_env) -> None:
        env = command_env
        await start_auto_inflight(env)
        watchdog = env.controller.armed_watchdog
        assert watchdog is not None
        env.freezer.move_to(watchdog.deadline_utc)
        await env.controller.async_dispatch(WatchdogFired(watchdog))
        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        await finish_reconciliation(env)
        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.SENSOR_FAULT

    async def test_delete_joins_off_already_in_progress(self, command_env) -> None:
        env = command_env
        await start_auto_inflight(env)
        env.actuator.allow_on.set()
        await spin_until(
            lambda: (
                env.controller.session is not None
                and env.controller.session.pulse_confirmed_at_utc is not None
            )
        )
        env.actuator.allow_off.clear()
        await env.controller.async_dispatch(StopRequested())
        await spin_until(lambda: env.actuator.off_started.is_set())
        operation = env.controller.off_operation
        assert operation is not None and not operation.done()
        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        await spin_until(lambda: not env.controller.command_authorization_open)
        assert env.controller.off_operation is operation
        env.actuator.allow_off.set()
        await finish_reconciliation(env)
        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.USER_STOP

    async def test_delete_while_off_retry_waits_uses_delayed_exact_proof(self, command_env) -> None:
        env = command_env
        await start_auto_inflight(env)
        env.actuator.allow_on.set()
        await spin_until(
            lambda: (
                env.controller.session is not None
                and env.controller.session.pulse_confirmed_at_utc is not None
            )
        )
        env.actuator.off_behavior = "silent"
        await env.controller.async_dispatch(StopRequested())
        await spin_until(lambda: env.actuator.off_started.is_set())
        operation = env.controller.off_operation
        assert operation is not None and not operation.done()
        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        env.actuator.prove_off()
        await finish_reconciliation(env)
        assert env.controller.off_operation is operation
        assert env.actuator.off_calls == 1
        _record, _history, summary = persisted_summary(env)
        assert summary is not None and summary.reason is CompletionReason.USER_STOP

    async def test_unconfirmed_delete_keeps_exact_blocker_slot_and_open_accounting(
        self, command_env
    ) -> None:
        env = command_env
        await start_auto_inflight(env)
        record_id = env.controller.safety_record_id
        # Keep this test on the normal three-attempt path; separate lifecycle
        # tests cover exhaustion of the unchanged eight-second teardown budget.
        env.runtime.shutdown_off_budget_s = 1_000
        env.actuator.off_behavior = "silent"
        assert env.hass.config_entries.async_remove_subentry(env.entry, env.subentry_id)
        env.actuator.allow_on.set()
        await spin_until(lambda: env.actuator.off_calls == 1)
        for expected_calls in (2, 3):
            env.freezer.tick(30)
            async_fire_time_changed(env.hass, dt_util.utcnow())
            await spin_until(lambda expected=expected_calls: env.actuator.off_calls == expected)
        env.freezer.tick(30)
        async_fire_time_changed(env.hass, dt_util.utcnow())
        await spin_until(
            lambda: (
                (
                    record_id,
                    BlockerReason.INTEGRATION_OFF_UNCONFIRMED,
                )
                in env.runtime.slots.blockers()
            ),
            turns=200,
        )
        await settle(env.hass)
        assert (
            env.runtime.store.data.safety_records[record_id].runtime_lifecycle
            is RuntimeLifecycle.DELETE_PENDING
        ), (
            env.runtime.coordinator.dirty,
            env.runtime.coordinator.reconciling,
            env.runtime.coordinator.failed,
            env.runtime.coordinator.last_error,
        )

        record = env.runtime.store.data.safety_records[record_id]
        history = env.runtime.store.data.zone_histories[record.zone_history_id]
        assert record.runtime_lifecycle is RuntimeLifecycle.DELETE_PENDING
        assert record.possible_flow_owner is not None
        assert record.possible_flow_owner.value == "integration"
        assert history.zone_runtime.session is not None
        assert env.runtime.slots.owner == env.subentry_id
        blockers = env.runtime.slots.blockers()
        assert (record_id, BlockerReason.INTEGRATION_OFF_UNCONFIRMED) in blockers
        assert {owner for owner, _reason in blockers} == {record_id}

        env.actuator.prove_off()
        await spin_until(
            lambda: (
                (
                    record_id,
                    BlockerReason.INTEGRATION_OFF_UNCONFIRMED,
                )
                not in env.runtime.slots.blockers()
            ),
            turns=200,
        )
        history = env.runtime.store.data.zone_histories[record.zone_history_id]
        assert history.zone_runtime.session is None
        assert env.runtime.slots.owner is None
        assert env.runtime.slots.blockers() == frozenset()

    async def test_same_record_reactivation_retains_unconfirmed_open_accounting(
        self, command_env
    ) -> None:
        env = command_env
        await start_auto_inflight(env)
        record_id = env.controller.safety_record_id
        original = env.runtime.store.data.safety_records[record_id]
        lineage_id = original.safety_lineage_id
        history_id = original.zone_history_id
        old_subentry_id = env.subentry_id
        config = dict(env.entry.subentries[old_subentry_id].data)

        env.runtime.shutdown_off_budget_s = 1_000
        env.actuator.off_behavior = "silent"
        assert env.hass.config_entries.async_remove_subentry(env.entry, old_subentry_id)
        env.actuator.allow_on.set()
        await spin_until(lambda: env.actuator.off_calls == 1)
        for expected_calls in (2, 3):
            env.freezer.tick(30)
            async_fire_time_changed(env.hass, dt_util.utcnow())
            await spin_until(lambda expected=expected_calls: env.actuator.off_calls == expected)
        env.freezer.tick(30)
        async_fire_time_changed(env.hass, dt_util.utcnow())
        await spin_until(
            lambda: (
                (record_id, BlockerReason.INTEGRATION_OFF_UNCONFIRMED)
                in env.runtime.slots.blockers()
            ),
            turns=200,
        )
        await settle(env.hass)

        tombstone = env.runtime.store.data.safety_records[record_id]
        tombstone_history = env.runtime.store.data.zone_histories[history_id]
        assert tombstone.runtime_lifecycle is RuntimeLifecycle.DELETE_PENDING
        assert tombstone.acknowledgement_required
        assert tombstone.possible_flow_owner is not None
        assert tombstone_history.zone_runtime.session is not None
        open_session_id = tombstone_history.zone_runtime.session.context.session_id

        env.hass.states.async_set(SENSOR, "35")
        readded_id = f"stage4-reactivated-{env.actuator.domain}"
        assert env.hass.config_entries.async_add_subentry(
            env.entry,
            ConfigSubentry(
                data=MappingProxyType(config),
                subentry_id=readded_id,
                subentry_type="zone",
                title="Reactivated safety record",
                unique_id=None,
            ),
        )
        await settle(env.hass)

        active = env.runtime.store.data.safety_records[record_id]
        history = env.runtime.store.data.zone_histories[history_id]
        reactivated = env.runtime.controllers[readded_id]
        assert active.runtime_lifecycle is RuntimeLifecycle.ACTIVE
        assert active.active_subentry_id == readded_id
        assert active.safety_record_id == record_id
        assert active.safety_lineage_id == lineage_id
        assert active.zone_history_id == history_id
        assert active.acknowledgement_required
        assert active.possible_flow_owner is not None
        assert (
            record_id,
            BlockerReason.INTEGRATION_OFF_UNCONFIRMED,
        ) in env.runtime.slots.blockers()
        assert history.zone_runtime.session is not None
        assert history.zone_runtime.session.context.session_id == open_session_id
        assert history.zone_runtime.sensor_identity.last_known_entity_id == SENSOR
        assert history.zone_runtime.zone_fault is None
        assert history.zone_runtime.state not in (
            ControllerState.WATERING,
            ControllerState.SOAKING,
        )
        assert reactivated.state not in (
            ControllerState.WATERING,
            ControllerState.SOAKING,
        )
        assert reactivated.off_operation is None

        env.actuator.prove_off()
        await spin_until(
            lambda: (
                (record_id, BlockerReason.INTEGRATION_OFF_UNCONFIRMED)
                not in env.runtime.slots.blockers()
            ),
            turns=200,
        )
        assert env.runtime.store.data.safety_records[record_id].acknowledgement_required
