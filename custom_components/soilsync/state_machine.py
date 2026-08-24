"""Pure deterministic state machine for SoilSync.

Implements every formal transition T1-T59 (SPECIFICATION.md §14), the guard
legend, exact hysteresis (§17), pulse/soak/recheck and AUTO freshness
watchdog decisions (§18), manual clamping (§20), and first-terminal-request
arbitration (§22.2) as one pure function: ``decide(TransitionInput) ->
Decision``. No homeassistant imports, no I/O, no hidden clock — time comes
only from ``TransitionInput.now_utc`` (§37).

Execution model
---------------
WATERING exits are two-phase, matching §22's cooperative termination:

1. A terminal trigger *commits* ``session.pending_termination_reason`` (the
   first request accepted owns the session reason) and requests the one
   idempotent OFF operation. The commit decision is not a formal transition
   (``transition_id=None``); the zone remains WATERING while OFF executes
   (§12.1: "ON until termination/OFF sequence"). Faults latch at commit so
   "AUTO WATERING stops immediately" (§26.1) is visible while OFF runs.
2. OFF evidence finalizes the transition: ``OffConfirmed`` yields the §14
   row for the committed reason, with the destination evaluated at OFF
   confirmation as §20.3 requires; ``OffNotConfirmed`` yields T15/T34/T49
   with fault ``ACTUATOR_OFF_TIMEOUT``, superseding the requested
   destination (§22.2) while leaving accounting open for later OFF proof.

An external OFF observed during WATERING is itself trustworthy OFF evidence
(§19.1), so T16 finalizes immediately at that event. SOAKING, IDLE,
DISABLED, and FAULT rows are single-phase because no integration-commanded
water is flowing.

``assert`` statements are internal-consistency checks on adapter contracts,
not decision logic; they are excluded from the branch-coverage gate.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from .const import (
    GUARD_ACTUATOR,
    GUARD_DAILY_FIT,
    GUARD_ENABLED,
    GUARD_FRESH,
    GUARD_INTERVAL,
    GUARD_MANUAL_SAFE,
    GUARD_MANUAL_SENSOR,
    GUARD_POST,
    GUARD_SLOT,
    GUARD_START,
)
from .models import (
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
    Decision,
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
    GuardResult,
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
    RuntimeEstimationReason,
    ScheduleEvaluation,
    SessionContext,
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
)

# Sensor fault code -> WATERING finalize row (§14 T10/T11/T57).
_SENSOR_FAULT_ROWS = {
    FaultCode.SENSOR_UNAVAILABLE: "T10",
    FaultCode.SENSOR_INVALID: "T11",
    FaultCode.SENSOR_STALE: "T57",
}

# Committed cancellation reason -> WATERING finalize row.
_CANCELLATION_ROWS = {
    CompletionReason.USER_STOP: "T17",
    CompletionReason.ZONE_DISABLED: "T18",
    CompletionReason.HOME_ASSISTANT_SHUTDOWN: "T19",
    CompletionReason.CONFIG_RELOAD: "T20",
    CompletionReason.CONFIG_CHANGED: "T21",
    CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE: "T16",
}


def decide(inp: TransitionInput) -> Decision:
    """Compute the deterministic decision for one normalized event."""
    event = inp.event

    # Cross-state rows.
    if isinstance(event, StoreIntegrityLost):
        return _integrity_lost(inp)  # T52
    if isinstance(event, ConfigurationInvalid) and event.at_setup:
        return _configuration_invalid(inp, "T53")

    if inp.state is ControllerState.IDLE:
        return _decide_idle(inp)
    if inp.state is ControllerState.DISABLED:
        return _decide_disabled(inp)
    if inp.state is ControllerState.WATERING:
        return _decide_watering(inp)
    if inp.state is ControllerState.SOAKING:
        return _decide_soaking(inp)
    return _decide_fault(inp)


# ---------------------------------------------------------------------------
# Guard helpers (§14 legend, §16, §17)
# ---------------------------------------------------------------------------


def _fresh_valid(inp: TransitionInput, obs: MoistureObservation | None = None) -> bool:
    """G-FRESH: observation VALID and fresh; equality is fresh (§6)."""
    o = obs if obs is not None else inp.observation
    return o.classification is MoistureClassification.VALID and o.is_fresh(
        inp.now_utc, inp.config.sensor_max_age_s
    )


def _interval_elapsed(inp: TransitionInput) -> bool:
    """G-INT: minimum automatic-session interval elapsed (§19.4)."""
    if inp.last_session_end_utc is None:
        return True
    delta = inp.now_utc - inp.last_session_end_utc
    return delta >= timedelta(seconds=inp.config.min_session_interval_s)


def _actuator_ready(inp: TransitionInput) -> bool:
    """G-ACT: available and terminal OFF before ON (§11.1)."""
    return inp.actuator.available and inp.actuator.proven_off


def _daily_fits(inp: TransitionInput) -> bool:
    """G-DAY: current-day runtime + whole pulse <= daily limit (§18.3)."""
    return inp.daily_runtime_s + inp.config.pulse_duration_s <= inp.config.max_daily_runtime_s


def _session_fits(inp: TransitionInput, session: SessionContext) -> bool:
    """G-SESS: session runtime + whole pulse <= session limit (§18.3)."""
    return (
        session.session_runtime_s + inp.config.pulse_duration_s <= inp.config.max_session_runtime_s
    )


def _post_qualifies(inp: TransitionInput) -> bool:
    """G-POST (§18.4): VALID, fresh, reported_at >= recheck_not_before."""
    session = inp.session
    if session is None or session.recheck_not_before_utc is None:
        return False
    if not _fresh_valid(inp):
        return False
    obs = inp.observation
    assert obs.reported_at_utc is not None
    return obs.reported_at_utc >= session.recheck_not_before_utc


def _daily_remaining(inp: TransitionInput) -> float:
    return inp.config.max_daily_runtime_s - inp.daily_runtime_s


def _no_op() -> Decision:
    return Decision(transition_id=None, new_state=None, no_op=True)


# ---------------------------------------------------------------------------
# Cross-state rows: T52 / T53 (and T5 from IDLE/FAULT)
# ---------------------------------------------------------------------------


def _integrity_lost(inp: TransitionInput) -> Decision:
    """T52: initialized Store integrity loss (§23.5)."""
    return Decision(
        transition_id="T52",
        new_state=ControllerState.FAULT,
        actions=(
            PersistState("integrity_reconstruction"),
            EmitFaultSet(FaultCode.RESTORED_FROM_UNSAFE_STATE, replaces=inp.active_fault),
        ),
        fault=FaultCode.RESTORED_FROM_UNSAFE_STATE,
    )


def _configuration_invalid(inp: TransitionInput, row: str) -> Decision:
    """T5 (IDLE) / T53 (setup): invalid configuration blocks operation."""
    return Decision(
        transition_id=row,
        new_state=ControllerState.FAULT,
        actions=(
            PersistState("configuration_invalid"),
            EmitFaultSet(FaultCode.CONFIGURATION_INVALID, replaces=inp.active_fault),
        ),
        fault=FaultCode.CONFIGURATION_INVALID,
    )


# ---------------------------------------------------------------------------
# IDLE
# ---------------------------------------------------------------------------


def _decide_idle(inp: TransitionInput) -> Decision:
    event = inp.event
    if isinstance(event, (AutoEvaluate, MoistureReport, SlotGranted)):
        return _evaluate_auto_start(inp)
    if isinstance(event, ManualStartRequested):
        return _manual_start(inp, event, row="T3")
    if isinstance(event, DisableRequested):
        return Decision(  # T4
            transition_id="T4",
            new_state=ControllerState.DISABLED,
            actions=(PersistState("disabled"),),
        )
    if isinstance(event, ConfigurationInvalid):
        return _configuration_invalid(inp, "T5")
    if isinstance(event, ExternalActuatorOn):
        if inp.external_on:
            return _no_op()  # already tracked
        return Decision(  # T54
            transition_id="T54",
            new_state=ControllerState.IDLE,
            actions=(SetExternalOn(True), AddBlocker(BlockerReason.EXTERNAL_FLOW)),
        )
    if isinstance(event, ExternalActuatorOff):
        if not inp.external_on:
            return _no_op()  # no occupancy to clear
        return Decision(  # T58
            transition_id="T58",
            new_state=ControllerState.IDLE,
            actions=(SetExternalOn(False), RemoveBlocker(BlockerReason.EXTERNAL_FLOW)),
        )
    return _no_op()


def _evaluate_auto_start(inp: TransitionInput) -> Decision:
    """T1/T2 and the non-transition slot wait (§14 note, §16)."""
    obs = inp.observation
    failed: list[str] = []
    if not inp.enabled:
        failed.append(GUARD_ENABLED)
    if not _fresh_valid(inp):
        failed.append(GUARD_FRESH)
    else:
        assert obs.value is not None
        if not obs.value < inp.config.start_threshold:
            failed.append(GUARD_START)  # equality at start does not start (§17)
    if not _interval_elapsed(inp):
        failed.append(GUARD_INTERVAL)
    if not _actuator_ready(inp):
        failed.append(GUARD_ACTUATOR)
    if not _daily_fits(inp):
        failed.append(GUARD_DAILY_FIT)

    if failed:
        # T2: record the guard result only; decline an offered grant.
        actions: tuple = ()
        if isinstance(inp.event, SlotGranted):
            actions = (ReleaseSlot(),)
        return Decision(
            transition_id="T2",
            new_state=ControllerState.IDLE,
            actions=actions,
            guard_result=GuardResult(passed=False, failed_guards=tuple(failed)),
        )
    if not (inp.resource.slot_granted and inp.resource.blockers_empty):
        # Waiting for the global slot is a resource operation, not a
        # transition (§14 note): stay IDLE with the request queued.
        return Decision(
            transition_id=None,
            new_state=None,
            actions=(RequestSlot(),),
            guard_result=GuardResult(passed=False, failed_guards=(GUARD_SLOT,)),
        )
    return _start_auto_pulse(inp, session=None)  # T1


def _start_auto_pulse(inp: TransitionInput, session: SessionContext | None) -> Decision:
    """T1 (new session) / T25 (next pulse): persist intent, ON, watchdog."""
    obs = inp.observation
    assert obs.reported_at_utc is not None
    fresh_until = obs.reported_at_utc + timedelta(seconds=inp.config.sensor_max_age_s)
    if session is None:
        identity = inp.new_session_identity
        if identity is None:
            raise ValueError("new_session_identity is required to create a session")
        generation = 1
        new_session = SessionContext(
            session_id=identity.session_id,
            owner_run_id=identity.owner_run_id,
            config_fingerprint=identity.config_fingerprint,
            mode=SessionMode.AUTO,
            started_at_utc=inp.now_utc,
            cycle=1,
            pulse_intent_at_utc=inp.now_utc,
            sensor_fresh_until_utc=fresh_until,
            sensor_freshness_watchdog_generation=generation,
            moisture_at_start=obs.value,
        )
        row = "T1"
        started: tuple = (EmitSessionStarted(),)
    else:
        generation = session.sensor_freshness_watchdog_generation + 1
        new_session = session.evolve(
            cycle=session.cycle + 1,
            pulse_intent_at_utc=inp.now_utc,
            pulse_commanded_at_utc=None,
            pulse_confirmed_at_utc=None,
            pulse_ends_at_utc=None,
            off_confirmed_at_utc=None,
            soak_ends_at_utc=None,
            recheck_not_before_utc=None,
            recheck_grace_deadline_at_utc=None,
            sensor_fresh_until_utc=fresh_until,
            sensor_freshness_watchdog_generation=generation,
        )
        row = "T25"
        started = ()
    token = WatchdogToken(generation, fresh_until)
    return Decision(
        transition_id=row,
        new_state=ControllerState.WATERING,
        actions=(
            PersistState("hazard_intent"),
            ArmWatchdog(token),  # armed no later than ON (§18.5)
            TurnOn(),
            ArmTimer(
                TimerKind.ON_CONFIRM_TIMEOUT,
                inp.now_utc + timedelta(seconds=inp.config.actuator_confirm_timeout_s),
            ),
            *started,
        ),
        session=new_session,
    )


# ---------------------------------------------------------------------------
# Manual watering (§20)
# ---------------------------------------------------------------------------


def _manual_guard_failures(inp: TransitionInput, requested_s: float) -> list[str]:
    """G-MANUAL-SAFE decomposition (§14 legend, §20.1 refusal list)."""
    failed: list[str] = []
    if not (math.isfinite(requested_s) and requested_s > 0):
        failed.append(f"{GUARD_MANUAL_SAFE}:invalid_duration")
    if not inp.enabled:
        failed.append(GUARD_ENABLED)
    if inp.session is not None:
        failed.append(f"{GUARD_MANUAL_SAFE}:active_session")
    if inp.active_fault is not None and not inp.active_fault.allows_manual:
        failed.append(GUARD_MANUAL_SENSOR)
    if not _actuator_ready(inp):
        failed.append(GUARD_ACTUATOR)
    if _daily_remaining(inp) <= 0:
        failed.append(f"{GUARD_MANUAL_SAFE}:daily_exhausted")
    if not inp.resource.blockers_empty:
        failed.append(f"{GUARD_MANUAL_SAFE}:water_resource_occupied")
    return failed


def _clamp_manual(
    inp: TransitionInput, requested_s: float
) -> tuple[float, tuple[ManualClampReason, ...]]:
    """§20.1: effective duration and every cap below the request."""
    caps = (
        (float(inp.config.manual_max_duration_s), ManualClampReason.MANUAL_MAX_DURATION),
        (float(inp.config.max_session_runtime_s), ManualClampReason.MAX_SESSION_RUNTIME),
        (_daily_remaining(inp), ManualClampReason.REMAINING_DAILY_BUDGET),
    )
    effective = min(requested_s, *(cap for cap, _ in caps))
    reasons = tuple(reason for cap, reason in caps if cap < requested_s)
    return effective, reasons


def _manual_start(inp: TransitionInput, event: ManualStartRequested, row: str) -> Decision:
    """T3 (IDLE) / T40 (sensor-only FAULT), plus refusals and slot wait."""
    failed = _manual_guard_failures(inp, event.requested_duration_s)
    if failed:
        # T41 in FAULT; a plain refusal record from IDLE (§14 has no row).
        return Decision(
            transition_id="T41" if row == "T40" else None,
            new_state=inp.state,
            guard_result=GuardResult(passed=False, failed_guards=tuple(failed)),
        )
    if not inp.resource.slot_granted:
        # Queue for the slot; the controller re-issues the manual request
        # (with its duration) when the grant is offered (§14 note).
        return Decision(
            transition_id=None,
            new_state=None,
            actions=(RequestSlot(),),
            guard_result=GuardResult(passed=False, failed_guards=(GUARD_SLOT,)),
        )
    identity = inp.new_session_identity
    if identity is None:
        raise ValueError("new_session_identity is required to create a session")
    effective, clamp_reasons = _clamp_manual(inp, event.requested_duration_s)
    retained = inp.active_fault if row == "T40" else None
    obs = inp.observation
    session = SessionContext(
        session_id=identity.session_id,
        owner_run_id=identity.owner_run_id,
        config_fingerprint=identity.config_fingerprint,
        mode=SessionMode.MANUAL,
        started_at_utc=inp.now_utc,
        cycle=0,
        pulse_intent_at_utc=inp.now_utc,
        manual_requested_duration_s=event.requested_duration_s,
        manual_effective_duration_s=effective,
        manual_clamp_reasons=clamp_reasons,
        retained_sensor_fault=retained,
        moisture_at_start=(
            obs.value if obs.classification is MoistureClassification.VALID else None
        ),
    )
    return Decision(
        transition_id=row,
        new_state=ControllerState.WATERING,
        actions=(
            PersistState("hazard_intent"),
            TurnOn(),
            ArmTimer(
                TimerKind.ON_CONFIRM_TIMEOUT,
                inp.now_utc + timedelta(seconds=inp.config.actuator_confirm_timeout_s),
            ),
            EmitSessionStarted(),
        ),
        session=session,
    )


# ---------------------------------------------------------------------------
# DISABLED
# ---------------------------------------------------------------------------


def _decide_disabled(inp: TransitionInput) -> Decision:
    event = inp.event
    if isinstance(event, EnableRequested):
        if inp.active_fault is not None:
            return Decision(  # T46
                transition_id="T46",
                new_state=ControllerState.FAULT,
                actions=(PersistState("enabled"),),
                fault=inp.active_fault,
            )
        return Decision(  # T47
            transition_id="T47",
            new_state=ControllerState.IDLE,
            actions=(PersistState("enabled"), ScheduleEvaluation()),
        )
    if isinstance(event, ExternalActuatorOn):
        if inp.external_on:
            return _no_op()
        return Decision(  # T55
            transition_id="T55",
            new_state=ControllerState.DISABLED,
            actions=(SetExternalOn(True), AddBlocker(BlockerReason.EXTERNAL_FLOW)),
        )
    if isinstance(event, ExternalActuatorOff):
        if inp.external_on:
            return Decision(  # T59
                transition_id="T59",
                new_state=ControllerState.DISABLED,
                actions=(SetExternalOn(False), RemoveBlocker(BlockerReason.EXTERNAL_FLOW)),
            )
        if inp.session is not None:
            # Delayed OFF proof for an open accounting record retained
            # across Disable (§14 preamble, AC4).
            return _close_open_accounting(inp, event.at_utc)
        return _no_op()
    if isinstance(event, OffConfirmed):
        if inp.session is not None:
            return _close_open_accounting(inp, event.at_utc)
        return _no_op()
    if isinstance(event, ManualStartRequested):
        return Decision(
            transition_id=None,
            new_state=None,
            guard_result=GuardResult(passed=False, failed_guards=(GUARD_ENABLED,)),
        )
    return _no_op()


# ---------------------------------------------------------------------------
# WATERING
# ---------------------------------------------------------------------------


def _decide_watering(inp: TransitionInput) -> Decision:
    session = inp.session
    if session is None:
        raise ValueError("WATERING requires an active session")
    event = inp.event
    pending = session.pending_termination_reason

    if isinstance(event, OnConfirmed):
        return _on_confirmed(inp, session, event)
    if isinstance(event, OnConfirmTimeout):
        if pending is not None or session.pulse_confirmed_at_utc is not None:
            # Already terminal, or confirmation arrived before the stale
            # timeout callback ran: the timeout is obsolete.
            return _no_op()
        return _commit_termination(
            inp,
            session,
            CompletionReason.ACTUATOR_FAULT,
            fault=FaultCode.ACTUATOR_ON_TIMEOUT,
            defensive=True,
        )
    if isinstance(event, PulseDeadlineReached):
        if session.mode is SessionMode.AUTO and pending is None:
            # Normal pulse end: request the one OFF; T6 finalizes on proof.
            return Decision(transition_id=None, new_state=None, actions=(ExecuteOff(),))
        return _no_op()
    if isinstance(event, ManualDeadlineReached):
        if session.mode is SessionMode.MANUAL and pending is None:
            return _commit_termination(inp, session, CompletionReason.MANUAL_COMPLETE)
        return _no_op()
    if isinstance(event, MoistureReport):
        return _watering_moisture(inp, session, event.observation)
    if isinstance(event, WatchdogFired):
        return _watchdog_fired(inp, session, event)
    if isinstance(event, StopRequested):
        if pending is not None:
            return _no_op()  # first terminal request owns the reason (§22.2)
        return _commit_termination(inp, session, CompletionReason.USER_STOP)
    if isinstance(event, DisableRequested):
        if pending is not None:
            return _no_op()
        return _commit_termination(inp, session, CompletionReason.ZONE_DISABLED)
    if isinstance(event, HomeAssistantShutdown):
        if pending is not None:
            return _no_op()
        return _commit_termination(inp, session, CompletionReason.HOME_ASSISTANT_SHUTDOWN)
    if isinstance(event, ConfigEntryReload):
        if pending is not None:
            return _no_op()
        return _commit_termination(inp, session, CompletionReason.CONFIG_RELOAD)
    if isinstance(event, ConfigChangedPrepare):
        if pending is not None:
            return _no_op()
        return _commit_termination(inp, session, CompletionReason.CONFIG_CHANGED)
    if isinstance(event, ActuatorBecameUnavailable):
        if pending is not None:
            # Unavailability during OFF handling is not proof of OFF; the
            # running OFF operation continues (§11.3).
            return _no_op()
        return _commit_termination(
            inp,
            session,
            CompletionReason.ACTUATOR_FAULT,
            fault=FaultCode.ACTUATOR_UNAVAILABLE,
            defensive=True,
        )
    if isinstance(event, ExternalActuatorOff):
        if pending is not None:
            # OFF evidence for the already committed termination.
            return _finalize_watering(inp, session, pending, event.at_utc)
        # T16: external OFF is an intentional stop with trustworthy closure
        # evidence; the idempotent defensive OFF is still issued (§19.1).
        return _finalize_watering(
            inp,
            session,
            CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE,
            event.at_utc,
            extra_actions=(ExecuteOff(defensive=True),),
        )
    if isinstance(event, OffConfirmed):
        if pending is not None:
            return _finalize_watering(inp, session, pending, event.at_utc)
        if session.mode is SessionMode.AUTO:
            return _pulse_off_to_soaking(inp, session, event.at_utc)  # T6
        return _finalize_watering(inp, session, CompletionReason.MANUAL_COMPLETE, event.at_utc)
    if isinstance(event, OffNotConfirmed):
        return _off_not_confirmed(inp, session)
    if isinstance(event, StartupPersistedWatering):
        return _startup_persisted_watering(inp, session, event)
    if isinstance(event, ManualStartRequested):
        return Decision(
            transition_id=None,
            new_state=None,
            guard_result=GuardResult(
                passed=False, failed_guards=(f"{GUARD_MANUAL_SAFE}:active_session",)
            ),
        )
    return _no_op()


def _on_confirmed(inp: TransitionInput, session: SessionContext, event: OnConfirmed) -> Decision:
    """§11.2 step 6: record confirmation and arm the absolute deadline."""
    if session.mode is SessionMode.AUTO:
        ends = event.at_utc + timedelta(seconds=inp.config.pulse_duration_s)
        timer = TimerKind.PULSE_END
    else:
        assert session.manual_effective_duration_s is not None
        ends = event.at_utc + timedelta(seconds=session.manual_effective_duration_s)
        timer = TimerKind.MANUAL_END
    new_session = session.evolve(pulse_confirmed_at_utc=event.at_utc, pulse_ends_at_utc=ends)
    actions: tuple = (PersistState("on_confirmed"),)
    if session.pending_termination_reason is None:
        actions = (*actions, ArmTimer(timer, ends))
    return Decision(transition_id=None, new_state=None, actions=actions, session=new_session)


def _watering_moisture(
    inp: TransitionInput, session: SessionContext, obs: MoistureObservation
) -> Decision:
    if session.mode is SessionMode.MANUAL:
        # T12: bookkeeping only; sensor state never terminates MANUAL (§10.4).
        return Decision(transition_id="T12", new_state=ControllerState.WATERING)
    if session.pending_termination_reason is not None:
        return _no_op()  # terminal request already committed (T56 guard)
    if obs.classification is MoistureClassification.VALID:
        assert obs.reported_at_utc is not None
        new_fresh = obs.reported_at_utc + timedelta(seconds=inp.config.sensor_max_age_s)
        current = session.sensor_fresh_until_utc
        if current is not None and new_fresh < current:
            # An older replayed report can never shorten the deadline.
            return _no_op()
        generation = session.sensor_freshness_watchdog_generation + 1
        token = WatchdogToken(generation, new_fresh)
        return Decision(  # T56
            transition_id="T56",
            new_state=ControllerState.WATERING,
            actions=(ArmWatchdog(token),),
            session=session.evolve(
                sensor_fresh_until_utc=new_fresh,
                sensor_freshness_watchdog_generation=generation,
            ),
        )
    if obs.classification is MoistureClassification.INVALID:
        return _commit_termination(
            inp, session, CompletionReason.SENSOR_FAULT, fault=FaultCode.SENSOR_INVALID
        )
    if obs.classification is MoistureClassification.UNAVAILABLE:
        return _commit_termination(
            inp, session, CompletionReason.SENSOR_FAULT, fault=FaultCode.SENSOR_UNAVAILABLE
        )
    # STALE classification (fallback-scan replay): staleness of flowing AUTO
    # water is decided solely by the freshness watchdog (§18.5).
    return _no_op()


def _watchdog_fired(
    inp: TransitionInput, session: SessionContext, event: WatchdogFired
) -> Decision:
    """§18.5 exact callback algorithm."""
    if session.mode is not SessionMode.AUTO:
        return _no_op()  # step 2: not WATERING(AUTO)
    if session.pending_termination_reason is not None:
        return _no_op()  # a terminal request is already committed
    if inp.armed_watchdog is None or event.token != inp.armed_watchdog:
        return _no_op()  # step 3: superseded token
    assert session.sensor_fresh_until_utc is not None
    if session.sensor_fresh_until_utc > inp.now_utc:
        # Step 5: not expired; ensure the current deadline is armed.
        return Decision(
            transition_id=None,
            new_state=None,
            actions=(
                ArmWatchdog(
                    WatchdogToken(
                        session.sensor_freshness_watchdog_generation,
                        session.sensor_fresh_until_utc,
                    )
                ),
            ),
        )
    # Step 6: genuine expiry.
    return _commit_termination(
        inp, session, CompletionReason.SENSOR_FAULT, fault=FaultCode.SENSOR_STALE
    )


def _commit_termination(
    inp: TransitionInput,
    session: SessionContext,
    reason: CompletionReason,
    fault: FaultCode | None = None,
    defensive: bool = False,
) -> Decision:
    """Commit the first terminal request and request the one OFF (§22.2)."""
    actions: list = [PersistState("termination_committed")]
    if fault is not None:
        actions.append(EmitFaultSet(fault, replaces=session.retained_sensor_fault))
    actions.append(ExecuteOff(defensive=defensive))
    return Decision(
        transition_id=None,
        new_state=None,
        actions=tuple(actions),
        fault=fault,
        session=session.evolve(pending_termination_reason=reason),
    )


def _close_runtime(
    session: SessionContext, off_at: datetime, reason: CompletionReason
) -> SessionContext:
    """Close the accounting interval (§19.1/§19.2 anchors)."""
    if reason is CompletionReason.RESTART_RECOVERY:
        anchor = session.pulse_intent_at_utc
    else:
        anchor = session.pulse_commanded_at_utc
    delta = 0.0 if anchor is None else max(0.0, (off_at - anchor).total_seconds())
    return session.evolve(
        off_confirmed_at_utc=off_at,
        session_runtime_s=session.session_runtime_s + delta,
    )


def _pulse_off_to_soaking(
    inp: TransitionInput, session: SessionContext, off_at: datetime
) -> Decision:
    """T6: confirmed normal AUTO pulse OFF arms the full soak (§18.1)."""
    soak_ends = off_at + timedelta(seconds=inp.config.soak_duration_s)
    grace = soak_ends + timedelta(seconds=inp.config.sensor_max_age_s)
    closed = _close_runtime(session, off_at, CompletionReason.TARGET_REACHED)
    new_session = closed.evolve(
        soak_ends_at_utc=soak_ends,
        recheck_not_before_utc=soak_ends,
        recheck_grace_deadline_at_utc=grace,
    )
    return Decision(
        transition_id="T6",
        new_state=ControllerState.SOAKING,
        actions=(
            PersistState("soaking"),
            ArmTimer(TimerKind.SOAK_END, soak_ends),
            # §21: the soaking zone releases; when a qualifying recheck later
            # needs the next pulse, its RequestSlot joins the queue tail.
            ReleaseSlot(),
        ),
        session=new_session,
    )


def _finalize_watering(
    inp: TransitionInput,
    session: SessionContext,
    reason: CompletionReason,
    off_at: datetime,
    extra_actions: tuple = (),
) -> Decision:
    """Finalize a committed WATERING exit on OFF evidence (§14 rows)."""
    closed = _close_runtime(session, off_at, reason)
    if reason is CompletionReason.MANUAL_COMPLETE:
        return _finalize_manual_complete(inp, closed, extra_actions)
    if reason is CompletionReason.RESTART_RECOVERY:
        row = "T48"
    elif reason is CompletionReason.SENSOR_FAULT:
        assert inp.active_fault is not None
        row = _SENSOR_FAULT_ROWS[inp.active_fault]
    elif reason is CompletionReason.ACTUATOR_FAULT:
        row = "T13" if inp.active_fault is FaultCode.ACTUATOR_UNAVAILABLE else "T14"
    else:
        row = _CANCELLATION_ROWS[reason]
    destination, dest_fault, clear_actions, clear_fault = _post_destination(inp, closed, reason)
    secondary = None
    if reason is CompletionReason.ACTUATOR_FAULT and closed.retained_sensor_fault is not None:
        # MF5: the actuator fault supersedes; sensor context stays secondary.
        secondary = closed.retained_sensor_fault
    return Decision(
        transition_id=row,
        new_state=destination,
        actions=(
            *extra_actions,
            PersistState("session_finalized"),
            ReleaseSlot(),
            EmitSessionFinished(),
            *clear_actions,
        ),
        reason=reason,
        fault=dest_fault,
        secondary_fault=secondary,
        clear_fault=clear_fault,
        clear_session=True,
        final_session=closed,
    )


def _finalize_manual_complete(
    inp: TransitionInput, closed: SessionContext, extra_actions: tuple
) -> Decision:
    """T7/T8/T9: POST(fault) evaluated at terminal OFF confirmation (§20.3)."""
    retained = closed.retained_sensor_fault
    base_actions = (
        *extra_actions,
        PersistState("session_finalized"),
        ReleaseSlot(),
        EmitSessionFinished(),
    )
    if retained is None:
        row, destination = "T7", ControllerState.IDLE
        actions: tuple = base_actions
        fault = None
        clear_fault = False
    elif _fresh_valid(inp):
        # T9: recovered; the fault clears after the finish event (§20.3, §32).
        row, destination = "T9", ControllerState.IDLE
        actions = (*base_actions, EmitFaultCleared(retained))
        fault = None
        clear_fault = True
    else:
        row, destination = "T8", ControllerState.FAULT
        actions = base_actions
        fault = retained
        clear_fault = False
    if not inp.enabled:
        destination = ControllerState.DISABLED  # Disable controls state (§22.3)
    return Decision(
        transition_id=row,
        new_state=destination,
        actions=actions,
        reason=CompletionReason.MANUAL_COMPLETE,
        fault=fault,
        clear_fault=clear_fault,
        clear_session=True,
        final_session=closed,
    )


def _post_destination(
    inp: TransitionInput, closed: SessionContext, reason: CompletionReason
) -> tuple[ControllerState, FaultCode | None, tuple, bool]:
    """POST(retained/new fault) rule (§14 legend) plus Disable override."""
    if reason is CompletionReason.ZONE_DISABLED:
        return ControllerState.DISABLED, None, (), False
    if reason in (CompletionReason.SENSOR_FAULT, CompletionReason.ACTUATOR_FAULT):
        destination = ControllerState.DISABLED if not inp.enabled else ControllerState.FAULT
        return destination, inp.active_fault, (), False
    if not inp.enabled:
        return ControllerState.DISABLED, None, (), False
    retained = closed.retained_sensor_fault
    new_fault = inp.active_fault if inp.active_fault is not retained else None
    if new_fault is not None:
        return ControllerState.FAULT, new_fault, (), False
    if retained is not None:
        if _fresh_valid(inp):
            # Recovered at completion: fault clears after the finish event.
            return ControllerState.IDLE, None, (EmitFaultCleared(retained),), True
        return ControllerState.FAULT, retained, (), False
    return ControllerState.IDLE, None, (), False


def _off_not_confirmed(inp: TransitionInput, session: SessionContext) -> Decision:
    """T15 (or T49 during restart recovery): OFF unproven after retries."""
    pending = session.pending_termination_reason
    if pending is CompletionReason.RESTART_RECOVERY:
        row = "T49"
        committed = CompletionReason.RESTART_RECOVERY
    else:
        row = "T15"
        committed = CompletionReason.ACTUATOR_FAULT  # supersedes (§22.2)
    new_session = session.evolve(
        pending_termination_reason=committed,
        runtime_estimated=True,
        runtime_estimation_reason=RuntimeEstimationReason.OFF_UNCONFIRMED,
    )
    return Decision(
        transition_id=row,
        new_state=ControllerState.FAULT,
        actions=(
            PersistState("off_unconfirmed"),
            AddBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED),
            EmitFaultSet(FaultCode.ACTUATOR_OFF_TIMEOUT, replaces=inp.active_fault),
        ),
        reason=committed,
        fault=FaultCode.ACTUATOR_OFF_TIMEOUT,
        secondary_fault=session.retained_sensor_fault,
        session=new_session,
    )


def _startup_persisted_watering(
    inp: TransitionInput, session: SessionContext, event: StartupPersistedWatering
) -> Decision:
    """§25.2: never resume; conservative estimate; defensive OFF as needed."""
    if event.finding is ActuatorFinding.OFF:
        # Found OFF: estimate intent -> reconciliation time and finalize now.
        estimated = session.evolve(
            pending_termination_reason=CompletionReason.RESTART_RECOVERY,
            runtime_estimated=True,
            runtime_estimation_reason=RuntimeEstimationReason.RESTART_FOUND_OFF_UNKNOWN_STOP,
        )
        return _finalize_watering(inp, estimated, CompletionReason.RESTART_RECOVERY, inp.now_utc)
    if event.finding is ActuatorFinding.ON:
        estimation = RuntimeEstimationReason.RESTART_FOUND_ON
    else:
        estimation = RuntimeEstimationReason.OFF_UNCONFIRMED
    committed = session.evolve(
        pending_termination_reason=CompletionReason.RESTART_RECOVERY,
        runtime_estimated=True,
        runtime_estimation_reason=estimation,
    )
    return Decision(
        transition_id=None,
        new_state=None,
        actions=(
            PersistState("restart_recovery"),
            AddBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED),
            ExecuteOff(defensive=True),
        ),
        session=committed,
    )


# ---------------------------------------------------------------------------
# SOAKING
# ---------------------------------------------------------------------------


def _decide_soaking(inp: TransitionInput) -> Decision:
    session = inp.session
    if session is None:
        raise ValueError("SOAKING requires an active session")
    event = inp.event
    pending = session.pending_termination_reason

    if pending is not None:
        # A termination (external interference) is committed; only OFF
        # evidence may advance the session (§22.2 first-terminal rule).
        if isinstance(event, (OffConfirmed, ExternalActuatorOff)):
            at = event.at_utc
            return _finalize_soaking_external(inp, session, at)  # T33
        if isinstance(event, OffNotConfirmed):
            return _soaking_off_not_confirmed(inp, session)  # T34
        return _no_op()

    if isinstance(event, MoistureReport):
        return _soaking_moisture(inp, session, event.observation)
    if isinstance(event, (SoakDeadlineReached, AutoEvaluate, SlotGranted)):
        return _soaking_deadline_or_evaluate(inp, session, event)
    if isinstance(event, GraceDeadlineReached):
        return _soaking_grace(inp, session)
    if isinstance(event, ActuatorBecameUnavailable):
        # T32: water was already proven OFF earlier; finalize immediately.
        return _finalize_soaking_fault(
            inp, session, "T32", CompletionReason.ACTUATOR_FAULT, FaultCode.ACTUATOR_UNAVAILABLE
        )
    if isinstance(event, ExternalActuatorOn):
        # Commit interference; T33/T34 finalize on OFF evidence (§11.4).
        return Decision(
            transition_id=None,
            new_state=None,
            actions=(
                PersistState("external_interference"),
                AddBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED),
                ExecuteOff(defensive=True),
            ),
            session=session.evolve(
                pending_termination_reason=CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE,
                last_recheck_value=None,  # invalidate the soak's reports
            ),
        )
    if isinstance(event, StopRequested):
        return _finalize_soaking_cancel(
            inp, session, "T35", CompletionReason.USER_STOP, ControllerState.IDLE
        )
    if isinstance(event, DisableRequested):
        return _finalize_soaking_cancel(
            inp, session, "T36", CompletionReason.ZONE_DISABLED, ControllerState.DISABLED
        )
    if isinstance(event, HomeAssistantShutdown):
        # T37: persist the active soak unchanged; no completion.
        return Decision(
            transition_id="T37",
            new_state=ControllerState.SOAKING,
            actions=(PersistState("soaking_preserved"),),
        )
    if isinstance(event, ConfigEntryReload):
        return _finalize_soaking_cancel(
            inp, session, "T38", CompletionReason.CONFIG_RELOAD, ControllerState.IDLE
        )
    if isinstance(event, ConfigChangedPrepare):
        return _finalize_soaking_cancel(
            inp, session, "T39", CompletionReason.CONFIG_CHANGED, ControllerState.IDLE
        )
    if isinstance(event, StartupPersistedSoaking):
        return _startup_persisted_soaking(inp, session, event)
    if isinstance(event, ManualStartRequested):
        return Decision(
            transition_id=None,
            new_state=None,
            guard_result=GuardResult(
                passed=False, failed_guards=(f"{GUARD_MANUAL_SAFE}:active_session",)
            ),
        )
    return _no_op()


def _soaking_moisture(
    inp: TransitionInput, session: SessionContext, obs: MoistureObservation
) -> Decision:
    assert session.soak_ends_at_utc is not None
    effective_at = obs.reported_at_utc if obs.reported_at_utc is not None else inp.now_utc
    if effective_at < session.soak_ends_at_utc:
        # T22: pre-deadline reports update observability only (§18.4).
        return Decision(transition_id="T22", new_state=ControllerState.SOAKING)
    if obs.classification is MoistureClassification.INVALID:
        return _finalize_soaking_fault(
            inp, session, "T29", CompletionReason.SENSOR_FAULT, FaultCode.SENSOR_INVALID
        )
    if obs.classification is MoistureClassification.UNAVAILABLE:
        return _finalize_soaking_fault(
            inp, session, "T30", CompletionReason.SENSOR_FAULT, FaultCode.SENSOR_UNAVAILABLE
        )
    if _post_qualifies(inp):
        return _soaking_recheck(inp, session)
    # Post-deadline but not qualifying (stale replay, lapsed freshness, or a
    # report from before the soak deadline): keep waiting; the grace
    # deadline arbitrates (§18.4).
    return _no_op()


def _soaking_deadline_or_evaluate(
    inp: TransitionInput, session: SessionContext, event: object
) -> Decision:
    assert session.soak_ends_at_utc is not None
    if inp.now_utc < session.soak_ends_at_utc:
        return _no_op()  # early trigger; nothing can decide yet
    if _post_qualifies(inp):
        return _soaking_recheck(inp, session)
    if isinstance(event, SlotGranted):
        # Guards no longer pass on the offered grant; decline it (§14 note).
        return Decision(
            transition_id=None,
            new_state=None,
            actions=(ReleaseSlot(),),
            guard_result=GuardResult(passed=False, failed_guards=(GUARD_POST,)),
        )
    if isinstance(event, SoakDeadlineReached):
        assert session.recheck_grace_deadline_at_utc is not None
        # T23: arm/retain the bounded grace wait.
        return Decision(
            transition_id="T23",
            new_state=ControllerState.SOAKING,
            actions=(ArmTimer(TimerKind.GRACE, session.recheck_grace_deadline_at_utc),),
        )
    return _no_op()


def _soaking_grace(inp: TransitionInput, session: SessionContext) -> Decision:
    """Grace deadline: re-check the current observation before faulting."""
    if _post_qualifies(inp):
        # A report observed exactly at the grace deadline qualifies (§18.4).
        return _soaking_recheck(inp, session)
    obs = inp.observation
    assert session.soak_ends_at_utc is not None
    effective_at = obs.reported_at_utc if obs.reported_at_utc is not None else inp.now_utc
    if (
        obs.classification is MoistureClassification.INVALID
        and effective_at >= session.soak_ends_at_utc
    ):
        return _finalize_soaking_fault(
            inp, session, "T29", CompletionReason.SENSOR_FAULT, FaultCode.SENSOR_INVALID
        )
    if obs.classification is MoistureClassification.UNAVAILABLE:
        return _finalize_soaking_fault(
            inp, session, "T30", CompletionReason.SENSOR_FAULT, FaultCode.SENSOR_UNAVAILABLE
        )
    return _finalize_soaking_fault(  # T31
        inp, session, "T31", CompletionReason.SENSOR_FAULT, FaultCode.SENSOR_STALE
    )


def _soaking_recheck(inp: TransitionInput, session: SessionContext) -> Decision:
    """Qualifying recheck: T24-T28, T32, T25, or a slot wait (§18.4, §14)."""
    obs = inp.observation
    assert obs.value is not None
    updated = session.evolve(last_recheck_value=obs.value)
    if obs.value >= inp.config.target_threshold:
        # T24: equality at the target completes (§17).
        return _finalize_soaking_completion(inp, updated, "T24", CompletionReason.TARGET_REACHED)
    if not updated.cycle < inp.config.max_cycles:
        return _finalize_soaking_completion(inp, updated, "T26", CompletionReason.MAX_CYCLES)
    if not _session_fits(inp, updated):
        return _finalize_soaking_completion(
            inp, updated, "T27", CompletionReason.MAX_SESSION_RUNTIME
        )
    if not _daily_fits(inp):
        return _finalize_soaking_completion(
            inp, updated, "T28", CompletionReason.DAILY_RUNTIME_LIMIT
        )
    if not inp.actuator.available:
        return _finalize_soaking_fault(
            inp, updated, "T32", CompletionReason.ACTUATOR_FAULT, FaultCode.ACTUATOR_UNAVAILABLE
        )
    if not (inp.resource.slot_granted and inp.resource.blockers_empty and inp.actuator.proven_off):
        # Wait for the slot/blockers; every guard re-runs on the grant.
        return Decision(
            transition_id=None,
            new_state=None,
            actions=(RequestSlot(),),
            guard_result=GuardResult(passed=False, failed_guards=(GUARD_SLOT,)),
            session=updated,
        )
    return _start_auto_pulse(inp, session=updated)  # T25


def _finalize_soaking_completion(
    inp: TransitionInput, session: SessionContext, row: str, reason: CompletionReason
) -> Decision:
    destination = ControllerState.IDLE if inp.enabled else ControllerState.DISABLED
    return Decision(
        transition_id=row,
        new_state=destination,
        actions=(PersistState("session_finalized"), ReleaseSlot(), EmitSessionFinished()),
        reason=reason,
        clear_session=True,
        final_session=session,
    )


def _finalize_soaking_fault(
    inp: TransitionInput,
    session: SessionContext,
    row: str,
    reason: CompletionReason,
    fault: FaultCode,
) -> Decision:
    return Decision(
        transition_id=row,
        new_state=ControllerState.FAULT,
        actions=(
            PersistState("session_finalized"),
            EmitFaultSet(fault, replaces=session.retained_sensor_fault),
            ReleaseSlot(),
            EmitSessionFinished(),
        ),
        reason=reason,
        fault=fault,
        clear_session=True,
        final_session=session,
    )


def _finalize_soaking_cancel(
    inp: TransitionInput,
    session: SessionContext,
    row: str,
    reason: CompletionReason,
    destination: ControllerState,
) -> Decision:
    return Decision(
        transition_id=row,
        new_state=destination,
        actions=(
            PersistState("session_finalized"),
            ExecuteOff(defensive=True),  # idempotent OFF assurance
            ReleaseSlot(),
            EmitSessionFinished(),
        ),
        reason=reason,
        clear_session=True,
        final_session=session,
    )


def _finalize_soaking_external(
    inp: TransitionInput, session: SessionContext, off_at: datetime
) -> Decision:
    """T33: defensive OFF confirmed after external ON during SOAKING."""
    closed = _close_runtime(session, off_at, CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE)
    return Decision(
        transition_id="T33",
        new_state=ControllerState.IDLE if inp.enabled else ControllerState.DISABLED,
        actions=(
            PersistState("session_finalized"),
            RemoveBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED),
            ReleaseSlot(),
            EmitSessionFinished(),
        ),
        reason=CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE,
        clear_session=True,
        final_session=closed,
    )


def _soaking_off_not_confirmed(inp: TransitionInput, session: SessionContext) -> Decision:
    """T34: external ON during SOAKING and OFF cannot be proven."""
    new_session = session.evolve(
        pending_termination_reason=CompletionReason.ACTUATOR_FAULT,
        runtime_estimated=True,
        runtime_estimation_reason=RuntimeEstimationReason.OFF_UNCONFIRMED,
    )
    return Decision(
        transition_id="T34",
        new_state=ControllerState.FAULT,
        actions=(
            PersistState("off_unconfirmed"),
            EmitFaultSet(FaultCode.ACTUATOR_OFF_TIMEOUT, replaces=inp.active_fault),
        ),
        reason=CompletionReason.ACTUATOR_FAULT,
        fault=FaultCode.ACTUATOR_OFF_TIMEOUT,
        secondary_fault=session.retained_sensor_fault,
        session=new_session,
    )


def _startup_persisted_soaking(
    inp: TransitionInput, session: SessionContext, event: StartupPersistedSoaking
) -> Decision:
    if event.trusted:
        if event.current_run_id is None:
            raise ValueError("trusted SOAKING adoption requires current_run_id")
        assert session.soak_ends_at_utc is not None
        assert session.recheck_grace_deadline_at_utc is not None
        rebased = session.evolve(owner_run_id=event.current_run_id)
        if session.soak_ends_at_utc > inp.now_utc:
            timers: tuple = (ArmTimer(TimerKind.SOAK_END, session.soak_ends_at_utc),)
        elif session.recheck_grace_deadline_at_utc > inp.now_utc:
            timers = (ArmTimer(TimerKind.GRACE, session.recheck_grace_deadline_at_utc),)
        else:
            # Both deadlines passed offline: the controller feeds
            # GraceDeadlineReached immediately after adoption (§25.3).
            timers = ()
        return Decision(  # T50
            transition_id="T50",
            new_state=ControllerState.SOAKING,
            actions=(PersistState("soaking_owner_rebase"), *timers),
            session=rebased,
        )
    # T51: terminate the old session; never rebase first.
    if event.unsafe_fault is not None:
        return Decision(
            transition_id="T51",
            new_state=ControllerState.FAULT,
            actions=(
                PersistState("session_finalized"),
                EmitFaultSet(event.unsafe_fault, replaces=inp.active_fault),
                EmitSessionFinished(),
            ),
            reason=CompletionReason.RESTART_RECOVERY,
            fault=event.unsafe_fault,
            clear_session=True,
            final_session=session,
        )
    return Decision(
        transition_id="T51",
        new_state=ControllerState.IDLE if inp.enabled else ControllerState.DISABLED,
        actions=(PersistState("session_finalized"), EmitSessionFinished()),
        reason=CompletionReason.RESTART_RECOVERY,
        clear_session=True,
        final_session=session,
    )


# ---------------------------------------------------------------------------
# FAULT
# ---------------------------------------------------------------------------


def _decide_fault(inp: TransitionInput) -> Decision:
    event = inp.event
    fault = inp.active_fault

    if isinstance(event, ManualStartRequested):
        return _manual_start(inp, event, row="T40")
    if isinstance(event, MoistureReport):
        return _fault_auto_clear_check(inp, fault)
    if isinstance(event, ExternalActuatorOff):
        if inp.session is not None:
            # Delayed OFF proof closes the open accounting record (§11.3).
            return _close_open_accounting(inp, event.at_utc)
        if inp.external_on:
            # §11.4: external occupancy bookkeeping continues in FAULT.
            return Decision(
                transition_id=None,
                new_state=None,
                actions=(SetExternalOn(False), RemoveBlocker(BlockerReason.EXTERNAL_FLOW)),
            )
        return _fault_auto_clear_check(inp, fault)
    if isinstance(event, OffConfirmed):
        if inp.session is not None:
            return _close_open_accounting(inp, event.at_utc)
        return _no_op()
    if isinstance(event, ExternalActuatorOn):
        if inp.external_on:
            return _no_op()
        # Non-session FAULT external ON adds external_flow (§11.4).
        return Decision(
            transition_id=None,
            new_state=None,
            actions=(SetExternalOn(True), AddBlocker(BlockerReason.EXTERNAL_FLOW)),
        )
    if isinstance(event, ClearFaultRequested):
        return _clear_fault_request(inp, fault)
    if isinstance(event, DisableRequested):
        return Decision(  # T45: retain fault metadata
            transition_id="T45",
            new_state=ControllerState.DISABLED,
            actions=(PersistState("disabled"),),
        )
    if isinstance(event, ConfigurationInvalid):
        if fault is FaultCode.CONFIGURATION_INVALID:
            return _no_op()
        return _configuration_invalid(inp, "T5")
    return _no_op()


def _fault_auto_clear_check(inp: TransitionInput, fault: FaultCode | None) -> Decision:
    """T42: auto-clear when the condition is verified and no session exists."""
    if fault is None or not fault.auto_clears or inp.session is not None:
        return _no_op()
    # Sensor faults resolve on VALID+fresh; ACTUATOR_UNAVAILABLE and
    # ACTUATOR_ON_TIMEOUT resolve on available + observed OFF (§26.1).
    resolved = _fresh_valid(inp) if fault.is_sensor_only else _actuator_ready(inp)
    if not resolved:
        return _no_op()
    return Decision(
        transition_id="T42",
        new_state=ControllerState.IDLE,
        actions=(PersistState("fault_cleared"), EmitFaultCleared(fault)),
        clear_fault=True,
    )


def _clear_fault_request(inp: TransitionInput, fault: FaultCode | None) -> Decision:
    """T43/T44: acknowledgement per the §26.1 matrix and OFF proof (§21)."""
    if fault is None:
        return _no_op()
    if fault.requires_reconfigure:
        return Decision(  # T44: clear_fault is always refused (§26.1)
            transition_id="T44",
            new_state=ControllerState.FAULT,
            guard_result=GuardResult(passed=False, failed_guards=("fault-requires-reconfigure",)),
        )
    # Sensor faults resolve on VALID+fresh; actuator and integrity faults
    # require observed terminal OFF before acknowledgement (§21, §26.1).
    resolved = _fresh_valid(inp) if fault.is_sensor_only else _actuator_ready(inp)
    if not resolved:
        return Decision(
            transition_id="T44",
            new_state=ControllerState.FAULT,
            guard_result=GuardResult(passed=False, failed_guards=("fault-condition-unresolved",)),
        )
    return Decision(
        transition_id="T43",
        new_state=ControllerState.IDLE,
        actions=(PersistState("fault_cleared"), EmitFaultCleared(fault)),
        clear_fault=True,
    )


# ---------------------------------------------------------------------------
# Delayed OFF-proof accounting closure (§14 preamble, §11.3, AC4)
# ---------------------------------------------------------------------------


def _close_open_accounting(inp: TransitionInput, off_at: datetime) -> Decision:
    """Close an open (OFF-unconfirmed) accounting record on later OFF proof.

    The committed reason and fault remain; only now do session_finished and
    last_session_end_utc materialize, using the later, safer timestamp.
    """
    session = inp.session
    assert session is not None
    reason = session.pending_termination_reason
    assert reason is not None
    closed = _close_runtime(session, off_at, reason)
    return Decision(
        transition_id=None,
        new_state=None,
        actions=(
            PersistState("delayed_accounting_closed"),
            RemoveBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED),
            ReleaseSlot(),
            EmitSessionFinished(),
        ),
        reason=reason,
        clear_session=True,
        final_session=closed,
    )
