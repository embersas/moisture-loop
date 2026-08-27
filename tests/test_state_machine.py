"""Slices 2-3: exhaustive pure state-machine suite (SPECIFICATION.md §§14-22).

Table-driven coverage for every formal transition T1-T59, every guard
branch, exact threshold/time equality, watchdog token semantics, race
arbitration, with the Stage-7 I1-I37 matrix maintained in the mechanical
traceability layer. Pure layer: runs with no homeassistant installed,
controlled time inputs, no real sleeps.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from custom_components.moisture_loop.models import (
    ActuatorAssessment,
    ActuatorBecameUnavailable,
    ActuatorFinding,
    AddBlocker,
    ArmTimer,
    ArmWatchdog,
    AutoEvaluate,
    BlockerReason,
    ClearFaultRequested,
    CompletionReason,
    ConfigChangedPrepare,
    ConfigEntryReload,
    ConfigurationInvalid,
    ControllerState,
    DisableRequested,
    EmitFaultCleared,
    EmitFaultSet,
    EmitSessionFinished,
    EmitSessionStarted,
    EnableRequested,
    ExecuteOff,
    ExternalActuatorOff,
    ExternalActuatorOn,
    FaultCode,
    GraceDeadlineReached,
    HomeAssistantShutdown,
    ManualClampReason,
    ManualDeadlineReached,
    ManualStartRequested,
    MoistureClassification,
    MoistureObservation,
    MoistureReport,
    OffConfirmed,
    OffNotConfirmed,
    OnConfirmed,
    OnConfirmTimeout,
    PersistState,
    PulseDeadlineReached,
    ReleaseSlot,
    RemoveBlocker,
    RequestSlot,
    ResourceAssessment,
    ScheduleEvaluation,
    SessionContext,
    SessionIdentity,
    SessionMode,
    SetExternalOn,
    SlotGranted,
    SoakDeadlineReached,
    StartupPersistedSoaking,
    StartupPersistedWatering,
    StopRequested,
    StoreIntegrityLost,
    TimerKind,
    TransitionInput,
    TurnOn,
    WatchdogFired,
    WatchdogToken,
    ZoneConfig,
)
from custom_components.moisture_loop.state_machine import decide

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)
SEC = timedelta(seconds=1)

CONFIG = ZoneConfig(
    name="Front bed",
    moisture_sensor="sensor.front_bed_moisture",
    actuator="switch.front_bed_valve",
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

IDENTITY = SessionIdentity("sess-new", "run-1", "fp-1")

READY = ActuatorAssessment(available=True, proven_off=True, observed_on=False)
ACT_ON = ActuatorAssessment(available=True, proven_off=False, observed_on=True)
ACT_UNKNOWN = ActuatorAssessment(available=False, proven_off=False, observed_on=False)
GRANTED = ResourceAssessment(slot_granted=True, blockers_empty=True)
NOT_GRANTED = ResourceAssessment(slot_granted=False, blockers_empty=True)
BLOCKED = ResourceAssessment(slot_granted=False, blockers_empty=False)


def obs(
    value: float | None = 27.0,
    at: datetime | None = NOW,
    cls: MoistureClassification = MoistureClassification.VALID,
    age: float | None = 0.0,
) -> MoistureObservation:
    return MoistureObservation(value=value, classification=cls, reported_at_utc=at, age_s=age)


UNAVAILABLE_OBS = MoistureObservation(None, MoistureClassification.UNAVAILABLE, None, None)
INVALID_OBS = MoistureObservation(150.0, MoistureClassification.INVALID, NOW, 0.0)


def stale_obs(at: datetime) -> MoistureObservation:
    return MoistureObservation(33.0, MoistureClassification.STALE, at, None)


def auto_session(**over: object) -> SessionContext:
    base: dict[str, object] = {
        "session_id": "sess-a",
        "owner_run_id": "run-1",
        "config_fingerprint": "fp-1",
        "mode": SessionMode.AUTO,
        "started_at_utc": NOW - timedelta(minutes=10),
        "cycle": 1,
        "pulse_intent_at_utc": NOW - timedelta(minutes=6),
        "pulse_commanded_at_utc": NOW - timedelta(minutes=5),
        "pulse_confirmed_at_utc": NOW - timedelta(minutes=5),
        "pulse_ends_at_utc": NOW,
        "sensor_fresh_until_utc": NOW + timedelta(hours=1),
        "sensor_freshness_watchdog_generation": 1,
    }
    base.update(over)
    return SessionContext(**base)  # type: ignore[arg-type]


def manual_session(**over: object) -> SessionContext:
    base: dict[str, object] = {
        "session_id": "sess-m",
        "owner_run_id": "run-1",
        "config_fingerprint": "fp-1",
        "mode": SessionMode.MANUAL,
        "started_at_utc": NOW - timedelta(minutes=10),
        "cycle": 0,
        "pulse_intent_at_utc": NOW - timedelta(minutes=10),
        "pulse_commanded_at_utc": NOW - timedelta(minutes=9),
        "pulse_confirmed_at_utc": NOW - timedelta(minutes=9),
        "manual_requested_duration_s": 600.0,
        "manual_effective_duration_s": 540.0,
    }
    base.update(over)
    return SessionContext(**base)  # type: ignore[arg-type]


def soak_session(
    soak_ends: datetime = NOW - timedelta(minutes=1),
    **over: object,
) -> SessionContext:
    base: dict[str, object] = {
        "session_id": "sess-a",
        "owner_run_id": "run-1",
        "config_fingerprint": "fp-1",
        "mode": SessionMode.AUTO,
        "started_at_utc": NOW - timedelta(minutes=40),
        "cycle": 1,
        "session_runtime_s": 300.0,
        "pulse_intent_at_utc": NOW - timedelta(minutes=30),
        "pulse_commanded_at_utc": NOW - timedelta(minutes=29),
        "pulse_confirmed_at_utc": NOW - timedelta(minutes=29),
        "off_confirmed_at_utc": soak_ends - timedelta(seconds=CONFIG.soak_duration_s),
        "soak_ends_at_utc": soak_ends,
        "recheck_not_before_utc": soak_ends,
        "recheck_grace_deadline_at_utc": soak_ends + timedelta(seconds=CONFIG.sensor_max_age_s),
    }
    base.update(over)
    return SessionContext(**base)  # type: ignore[arg-type]


def make_input(
    state: ControllerState,
    event: object,
    *,
    session: SessionContext | None = None,
    enabled: bool = True,
    fault: FaultCode | None = None,
    secondary: FaultCode | None = None,
    observation: MoistureObservation | None = None,
    daily: float = 0.0,
    last_end: datetime | None = None,
    actuator: ActuatorAssessment = READY,
    resource: ResourceAssessment = GRANTED,
    armed: WatchdogToken | None = None,
    external: bool = False,
    identity: SessionIdentity | None = IDENTITY,
    now: datetime = NOW,
    config: ZoneConfig = CONFIG,
) -> TransitionInput:
    return TransitionInput(
        now_utc=now,
        config=config,
        state=state,
        enabled=enabled,
        session=session,
        active_fault=fault,
        secondary_fault=secondary,
        observation=observation if observation is not None else obs(),
        daily_runtime_s=daily,
        last_session_end_utc=last_end,
        actuator=actuator,
        resource=resource,
        armed_watchdog=armed,
        event=event,  # type: ignore[arg-type]
        external_on=external,
        new_session_identity=identity,
    )


def pending(reason: CompletionReason, base: Callable = auto_session, **over: object):
    return base(pending_termination_reason=reason, **over)


# ---------------------------------------------------------------------------
# Canonical inputs: one representative input per formal transition row.
# The mechanical audit asserts exactly T1-T59 are represented (§45.26).
# ---------------------------------------------------------------------------

CANONICAL: dict[str, Callable[[], TransitionInput]] = {
    "T1": lambda: make_input(ControllerState.IDLE, AutoEvaluate()),
    "T2": lambda: make_input(ControllerState.IDLE, AutoEvaluate(), observation=obs(value=35.0)),
    "T3": lambda: make_input(ControllerState.IDLE, ManualStartRequested(600.0)),
    "T4": lambda: make_input(ControllerState.IDLE, DisableRequested()),
    "T5": lambda: make_input(ControllerState.IDLE, ConfigurationInvalid()),
    "T6": lambda: make_input(ControllerState.WATERING, OffConfirmed(NOW), session=auto_session()),
    "T7": lambda: make_input(
        ControllerState.WATERING,
        OffConfirmed(NOW),
        session=pending(CompletionReason.MANUAL_COMPLETE, manual_session),
    ),
    "T8": lambda: make_input(
        ControllerState.WATERING,
        OffConfirmed(NOW),
        session=pending(
            CompletionReason.MANUAL_COMPLETE,
            manual_session,
            retained_sensor_fault=FaultCode.SENSOR_UNAVAILABLE,
        ),
        fault=FaultCode.SENSOR_UNAVAILABLE,
        observation=UNAVAILABLE_OBS,
    ),
    "T9": lambda: make_input(
        ControllerState.WATERING,
        OffConfirmed(NOW),
        session=pending(
            CompletionReason.MANUAL_COMPLETE,
            manual_session,
            retained_sensor_fault=FaultCode.SENSOR_UNAVAILABLE,
        ),
        fault=FaultCode.SENSOR_UNAVAILABLE,
        observation=obs(),
    ),
    "T10": lambda: make_input(
        ControllerState.WATERING,
        OffConfirmed(NOW),
        session=pending(CompletionReason.SENSOR_FAULT),
        fault=FaultCode.SENSOR_UNAVAILABLE,
        observation=UNAVAILABLE_OBS,
    ),
    "T11": lambda: make_input(
        ControllerState.WATERING,
        OffConfirmed(NOW),
        session=pending(CompletionReason.SENSOR_FAULT),
        fault=FaultCode.SENSOR_INVALID,
        observation=INVALID_OBS,
    ),
    "T12": lambda: make_input(
        ControllerState.WATERING, MoistureReport(obs()), session=manual_session()
    ),
    "T13": lambda: make_input(
        ControllerState.WATERING,
        OffConfirmed(NOW),
        session=pending(CompletionReason.ACTUATOR_FAULT),
        fault=FaultCode.ACTUATOR_UNAVAILABLE,
    ),
    "T14": lambda: make_input(
        ControllerState.WATERING,
        OffConfirmed(NOW),
        session=pending(CompletionReason.ACTUATOR_FAULT),
        fault=FaultCode.ACTUATOR_ON_TIMEOUT,
    ),
    "T15": lambda: make_input(
        ControllerState.WATERING,
        OffNotConfirmed(),
        session=pending(CompletionReason.USER_STOP),
        actuator=ACT_UNKNOWN,
    ),
    "T16": lambda: make_input(
        ControllerState.WATERING, ExternalActuatorOff(NOW), session=auto_session()
    ),
    "T17": lambda: make_input(
        ControllerState.WATERING,
        OffConfirmed(NOW),
        session=pending(CompletionReason.USER_STOP),
    ),
    "T18": lambda: make_input(
        ControllerState.WATERING,
        OffConfirmed(NOW),
        session=pending(CompletionReason.ZONE_DISABLED),
        enabled=False,
    ),
    "T19": lambda: make_input(
        ControllerState.WATERING,
        OffConfirmed(NOW),
        session=pending(CompletionReason.HOME_ASSISTANT_SHUTDOWN),
    ),
    "T20": lambda: make_input(
        ControllerState.WATERING,
        OffConfirmed(NOW),
        session=pending(CompletionReason.CONFIG_RELOAD),
    ),
    "T21": lambda: make_input(
        ControllerState.WATERING,
        OffConfirmed(NOW),
        session=pending(CompletionReason.CONFIG_CHANGED),
    ),
    "T22": lambda: make_input(
        ControllerState.SOAKING,
        MoistureReport(obs(value=33.0, at=NOW - timedelta(minutes=5))),
        session=soak_session(soak_ends=NOW + timedelta(minutes=10)),
    ),
    "T23": lambda: make_input(
        ControllerState.SOAKING,
        SoakDeadlineReached(),
        session=soak_session(),
        observation=obs(value=33.0, at=NOW - timedelta(minutes=30)),
    ),
    "T24": lambda: make_input(
        ControllerState.SOAKING,
        MoistureReport(obs(value=45.0)),
        session=soak_session(),
        observation=obs(value=45.0),
    ),
    "T25": lambda: make_input(
        ControllerState.SOAKING,
        MoistureReport(obs(value=35.0)),
        session=soak_session(),
        observation=obs(value=35.0),
    ),
    "T26": lambda: make_input(
        ControllerState.SOAKING,
        MoistureReport(obs(value=35.0)),
        session=soak_session(cycle=4),
        observation=obs(value=35.0),
    ),
    "T27": lambda: make_input(
        ControllerState.SOAKING,
        MoistureReport(obs(value=35.0)),
        session=soak_session(session_runtime_s=1600.0),
        observation=obs(value=35.0),
    ),
    "T28": lambda: make_input(
        ControllerState.SOAKING,
        MoistureReport(obs(value=35.0)),
        session=soak_session(),
        observation=obs(value=35.0),
        daily=3400.0,
    ),
    "T29": lambda: make_input(
        ControllerState.SOAKING,
        MoistureReport(INVALID_OBS),
        session=soak_session(),
        observation=INVALID_OBS,
    ),
    "T30": lambda: make_input(
        ControllerState.SOAKING,
        MoistureReport(UNAVAILABLE_OBS),
        session=soak_session(),
        observation=UNAVAILABLE_OBS,
    ),
    "T31": lambda: make_input(
        ControllerState.SOAKING,
        GraceDeadlineReached(),
        session=soak_session(soak_ends=NOW - timedelta(hours=2)),
        observation=obs(value=33.0, at=NOW - timedelta(hours=3)),
    ),
    "T32": lambda: make_input(
        ControllerState.SOAKING,
        ActuatorBecameUnavailable(),
        session=soak_session(),
        actuator=ACT_UNKNOWN,
    ),
    "T33": lambda: make_input(
        ControllerState.SOAKING,
        OffConfirmed(NOW),
        session=pending(CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE, soak_session),
    ),
    "T34": lambda: make_input(
        ControllerState.SOAKING,
        OffNotConfirmed(),
        session=pending(CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE, soak_session),
        actuator=ACT_ON,
    ),
    "T35": lambda: make_input(ControllerState.SOAKING, StopRequested(), session=soak_session()),
    "T36": lambda: make_input(ControllerState.SOAKING, DisableRequested(), session=soak_session()),
    "T37": lambda: make_input(
        ControllerState.SOAKING, HomeAssistantShutdown(), session=soak_session()
    ),
    "T38": lambda: make_input(ControllerState.SOAKING, ConfigEntryReload(), session=soak_session()),
    "T39": lambda: make_input(
        ControllerState.SOAKING, ConfigChangedPrepare(), session=soak_session()
    ),
    "T40": lambda: make_input(
        ControllerState.FAULT,
        ManualStartRequested(600.0),
        fault=FaultCode.SENSOR_UNAVAILABLE,
        observation=UNAVAILABLE_OBS,
    ),
    "T41": lambda: make_input(
        ControllerState.FAULT,
        ManualStartRequested(600.0),
        fault=FaultCode.ACTUATOR_OFF_TIMEOUT,
        actuator=ACT_ON,
        resource=BLOCKED,
    ),
    "T42": lambda: make_input(
        ControllerState.FAULT, MoistureReport(obs()), fault=FaultCode.SENSOR_STALE
    ),
    "T43": lambda: make_input(
        ControllerState.FAULT, ClearFaultRequested(), fault=FaultCode.ACTUATOR_OFF_TIMEOUT
    ),
    "T44": lambda: make_input(
        ControllerState.FAULT,
        ClearFaultRequested(),
        fault=FaultCode.ACTUATOR_OFF_TIMEOUT,
        actuator=ACT_ON,
    ),
    "T45": lambda: make_input(
        ControllerState.FAULT, DisableRequested(), fault=FaultCode.SENSOR_STALE
    ),
    "T46": lambda: make_input(
        ControllerState.DISABLED,
        EnableRequested(),
        enabled=False,
        fault=FaultCode.SENSOR_STALE,
    ),
    "T47": lambda: make_input(ControllerState.DISABLED, EnableRequested(), enabled=False),
    "T48": lambda: make_input(
        ControllerState.WATERING,
        StartupPersistedWatering(ActuatorFinding.OFF),
        session=auto_session(),
    ),
    "T49": lambda: make_input(
        ControllerState.WATERING,
        OffNotConfirmed(),
        session=pending(CompletionReason.RESTART_RECOVERY),
        actuator=ACT_UNKNOWN,
    ),
    "T50": lambda: make_input(
        ControllerState.SOAKING,
        StartupPersistedSoaking(trusted=True, current_run_id="run-2"),
        session=soak_session(soak_ends=NOW + timedelta(minutes=5)),
    ),
    "T51": lambda: make_input(
        ControllerState.SOAKING,
        StartupPersistedSoaking(trusted=False),
        session=soak_session(),
    ),
    "T52": lambda: make_input(ControllerState.IDLE, StoreIntegrityLost()),
    "T53": lambda: make_input(ControllerState.IDLE, ConfigurationInvalid(at_setup=True)),
    "T54": lambda: make_input(ControllerState.IDLE, ExternalActuatorOn(), actuator=ACT_ON),
    "T55": lambda: make_input(
        ControllerState.DISABLED, ExternalActuatorOn(), enabled=False, actuator=ACT_ON
    ),
    "T56": lambda: make_input(
        ControllerState.WATERING,
        MoistureReport(obs()),
        session=auto_session(),
        armed=WatchdogToken(1, NOW + timedelta(hours=1)),
    ),
    "T57": lambda: make_input(
        ControllerState.WATERING,
        OffConfirmed(NOW),
        session=pending(CompletionReason.SENSOR_FAULT),
        fault=FaultCode.SENSOR_STALE,
        observation=obs(at=NOW - timedelta(hours=3)),
    ),
    "T58": lambda: make_input(ControllerState.IDLE, ExternalActuatorOff(NOW), external=True),
    "T59": lambda: make_input(
        ControllerState.DISABLED, ExternalActuatorOff(NOW), enabled=False, external=True
    ),
}

# Expected destination state per canonical row.
EXPECTED_DESTINATION: dict[str, ControllerState | None] = {
    "T1": ControllerState.WATERING,
    "T2": ControllerState.IDLE,
    "T3": ControllerState.WATERING,
    "T4": ControllerState.DISABLED,
    "T5": ControllerState.FAULT,
    "T6": ControllerState.SOAKING,
    "T7": ControllerState.IDLE,
    "T8": ControllerState.FAULT,
    "T9": ControllerState.IDLE,
    "T10": ControllerState.FAULT,
    "T11": ControllerState.FAULT,
    "T12": ControllerState.WATERING,
    "T13": ControllerState.FAULT,
    "T14": ControllerState.FAULT,
    "T15": ControllerState.FAULT,
    "T16": ControllerState.IDLE,
    "T17": ControllerState.IDLE,
    "T18": ControllerState.DISABLED,
    "T19": ControllerState.IDLE,
    "T20": ControllerState.IDLE,
    "T21": ControllerState.IDLE,
    "T22": ControllerState.SOAKING,
    "T23": ControllerState.SOAKING,
    "T24": ControllerState.IDLE,
    "T25": ControllerState.WATERING,
    "T26": ControllerState.IDLE,
    "T27": ControllerState.IDLE,
    "T28": ControllerState.IDLE,
    "T29": ControllerState.FAULT,
    "T30": ControllerState.FAULT,
    "T31": ControllerState.FAULT,
    "T32": ControllerState.FAULT,
    "T33": ControllerState.IDLE,
    "T34": ControllerState.FAULT,
    "T35": ControllerState.IDLE,
    "T36": ControllerState.DISABLED,
    "T37": ControllerState.SOAKING,
    "T38": ControllerState.IDLE,
    "T39": ControllerState.IDLE,
    "T40": ControllerState.WATERING,
    "T41": ControllerState.FAULT,
    "T42": ControllerState.IDLE,
    "T43": ControllerState.IDLE,
    "T44": ControllerState.FAULT,
    "T45": ControllerState.DISABLED,
    "T46": ControllerState.FAULT,
    "T47": ControllerState.IDLE,
    "T48": ControllerState.IDLE,
    "T49": ControllerState.FAULT,
    "T50": ControllerState.SOAKING,
    "T51": ControllerState.IDLE,
    "T52": ControllerState.FAULT,
    "T53": ControllerState.FAULT,
    "T54": ControllerState.IDLE,
    "T55": ControllerState.DISABLED,
    "T56": ControllerState.WATERING,
    "T57": ControllerState.FAULT,
    "T58": ControllerState.IDLE,
    "T59": ControllerState.DISABLED,
}


class TestTransitionTable:
    """Table-driven proof that every §14 row is implemented."""

    def test_inventory_is_exactly_t1_to_t59(self) -> None:
        assert set(CANONICAL) == {f"T{i}" for i in range(1, 60)}
        assert set(EXPECTED_DESTINATION) == set(CANONICAL)

    def test_spec_table_implementation_and_diagram_have_exact_t1_t59_parity(self) -> None:
        spec = (Path(__file__).resolve().parents[1] / "SPECIFICATION.md").read_text(
            encoding="utf-8"
        )
        table_text = spec.split("| ID | From | Trigger | Guard | Action | To | Reason/fault |", 1)[
            1
        ].split("The normative table contains **59 transitions**", 1)[0]
        rows: dict[str, tuple[str, ...]] = {}
        for raw in table_text.splitlines():
            match = re.match(r"\| (T\d+) \|(.+)\|$", raw)
            if match is None:
                continue
            transition_id = match.group(1)
            assert transition_id not in rows
            columns = tuple(part.strip() for part in match.group(2).split("|"))
            assert len(columns) == 6
            assert all(columns)
            rows[transition_id] = columns

        expected = {f"T{i}" for i in range(1, 60)}
        assert set(rows) == expected
        implementation = Path(__file__).resolve().parents[1] / (
            "custom_components/moisture_loop/state_machine.py"
        )
        tree = ast.parse(implementation.read_text(encoding="utf-8"))
        implementation_ids = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and re.fullmatch(r"T\d+", node.value)
        }
        assert implementation_ids == expected

        diagram = spec.split("```mermaid", 1)[1].split("```", 1)[0]
        assert set(re.findall(r"\bT\d+\b", diagram)) == expected

        for transition_id, (_from, _trigger, _guard, action, destination, reason) in rows.items():
            decision = decide(CANONICAL[transition_id]())
            state_name = EXPECTED_DESTINATION[transition_id].value.upper()
            assert state_name in destination or (
                "POST(" in destination and state_name in {"IDLE", "FAULT"}
            )
            assert action != "—"
            if decision.reason is not None:
                assert decision.reason.value.upper() in reason or transition_id == "T49"
            if decision.fault is not None:
                assert decision.fault.value.upper() in reason or "retained" in reason

    @pytest.mark.parametrize("row", sorted(CANONICAL, key=lambda r: int(r[1:])))
    def test_row_produces_its_transition(self, row: str) -> None:
        decision = decide(CANONICAL[row]())
        assert decision.transition_id == row
        assert decision.new_state is EXPECTED_DESTINATION[row]
        assert not decision.no_op


class TestT1AutoStart:
    def test_t1_creates_auto_session_and_orders_actions(self) -> None:
        d = decide(CANONICAL["T1"]())
        assert d.session is not None
        s = d.session
        assert s.mode is SessionMode.AUTO
        assert s.cycle == 1
        assert s.pulse_intent_at_utc == NOW
        assert s.moisture_at_start == 27.0
        assert s.sensor_fresh_until_utc == NOW + timedelta(seconds=7200)
        assert s.sensor_freshness_watchdog_generation == 1
        kinds = [type(a) for a in d.actions]
        # Persist intent before ON; watchdog armed no later than ON (§18.5).
        assert kinds.index(PersistState) < kinds.index(TurnOn)
        assert kinds.index(ArmWatchdog) < kinds.index(TurnOn)
        assert EmitSessionStarted in kinds
        watchdog = next(a for a in d.actions if isinstance(a, ArmWatchdog))
        assert watchdog.token == WatchdogToken(1, NOW + timedelta(seconds=7200))
        confirm = next(a for a in d.actions if isinstance(a, ArmTimer))
        assert confirm.kind is TimerKind.ON_CONFIRM_TIMEOUT
        assert confirm.at_utc == NOW + timedelta(seconds=30)

    def test_t1_requires_identity(self) -> None:
        with pytest.raises(ValueError):
            decide(make_input(ControllerState.IDLE, AutoEvaluate(), identity=None))

    @pytest.mark.parametrize(
        ("kwargs", "guard"),
        [
            ({"enabled": False}, "G-EN"),
            ({"observation": UNAVAILABLE_OBS}, "G-FRESH"),
            ({"observation": obs(at=NOW - timedelta(hours=3))}, "G-FRESH"),
            ({"observation": obs(value=30.0)}, "G-START"),
            ({"last_end": NOW - timedelta(hours=1)}, "G-INT"),
            ({"actuator": ACT_UNKNOWN}, "G-ACT"),
            ({"actuator": ACT_ON}, "G-ACT"),
            ({"daily": 3301.0}, "G-DAY"),
        ],
    )
    def test_t2_records_each_failed_guard(self, kwargs: dict, guard: str) -> None:
        d = decide(make_input(ControllerState.IDLE, AutoEvaluate(), **kwargs))
        assert d.transition_id == "T2"
        assert d.guard_result is not None
        assert guard in d.guard_result.failed_guards

    def test_slot_wait_is_not_a_transition(self) -> None:
        d = decide(make_input(ControllerState.IDLE, AutoEvaluate(), resource=NOT_GRANTED))
        assert d.transition_id is None
        assert d.new_state is None
        assert d.actions == (RequestSlot(),)
        assert d.guard_result is not None
        assert d.guard_result.failed_guards == ("G-SLOT",)

    def test_blockers_nonempty_waits_too(self) -> None:
        d = decide(make_input(ControllerState.IDLE, AutoEvaluate(), resource=BLOCKED))
        assert d.transition_id is None
        assert d.actions == (RequestSlot(),)

    def test_slot_granted_reruns_guards_and_starts(self) -> None:
        d = decide(make_input(ControllerState.IDLE, SlotGranted()))
        assert d.transition_id == "T1"

    def test_slot_granted_declined_when_guards_now_fail(self) -> None:
        d = decide(make_input(ControllerState.IDLE, SlotGranted(), observation=obs(value=50.0)))
        assert d.transition_id == "T2"
        assert ReleaseSlot() in d.actions

    def test_moisture_report_in_idle_evaluates(self) -> None:
        d = decide(make_input(ControllerState.IDLE, MoistureReport(obs())))
        assert d.transition_id == "T1"


class TestHysteresis:
    """§17: exact, asymmetric, no epsilon."""

    def test_start_boundary(self) -> None:
        below = decide(
            make_input(ControllerState.IDLE, AutoEvaluate(), observation=obs(value=29.999))
        )
        assert below.transition_id == "T1"
        equal = decide(
            make_input(ControllerState.IDLE, AutoEvaluate(), observation=obs(value=30.0))
        )
        assert equal.transition_id == "T2"

    def test_target_boundary_on_recheck(self) -> None:
        continue_ = decide(
            make_input(
                ControllerState.SOAKING,
                MoistureReport(obs(value=39.999)),
                session=soak_session(),
                observation=obs(value=39.999),
            )
        )
        assert continue_.transition_id == "T25"
        complete = decide(
            make_input(
                ControllerState.SOAKING,
                MoistureReport(obs(value=40.0)),
                session=soak_session(),
                observation=obs(value=40.0),
            )
        )
        assert complete.transition_id == "T24"
        assert complete.reason is CompletionReason.TARGET_REACHED

    def test_freshness_equality_is_fresh(self) -> None:
        boundary = obs(at=NOW - timedelta(seconds=7200))
        d = decide(make_input(ControllerState.IDLE, AutoEvaluate(), observation=boundary))
        assert d.transition_id == "T1"
        just_over = obs(at=NOW - timedelta(seconds=7200) - timedelta(microseconds=1))
        d2 = decide(make_input(ControllerState.IDLE, AutoEvaluate(), observation=just_over))
        assert d2.transition_id == "T2"

    def test_interval_equality_elapsed(self) -> None:
        exact = decide(
            make_input(
                ControllerState.IDLE, AutoEvaluate(), last_end=NOW - timedelta(seconds=21600)
            )
        )
        assert exact.transition_id == "T1"
        short = decide(
            make_input(
                ControllerState.IDLE,
                AutoEvaluate(),
                last_end=NOW - timedelta(seconds=21599),
            )
        )
        assert short.transition_id == "T2"

    def test_daily_whole_fit_equality(self) -> None:
        fits = decide(make_input(ControllerState.IDLE, AutoEvaluate(), daily=3300.0))
        assert fits.transition_id == "T1"
        over = decide(make_input(ControllerState.IDLE, AutoEvaluate(), daily=3300.5))
        assert over.transition_id == "T2"


class TestPostSoakEquality:
    """§18.4 exact boundary semantics (Scenario M, SR3)."""

    def test_report_exactly_at_soak_end_qualifies(self) -> None:
        soak_end = NOW - timedelta(minutes=5)
        report = obs(value=45.0, at=soak_end)
        d = decide(
            make_input(
                ControllerState.SOAKING,
                MoistureReport(report),
                session=soak_session(soak_ends=soak_end),
                observation=report,
            )
        )
        assert d.transition_id == "T24"

    def test_report_one_microsecond_before_does_not_qualify(self) -> None:
        soak_end = NOW - timedelta(minutes=5)
        report = obs(value=45.0, at=soak_end - timedelta(microseconds=1))
        d = decide(
            make_input(
                ControllerState.SOAKING,
                MoistureReport(report),
                session=soak_session(soak_ends=soak_end),
                observation=report,
            )
        )
        # Pre-deadline report timestamp: observability only.
        assert d.transition_id == "T22"

    def test_old_report_after_deadline_cannot_decide(self) -> None:
        """SR2: report 10 s after OFF cannot decide at soak end."""
        soak_end = NOW - timedelta(minutes=1)
        old = obs(value=33.0, at=soak_end - timedelta(minutes=19, seconds=50))
        d = decide(
            make_input(
                ControllerState.SOAKING,
                SoakDeadlineReached(),
                session=soak_session(soak_ends=soak_end),
                observation=old,
            )
        )
        assert d.transition_id == "T23"  # arm grace and wait

    def test_grace_boundary_report_qualifies(self) -> None:
        """§18.4: a report observed exactly at the grace deadline qualifies."""
        soak_end = NOW - timedelta(seconds=7200)
        report = obs(value=45.0, at=NOW)
        d = decide(
            make_input(
                ControllerState.SOAKING,
                GraceDeadlineReached(),
                session=soak_session(soak_ends=soak_end),
                observation=report,
            )
        )
        assert d.transition_id == "T24"

    def test_grace_without_qualifying_report_is_sensor_stale(self) -> None:
        d = decide(CANONICAL["T31"]())
        assert d.reason is CompletionReason.SENSOR_FAULT
        assert d.fault is FaultCode.SENSOR_STALE

    def test_grace_with_invalid_observation_uses_t29(self) -> None:
        soak_end = NOW - timedelta(hours=1)
        d = decide(
            make_input(
                ControllerState.SOAKING,
                GraceDeadlineReached(),
                session=soak_session(soak_ends=soak_end),
                observation=INVALID_OBS,
            )
        )
        assert d.transition_id == "T29"

    def test_grace_with_unavailable_observation_uses_t30(self) -> None:
        soak_end = NOW - timedelta(hours=1)
        d = decide(
            make_input(
                ControllerState.SOAKING,
                GraceDeadlineReached(),
                session=soak_session(soak_ends=soak_end),
                observation=UNAVAILABLE_OBS,
            )
        )
        assert d.transition_id == "T30"

    def test_grace_with_pre_deadline_invalid_falls_to_stale(self) -> None:
        soak_end = NOW - timedelta(hours=1)
        old_invalid = MoistureObservation(
            150.0, MoistureClassification.INVALID, soak_end - timedelta(hours=1), None
        )
        d = decide(
            make_input(
                ControllerState.SOAKING,
                GraceDeadlineReached(),
                session=soak_session(soak_ends=soak_end),
                observation=old_invalid,
            )
        )
        assert d.transition_id == "T31"

    def test_post_deadline_stale_replay_waits(self) -> None:
        soak_end = NOW - timedelta(minutes=1)
        replay = stale_obs(NOW)
        d = decide(
            make_input(
                ControllerState.SOAKING,
                MoistureReport(replay),
                session=soak_session(soak_ends=soak_end),
                observation=replay,
            )
        )
        assert d.no_op

    def test_soak_deadline_with_qualifying_report_decides_immediately(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                SoakDeadlineReached(),
                session=soak_session(),
                observation=obs(value=45.0),
            )
        )
        assert d.transition_id == "T24"

    def test_early_soak_trigger_no_ops(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                SoakDeadlineReached(),
                session=soak_session(soak_ends=NOW + timedelta(minutes=5)),
            )
        )
        assert d.no_op

    def test_recheck_grace_deadline_computed_from_soak_end(self) -> None:
        d = decide(CANONICAL["T6"]())
        assert d.session is not None
        assert d.session.soak_ends_at_utc == NOW + timedelta(seconds=1200)
        assert d.session.recheck_not_before_utc == d.session.soak_ends_at_utc
        assert d.session.recheck_grace_deadline_at_utc == d.session.soak_ends_at_utc + timedelta(
            seconds=7200
        )


class TestWatchdog:
    """§18.5 exact algorithm; SR5-SR13 pure obligations."""

    ARMED = WatchdogToken(1, NOW + timedelta(hours=1))

    def watering(self, **over: object) -> SessionContext:
        return auto_session(**over)

    def test_valid_report_extends_from_its_own_timestamp(self) -> None:
        """SR6/SR7: extension does not require reaching the old deadline."""
        report = obs(value=27.0, at=NOW - timedelta(minutes=30))
        d = decide(
            make_input(
                ControllerState.WATERING,
                MoistureReport(report),
                session=self.watering(
                    sensor_fresh_until_utc=NOW + timedelta(minutes=5),
                    sensor_freshness_watchdog_generation=3,
                ),
                armed=WatchdogToken(3, NOW + timedelta(minutes=5)),
            )
        )
        assert d.transition_id == "T56"
        assert d.session is not None
        assert d.session.sensor_fresh_until_utc == report.reported_at_utc + timedelta(seconds=7200)
        assert d.session.sensor_freshness_watchdog_generation == 4
        arm = next(a for a in d.actions if isinstance(a, ArmWatchdog))
        assert arm.token.generation == 4

    def test_older_replayed_report_cannot_shorten(self) -> None:
        report = obs(value=27.0, at=NOW - timedelta(hours=1, minutes=30))
        d = decide(
            make_input(
                ControllerState.WATERING,
                MoistureReport(report),
                session=self.watering(sensor_fresh_until_utc=NOW + timedelta(hours=1)),
                armed=self.ARMED,
            )
        )
        assert d.no_op

    def test_sr13_superseded_callback_no_ops(self) -> None:
        """SR13: report 10:00 arms 12:00; 11:59 arms 13:59; old 12:00 no-ops."""
        cfg = CONFIG  # sensor_max_age 2 h
        old_token = WatchdogToken(1, NOW)  # armed at report 10:00 -> 12:00 (=NOW)
        new_deadline = NOW - timedelta(minutes=1) + timedelta(hours=2)  # 13:59
        session = self.watering(
            sensor_fresh_until_utc=new_deadline,
            sensor_freshness_watchdog_generation=2,
        )
        d = decide(
            make_input(
                ControllerState.WATERING,
                WatchdogFired(old_token),
                session=session,
                armed=WatchdogToken(2, new_deadline),
                config=cfg,
            )
        )
        assert d.no_op
        assert d.transition_id is None
        assert d.actions == ()
        assert d.fault is None
        assert d.reason is None
        assert d.new_state is None

    def test_current_token_expiry_commits_sensor_stale(self) -> None:
        token = WatchdogToken(1, NOW)
        session = self.watering(sensor_fresh_until_utc=NOW)
        d = decide(
            make_input(
                ControllerState.WATERING,
                WatchdogFired(token),
                session=session,
                armed=token,
            )
        )
        assert d.transition_id is None  # commit phase
        assert d.fault is FaultCode.SENSOR_STALE
        assert d.session is not None
        assert d.session.pending_termination_reason is CompletionReason.SENSOR_FAULT
        assert ExecuteOff(defensive=False) in d.actions

    def test_current_token_future_deadline_rearms(self) -> None:
        token = WatchdogToken(2, NOW + timedelta(minutes=10))
        session = self.watering(
            sensor_fresh_until_utc=NOW + timedelta(minutes=10),
            sensor_freshness_watchdog_generation=2,
        )
        d = decide(
            make_input(
                ControllerState.WATERING,
                WatchdogFired(token),
                session=session,
                armed=token,
            )
        )
        assert d.transition_id is None
        assert d.actions == (ArmWatchdog(WatchdogToken(2, NOW + timedelta(minutes=10))),)

    def test_boundary_race_report_first_prevents_expiry(self) -> None:
        """SR10: VALID report at the exact boundary processed first wins."""
        boundary = NOW
        report = obs(value=27.0, at=boundary)
        session = self.watering(sensor_fresh_until_utc=boundary)
        d1 = decide(
            make_input(
                ControllerState.WATERING,
                MoistureReport(report),
                session=session,
                armed=WatchdogToken(1, boundary),
            )
        )
        assert d1.transition_id == "T56"
        # The queued old callback then no-ops against the replaced token.
        assert d1.session is not None
        d2 = decide(
            make_input(
                ControllerState.WATERING,
                WatchdogFired(WatchdogToken(1, boundary)),
                session=d1.session,
                armed=WatchdogToken(2, boundary + timedelta(seconds=7200)),
            )
        )
        assert d2.no_op

    def test_boundary_race_watchdog_first_terminates_permanently(self) -> None:
        token = WatchdogToken(1, NOW)
        session = self.watering(sensor_fresh_until_utc=NOW)
        d1 = decide(
            make_input(ControllerState.WATERING, WatchdogFired(token), session=session, armed=token)
        )
        assert d1.session is not None
        assert d1.session.pending_termination_reason is CompletionReason.SENSOR_FAULT
        # A later report cannot resurrect the session (commit owns it).
        d2 = decide(
            make_input(
                ControllerState.WATERING,
                MoistureReport(obs()),
                session=d1.session,
                armed=token,
            )
        )
        assert d2.no_op

    def test_manual_ignores_watchdog(self) -> None:
        """SR9: MANUAL never obeys the AUTO watchdog."""
        token = WatchdogToken(1, NOW - timedelta(minutes=1))
        d = decide(
            make_input(
                ControllerState.WATERING,
                WatchdogFired(token),
                session=manual_session(),
                armed=token,
            )
        )
        assert d.no_op

    def test_mismatched_token_no_ops(self) -> None:
        d = decide(
            make_input(
                ControllerState.WATERING,
                WatchdogFired(WatchdogToken(1, NOW)),
                session=self.watering(sensor_fresh_until_utc=NOW),
                armed=WatchdogToken(2, NOW + timedelta(hours=1)),
            )
        )
        assert d.no_op

    def test_no_armed_token_no_ops(self) -> None:
        d = decide(
            make_input(
                ControllerState.WATERING,
                WatchdogFired(WatchdogToken(1, NOW)),
                session=self.watering(sensor_fresh_until_utc=NOW),
                armed=None,
            )
        )
        assert d.no_op

    def test_watchdog_after_commit_no_ops(self) -> None:
        token = WatchdogToken(1, NOW)
        d = decide(
            make_input(
                ControllerState.WATERING,
                WatchdogFired(token),
                session=pending(
                    CompletionReason.USER_STOP, auto_session, sensor_fresh_until_utc=NOW
                ),
                armed=token,
            )
        )
        assert d.no_op

    def test_watchdog_in_soaking_no_ops(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                WatchdogFired(WatchdogToken(1, NOW)),
                session=soak_session(),
            )
        )
        assert d.no_op


class TestWateringSensorFaults:
    """SR8: INVALID/UNAVAILABLE take their immediate specific paths."""

    def test_invalid_commits_sensor_invalid(self) -> None:
        d = decide(
            make_input(
                ControllerState.WATERING,
                MoistureReport(INVALID_OBS),
                session=auto_session(),
            )
        )
        assert d.fault is FaultCode.SENSOR_INVALID
        assert d.session is not None
        assert d.session.pending_termination_reason is CompletionReason.SENSOR_FAULT
        assert any(isinstance(a, ExecuteOff) for a in d.actions)
        assert any(isinstance(a, EmitFaultSet) for a in d.actions)

    def test_unavailable_commits_sensor_unavailable(self) -> None:
        d = decide(
            make_input(
                ControllerState.WATERING,
                MoistureReport(UNAVAILABLE_OBS),
                session=auto_session(),
            )
        )
        assert d.fault is FaultCode.SENSOR_UNAVAILABLE

    def test_stale_classification_no_ops_during_auto(self) -> None:
        d = decide(
            make_input(
                ControllerState.WATERING,
                MoistureReport(stale_obs(NOW - timedelta(hours=3))),
                session=auto_session(),
            )
        )
        assert d.no_op

    def test_report_after_commit_no_ops(self) -> None:
        d = decide(
            make_input(
                ControllerState.WATERING,
                MoistureReport(obs()),
                session=pending(CompletionReason.SENSOR_FAULT),
            )
        )
        assert d.no_op

    def test_manual_bookkeeping_never_terminates(self) -> None:
        """I6: sensor state never terminates MANUAL."""
        for observation in (INVALID_OBS, UNAVAILABLE_OBS, obs(), stale_obs(NOW)):
            d = decide(
                make_input(
                    ControllerState.WATERING,
                    MoistureReport(observation),
                    session=manual_session(),
                )
            )
            assert d.transition_id == "T12"
            assert d.fault is None
            assert not any(isinstance(a, ExecuteOff) for a in d.actions)


class TestTerminationArbitration:
    """§22.2/§22.3: first terminal request owns the reason; one OFF."""

    def test_stop_commits_user_stop(self) -> None:
        d = decide(make_input(ControllerState.WATERING, StopRequested(), session=auto_session()))
        assert d.session is not None
        assert d.session.pending_termination_reason is CompletionReason.USER_STOP
        assert sum(isinstance(a, ExecuteOff) for a in d.actions) == 1

    @pytest.mark.parametrize(
        "event",
        [
            StopRequested(),
            DisableRequested(),
            HomeAssistantShutdown(),
            ConfigEntryReload(),
            ConfigChangedPrepare(),
            OnConfirmTimeout(),
            ActuatorBecameUnavailable(),
            PulseDeadlineReached(),
            ManualDeadlineReached(),
        ],
    )
    def test_second_terminal_request_no_ops(self, event: object) -> None:
        session = pending(CompletionReason.USER_STOP, manual_session)
        d = decide(make_input(ControllerState.WATERING, event, session=session))
        assert d.no_op

    def test_stop_vs_pulse_expiry_one_reason(self) -> None:
        """AC2: whichever commits first owns the reason; one OFF operation."""
        stop_first = decide(
            make_input(ControllerState.WATERING, StopRequested(), session=auto_session())
        )
        assert stop_first.session is not None
        after = decide(
            make_input(ControllerState.WATERING, PulseDeadlineReached(), session=stop_first.session)
        )
        assert after.no_op
        final = decide(
            make_input(ControllerState.WATERING, OffConfirmed(NOW), session=stop_first.session)
        )
        assert final.transition_id == "T17"
        assert final.reason is CompletionReason.USER_STOP

    def test_disable_still_controls_operational_state(self) -> None:
        """SR11/§22.3: Stop committed first, Disable applied -> DISABLED."""
        session = pending(CompletionReason.USER_STOP)
        d = decide(
            make_input(ControllerState.WATERING, OffConfirmed(NOW), session=session, enabled=False)
        )
        assert d.transition_id == "T17"
        assert d.reason is CompletionReason.USER_STOP
        assert d.new_state is ControllerState.DISABLED

    def test_pulse_deadline_requests_single_off(self) -> None:
        d = decide(
            make_input(ControllerState.WATERING, PulseDeadlineReached(), session=auto_session())
        )
        assert d.transition_id is None
        assert d.actions == (ExecuteOff(),)

    def test_manual_deadline_commits_manual_complete(self) -> None:
        d = decide(
            make_input(ControllerState.WATERING, ManualDeadlineReached(), session=manual_session())
        )
        assert d.session is not None
        assert d.session.pending_termination_reason is CompletionReason.MANUAL_COMPLETE

    def test_pulse_deadline_on_manual_session_no_ops(self) -> None:
        d = decide(
            make_input(ControllerState.WATERING, PulseDeadlineReached(), session=manual_session())
        )
        assert d.no_op

    def test_manual_deadline_on_auto_session_no_ops(self) -> None:
        d = decide(
            make_input(ControllerState.WATERING, ManualDeadlineReached(), session=auto_session())
        )
        assert d.no_op

    def test_external_on_during_own_watering_no_ops(self) -> None:
        d = decide(
            make_input(ControllerState.WATERING, ExternalActuatorOn(), session=auto_session())
        )
        assert d.no_op


class TestOffEvidence:
    """T15/T49 supersede; delayed closure (AC4); T16 external closure."""

    def test_t15_supersedes_requested_destination(self) -> None:
        d = decide(CANONICAL["T15"]())
        assert d.reason is CompletionReason.ACTUATOR_FAULT
        assert d.fault is FaultCode.ACTUATOR_OFF_TIMEOUT
        assert AddBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED) in d.actions
        # Accounting stays open: no session_finished, session retained.
        assert not any(isinstance(a, EmitSessionFinished) for a in d.actions)
        assert d.session is not None
        assert d.session.runtime_estimated
        assert not d.clear_session

    def test_t49_keeps_restart_recovery_reason(self) -> None:
        d = decide(CANONICAL["T49"]())
        assert d.reason is CompletionReason.RESTART_RECOVERY
        assert d.fault is FaultCode.ACTUATOR_OFF_TIMEOUT
        assert d.session is not None
        assert d.session.pending_termination_reason is CompletionReason.RESTART_RECOVERY

    def test_delayed_off_proof_closes_accounting_in_fault(self) -> None:
        open_session = pending(
            CompletionReason.ACTUATOR_FAULT,
            auto_session,
            runtime_estimated=True,
        )
        later = NOW + timedelta(hours=2)
        d = decide(
            make_input(
                ControllerState.FAULT,
                OffConfirmed(later),
                session=open_session,
                fault=FaultCode.ACTUATOR_OFF_TIMEOUT,
                now=later,
            )
        )
        assert d.transition_id is None
        assert d.clear_session
        assert d.final_session is not None
        assert d.final_session.off_confirmed_at_utc == later
        # §19.1 accounting: commanded -> observed OFF, the later timestamp.
        expected = (later - open_session.pulse_commanded_at_utc).total_seconds()
        assert d.final_session.session_runtime_s == pytest.approx(expected)
        assert RemoveBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED) in d.actions
        assert any(isinstance(a, EmitSessionFinished) for a in d.actions)
        # The acknowledgement-required fault remains latched.
        assert not d.clear_fault

    def test_delayed_external_off_proof_in_fault(self) -> None:
        open_session = pending(CompletionReason.ACTUATOR_FAULT)
        d = decide(
            make_input(
                ControllerState.FAULT,
                ExternalActuatorOff(NOW + SEC),
                session=open_session,
                fault=FaultCode.ACTUATOR_OFF_TIMEOUT,
            )
        )
        assert d.clear_session
        assert any(isinstance(a, EmitSessionFinished) for a in d.actions)

    def test_delayed_off_proof_in_disabled(self) -> None:
        open_session = pending(CompletionReason.ACTUATOR_FAULT)
        d = decide(
            make_input(
                ControllerState.DISABLED,
                OffConfirmed(NOW + SEC),
                session=open_session,
                enabled=False,
                fault=FaultCode.ACTUATOR_OFF_TIMEOUT,
            )
        )
        assert d.clear_session
        d2 = decide(
            make_input(
                ControllerState.DISABLED,
                ExternalActuatorOff(NOW + SEC),
                session=open_session,
                enabled=False,
            )
        )
        assert d2.clear_session

    def test_t16_closes_accounting_at_observed_external_off(self) -> None:
        """ER9/§19.1: external OFF timestamp is trustworthy closure."""
        observed = NOW - timedelta(seconds=30)
        session = auto_session()
        d = decide(
            make_input(ControllerState.WATERING, ExternalActuatorOff(observed), session=session)
        )
        assert d.transition_id == "T16"
        assert d.reason is CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE
        assert d.final_session is not None
        assert d.final_session.off_confirmed_at_utc == observed
        assert ExecuteOff(defensive=True) in d.actions  # still issued

    def test_external_off_during_pending_finalizes_committed_reason(self) -> None:
        session = pending(CompletionReason.USER_STOP)
        d = decide(make_input(ControllerState.WATERING, ExternalActuatorOff(NOW), session=session))
        assert d.transition_id == "T17"
        assert d.reason is CompletionReason.USER_STOP

    def test_measured_accounting_command_to_off(self) -> None:
        """§19.1: accounted = off_confirmed - pulse_commanded."""
        session = pending(CompletionReason.USER_STOP)
        d = decide(make_input(ControllerState.WATERING, OffConfirmed(NOW), session=session))
        assert d.final_session is not None
        expected = (NOW - session.pulse_commanded_at_utc).total_seconds()
        assert d.final_session.session_runtime_s == pytest.approx(expected)

    def test_zero_flow_session_charges_nothing_measured(self) -> None:
        session = pending(CompletionReason.USER_STOP, auto_session, pulse_commanded_at_utc=None)
        d = decide(make_input(ControllerState.WATERING, OffConfirmed(NOW), session=session))
        assert d.final_session is not None
        assert d.final_session.session_runtime_s == 0.0

    def test_off_confirmed_before_anchor_clamps_to_zero(self) -> None:
        session = pending(CompletionReason.USER_STOP)
        early = session.pulse_commanded_at_utc - SEC
        d = decide(make_input(ControllerState.WATERING, OffConfirmed(early), session=session))
        assert d.final_session is not None
        assert d.final_session.session_runtime_s == 0.0


class TestManualClamping:
    """§20.1/§35.5 duration formula and clamp reasons (MF2 pure)."""

    def test_spec_35_5_example(self) -> None:
        cfg = ZoneConfig(
            name="Bed",
            moisture_sensor="sensor.m",
            actuator="switch.a",
            start_threshold=30.0,
            target_threshold=40.0,
            pulse_duration_s=300,
            soak_duration_s=1200,
            max_cycles=4,
            max_session_runtime_s=1200,  # 20 min
            max_daily_runtime_s=3600,
            min_session_interval_s=21600,
            sensor_max_age_s=7200,
            actuator_confirm_timeout_s=30,
            manual_max_duration_s=1800,  # 30 min
        )
        d = decide(
            make_input(
                ControllerState.FAULT,
                ManualStartRequested(2700.0),  # 45 min
                fault=FaultCode.SENSOR_UNAVAILABLE,
                observation=UNAVAILABLE_OBS,
                daily=2880.0,  # 12 min remaining
                config=cfg,
            )
        )
        assert d.transition_id == "T40"
        assert d.session is not None
        assert d.session.manual_effective_duration_s == pytest.approx(720.0)
        assert set(d.session.manual_clamp_reasons) == {
            ManualClampReason.MANUAL_MAX_DURATION,
            ManualClampReason.MAX_SESSION_RUNTIME,
            ManualClampReason.REMAINING_DAILY_BUDGET,
        }

    def test_no_clamp_when_request_fits(self) -> None:
        d = decide(make_input(ControllerState.IDLE, ManualStartRequested(600.0)))
        assert d.session is not None
        assert d.session.manual_effective_duration_s == 600.0
        assert d.session.manual_clamp_reasons == ()

    def test_cap_equal_to_request_is_not_a_clamp(self) -> None:
        d = decide(make_input(ControllerState.IDLE, ManualStartRequested(1800.0)))
        assert d.session is not None
        assert d.session.manual_effective_duration_s == 1800.0
        assert ManualClampReason.MANUAL_MAX_DURATION not in d.session.manual_clamp_reasons

    def test_retained_fault_recorded_on_t40(self) -> None:
        d = decide(CANONICAL["T40"]())
        assert d.session is not None
        assert d.session.retained_sensor_fault is FaultCode.SENSOR_UNAVAILABLE
        assert d.session.mode is SessionMode.MANUAL
        assert not d.clear_fault  # starting manual does not clear the fault

    def test_manual_slot_wait(self) -> None:
        d = decide(
            make_input(ControllerState.IDLE, ManualStartRequested(600.0), resource=NOT_GRANTED)
        )
        assert d.transition_id is None
        assert d.actions == (RequestSlot(),)

    def test_manual_identity_required(self) -> None:
        with pytest.raises(ValueError):
            decide(make_input(ControllerState.IDLE, ManualStartRequested(600.0), identity=None))

    @pytest.mark.parametrize(
        ("kwargs", "expected_tag"),
        [
            ({"event_duration": 0.0}, "G-MANUAL-SAFE:invalid_duration"),
            ({"event_duration": float("nan")}, "G-MANUAL-SAFE:invalid_duration"),
            ({"event_duration": -5.0}, "G-MANUAL-SAFE:invalid_duration"),
            ({"enabled": False}, "G-EN"),
            ({"actuator": ACT_UNKNOWN}, "G-ACT"),
            ({"daily": 3600.0}, "G-MANUAL-SAFE:daily_exhausted"),
            ({"resource": BLOCKED}, "G-MANUAL-SAFE:water_resource_occupied"),
        ],
    )
    def test_manual_refusals_from_idle(self, kwargs: dict, expected_tag: str) -> None:
        duration = kwargs.pop("event_duration", 600.0)
        d = decide(make_input(ControllerState.IDLE, ManualStartRequested(duration), **kwargs))
        assert d.transition_id is None
        assert d.guard_result is not None
        assert expected_tag in d.guard_result.failed_guards

    def test_manual_refused_with_active_session(self) -> None:
        for state, session in (
            (ControllerState.WATERING, auto_session()),
            (ControllerState.SOAKING, soak_session()),
        ):
            d = decide(make_input(state, ManualStartRequested(600.0), session=session))
            assert d.transition_id is None
            assert d.guard_result is not None
            assert "G-MANUAL-SAFE:active_session" in d.guard_result.failed_guards

    def test_manual_refused_while_disabled(self) -> None:
        d = decide(make_input(ControllerState.DISABLED, ManualStartRequested(600.0), enabled=False))
        assert d.guard_result is not None
        assert "G-EN" in d.guard_result.failed_guards


class TestManualFaultMatrix:
    """MF1 pure: sensor faults permit manual; every other fault refuses."""

    @pytest.mark.parametrize(
        "fault",
        [FaultCode.SENSOR_UNAVAILABLE, FaultCode.SENSOR_STALE, FaultCode.SENSOR_INVALID],
    )
    def test_sensor_faults_permit_manual(self, fault: FaultCode) -> None:
        d = decide(
            make_input(
                ControllerState.FAULT,
                ManualStartRequested(600.0),
                fault=fault,
                observation=UNAVAILABLE_OBS,
            )
        )
        assert d.transition_id == "T40"
        assert d.session is not None
        assert d.session.retained_sensor_fault is fault

    @pytest.mark.parametrize(
        "fault",
        [
            FaultCode.ACTUATOR_UNAVAILABLE,
            FaultCode.ACTUATOR_ON_TIMEOUT,
            FaultCode.ACTUATOR_OFF_TIMEOUT,
            FaultCode.CONFIGURATION_INVALID,
            FaultCode.RESTORED_FROM_UNSAFE_STATE,
        ],
    )
    def test_blocking_faults_refuse_manual(self, fault: FaultCode) -> None:
        d = decide(make_input(ControllerState.FAULT, ManualStartRequested(600.0), fault=fault))
        assert d.transition_id == "T41"
        assert d.guard_result is not None
        assert "G-MANUAL-SENSOR" in d.guard_result.failed_guards


class TestManualCompletion:
    """T7/T8/T9 destinations evaluated at OFF confirmation (§20.3, MF3/MF4)."""

    def test_t8_returns_to_same_fault_without_event_churn(self) -> None:
        d = decide(CANONICAL["T8"]())
        assert d.fault is FaultCode.SENSOR_UNAVAILABLE
        assert not d.clear_fault
        assert not any(isinstance(a, EmitFaultSet) for a in d.actions)
        assert not any(isinstance(a, EmitFaultCleared) for a in d.actions)

    def test_t9_orders_finish_before_clear(self) -> None:
        d = decide(CANONICAL["T9"]())
        assert d.clear_fault
        kinds = [type(a) for a in d.actions]
        assert kinds.index(EmitSessionFinished) < kinds.index(EmitFaultCleared)

    def test_manual_disabled_at_completion_goes_disabled(self) -> None:
        session = pending(CompletionReason.MANUAL_COMPLETE, manual_session)
        d = decide(
            make_input(ControllerState.WATERING, OffConfirmed(NOW), session=session, enabled=False)
        )
        assert d.new_state is ControllerState.DISABLED

    def test_unexpected_manual_off_still_finalizes(self) -> None:
        """OffConfirmed on MANUAL with no pending reason finalizes robustly."""
        d = decide(
            make_input(ControllerState.WATERING, OffConfirmed(NOW), session=manual_session())
        )
        assert d.transition_id == "T7"

    def test_mf5_actuator_fault_supersedes_with_secondary(self) -> None:
        session = pending(
            CompletionReason.ACTUATOR_FAULT,
            manual_session,
            retained_sensor_fault=FaultCode.SENSOR_UNAVAILABLE,
        )
        d = decide(
            make_input(
                ControllerState.WATERING,
                OffConfirmed(NOW),
                session=session,
                fault=FaultCode.ACTUATOR_UNAVAILABLE,
            )
        )
        assert d.transition_id == "T13"
        assert d.fault is FaultCode.ACTUATOR_UNAVAILABLE
        assert d.secondary_fault is FaultCode.SENSOR_UNAVAILABLE

    def test_stop_during_manual_from_fault_restores_fault(self) -> None:
        session = pending(
            CompletionReason.USER_STOP,
            manual_session,
            retained_sensor_fault=FaultCode.SENSOR_INVALID,
        )
        d = decide(
            make_input(
                ControllerState.WATERING,
                OffConfirmed(NOW),
                session=session,
                fault=FaultCode.SENSOR_INVALID,
                observation=INVALID_OBS,
            )
        )
        assert d.transition_id == "T17"
        assert d.new_state is ControllerState.FAULT
        assert d.fault is FaultCode.SENSOR_INVALID

    def test_stop_during_manual_recovered_clears_after_finish(self) -> None:
        session = pending(
            CompletionReason.USER_STOP,
            manual_session,
            retained_sensor_fault=FaultCode.SENSOR_INVALID,
        )
        d = decide(
            make_input(
                ControllerState.WATERING,
                OffConfirmed(NOW),
                session=session,
                fault=FaultCode.SENSOR_INVALID,
                observation=obs(),
            )
        )
        assert d.new_state is ControllerState.IDLE
        assert d.clear_fault
        kinds = [type(a) for a in d.actions]
        assert kinds.index(EmitSessionFinished) < kinds.index(EmitFaultCleared)


class TestOnConfirmation:
    def test_auto_on_confirmed_arms_pulse_deadline(self) -> None:
        at = NOW
        d = decide(
            make_input(
                ControllerState.WATERING,
                OnConfirmed(at),
                session=auto_session(pulse_confirmed_at_utc=None, pulse_ends_at_utc=None),
            )
        )
        assert d.session is not None
        assert d.session.pulse_confirmed_at_utc == at
        assert d.session.pulse_ends_at_utc == at + timedelta(seconds=300)
        timer = next(a for a in d.actions if isinstance(a, ArmTimer))
        assert timer.kind is TimerKind.PULSE_END

    def test_manual_on_confirmed_arms_manual_deadline(self) -> None:
        d = decide(make_input(ControllerState.WATERING, OnConfirmed(NOW), session=manual_session()))
        timer = next(a for a in d.actions if isinstance(a, ArmTimer))
        assert timer.kind is TimerKind.MANUAL_END
        assert timer.at_utc == NOW + timedelta(seconds=540)

    def test_on_confirmed_with_pending_skips_timer(self) -> None:
        d = decide(
            make_input(
                ControllerState.WATERING,
                OnConfirmed(NOW),
                session=pending(CompletionReason.USER_STOP),
            )
        )
        assert not any(isinstance(a, ArmTimer) for a in d.actions)

    def test_stale_on_timeout_after_confirmation_no_ops(self) -> None:
        d = decide(make_input(ControllerState.WATERING, OnConfirmTimeout(), session=auto_session()))
        # auto_session() has pulse_confirmed_at set: the timeout is obsolete.
        assert d.no_op

    def test_on_timeout_commits_defensive_off(self) -> None:
        unconfirmed = auto_session(pulse_confirmed_at_utc=None, pulse_ends_at_utc=None)
        d = decide(make_input(ControllerState.WATERING, OnConfirmTimeout(), session=unconfirmed))
        assert d.fault is FaultCode.ACTUATOR_ON_TIMEOUT
        assert ExecuteOff(defensive=True) in d.actions

    def test_actuator_unavailable_commits_defensive_off(self) -> None:
        d = decide(
            make_input(
                ControllerState.WATERING,
                ActuatorBecameUnavailable(),
                session=auto_session(),
                actuator=ACT_UNKNOWN,
            )
        )
        assert d.fault is FaultCode.ACTUATOR_UNAVAILABLE
        assert ExecuteOff(defensive=True) in d.actions


class TestSoakingContinuation:
    def test_t25_increments_cycle_and_rearms_watchdog(self) -> None:
        d = decide(CANONICAL["T25"]())
        assert d.session is not None
        assert d.session.cycle == 2
        assert d.session.pulse_intent_at_utc == NOW
        assert d.session.pulse_commanded_at_utc is None
        assert d.session.soak_ends_at_utc is None
        assert d.session.last_recheck_value == 35.0
        arm = next(a for a in d.actions if isinstance(a, ArmWatchdog))
        assert arm.token.generation == d.session.sensor_freshness_watchdog_generation
        assert not any(isinstance(a, EmitSessionStarted) for a in d.actions)

    def test_session_fit_equality_continues(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                MoistureReport(obs(value=35.0)),
                session=soak_session(session_runtime_s=1500.0),
                observation=obs(value=35.0),
            )
        )
        assert d.transition_id == "T25"

    def test_soaking_slot_wait_records_recheck(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                MoistureReport(obs(value=35.0)),
                session=soak_session(),
                observation=obs(value=35.0),
                resource=NOT_GRANTED,
            )
        )
        assert d.transition_id is None
        assert d.actions == (RequestSlot(),)
        assert d.session is not None
        assert d.session.last_recheck_value == 35.0

    def test_soaking_blockers_prevent_next_pulse(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                MoistureReport(obs(value=35.0)),
                session=soak_session(),
                observation=obs(value=35.0),
                resource=ResourceAssessment(slot_granted=True, blockers_empty=False),
            )
        )
        assert d.transition_id is None
        assert d.actions == (RequestSlot(),)

    def test_soaking_actuator_not_proven_off_waits(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                MoistureReport(obs(value=35.0)),
                session=soak_session(),
                observation=obs(value=35.0),
                actuator=ActuatorAssessment(available=True, proven_off=False, observed_on=False),
            )
        )
        assert d.transition_id is None

    def test_slot_granted_in_soaking_starts_t25(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                SlotGranted(),
                session=soak_session(),
                observation=obs(value=35.0),
            )
        )
        assert d.transition_id == "T25"

    def test_slot_granted_in_soaking_declined_when_stale(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                SlotGranted(),
                session=soak_session(),
                observation=obs(value=35.0, at=NOW - timedelta(hours=3)),
            )
        )
        assert d.transition_id is None
        assert ReleaseSlot() in d.actions

    def test_t24_records_last_recheck_value(self) -> None:
        d = decide(CANONICAL["T24"]())
        assert d.final_session is not None
        assert d.final_session.last_recheck_value == 45.0

    def test_completion_while_disabled_goes_disabled(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                MoistureReport(obs(value=45.0)),
                session=soak_session(),
                observation=obs(value=45.0),
                enabled=False,
            )
        )
        assert d.transition_id == "T24"
        assert d.new_state is ControllerState.DISABLED

    def test_t26_t27_t28_reasons(self) -> None:
        assert decide(CANONICAL["T26"]()).reason is CompletionReason.MAX_CYCLES
        assert decide(CANONICAL["T27"]()).reason is CompletionReason.MAX_SESSION_RUNTIME
        assert decide(CANONICAL["T28"]()).reason is CompletionReason.DAILY_RUNTIME_LIMIT


class TestSoakingExternalInterference:
    def test_external_on_commits_defensive_off_and_blocker(self) -> None:
        session = soak_session(last_recheck_value=33.0)
        d = decide(
            make_input(
                ControllerState.SOAKING, ExternalActuatorOn(), session=session, actuator=ACT_ON
            )
        )
        assert d.transition_id is None
        assert AddBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED) in d.actions
        assert ExecuteOff(defensive=True) in d.actions
        assert d.session is not None
        assert (
            d.session.pending_termination_reason is CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE
        )
        assert d.session.last_recheck_value is None  # soak reports invalidated

    def test_second_external_on_no_ops(self) -> None:
        session = pending(CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE, soak_session)
        d = decide(
            make_input(
                ControllerState.SOAKING, ExternalActuatorOn(), session=session, actuator=ACT_ON
            )
        )
        assert d.no_op

    def test_t33_removes_only_matching_blocker(self) -> None:
        d = decide(CANONICAL["T33"]())
        assert RemoveBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED) in d.actions
        assert d.reason is CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE

    def test_t33_while_disabled_goes_disabled(self) -> None:
        session = pending(CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE, soak_session)
        d = decide(
            make_input(ControllerState.SOAKING, OffConfirmed(NOW), session=session, enabled=False)
        )
        assert d.transition_id == "T33"
        assert d.new_state is ControllerState.DISABLED

    def test_t34_retains_blocker(self) -> None:
        d = decide(CANONICAL["T34"]())
        assert d.fault is FaultCode.ACTUATOR_OFF_TIMEOUT
        assert not any(isinstance(a, RemoveBlocker) for a in d.actions)
        assert not d.clear_session  # accounting/session stays open

    def test_external_off_via_state_change_finalizes_t33(self) -> None:
        session = pending(CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE, soak_session)
        d = decide(make_input(ControllerState.SOAKING, ExternalActuatorOff(NOW), session=session))
        assert d.transition_id == "T33"

    def test_other_events_no_op_while_interference_pending(self) -> None:
        session = pending(CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE, soak_session)
        for event in (
            StopRequested(),
            DisableRequested(),
            SoakDeadlineReached(),
            GraceDeadlineReached(),
            MoistureReport(obs(value=45.0)),
            HomeAssistantShutdown(),
            ConfigEntryReload(),
            ConfigChangedPrepare(),
        ):
            d = decide(make_input(ControllerState.SOAKING, event, session=session))
            assert d.no_op, f"{type(event).__name__} must no-op while pending"

    def test_stray_off_evidence_without_pending_no_ops(self) -> None:
        d = decide(make_input(ControllerState.SOAKING, OffConfirmed(NOW), session=soak_session()))
        assert d.no_op
        d2 = decide(make_input(ControllerState.SOAKING, OffNotConfirmed(), session=soak_session()))
        assert d2.no_op


class TestSoakingLifecycle:
    def test_t37_preserves_session(self) -> None:
        d = decide(CANONICAL["T37"]())
        assert not d.clear_session
        assert d.reason is None
        assert d.actions == (PersistState("soaking_preserved"),)

    def test_t35_t36_t38_t39_reasons_and_off_assurance(self) -> None:
        for row, reason in (
            ("T35", CompletionReason.USER_STOP),
            ("T36", CompletionReason.ZONE_DISABLED),
            ("T38", CompletionReason.CONFIG_RELOAD),
            ("T39", CompletionReason.CONFIG_CHANGED),
        ):
            d = decide(CANONICAL[row]())
            assert d.reason is reason
            assert ExecuteOff(defensive=True) in d.actions
            assert d.clear_session

    def test_t32_from_recheck_path(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                MoistureReport(obs(value=35.0)),
                session=soak_session(),
                observation=obs(value=35.0),
                actuator=ActuatorAssessment(available=False, proven_off=True, observed_on=False),
            )
        )
        assert d.transition_id == "T32"
        assert d.fault is FaultCode.ACTUATOR_UNAVAILABLE


class TestStartupRecovery:
    """T48-T51 pure decisions (§25.2-§25.3)."""

    def test_found_off_finalizes_with_intent_anchor(self) -> None:
        session = auto_session()
        d = decide(
            make_input(
                ControllerState.WATERING,
                StartupPersistedWatering(ActuatorFinding.OFF),
                session=session,
            )
        )
        assert d.transition_id == "T48"
        assert d.reason is CompletionReason.RESTART_RECOVERY
        assert d.final_session is not None
        assert d.final_session.runtime_estimated
        # §19.2: intent -> reconciliation time, never scheduled pulse end.
        expected = (NOW - session.pulse_intent_at_utc).total_seconds()
        assert d.final_session.session_runtime_s == pytest.approx(
            session.session_runtime_s + expected
        )

    def test_found_on_commits_defensive_off(self) -> None:
        d = decide(
            make_input(
                ControllerState.WATERING,
                StartupPersistedWatering(ActuatorFinding.ON),
                session=auto_session(),
                actuator=ACT_ON,
            )
        )
        assert d.transition_id is None
        assert AddBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED) in d.actions
        assert ExecuteOff(defensive=True) in d.actions
        assert d.session is not None
        assert d.session.pending_termination_reason is CompletionReason.RESTART_RECOVERY
        assert d.session.runtime_estimated
        # OFF confirmation then finalizes T48 from the intent anchor.
        off_at = NOW + timedelta(minutes=1)
        d2 = decide(
            make_input(
                ControllerState.WATERING,
                OffConfirmed(off_at),
                session=d.session,
                now=off_at,
            )
        )
        assert d2.transition_id == "T48"

    def test_confirmed_off_releases_only_the_matching_blocker(self) -> None:
        """F1 pure: T48 releases (record, integration_off_unconfirmed).

        SPEC 11.3 step 5: confirmed terminal OFF persists the confirmation,
        closes accounting, releases the slot and removes ONLY the matching
        key.  T49 (OFF still unproven) must keep it instead.
        """
        armed = decide(
            make_input(
                ControllerState.WATERING,
                StartupPersistedWatering(ActuatorFinding.ON),
                session=auto_session(),
                actuator=ACT_ON,
            )
        )
        assert AddBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED) in armed.actions
        off_at = NOW + timedelta(minutes=1)
        confirmed = decide(
            make_input(
                ControllerState.WATERING,
                OffConfirmed(off_at),
                session=armed.session,
                now=off_at,
            )
        )
        assert confirmed.transition_id == "T48"
        assert RemoveBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED) in confirmed.actions
        assert ReleaseSlot() in confirmed.actions
        # Only that one reason is ever removed by this row.
        removals = [a for a in confirmed.actions if isinstance(a, RemoveBlocker)]
        assert removals == [RemoveBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED)]
        # The unproven branch keeps the key instead of releasing it.
        unproven = decide(
            make_input(
                ControllerState.WATERING,
                OffNotConfirmed(),
                session=armed.session,
                actuator=ACT_ON,
            )
        )
        assert unproven.transition_id == "T49"
        assert not [a for a in unproven.actions if isinstance(a, RemoveBlocker)]
        assert AddBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED) in unproven.actions

    def test_unproven_commits_and_can_escalate_to_t49(self) -> None:
        d = decide(
            make_input(
                ControllerState.WATERING,
                StartupPersistedWatering(ActuatorFinding.UNPROVEN),
                session=auto_session(),
                actuator=ACT_UNKNOWN,
            )
        )
        assert d.session is not None
        d2 = decide(
            make_input(
                ControllerState.WATERING,
                OffNotConfirmed(),
                session=d.session,
                actuator=ACT_UNKNOWN,
            )
        )
        assert d2.transition_id == "T49"

    def test_t50_rebases_owner_only(self) -> None:
        """LC10 pure: rebase changes owner_run_id and nothing else."""
        session = soak_session(soak_ends=NOW + timedelta(minutes=5))
        d = decide(
            make_input(
                ControllerState.SOAKING,
                StartupPersistedSoaking(trusted=True, current_run_id="run-2"),
                session=session,
            )
        )
        assert d.transition_id == "T50"
        assert d.session is not None
        assert d.session.owner_run_id == "run-2"
        assert d.session == session.evolve(owner_run_id="run-2")
        timer = next(a for a in d.actions if isinstance(a, ArmTimer))
        assert timer.kind is TimerKind.SOAK_END

    def test_t50_offline_soak_deadline_arms_grace(self) -> None:
        session = soak_session(soak_ends=NOW - timedelta(minutes=5))
        d = decide(
            make_input(
                ControllerState.SOAKING,
                StartupPersistedSoaking(trusted=True, current_run_id="run-2"),
                session=session,
            )
        )
        timer = next(a for a in d.actions if isinstance(a, ArmTimer))
        assert timer.kind is TimerKind.GRACE

    def test_t50_both_deadlines_passed_arms_nothing(self) -> None:
        session = soak_session(soak_ends=NOW - timedelta(hours=3))
        d = decide(
            make_input(
                ControllerState.SOAKING,
                StartupPersistedSoaking(trusted=True, current_run_id="run-2"),
                session=session,
            )
        )
        assert not any(isinstance(a, ArmTimer) for a in d.actions)

    def test_t50_requires_run_id(self) -> None:
        with pytest.raises(ValueError):
            decide(
                make_input(
                    ControllerState.SOAKING,
                    StartupPersistedSoaking(trusted=True),
                    session=soak_session(),
                )
            )

    def test_t51_unsafe_goes_fault(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                StartupPersistedSoaking(trusted=False, unsafe_fault=FaultCode.ACTUATOR_OFF_TIMEOUT),
                session=soak_session(),
                actuator=ACT_UNKNOWN,
            )
        )
        assert d.transition_id == "T51"
        assert d.new_state is ControllerState.FAULT
        assert d.fault is FaultCode.ACTUATOR_OFF_TIMEOUT

    def test_t51_disabled_goes_disabled(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                StartupPersistedSoaking(trusted=False),
                session=soak_session(),
                enabled=False,
            )
        )
        assert d.new_state is ControllerState.DISABLED

    def test_t52_from_every_state(self) -> None:
        for state in ControllerState:
            session = auto_session() if state is ControllerState.WATERING else None
            if state is ControllerState.SOAKING:
                session = soak_session()
            d = decide(make_input(state, StoreIntegrityLost(), session=session))
            assert d.transition_id == "T52"
            assert d.fault is FaultCode.RESTORED_FROM_UNSAFE_STATE

    def test_t53_regardless_of_state(self) -> None:
        d = decide(
            make_input(ControllerState.DISABLED, ConfigurationInvalid(at_setup=True), enabled=False)
        )
        assert d.transition_id == "T53"


class TestExternalOccupancy:
    def test_t55_disabled_external_on_adds_blocker_without_off(self) -> None:
        decision = decide(CANONICAL["T55"]())
        assert decision.transition_id == "T55"
        assert decision.new_state is ControllerState.DISABLED
        assert any(
            isinstance(action, AddBlocker) and action.reason is BlockerReason.EXTERNAL_FLOW
            for action in decision.actions
        )
        assert any(isinstance(action, SetExternalOn) for action in decision.actions)
        assert not any(isinstance(action, ExecuteOff) for action in decision.actions)

    """T54/T55/T58/T59 and keyed-blocker semantics (pure obligations)."""

    def test_t54_adds_external_flow_without_off(self) -> None:
        d = decide(CANONICAL["T54"]())
        assert SetExternalOn(True) in d.actions
        assert AddBlocker(BlockerReason.EXTERNAL_FLOW) in d.actions
        assert not any(isinstance(a, ExecuteOff) for a in d.actions)

    def test_t58_removes_only_external_flow(self) -> None:
        d = decide(CANONICAL["T58"]())
        assert RemoveBlocker(BlockerReason.EXTERNAL_FLOW) in d.actions
        assert not any(
            isinstance(a, RemoveBlocker) and a.reason is not BlockerReason.EXTERNAL_FLOW
            for a in d.actions
        )

    def test_duplicate_external_on_no_ops(self) -> None:
        assert decide(make_input(ControllerState.IDLE, ExternalActuatorOn(), external=True)).no_op
        assert decide(
            make_input(ControllerState.DISABLED, ExternalActuatorOn(), enabled=False, external=True)
        ).no_op

    def test_off_without_occupancy_no_ops(self) -> None:
        assert decide(make_input(ControllerState.IDLE, ExternalActuatorOff(NOW))).no_op
        assert decide(
            make_input(ControllerState.DISABLED, ExternalActuatorOff(NOW), enabled=False)
        ).no_op

    def test_fault_state_external_bookkeeping(self) -> None:
        """§11.4: non-session sensor-only FAULT still tracks external flow."""
        d = decide(
            make_input(
                ControllerState.FAULT,
                ExternalActuatorOn(),
                fault=FaultCode.SENSOR_STALE,
                actuator=ACT_ON,
            )
        )
        assert AddBlocker(BlockerReason.EXTERNAL_FLOW) in d.actions
        assert d.transition_id is None
        again = decide(
            make_input(
                ControllerState.FAULT,
                ExternalActuatorOn(),
                fault=FaultCode.SENSOR_STALE,
                external=True,
            )
        )
        assert again.no_op
        off = decide(
            make_input(
                ControllerState.FAULT,
                ExternalActuatorOff(NOW),
                fault=FaultCode.SENSOR_STALE,
                external=True,
            )
        )
        assert RemoveBlocker(BlockerReason.EXTERNAL_FLOW) in off.actions


class TestFaultHandling:
    def test_t42_sensor_auto_clear(self) -> None:
        d = decide(CANONICAL["T42"]())
        assert d.clear_fault
        assert EmitFaultCleared(FaultCode.SENSOR_STALE) in d.actions

    def test_auto_clear_requires_fresh_valid(self) -> None:
        d = decide(
            make_input(
                ControllerState.FAULT,
                MoistureReport(stale_obs(NOW - timedelta(hours=3))),
                fault=FaultCode.SENSOR_STALE,
                observation=stale_obs(NOW - timedelta(hours=3)),
            )
        )
        assert d.no_op

    def test_auto_clear_blocked_during_manual_session(self) -> None:
        """§26.1: clearing is deferred until the manual session finishes."""
        d = decide(
            make_input(
                ControllerState.FAULT,
                MoistureReport(obs()),
                fault=FaultCode.SENSOR_STALE,
                session=manual_session(),
            )
        )
        assert d.no_op

    def test_actuator_fault_auto_clears_on_off_proof(self) -> None:
        d = decide(
            make_input(
                ControllerState.FAULT,
                ExternalActuatorOff(NOW),
                fault=FaultCode.ACTUATOR_UNAVAILABLE,
            )
        )
        assert d.transition_id == "T42"

    def test_no_fault_auto_clear_no_ops(self) -> None:
        d = decide(make_input(ControllerState.FAULT, MoistureReport(obs())))
        assert d.no_op

    def test_off_timeout_never_auto_clears(self) -> None:
        d = decide(
            make_input(
                ControllerState.FAULT,
                ExternalActuatorOff(NOW),
                fault=FaultCode.ACTUATOR_OFF_TIMEOUT,
            )
        )
        assert d.no_op  # requires acknowledgement (T43), never auto (T42)

    def test_t43_ack_after_off_proof(self) -> None:
        d = decide(CANONICAL["T43"]())
        assert d.clear_fault
        assert d.new_state is ControllerState.IDLE

    def test_t44_refused_while_unresolved(self) -> None:
        d = decide(CANONICAL["T44"]())
        assert not d.clear_fault
        assert d.new_state is ControllerState.FAULT

    def test_configuration_invalid_refuses_clear_fault(self) -> None:
        d = decide(
            make_input(
                ControllerState.FAULT,
                ClearFaultRequested(),
                fault=FaultCode.CONFIGURATION_INVALID,
            )
        )
        assert d.transition_id == "T44"
        assert d.guard_result is not None
        assert "fault-requires-reconfigure" in d.guard_result.failed_guards

    def test_sensor_fault_clear_request(self) -> None:
        resolved = decide(
            make_input(ControllerState.FAULT, ClearFaultRequested(), fault=FaultCode.SENSOR_STALE)
        )
        assert resolved.transition_id == "T43"
        unresolved = decide(
            make_input(
                ControllerState.FAULT,
                ClearFaultRequested(),
                fault=FaultCode.SENSOR_STALE,
                observation=UNAVAILABLE_OBS,
            )
        )
        assert unresolved.transition_id == "T44"

    def test_restored_from_unsafe_state_ack_requires_off(self) -> None:
        refused = decide(
            make_input(
                ControllerState.FAULT,
                ClearFaultRequested(),
                fault=FaultCode.RESTORED_FROM_UNSAFE_STATE,
                actuator=ACT_UNKNOWN,
            )
        )
        assert refused.transition_id == "T44"
        allowed = decide(
            make_input(
                ControllerState.FAULT,
                ClearFaultRequested(),
                fault=FaultCode.RESTORED_FROM_UNSAFE_STATE,
            )
        )
        assert allowed.transition_id == "T43"

    def test_clear_fault_without_fault_no_ops(self) -> None:
        assert decide(make_input(ControllerState.FAULT, ClearFaultRequested())).no_op

    def test_stray_off_confirmed_without_session_no_ops(self) -> None:
        assert decide(
            make_input(ControllerState.FAULT, OffConfirmed(NOW), fault=FaultCode.SENSOR_STALE)
        ).no_op

    def test_config_invalid_in_fault(self) -> None:
        same = decide(
            make_input(
                ControllerState.FAULT,
                ConfigurationInvalid(),
                fault=FaultCode.CONFIGURATION_INVALID,
            )
        )
        assert same.no_op
        different = decide(
            make_input(ControllerState.FAULT, ConfigurationInvalid(), fault=FaultCode.SENSOR_STALE)
        )
        assert different.transition_id == "T5"

    def test_t45_retains_metadata_t46_restores(self) -> None:
        d45 = decide(CANONICAL["T45"]())
        assert d45.fault is None  # metadata retained by controller, not cleared
        assert not d45.clear_fault
        d46 = decide(CANONICAL["T46"]())
        assert d46.fault is FaultCode.SENSOR_STALE

    def test_t47_schedules_evaluation(self) -> None:
        d = decide(CANONICAL["T47"]())
        assert ScheduleEvaluation() in d.actions


class TestNoOpsAndErrors:
    def test_inactive_state_no_ops(self) -> None:
        cases = [
            (ControllerState.IDLE, StopRequested(), {}),
            (ControllerState.IDLE, EnableRequested(), {}),
            (ControllerState.IDLE, ClearFaultRequested(), {}),
            (ControllerState.IDLE, OffConfirmed(NOW), {}),
            (ControllerState.IDLE, SoakDeadlineReached(), {}),
            (ControllerState.DISABLED, AutoEvaluate(), {"enabled": False}),
            (ControllerState.DISABLED, StopRequested(), {"enabled": False}),
            (ControllerState.DISABLED, DisableRequested(), {"enabled": False}),
            (ControllerState.FAULT, AutoEvaluate(), {"fault": FaultCode.SENSOR_STALE}),
            (ControllerState.FAULT, StopRequested(), {"fault": FaultCode.SENSOR_STALE}),
            (
                ControllerState.FAULT,
                ExternalActuatorOn(),
                {"fault": FaultCode.SENSOR_STALE, "external": True},
            ),
        ]
        for state, event, kwargs in cases:
            d = decide(make_input(state, event, **kwargs))  # type: ignore[arg-type]
            assert d.no_op, f"{state} + {type(event).__name__} must no-op"

    def test_soaking_stray_pulse_deadline_no_ops(self) -> None:
        d = decide(
            make_input(ControllerState.SOAKING, PulseDeadlineReached(), session=soak_session())
        )
        assert d.no_op

    def test_watering_stray_events_no_op(self) -> None:
        for event in (SoakDeadlineReached(), GraceDeadlineReached(), AutoEvaluate()):
            d = decide(make_input(ControllerState.WATERING, event, session=auto_session()))
            assert d.no_op

    def test_watering_without_session_raises(self) -> None:
        with pytest.raises(ValueError):
            decide(make_input(ControllerState.WATERING, StopRequested()))

    def test_soaking_without_session_raises(self) -> None:
        with pytest.raises(ValueError):
            decide(make_input(ControllerState.SOAKING, StopRequested()))

    def test_startup_soaking_event_in_watering_no_ops(self) -> None:
        d = decide(
            make_input(
                ControllerState.WATERING,
                StartupPersistedSoaking(trusted=False),
                session=auto_session(),
            )
        )
        assert d.no_op

    def test_startup_watering_event_in_soaking_no_ops(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                StartupPersistedWatering(ActuatorFinding.OFF),
                session=soak_session(),
            )
        )
        assert d.no_op

    def test_determinism_same_input_same_decision(self) -> None:
        for row in ("T1", "T24", "T56"):
            assert decide(CANONICAL[row]()) == decide(CANONICAL[row]())


class TestRemainingCommitAndBranchPaths:
    @pytest.mark.parametrize(
        ("event", "reason"),
        [
            (DisableRequested(), CompletionReason.ZONE_DISABLED),
            (HomeAssistantShutdown(), CompletionReason.HOME_ASSISTANT_SHUTDOWN),
            (ConfigEntryReload(), CompletionReason.CONFIG_RELOAD),
            (ConfigChangedPrepare(), CompletionReason.CONFIG_CHANGED),
        ],
    )
    def test_watering_lifecycle_commits(self, event: object, reason: CompletionReason) -> None:
        d = decide(make_input(ControllerState.WATERING, event, session=auto_session()))
        assert d.transition_id is None
        assert d.session is not None
        assert d.session.pending_termination_reason is reason
        assert sum(isinstance(a, ExecuteOff) for a in d.actions) == 1

    def test_soaking_session_without_recheck_deadline_waits(self) -> None:
        """A post-deadline report cannot qualify without recheck anchors."""
        session = soak_session(recheck_not_before_utc=None)
        d = decide(
            make_input(
                ControllerState.SOAKING,
                MoistureReport(obs(value=45.0)),
                session=session,
                observation=obs(value=45.0),
            )
        )
        assert d.no_op

    def test_manual_refused_with_lingering_session_record(self) -> None:
        d = decide(
            make_input(ControllerState.IDLE, ManualStartRequested(600.0), session=manual_session())
        )
        assert d.guard_result is not None
        assert "G-MANUAL-SAFE:active_session" in d.guard_result.failed_guards

    def test_disabled_off_confirmed_without_session_no_ops(self) -> None:
        d = decide(make_input(ControllerState.DISABLED, OffConfirmed(NOW), enabled=False))
        assert d.no_op

    def test_new_fault_at_cancellation_finalize_goes_fault(self) -> None:
        """POST rule: a new (non-retained) fault at finalize wins IDLE."""
        session = pending(CompletionReason.USER_STOP)
        d = decide(
            make_input(
                ControllerState.WATERING,
                OffConfirmed(NOW),
                session=session,
                fault=FaultCode.ACTUATOR_UNAVAILABLE,
            )
        )
        assert d.transition_id == "T17"
        assert d.new_state is ControllerState.FAULT
        assert d.fault is FaultCode.ACTUATOR_UNAVAILABLE

    def test_auto_evaluate_in_soaking_without_qualifying_report_no_ops(self) -> None:
        d = decide(
            make_input(
                ControllerState.SOAKING,
                AutoEvaluate(),
                session=soak_session(),
                observation=obs(value=33.0, at=NOW - timedelta(minutes=30)),
            )
        )
        assert d.no_op


class TestNewZoneSafeDefault:
    """LC14/I20: the fresh-zone DISABLED default is inert at the pure layer.

    The authoritative fresh-zone default itself is persisted by the entry
    reconciler (a Home Assistant layer), so these tests own the pure half of
    the contract: a zone holding that default admits nothing, and only an
    explicit enable moves it, through the existing T46/T47 rows.
    """

    def _fully_eligible(self, event: object) -> TransitionInput:
        """Everything an AUTO start needs, except ``enabled``."""
        return make_input(
            ControllerState.DISABLED,
            event,
            enabled=False,
            observation=obs(value=27.0),  # VALID, fresh, strictly below start 30
            actuator=READY,  # available and proven OFF
            resource=GRANTED,  # slot grantable, no blocker
            daily=0.0,  # whole daily budget available
            last_end=None,  # minimum interval satisfied
            fault=None,
        )

    @pytest.mark.parametrize(
        "event",
        [AutoEvaluate(), MoistureReport(obs(value=27.0)), SlotGranted()],
    )
    def test_lc14_fresh_default_admits_no_auto_when_every_other_gate_passes(
        self, event: object
    ) -> None:
        d = decide(self._fully_eligible(event))
        assert d.no_op
        assert d.new_state is None
        assert d.session is None
        assert not any(isinstance(action, (TurnOn, RequestSlot)) for action in d.actions)

    def test_lc14_repeated_qualifying_reports_never_arm_the_fresh_default(self) -> None:
        """Two further VALID, fresh, below-threshold reports stay inert."""
        for offset in (60, 120):
            report = MoistureReport(obs(value=26.0, at=NOW + timedelta(seconds=offset)))
            d = decide(
                make_input(
                    ControllerState.DISABLED,
                    report,
                    enabled=False,
                    observation=report.observation,
                    now=NOW + timedelta(seconds=offset),
                )
            )
            assert d.no_op
            assert d.session is None
            assert not any(isinstance(action, (TurnOn, RequestSlot)) for action in d.actions)

    def test_lc14_manual_is_refused_on_the_fresh_default(self) -> None:
        d = decide(make_input(ControllerState.DISABLED, ManualStartRequested(600.0), enabled=False))
        assert d.session is None
        assert d.guard_result is not None
        assert not d.guard_result.passed
        assert "G-EN" in d.guard_result.failed_guards
        assert not any(isinstance(action, TurnOn) for action in d.actions)

    def test_lc14_explicit_enable_uses_the_existing_t47_path(self) -> None:
        d = decide(self._fully_eligible(EnableRequested()))
        assert d.transition_id == "T47"
        assert d.new_state is ControllerState.IDLE
        assert any(isinstance(action, ScheduleEvaluation) for action in d.actions)
        assert not any(isinstance(action, TurnOn) for action in d.actions)

    def test_lc14_explicit_enable_with_a_fault_uses_the_existing_t46_path(self) -> None:
        d = decide(
            make_input(
                ControllerState.DISABLED,
                EnableRequested(),
                enabled=False,
                fault=FaultCode.SENSOR_STALE,
            )
        )
        assert d.transition_id == "T46"
        assert d.new_state is ControllerState.FAULT
        assert d.fault is FaultCode.SENSOR_STALE

    def test_lc14_controller_state_set_is_still_exactly_five(self) -> None:
        assert [member.value for member in ControllerState] == [
            "disabled",
            "idle",
            "watering",
            "soaking",
            "fault",
        ]
