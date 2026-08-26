"""Slice 7 tests: zone runtime controller (§§11, 16-22; SR/MF/AC/ER groups).

HA-harness suite with scripted mock switch and valve actuators, frozen time
(pytest-freezer + async_fire_time_changed), and deterministic task/timer
sequencing. No real sleeps. Skips cleanly in the pure environment.
"""

from __future__ import annotations

from datetime import UTC, timedelta
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.moisture_loop.models import (
    ActuatorIdentity,
    AppliedConfigurationShadow,
    AppliedEntityIdentity,
    BlockerReason,
    CompletionReason,
    ControllerState,
    FaultCode,
    IdentityStatus,
    ManualClampReason,
    NormalizedZoneSettings,
    RuntimeLifecycle,
    SafetyRecord,
    SensorIdentity,
    SessionMode,
    ZoneConfig,
    ZoneDailyRuntime,
    ZoneHistory,
    ZoneRuntime,
)
from custom_components.moisture_loop.reconciliation import (
    FinalOnAuthorizationResult,
    FinalOnAuthorizationToken,
)
from custom_components.moisture_loop.slot_manager import SlotManager
from custom_components.moisture_loop.storage import (
    SafetyStore,
    StoreWriteVerificationError,
)
from custom_components.moisture_loop.zone_controller import (
    ActuatorAdapter,
    ZoneController,
)

GEN = "11111111-2222-3333-4444-555555555555"
ZONE = "zone-1"
SENSOR = "sensor.moisture_1"
SWITCH = "switch.valve_1"
VALVE = "valve.valve_1"
START_AT = "2026-08-21 12:00:00+00:00"

CONFIG = ZoneConfig(
    name="Front bed",
    moisture_sensor=SENSOR,
    actuator=SWITCH,
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

# Short freshness horizon so the AUTO watchdog fires inside one pulse.
WATCHDOG_CONFIG = ZoneConfig(
    name="Front bed",
    moisture_sensor=SENSOR,
    actuator=SWITCH,
    start_threshold=30.0,
    target_threshold=40.0,
    pulse_duration_s=1800,
    soak_duration_s=1200,
    max_cycles=4,
    max_session_runtime_s=1800,
    max_daily_runtime_s=3600,
    min_session_interval_s=900,
    sensor_max_age_s=300,
    actuator_confirm_timeout_s=30,
    manual_max_duration_s=1800,
)

VALVE_CONFIG = ZoneConfig(
    name="Front bed",
    moisture_sensor=SENSOR,
    actuator=VALVE,
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


class ScriptedSwitch:
    """Mock switch whose services acknowledge, stay silent, or misbehave."""

    def __init__(self, hass) -> None:
        self.hass = hass
        self.on_calls = 0
        self.off_calls = 0
        self.on_behavior = "ack"  # ack | silent
        self.off_behavior = "ack"
        hass.states.async_set(SWITCH, "off")

        async def turn_on(call) -> None:
            self.on_calls += 1
            if self.on_behavior == "error":
                raise RuntimeError("scripted ON failure")
            if self.on_behavior == "ack":
                hass.states.async_set(SWITCH, "on", context=call.context)

        async def turn_off(call) -> None:
            self.off_calls += 1
            if self.off_behavior == "error":
                raise RuntimeError("scripted OFF failure")
            if self.off_behavior == "ack":
                hass.states.async_set(SWITCH, "off", context=call.context)

        hass.services.async_register("switch", "turn_on", turn_on)
        hass.services.async_register("switch", "turn_off", turn_off)

    def set_state(self, state: str) -> None:
        self.hass.states.async_set(SWITCH, state)


class ScriptedValve:
    """Mock valve with transitional states and position semantics."""

    def __init__(self, hass) -> None:
        self.hass = hass
        self.open_calls = 0
        self.close_calls = 0
        hass.states.async_set(VALVE, "closed", {"current_position": 0})

        async def open_valve(call) -> None:
            self.open_calls += 1
            hass.states.async_set(
                VALVE,
                "opening",
                {"current_position": 10},
                context=call.context,
            )

        async def close_valve(call) -> None:
            self.close_calls += 1
            hass.states.async_set(
                VALVE,
                "closing",
                {"current_position": 10},
                context=call.context,
            )

        hass.services.async_register("valve", "open_valve", open_valve)
        hass.services.async_register("valve", "close_valve", close_valve)

    def set_state(self, state: str, position: int | None = None) -> None:
        attrs = {} if position is None else {"current_position": position}
        self.hass.states.async_set(VALVE, state, attrs)


class ControllerTestAuthorization:
    """Explicit unit-test authority; production always uses EntryRuntime."""

    def __init__(self) -> None:
        self.tokens: dict[str, FinalOnAuthorizationToken] = {}
        self.pre_dispatch_failures: tuple[str, ...] = ()
        self.post_dispatch_failures: tuple[str, ...] = ()
        self.configuration_authority_valid = True

    def authorize_on(self, controller, session_id, command_attempt_id):
        if self.pre_dispatch_failures:
            return FinalOnAuthorizationResult(
                token=None,
                failed_predicates=self.pre_dispatch_failures,
                configuration_authority_valid=self.configuration_authority_valid,
            )
        applied = controller.applied_config
        assert applied is not None
        token = FinalOnAuthorizationToken(
            subentry_id=controller.zone_id,
            safety_record_id=controller.safety_record_id,
            zone_history_id=controller.zone_history_id,
            session_id=session_id,
            command_attempt_id=command_attempt_id,
            applied_generation=applied.applied_generation,
            zone_config_fingerprint=applied.config_fingerprint,
            entry_snapshot_fingerprint=applied.entry_snapshot_fingerprint,
        )
        self.tokens[command_attempt_id] = token
        return FinalOnAuthorizationResult(token=token, configuration_authority_valid=True)

    def recheck_on_authorization(self, controller, token):
        if self.post_dispatch_failures:
            return FinalOnAuthorizationResult(
                token=None,
                failed_predicates=self.post_dispatch_failures,
                configuration_authority_valid=self.configuration_authority_valid,
            )
        if self.tokens.get(token.command_attempt_id) != token:
            return FinalOnAuthorizationResult(
                token=None,
                failed_predicates=("authorization_token_matches",),
                configuration_authority_valid=False,
            )
        return FinalOnAuthorizationResult(token=token, configuration_authority_valid=True)

    def finish_on_authorization(self, token):
        if self.tokens.get(token.command_attempt_id) == token:
            self.tokens.pop(token.command_attempt_id, None)


async def build_env(
    hass,
    freezer,
    config=CONFIG,
    actuator_cls=ScriptedSwitch,
    safety_record_id: str | None = None,
):
    freezer.move_to(START_AT)
    store = SafetyStore(hass, "entry-1", GEN)
    await store.async_first_initialize()
    record_id = safety_record_id or ZONE
    actuator_domain = config.actuator.split(".", 1)[0]
    history_id = f"{record_id}-history"
    applied = AppliedConfigurationShadow(
        subentry_id=ZONE,
        config_fingerprint=f"test-{record_id}",
        entry_snapshot_fingerprint=f"test-entry-{record_id}",
        applied_generation=1,
        normalized_settings=NormalizedZoneSettings.from_config(config),
        sensor_identity=AppliedEntityIdentity(None, config.moisture_sensor, "sensor"),
        actuator_identity=AppliedEntityIdentity(None, config.actuator, actuator_domain),
    )
    history = ZoneHistory(
        zone_history_id=history_id,
        active_subentry_id=ZONE,
        previous_subentry_ids=(),
        last_session_end_utc=None,
        last_auto_session_start_utc=None,
        zone_runtime=ZoneRuntime(
            enabled=True,
            state=ControllerState.IDLE,
            zone_fault=None,
            secondary_fault=None,
            sensor_identity=SensorIdentity(None, config.moisture_sensor),
            last_session_summary=None,
            session=None,
        ),
        daily=ZoneDailyRuntime(dt_util.utcnow().date(), 0.0),
    )
    record = SafetyRecord(
        safety_record_id=record_id,
        zone_id=ZONE,
        active_subentry_id=ZONE,
        previous_subentry_ids=(),
        safety_lineage_id=f"{record_id}-lineage",
        zone_history_id=history_id,
        historical_zone_history_ids=(),
        runtime_lifecycle=RuntimeLifecycle.ACTIVE,
        applied_config=applied,
        actuator_identity=ActuatorIdentity(
            registry_entry_id=None,
            last_known_entity_id=config.actuator,
            domain=actuator_domain,
            identity_status=IdentityStatus.REGISTRY_UNAVAILABLE,
            off_service=("switch.turn_off" if actuator_domain == "switch" else "valve.close_valve"),
            confirm_timeout_s=config.actuator_confirm_timeout_s,
        ),
        blocker_reasons=(),
        possible_flow_owner=None,
        identity_incident=None,
        actuator_fault=None,
        acknowledgement_required=False,
    )
    await store.async_reconcile(
        lambda data: (
            {**data.safety_records, record_id: record},
            {**data.zone_histories, history_id: history},
        )
    )
    slots = SlotManager()
    await slots.async_enable_grants()
    actuator = actuator_cls(hass)
    await hass.async_block_till_done()
    events: list[tuple[str, dict]] = []
    authorization = ControllerTestAuthorization()
    ctrl = ZoneController(
        hass,
        ZONE,
        config,
        store,
        slots,
        run_id="run-1",
        local_tz=UTC,
        authorization=authorization,
        emit=lambda kind, payload: events.append((kind, dict(payload))),
        safety_record_id=record_id,
    )
    ctrl.async_attach()
    await hass.async_block_till_done()
    return SimpleNamespace(
        hass=hass,
        freezer=freezer,
        store=store,
        slots=slots,
        actuator=actuator,
        ctrl=ctrl,
        events=events,
        authorization=authorization,
    )


@pytest.fixture
async def env(hass, hass_storage, freezer):
    e = await build_env(hass, freezer)
    yield e
    await e.ctrl.async_detach()


@pytest.fixture
async def wenv(hass, hass_storage, freezer):
    e = await build_env(hass, freezer, config=WATCHDOG_CONFIG)
    yield e
    await e.ctrl.async_detach()


@pytest.fixture
async def venv(hass, hass_storage, freezer):
    e = await build_env(hass, freezer, config=VALVE_CONFIG, actuator_cls=ScriptedValve)
    yield e
    await e.ctrl.async_detach()


async def settle(e, cycles: int = 10) -> None:
    """Drain tracked tasks and let background chains progress.

    The session-owner and slot-wait tasks are HA background tasks (they live
    for a whole session), so ``async_block_till_done`` alone cannot wait for
    their next step; a fixed number of loop passes settles every cascade
    deterministically without real sleeps.
    """
    import asyncio

    for _ in range(cycles):
        await asyncio.sleep(0)
        await e.hass.async_block_till_done()


async def advance(e, seconds: float) -> None:
    e.freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(e.hass, dt_util.utcnow())
    await settle(e)


async def set_moisture(e, value: str) -> None:
    e.hass.states.async_set(SENSOR, value)
    await settle(e)


def event_kinds(e) -> list[str]:
    return [kind for kind, _ in e.events]


class TestNormalAutoSession:
    async def test_full_session_pulse_soak_recheck_target(self, env) -> None:
        await set_moisture(env, "27")
        # T1: intent persisted, ON commanded and confirmed.
        assert env.ctrl.state is ControllerState.WATERING
        assert env.actuator.on_calls == 1
        session = env.ctrl.session
        assert session is not None and session.cycle == 1
        assert session.pulse_confirmed_at_utc is not None
        assert env.slots.owner == ZONE
        assert "session_started" in event_kinds(env)

        # Pulse deadline -> one OFF -> SOAKING (T6).
        await advance(env, 300)
        assert env.ctrl.state is ControllerState.SOAKING
        assert env.actuator.off_calls == 1
        assert env.slots.owner is None  # released; requeues at recheck
        assert env.ctrl.daily.runtime_s == pytest.approx(300.0)

        # Pre-deadline report updates observability only (T22).
        await set_moisture(env, "35")
        assert env.ctrl.state is ControllerState.SOAKING

        # Soak deadline without a qualifying report arms grace (T23).
        await advance(env, 1200)
        assert env.ctrl.state is ControllerState.SOAKING

        # A fresh post-deadline report below target starts pulse 2 (T25).
        await set_moisture(env, "35")
        assert env.ctrl.state is ControllerState.WATERING
        assert env.ctrl.session is not None and env.ctrl.session.cycle == 2
        assert env.actuator.on_calls == 2

        # Pulse 2 OFF, soak, then a target-reaching report completes (T24).
        await advance(env, 300)
        assert env.ctrl.state is ControllerState.SOAKING
        await advance(env, 1200)
        await set_moisture(env, "45")
        assert env.ctrl.state is ControllerState.IDLE
        assert env.ctrl.session is None
        summary = env.ctrl.last_summary
        assert summary is not None
        assert summary.reason.value == "target_reached"
        assert summary.cycles == 2
        assert summary.moisture_before == 27.0
        assert summary.moisture_after == 45.0
        assert not summary.runtime_estimated
        assert summary.runtime_s == pytest.approx(600.0)
        assert env.ctrl.daily.runtime_s == pytest.approx(600.0)
        assert env.ctrl.last_session_end is not None
        assert event_kinds(env).count("session_finished") == 1
        assert event_kinds(env).count("session_started") == 1

        # Canonical schema-2 history/runtime owns the finished summary.
        history = env.store.data.zone_histories[env.ctrl.zone_history_id]
        assert history.zone_runtime.state is ControllerState.IDLE
        assert history.zone_runtime.session is None
        assert history.zone_runtime.last_session_summary is not None
        assert history.daily is not None and history.daily.runtime_s == pytest.approx(600.0)

    async def test_min_interval_blocks_immediate_restart(self, env) -> None:
        await set_moisture(env, "27")
        await env.ctrl.async_stop_watering()
        await settle(env)
        assert env.ctrl.state is ControllerState.IDLE
        # A new dry report right away is refused by G-INT.
        decision = await env.ctrl.async_evaluate()
        assert decision.transition_id == "T2"
        assert decision.guard_result is not None
        assert "G-INT" in decision.guard_result.failed_guards

    async def test_no_duplicate_session_from_report_bursts(self, env) -> None:
        await set_moisture(env, "27")
        assert env.actuator.on_calls == 1
        for _ in range(3):
            await set_moisture(env, "26")  # changed reports during WATERING
        assert env.actuator.on_calls == 1  # T56 refreshes; no second ON
        assert event_kinds(env).count("session_started") == 1


class TestOnSequence:
    async def test_stage4_live_session_uses_only_canonical_schema2_writes(self, env) -> None:
        assert not hasattr(env.store, "async_update_record_runtime")
        assert not hasattr(env.store, "async_update_zone")
        await set_moisture(env, "27")
        assert env.actuator.on_calls == 1
        await env.ctrl.async_stop_watering()
        await settle(env)
        history = env.store.data.zone_histories[env.ctrl.zone_history_id]
        assert history.zone_runtime.session is None
        assert history.zone_runtime.last_session_summary is not None
        assert history.zone_runtime.last_session_summary.reason is CompletionReason.USER_STOP

    async def test_on_timeout_faults_after_defensive_off(self, env) -> None:
        env.actuator.on_behavior = "silent"
        await set_moisture(env, "27")
        assert env.ctrl.state is ControllerState.WATERING
        assert env.actuator.on_calls == 1
        # Confirmation window expires (§11.2 step 7).
        await advance(env, 30)
        # Defensive OFF acknowledged -> T14.
        assert env.ctrl.state is ControllerState.FAULT
        assert env.ctrl.active_fault is FaultCode.ACTUATOR_ON_TIMEOUT
        assert env.actuator.off_calls >= 1
        assert env.ctrl.last_session_end is not None  # interval reset (§19.4)

    async def test_write_ahead_gate_no_on_after_persist_failure(self, env) -> None:
        async def failing_update(*args, **kwargs):
            raise StoreWriteVerificationError("injected")

        env.store.async_update_controller_runtime = failing_update  # type: ignore[method-assign]
        await set_moisture(env, "27")
        assert env.actuator.on_calls == 0  # ON never issued (I15)
        assert env.ctrl.state is ControllerState.FAULT
        assert env.ctrl.active_fault is FaultCode.RESTORED_FROM_UNSAFE_STATE

    async def test_pre_on_freshness_recheck_aborts_stale_start(
        self, hass, hass_storage, freezer
    ) -> None:
        e = await build_env(hass, freezer, config=WATCHDOG_CONFIG)
        original = e.store.async_update_controller_runtime
        calls = 0

        async def slow_first_persist(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                # Verified write-ahead persistence consumes more time than
                # the freshness horizon (§18.1/§18.5).
                e.freezer.tick(timedelta(seconds=400))
            return await original(*args, **kwargs)

        e.store.async_update_controller_runtime = slow_first_persist  # type: ignore[method-assign]
        await set_moisture(e, "27")
        assert e.actuator.on_calls == 0  # ON was never issued
        assert e.ctrl.state is ControllerState.FAULT
        assert e.ctrl.active_fault is FaultCode.SENSOR_STALE
        await e.ctrl.async_detach()


class TestWatchdog:
    async def test_sr5_freshness_expiry_stops_flowing_auto(self, wenv) -> None:
        await set_moisture(wenv, "27")  # report at T0; fresh until T0+300
        assert wenv.ctrl.state is ControllerState.WATERING
        assert wenv.actuator.on_calls == 1
        # No further report: the watchdog commits at the deadline, far
        # before the 30-minute pulse end.
        await advance(wenv, 300)
        assert wenv.ctrl.state is ControllerState.FAULT
        assert wenv.ctrl.active_fault is FaultCode.SENSOR_STALE
        assert wenv.actuator.off_calls == 1
        # The session never resumes (I13/I30).
        await advance(wenv, 1500)
        assert wenv.actuator.on_calls == 1
        summary = wenv.ctrl.last_summary
        assert summary is not None and summary.reason.value == "sensor_fault"

    async def test_sr6_identical_report_extends_deadline(self, wenv) -> None:
        await set_moisture(wenv, "27")
        first_token = wenv.ctrl.armed_watchdog
        assert first_token is not None
        await advance(wenv, 200)  # before expiry
        await set_moisture(wenv, "27")  # identical -> state_reported
        second_token = wenv.ctrl.armed_watchdog
        assert second_token is not None
        assert second_token.generation == first_token.generation + 1
        assert second_token.deadline_utc == first_token.deadline_utc + timedelta(seconds=200)
        # The old deadline passes without a fault.
        await advance(wenv, 100)
        assert wenv.ctrl.state is ControllerState.WATERING
        # The new deadline is genuine.
        await advance(wenv, 200)
        assert wenv.ctrl.state is ControllerState.FAULT
        assert wenv.ctrl.active_fault is FaultCode.SENSOR_STALE

    async def test_sr13_deliberately_executed_stale_callback_no_ops(self, wenv) -> None:
        from custom_components.moisture_loop.models import WatchdogFired

        await set_moisture(wenv, "27")
        old_token = wenv.ctrl.armed_watchdog
        assert old_token is not None
        await advance(wenv, 299)
        await set_moisture(wenv, "27")  # re-arms with a newer deadline
        new_token = wenv.ctrl.armed_watchdog
        assert new_token != old_token
        await advance(wenv, 1)  # the OLD deadline instant
        events_before = list(wenv.events)
        decision = await wenv.ctrl.async_dispatch(WatchdogFired(old_token))
        await settle(wenv)
        # The stale callback no-ops: no OFF, no fault, no reason, WATERING
        # preserved, and the newer arm intact (SR13).
        assert decision.no_op
        assert wenv.ctrl.state is ControllerState.WATERING
        assert wenv.ctrl.active_fault is None
        assert wenv.actuator.off_calls == 0
        assert wenv.events == events_before
        assert wenv.ctrl.armed_watchdog == new_token

    async def test_sr8_invalid_and_unavailable_take_specific_paths(self, env) -> None:
        await set_moisture(env, "27")
        await set_moisture(env, "150")  # INVALID mid-pulse
        assert env.ctrl.state is ControllerState.FAULT
        assert env.ctrl.active_fault is FaultCode.SENSOR_INVALID
        assert env.actuator.off_calls == 1

    async def test_sr8_unavailable_mid_pulse(self, env) -> None:
        await set_moisture(env, "27")
        await set_moisture(env, "unavailable")
        assert env.ctrl.state is ControllerState.FAULT
        assert env.ctrl.active_fault is FaultCode.SENSOR_UNAVAILABLE


class TestManual:
    async def test_manual_session_ignores_sensor_health(self, env) -> None:
        """SR9/MF: manual runs to its bounded deadline despite the sensor."""
        await env.ctrl.async_manual_start(600.0)
        await settle(env)  # slot granted; T3 executes on the grant
        assert env.ctrl.state is ControllerState.WATERING
        assert env.ctrl.session is not None
        assert env.ctrl.session.mode is SessionMode.MANUAL
        await set_moisture(env, "unavailable")  # ignored (T12)
        assert env.ctrl.state is ControllerState.WATERING
        await set_moisture(env, "150")  # ignored (T12)
        assert env.ctrl.state is ControllerState.WATERING
        await advance(env, 600)
        assert env.ctrl.state is ControllerState.IDLE
        assert env.ctrl.last_summary is not None
        assert env.ctrl.last_summary.reason.value == "manual_complete"
        assert env.actuator.off_calls == 1

    async def test_manual_from_sensor_fault_returns_to_fault(self, env) -> None:
        """MF3: retained fault, no event churn, back to the same episode."""
        await set_moisture(env, "27")
        await set_moisture(env, "unavailable")  # AUTO aborts -> FAULT
        assert env.ctrl.active_fault is FaultCode.SENSOR_UNAVAILABLE
        events_before = event_kinds(env)
        await env.ctrl.async_manual_start(600.0)
        await settle(env)  # slot granted; T40 executes on the grant
        assert env.ctrl.state is ControllerState.WATERING
        assert env.ctrl.active_fault is FaultCode.SENSOR_UNAVAILABLE  # visible
        assert "fault_cleared" not in event_kinds(env)[len(events_before) :]
        await advance(env, 600)
        assert env.ctrl.state is ControllerState.FAULT
        assert env.ctrl.active_fault is FaultCode.SENSOR_UNAVAILABLE
        new_events = event_kinds(env)[len(events_before) :]
        assert "fault_set" not in new_events  # no duplicate fault_set (MF3)
        assert new_events.count("session_finished") == 1

    async def test_manual_recovery_clears_after_finish(self, env) -> None:
        """MF4: recovery mid-manual never interrupts; ordered events."""
        await set_moisture(env, "27")
        await set_moisture(env, "unavailable")
        await env.ctrl.async_manual_start(600.0)
        await settle(env)
        await set_moisture(env, "33")  # sensor recovers mid-run
        assert env.ctrl.state is ControllerState.WATERING  # not interrupted
        await advance(env, 600)
        assert env.ctrl.state is ControllerState.IDLE
        assert env.ctrl.active_fault is None
        kinds = event_kinds(env)
        assert (
            kinds.index("session_finished", kinds.index("session_started", 1))
            < (len(kinds) - 1 - kinds[::-1].index("fault_cleared")) + len(kinds) * 0
        )  # finish precedes clear
        finish_idx = len(kinds) - 1 - kinds[::-1].index("session_finished")
        clear_idx = len(kinds) - 1 - kinds[::-1].index("fault_cleared")
        assert finish_idx < clear_idx

    async def test_mf5_actuator_fault_supersedes_mid_manual(self, env) -> None:
        await set_moisture(env, "27")
        await set_moisture(env, "unavailable")
        await env.ctrl.async_manual_start(600.0)
        await settle(env)
        env.actuator.set_state("unavailable")
        await settle(env)
        # Defensive OFF, acknowledged by the scripted switch.
        assert env.ctrl.state is ControllerState.FAULT
        assert env.ctrl.active_fault is FaultCode.ACTUATOR_UNAVAILABLE
        assert env.ctrl.secondary_fault is FaultCode.SENSOR_UNAVAILABLE
        # Manual is now blocked (MF5).
        refused = await env.ctrl.async_manual_start(600.0)
        assert refused.transition_id == "T41"

    async def test_manual_clamp_arms_effective_deadline(self, env) -> None:
        await env.ctrl.async_manual_start(4000.0)
        await settle(env)
        session = env.ctrl.session
        assert session is not None
        assert session.manual_effective_duration_s == 1800.0
        assert ManualClampReason.MANUAL_MAX_DURATION in session.manual_clamp_reasons
        assert session is not None and session.pulse_confirmed_at_utc is not None
        assert session.pulse_ends_at_utc == session.pulse_confirmed_at_utc + timedelta(seconds=1800)
        # Not finished before the effective deadline...
        await advance(env, 1799)
        assert env.ctrl.state is ControllerState.WATERING
        await advance(env, 1)
        assert env.ctrl.state is ControllerState.IDLE

    async def test_manual_queues_for_slot(self, env) -> None:
        other = await env.slots.async_request("other-zone")
        assert not other.pending
        decision = await env.ctrl.async_manual_start(600.0)
        await settle(env)
        assert decision.transition_id is None  # queued, not started
        assert env.actuator.on_calls == 0
        await env.slots.async_release("other-zone")
        await settle(env)
        assert env.ctrl.state is ControllerState.WATERING
        assert env.ctrl.session is not None
        assert env.ctrl.session.mode is SessionMode.MANUAL
        assert env.actuator.on_calls == 1


class TestTerminationRaces:
    async def test_ac1_stop_during_pulse_single_off(self, env) -> None:
        await set_moisture(env, "27")
        await env.ctrl.async_stop_watering()
        await settle(env)
        assert env.ctrl.state is ControllerState.IDLE
        assert env.actuator.off_calls == 1
        assert env.ctrl.last_summary is not None
        assert env.ctrl.last_summary.reason.value == "user_stop"

    async def test_ac1_disable_during_pulse(self, env) -> None:
        await set_moisture(env, "27")
        await env.ctrl.async_set_enabled(False)
        await settle(env)
        assert env.ctrl.state is ControllerState.DISABLED
        assert env.actuator.off_calls == 1
        assert env.ctrl.last_summary is not None
        assert env.ctrl.last_summary.reason.value == "zone_disabled"

    async def test_ac2_stop_vs_pulse_expiry_single_reason(self, env) -> None:
        await set_moisture(env, "27")
        # Stop commits first; the pulse deadline then fires and must no-op.
        await env.ctrl.async_stop_watering()
        await advance(env, 300)
        assert env.ctrl.state is ControllerState.IDLE
        assert env.actuator.off_calls == 1
        assert event_kinds(env).count("session_finished") == 1
        assert env.ctrl.last_summary is not None
        assert env.ctrl.last_summary.reason.value == "user_stop"

    async def test_ac4_off_timeout_delayed_proof_closes_later(self, env) -> None:
        await set_moisture(env, "27")
        env.actuator.off_behavior = "silent"
        await env.ctrl.async_stop_watering()
        await settle(env)
        # Three OFF attempts, each with a full confirm window (§11.3).
        for _ in range(3):
            await advance(env, 30)
        assert env.actuator.off_calls == 3
        assert env.ctrl.state is ControllerState.FAULT
        assert env.ctrl.active_fault is FaultCode.ACTUATOR_OFF_TIMEOUT
        assert ("zone-1", BlockerReason.INTEGRATION_OFF_UNCONFIRMED) in env.slots.blockers()
        # Accounting stays open: no session_finished yet.
        assert "session_finished" not in event_kinds(env)
        assert env.ctrl.session is not None

        # Later observed OFF closes accounting at the later timestamp (AC4)
        # and removes only the matching blocker; the fault stays latched.
        await advance(env, 3600)
        env.actuator.set_state("off")
        await settle(env)
        assert "session_finished" in event_kinds(env)
        assert env.ctrl.session is None
        assert env.slots.blockers() == frozenset()
        assert env.ctrl.active_fault is FaultCode.ACTUATOR_OFF_TIMEOUT
        assert env.ctrl.last_summary is not None
        # commanded at T0, proof at T0+3690: conservative accounting.
        assert env.ctrl.last_summary.runtime_s == pytest.approx(3690.0)
        assert env.ctrl.daily.runtime_s == pytest.approx(3690.0)

    async def test_clear_fault_after_off_proof(self, env) -> None:
        await set_moisture(env, "27")
        env.actuator.off_behavior = "silent"
        await env.ctrl.async_stop_watering()
        await settle(env)
        for _ in range(3):
            await advance(env, 30)
        refused = await env.ctrl.async_clear_fault()
        assert refused.transition_id == "T44"  # OFF not yet observed
        env.actuator.set_state("off")
        await settle(env)
        cleared = await env.ctrl.async_clear_fault()
        assert cleared.transition_id == "T43"
        assert env.ctrl.state is ControllerState.IDLE
        assert env.ctrl.active_fault is None


class TestExternalInterference:
    async def test_stage2_blocker_uses_safety_record_not_zone_id(
        self, hass, hass_storage, freezer
    ) -> None:
        exact_record_id = "durable-safety-record-a"
        e = await build_env(hass, freezer, safety_record_id=exact_record_id)
        try:
            e.actuator.set_state("on")
            await settle(e)
            assert e.slots.blockers() == {(exact_record_id, BlockerReason.EXTERNAL_FLOW)}
            assert (ZONE, BlockerReason.EXTERNAL_FLOW) not in e.slots.blockers()
        finally:
            await e.ctrl.async_detach()

    async def test_er9_external_off_during_watering(self, env) -> None:
        await set_moisture(env, "27")
        await advance(env, 100)
        env.actuator.set_state("off")  # external stop mid-pulse
        await settle(env)
        assert env.ctrl.state is ControllerState.IDLE
        assert env.ctrl.last_summary is not None
        assert env.ctrl.last_summary.reason.value == "external_actuator_state_change"
        # Accounting closed at the observed external OFF (§19.1): ~100 s.
        assert env.ctrl.last_summary.runtime_s == pytest.approx(100.0)
        # The defensive idempotent OFF was still issued (§11.4).
        assert env.actuator.off_calls >= 1

    async def test_er10_external_on_during_soaking_counter_commanded(self, env) -> None:
        await set_moisture(env, "27")
        await advance(env, 300)  # -> SOAKING
        assert env.ctrl.state is ControllerState.SOAKING
        env.actuator.set_state("on")  # interference
        await settle(env)
        # Defensive OFF acknowledged -> T33 IDLE; blocker cycle completed.
        assert env.ctrl.state is ControllerState.IDLE
        assert env.ctrl.last_summary is not None
        assert env.ctrl.last_summary.reason.value == "external_actuator_state_change"
        assert env.slots.blockers() == frozenset()

    async def test_er10_escalates_when_off_unproven(self, env) -> None:
        await set_moisture(env, "27")
        await advance(env, 300)
        env.actuator.off_behavior = "silent"
        env.actuator.set_state("on")
        await settle(env)
        for _ in range(3):
            await advance(env, 30)
        assert env.ctrl.state is ControllerState.FAULT
        assert env.ctrl.active_fault is FaultCode.ACTUATOR_OFF_TIMEOUT
        assert ("zone-1", BlockerReason.INTEGRATION_OFF_UNCONFIRMED) in env.slots.blockers()

    async def test_er11_external_on_during_off_joins_same_operation(self, env) -> None:
        from custom_components.moisture_loop.models import ExternalActuatorOn

        await set_moisture(env, "27")
        await advance(env, 300)  # SOAKING
        env.actuator.off_behavior = "silent"
        env.actuator.set_state("on")
        await settle(env)
        off_calls_before = env.actuator.off_calls
        # A second interference observation while OFF is already in flight
        # joins the existing operation; no second normal OFF sequence.
        decision = await env.ctrl.async_dispatch(ExternalActuatorOn())
        assert decision.no_op
        await settle(env)
        assert env.actuator.off_calls == off_calls_before

    async def test_t54_t58_external_flow_in_idle(self, env) -> None:
        env.actuator.set_state("on")  # external ON while IDLE
        await settle(env)
        assert env.ctrl.state is ControllerState.IDLE
        assert env.ctrl.external_on
        assert ("zone-1", BlockerReason.EXTERNAL_FLOW) in env.slots.blockers()
        assert env.actuator.off_calls == 0  # respected, never counter-commanded
        # A dry evaluation cannot start while the resource is occupied.
        await set_moisture(env, "27")
        assert env.actuator.on_calls == 0
        # Proven OFF releases the key (T58); the earlier dry report was a
        # G-ACT guard refusal, so the next normal evaluation trigger starts.
        env.actuator.set_state("off")
        await settle(env)
        assert not env.ctrl.external_on
        assert env.slots.blockers() == frozenset()
        await env.ctrl.async_evaluate()
        await settle(env)
        assert env.ctrl.state is ControllerState.WATERING
        assert env.actuator.on_calls == 1

    async def test_slot_blocked_evaluation_waits(self, env) -> None:
        await env.slots.async_add_blocker("other-zone", BlockerReason.EXTERNAL_FLOW)
        await set_moisture(env, "27")
        assert env.actuator.on_calls == 0
        assert env.ctrl.state is ControllerState.IDLE
        await env.slots.async_remove_blocker("other-zone", BlockerReason.EXTERNAL_FLOW)
        await settle(env)
        assert env.ctrl.state is ControllerState.WATERING
        assert env.actuator.on_calls == 1


class TestValveActuator:
    async def test_valve_flow_with_transitional_states(self, venv) -> None:
        await set_moisture(venv, "27")
        # open_valve leaves the valve 'opening': transitional, unconfirmed.
        assert venv.actuator.open_calls == 1
        session = venv.ctrl.session
        assert session is not None and session.pulse_confirmed_at_utc is None
        venv.actuator.set_state("open", position=100)
        await settle(venv)
        session = venv.ctrl.session
        assert session is not None and session.pulse_confirmed_at_utc is not None
        # Pulse end: close_valve leaves 'closing' (never proof of OFF).
        await advance(venv, 300)
        assert venv.actuator.close_calls == 1
        assert venv.ctrl.state is ControllerState.WATERING  # OFF unproven yet
        venv.actuator.set_state("closed", position=0)
        await settle(venv)
        assert venv.ctrl.state is ControllerState.SOAKING  # T6 after proof

    async def test_assessment_matrix(self, hass) -> None:
        adapter = ActuatorAdapter(hass, VALVE)

        def state_of(raw: str, position: int | None = None):
            attrs = {} if position is None else {"current_position": position}
            hass.states.async_set(VALVE, raw, attrs)
            return hass.states.get(VALVE)

        # §11.1 valve matrix.
        a = adapter.assess(state_of("open"))
        assert a.observed_on and not a.proven_off
        a = adapter.assess(state_of("closed", 0))
        assert a.proven_off and not a.observed_on
        a = adapter.assess(state_of("closed"))
        assert a.proven_off  # closed without position reporting
        a = adapter.assess(state_of("closed", 30))
        assert a.observed_on and not a.proven_off  # nonzero position flows
        a = adapter.assess(state_of("opening", 10))
        assert not a.proven_off and a.observed_on
        a = adapter.assess(state_of("closing", 0))
        assert not a.proven_off and not a.observed_on  # transitional
        a = adapter.assess(state_of("unavailable"))
        assert not a.available and not a.proven_off
        a = adapter.assess(state_of("unknown"))
        assert not a.available
        a = adapter.assess(state_of("surprise"))
        assert a.available and not a.proven_off and not a.observed_on
        a = adapter.assess(None)
        assert not a.available

        switch_adapter = ActuatorAdapter(hass, SWITCH)
        hass.states.async_set(SWITCH, "on")
        a = switch_adapter.assess(hass.states.get(SWITCH))
        assert a.observed_on and not a.proven_off
        hass.states.async_set(SWITCH, "off")
        a = switch_adapter.assess(hass.states.get(SWITCH))
        assert a.proven_off
        hass.states.async_set(SWITCH, "weird")
        a = switch_adapter.assess(hass.states.get(SWITCH))
        assert a.available and not a.proven_off and not a.observed_on


class TestLifecycleInputs:
    async def test_config_reload_terminates_watering(self, env) -> None:
        from custom_components.moisture_loop.models import ConfigEntryReload

        await set_moisture(env, "27")
        await env.ctrl.async_dispatch(ConfigEntryReload())
        await settle(env)
        assert env.ctrl.state is ControllerState.IDLE
        assert env.ctrl.last_summary is not None
        assert env.ctrl.last_summary.reason.value == "config_reload"
        assert env.actuator.off_calls == 1

    async def test_sensor_removal_faults_configuration(self, env) -> None:
        from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED

        env.hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED, {"action": "remove", "entity_id": SENSOR}
        )
        await settle(env)
        assert env.ctrl.state is ControllerState.FAULT
        assert env.ctrl.active_fault is FaultCode.CONFIGURATION_INVALID

    async def test_evaluate_now_uses_normal_guards(self, env) -> None:
        # No fresh report at all: evaluation refuses (I27-adjacent).
        decision = await env.ctrl.async_evaluate()
        assert decision.transition_id == "T2"
        assert decision.guard_result is not None
        assert "G-FRESH" in decision.guard_result.failed_guards


class TestControllerEdges:
    """Remaining deterministic edge paths (adoption, failures, joins)."""

    async def test_retained_runtime_is_observation_only(self, env) -> None:
        env.ctrl.update_runtime_ownership(
            zone_history_id=env.ctrl.zone_history_id,
            lifecycle=RuntimeLifecycle.DELETE_PENDING,
            applied_config=env.ctrl.applied_config,
        )
        assert (await env.ctrl.async_evaluate()).no_op
        assert (await env.ctrl.async_manual_start(60)).no_op
        assert (await env.ctrl.async_fallback_scan()).no_op
        env.ctrl._ensure_slot_request()
        assert env.ctrl._slot_task is None
        env.ctrl.update_runtime_ownership(
            zone_history_id=env.ctrl.zone_history_id,
            lifecycle=RuntimeLifecycle.ACTIVE,
            applied_config=env.ctrl.applied_config,
        )

    async def test_retained_runtime_declines_late_slot_grant(self, env) -> None:
        await env.slots.async_add_blocker("other", BlockerReason.EXTERNAL_FLOW)
        env.ctrl._ensure_slot_request()
        await settle(env)
        assert env.slots.snapshot().queue == (ZONE,)
        env.ctrl.update_runtime_ownership(
            zone_history_id=env.ctrl.zone_history_id,
            lifecycle=RuntimeLifecycle.DELETE_PENDING,
            applied_config=env.ctrl.applied_config,
        )
        await env.slots.async_remove_blocker("other", BlockerReason.EXTERNAL_FLOW)
        await settle(env)
        assert env.slots.owner is None
        assert env.ctrl.session is None
        env.ctrl.update_runtime_ownership(
            zone_history_id=env.ctrl.zone_history_id,
            lifecycle=RuntimeLifecycle.ACTIVE,
            applied_config=env.ctrl.applied_config,
        )

    async def test_attach_adopts_persisted_record(self, hass, hass_storage, freezer) -> None:
        from dataclasses import replace
        from datetime import date, datetime

        from custom_components.moisture_loop.models import ZoneDailyRuntime

        e = await build_env(hass, freezer)
        await e.ctrl.async_detach()
        safety_record = e.store.data.safety_records[e.ctrl.safety_record_id]
        history = e.store.data.zone_histories[safety_record.zone_history_id]
        last_end = datetime(2026, 8, 21, 6, 0, tzinfo=UTC)
        histories = dict(e.store.data.zone_histories)
        histories[history.zone_history_id] = history.evolve(
            last_session_end_utc=last_end,
            last_auto_session_start_utc=datetime(2026, 8, 21, 5, 0, tzinfo=UTC),
            daily=ZoneDailyRuntime(date(2026, 8, 21), 123.0),
            zone_runtime=replace(
                history.zone_runtime,
                state=ControllerState.FAULT,
                zone_fault=FaultCode.SENSOR_STALE,
            ),
        )
        await e.store.async_reconcile(lambda data: (dict(data.safety_records), histories))
        ctrl2 = ZoneController(
            hass,
            ZONE,
            CONFIG,
            e.store,
            e.slots,
            run_id="run-2",
            local_tz=UTC,
            authorization=e.authorization,
        )
        ctrl2.async_attach()
        assert ctrl2.state is ControllerState.FAULT
        assert ctrl2.active_fault is FaultCode.SENSOR_STALE
        assert ctrl2.daily.runtime_s == 123.0
        assert ctrl2.last_session_end == last_end
        assert not ctrl2.external_on
        assert ctrl2.secondary_fault is None
        assert ctrl2.observation is not None
        await ctrl2.async_detach()

    async def test_actuator_unavailable_while_idle_is_ignored(self, env) -> None:
        env.actuator.set_state("unavailable")
        await settle(env)
        assert env.ctrl.state is ControllerState.IDLE
        env.actuator.set_state("weird-state")  # available, neither on nor off
        await settle(env)
        assert env.ctrl.state is ControllerState.IDLE

    async def test_enable_schedules_evaluation(self, env) -> None:
        await set_moisture(env, "27")
        await env.ctrl.async_stop_watering()
        await settle(env)
        await env.ctrl.async_set_enabled(False)
        await settle(env)
        assert env.ctrl.state is ControllerState.DISABLED
        await advance(env, 900)  # interval elapses while disabled
        await env.ctrl.async_set_enabled(True)
        await settle(env)
        # T47 schedules a guarded evaluation which starts a session.
        assert env.ctrl.state is ControllerState.WATERING

    async def test_persist_failure_with_flowing_actuator_forces_off(self, env) -> None:
        await set_moisture(env, "27")
        assert env.ctrl.state is ControllerState.WATERING

        async def failing_update(*args, **kwargs):
            raise StoreWriteVerificationError("injected mid-session")

        env.store.async_update_controller_runtime = failing_update  # type: ignore[method-assign]
        await env.ctrl.async_stop_watering()  # commit persist fails
        await settle(env)
        assert env.ctrl.state is ControllerState.FAULT
        assert env.ctrl.active_fault is FaultCode.RESTORED_FROM_UNSAFE_STATE
        # OFF reconciliation was still requested and executed.
        assert env.actuator.off_calls >= 1

    async def test_post_on_persist_failure_fails_closed(self, env) -> None:
        original = env.store.async_update_controller_runtime
        calls = 0

        async def failing_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls >= 2:  # the pulse_commanded anchor write
                raise StoreWriteVerificationError("injected post-ON")
            return await original(*args, **kwargs)

        env.store.async_update_controller_runtime = failing_second  # type: ignore[method-assign]
        await set_moisture(env, "27")
        assert env.ctrl.state is ControllerState.FAULT
        assert env.ctrl.active_fault is FaultCode.RESTORED_FROM_UNSAFE_STATE

    async def test_on_service_exception_faults(self, env) -> None:
        env.actuator.on_behavior = "error"
        await set_moisture(env, "27")
        assert env.ctrl.state is ControllerState.FAULT
        assert env.ctrl.active_fault is FaultCode.ACTUATOR_ON_TIMEOUT

    async def test_off_service_exception_attempts_continue(self, env) -> None:
        await set_moisture(env, "27")
        env.actuator.off_behavior = "error"
        await env.ctrl.async_stop_watering()
        await settle(env)
        for _ in range(3):
            await advance(env, 30)
        # Three attempts despite the raising service.
        assert env.actuator.off_calls == 3
        assert env.ctrl.active_fault is FaultCode.ACTUATOR_OFF_TIMEOUT

    async def test_daily_lazy_rollover(self, env) -> None:
        await set_moisture(env, "27")
        await advance(env, 300)  # 300 s charged today
        assert env.ctrl.daily.runtime_s == pytest.approx(300.0)
        env.freezer.tick(timedelta(days=1))
        assert env.ctrl.daily.runtime_s == 0.0  # new HA-local day

    async def test_charge_entirely_on_previous_day(self, hass, hass_storage, freezer) -> None:
        e = await build_env(hass, freezer)
        e.freezer.move_to("2026-08-21 23:55:00+00:00")
        await e.ctrl.async_manual_start(300.0)
        await settle(e)
        assert e.ctrl.state is ControllerState.WATERING
        await advance(e, 300)  # OFF lands exactly at local midnight
        assert e.ctrl.state is ControllerState.IDLE
        # The whole interval belongs to Aug 21; the new day starts at zero.
        assert e.ctrl.daily.runtime_s == 0.0
        await e.ctrl.async_detach()

    async def test_duplicate_slot_request_reuses_wait_task(self, env) -> None:
        await env.slots.async_add_blocker("other", BlockerReason.EXTERNAL_FLOW)
        await set_moisture(env, "27")
        await env.ctrl.async_evaluate()  # second RequestSlot while queued
        await settle(env)
        assert env.slots.snapshot().queue == (ZONE,)

    async def test_detach_cancels_queued_slot_wait(self, hass, hass_storage, freezer) -> None:
        e = await build_env(hass, freezer)
        await e.slots.async_add_blocker("other", BlockerReason.EXTERNAL_FLOW)
        await set_moisture(e, "27")
        assert e.slots.snapshot().queue == (ZONE,)
        await e.ctrl.async_detach()
        await settle(e)
        assert e.slots.snapshot().queue == ()

    async def test_perform_on_guards_without_session(self, env) -> None:
        await env.ctrl._perform_on()  # no session: returns without commands
        assert env.actuator.on_calls == 0
        # Pending termination also suppresses a late ON request.
        await set_moisture(env, "27")
        env.actuator.on_calls = 0
        await env.ctrl.async_stop_watering()
        await env.ctrl._perform_on()
        assert env.actuator.on_calls == 0

    async def test_off_operation_join_and_completed_paths(self, env) -> None:
        import asyncio

        await set_moisture(env, "27")
        env.actuator.off_behavior = "silent"
        await env.ctrl.async_stop_watering()
        await settle(env)
        # The operation is in flight: joining awaits the same future.
        op = env.ctrl._off_operation
        assert op is not None and not op.done()
        join_task = asyncio.ensure_future(env.ctrl._ensure_off_operation())
        await settle(env)
        env.actuator.off_behavior = "ack"
        env.actuator.set_state("off")
        await settle(env)
        assert await join_task is True
        # Completed-and-proven: a further assurance call joins trivially.
        assert await env.ctrl._ensure_off_operation() is True

    async def test_off_operation_internal_error_fails_closed(self, env) -> None:
        await set_moisture(env, "27")

        async def broken_attempts():
            raise RuntimeError("injected")

        env.ctrl._run_off_attempts = broken_attempts  # type: ignore[method-assign]
        with pytest.raises(RuntimeError):
            await env.ctrl._ensure_off_operation()
        assert env.ctrl._off_operation is not None
        assert env.ctrl._off_operation.result() is False

    async def test_wait_off_proof_short_circuits(self, env) -> None:
        env.ctrl._off_proven.set()
        assert await env.ctrl._wait_off_proof() is True

    async def test_terminal_on_helper(self, hass) -> None:
        adapter = ActuatorAdapter(hass, SWITCH)
        assert not adapter.is_terminal_on(None)
        assert adapter.entity_id == SWITCH
        valve_adapter = ActuatorAdapter(hass, VALVE)
        hass.states.async_set(VALVE, "opening")
        assert not valve_adapter.is_terminal_on(hass.states.get(VALVE))
        hass.states.async_set(VALVE, "open")
        assert valve_adapter.is_terminal_on(hass.states.get(VALVE))

    async def test_snapshot_properties(self, env) -> None:
        assert env.ctrl.enabled is True
        assert env.ctrl.observation.classification.value == "unavailable"
        assert env.ctrl.armed_watchdog is None
        assert env.ctrl.last_summary is None

    async def test_attach_record_without_daily(self, hass, hass_storage, freezer) -> None:
        e = await build_env(hass, freezer)
        await e.ctrl.async_detach()
        safety_record = e.store.data.safety_records[e.ctrl.safety_record_id]
        history = e.store.data.zone_histories[safety_record.zone_history_id]
        histories = dict(e.store.data.zone_histories)
        histories[history.zone_history_id] = history.evolve(daily=None)
        await e.store.async_reconcile(lambda data: (dict(data.safety_records), histories))
        ctrl2 = ZoneController(
            hass,
            ZONE,
            CONFIG,
            e.store,
            e.slots,
            run_id="run-2",
            local_tz=UTC,
            authorization=e.authorization,
        )
        ctrl2.async_attach()
        assert ctrl2.daily.runtime_s == 0.0  # controller keeps its fresh counter
        await ctrl2.async_detach()

    async def test_unhandled_action_falls_through(self, env) -> None:
        from custom_components.moisture_loop.models import Decision, RequeueSlotTail

        # RequeueSlotTail is vocabulary the pure core no longer emits; the
        # apply chain tolerates it as a no-op.
        decision = Decision(transition_id=None, new_state=None)
        await env.ctrl._apply_action_locked(RequeueSlotTail(), decision)

    async def test_session_vanishing_during_on_call(self, env) -> None:
        async def clearing_turn_on(call) -> None:
            env.actuator.on_calls += 1
            env.ctrl._session = None  # concurrent finalize during the call

        env.hass.services.async_register("switch", "turn_on", clearing_turn_on)
        await set_moisture(env, "27")
        # No commanded anchor could be persisted; nothing crashes.
        assert env.actuator.on_calls == 1
